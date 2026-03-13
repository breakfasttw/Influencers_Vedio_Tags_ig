# 統一計算社群分群 (模組化參數調校版 12+1 合併邏輯)
# input: influencer_bonding_matrix.csv (加權連結矩陣)
# output: community_master.json (各演算法結果與 Q 度)

import pandas as pd
import networkx as nx
from networkx.algorithms import community
import igraph as ig
import json
import os
import numpy as np
from config import *

# ==========================================
# 0. 共同設定與資料載入函式
# ==========================================
def load_and_prepare_graphs():
    """
    讀取 Bonding Matrix 並產製適合不同套件(igraph, NetworkX)的圖形物件。
    """
    matrix_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    if not os.path.exists(matrix_path):
        raise FileNotFoundError(f"找不到矩陣檔案 {matrix_path}")
        
    full_bonding_df = pd.read_csv(matrix_path, index_col=0)
    
    # --- [關鍵修正]：僅保留有互動強度的節點參與分群 ---
    # 計算每個 Row 的加總，大於 0 代表有標記他人或被標記
    active_mask = full_bonding_df.sum(axis=1) > 0
    bonding_df = full_bonding_df.loc[active_mask, active_mask]
    
    node_names = bonding_df.index.tolist()
    print(f"   [資訊] 原始網紅數: {len(full_bonding_df)}, 參與分群網紅數: {len(node_names)}")
    
    # --- 準備 igraph 物件 (用於 Walktrap) ---
    upper_tri = np.triu(bonding_df.values, k=1)
    sources, targets = np.where(upper_tri > 0)
    weights = upper_tri[sources, targets]
    
    g_ig = ig.Graph(n=len(node_names), edges=list(zip(sources, targets)), directed=False)
    g_ig.vs['name'] = node_names
    g_ig.es['weight'] = weights

    # --- 準備 NetworkX 物件 (用於 Louvain/Greedy) ---
    G_nx = nx.Graph()
    G_nx.add_nodes_from(node_names)
    for (s, t), w in zip(list(zip(sources, targets)), weights):
        G_nx.add_edge(node_names[s], node_names[t], weight=w)

    return G_nx, g_ig, node_names

# ==========================================
# 1. 分群上限設定，搭配 config 的 CUSTOM_COLORS
# ==========================================
def merge_communities(communities):
    """
    將分群結果按規模排序，保留前 12 大，其餘合併為第 13 群。
    """
    MAX_CORE_GROUPS = 12 # 全域參數設定
    
    # 1. 依照人數從多到少排序
    sorted_comm = sorted(communities, key=len, reverse=True)
    
    if len(sorted_comm) <= MAX_CORE_GROUPS:
        return sorted_comm
    
    # 2. 拆分前 12 群與剩下的群組
    top_12 = sorted_comm[:MAX_CORE_GROUPS]
    others = sorted_comm[MAX_CORE_GROUPS:]
    
    # 3. 將剩下的所有人合併成一個 List (第 13 群)
    merged_group_13 = []
    for comm in others:
        merged_group_13.extend(comm)
        
    top_12.append(merged_group_13)
    return top_12

# ==========================================
# 2. WalkTrap 演算法函式
# ==========================================
def compute_walktrap_algorithm(g_ig, node_names):
    """
    Walktrap 演算法：基於隨機走訪(Random Walk)的社群偵測。
    
    [可調參數說明]：
    - steps (預設 4)：隨機走訪的步數。
        * 步數短(3-4)：能捕捉到更緊密、微小的社交核心。
        * 步數長(5-8)：會將鄰近的小社群合併為較大的生活圈。
    - weights: 使用加權計算，次數越高越容易被困在同一個群體。
    """
    print("-> 正在執行 Walktrap 運算...")
    
    # 核心參數：steps
    walk_steps = 4 
    
    # 執行運算
    dendrogram = g_ig.community_walktrap(weights='weight', steps=walk_steps)
    clusters = dendrogram.as_clustering() # 自動選取 Modularity 最高處切割
    
    # 計算模組化 Q 度 (加權版)
    q_score = g_ig.modularity(clusters, weights='weight')
    
    # 轉換為標準名單格式
    raw_communities = [list(np.array(node_names)[list(c)]) for c in clusters]
    return {
        "modularity": q_score, 
        "communities": merge_communities(raw_communities), 
        "params": {"steps": walk_steps}
    }

