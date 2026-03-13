# 統一計算社群分群 (模組化參數調校版 12+1 合併邏輯 + 加權中觀指標擴充)
# input: influencer_bonding_matrix.csv (加權連結矩陣), username_edge_list.csv, zero_degree.json
# output: community_master.json (各演算法結果與 Q 度、中觀層次 SNA 指標)

import pandas as pd
import networkx as nx
from networkx.algorithms import community
import igraph as ig
import json
import os
import numpy as np
from config import *

# ==========================================
# 0. SNA 中觀指標運算分流設定檔 (Configuration)
# Y: 剔除 0-Degree 後才計算 (孤立節點不參與群體指標，其個人指標直接補 0)
# ==========================================
SNA_METRICS_CONFIG = {
    "Meso": {
        "Within_module_Degree": "Y",
        "Participation_Coefficient": "Y",
        "Cluster_Density": "Y",
        "Inter_cluster_Edge_Density": "Y"
    }
}

# ==========================================
# 1. 共同設定與資料載入函式
# ==========================================
def load_and_prepare_graphs():
    """
    讀取 Bonding Matrix 並產製適合不同套件(igraph, NetworkX)的圖形物件。
    同步載入 Edge List 建立有向加權圖，以供中觀指標計算。
    """
    matrix_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    edge_path = EDGE_LIST_PATH
    zero_path = os.path.join(INPUT_DIR, 'zero_degree.json')
    
    if not all(os.path.exists(p) for p in [matrix_path, edge_path, zero_path]):
        raise FileNotFoundError(f"錯誤：找不到矩陣、邊清單或 zero_degree.json 檔案")
        
    full_bonding_df = pd.read_csv(matrix_path, index_col=0)
    with open(zero_path, 'r', encoding='utf-8') as f:
        zero_degree_nodes = json.load(f)
    
    # --- [關鍵修正]：僅保留有互動強度的節點參與分群 (天然排除 0-Degree) ---
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

    # --- 準備 NetworkX 物件 (用於 Louvain/Greedy 與模組內分支度) ---
    # 此為 Bonding 強度的無向圖
    G_nx = nx.Graph()
    G_nx.add_nodes_from(node_names)
    for (s, t), w in zip(list(zip(sources, targets)), weights):
        G_nx.add_edge(node_names[s], node_names[t], weight=w)

    # --- 準備有向加權圖 (用於參與係數與網路密度) ---
    df_edges = pd.read_csv(edge_path)
    df_edges = df_edges[df_edges['source'] != df_edges['target']] # 剔除自我標記
    
    G_dir = nx.DiGraph()
    G_dir.add_nodes_from(node_names) # 只加入活躍網紅
    for _, row in df_edges.iterrows():
        if row['source'] in node_names and row['target'] in node_names:
            G_dir.add_edge(row['source'], row['target'], weight=row['count'])

    return G_dir, G_nx, g_ig, node_names, zero_degree_nodes

