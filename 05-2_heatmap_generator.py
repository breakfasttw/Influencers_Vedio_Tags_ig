# input: influencer_bonding_matrix.csv (由 05-1 產出)
# output: 
# 1. influencer_clustered_heatmap.png (加權聚類熱圖)
# 2. matrix.json (供前端顯示使用)

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import json
import os
import numpy as np
from config import *

def generate_clustered_heatmap_and_json():
    """
    讀取加權連結矩陣 (Bonding Matrix)，過濾無互動網紅後，
    使用 Ward 聚類法繪製熱圖，並產出排序後的 JSON。
    """
    print("--- 執行 05-2：產生加權關聯熱圖與排序數據 ---")
    
    # ==========================================
    # 1. 讀取 Bonding 矩陣
    # ==========================================
    # 這裡是 05-1 產出的「連結強度」矩陣
    matrix_path = os.path.join(INPUT_DIR, 'influencer_bonding_matrix.csv')
    if not os.path.exists(matrix_path):
        print(f"錯誤：找不到矩陣檔案 {matrix_path}，請先執行 05-1。")
        return
        
    df = pd.read_csv(matrix_path, index_col=0)

    # ==========================================
    # 2. 過濾孤島 (這在 Tagging 網路中非常重要，因為很多人可能沒被標記)
    # ==========================================
    # 計算每個節點的總連結強度
    node_strength = df.sum(axis=1)
    isolated_nodes = node_strength[node_strength == 0].index.tolist()
    
    # 產出乾淨的矩陣供繪圖使用
    clean_df = df.drop(index=isolated_nodes, columns=isolated_nodes)
    
    isolated_count = len(isolated_nodes)
    print(f"原始網紅數: {len(df)}, 排除無互動者: {isolated_count}, 進入分析數: {len(clean_df)}")

    if clean_df.empty:
        print("警告：過濾後無剩餘資料，無法產製圖表。")
        return

    # ==========================================
    # 3. 繪製加權聚類熱力圖 (Clustermap)
    # ==========================================
    plt.rcParams['font.sans-serif'] = FONT_SETTING
    plt.rcParams['axes.unicode_minus'] = False

    # 參數說明：
    # - method='ward': 最小化簇內方差，最適合處理連續的 count 權重
    # - cmap='YlOrRd': 越紅代表互動權重越高 (深紅區代表核心朋友圈)
    g = sns.clustermap(
        clean_df,
        method='ward',      
        cmap='YlOrRd',      
        figsize=(25, 25), 
        xticklabels=True, 
        yticklabels=True,
        cbar_kws={'label': '連結強度 (加權後得分)'}, 
        dendrogram_ratio=(0.1, 0.1), # 樹狀圖比例
        cbar_pos=(0.02, 0.8, 0.03, 0.15) 
    )
    
    # ==========================================
    # 4. 捕捉聚類順序並產出 JSON (供前端 Dashboard)
    # ==========================================
    # 獲取聚類後的索引順序，這能讓 JSON 的矩陣呈現明顯的區塊感
    reordered_labels = [clean_df.index[i] for i in g.dendrogram_row.reordered_ind]
    reordered_matrix = clean_df.loc[reordered_labels, reordered_labels]
    
    matrix_data = {
        "z": reordered_matrix.values.tolist(), 
        "x": reordered_labels, 
        "y": reordered_labels,
        "is_weighted": True,
        "reciprocity_setting": USE_RECIPROCITY_WEIGHTING
    }
    
    # 儲存 JSON
    output_json_path = os.path.join(INPUT_DIR, 'matrix.json')
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(matrix_data, f, ensure_ascii=False, indent=2)

    # 儲存圖片
    output_png_path = os.path.join(INPUT_DIR, 'influencer_clustered_heatmap.png')
    mode_text = "互惠加權模式" if USE_RECIPROCITY_WEIGHTING else "廣義生活圈模式"
    g.fig.suptitle(f"網紅互動加權熱圖 - {mode_text}\n(排除 {isolated_count} 位無互動者)", fontsize=24, y=1.02)
    plt.savefig(output_png_path, bbox_inches='tight', dpi=150)
    plt.close()

    print("-" * 30)
    print(f"階段 05-2 完成。熱力圖已存至: {output_png_path}")

if __name__ == "__main__":
    generate_clustered_heatmap_and_json()