import streamlit as st
import pandas as pd
import numpy as np
import requests
import urllib3
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re
import PyPDF2
import google.generativeai as genai
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="台灣股市投資", layout="wide")
st.title("📈 台灣股市戰情室")
st.markdown("追蹤台股大盤動向、法人與主力分點籌碼變化，以及個股全方位分析。")

# ==========================================
# 0. Gemini AI 配置 (用於綜合決策報告)
# ==========================================
HAS_GEMINI_KEY = False
try:
    if "GEMINI_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_KEY"], transport='rest')
        HAS_GEMINI_KEY = True
except Exception:
    pass

# ==========================================
# 1. 專屬抓取與處理引擎
# ==========================================
@st.cache_data(ttl=3600)
def get_realtime_price(symbol):
    try:
        symbol = str(symbol).strip()
        for suffix in [".TW", ".TWO"]:
            ticker = f"{symbol}{suffix}"
            data = yf.download(ticker, period="1d", progress=False)
            if not data.empty:
                return round(float(data['Close'].iloc[-1]), 2)
        return 0
    except:
        return 0

@st.cache_data(ttl=300)
def fetch_tw_indices():
    data = {
        "上市加權 (TAIEX)": {"price": "讀取失敗", "diff": "0.00 (0.00%)", "volume": "-", "history": None},
        "上櫃指數 (OTC)": {"price": "讀取失敗", "diff": "0.00 (0.00%)", "volume": "-", "history": None}
    }
    try:
        twii = yf.Ticker("^TWII").history(period="3mo")
        if twii is not None and not twii.empty and len(twii) >= 2:
            current = float(twii['Close'].iloc[-1])
            prev = float(twii['Close'].iloc[-2])
            vol = float(twii['Volume'].iloc[-1]) 
            diff = current - prev
            pct = (diff/prev)*100
            vol_display = "Yahoo API 暫不支援" if vol == 0 else f"{int(vol):,}"
            data["上市加權 (TAIEX)"] = {"price": f"{current:,.2f}", "diff": f"{diff:+.2f} ({pct:+.2f}%)", "volume": vol_display, "history": twii}
    except: pass
    try:
        two = yf.Ticker("006201.TWO").history(period="3mo")
        if two is not None and not two.empty and len(two) >= 2:
            current = float(two['Close'].iloc[-1])
            prev = float(two['Close'].iloc[-2])
            vol = float(two['Volume'].iloc[-1])
            diff = current - prev
            pct = (diff/prev)*100
            data["上櫃指數 (OTC)"] = {"price": f"{current:,.2f}", "diff": f"{diff:+.2f} ({pct:+.2f}%)", "volume": f"{int(vol):,}", "history": two}
    except: pass
    return data

