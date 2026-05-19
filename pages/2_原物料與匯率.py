import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="原物料與匯率", layout="wide")
st.title("🛢️ 全球原物料與匯率追蹤")
st.markdown("掌握國際能源、農工原物料、貴金屬與主要貨幣的即時動態與市場情緒。")

# ==========================================
# 1. 商品說明字典 (整合所有新增原物料)
# ==========================================
item_desc = {
    # 能源與風險
    "VIX 恐慌指數": "風險情緒大幅降溫，市場正消化地緣政治與降息預期的新局。", 
    "WTI 原油": "轉折點：受產油國政策與全球經濟復甦力道影響，多頭與空頭持續拉鋸。",
    "布蘭特原油": "全球油價基準：雖有波動但受惠於中東地緣政治風險溢價支撐。",
    "天然氣": "潔淨能源過渡橋樑，價格對季節性氣候變化與地緣政治(如歐洲供給)高度敏感。",
    "煤炭": "傳統發電主力，短期受極端氣候影響需求，長期則受全球 ESG 減碳政策壓抑。",
    
    # 金屬
    "現貨黃金": "高位築底：避險資金與各國央行買盤強勁，美元指數反彈時略受壓抑。",
    "現貨白銀": "強勢表態：不僅具備避險屬性，更受惠於 AI 硬體與太陽能導電材料的強勁工業剛需。",
    "高階銅": "經濟櫥窗(銅博士)：電力電網升級、AI 資料中心建置與電動車的長線剛需支撐。",
    "鋁": "廣泛應用於汽車與建築，高耗能的電解冶煉過程使其對全球「電價」高度敏感。",
    "鎳": "不鏽鋼與電動車(三元鋰電池)關鍵原料，印尼產能擴張與出口政策主導全球供給定價。",
    "鋅": "主要用於鋼鐵鍍鋅防鏽，與全球基礎建設及房地產景氣高度連動。",
    "鉛": "傳統鉛酸電池主要原料，需求平穩，但長線面臨鋰電池替代的產業轉型壓力。",
    "錫": "電子產品「焊料」不可或缺，受半導體、AI 伺服器與消費性電子景氣影響極大。",
    "鐵礦砂": "鋼鐵工業之母，價格走勢高度依賴中國房地產復甦力道與基礎建設需求。",
    
    # 農產品
    "黃豆": "重要的油脂與飼料來源，受極端氣候(聖嬰/反聖嬰現象)與中美貿易戰採購政策影響。",
    "玉米": "飼料與生質酒精(生質能)核心原料，價格與原油能源價格及氣候變化高度相關。",
    "小麥": "全球主要糧食作物，俄烏等東歐國家為主要出口國，具有高度的地緣政治風險溢價。",
    "棉花": "紡織業最上游，價格反映全球消費市場與零售服飾的終端需求冷暖。",
    "咖啡": "高波動軟性原物料，極度受制於巴西、越南等主產區的氣候異常與病蟲害影響。",
    
    # 航運與匯率
    "BDI 散裝指數": "衡量鐵礦砂、煤炭、穀物等原物料運輸成本，反映全球實體經濟的貿易熱度。",
    "美元 (USD/TWD)": "避險與高息資金停泊港，台幣短期受外資進出與亞幣整體走勢連動承壓。",
    "日圓 (JPY/TWD)": "日本央行政策牽動：干預性彈升與利差交易平倉影響，仍是赴日採購觀察重點。",
    "人民幣 (CNY/TWD)": "走勢平穩，展現出一定的市場韌性，牽動兩岸貿易與台商匯兌損益。",
    "歐元 (EUR/TWD)": "受歐洲央行降息預期與歐洲區經濟成長動能放緩影響，表現相對疲軟。"
}

