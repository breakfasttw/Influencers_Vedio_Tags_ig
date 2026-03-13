# input: AisaTop200.csv (MASTER_LIST_PATH)、EDGE_LIST_PATH (02-1 產出)
# output: 
# 1. influencer_binary_matrix.csv
# 2. influencer_frequency_matrix.csv
# 3. influencer_bonding_matrix.csv (根據開關加權後的矩陣)
# 4. network_metrics_report.csv (網紅為物件的各項統計，包含擴充微觀 SNA 指標)
# 5. zero_degree.json (孤立節點名單)
# 6. global_stats_temp.json (母體統計結果，包含宏觀 SNA 指標)

import pandas as pd
import numpy as np
import os
import json
import networkx as nx
from config import *

# 確保 config 有定義開關
if 'USE_RECIPROCITY_WEIGHTING' not in locals():
    USE_RECIPROCITY_WEIGHTING = False

# ==========================================
# 0. SNA 指標運算分流設定檔 (Configuration)
# N: 不剔除 0-Degree (使用全體網路 G_full 計算)
# Y: 剔除 0-Degree 後才計算 (使用去孤島網路 G_filtered 計算，被剔除者於報表中補 0)
# ==========================================
SNA_METRICS_CONFIG = {
    "Micro": {
        "In_Degree": "N",
        "Out_Degree": "N",
        "Mutual_Follow": "N",
        "Network_Influence_Score": "N",
        "Betweenness_Centrality": "Y",
        "Eigenvector_Centrality": "Y",
        "Local_Clustering_Coefficient": "Y",
        "Core-periphery_Coreness": "Y"
    },
    "Macro": {
        "Density": "N",
        "Density_0": "Y",
        "Reciprocity": "Y",
        "Transitivity": "Y",
        "Avg_Clustering": "Y",
        "Assortativity": "Y",
        "Core-periphery_Structure_Fit": "Y"
    }
}

# ==========================================
# Step 1. 讀取母體名單並建立 Mapping 字典
# ==========================================
def step1_load_and_clean_data(master_list_path):
    if not os.path.exists(master_list_path):
        print(f"錯誤：找不到母體名單檔案 {master_list_path}")
        return None, None, None
        
    master_df = pd.read_csv(master_list_path)
    master_df.columns = master_df.columns.str.strip()
    
    # 確保名稱一致性並去重
    ordered_influencers = master_df['person_name'].astype(str).str.strip().drop_duplicates().tolist()
    
    # 建立映射表 (對應 AisaTop200.csv 的實際欄位名稱)
    attr_maps = {
        'rank': dict(zip(master_df['person_name'], master_df['Aisa_Order'])),
        'url': dict(zip(master_df['person_name'], master_df.get('ig_url', ''))),
        'followers': dict(zip(master_df['person_name'], master_df.get('Followers', ''))),
        'following': dict(zip(master_df['person_name'], master_df.get('Following', ''))),
        'posts': dict(zip(master_df['person_name'], master_df.get('posts', ''))),
        'category': dict(zip(master_df['person_name'], master_df.get('category', '')))
    }
    
    return master_df, ordered_influencers, attr_maps

