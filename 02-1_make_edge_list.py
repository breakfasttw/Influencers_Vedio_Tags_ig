# 產製圈內標記關係 edge 表格
# input 1 = influencer_tag_count_final.csv (標記次數統計表)
# input 2 = Aisa100_ig.csv (母體名單，用來確保只分析圈內人)

# output edge表、自我標記統計
# username_edge_list.csv (包含 count 權重)
# self_promotion_stats.csv (紀錄網紅 tag 自己的次數)

import pandas as pd
import os
from config import *

# ==========================================
# 1. 參數設定 (維持彈性維護路徑)
# ==========================================
# 沿用原本變數名稱，但對應本次專案檔案
INPUT_FILENAME = 'influencer_tag_count_final.csv'
OUTPUT_FILENAME = 'username_edge_list.csv'
SELF_PROMO_FILENAME = 'self_promotion_stats.csv'

if not os.path.exists(INPUT_DIR):
    os.makedirs(INPUT_DIR)

def solve_phase_1():
    print("--- 修正執行 02-1：產製標記關係邊名單 (對調對象 + 加總去重版) ---")
    
    # 2. 讀取母體名單
    if not os.path.exists(MASTER_LIST_PATH):
        print(f"錯誤：找不到檔案 {MASTER_LIST_PATH}")
        return
    master_df = pd.read_csv(MASTER_LIST_PATH)
    master_df.columns = master_df.columns.str.strip()
    influencer_set = set(master_df['person_name'].astype(str).str.strip())

    # 3. 處理標記數據
    if not os.path.exists(INPUT_FILENAME):
        print(f"錯誤：找不到檔案 {INPUT_FILENAME}")
        return
    tag_df = pd.read_csv(INPUT_FILENAME)
    tag_df['person_name'] = tag_df['person_name'].astype(str).str.strip()
    tag_df['tagger_person_name'] = tag_df['tagger_person_name'].astype(str).str.strip()

    # --- [修正點]：判定自我標記與圈內過濾 ---
    edge_df = tag_df[
        (tag_df['tagger_person_name'] != tag_df['person_name']) & 
        (tag_df['tagger_person_name'].isin(influencer_set)) &
        (tag_df['person_name'].isin(influencer_set))
    ].copy()

    # --- [修正點]：根據你的要求對調 source/target ---
    # person_name -> source (發起標記者)
    # tagger_person_name -> target (接收標記者)
    edge_df = edge_df.rename(columns={
        'person_name': 'source',
        'tagger_person_name': 'target',
        'count': 'count'
    })[['source', 'target', 'count']]

    # --- [關鍵新增]：加總重複的邊 ---
    # 若對調後出現相同的 (source, target) 對象，將其 count 加總
    edge_df = edge_df.groupby(['source', 'target'], as_index=False)['count'].sum()
    
    # 排序
    edge_df = edge_df.sort_values(by='source', ascending=True)

    # 處理自我標記
    self_promo_df = tag_df[tag_df['tagger_person_name'] == tag_df['person_name']].copy()
    self_promo_df = self_promo_df[['person_name', 'count']].rename(columns={'count': 'self_tag_count'})

    # 4. 產出 CSV
    edge_save_path = os.path.join(INPUT_DIR, OUTPUT_FILENAME)
    edge_df.to_csv(edge_save_path, index=False, encoding='utf-8-sig')
    
    self_save_path = os.path.join(INPUT_DIR, SELF_PROMO_FILENAME)
    self_promo_df.to_csv(self_save_path, index=False, encoding='utf-8-sig')

    print("-" * 30)
    print(f"階段 02-1 完成。互動總量: {edge_df['count'].sum()} 次")

if __name__ == "__main__":
    solve_phase_1()