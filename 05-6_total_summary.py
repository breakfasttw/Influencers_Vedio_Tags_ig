# 產製專案全域統計摘要報告
# input: network_metrics_report.csv, community_master.json, influencer_bonding_matrix.csv
# output: summary_report.json (全域數據分析報告)

import pandas as pd
import json
import os
import numpy as np
from config import *

def run_summary_export():
    print("--- 執行 05-5：產製分析總結摘要報告 ---")
    
    # ==========================================
    # 1. 載入所有分析結果
    # ==========================================
    metrics_path = os.path.join(INPUT_DIR, 'network_metrics_report.csv')
    bonding_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    comm_path = os.path.join(INPUT_DIR, 'community_master.json')
    
    if not all(os.path.exists(p) for p in [metrics_path, bonding_path, comm_path]):
        print("錯誤：分析檔案不齊全，請依序執行 05-1 ~ 05-4。")
        return

    metrics_df = pd.read_csv(metrics_path)
    bonding_df = pd.read_csv(bonding_path, index_col=0)
    with open(comm_path, 'r', encoding='utf-8') as f:
        comm_results = json.load(f)

    # ==========================================
    # 2. 計算全域網路指標 (Global Statistics)
    # ==========================================
    # 欄位定義 (對應你修正後的 05-1 欄位名)
    in_col = 'In_Degree (被標記數)'
    out_col = 'Out_Degree (主動標記數)'
    
    total_nodes = len(metrics_df)
    # 識別孤島 (0-Degree)
    zero_degree_nodes = metrics_df[(metrics_df[in_col] == 0) & (metrics_df[out_col] == 0)]
    isolated_count = len(zero_degree_nodes)
    
    # 標記互動總次數 (Frequency 總和)
    total_tag_interactions = int(metrics_df[in_col].sum())
    
    # 網路密度計算：
    # 公式：實際存在的邊數量 / 可能存在的最大邊數量
    # 這裡是使用加權網路，我們改看「活躍連結數」
    active_edges_count = np.count_nonzero(bonding_df.values) / 2 # 因為是無向矩陣，要除以 2
    max_possible_edges = (total_nodes * (total_nodes - 1)) / 2
    network_density = active_edges_count / max_possible_edges if max_possible_edges > 0 else 0

    # ==========================================
    # 3. 整理演算法分群摘要 (Algorithm Summaries)
    # ==========================================
    algo_summaries = {}
    for algo, data in comm_results.items():
        communities = data['communities']
        # 整理每一群的領袖與人數
        group_details = []
        for i, comm in enumerate(communities):
            group_label = chr(i + 65)
            # 找出該群領袖
            group_metrics = metrics_df[metrics_df['Person_Name'].isin(comm)]
            leader = group_metrics.loc[group_metrics[in_col].idxmax(), 'Person_Name']
            
            group_details.append({
                "group": group_label,
                "leader": leader,
                "size": len(comm),
                "is_mixed_group": True if i == 12 else False
            })
            
        algo_summaries[algo] = {
            "modularity": round(data['modularity'], 4),
            "group_count": len(communities),
            "top_groups": group_details
        }

    # ==========================================
    # 4. 產出名人堂 (Top Performers)
    # ==========================================
    top_tagged = metrics_df.sort_values(by=in_col, ascending=False).head(5)
    top_taggers = metrics_df.sort_values(by=out_col, ascending=False).head(5)

    # ==========================================
    # 5. 組裝並匯出報告
    # ==========================================
    summary_report = {
        "project_metadata": {
            "total_influencers": total_nodes,
            "analysis_date": "2026-03", # 固定時間戳記
            "reciprocity_mode": USE_RECIPROCITY_WEIGHTING
        },
        "network_overview": {
            "total_interactions": total_tag_interactions,
            "active_social_links": int(active_edges_count),
            "isolated_influencers": isolated_count,
            "isolation_rate": f"{round((isolated_count / total_nodes) * 100, 2)}%",
            "density": round(network_density, 6)
        },
        "top_performers": {
            "most_tagged (被動核心)": top_tagged[['Person_Name', in_col]].to_dict('records'),
            "most_active (主動串聯)": top_taggers[['Person_Name', out_col]].to_dict('records')
        },
        "algorithm_comparison": algo_summaries
    }

    # 儲存為 JSON
    output_path = os.path.join(INPUT_DIR, 'summary_report.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary_report, f, ensure_ascii=False, indent=2)

    print("-" * 30)
    print(f"階段 05-5 完成。最終報告已儲存至 {output_path}")
    print(f"[數據亮點]：本次分析捕捉到 {total_tag_interactions} 次標記互動，網路密度為 {network_density:.6f}")
    if isolated_count > 0:
        print(f"[提示]：共有 {isolated_count} 位網紅處於孤島狀態，未參與標記互動。")

if __name__ == "__main__":
    run_summary_export()