# ==========================================
# 2. 分群上限設定，搭配 config 的 CUSTOM_COLORS
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
# 3. 中觀層次指標計算核心 (Meso Metrics Engine)
# ==========================================
def compute_meso_metrics(G_dir, G_nx, membership, zero_degree_nodes):
    """
    計算中觀層次 SNA 指標。
    G_dir: 真實標記次數的有向圖 (用於密度與參與係數)
    G_nx: Bonding 強度的無向圖 (用於模組內分支度)
    """
    meso_results = {
        "Cluster_Density": {},
        "Inter_cluster_Edge_Density": {},
        "Node_Metrics": {}
    }
    
    node_to_cluster = {}
    for cid, members in enumerate(membership):
        for node in members:
            node_to_cluster[node] = cid

    # --- A. 群體指標 (Cluster-wide Metrics) ---
    for cid, members in enumerate(membership):
        group_name = f"Group_{cid}"
        # 1. Cluster Density (群內密度 - 無加權)
        if len(members) > 1:
            meso_results["Cluster_Density"][group_name] = nx.density(G_dir.subgraph(members))
        else:
            meso_results["Cluster_Density"][group_name] = 0.0

    # 2. Inter-cluster Edge Density (群間邊密度 - 無加權)
    for cid1, members1 in enumerate(membership):
        g1_name = f"Group_{cid1}"
        meso_results["Inter_cluster_Edge_Density"][g1_name] = {}
        
        for cid2, members2 in enumerate(membership):
            if cid1 == cid2: continue
            g2_name = f"Group_{cid2}"
            
            if len(members1) == 0 or len(members2) == 0:
                meso_results["Inter_cluster_Edge_Density"][g1_name][g2_name] = 0.0
            else:
                edges_between = len(list(nx.edge_boundary(G_dir, members1, members2)))
                possible_edges = len(members1) * len(members2)
                meso_results["Inter_cluster_Edge_Density"][g1_name][g2_name] = edges_between / possible_edges

    # --- B. 個人在群內的指標 (Node-specific Cluster Metrics) ---
    for cid, members in enumerate(membership):
        # 3. Within-module Degree (依據 Bonding 強度計算 Z-score)
        in_cluster_degrees = {}
        if len(members) > 0:
            subg = G_nx.subgraph(members) # 使用加權無向圖 G_nx
            for n in members:
                in_cluster_degrees[n] = subg.degree(n, weight='weight')
                
            mean_k = np.mean(list(in_cluster_degrees.values()))
            std_k = np.std(list(in_cluster_degrees.values()))
        else:
            mean_k, std_k = 0, 0

        for node in members:
            if node not in meso_results["Node_Metrics"]:
                meso_results["Node_Metrics"][node] = {}
                
            if std_k > 0 and node in in_cluster_degrees:
                z_score = (in_cluster_degrees[node] - mean_k) / std_k
            else:
                z_score = 0.0
            meso_results["Node_Metrics"][node]["Within_module_Degree"] = round(z_score, 4)

    # 4. Participation Coefficient (參與係數 P - 依據 Tag 有向加權)
    for node in G_dir.nodes():
        total_weight = G_dir.degree(node, weight='weight') # 總互動強度 (In + Out)
        if total_weight == 0:
            meso_results["Node_Metrics"][node]["Participation_Coefficient"] = 0.0
            continue
            
        cluster_links = {}
        # 統計連向各群的標記權重
        for neighbor in G_dir.successors(node):
            if neighbor in node_to_cluster:
                cid = node_to_cluster[neighbor]
                cluster_links[cid] = cluster_links.get(cid, 0) + G_dir[node][neighbor]['weight']
        # 統計來自各群的標記權重
        for neighbor in G_dir.predecessors(node):
            if neighbor in node_to_cluster:
                cid = node_to_cluster[neighbor]
                cluster_links[cid] = cluster_links.get(cid, 0) + G_dir[neighbor][node]['weight']
                
        sum_sq = sum((cw / total_weight) ** 2 for cw in cluster_links.values())
        p_coef = 1.0 - sum_sq
        meso_results["Node_Metrics"][node]["Participation_Coefficient"] = round(p_coef, 4)

    # --- C. 補齊 0-Degree 網紅的中觀數值 ---
    for node in zero_degree_nodes:
        meso_results["Node_Metrics"][node] = {
            "Within_module_Degree": 0.0,
            "Participation_Coefficient": 0.0
        }

    return meso_results

# ==========================================
# 4. WalkTrap 演算法函式
# ==========================================
def compute_walktrap_algorithm(G_dir, G_nx, g_ig, node_names, zero_degree_nodes):
    """
    Walktrap 演算法：基於隨機走訪(Random Walk)的社群偵測。
    """
    print("-> 正在執行 Walktrap 運算...")
    walk_steps = 4 
    
    dendrogram = g_ig.community_walktrap(weights='weight', steps=walk_steps)
    clusters = dendrogram.as_clustering()
    q_score = g_ig.modularity(clusters, weights='weight')
    
    raw_communities = [list(np.array(node_names)[list(c)]) for c in clusters]
    final_communities = merge_communities(raw_communities)
    
    meso_metrics = compute_meso_metrics(G_dir, G_nx, final_communities, zero_degree_nodes)
    
    return {
        "modularity": q_score, 
        "Cluster_Density": meso_metrics["Cluster_Density"],
        "Inter_cluster_Edge_Density": meso_metrics["Inter_cluster_Edge_Density"],
        "membership": final_communities,
        "node_metrics": meso_metrics["Node_Metrics"],
        "params": {"steps": walk_steps}
    }

