# 產製演算法視覺化、分群報告與網頁數據 (細節完全還原原專案版)
# input: network_metrics_report.csv, influencer_bonding_matrix.csv, community_master.json
# output: 各演算法資料夾內之 PNG, JSON, CSV 以及 zero_degree.json

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import os
import json
from adjustText import adjust_text
from config import *

def generate_visuals():
    print("--- 執行 05-4：產製專業視覺化圖表與對齊報表格式 ---")
    
    # ==========================================
    # 1. 載入數據與欄位定義 (對應 05-1 修正後的名稱)
    # ==========================================
    metrics_path = os.path.join(INPUT_DIR, 'network_metrics_report.csv')
    matrix_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    comm_path = os.path.join(INPUT_DIR, 'community_master.json')
    
    metrics_df = pd.read_csv(metrics_path)
    in_col = 'In_Degree (被標記數)'
    out_col = 'Out_Degree (主動標記數)'
    
    # 識別並輸出孤島 (0-Degree)
    zero_degree_list = metrics_df[(metrics_df[in_col] == 0) & (metrics_df[out_col] == 0)]['Person_Name'].tolist()
    with open(os.path.join(INPUT_DIR, 'zero_degree.json'), 'w', encoding='utf-8') as f:
        json.dump(zero_degree_list, f, ensure_ascii=False, indent=2)

    metrics_lookup = metrics_df.set_index('Person_Name').to_dict('index')
    bonding_df = pd.read_csv(matrix_path, index_col=0)
    
    with open(comm_path, 'r', encoding='utf-8') as f:
        all_comm_results = json.load(f)

    # ==========================================
    # 2. 演算法循環處理
    # ==========================================
    for algo_name, config in ALGO_CONFIG.items():
        if algo_name not in all_comm_results: continue
            
        print(f"正在處理 {algo_name} ...")
        
        # 建立專屬輸出路徑 (細節 1: 資料夾存放)
        out_dir = os.path.join(INPUT_DIR, algo_name)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        suffix = config['suffix']
        communities = all_comm_results[algo_name]['communities']
        
        # 建立群組映射與報表列表
        community_map = {}
        report_data = []
        legend_handles = [] # 用於存放右上角圖例
        
        for i, comm in enumerate(communities):
            group_label = f"{chr(i + 1 + 64)}" # A, B, C...
            group_color = CUSTOM_COLORS[i % len(CUSTOM_COLORS)]
            
            # 建立圖例項 (細節 2: 右上角圖例)
            legend_handles.append(mpatches.Patch(color=group_color, label=f'派系 {group_label}'))
            
            # 找出核心領袖 (群組內被標記數最高者)
            group_metrics = {node: metrics_lookup[node].get(in_col, 0) for node in comm}
            leader = max(group_metrics, key=group_metrics.get)
            
            # 建立 CSV 報表數據 (細節 3: 報表格式還原)
            report_data.append({
                '派系名稱': group_label,
                '成員總數': len(comm),
                '核心領袖': leader,
                '所有成員': ' | '.join(comm)
            })
            
            for node in comm:
                community_map[node] = i

        # 輸出報表 CSV
        pd.DataFrame(report_data).to_csv(
            os.path.join(out_dir, f'community_grouping_report_final{suffix}.csv'), 
            index=False, encoding='utf-8-sig'
        )

        # --- 繪製加權網路圖 ---
        G_core = nx.Graph()
        core_nodes = [n for n in bonding_df.index if n not in zero_degree_list]
        G_core.add_nodes_from(core_nodes)
        
        edge_weights = []
        for i, node_a in enumerate(core_nodes):
            for j, node_b in enumerate(core_nodes):
                if i < j:
                    w = bonding_df.loc[node_a, node_b]
                    if w > 0:
                        G_core.add_edge(node_a, node_b, weight=w)
                        edge_weights.append(w)

        plt.figure(figsize=(24, 24))
        plt.rcParams['font.sans-serif'] = FONT_SETTING
        pos = nx.spring_layout(G_core, k=0.4, weight='weight', iterations=50, seed=RANDOM_SEED)

        # 點與邊的視覺化設定
        node_sizes = [metrics_lookup[n].get(in_col, 0) * 45 + 200 for n in G_core.nodes()]
        node_colors = [CUSTOM_COLORS[community_map.get(n, 0) % len(CUSTOM_COLORS)] for n in G_core.nodes()]
        
        if edge_weights:
            max_w = max(edge_weights)
            widths = [(w / max_w) * 7 + 0.5 for w in edge_weights]
            nx.draw_networkx_edges(G_core, pos, width=widths, alpha=0.15, edge_color='#A9A9A9')

        nx.draw_networkx_nodes(G_core, pos, node_size=node_sizes, node_color=node_colors, alpha=0.85)

        # 文字避讓與關鍵標籤
        texts = [plt.text(pos[n][0], pos[n][1], n, fontsize=12, fontweight='bold') 
                 for n in G_core.nodes() if metrics_lookup[n].get(in_col, 0) > 3]
        if texts: adjust_text(texts, arrowprops=dict(arrowstyle='->', color='#696969', lw=0.6))

        # 標題與圖例 (右上角圖例實作)
        plt.title(f"台灣網紅社群標記互動網路分析 - {algo_name}", fontsize=32, pad=30)
        plt.legend(handles=legend_handles, title="社群分群圖例", loc='upper right', 
                   prop={'size': 14}, title_fontsize=16, frameon=True, shadow=True)
        
        plt.suptitle(f"演算法: {algo_name} | Q 度: {all_comm_results[algo_name]['modularity']:.4f} | 排除孤島: {len(zero_degree_list)} 位", 
                     fontsize=18, y=0.91)
        
        plt.axis('off')
        plt.savefig(os.path.join(out_dir, f'social_network_graph_weighted{suffix}.png'), bbox_inches='tight', dpi=150)
        plt.close()

        # --- 產出 JSON ---
        nodes_json = []
        for node in bonding_df.index:
            g_idx = community_map.get(node, -1)
            nodes_json.append({
                "id": node, "name": node, 
                "group": f"{chr(g_idx + 1 + 64)}" if g_idx != -1 else "Isolated",
                "color": CUSTOM_COLORS[g_idx % len(CUSTOM_COLORS)] if g_idx != -1 else '#D3D3D3',
                "val": 1 + metrics_lookup[node].get(in_col, 0) / 8,
                "category": str(metrics_lookup[node].get('category', '未知'))
            })
        links_json = [{"source": u, "target": v, "value": d['weight']} for u, v, d in G_core.edges(data=True)]
        with open(os.path.join(out_dir, f'nodes_edges{suffix}.json'), 'w', encoding='utf-8') as f:
            json.dump({"nodes": nodes_json, "links": links_json}, f, ensure_ascii=False, indent=2)

    print("-" * 30)
    print("階段 05-4 修正完成：已還原目錄結構、圖例與 CSV 報表格式。")

if __name__ == "__main__":
    generate_visuals()