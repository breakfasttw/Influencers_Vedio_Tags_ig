# 執行演算法、參數設定

# input
# EDGE_LIST_PATH
# influencer_reciprocity_matrix.csv  (Walktrap 加權需要)

# output
# community_master.json 每個演算法內有誰、Q度

import pandas as pd
import networkx as nx
from networkx.algorithms import community
import igraph as ig
import json
import os
from config import *

def run_community_compute():
    print("--- 執行 03-0：統一計算社群分群 (還原原始演算法參數) ---")
    
    # 1. 載入邊清單與互惠矩陣 (Walktrap 加權需要)
    if not os.path.exists(EDGE_LIST_PATH) or not os.path.exists(RECIP_MATRIX_PATH):
        print("錯誤：找不到邊清單或互惠矩陣檔案。")
        return
        
    df_edges = pd.read_csv(EDGE_LIST_PATH)
    recip_df = pd.read_csv(RECIP_MATRIX_PATH, index_col=0)
    
    # 建立 NetworkX 圖形 (用於計算全域與分群)
    G_nx = nx.from_pandas_edgelist(df_edges, source='source', target='target', create_using=nx.DiGraph())
    G_undir = G_nx.to_undirected()
    
    results = {}

    # --- [Algorithm 1: Greedy Modularity] ---
    # 比照 03-1-1：使用 NetworkX 的 Greedy 演算法
    print("正在計算 Greedy Modularity...")
    c_greedy = list(community.greedy_modularity_communities(G_undir))
    results['Greedy'] = {
        "communities": [list(c) for c in c_greedy],
        "Q": community.modularity(G_undir, c_greedy)
    }

    # --- [Algorithm 2: Louvain] ---
    # 比照 03-1-2：固定 seed=42 確保分群穩定性
    print("正在計算 Louvain (seed=42)...")
    c_louvain = list(community.louvain_communities(G_undir, seed=RANDOM_SEED))
    results['Louvain'] = {
        "communities": [list(c) for c in c_louvain],
        "Q": community.modularity(G_undir, c_louvain)
    }

    # --- [Algorithm 3: Walktrap] ---
    # 比照 03-1-3：還原 igraph 權重 (互粉=2.0, 單向=1.0) 與 steps=4
    print("正在計算 Walktrap (steps=4, Weighted)...")
    
    # 1. 建立 igraph 節點映射
    node_names = list(G_undir.nodes())
    node_map = {name: i for i, name in enumerate(node_names)}
    
    # 2. 建立邊與權重 (還原原始權重邏輯)
    edges = []
    weights = []
    processed_pairs = set()
    
    for u, v in G_undir.edges():
        pair = tuple(sorted((u, v)))
        if pair not in processed_pairs:
            # 依據互惠矩陣給予權重：2.0 (互粉) or 1.0 (單向)
            w = 2.0 if recip_df.at[u, v] == 2 else 1.0
            edges.append((node_map[u], node_map[v]))
            weights.append(w)
            processed_pairs.add(pair)
            
    # 3. 執行 igraph Walktrap
    g_ig = ig.Graph(n=len(node_names), edges=edges, directed=False)
    g_ig.es['weight'] = weights
    wt_dendrogram = g_ig.community_walktrap(weights='weight', steps=4)
    comm_result = wt_dendrogram.as_clustering() # 自動切割最高 Modularity 處
    
    # 4. 轉換結果
    membership = comm_result.membership
    groups = {}
    for idx, group_id in enumerate(membership):
        name = node_names[idx]
        if group_id not in groups: groups[group_id] = []
        groups[group_id].append(name)
    
    c_wt = sorted(groups.values(), key=len, reverse=True)
    results['Walktrap'] = {
        "communities": c_wt,
        "Q": comm_result.modularity
    }

    OUTPUT_FILE = 'community_master.json'
    # 儲存核心運算結果，確保後續 03-1 繪圖與 04-1 統計之數據源完全一致
    with open(os.path.join(INPUT_DIR,OUTPUT_FILE  ), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)
    
    print(f"03-0 執行成功：三種演算法參數已完全還原。")
    print(f"檔案已輸出為{OUTPUT_FILE }")

if __name__ == "__main__":
    run_community_compute()