# ==========================================
# 5. Louvain 演算法函式
# ==========================================
def compute_louvain_algorithm(G_dir, G_nx, zero_degree_nodes):
    """
    Louvain 演算法：基於多層級模組化最大化的啟發式演算法。
    """
    print("-> 正在執行 Louvain 運算...")
    res_val = 1.0 
    
    louvain_comm_list = community.louvain_communities(G_nx, weight='weight', resolution=res_val, seed=RANDOM_SEED)
    q_score = community.modularity(G_nx, louvain_comm_list, weight='weight')
    
    raw_communities = [list(c) for c in louvain_comm_list]
    final_communities = merge_communities(raw_communities)
    
    meso_metrics = compute_meso_metrics(G_dir, G_nx, final_communities, zero_degree_nodes)
    
    return {
        "modularity": q_score, 
        "Cluster_Density": meso_metrics["Cluster_Density"],
        "Inter_cluster_Edge_Density": meso_metrics["Inter_cluster_Edge_Density"],
        "membership": final_communities,
        "node_metrics": meso_metrics["Node_Metrics"],
        "params": {"resolution": res_val}
    }

# ==========================================
# 6. Greedy Modularity 演算法函式
# ==========================================
def compute_greedy_algorithm(G_dir, G_nx, zero_degree_nodes):
    """
    Greedy Modularity (Clauset-Newman-Moore)：貪婪搜尋最大化 Q 度的分群方式。
    """
    print("-> 正在執行 Greedy Modularity 運算...")
    res_val = 1.0
    
    greedy_comm_iter = community.greedy_modularity_communities(G_nx, weight='weight', resolution=res_val)
    q_score = community.modularity(G_nx, greedy_comm_iter, weight='weight')
    
    raw_communities = [list(c) for c in greedy_comm_iter]
    final_communities = merge_communities(raw_communities)
    
    meso_metrics = compute_meso_metrics(G_dir, G_nx, final_communities, zero_degree_nodes)
    
    return {
        "modularity": q_score, 
        "Cluster_Density": meso_metrics["Cluster_Density"],
        "Inter_cluster_Edge_Density": meso_metrics["Inter_cluster_Edge_Density"],
        "membership": final_communities,
        "node_metrics": meso_metrics["Node_Metrics"],
        "params": {"resolution": res_val}
    }

# ==========================================
# 7. 儲存與輸出函式
# ==========================================
def export_community_results(all_results):
    save_path = os.path.join(INPUT_DIR, 'community_master.json')
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"--- 分群與中觀指標結果已成功儲存至 {save_path} ---")

# ==========================================
# 8. 主執行函式 (Main Function)
# ==========================================
def run_community_compute():
    print("--- 開始執行 05-3：加權社群偵測與中觀指標計算 ---")
    
    try:
        # A. 資料準備 (取得包含加權的有向圖、無向圖，與孤立名單)
        G_dir, G_nx, g_ig, node_names, zero_degree_nodes = load_and_prepare_graphs()
        
        # B. 執行各演算法
        final_results = {}
        
        final_results['Walktrap'] = compute_walktrap_algorithm(G_dir, G_nx, g_ig, node_names, zero_degree_nodes)
        final_results['Louvain'] = compute_louvain_algorithm(G_dir, G_nx, zero_degree_nodes)
        final_results['Greedy'] = compute_greedy_algorithm(G_dir, G_nx, zero_degree_nodes)
        
        # C. 顯示初步結果
        print("\n[演算法效能 Q 度摘要]")
        for algo, data in final_results.items():
            print(f"- {algo:10}: {len(data['membership'])} 群, Q={data['modularity']:.4f}")
            
        # D. 輸出
        export_community_results(final_results)
        
    except Exception as e:
        print(f"執行分群運算時發生錯誤: {e}")

if __name__ == "__main__":
    run_community_compute()