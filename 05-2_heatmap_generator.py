# input
# influencer_adjacency_matrix.csv、influencer_reciprocity_matrix.csv、

# output 熱力圖相關
# influencer_clustered_heatmap.png、matrix.json

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import json
import os
from config import *

# ==========================================
# 1. 關聯熱圖模組 (過濾孤島 + 產出矩陣數據)
# ==========================================
def generate_clustered_heatmap_and_json():
    """
    讀取互惠矩陣，過濾無連結網紅後繪製階層聚類熱圖，
    並捕捉聚類後的順序產出 matrix.json。
    """
    print("--- 執行 03-2：產生關聯熱圖並捕捉聚類排序 ---")
    
    # 讀取由 05-1 產出的互惠矩陣
    recip_path = os.path.join(INPUT_DIR, 'influencer_reciprocity_matrix.csv')
    if not os.path.exists(recip_path):
        print(f"錯誤：找不到互惠矩陣 {recip_path}，請先執行 02-2。")
        return
        
    recip_df = pd.read_csv(recip_path, index_col=0)
    
    # --- [邏輯還原] 過濾 Degree = 0 的孤島節點 ---
    # 判斷標準：在矩陣中橫列或直欄都沒有值大於 0 的節點
    adj_temp = (recip_df.fillna(0) > 0).astype(int)
    nodes_with_edges = adj_temp.index[(adj_temp.sum(axis=1) > 0) | (adj_temp.sum(axis=0) > 0)]
    clean_df = recip_df.loc[nodes_with_edges, nodes_with_edges].fillna(0)
    isolated_count = len(recip_df) - len(clean_df)
    
    # 設定字體與主題 (採用 03-1-1 之參數)
    sns.set_theme(font=FONT_SETTING[0]) # 使用 Iansui
    
    # 繪製 Clustermap
    g = sns.clustermap(
        clean_df, 
        cmap="YlOrRd", 
        linewidths=.3, 
        linecolor='lightgray',
        figsize=(25, 25), 
        xticklabels=True, 
        yticklabels=True,
        cbar_kws={'label': '關係強度'}, 
        dendrogram_ratio=(0.08, 0.08),
        cbar_pos=(0.02, 0.8, 0.03, 0.15) 
    )
    
    # --- [關鍵邏輯] 捕捉聚類順序並產出 JSON ---
    # 依據樹狀圖 (Dendrogram) 的排序重新排列標籤
    reordered_labels = [clean_df.index[i] for i in g.dendrogram_row.reordered_ind]
    reordered_matrix = clean_df.loc[reordered_labels, reordered_labels]
    
    # 格式化為前端矩陣圖格式
    matrix_data = {
        "z": reordered_matrix.values.tolist(), 
        "x": reordered_labels, 
        "y": reordered_labels
    }
    
    # 輸出 matrix.json 至根目錄的 Output
    with open(os.path.join(INPUT_DIR, 'matrix.json'), 'w', encoding='utf-8') as f:
        json.dump(matrix_data, f, ensure_ascii=False, indent=2)

    # 設定標題與說明文字
    g.fig.suptitle(f"網紅關聯強度矩陣 (已移除 {isolated_count} 位無連結網紅)", 
                   fontsize=30, y=1.03, weight='bold')
    
    plt.gcf().text(0.5, 0.99, "關係強度指標 (0: 無關係, 1: 單向關注, 2: 雙向互粉)", 
                   ha='center', fontsize=18, color='gray', style='italic')
    
    # 存檔
    output_png = os.path.join(INPUT_DIR, 'influencer_clustered_heatmap.png')
    g.savefig(output_png, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"成功：熱圖已儲存至 {output_png}，矩陣數據已儲存至 matrix.json。")

# ==========================================
# 執行
# ==========================================
if __name__ == "__main__":
    generate_clustered_heatmap_and_json()