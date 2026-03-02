import pandas as pd
import os
import glob
import ast

# ==========================================
# 1. 參數設定區
# ==========================================
# 這裡依照您的需求設定
input_path = r"ignore\tagger"          # 使用 r 避免斜線轉義問題
mapping_filename = "ownerid_mapping.csv"  # 放在根目錄，不加路徑
output_dir = "Output"
output_filename = "influencer_tag_count.csv"

def run_influencer_analysis():
    # 確保輸出資料夾存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"系統訊息：已建立輸出資料夾 {output_dir}")

    # ------------------------------------------
    # 2. 準備參照表 (直接從根目錄讀取)
    # ------------------------------------------
    # 因為檔案在根目錄，我們直接使用檔名即可
    mapping_path = mapping_filename 
    
    if not os.path.exists(mapping_path):
        print(f"錯誤：在根目錄找不到參照檔 {mapping_path}")
        return

    # 讀取參照表
    mapping_df = pd.read_csv(mapping_path, dtype={'post_owner.id': str})
    id_to_name = dict(zip(mapping_df['post_owner.id'], mapping_df['post_owner.username']))
    valid_influencer_ids = set(mapping_df['post_owner.id'].unique())

    # ------------------------------------------
    # 3. 掃描資料夾 (ignore\tagger)
    # ------------------------------------------
    # 這裡只會掃描 input_path 內的檔案
    all_files = glob.glob(os.path.join(input_path, "*.csv"))
    
    if not all_files:
        print(f"系統訊息：在 {input_path} 資料夾下找不到任何 CSV 檔案。")
        return

    all_processed_data = []
    print(f"開始處理資料，目標資料夾：{input_path}，共計 {len(all_files)} 個檔案...")

    for file in all_files:
        try:
            df = pd.read_csv(file, dtype={'post_owner.id': str})
            
            if 'tags' not in df.columns:
                continue

            # 解析 Tags
            def parse_tags(tag_str):
                if pd.isna(tag_str) or tag_str == "" or tag_str == "{}":
                    return []
                try:
                    tag_dict = ast.literal_eval(tag_str)
                    return list(tag_dict.values())
                except:
                    return []

            df['tag_id'] = df['tags'].apply(parse_tags)
            df_exploded = df.explode('tag_id')
            df_exploded = df_exploded.dropna(subset=['tag_id'])
            df_exploded['tag_id'] = df_exploded['tag_id'].astype(str)

            # 篩選白名單
            df_filtered = df_exploded[df_exploded['tag_id'].isin(valid_influencer_ids)].copy()

            if not df_filtered.empty:
                all_processed_data.append(df_filtered[['post_owner.id', 'post_owner.username', 'tag_id']])

        except Exception as e:
            print(f"處理檔案 {file} 時發生錯誤: {e}")

    # ------------------------------------------
    # 4. 聚合與輸出
    # ------------------------------------------
    if not all_processed_data:
        print("處理完成：沒有找到符合條件的標記資料。")
        return

    final_df = pd.concat(all_processed_data, ignore_index=True)
    analysis_result = final_df.groupby(['post_owner.id', 'post_owner.username', 'tag_id']).size().reset_index(name='count')
    
    # 關聯回被 tag 者的 username
    analysis_result['tagged_username'] = analysis_result['tag_id'].map(id_to_name)

    output_full_path = os.path.join(output_dir, output_filename)
    analysis_result.to_csv(output_full_path, index=False, encoding='utf-8-sig')
    
    print("-" * 30)
    print(f"分析成功！結果儲存於：{output_full_path}")

if __name__ == "__main__":
    run_influencer_analysis()