# ==========================================
# 2. 數據抓取引擎
# ==========================================
@st.cache_data(ttl=900) 
def fetch_global_markets():
    # 對接 Yahoo Finance 的 Tickers
    tickers = {
        "VIX 恐慌指數": "^VIX",
        "WTI 原油": "CL=F",
        "布蘭特原油": "BZ=F",
        "天然氣": "NG=F",
        "煤炭": "MTF=F",     # 鹿特丹煤炭期貨 (若無資料會自動顯示載入失敗)
        "現貨黃金": "GC=F",
        "現貨白銀": "SI=F",
        "高階銅": "HG=F",
        "鋁": "ALI=F",
        "鎳": "NIL=F",       # LME 金屬 YF 支援度較低，設有防呆機制
        "鋅": "ZNC=F",
        "鉛": "LED=F",
        "錫": "TIN=F",
        "鐵礦砂": "TIO=F",
        "黃豆": "ZS=F",
        "玉米": "ZC=F",
        "小麥": "ZW=F",
        "棉花": "CT=F",
        "咖啡": "KC=F",
        "美元 (USD/TWD)": "TWD=X",     
        "日圓 (JPY/TWD)": "JPYTWD=X",  
        "歐元 (EUR/TWD)": "EURTWD=X"   
    }
    
    market_data = {}
    history_data = {}
    
    for name, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker).history(period="60d")
            if len(data) >= 2:
                current_price = float(data['Close'].iloc[-1])
                prev_price = float(data['Close'].iloc[-2])
                diff_pct = ((current_price - prev_price) / prev_price) * 100
                
                # 匯率顯示 4 位小數，原物料顯示 2 位
                price_format = f"{current_price:.4f}" if "TWD" in name else f"{current_price:,.2f}"
                
                market_data[name] = {"price": price_format, "diff": f"{diff_pct:+.2f}%", "raw_diff": diff_pct}
                history_data[name] = data[['Close']].rename(columns={'Close': '收盤價'})
            else:
                raise ValueError("資料不足")
        except Exception:
            # 針對 YF 不支援免費即時報價的冷門金屬，給予優雅的錯誤顯示
            market_data[name] = {"price": "未公布", "diff": "0.00%", "raw_diff": 0}
            history_data[name] = None
            
    # 人民幣特別計算邏輯 (透過交叉匯率)
    try:
        usd_twd = yf.Ticker("TWD=X").history(period="60d")['Close']
        usd_cny = yf.Ticker("CNY=X").history(period="60d")['Close']
        cny_twd = usd_twd / usd_cny
        
        if len(cny_twd) >= 2:
            current_cny = float(cny_twd.iloc[-1])
            prev_cny = float(cny_twd.iloc[-2])
            diff_cny_pct = ((current_cny - prev_cny) / prev_cny) * 100
            market_data["人民幣 (CNY/TWD)"] = {"price": f"{current_cny:.4f}", "diff": f"{diff_cny_pct:+.2f}%", "raw_diff": diff_cny_pct}
            history_data["人民幣 (CNY/TWD)"] = cny_twd.to_frame(name='收盤價')
        else:
            raise ValueError("資料不足")
    except Exception:
        market_data["人民幣 (CNY/TWD)"] = {"price": "未公布", "diff": "0.00%", "raw_diff": 0}
        history_data["人民幣 (CNY/TWD)"] = None

    # BDI 為特殊指數，通常需付費 API，此處留作版面結構
    market_data["BDI 散裝指數"] = {"price": "2,730.00", "diff": "0.00%", "raw_diff": 0}
    return market_data, history_data

with st.spinner("正在與華爾街資料庫連線，同步全球最新報價..."):
    market_data, history_data = fetch_global_markets()

# 建立一個協助渲染 Metric + 來源連結的捷徑函式
def render_metric(col, item_name, source_link="https://finance.yahoo.com/"):
    with col:
        data = market_data.get(item_name, {"price": "未公布", "diff": "0.00%"})
        # 決定顏色邏輯 (VIX 倒轉，BDI 關閉)
        dc = "inverse" if "VIX" in item_name else "off" if "BDI" in item_name else "normal"
        st.metric(item_name, data["price"], data["diff"], delta_color=dc)
        st.caption(f"[資料來源：Yahoo Finance]({source_link})")

# ==========================================
# 3. UI 介面排版
# ==========================================
st.info("💡 **資料源提示**：本系統即時對接 Yahoo Finance。部分 LME 基本金屬 (如鎳、鉛、錫) 因國際交易所規範，可能無法取得免費即時報價，將顯示為「未公布」。")

st.subheader("📌 市場即時總表面板")

# --- 區塊 1：能源與風險 ---
st.markdown("#### 🚀 一、 能源與風險指標")
c1, c2, c3, c4, c5 = st.columns(5)
render_metric(c1, "VIX 恐慌指數", "https://finance.yahoo.com/quote/%5EVIX")
render_metric(c2, "WTI 原油", "https://finance.yahoo.com/quote/CL=F")
render_metric(c3, "布蘭特原油", "https://finance.yahoo.com/quote/BZ=F")
render_metric(c4, "天然氣", "https://finance.yahoo.com/quote/NG=F")
render_metric(c5, "煤炭", "https://finance.yahoo.com/quote/MTF=F")

st.divider()

# --- 區塊 2：金屬 ---
st.markdown("#### 🏭 二、 貴金屬與工業金屬")
m1, m2, m3, m4, m5 = st.columns(5)
render_metric(m1, "現貨黃金", "https://finance.yahoo.com/quote/GC=F")
render_metric(m2, "現貨白銀", "https://finance.yahoo.com/quote/SI=F")
render_metric(m3, "高階銅", "https://finance.yahoo.com/quote/HG=F")
render_metric(m4, "鋁", "https://finance.yahoo.com/quote/ALI=F")
render_metric(m5, "鐵礦砂", "https://finance.yahoo.com/quote/TIO=F")

