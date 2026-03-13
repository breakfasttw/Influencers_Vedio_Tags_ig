# input: 
    # metrics_path = os.path.join(INPUT_DIR, 'network_metrics_report.csv')
    # bonding_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    # freq_path = os.path.join(INPUT_DIR, 'influencer_frequency_matrix.csv')
    # comm_path = os.path.join(INPUT_DIR, 'community_master.json')
    # metrics_df = pd.read_csv(metrics_path)
# output: 
    # 三種檔案的分群圖片、community_grouping_report_final、nodes_edges
    # 


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import os
import json
from adjustText import adjust_text
from config import *

# ==========================================
# 1. 資料載入與前處理函式
# ==========================================
def load_analysis_data():
    """載入 05-1 與 05-3 產出的所有必要數據"""
    metrics_path = os.path.join(INPUT_DIR, 'network_metrics_report.csv')
    bonding_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    # [關鍵修正]：指向 frequency 矩陣以獲取有向資訊
    freq_path = os.path.join(INPUT_DIR, 'influencer_frequency_matrix.csv')
    comm_path = os.path.join(INPUT_DIR, 'community_master.json')

    metrics_df = pd.read_csv(metrics_path)
    # 識別孤島 (0-Degree) 並獨立輸出
    in_col, out_col = 'In_Degree (被標記數)', 'Out_Degree (主動標記數)'
    zero_nodes = metrics_df[(metrics_df[in_col] == 0) & (metrics_df[out_col] == 0)]['Person_Name'].tolist()
    
    with open(os.path.join(INPUT_DIR, 'zero_degree.json'), 'w', encoding='utf-8') as f:
        json.dump(zero_nodes, f, ensure_ascii=False, indent=2)

    with open(comm_path, 'r', encoding='utf-8') as f:
        all_comm_results = json.load(f)

    return {
        "metrics_lookup": metrics_df.set_index('Person_Name').to_dict('index'),
        "bonding_df": pd.read_csv(bonding_path, index_col=0),
        "freq_df": pd.read_csv(freq_path, index_col=0),
        "comm_results": all_comm_results,
        "zero_nodes": zero_nodes,
        "raw_metrics_df": metrics_df # 供後續 JOIN 使用
    }

# ==========================================
# 2. 分群報告產製函式 (CSV)
# ==========================================
def export_grouping_csv(algo_name, communities, metrics_lookup, zero_nodes, output_dir, suffix):
    report_data = []
    in_col = 'In_Degree (被標記數)'
    leader_map = {}
    
    # A. 處理主體社群 (A-M)
    for i, comm in enumerate(communities):
        group_label = chr(i + 65) # A, B, C...
        leader = max(comm, key=lambda n: metrics_lookup[n].get(in_col, 0))
        leader_map[i] = leader
        
        display_name = f"{group_label} (其他小群)" if i == 12 else group_label
        
        report_data.append({
            '派系名稱': display_name,
            '成員總數': len(comm),
            '核心領袖': leader,
            '所有成員': ' | '.join(comm)
        })
    
    # B. 處理 0-Degree (孤島) - 僅出現在 CSV 中
    if zero_nodes:
        report_data.append({
            '派系名稱': '0-Degree (孤島)',
            '成員總數': len(zero_nodes),
            '核心領袖': 'N/A',
            '所有成員': ' | '.join(zero_nodes)
        })
    
    df = pd.DataFrame(report_data)
    df.to_csv(os.path.join(output_dir, f'community_grouping_report_final{suffix}.csv'), index=False, encoding='utf-8-sig')
    return leader_map

# ==========================================
# 3. 網頁數據產製函式 (JSON)
# ==========================================

