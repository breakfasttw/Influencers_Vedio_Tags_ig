import pandas as pd

# ==========================================
# 1. 檔案路徑與設定
# ==========================================
source_file = r"output/influencer_tag_count.csv"      # 第一階段輸出的檔案
mapping_file = "AisaTop200.csv"                # 網紅人名對照表
output_filename = r"output/influencer_tag_count_final.csv"

def generate_final_report():
    print(f"開始執行最終資料轉換...")

    # 讀取檔案
    try:
        tag_count_df = pd.read_csv(source_file)
        aisa_top200_df = pd.read_csv(mapping_file)
    except FileNotFoundError as e:
        print(f"錯誤：找不到檔案 {e.filename}，請確認檔案是否存在。")
        return

    # ------------------------------------------
    # 2. 建立 ig_id -> person_name 的映射字典
    # ------------------------------------------
    # 確保 ig_id 為字串型別以利比對
    aisa_top200_df['ig_id'] = aisa_top200_df['ig_id'].astype(str)
    
    # 建立映射表 (字典)
    name_mapping = dict(zip(aisa_top200_df['ig_id'], aisa_top200_df['person_name']))

    # ------------------------------------------
    # 3. 欄位名稱對應 (Mapping)
    # ------------------------------------------
    # 轉換 post_owner.username 為 tagger_person_name (發文者)
    tag_count_df['tagger_person_name'] = tag_count_df['post_owner.username'].astype(str).map(name_mapping)
    
    # 轉換 tagged_username 為 person_name (被標記者)
    tag_count_df['person_name'] = tag_count_df['tagged_username'].astype(str).map(name_mapping)

    # 只保留兩邊都能成功對應到人名的資料 (即都在 AisaTop200 名單內的標記行為)
    filtered_df = tag_count_df.dropna(subset=['tagger_person_name', 'person_name']).copy()

    # ------------------------------------------
    # 4. 偵測重複 PK 並列印至終端機
    # ------------------------------------------
    # 計算每個 (person_name, tagger_person_name) 出現的次數
    counts_per_pair = filtered_df.groupby(['person_name', 'tagger_person_name']).size()
    duplicates = counts_per_pair[counts_per_pair > 1]

    if not duplicates.empty:
        print("\n" + "="*50)
        print("【偵測到重複 PK 值，將進行 Count 加總列印】")
        print("="*50)
        for (p_name, t_name), size in duplicates.items():
            # 抓出這些重複行的原始 count 數值
            sub_df = filtered_df[(filtered_df['person_name'] == p_name) & 
                                 (filtered_df['tagger_person_name'] == t_name)]
            counts_list = sub_df['count'].tolist()
            total_sum = sum(counts_list)
            print(f"PK組: {t_name} (發文者) -> {p_name} (被標記)")
            print(f"  - 原始多筆 Count: {counts_list}")
            print(f"  - 加總後合計: {total_sum}")
        print("="*50 + "\n")
    else:
        print("\n系統訊息：未發現重複的 PK 值組合。")

    # ------------------------------------------
    # 5. 執行 GroupBy 加總與輸出
    # ------------------------------------------
    # 依據人名組合進行 Count 合併
    final_df = filtered_df.groupby(['person_name', 'tagger_person_name'])['count'].sum().reset_index()

    # 調整欄位順序
    final_df = final_df[['person_name', 'tagger_person_name', 'count']]

    # 依照 Count 由大到小排序，讓報表更直觀
    final_df = final_df.sort_values(by='count', ascending=False)

    # 輸出 CSV
    final_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"處理完成！最終報表已儲存至: {output_filename}")
    print("-" * 30)
    print("前 5 筆資料預覽：")
    print(final_df.head())

if __name__ == "__main__":
    generate_final_report()