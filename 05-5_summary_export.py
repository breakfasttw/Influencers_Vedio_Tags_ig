# 整合演算法數據報表 (也可整合至05-4但太龐大)

#  input 
# global_stats_temp.json

# output 
# network_summary.json

import json
import os
from config import *

def run_final_summary():
    print("--- 執行 04-1：匯整最終統計摘要 ---")
    
    # 1. 讀取全域指標 (由 05-1 產出)
    stats_temp_path = os.path.join(INPUT_DIR, 'global_stats_temp.json')
    if not os.path.exists(stats_temp_path):
        print("錯誤：找不到全域指標暫存檔。"); return
    
    with open(stats_temp_path, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    # 2. 讀取分群運算結果 (由 03-0 產出)
    master_path = os.path.join(INPUT_DIR, 'community_master.json')
    with open(master_path, 'r', encoding='utf-8') as f:
        comm_data = json.load(f)
    
    # 3. 整合演算法指標
    for algo in ['Greedy', 'Louvain', 'Walktrap']:
        summary[algo] = {
            "Group_Count": len(comm_data[algo]['communities']),
            "Group_Size": [len(c) for c in comm_data[algo]['communities']],
            "Modularity_Score_Q": round(comm_data[algo]['Q'], 6)
        }
    
    # 4. 輸出最終結果
    output_path = os.path.join('Output', 'network_summary.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=4)
    
    print(f"分析完成！最終摘要已儲存至: {output_path}")

if __name__ == "__main__":
    run_final_summary()