@st.cache_data(ttl=300) 
def fetch_real_ranking_data():
    tickers = ["2330.TW", "2317.TW", "2454.TW", "2382.TW", "3231.TW", "2352.TW", "3017.TW", "3324.TW", "2324.TW", "2376.TW", "2356.TW", "2353.TW", "2303.TW", "2603.TW", "2609.TW", "2615.TW", "2618.TW", "2610.TW", "2881.TW", "2891.TW", "2882.TW", "2886.TW", "1519.TW", "3481.TW", "2409.TW", "2363.TW", "1101.TW", "2002.TW", "2308.TW", "2395.TW"]
    try:
        df = yf.download(tickers, period="5d", progress=False)
        results = []
        for ticker in tickers:
            try:
                closes = df['Close'][ticker].dropna()
                volumes = df['Volume'][ticker].dropna()
                if len(closes) >= 2:
                    current = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2])
                    diff_pct = ((current - prev) / prev) * 100
                    vol = int(volumes.iloc[-1] / 1000) 
                    name_map = {"2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "3231": "緯創", "2352": "佳世達", "2603": "長榮", "3481": "群創", "1519": "華城", "3017": "奇鋐", "3324": "雙鴻", "2324": "仁寶"}
                    stock_id = ticker.replace(".TW", "")
                    stock_name = name_map.get(stock_id, stock_id)
                    results.append({"股票名稱": f"{stock_id} {stock_name}", "收盤價_數值": current, "漲跌幅_數值": diff_pct, "成交量_數值": vol})
            except: continue
        res_df = pd.DataFrame(results)
        if res_df.empty: return None, None, None
        gainers = res_df.sort_values(by="漲跌幅_數值", ascending=False).head(10).copy()
        losers = res_df.sort_values(by="漲跌幅_數值", ascending=True).head(10).copy()
        volumes = res_df.sort_values(by="成交量_數值", ascending=False).head(10).copy()
        def format_df(d):
            d["收盤價"] = d["收盤價_數值"].apply(lambda x: f"{x:,.2f}")
            d["漲跌幅"] = d["漲跌幅_數值"].apply(lambda x: f"{x:+.2f}%")
            d["成交量(張)"] = d["成交量_數值"].apply(lambda x: f"{x:,}")
            return d[["股票名稱", "收盤價", "漲跌幅", "成交量(張)"]]
        return format_df(gainers), format_df(losers), format_df(volumes)
    except: return None, None, None

def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for i in range(min(10, len(pdf_reader.pages))):
            text += pdf_reader.pages[i].extract_text()
        return text
    except Exception as e:
        return ""

def generate_overall_ai_analysis(date_str, compiled_text, model_name):
    if not HAS_GEMINI_KEY: 
        return "⚠️ 未在 Secrets 中偵測到有效的 GEMINI_KEY。"

    prompt = f"""
    你是一位資深的台股籌碼與短線趨勢策略分析師。以下是 {date_str} 當日，三大法人（外資、投信、自營商）與六大關鍵主力券商分點的買賣超原始資料萃取內容：
    
    {compiled_text[:30000]}
    
    請針對這份今日上傳的籌碼數據，進行多空交叉解讀並產出明天的實戰操作指南。報告中必須精準包含以下核心大項：
    
    1. 🎯【今日買賣超熱門股深度分析】：
       - 請分別揪出今日法人與主力券商共同高度集中的【買超熱門股】與【賣超熱門股】。
       - 說明背後可能的主力意圖（如分點合力鎖股、法人倒貨等）。
       
    2. 📈【明日投資觀察建議與注意股票】：
       - 依據籌碼流向，明確列出投資人明天（次一交易日）應該「特別注意」的個股清單。
       - 給出具體的明日前瞻操作策略與觀察重點。
    
    請直接輸出分析內容，不需任何客套問候語，並請善用大標題、條列式與粗體字進行重點標示，保持整潔專業。
    """

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "404" in err_msg and "is not found" in err_msg:
            return f"❌ 您的金鑰不支援模型【{model_name}】。 👉 **請嘗試從選單切換成其他模型再試一次！**"
        return f"產生分析報告失敗: {err_msg}"

# ==========================================
# 2. 介面排版
# ==========================================
with st.spinner("正在載入台股大盤與排行數據..."):
    tw_data = fetch_tw_indices()
    gainers_df, losers_df, volume_df = fetch_real_ranking_data()

tab1, tab2, tab3 = st.tabs(["📊 大盤與排行", "🕵️‍♂️ 籌碼追蹤(法人與分點)", "🤖 個股分析"])

# ----------------- 分頁 1：大盤與排行 -----------------
with tab1:
    st.subheader("📌 台股上市櫃指數與 K 線動態")
    col1, col2 = st.columns(2)
    with col1: 
        st.metric("上市加權指數 (TAIEX)", tw_data["上市加權 (TAIEX)"]["price"], tw_data["上市加權 (TAIEX)"]["diff"])
        st.caption(f"📊 成交量數值：**{tw_data['上市加權 (TAIEX)']['volume']}**") 
    with col2: 
        st.metric("上櫃指數 (OTC)", tw_data["上櫃指數 (OTC)"]["price"], tw_data["上櫃指數 (OTC)"]["diff"])
        st.caption(f"📊 成交量數值：**{tw_data['上櫃指數 (OTC)']['volume']}** (富櫃50代理)")
    
    st.write("") 
    df_k = tw_data["上市加權 (TAIEX)"]["history"]
    if df_k is not None and not df_k.empty:
        df_k.index = df_k.index.tz_localize(None) 
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=df_k.index, open=df_k['Open'], high=df_k['High'], low=df_k['Low'], close=df_k['Close'], increasing_line_color='red', decreasing_line_color='green', name="K線"), row=1, col=1)
        colors = ['red' if row['Close'] >= row['Open'] else 'green' for idx, row in df_k.iterrows()]
        fig.add_trace(go.Bar(x=df_k.index, y=df_k['Volume'], marker_color=colors, name="成交量"), row=2, col=1)
        fig.update_layout(title="加權指數 近三個月 K 線與成交量", margin=dict(l=0, r=0, t=40, b=0), height=450, showlegend=False, xaxis_rangeslider_visible=False)
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])]) 
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ 暫時無法從 Yahoo Finance 取得 K 線歷史資料。")

    st.markdown("---")
    st.subheader("🔥 市場焦點排行 (真實數據)")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown("**📈 漲幅排行 Top 10**")
        if gainers_df is not None: st.dataframe(gainers_df, hide_index=True)
        else: st.warning("排行載入中")
    with r2:
        st.markdown("**📉 跌幅排行 Top 10**")
        if losers_df is not None: st.dataframe(losers_df, hide_index=True)
        else: st.warning("排行載入中")
    with r3:
        st.markdown("**💥 爆大量排行 Top 10**")
        if volume_df is not None: st.dataframe(volume_df, hide_index=True)
        else: st.warning("排行載入中")

