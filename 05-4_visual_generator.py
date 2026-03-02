# 產製演算法所需網頁數據

# input 
# network_metrics_report.csv、influencer_reciprocity_matrix.csv、zero_degree.json

# output 
# 三種演算法的 social_network_graph_optimized{suffix}.png
# 三種演算法的 nodes_edges{suffix}.json
# 三種演算法的 community_grouping_report_final{suffix}.csv

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import networkx as nx
import os
import json
from adjustText import adjust_text
from config import *

def generate_visuals():
    # 1. 載入基礎數據 (由 05-1、05-2 產出的全域報表與矩陣)
    metrics_path = os.path.join(INPUT_DIR, 'network_metrics_report.csv')
    recip_path = os.path.join(INPUT_DIR, 'influencer_reciprocity_matrix.csv')
    zero_degree_path = os.path.join(INPUT_DIR, 'zero_degree.json') # 讀取全域孤立點清單
    
    if not all(os.path.exists(p) for p in [metrics_path, recip_path, zero_degree_path]):
        print("錯誤：找不到 02-2 產出的必要檔案，請先執行 02-2。")
        return

    metrics_df = pd.read_csv(metrics_path)
    recip_df = pd.read_csv(recip_path, index_col=0)
    metrics_lookup = metrics_df.set_index('Person_Name').to_dict('index')
    
    # 讀取孤立點資料 (不分演算法，全域一致)
    with open(zero_degree_path, 'r', encoding='utf-8') as f:
        isolated_nodes = json.load(f)
    
    # 2. 讀取社群運算結果 (由 03-0 產出)
    master_json_path = os.path.join(INPUT_DIR, 'community_master.json')
    with open(master_json_path, 'r', encoding='utf-8') as f:
        master_data = json.load(f)

    # 3. 遍歷演算法產製視覺化與報表
    for algo_name, cfg in ALGO_CONFIG.items():
        print(f"--- 正在產製 {algo_name} 視覺化成果與報表 (含 0-Degree 修正) ---")
        out_dir = cfg['output_dir']
        suffix = cfg['suffix']
        group_label_base = cfg['label']
        if not os.path.exists(out_dir): os.makedirs(out_dir)
            
        communities = master_data[algo_name]['communities']
        community_map = {member: i for i, comm in enumerate(communities) for member in comm}
        my_cmap = ListedColormap(CUSTOM_COLORS[:len(communities)])

        # 建立有向圖形 (僅包含有出現在分群中的核心節點)
        G_core = nx.DiGraph() 
        for comm in communities: G_core.add_nodes_from(comm)
        
        df_edges = pd.read_csv(EDGE_LIST_PATH)
        for _, row in df_edges.iterrows():
            src, tgt = str(row['source']), str(row['target'])
            if src in G_core and tgt in G_core:
                G_core.add_edge(src, tgt)

        # --- A. 繪製社群網絡圖 (還原原始巨大畫布與細節) ---
        fig, ax = plt.subplots(figsize=(34, 34))
        plt.rcParams['font.sans-serif'] = FONT_SETTING
        plt.rcParams['axes.unicode_minus'] = False
        pos = nx.spring_layout(G_core, k=0.35, iterations=120, seed=RANDOM_SEED)
        
        mutual_edges = [e for e in G_core.edges() if recip_df.at[e[0], e[1]] == 2]
        single_edges = [e for e in G_core.edges() if recip_df.at[e[0], e[1]] != 2]

        # 繪製連線
        nx.draw_networkx_edges(G_core, pos, edgelist=single_edges, alpha=0.15, width=0.8, 
                               edge_color='#AAAAAA', ax=ax, arrows=True, arrowstyle='-|>', arrowsize=15)
        nx.draw_networkx_edges(G_core, pos, edgelist=mutual_edges, alpha=0.5, width=2.8, 
                               edge_color='#222222', ax=ax, arrows=True, arrowstyle='-|>', arrowsize=20,
                               connectionstyle='arc3,rad=0.1')
        
        # 繪製節點
        node_sizes = [200 + metrics_lookup.get(n, {}).get('In_Degree (被追蹤數)', 0) * 450 for n in G_core.nodes()]
        node_colors = [community_map.get(n, 0) for n in G_core.nodes()]
        nx.draw_networkx_nodes(G_core, pos, node_size=node_sizes, node_color=node_colors, 
                               cmap=my_cmap, alpha=0.9, ax=ax)
        
        # 標籤避讓
        texts = [ax.text(pos[n][0], pos[n][1], n, fontsize=12, weight='bold') for n in G_core.nodes() 
                 if metrics_lookup.get(n, {}).get('Mutual_Follow (互粉數)', 0) > 0 or 
                    metrics_lookup.get(n, {}).get('In_Degree (被追蹤數)', 0) > 2]
        if texts:
            adjust_text(texts, arrowprops=dict(arrowstyle='->', color='red', lw=0.5, alpha=0.4))

        # 標題與標註
        ax.set_title(f"網紅社群勢力圖 ({algo_name} 分群 | 已移除 {len(isolated_nodes)} 位無連結網紅)", 
                     fontsize=36, pad=50, weight='bold', loc='center')
        plt.gcf().text(0.9, 0.92, "節點大小：被追蹤數 | 位置：社交親疏 | 連線：追蹤方向(箭頭)", 
                       ha='right', fontsize=18, color='#444444')

        # 圖例產製
        legend_handles = []
        for i, comm in enumerate(communities):
            leader = max(list(comm), key=lambda m: metrics_lookup.get(m, {}).get('In_Degree (被追蹤數)', 0))
            legend_handles.append(mpatches.Patch(color=CUSTOM_COLORS[i % len(CUSTOM_COLORS)], label=f"{chr(i+1 + 64)}：{leader}"))
        ax.legend(handles=legend_handles, title=f"社群領袖 ({algo_name})", loc='upper right', fontsize=16)

        plt.axis('off')
        plt.savefig(os.path.join(out_dir, f'social_network_graph_optimized{suffix}.png'), bbox_inches='tight', dpi=300)
        plt.close()

        # --- B. 產出分群報告 CSV (修正：加入 0-Degree 邏輯) ---
        report_data = []
        for i, comm in enumerate(communities):
            leader = max(list(comm), key=lambda m: metrics_lookup.get(m, {}).get('In_Degree (被追蹤數)', 0))
            report_data.append({
                '派系名稱': f"{chr(i+1 + 64)}", 
                '成員總數': len(comm), 
                '核心領袖': leader, 
                '所有成員': " | ".join(list(comm))
            })
        
        # [關鍵修正]：將孤立點加入 CSV 結尾
        if isolated_nodes:
            report_data.append({
                '派系名稱': '0關聯', 
                '成員總數': len(isolated_nodes), 
                '核心領袖': isolated_nodes[0] if isolated_nodes else "None", 
                '所有成員': " | ".join(isolated_nodes)
            })
            
        pd.DataFrame(report_data).to_csv(os.path.join(out_dir, f'community_grouping_report_final{suffix}.csv'), index=False, encoding='utf-8-sig')

        # --- C. 產出網頁 JSON ---
        nodes_json = []
        for node in G_core.nodes():
            g_idx = community_map.get(node, 0)
            m = metrics_lookup.get(node, {})
            nodes_json.append({
                "id": node, "name": node, "group": f"{chr(g_idx+1 + 64)}", 
                "color": CUSTOM_COLORS[g_idx % len(CUSTOM_COLORS)], 
                "val": 1 + m.get('In_Degree (被追蹤數)', 0) / 4,
                "metrics": {
                    "in_degree": int(m.get('In_Degree (被追蹤數)', 0)), 
                    "out_degree": int(m.get('Out_Degree (主動追蹤數)', 0)),
                    "mutual": int(m.get('Mutual_Follow (互粉數)', 0)),
                    "distinct_following": int(m.get('distinct_following', 0))},
                    "between_centrality":float(m.get('Betweenness_Centrality', 0)),
                    "category": str(m.get('category', 0))

            })
        links_json = [{"source": u, "target": v, "type": "mutual" if recip_df.at[u, v] == 2 else "single"} for u, v in G_core.edges()]
        with open(os.path.join(out_dir, f'nodes_edges{suffix}.json'), 'w', encoding='utf-8') as f:
            json.dump({"nodes": nodes_json, "links": links_json}, f, ensure_ascii=False, indent=2)

    print("--- 03-1 完成：分群報告 CSV 已包含 0-Degree 資料 ---")

if __name__ == "__main__":
    generate_visuals()