# ==========================================
# Step 2. 建立三層次矩陣與雙軌網路圖
# ==========================================
def step2_build_matrices_and_graphs(edge_list_path, ordered_influencers):
    if not os.path.exists(edge_list_path):
        print(f"錯誤：找不到邊清單 {edge_list_path}")
        return [None] * 7
        
    df_edges = pd.read_csv(edge_list_path)
    
    # [核心修改] 從源頭排除「自己標記自己 (Self-loops)」
    df_edges = df_edges[df_edges['source'] != df_edges['target']].copy()

    # --- A. Frequency Matrix (原始次數) ---
    freq_matrix = pd.DataFrame(0, index=ordered_influencers, columns=ordered_influencers)
    edge_pivot = df_edges.pivot(index='source', columns='target', values='count').fillna(0)
    edge_pivot = edge_pivot.reindex(index=ordered_influencers, columns=ordered_influencers, fill_value=0)
    freq_matrix = freq_matrix.add(edge_pivot, fill_value=0)

    # --- B. Binary Matrix (有無標記) ---
    binary_matrix = (freq_matrix > 0).astype(int)

    # --- C. Bonding Matrix (連結強度 - 演算法用) ---
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

    # --- D. 建立雙軌網路圖 ---
    G_full_dir = nx.DiGraph()
    G_full_dir.add_nodes_from(ordered_influencers)
    for _, row in df_edges.iterrows():
        # count 作為加權，1/count 作為距離
        G_full_dir.add_edge(row['source'], row['target'], weight=row['count'], distance=1.0/row['count'])
        
    zero_degree_nodes = [n for n in G_full_dir.nodes() if G_full_dir.degree(n) == 0]
    
    G_filtered_dir = G_full_dir.copy()
    G_filtered_dir.remove_nodes_from(zero_degree_nodes)
    
    # 用於計算 Coreness (不支援加權，單純使用拓樸結構)
    G_filtered_undir = nx.Graph(G_filtered_dir)

    return freq_matrix, binary_matrix, bonding_matrix, G_full_dir, G_filtered_dir, G_filtered_undir, zero_degree_nodes

