# 產製網頁介接用之全域統計摘要報告
# input: network_metrics_report.csv, community_master.json, influencer_frequency_matrix.csv
# output: network_summary.json, global_stats_temp.json

import pandas as pd
import networkx as nx
import json
import os
from config import *

def run_summary_export():
    print("--- 執行 05-5：產製對齊網頁格式之 network_summary.json ---")
    
    # ==========================================
    # 1. 載入必要數據
    # ==========================================
    metrics_path = os.path.join(INPUT_DIR, 'network_metrics_report.csv')
    freq_path = os.path.join(INPUT_DIR, 'influencer_frequency_matrix.csv')
    comm_path = os.path.join(INPUT_DIR, 'community_master.json')
    
    if not all(os.path.exists(p) for p in [metrics_path, freq_path, comm_path]):
        print("錯誤：遺失必要分析檔案，請確保 05-1 至 05-4 已執行完成。")
        return

    metrics_df = pd.read_csv(metrics_path)
    freq_df = pd.read_csv(freq_path, index_col=0)
    with open(comm_path, 'r', encoding='utf-8') as f:
        comm_results = json.load(f)

    # 建立有向圖以計算網路指標
    G_dir = nx.from_pandas_adjacency(freq_df, create_using=nx.DiGraph)
    
    # 欄位映射定義
    in_col = 'In_Degree (被標記數)'
    out_col = 'Out_Degree (主動標記數)'
    btw_col = 'Betweenness_Centrality'

    # ==========================================
    # 2. 計算全域指標 (對齊 global_stats_temp.json)
    # ==========================================
    density = round(nx.density(G_dir), 6)
    reciprocity = round(nx.reciprocity(G_dir), 6)
    transitivity = round(nx.transitivity(G_dir), 6)
    avg_clustering = round(nx.average_clustering(G_dir.to_undirected()), 6)
    
    active_nodes = len(metrics_df[metrics_df[in_col] + metrics_df[out_col] > 0])
    isolated_nodes = len(metrics_df[metrics_df[in_col] + metrics_df[out_col] == 0])

    # ==========================================
    # 3. 產出 network_summary.json
    # ==========================================
    
    # A. Algorithm Comparison 
    algo_comparison = {}
    for algo, data in comm_results.items():
        communities = data['communities']
        group_list = []
        for i, comm in enumerate(communities):
            group_label = chr(i + 65)
            # 尋找領袖 (被標記數最高者)
            group_metrics = metrics_df[metrics_df['Person_Name'].isin(comm)]
            leader = group_metrics.sort_values(in_col, ascending=False).iloc[0]['Person_Name']
            
            group_list.append({
                "group_id": group_label,
                "leader": leader,
                "member_count": len(comm),
                "is_other_group": True if i == 12 else False
            })
            
        algo_comparison[algo] = {
            "modularity": round(data['modularity'], 4),
            "group_count": len(communities),
            "groups": group_list
        }

    final_summary = {
        "metadata": {
            "total_influencers": len(metrics_df),
            "active_nodes": active_nodes,
            "isolated_nodes": isolated_nodes,
            "reciprocity_mode": USE_RECIPROCITY_WEIGHTING,
            "analysis_date": "2026-03-04"
        },
        "global_metrics": {
            "density": density,
            "reciprocity": reciprocity,
            "transitivity": transitivity,
            "average_clustering": avg_clustering
        },
        "top_influencers": {
            "by_in_degree": metrics_df.sort_values(in_col, ascending=False).head(5)[['Person_Name', in_col]].to_dict('records'),
            "by_out_degree": metrics_df.sort_values(out_col, ascending=False).head(5)[['Person_Name', out_col]].to_dict('records'),
            "by_betweenness": metrics_df.sort_values(btw_col, ascending=False).head(5)[['Person_Name', btw_col]].to_dict('records')
        },
        "algorithm_comparison": algo_comparison
    }

    # ==========================================
    # 4. 產出 global_stats_temp.json
    # ==========================================
    global_stats_temp = {
        "modularity_scores": {algo: round(data['modularity'], 4) for algo, data in comm_results.items()},
        "total_nodes": len(metrics_df),
        "active_nodes": active_nodes,
        "isolated_nodes": isolated_nodes,
        "density": density,
        "reciprocity": reciprocity,
        "transitivity": transitivity,
        "avg_clustering": avg_clustering
    }

    # 儲存檔案
    with open(os.path.join(INPUT_DIR, 'network_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(final_summary, f, ensure_ascii=False, indent=2)
        
    with open(os.path.join(INPUT_DIR, 'global_stats_temp.json'), 'w', encoding='utf-8') as f:
        json.dump(global_stats_temp, f, ensure_ascii=False, indent=2)

    print("-" * 30)
    print("05-5 執行完成：已依照舊專案格式產出 network_summary 與 global_stats_temp。")

if __name__ == "__main__":
    run_summary_export()