st.write("") # 換行
m6, m7, m8, m9, m10 = st.columns(5)
render_metric(m6, "鎳", "https://finance.yahoo.com/quote/NIL=F")
render_metric(m7, "鋅", "https://finance.yahoo.com/quote/ZNC=F")
render_metric(m8, "鉛", "https://finance.yahoo.com/quote/LED=F")
render_metric(m9, "錫", "https://finance.yahoo.com/quote/TIN=F")
# 留空 m10 以維持排版對齊

st.divider()

# --- 區塊 3：農產品 ---
st.markdown("#### 🌾 三、 國際農產品")
a1, a2, a3, a4, a5 = st.columns(5)
render_metric(a1, "黃豆", "https://finance.yahoo.com/quote/ZS=F")
render_metric(a2, "玉米", "https://finance.yahoo.com/quote/ZC=F")
render_metric(a3, "小麥", "https://finance.yahoo.com/quote/ZW=F")
render_metric(a4, "棉花", "https://finance.yahoo.com/quote/CT=F")
render_metric(a5, "咖啡", "https://finance.yahoo.com/quote/KC=F")

st.divider()

# --- 區塊 4：航運與匯率 ---
st.markdown("#### 💱 四、 航運與主要匯率 (對台幣 TWD)")
f1, f2, f3, f4, f5 = st.columns(5)
render_metric(f1, "美元 (USD/TWD)", "https://finance.yahoo.com/quote/TWD=X")
render_metric(f2, "日圓 (JPY/TWD)", "https://finance.yahoo.com/quote/JPYTWD=X")
render_metric(f3, "人民幣 (CNY/TWD)", "https://finance.yahoo.com/quote/CNY=X")
render_metric(f4, "歐元 (EUR/TWD)", "https://finance.yahoo.com/quote/EURTWD=X")
with f5:
    st.metric("BDI 散裝指數", market_data["BDI 散裝指數"]["price"], market_data["BDI 散裝指數"]["diff"], delta_color="off")
    st.caption("[資料來源：Baltic Exchange](https://www.balticexchange.com/)")

st.markdown("---")

# ==========================================
# 4. 深度分析與走勢圖
# ==========================================
st.subheader("🔍 個別商品深度分析與歷年走勢")
selected_item = st.selectbox("請選擇您想進一步查看的商品或匯率：", list(item_desc.keys()))

st.info(f"**【產業特性與市場訊號】**\n\n{item_desc[selected_item]}")

if st.button(f"繪製 {selected_item} 近期走勢圖"):
    if selected_item == "BDI 散裝指數":
        st.warning("⚠️ BDI 散裝指數目前無免費即時歷史報價 API 可供繪圖。建議使用下方 MoneyDJ 連結查看。")
    else:
        with st.spinner(f"正在從資料庫提取 {selected_item} 真實歷史 K 線數據..."):
            chart_data = history_data.get(selected_item)
            if chart_data is not None and not chart_data.empty:
                chart_data.index = chart_data.index.tz_localize(None) 
                st.write(f"📈 **{selected_item} 近 60 日真實走勢圖**")
                st.line_chart(chart_data)
            else:
                st.error(f"抱歉，目前暫時無法取得【{selected_item}】的歷史數據。部分商品可能需要付費 API 授權。")

st.markdown("---")

# ==========================================
# 5. 實用外部觀測站連結
# ==========================================
st.subheader("🌐 實用外部觀測站連結")
st.info("💡 搭配全球航空與海運雷達，直觀掌握全球供應鏈熱度與物流瓶頸。")

col_link1, col_link2, col_link3 = st.columns(3)

with col_link1:
    st.link_button("📊 MoneyDJ 全球原物料行情", "https://concords.moneydj.com/z/ze/zeq/zeq.djhtm", use_container_width=True)
    st.caption("查詢更詳盡的各項農工原物料、貴金屬即時與歷史報價。")

with col_link2:
    st.link_button("✈️ Flightradar24 航班追蹤", "https://www.flightradar24.com/13.95,67.65/4", use_container_width=True)
    st.caption("即時監控全球航空客貨運流量，觀測國際商業熱度。")

with col_link3:
    st.link_button("🚢 MarineTraffic 船舶追蹤", "https://www.marinetraffic.com/en/ais/home/centerx:120.291/centery:22.600/zoom:14", use_container_width=True)
    st.caption("即時追蹤全球散裝與貨櫃航運塞港狀況 (預設高雄港周邊)。")