# ==========================================
# Step 3. 指標分流運算引擎 (微觀與宏觀)
# ==========================================
def step3_compute_metrics(G_full_dir, G_filtered_dir, G_filtered_undir, ordered_influencers, zero_degree_nodes, binary_matrix):
    node_count = len(ordered_influencers)
    
    # 算出整個網路的總標記數 (供影響力分數作為分母)
    in_strength_full = dict(G_full_dir.in_degree(weight='weight'))
    out_strength_full = dict(G_full_dir.out_degree(weight='weight'))
    total_network_tags = sum(in_strength_full.values())
    
    # 計算互標人數矩陣邏輯 (沿用原寫法，極快)
    mutual_tags = np.logical_and(binary_matrix.values, binary_matrix.values.T).astype(int)
    mutual_count = np.sum(mutual_tags, axis=1)
    mutual_dict = dict(zip(ordered_influencers, mutual_count))

    # --- A. 微觀指標 (Micro Metrics) ---
    micro_metrics = {node: {} for node in ordered_influencers}
    
    for n in ordered_influencers:
        micro_metrics[n]['in_degree'] = in_strength_full.get(n, 0)
        micro_metrics[n]['out_degree'] = out_strength_full.get(n, 0)
        micro_metrics[n]['mutual'] = mutual_dict.get(n, 0)
        # [修改] 影響力分數 = 個人被標記總次數 / 網路總標記次數
        score = (in_strength_full.get(n, 0) / total_network_tags) if total_network_tags > 0 else 0
        micro_metrics[n]['network_influence_score'] = round(score, 4)
        
    # [Y：剔除 0-Degree 後計算進階指標] 
    # Betweenness: 使用 distance (倒數) 計算最短路徑
    betweenness_dict = nx.betweenness_centrality(G_filtered_dir, weight='distance')
    
    # Local Clustering: 支援加權
    local_clustering_dict = nx.clustering(G_filtered_dir, weight='weight')
    
    # Coreness: k-core 不支援加權，使用無向 binary 圖
    coreness_dict = nx.core_number(G_filtered_undir)
    
    # Eigenvector: 使用 weight 進行加權運算 (解決 disconnected graphs 問題)
    eigenvector_dict = {}
    for component in nx.weakly_connected_components(G_filtered_dir):
        subgraph = G_filtered_dir.subgraph(component)
        if len(subgraph) > 1:
            try:
                sub_ev = nx.eigenvector_centrality_numpy(subgraph, weight='weight')
                eigenvector_dict.update(sub_ev)
            except Exception:
                try:
                    sub_ev = nx.eigenvector_centrality(subgraph, max_iter=2000, weight='weight')
                    eigenvector_dict.update(sub_ev)
                except Exception as e:
                    print(f"警告：某個子圖 Eigenvector 計算失敗，該區塊節點標記為 0。原因: {e}")

    # 為所有節點寫入進階指標 (0-Degree 者補 0)
    for n in ordered_influencers:
        if n in zero_degree_nodes:
            micro_metrics[n]['betweenness'] = 0.0
            micro_metrics[n]['eigenvector'] = 0.0
            micro_metrics[n]['local_clustering'] = 0.0
            micro_metrics[n]['coreness'] = 0
        else:
            micro_metrics[n]['betweenness'] = betweenness_dict.get(n, 0.0)
            micro_metrics[n]['eigenvector'] = eigenvector_dict.get(n, 0.0)
            micro_metrics[n]['local_clustering'] = local_clustering_dict.get(n, 0.0)
            micro_metrics[n]['coreness'] = coreness_dict.get(n, 0)

    # --- B. 宏觀指標 (Macro Metrics) ---
    macro_metrics = {
        "母體數": node_count, 
        "0-Degree": len(zero_degree_nodes),
        "全網總標記次數(Total Tags)": total_network_tags
    }
    
    # [N：不剔除 0-Degree]
    macro_metrics["密度(Density)"] = nx.density(G_full_dir) # 無加權
    
    # [Y：剔除 0-Degree]
    if len(G_filtered_dir) > 0:
        macro_metrics["密度去0(Density_0)"] = nx.density(G_filtered_dir) # 無加權
        macro_metrics["互惠率(Reciprocity)"] = nx.reciprocity(G_filtered_dir) # 無加權
        macro_metrics["傳遞性(Transitivity)"] = nx.transitivity(G_filtered_dir) # 無加權
        macro_metrics["團體凝聚力(Avg Clustering)"] = nx.average_clustering(G_filtered_dir, weight='weight') # 加權
        
        try:
            # 同質性係數：大網紅標記大網紅 (加權)
            macro_metrics["同質性係數(Assortativity)"] = nx.degree_assortativity_coefficient(G_filtered_dir, weight='weight')
        except:
            macro_metrics["同質性係數(Assortativity)"] = 0.0
            
        # 核心邊陲結構適配度 (Core-periphery Structure Fit - 無加權)
        c_nums = nx.core_number(G_filtered_undir)
        max_core_val = max(c_nums.values()) if c_nums else 0
        core_nodes = [n for n, c in c_nums.items() if c == max_core_val]
        if len(core_nodes) > 1:
            macro_metrics["核心邊陲結構適配度(Core-periphery Structure Fit)"] = nx.density(G_filtered_dir.subgraph(core_nodes))
        else:
            macro_metrics["核心邊陲結構適配度(Core-periphery Structure Fit)"] = 0.0
    else:
        macro_metrics.update({"密度去0(Density_0)": 0, "互惠率(Reciprocity)": 0, "傳遞性(Transitivity)": 0, 
                              "團體凝聚力(Avg Clustering)": 0, "同質性係數(Assortativity)": 0, 
                              "核心邊陲結構適配度(Core-periphery Structure Fit)": 0})

    return micro_metrics, macro_metrics

