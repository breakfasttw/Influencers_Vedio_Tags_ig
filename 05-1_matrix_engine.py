# input: AisaTop200.csv (MASTER_LIST_PATH)、EDGE_LIST_PATH (02-1 產出)
# output: 
# 1. influencer_binary_matrix.csv
# 2. influencer_frequency_matrix.csv
# 3. influencer_bonding_matrix.csv (根據開關加權後的矩陣)
# 4. network_metrics_report.csv (完整資訊報表)

import pandas as pd
import numpy as np
import os
import json
import networkx as nx
from config import *

# 確保 config 有定義開關
if 'USE_RECIPROCITY_WEIGHTING' not in locals():
    USE_RECIPROCITY_WEIGHTING = False

def run_matrix_engine():
    print(f"--- 執行 05-1：產製矩陣與完整欄位報表 (對應 AisaTop200 欄位) ---")
    
    # ==========================================
    # 1. 讀取母體名單並建立 Mapping 字典
    # ==========================================
    if not os.path.exists(MASTER_LIST_PATH):
        print(f"錯誤：找不到母體名單 {MASTER_LIST_PATH}")
        return
    
    # 讀取 AisaTop200.csv
    master_df = pd.read_csv(MASTER_LIST_PATH)
    master_df.columns = master_df.columns.str.strip()
    
    # 確保名稱一致性並去重
    ordered_influencers = master_df['person_name'].astype(str).str.strip().drop_duplicates().tolist()
    node_count = len(ordered_influencers)

    # 建立映射表 (對應 AisaTop200.csv 的實際欄位名稱)
    # Aisa_Order -> Original_Rank
    rank_map = dict(zip(master_df['person_name'], master_df['Aisa_Order']))
    url_map = dict(zip(master_df['person_name'], master_df.get('ig_url', '')))
    followers_map = dict(zip(master_df['person_name'], master_df.get('Followers', '')))
    following_map = dict(zip(master_df['person_name'], master_df.get('Following', '')))
    posts_map = dict(zip(master_df['person_name'], master_df.get('posts', ''))) 
    category_map = dict(zip(master_df['person_name'], master_df.get('category', '')))

    # ==========================================
    # 2. 建立三層次矩陣
    # ==========================================
    if not os.path.exists(EDGE_LIST_PATH):
        print(f"錯誤：找不到邊清單 {EDGE_LIST_PATH}")
        return
    df_edges = pd.read_csv(EDGE_LIST_PATH)

    # A. Frequency Matrix (原始次數)
    freq_matrix = pd.DataFrame(0, index=ordered_influencers, columns=ordered_influencers)
    edge_pivot = df_edges.pivot(index='source', columns='target', values='count').fillna(0)
    edge_pivot = edge_pivot.reindex(index=ordered_influencers, columns=ordered_influencers, fill_value=0)
    freq_matrix = freq_matrix.add(edge_pivot, fill_value=0)

    # B. Binary Matrix (有無標記)
    binary_matrix = (freq_matrix > 0).astype(int)

    # C. Bonding Matrix (連結強度 - 演算法用)
    bonding_val = np.zeros_like(freq_matrix.values, dtype=float)
    freq_val = freq_matrix.values
    for i in range(len(ordered_influencers)):
        for j in range(i + 1, len(ordered_influencers)):
            a_to_b, b_to_a = freq_val[i, j], freq_val[j, i]
            if a_to_b > 0 or b_to_a > 0:
                sum_w = a_to_b + b_to_a
                if USE_RECIPROCITY_WEIGHTING:
                    factor = (min(a_to_b, b_to_a) + 1) / (max(a_to_b, b_to_a) + 1)
                    final_w = sum_w * factor
                else:
                    final_w = sum_w
                bonding_val[i, j] = bonding_val[j, i] = final_w
    bonding_matrix = pd.DataFrame(bonding_val, index=ordered_influencers, columns=ordered_influencers)

    # ==========================================
    # 3. 計算 SNA 指標
    # ==========================================
    G = nx.DiGraph()
    G.add_nodes_from(ordered_influencers)
    for _, row in df_edges.iterrows():
        G.add_edge(row['source'], row['target'], weight=row['count'], distance=1.0/row['count'])

    in_strength = dict(G.in_degree(weight='weight'))
    out_strength = dict(G.out_degree(weight='weight'))
    betweenness = nx.betweenness_centrality(G, weight='distance')
    
    # 計算互標人數 (對應原本的互粉數)
    mutual_tags = np.logical_and(binary_matrix.values, binary_matrix.values.T).astype(int)
    mutual_count = np.sum(mutual_tags, axis=1)

    # ==========================================
    # 4. 整合產出報表 (維持原本要求的欄位名稱)
    # ==========================================
    metrics_report = pd.DataFrame({
        'Original_Rank': [rank_map.get(n, '') for n in ordered_influencers],
        'Person_Name': ordered_influencers,
        'In_Degree (被標記數)': [in_strength.get(n, 0) for n in ordered_influencers],
        'Out_Degree (主動標記數)': [out_strength.get(n, 0) for n in ordered_influencers],
        'Mutual_Follow (互標數)': mutual_count,
        'Network_Influence_Score': [(in_strength.get(n, 0) / (node_count - 1) * 100) for n in ordered_influencers],
        'Betweenness_Centrality': [round(betweenness.get(n, 0), 6) for n in ordered_influencers],
        'ig_url': [url_map.get(n, '') for n in ordered_influencers],
        'posts': [posts_map.get(n, '') for n in ordered_influencers],
        'Followers': [followers_map.get(n, '') for n in ordered_influencers],
        'Following': [following_map.get(n, '') for n in ordered_influencers],
        'category': [category_map.get(n, '') for n in ordered_influencers]
    })

    # # 處理外部追蹤資料 (若檔案存在則 mapping，否則填 0)
    # if os.path.exists(TOTAL_FOLLOWING_PATH):
    #     total_df = pd.read_csv(TOTAL_FOLLOWING_PATH)
    #     follow_map = dict(zip(total_df['source'].str.strip(), total_df['distinct_following']))
    #     metrics_report['distinct_following'] = metrics_report['Person_Name'].map(follow_map).fillna(0).astype(int)
    # else:
    #     metrics_report['distinct_following'] = 0

    # ==========================================
    # 5. 儲存結果
    # ==========================================
    binary_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_binary_matrix.csv'), encoding='utf-8-sig')
    freq_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_frequency_matrix.csv'), encoding='utf-8-sig')
    bonding_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv'), encoding='utf-8-sig')
    metrics_report.to_csv(os.path.join(INPUT_DIR, 'network_metrics_report.csv'), index=False, encoding='utf-8-sig')

    print("-" * 30)
    print(f"階段 05-1 完成。已根據 AisaTop200 格式產出三矩陣與完整報表。")

if __name__ == "__main__":
    run_matrix_engine()