# ==========================================
# 3. Louvain 演算法函式
# ==========================================
def compute_louvain_algorithm(G_nx):
    """
    Louvain 演算法：基於多層級模組化最大化的啟發式演算法。
    
    [可調參數說明]：
    - weight: 指定邊權重欄位。
    - resolution (預設 1.0)：解析度參數，控制分群規模。
        * resolution > 1.0：偏向分出「更多且更小」的社群（細膩捕捉互動事實）。
        * resolution < 1.0：偏向分出「更少且更大」的社群（區分廣義生活圈）。
    - seed: 隨機種子，確保結果可被重複驗證。
    """
    print("-> 正在執行 Louvain 運算...")
    
    # 核心參數
    res_val = 1.0 
    
    # 執行運算 (NetworkX 3.0+ 內建支持加權)
    louvain_comm_list = community.louvain_communities(
        G_nx, 
        weight='weight', 
        resolution=res_val, 
        seed=RANDOM_SEED
    )
    q_score = community.modularity(G_nx, louvain_comm_list, weight='weight')
    
    # 計算模組化 Q 度(注意：NetworkX 回傳 set，需轉為 list)
    raw_communities = [list(c) for c in louvain_comm_list]
    return {
        "modularity": q_score, 
        "communities": merge_communities(raw_communities),
        "params": {"resolution": res_val}
    }

# ==========================================
# 4. Greedy Modularity 演算法函式
# ==========================================
def compute_greedy_algorithm(G_nx):
    """
    Greedy Modularity (Clauset-Newman-Moore)：貪婪搜尋最大化 Q 度的分群方式。
    
    [可調參數說明]：
    - weight: 指定邊權重欄位。
    - resolution (預設 1.0)：
        * 影響力與 Louvain 類似，但在中小型網路(如 200 人)中，Greedy 通常會分得比 Louvain 更「大」一些。
    """
    print("-> 正在執行 Greedy Modularity 運算...")
    
    # 核心參數
    res_val = 1.0
    
    # 執行運算
    greedy_comm_iter = community.greedy_modularity_communities(
        G_nx, 
        weight='weight',
        resolution=res_val
    )
    
    # 計算模組化 Q 度
    q_score = community.modularity(G_nx, greedy_comm_iter, weight='weight')
    raw_communities = [list(c) for c in greedy_comm_iter]
    return {
        "modularity": q_score, 
        "communities": merge_communities(raw_communities),
        "params": {"resolution": res_val}
    }

# ==========================================
# 5. 儲存與輸出函式
# ==========================================
def export_community_results(all_results):
    """
    將所有演算法的結果整合存為 JSON，供後續視覺化程式 (05-4) 使用。
    """
    save_path = os.path.join(INPUT_DIR, 'community_master.json')
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"--- 分群結果已成功儲存至 {save_path} ---")

# ==========================================
# 6. 主執行函式 (Main Function)
# ==========================================
def run_community_compute():
    print("--- 開始執行 05-3：加權社群偵測與參數調校流程 ---")
    
    try:
        # A. 資料準備
        G_nx, g_ig, node_names = load_and_prepare_graphs()
        
        # B. 執行各演算法
        final_results = {}
        
        final_results['Walktrap'] = compute_walktrap_algorithm(g_ig, node_names)
        final_results['Louvain'] = compute_louvain_algorithm(G_nx)
        final_results['Greedy'] = compute_greedy_algorithm(G_nx)
        
        # C. 顯示初步結果
        print("\n[運算報告摘要]")
        for algo, data in final_results.items():
            print(f"- {algo:10}: {len(data['communities'])} 群, Q={data['modularity']:.4f}")
            
        # D. 輸出
        export_community_results(final_results)
        
    except Exception as e:
        print(f"執行分群運算時發生錯誤: {e}")

if __name__ == "__main__":
    run_community_compute()