# ==========================================
# Step 4. 組裝微觀報表與外部屬性
# ==========================================
def step4_assemble_dataframe(ordered_influencers, micro_metrics, attr_maps):
    # 嚴格依照指定順序與欄位名稱組裝
    metrics_report = pd.DataFrame({
        'Original_Rank': [attr_maps['rank'].get(n, '') for n in ordered_influencers],
        'Person_Name': ordered_influencers,
        'In_Degree (被標記數)': [micro_metrics[n]['in_degree'] for n in ordered_influencers],
        'Out_Degree (主動標記數)': [micro_metrics[n]['out_degree'] for n in ordered_influencers],
        'Mutual_Follow (互標數)': [micro_metrics[n]['mutual'] for n in ordered_influencers],
        'Network_Influence_Score': [micro_metrics[n]['network_influence_score'] for n in ordered_influencers],
        'Betweenness_Centrality': [round(micro_metrics[n]['betweenness'], 6) for n in ordered_influencers],
        'Eigenvector_Centrality': [round(micro_metrics[n]['eigenvector'], 6) for n in ordered_influencers],
        'Local_Clustering_Coefficient': [round(micro_metrics[n]['local_clustering'], 6) for n in ordered_influencers],
        'Core-periphery_Coreness': [micro_metrics[n]['coreness'] for n in ordered_influencers],
        'ig_url': [attr_maps['url'].get(n, '') for n in ordered_influencers],
        'posts': [attr_maps['posts'].get(n, '') for n in ordered_influencers],
        'Followers': [attr_maps['followers'].get(n, '') for n in ordered_influencers],
        'Following': [attr_maps['following'].get(n, '') for n in ordered_influencers],
        'category': [attr_maps['category'].get(n, '') for n in ordered_influencers]
    })
    return metrics_report

# ==========================================
# Step 5. 輸出所有結果與暫存檔案
# ==========================================
def step5_export_files(binary_matrix, freq_matrix, bonding_matrix, metrics_report, zero_degree_nodes, macro_metrics):
    os.makedirs(INPUT_DIR, exist_ok=True)
    
    # 輸出三種矩陣
    binary_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_binary_matrix.csv'), encoding='utf-8-sig')
    freq_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_frequency_matrix.csv'), encoding='utf-8-sig')
    bonding_matrix.to_csv(os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv'), encoding='utf-8-sig')
    
    # 輸出微觀節點指標報表
    metrics_report.to_csv(os.path.join(INPUT_DIR, 'network_metrics_report.csv'), index=False, encoding='utf-8-sig')
    
    # 輸出孤立節點暫存檔
    with open(os.path.join(INPUT_DIR, 'zero_degree.json'), 'w', encoding='utf-8') as f:
        json.dump(zero_degree_nodes, f, ensure_ascii=False, indent=2)

    # 輸出宏觀網路指標暫存檔
    with open(os.path.join(INPUT_DIR, 'global_stats_temp.json'), 'w', encoding='utf-8') as f:
        json.dump(macro_metrics, f, ensure_ascii=False, indent=4)

    print("=> 成功產出：influencer_binary_matrix.csv")
    print("=> 成功產出：influencer_frequency_matrix.csv")
    print("=> 成功產出：influencer_bonding_matrix.csv")
    print("=> 成功產出：network_metrics_report.csv")
    print("=> 成功產出：zero_degree.json & global_stats_temp.json")

# ==========================================
# 核心執行器 (Main Routine)
# ==========================================
def run_matrix_engine():
    print(f"--- 執行 05-1：產製標記矩陣與完整欄位報表 (加權擴充版) ---")
    
    # Step 1
    master_df, ordered_influencers, attr_maps = step1_load_and_clean_data(MASTER_LIST_PATH)
    if master_df is None: return
    
    # Step 2
    matrices_and_graphs = step2_build_matrices_and_graphs(EDGE_LIST_PATH, ordered_influencers)
    freq_matrix, binary_matrix, bonding_matrix, G_full_dir, G_filtered_dir, G_filtered_undir, zero_degree_nodes = matrices_and_graphs
    if freq_matrix is None: return
    
    # Step 3
    micro_metrics, macro_metrics = step3_compute_metrics(G_full_dir, G_filtered_dir, G_filtered_undir, ordered_influencers, zero_degree_nodes, binary_matrix)
    
    # Step 4
    metrics_report = step4_assemble_dataframe(ordered_influencers, micro_metrics, attr_maps)
    
    # Step 5
    step5_export_files(binary_matrix, freq_matrix, bonding_matrix, metrics_report, zero_degree_nodes, macro_metrics)
    
    print("-" * 30)
    print("階段 05-1 完成。已順利整合加權 SNA 指標。\n")

if __name__ == "__main__":
    run_matrix_engine()