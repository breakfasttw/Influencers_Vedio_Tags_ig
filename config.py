import os

# ==========================================
# 0. 全域參數設定
# ==========================================
TOTAL_INFLUENCERS = 200

# 隨機seed
RANDOM_SEED = 42

# 是否加入互惠係數
# 決定本次分析【T要引入互惠係數(細膩捕捉互動事實)】或是【F不引入互惠係數 (有效區分廣義上的生活圈)】?
USE_RECIPROCITY_WEIGHTING = False

# 圖例的顏色(依序)
CUSTOM_COLORS = ['#45B7D1', '#FFA07A', '#F7DC6F', "#58E751", '#BB8FCE', '#FF6B6B', "#5968EE", "#837B4D", "#F7A0C0", "#B5BCB2", "#8984CF", "#D9CB9B", "#5F5F5F"]

# 字體設定
FONT_SETTING = ['Iansui', 'Microsoft JhengHei', 'Arial Unicode MS', 'sans-serif']

# ==========================================
# 1. 路徑設定
# ==========================================
INPUT_DIR = 'Output'
MASTER_LIST_PATH = 'AisaTop200.csv'
EDGE_LIST_PATH = os.path.join(INPUT_DIR, 'username_edge_list.csv')
TOTAL_FOLLOWING_PATH = os.path.join(INPUT_DIR, 'username_total_following.csv')
RECIP_MATRIX_PATH = os.path.join(INPUT_DIR, 'influencer_reciprocity_matrix.csv')

# ==========================================
# 2. 演算法輸出規則 (路徑與檔名後綴)
# ==========================================
ALGO_CONFIG = {
    'Greedy': {
        'output_dir': 'Output',
        'suffix': '_gd',
        'label': ''
    },
    'Louvain': {
        'output_dir': os.path.join('Output', 'Louvain'),
        'suffix': '_lv',
        'label': ''
    },
    'Walktrap': {
        'output_dir': os.path.join('Output', 'Walktrap'),
        'suffix': '_wt',
        'label': ''
    }
}