# ----------------- 分頁 2：籌碼追蹤 -----------------
with tab2:
    st.markdown("### 🧠 當日整體籌碼 AI 綜合決策與明日建議")
    st.link_button("🔗 資料來源：券商分點進出查詢 (富邦)", "https://fubon-ebrokerdj.fbs.com.tw/Z/ZG/ZG_D.djhtm")
    st.write("請直接上傳今日各法人與主力分點的買賣超 PDF 或 TXT 檔案，系統將自動彙整並進行 AI 深度解析 (無需手動建檔儲存)。")

    col_date, _ = st.columns([1, 2])
    with col_date:
        selected_date = st.date_input("📅 選擇資料日期", datetime.now().date())
        date_str = str(selected_date)

    entities = ["外資", "投信", "自營商", "凱基台北", "元大新竹", "永豐金新竹", "富邦仁愛", "富邦建國", "富邦嘉義"]

    st.markdown("#### 📤 九大籌碼資料上傳區")
    
    uploaded_data = {}
    cols = st.columns(3)
    for idx, entity in enumerate(entities):
        with cols[idx % 3]:
            st.markdown(f"**{entity}**")
            files = st.file_uploader(f"上傳 {entity} 檔案", accept_multiple_files=True, type=['pdf', 'txt'], key=f"up_{entity}", label_visibility="collapsed")
            if files:
                uploaded_data[entity] = files
                st.success(f"✅ 已上傳 ({len(files)} 檔)")
            else:
                st.error("❌ 未上傳")

    st.divider()

    is_fully_ready = len(uploaded_data) == len(entities)
    if not is_fully_ready:
        st.warning("⚠️ 偵測到仍有部分分點或法人資料未上傳完畢。強烈建議全數上傳完成，以便 AI 進行最精準的交叉比對。")

    col_confirm_box, col_model_selector = st.columns([1, 2])
    with col_confirm_box:
        confirm_checked = st.checkbox("✅ 我確認資料皆已上傳完備", value=is_fully_ready, key="chk_confirm_uploaded_all")
    with col_model_selector:
        fallback_models = ['gemini-1.5-flash-001', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro']
        if HAS_GEMINI_KEY:
            try:
                models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                available_models = models if models else fallback_models
            except:
                available_models = fallback_models
        else:
            available_models = ['未設定金鑰']
        selected_model = st.selectbox("🤖 選擇分析決策模型", available_models, key="ai_final_model_selector")

    if st.button(f"🚀 啟動 {date_str} 籌碼 AI 綜合解析", type="primary", disabled=not confirm_checked):
        if not uploaded_data:
            st.error("請至少上傳一份資料檔案讓 AI 閱讀喔！")
        else:
            with st.spinner(f"AI ({selected_model}) 正在統整研讀所有上傳的原始檔案，請稍候..."):
                combo_text = ""
                for ent, files in uploaded_data.items():
                    combo_text += f"\n\n=== 【{ent}】買賣超資料 ===\n"
                    for f in files:
                        if f.name.endswith('.pdf'):
                            combo_text += extract_text_from_pdf(f) + "\n"
                        else:
                            combo_text += f.getvalue().decode("utf-8", errors="ignore") + "\n"

                analysis_report = generate_overall_ai_analysis(date_str, combo_text, selected_model)
                st.success("✅ AI 籌碼解析報告與操作建議生成完畢！")
                st.markdown(f"#### 📝 {date_str} 籌碼綜合決策報告")
                st.write(analysis_report)

                report_download = analysis_report.encode('utf-8-sig')
                st.download_button(
                    label="📥 匯出 AI 決策報告 (TXT 檔)",
                    data=report_download,
                    file_name=f"籌碼決策報告_{date_str}.txt",
                    mime="text/plain"
                )
                
    if not confirm_checked:
        st.caption("🔒 *請先勾選上方的『我確認資料皆已上傳完備』，即可解鎖並啟用 AI 深度解析按鈕。*")

# ----------------- 分頁 3：個股分析 -----------------
with tab3:
    st.markdown("### 🔍 個股全方位分析")
    
    st.markdown("##### 🔗 常用投資研究工具")
    l1, l2, l3, l4, l5 = st.columns(5)
    with l1: st.link_button("🌐 產業價值鏈平台", "https://ic.tpex.org.tw/")
    with l2: st.link_button("🌐 玩股網 WantGoo", "https://www.wantgoo.com/")
    with l3: st.link_button("🌐 MoneyDJ 財務", "https://concords.moneydj.com/z/zc/zcn/zcn_1101.djhtm")
    with l4: st.link_button("🌐 財報狗選股", "https://statementdog.com/screeners/custom")
    with l5: st.link_button("🌐 Yahoo奇摩股市", "https://tw.stock.yahoo.com/")
    
    st.write("") 
    
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1: analyze_code = st.text_input("請輸入股號", value="2330", key="analyze_input")
    with c2: period_choice = st.selectbox("技術面顯示區間", ["3mo", "6mo", "1y", "2y", "max"], index=0)
        
    if analyze_code:
        with st.spinner(f"正在分析 {analyze_code} ..."):
            df_hist = pd.DataFrame()
            stock_info = {}
            stock_name = ""
            for suffix in [".TW", ".TWO"]:
                ticker_full = f"{analyze_code}{suffix}"
                ticker_obj = yf.Ticker(ticker_full)
                df_hist = ticker_obj.history(period=period_choice)
                if not df_hist.empty:
                    # 💡 核心修復：加入 try-except 避震器防止 Yahoo 阻擋 IP 導致崩潰
                    try:
                        stock_info = ticker_obj.info 
                    except Exception:
                        stock_info = {}
                    
                    stock_name = stock_info.get('shortName', analyze_code)
                    break
                
            if not df_hist.empty:
                sub_tech, sub_fund = st.tabs(["📊 技術面分析", "🏢 基本面數據"])
                
                with sub_tech:
                    if isinstance(df_hist.columns, pd.MultiIndex): df_hist.columns = df_hist.columns.get_level_values(0)
                    df_hist['MA5'] = df_hist['Close'].rolling(window=5).mean()
                    df_hist['MA20'] = df_hist['Close'].rolling(window=20).mean()
                    df_hist['MA60'] = df_hist['Close'].rolling(window=60).mean()
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])
                    fig.add_trace(go.Candlestick(x=df_hist.index, open=df_hist['Open'], high=df_hist['High'], low=df_hist['Low'], close=df_hist['Close'], name="K線"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist['MA5'], name="MA5", line=dict(color='orange')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist['MA20'], name="MA20", line=dict(color='blue')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist['MA60'], name="MA60", line=dict(color='purple')), row=1, col=1)
                    colors = ['red' if df_hist['Close'].iloc[i] >= df_hist['Open'].iloc[i] else 'green' for i in range(len(df_hist))]
                    fig.add_trace(go.Bar(x=df_hist.index, y=df_hist['Volume'], name="成交量", marker_color=colors), row=2, col=1)
                    fig.update_layout(title=f"📈 {analyze_code} {stock_name} 技術走勢", xaxis_rangeslider_visible=False, height=600, template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)

                with sub_fund:
                    st.markdown(f"#### 🏦 {stock_name} ({analyze_code}) 公司基本面")
                    f_col1, f_col2, f_col3 = st.columns(3)
                    pe_ratio = stock_info.get('trailingPE', "N/A")
                    pb_ratio = stock_info.get('priceToBook', "N/A")
                    dividend_yield = stock_info.get('dividendYield', 0)
                    dividend_yield_display = f"{dividend_yield * 100:.2f} %" if dividend_yield else "N/A"
                    
                    with f_col1:
                        st.metric("本益比 (PE)", f"{pe_ratio}")
                        st.caption("衡量回本速度，通常越低越便宜")
                    with f_col2:
                        st.metric("股價淨值比 (PB)", f"{pb_ratio}")
                        st.caption("衡量資產價值，低於 1 可能被低估")
                    with f_col3:
                        st.metric("現金股利殖利率", dividend_yield_display)
                        st.caption("一年領到的利息佔股價的比率")
                    st.divider()
                    f_col4, f_col5, f_col6 = st.columns(3)
                    eps = stock_info.get('trailingEps', "N/A")
                    roe = stock_info.get('returnOnEquity', 0)
                    roe_display = f"{roe * 100:.2f} %" if roe else "N/A"
                    profit_margin = stock_info.get('profitMargins', 0)
                    pm_display = f"{profit_margin * 100:.2f} %" if profit_margin else "N/A"
                    
                    with f_col4: st.metric("每股盈餘 (EPS)", f"{eps}")
                    with f_col5: st.metric("股東權益報酬率 (ROE)", roe_display)
                    with f_col6: st.metric("淨利率", pm_display)
                    st.divider()
                    with st.expander("📖 查看公司產業簡介"):
                        summary = stock_info.get('longBusinessSummary', "無相關描述 (或 Yahoo 阻擋連線)")
                        st.write(summary)
                
                st.divider()
                st.markdown(f"### 🤖 【{stock_name}】AI 深度研究助理")
                st.caption("您可以在此上傳該公司的法說會報告、券商研報 (支援多個檔案)，或貼上財經新聞網址，讓 AI 為您進行交叉解析。")
                
                col_up1, col_up2 = st.columns(2)
                with col_up1:
                    uploaded_res_files = st.file_uploader("📂 上傳參考資料 (支援多個 PDF 或 TXT 檔)", accept_multiple_files=True, type=['pdf', 'txt'])
                with col_up2:
                    res_url = st.text_input("🔗 輸入參考新聞或資料網址 (選填)")
                    
                    fallback_models_t3 = ['gemini-1.5-flash-001', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro']
                    if HAS_GEMINI_KEY:
                        try:
                            models_t3 = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                            avail_models_t3 = models_t3 if models_t3 else fallback_models_t3
                        except:
                            avail_models_t3 = fallback_models_t3
                    else:
                        avail_models_t3 = ['未設定金鑰']
                    selected_model_t3 = st.selectbox("🤖 選擇解析模型", avail_models_t3, key="ai_model_t3")

                if st.button("🚀 啟動 AI 綜合研報解析", type="primary"):
                    if not HAS_GEMINI_KEY:
                        st.error("⚠️ 未設定 GEMINI_KEY，請先確認您的金鑰設定。")
                    elif not uploaded_res_files and not res_url:
                        st.warning("請至少上傳一份檔案，或是輸入一個參考網址讓 AI 閱讀喔！")
                    else:
                        with st.spinner("AI 正在發揮強大算力，閱讀並彙整多方資料中，請稍候..."):
                            combo_text = f"以下是針對【{stock_name} ({analyze_code})】的相關參考資料：\n\n"
                            
                            if uploaded_res_files:
                                for file in uploaded_res_files:
                                    combo_text += f"=== 檔案：{file.name} ===\n"
                                    if file.name.endswith('.pdf'):
                                        combo_text += extract_text_from_pdf(file) + "\n\n"
                                    else:
                                        combo_text += file.getvalue().decode("utf-8", errors="ignore") + "\n\n"
                            
                            if res_url:
                                combo_text += f"=== 網址參考：{res_url} ===\n"
                                try:
                                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                                    res = requests.get(res_url, headers=headers, timeout=5)
                                    clean_text = re.sub(r'<[^>]+>', ' ', res.text)
                                    combo_text += clean_text[:8000] + "\n\n"
                                except Exception as e:
                                    combo_text += f"(網址讀取失敗: {str(e)})\n\n"
                            
                            prompt = f"""
                            你是一位頂尖的證券分析師。請綜合研讀以下我提供的【{stock_name} ({analyze_code})】研究資料、新聞與報告：
                            
                            {combo_text[:30000]}
                            
                            請撰寫一份深度分析報告，報告需包含：
                            1. 總結這些資料中的核心重點與市場觀點。
                            2. 公司目前面臨的主要利多與利空因素。
                            3. 綜合評估與未來操作建議。
                            
                            請用繁體中文回覆，排版清晰，善用條列式與粗體字，無需客套話。
                            """
                            
                            try:
                                model = genai.GenerativeModel(selected_model_t3)
                                response = model.generate_content(prompt)
                                st.success("✅ 個股解析完成！")
                                
                                st.markdown(f"#### 📝 {stock_name} AI 深度研報")
                                st.write(response.text)
                                
                                report_download = response.text.encode('utf-8-sig')
                                st.download_button(
                                    label="📥 匯出 AI 深度研報 (TXT 檔)",
                                    data=report_download,
                                    file_name=f"{stock_name}_AI研報_{datetime.now().strftime('%Y%m%d')}.txt",
                                    mime="text/plain"
                                )
                            except Exception as e:
                                st.error(f"解析發生錯誤：{str(e)}")

            else:
                st.warning("找不到該股號的資料，請確認輸入是否正確。")
