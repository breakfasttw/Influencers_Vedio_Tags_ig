# 產製圈內追蹤關係 edge 表格
# input 1 = ignore/following_list 資料夾內的 {網紅id name}-Following.csv
# input 2 = 中文名稱 與  {網紅id name} 對應表

# output edge表、總追蹤數
# username_edge_list.csv
# username_total_following.csv


import pandas as pd
import os
import re

# ==========================================
# 1. 參數設定
# ==========================================
MASTER_LIST_PATH = 'Aisa100_ig.csv'
INPUT_DIR = 'ignore/following_list'
OUTPUT_DIR = 'Output'
OUTPUT_FILENAME = 'username_edge_list.csv'
TOTAL_FOLLOWING_FILENAME = 'username_total_following.csv'


if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def solve_phase_1():
    # ==========================================
    # 2. 讀取母體名單並建立映射 (Mapping)
    # ==========================================
    if not os.path.exists(MASTER_LIST_PATH):
        print(f"錯誤：找不到檔案 {MASTER_LIST_PATH}")
        return

    # 讀取檔案
    master_df = pd.read_csv(MASTER_LIST_PATH)
    
    # [關鍵防錯]：去除欄位名稱的前後空格 (例如將 "ig_id " 轉為 "ig_id")
    master_df.columns = master_df.columns.str.strip()
    
    # 檢查必要欄位是否存在
    required_cols = ['person_name', 'ig_id']
    for col in required_cols:
        if col not in master_df.columns:
            print(f"錯誤：母體檔案中找不到 '{col}' 欄位。目前的欄位有: {master_df.columns.tolist()}")
            return

    # [關鍵清理]：
    # 1. 將 ig_id 內容去空格並轉小寫
    # 2. 將 person_name 空格換成 "-"
    master_df['clean_ig_id'] = master_df['ig_id'].astype(str).str.strip().str.lower()
    # 使用正則表達式 [ ,，]+ 匹配：空格、半形逗號、全形逗號 (可匹配一個或多個)
    master_df['clean_person_name'] = master_df['person_name'].astype(str).str.replace(r'[ ,，]+', '-', regex=True)
    # master_df['clean_person_name'] = master_df['person_name'].astype(str).str.replace(' ', '-', regex=False)
    
    # 建立映射表：{ '帳號': '清理後的姓名' }
    id_to_person_map = dict(zip(master_df['clean_ig_id'], master_df['clean_person_name']))
    valid_ids = set(id_to_person_map.keys())

    # ==========================================
    # 3. 掃描 Following 資料夾
    # ==========================================
    all_edges = []

    # [新增需求]：建立統計追蹤總數的字典
    # 結構: { '蔡阿嘎': {'ids': set(), 'origin_count': 0} }
    total_stats = {}
    
    if not os.path.exists(INPUT_DIR):
        print(f"錯誤：找不到資料夾 {INPUT_DIR}")
        return

    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.csv')]
    print(f"預計處理 {len(files)} 個檔案...")

    for filename in files:
        # 提取檔名第一個橫槓前的字串作為 source_id
        source_id = filename.split('-Following')[0]
        # source_id = filename.split('-')[0].strip().lower()

        if source_id not in id_to_person_map:
            continue
        
        # 驗證此帳號是否在母體內
        if source_id not in valid_ids:
            # 除錯資訊：如果還是失敗，印出此 ID 讓使用者確認
            print(f"跳過：{filename} (提取到的 ID '{source_id}' 不在母體清單中)")
            continue
            
        source_name = id_to_person_map[source_id]
        # [新增需求]：初始化該網紅的統計資料
        if source_name not in total_stats:
            total_stats[source_name] = {'ids': set(), 'origin_count': 0}

        try:
            # 讀取該網紅追蹤的人，只取 username 欄位
            # [修改]：讀取時多取 ig_user_id 以便進行去重統計
            following_df = pd.read_csv(os.path.join(INPUT_DIR, filename), usecols=['username', 'ig_user_id'])
            
            # --- [新增需求邏輯：統計總追蹤人數] ---
            # 直接累加 row 數量
            total_stats[source_name]['origin_count'] += len(following_df)
            # 將 ig_user_id 轉為字串並去除空值，存入 set 進行自動去重 (跨帳號合併)
            valid_user_ids = following_df['ig_user_id'].dropna().astype(str).unique()
            total_stats[source_name]['ids'].update(valid_user_ids)

            # 清理追蹤清單中的帳號
            following_df['username'] = following_df['username'].astype(str).str.strip().str.lower()
            
            # 過濾：只保留追蹤對象也在母體名單內的紀錄 (圈內互動)
            in_circle = following_df[following_df['username'].isin(valid_ids)].copy()
            
            for target_id in in_circle['username']:
                target_name = id_to_person_map[target_id]
                
                # 排除自己追蹤自己（若有分帳則會保留）
                if source_name != target_name:
                    all_edges.append({
                        'source': source_name,
                        'target': target_name
                    })
                    
        except Exception as e:
            print(f"讀取檔案 {filename} 時發生錯誤: {e}")

    # ==========================================
    # 4. 去重並產出 CSV
    # ==========================================
    edge_df = pd.DataFrame(all_edges).drop_duplicates() # 處理多個小帳追蹤同一主帳
    edge_save_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    edge_df.to_csv(edge_save_path, index=False, encoding='utf-8-sig')
    print("-" * 30)
    print(f"階段 1-1 完成：邊名單已儲存至 {edge_save_path}")
    print(f"產生的關係總數 (Edge count): {len(edge_df)}")
    
    # ==========================================
    # 5. [新增需求] 產出 username_total_following.csv
    # ==========================================
    total_following_rows = []
    for name, data in total_stats.items():
        total_following_rows.append({
            'source': name,
            'distinct_following': len(data['ids']),
            'origin_following': data['origin_count']
        })
    
    total_df = pd.DataFrame(total_following_rows)
    total_save_path = os.path.join(OUTPUT_DIR, TOTAL_FOLLOWING_FILENAME)
    total_df.to_csv(total_save_path, index=False, encoding='utf-8-sig')
    print(f"階段 1-2 完成：總追蹤統計已儲存至 {total_save_path}")
    print(f"執行完畢！")

if __name__ == "__main__":
    solve_phase_1()