# ==========================================
# 3. 網頁數據產製函式 (JSON) - 修正版：排除孤立點
# ==========================================
def export_web_json(algo_name, node_names, G_draw, community_map, metrics_lookup, output_dir, suffix):
    """產出結構補全的有向 JSON 數據，且不包含 g_idx == -1 的節點與其連線"""
    nodes_json = []
    included_nodes = set()  # 用於追蹤哪些節點被保留下來
    
    # 1. 處理 Nodes (加入過濾邏輯)
    for node in node_names:
        g_idx = community_map.get(node, -1)
        
        # 【關鍵修改】如果是孤立點 (g_idx == -1)，直接跳過
        if g_idx == -1:
            continue
            
        m = metrics_lookup.get(node, {})
        included_nodes.add(node)  # 紀錄這個節點已進入 JSON
        
        # 建立補全的 nodes 結構
        nodes_json.append({
            "id": node, 
            "name": node,
            # 既然已過濾掉 -1，這裡就不再需要處理 "-" 或灰色邏輯
            "group": f"{chr(g_idx + 65)}", 
            "color": CUSTOM_COLORS[g_idx % len(CUSTOM_COLORS)], 
            "val": round(12 + m.get('In_Degree (被標記數)', 0) / 4, 2),
            "metrics": {
                "in_degree": int(m.get('In_Degree (被標記數)', 0)),
                "out_degree": int(m.get('Out_Degree (主動標記數)', 0)),
                "mutual": int(m.get('Mutual_Follow (互標數)', 0)),
                "Following": int(m.get('Following', 0)),
                "Followers":int(m.get('Followers', 0)),
                "posts":int(m.get('posts', 0)),
            },
            "between_centrality": float(round(m.get('Betweenness_Centrality', 0), 6)),
            "category": str(m.get('category', '未知'))
        })

    # 2. 處理 Links (【關鍵修改】確保 source 與 target 都在 included_nodes 內)
    links_json = [
        {"source": u, "target": v, "value": d['weight']} 
        for u, v, d in G_draw.edges(data=True)
        if u in included_nodes and v in included_nodes
    ]
    
    # 3. 寫入檔案
    output_path = os.path.join(output_dir, f'nodes_edges{suffix}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"nodes": nodes_json, "links": links_json}, f, ensure_ascii=False, indent=2)
        
    print(f"--- JSON 產製完成：{output_path} ---")
    print(f"原始總節點：{len(node_names)}，排除孤立點後剩餘：{len(nodes_json)}")

# def export_web_json(algo_name, node_names, G_draw, community_map, metrics_lookup, output_dir, suffix):
#     """產出結構補全的有向 JSON 數據"""
#     nodes_json = []
#     for node in node_names:
#         g_idx = community_map.get(node, -1)
#         m = metrics_lookup.get(node, {})
        
#         # 建立補全的 nodes 結構
#         nodes_json.append({
#             "id": node, "name": node,
#             "group": f"{chr(g_idx + 65)}" if g_idx != -1 else "-",
#             "color": CUSTOM_COLORS[g_idx % len(CUSTOM_COLORS)] if g_idx != -1 else '#D3D3D3',
#             "val": round(12 + m.get('In_Degree (被標記數)', 0) / 4, 2),
#             "metrics": {
#                 "in_degree": int(m.get('In_Degree (被標記數)', 0)),
#                 "out_degree": int(m.get('Out_Degree (主動標記數)', 0)),
#                 "mutual": int(m.get('Mutual_Follow (互標數)', 0)),
#                 "distinct_following": int(m.get('distinct_following', 0))
#             },
#             "between_centrality": float(round(m.get('Betweenness_Centrality', 0), 6)),
#             "category": str(m.get('category', '未知'))
#         })

#     links_json = [{"source": u, "target": v, "value": d['weight']} for u, v, d in G_draw.edges(data=True)]
    
#     with open(os.path.join(output_dir, f'nodes_edges{suffix}.json'), 'w', encoding='utf-8') as f:
#         json.dump({"nodes": nodes_json, "links": links_json}, f, ensure_ascii=False, indent=2)


# ==========================================
# 4. 網路圖視覺化函式 (PNG) - 排除 0-Degree 於圖例
# ==========================================
def save_network_graph(algo_name, G_draw, pos, metrics_lookup, community_map, communities, leader_map, q_score, zero_count, output_dir, suffix):
    """
    繪製高品質有向加權網路圖，並處理社群領袖圖例與標題佈局。
    
    [視覺化設計要點]：
    - Directed (有向性)：顯示箭頭以捕捉網紅之間的互動流向（誰 tag 誰）。
    - Weighted (加權性)：線條粗細代表互動次數，加重強關係的視覺權重。
    - Top 12 + 1 策略：圖例僅顯示前 12 大核心群組與第 13 個合併群組。
    """
    # 設定畫布大小與字體
    plt.figure(figsize=(24, 24))
    plt.rcParams['font.sans-serif'] = FONT_SETTING
    plt.rcParams['axes.unicode_minus'] = False
    
    # A. 建立圖例 (格式: A: 領袖) - 不包含 0-Degree
    legend_handles = []
    for i, leader in leader_map.items():
        group_label = chr(i + 65)  # A, B, C...
        member_count = len(communities[i])  # 取得該群組的人數
    
        # 組合新格式：A (成員數): 領袖名稱
        label = f"{group_label} ({member_count}): {leader}"
        
        if i == 12: 
            label += " (其他小群)"
        
        legend_handles.append(mpatches.Patch(color=CUSTOM_COLORS[i % len(CUSTOM_COLORS)], label=label))

    # B. 繪圖設定
    in_col = 'In_Degree (被標記數)'
    node_sizes = [metrics_lookup[n].get(in_col, 0) * 45 + 250 for n in G_draw.nodes()]
    node_colors = [CUSTOM_COLORS[community_map.get(n, 0) % len(CUSTOM_COLORS)] for n in G_draw.nodes()]
    
    weights = [d['weight'] for u, v, d in G_draw.edges(data=True)]
    max_w = max(weights) if weights else 1
    edge_widths = [(w / max_w) * 6 + 0.8 for w in weights]

    # C. 執行繪圖 (有向箭頭)
    
    # 線段與箭頭設定
    nx.draw_networkx_edges(G_draw, pos, width=edge_widths, alpha=0.45, edge_color="#3E3D3D",
                           arrows=True, arrowsize=8, arrowstyle='-|>') 
                                                # -> : 簡單線段箭頭（預設）。
                                                # <- : 反向箭頭。
                                                # <-> : 雙向箭頭。
                                                # -|> : 實心封閉三角形頭。
                                                # <-| : 反向實心封閉三角形頭。
                                                # simple : 包含箭身與箭頭的簡單造型。
                                                # fancy : 較具曲線美感的箭頭樣式。
                                                # wedge : 楔形（三角形）箭頭。
    
    # 圓圈圈屬性設定
    nx.draw_networkx_nodes(G_draw, pos, node_size=node_sizes, node_color=node_colors, alpha=0.75, edgecolors='white')

    # D. 文字標籤與標題修正
    texts = [plt.text(pos[n][0], pos[n][1], n, fontsize=8, fontweight='bold') 
             for n in G_draw.nodes() ] 
    #如果要限制 Label 最多顯示的數量，要加上這句：if metrics_lookup[n].get(in_col, 0) > 3
    if texts: adjust_text(texts, 
                          arrowprops=dict(
                              arrowstyle='-', 
                              linestyle='--',  # 設定虛線
                              color="#395182",  # 線條顏色
                              lw=0.4)) # 線條寬度

    plt.title(f"台灣網紅社群標記互動網路分析 - {algo_name}", fontsize=36, pad=120) # 增加 pad 防止重疊
    plt.suptitle(f"演算法: {algo_name} | Q 度: {q_score:.4f} | 已排除 {zero_count} 位孤島網紅", 
                 fontsize=21, y=0.93) # 調整 y 座標
    
    plt.legend(
        handles=legend_handles, 
        title="社群分群核心領袖", 
        loc='upper left',           # 圖例本身的锚點選在左上角
        bbox_to_anchor=(1.01, 1),   # 座標 (1.02, 1) 代表在繪圖區右側 2% 的位置
        prop={'size': 14}, 
        title_fontsize=16, 
        frameon=True, 
        shadow=True, 
        borderpad=1
    )

    # 獲取當前軸
    ax = plt.gca()

    # 移除上方、下方、左側、右側所有邊框
    for spine in ['top', 'bottom', 'left', 'right']:
        ax.spines[spine].set_visible(False)
    

    # 定義儲存路徑
    save_path = os.path.join(output_dir, f'social_network_graph_weighted{suffix}.png')
    plt.savefig(save_path, bbox_inches='tight', dpi=300)
    plt.close()
    
    print(f"   >> 已產出 {algo_name} 視覺化圖片：{save_path}")

# ==========================================
# 5. 主執行流程
# ==========================================
def generate_visuals():
    print("--- 執行 05-4：產製專業視覺化圖表與報表 ---")
    data = load_analysis_data()
    
    for algo_name, config in ALGO_CONFIG.items():
        if algo_name not in data["comm_results"]: continue
        
        print(f"正在處理 {algo_name} 演算法...")
        out_dir = os.path.join(INPUT_DIR, algo_name)
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        
        suffix = config['suffix']
        comm_info = data["comm_results"][algo_name]
        communities = comm_info['communities'] # 此處預期已在 05-3 處理過合併 13 群
        
        # A. 產製 CSV 報表並取得領袖地圖
        leader_map = export_grouping_csv(algo_name, communities, data["metrics_lookup"], data["zero_nodes"], out_dir, suffix)
        
        # B. 準備圖形物件
        core_nodes = [n for n in data["bonding_df"].index if n not in data["zero_nodes"]]
        community_map = {n: i for i, c in enumerate(communities) for n in c}
        
        # 使用 frequency 矩陣繪製有向邊
        G_draw = nx.DiGraph()
        G_draw.add_nodes_from(core_nodes)
        for u in core_nodes:
            for v in core_nodes:
                w = data["freq_df"].at[u, v]
                if w > 0: G_draw.add_edge(u, v, weight=w)

        # 佈局位置計算 (無向)
        # 重力導向演算法 (節點之間互有排斥力（像電荷），而邊則像彈簧一樣產生吸引力)
        G_layout = nx.Graph()
        G_layout.add_nodes_from(core_nodes)
        for i, u in enumerate(core_nodes):
            for j, v in enumerate(core_nodes):
                if i < j:
                    w = data["bonding_df"].at[u, v]
                    if w > 0: G_layout.add_edge(u, v, weight=w)
        # 過調整 spring_layout 的參數來改變視覺效果
        # k (最佳距離)： 預設值約為 $1 / \sqrt{n}$。
            # 調大（如 0.6 或 0.8）：節點間排斥力變強，圖會變得比較鬆散，Label 較好排開。
            # 調小（如 0.2 或 0.3）：排斥力變弱，社群內的節點會縮得更緊密，團塊感更明顯。
        # iterations (運算次數)： 預設 50。增加次數（如 100）會讓佈局趨於物理平衡穩定，但運算時間較長。
        # weight (權重影響力)：  'weight'代表 count 越高的人會被吸得越近。如果想忽略次數差異只看結構，可以拿掉這個參數。
        pos = nx.spring_layout(G_layout, k=0.7, weight='weight', iterations=200, seed=RANDOM_SEED)
        

        # C. 產出圖片與 JSON
        save_network_graph(algo_name, G_draw, pos, data["metrics_lookup"], community_map, 
                           communities, leader_map, comm_info['modularity'], len(data["zero_nodes"]), out_dir, suffix)
        
        export_web_json(algo_name, data["bonding_df"].index, G_draw, community_map, data["metrics_lookup"], out_dir, suffix)

    print("-" * 30)
    print("05-4 執行完成。")

if __name__ == "__main__":
    generate_visuals()