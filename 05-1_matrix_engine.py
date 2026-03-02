# input
# Aisa100_ig.csv、EDGE_LIST_PATH

# output
# zero_degree.json
# influencer_adjacency_matrix.csv、influencer_reciprocity_matrix.csv (雙矩陣)
# network_metrics_report.csv (網紅為物件的各項統計、類別)
# global_stats_temp.json (母體統計結果)


import pandas as pd
import numpy as np
import os
import json
import networkx as nx
from config import *

def run_matrix_engine():
    print("--- 開始執行 02-2：產製矩陣、全域指標與個人中介中心性 ---")
    
    # 1. 讀取母體清單 (對應 Aisa100_ig.csv 欄位: order, person_name)
    if not os.path.exists(MASTER_LIST_PATH):
        print(f"錯誤：找不到母體名單檔案 {MASTER_LIST_PATH}")
        return
        
    master_df = pd.read_csv(MASTER_LIST_PATH)
    # 清除欄位名稱可能存在的空格
    master_df.columns = master_df.columns.str.strip()
    
    # [修正]：使用正確的小寫欄位名稱 'person_name'
    # 確保名稱一致性，將空格或特殊符號替換為 "-"
    master_df['clean_person_name'] = master_df['person_name'].astype(str).str.strip().str.replace(r'[ ,，]+', '-', regex=True)

    # 決定固定排序並建立映射字典
    # 使用 dict.fromkeys 維持原始 CSV 的排序
    ordered_influencers = list(dict.fromkeys(master_df['clean_person_name'].tolist()))
    
    # 去重以建立映射表 (ig_url 與 Original Rank)
    unique_master = master_df.drop_duplicates(subset=['clean_person_name'], keep='first')
    # 網址表
    url_map = dict(zip(unique_master['clean_person_name'], unique_master['ig_url']))
    # [修正]：對應小寫欄位 'order' 作為 Original_Rank
    rank_map = dict(zip(unique_master['clean_person_name'], unique_master['order']))
    # 類別表
    category_map = dict(zip(unique_master['clean_person_name'], unique_master['category']))
    # 總粉絲樹表
    followers_map = dict(zip(unique_master['clean_person_name'], unique_master['followers']))

    # 2. 建立圖形並計算個人中介中心性
    if not os.path.exists(EDGE_LIST_PATH):
        print(f"錯誤：找不到邊清單檔案 {EDGE_LIST_PATH}")
        return
    df_edges = pd.read_csv(EDGE_LIST_PATH)

    # 建立 NetworkX 有向圖
    G = nx.from_pandas_edgelist(df_edges, source='source', target='target', create_using=nx.DiGraph())
    # 此指令會建立一個有向圖（在 NetworkX 中使用名為 `<head>` 的 pandas DataFrame 中的邊資料df_edges。
    # 透過指定 `<head> ` create_using=nx.DiGraph()，您可以確保產生的物件支援有向邊（來源邊和目標邊的順序很重要），而不是預設的無向邊nx.Graph。 
    # `<head>` 中的每一行都df_edges成為圖中的一條邊，名為「source」和「target」的列定義了關係的方向。
    
    # 確保所有母體成員都在圖中 (含孤立點)
    for person in ordered_influencers:
        if person not in G:
            G.add_node(person)
            
    # [關鍵產出] 找出孤立點並產出 zero_degree.json (僅在此產出一次)
    zero_degree_nodes = [node for node in ordered_influencers if G.degree(node) == 0]
    with open(os.path.join(INPUT_DIR, 'zero_degree.json'), 'w', encoding='utf-8') as f:
        json.dump(zero_degree_nodes, f, ensure_ascii=False, indent=2)

    # [關鍵產出] 計算全域指標 (新增 0-Degree 欄位)
    global_metrics = {
        "母體數": TOTAL_INFLUENCERS,
        "密度(Density)": nx.density(G),
        "互惠率(Reciprocity)": nx.reciprocity(G),
        "傳遞性(Transitivity)": nx.transitivity(G),
        "0-Degree": len(zero_degree_nodes),
        "團體凝聚力(Avg Clustering)": nx.average_clustering(G)
    }
    # 暫存給 04-1 使用
    with open(os.path.join(INPUT_DIR, 'global_stats_temp.json'), 'w', encoding='utf-8') as f:
        json.dump(global_metrics, f, ensure_ascii=False)

    # [關鍵產出] 個人指標：中介中心性 (Betweenness Centrality)
    betweenness = nx.betweenness_centrality(G, normalized=True)

    # 3. 建立矩陣
    node_count = len(ordered_influencers)
    adj_matrix = pd.DataFrame(0, index=ordered_influencers, columns=ordered_influencers)
    for _, row in df_edges.iterrows():
        src, tgt = str(row['source']), str(row['target'])
        if src in adj_matrix.index and tgt in adj_matrix.columns:
            adj_matrix.at[src, tgt] = 1

    # 建立互惠矩陣 (0/1/2)
    recip_values = adj_matrix.values + adj_matrix.values.T
    recip_matrix = pd.DataFrame(recip_values, index=ordered_influencers, columns=ordered_influencers)

    # 4. 彙整摘要報告
    in_degree = adj_matrix.sum(axis=0)
    out_degree = adj_matrix.sum(axis=1)
    mutual_count = (recip_matrix == 2).sum(axis=1)
    
    # 欄位：Original_Rank (來自 order), Person_Name (來自 clean_person_name)
    metrics_report = pd.DataFrame({
        'Original_Rank': [rank_map.get(name, 999) for name in ordered_influencers],
        'Person_Name': ordered_influencers,
        'In_Degree (被追蹤數)': in_degree.values,
        'Out_Degree (主動追蹤數)': out_degree.values,
        'Mutual_Follow (互粉數)': mutual_count.values,
        'Network_Influence_Score': (in_degree.values / (node_count - 1) * 100).round(2),
        'Betweenness_Centrality': [round(betweenness.get(name, 0), 6) for name in ordered_influencers],
        'ig_url': [url_map.get(name, '') for name in ordered_influencers],
        'category': [category_map.get(name, '') for name in ordered_influencers],
        'followers': [followers_map.get(name, '') for name in ordered_influencers]
    })

    # 整合外部追蹤數 (distinct_following)
    if os.path.exists(TOTAL_FOLLOWING_PATH):
        total_df = pd.read_csv(TOTAL_FOLLOWING_PATH)
        total_df['source'] = total_df['source'].str.strip().str.replace(' ', '-')
        follow_map = dict(zip(total_df['source'], total_df['distinct_following']))
        metrics_report['distinct_following'] = metrics_report['Person_Name'].map(follow_map).fillna(0).astype(int)

    # 5. 輸出結果檔案 (utf-8-sig)
    adj_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_adjacency_matrix.csv'), encoding='utf-8-sig')
    recip_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_reciprocity_matrix.csv'), encoding='utf-8-sig')
    metrics_report.to_csv(os.path.join(INPUT_DIR, 'network_metrics_report.csv'), index=False, encoding='utf-8-sig')

    print(f"02-2 執行完畢！已產出矩陣與包含 Betweenness_Centrality 的報表。")

if __name__ == "__main__":
    run_matrix_engine()