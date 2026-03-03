# input: influencer_bonding_matrix.csv
# output: community_master.json (包含各演算法的分群結果與 Modularity 分數)

import pandas as pd
import networkx as nx
from networkx.algorithms import community
import igraph as ig
import json
import os
import numpy as np
from config import *

def run_community_compute():
    print("--- 執行 05-3：加權社群分群運算 (Walktrap / Louvain / Greedy) ---")
    
    # 1. 載入 05-1 產出的連結強度矩陣
    matrix_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    if not os.path.exists(matrix_path):
        print(f"錯誤：找不到矩陣檔案 {matrix_path}")
        return
        
    bonding_df = pd.read_csv(matrix_path, index_col=0)
    node_names = bonding_df.index.tolist()
    
    # 2. 轉換為 igraph 格式 (用於計算 Walktrap，此演算法對加權網路最為精準)
    # 我們只取矩陣的上三角，避免無向圖重複建立邊
    upper_tri = np.triu(bonding_df.values, k=1)
    sources, targets = np.where(upper_tri > 0)
    weights = upper_tri[sources, targets]
    
    edges = list(zip(sources, targets))
    g_ig = ig.Graph(n=len(node_names), edges=edges, directed=False)
    g_ig.vs['name'] = node_names
    g_ig.es['weight'] = weights

    # 建立 NetworkX 圖形 (用於其他演算法與 Q 度計算)
    G_nx = nx.Graph()
    for (s, t), w in zip(edges, weights):
        G_nx.add_edge(node_names[s], node_names[t], weight=w)

    results = {}

    # --- [Algorithm 1: Walktrap] ---
    # 這是加權網路的首選，steps=4 是經典設定
    print("正在運算 Walktrap (加權隨機走訪)...")
    wt_dendrogram = g_ig.community_walktrap(weights='weight', steps=4)
    wt_comm = wt_dendrogram.as_clustering()
    
    results['Walktrap'] = {
        'modularity': g_ig.modularity(wt_comm, weights='weight'),
        'communities': [list(np.array(node_names)[list(c)]) for c in wt_comm]
    }

    # --- [Algorithm 2: Louvain] ---
    # 適合大型網路，快速尋找高密度區域
    print("正在運算 Louvain (模組化最佳化)...")
    lv_comm_dict = community.louvain_communities(G_nx, weight='weight', seed=RANDOM_SEED)
    
    results['Louvain'] = {
        'modularity': community.modularity(G_nx, lv_comm_dict, weight='weight'),
        'communities': [list(c) for c in lv_comm_dict]
    }

    # --- [Algorithm 3: Clauset-Newman-Moore (Greedy)] ---
    print("正在運算 Fast Greedy...")
    gd_comm_iter = community.greedy_modularity_communities(G_nx, weight='weight')
    
    results['Greedy'] = {
        'modularity': community.modularity(G_nx, gd_comm_iter, weight='weight'),
        'communities': [list(c) for c in gd_comm_iter]
    }

    # 3. 儲存結果
    output_path = os.path.join(INPUT_DIR, 'community_master.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("-" * 30)
    print(f"階段 05-3 完成。分群結果已存至 {output_path}")
    for algo, data in results.items():
        print(f"[{algo}] 找到 {len(data['communities'])} 個社群, Modularity: {data['modularity']:.4f}")

if __name__ == "__main__":
    run_community_compute()