import streamlit as st
import pandas as pd
import os

# ==========================================
# 1. 系統初始化與設定
# ==========================================
st.set_page_config(page_title="個人理財分析終端機", layout="wide")

# --- 自動建立歷史資料庫資料夾與個人庫存檔 ---
os.makedirs("history_data/三大法人", exist_ok=True)
os.makedirs("history_data/投資組合", exist_ok=True) 

def init_csv():
    portfolio_cols = ["股名", "股號", "成本價", "股數", "投資成本", "目前股價"]
    for f in ["portfolio_stocks.csv", "portfolio_etfs.csv"]:
        if not os.path.exists(f):
            pd.DataFrame(columns=portfolio_cols).to_csv(f, index=False, encoding='utf-8-sig')

init_csv()

# ==========================================
# 2. 首頁歡迎介面
# ==========================================
st.title("📊 個人專屬理財分析終端機")
st.markdown("歡迎進入戰情室！系統環境已初始化完畢。")
st.markdown("""
### 👈 請從左側選單選擇分析模組：

* **📈 1. 台灣經濟狀況**：追蹤國發會景氣對策信號、CPI、出口數據，並解析台經院營業氣候報告。
* **🛢️ 2. 原物料與匯率**：掌握 VIX 恐慌指數、國際原油、黃金銅價與主要貨幣即時報價。
* **💰 3. 台灣股市投資**：監控大盤 K 線、三大法人籌碼動向、個股技術面/基本面診斷，以及個人存股資產管理。
""")

st.info("💡 提示：左側選單是由 `pages/` 資料夾內的檔案自動生成的，切換頁面時系統會自動保留你的快取資料。")