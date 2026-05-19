import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
import urllib3
import yfinance as yf
import google.generativeai as genai
import PyPDF2
from datetime import datetime

# 隱藏 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 0. Gemini AI 配置 (自動從 Secrets 讀取)
# ==========================================
HAS_GEMINI_KEY = False
try:
    if "GEMINI_KEY" in st.secrets:
        # 💡 強制使用 REST API 通訊，繞過 Windows/企業防火牆的 gRPC 阻擋
        genai.configure(api_key=st.secrets["GEMINI_KEY"], transport='rest')
        HAS_GEMINI_KEY = True
except Exception:
    pass

# ==========================================
# 1. 核心處理工具與 AI 引擎
# ==========================================
def parse_tw_date(x):
    """轉換民國年格式為西元年/月"""
    x = str(x).strip()
    try:
        if 'M' in x:
            parts = x.split('M')
            return f"{int(parts[0])+1911}/{parts[1]}"
        elif len(x) == 5 and x.isdigit():
            return f"{int(x[:3])+1911}/{x[3:]}"
        elif len(x) == 6 and x.isdigit():
            return f"{x[:4]}/{x[4:]}"
        return x
    except: return x

def get_gemini_analysis(content, context_type="數據分析"):
    """具備完整錯誤捕捉的 AI 分析引擎"""
    if not HAS_GEMINI_KEY: 
        return "⚠️ 未在 .streamlit/secrets.toml 中偵測到有效的 GEMINI_KEY。"
    
    models_to_try = [
        'gemini-1.5-flash-latest',
        'gemini-1.5-flash', 
        'gemini-1.5-pro-latest',
        'gemini-1.5-pro', 
        'gemini-pro',
        'gemini-1.0-pro'
    ]
    
    prompt = f"你是一位資深台灣經貿分析師。請針對以下{context_type}內容進行專業解讀：\n\n{content}\n\n" \
             f"請提供核心亮點、產業強弱觀察、對台股的影響以及未來展望。使用繁體中文條列呈現。"
    
    error_logs = []
    
    try:
        available_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if available_models:
            models_to_try = available_models
    except Exception as e:
        error_logs.append(f"【獲取模型清單失敗】: {str(e)}")

    for model_name in models_to_try:
        try:
            full_model_name = model_name if model_name.startswith('models/') else f"models/{model_name}"
            model = genai.GenerativeModel(full_model_name)
            response = model.generate_content(prompt)
            return f"*(✅ 成功透過 {model_name} 模型分析)*\n\n" + response.text
        except Exception as e:
            error_logs.append(f"【{model_name}】錯誤: {str(e)}")
            continue
            
    error_msg = "\n\n".join(error_logs)
    return f"❌ **AI 分析連線失敗**。這通常是因為金鑰未開通 Generative Language API 權限，或該專案無效。\n\n**詳細錯誤紀錄：**\n{error_msg}"

def extract_text_from_pdf(pdf_file):
    """提取 PDF 檔案中的文字內容"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for i in range(min(5, len(pdf_reader.pages))):
            text += pdf_reader.pages[i].extract_text()
        return text
    except Exception as e:
        return f"PDF 讀取錯誤：{e}"

# ==========================================
# 2. 數據抓取引擎 (14項完整指標)
# ==========================================
@st.cache_data(ttl=3600)  
def fetch_full_macro_data():
    init_item = {"val": "未公布", "prev": None, "date": "-", "src": "#"}
    data = {k: init_item.copy() for k in [
        "gdp", "gnp", "cpi", "core_cpi", "ppi", "unemployment", "salary", 
        "pmi", "score", "stock_index", "export_order", "m1", "m2", "trade_balance"
    ]}
    
    data["gdp"]["src"] = "https://www.dgbas.gov.tw/"
    data["gnp"]["src"] = "https://www.dgbas.gov.tw/"
    data["cpi"]["src"] = "https://www.dgbas.gov.tw/"
    data["core_cpi"]["src"] = "https://www.dgbas.gov.tw/"
    data["ppi"]["src"] = "https://www.dgbas.gov.tw/"
    data["unemployment"]["src"] = "https://www.dgbas.gov.tw/"
    data["salary"]["src"] = "https://www.mol.gov.tw/"
    data["pmi"]["src"] = "https://www.ndc.gov.tw/"
    data["score"]["src"] = "https://www.ndc.gov.tw/"
    data["stock_index"]["src"] = "https://www.twse.com.tw/"
    data["export_order"]["src"] = "https://www.moea.gov.tw/"
    data["m1"]["src"] = "https://www.cbc.gov.tw/"
    data["m2"]["src"] = "https://www.cbc.gov.tw/"
    data["trade_balance"]["src"] = "https://www.mof.gov.tw/"

    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        res = requests.get("https://ods.ndc.gov.tw/download/27/1/1/csv", headers=headers, timeout=5, verify=False)
        res.encoding = 'utf-8'
        df = pd.read_csv(io.StringIO(res.text))
        curr, prev = df.iloc[-1], df.iloc[-2]
        data["score"].update({
            "val": f"{int(curr['景氣對策信號(分數)'])} 分",
            "prev": f"{curr['景氣對策信號(燈號)']} (差額 {int(curr['景氣對策信號(分數)'])-int(prev['景氣對策信號(分數)']):+d})",
            "date": parse_tw_date(curr.iloc[0])
        })
    except: pass

    try:
        res = requests.get("https://ws.dgbas.gov.tw/001/Upload/463/opendata/twn/1301010134-1.csv", headers=headers, timeout=5, verify=False)
        res.encoding = 'utf-8'
        df = pd.read_csv(io.StringIO(res.text))
        curr, prev = df.iloc[-1], df.iloc[-2]
        data["cpi"].update({"val": f"{curr.values[-1]}%", "prev": f"{curr.values[-1]-prev.values[-1]:+.2f}%", "date": parse_tw_date(curr.iloc[0])})
        
        res_u = requests.get("https://ws.dgbas.gov.tw/001/Upload/463/opendata/twn/1301010144-1.csv", headers=headers, timeout=5, verify=False)
        res_u.encoding = 'utf-8'
        df_u = pd.read_csv(io.StringIO(res_u.text))
        curr_u, prev_u = df_u.iloc[-1], df_u.iloc[-2]
        data["unemployment"].update({"val": f"{curr_u.values[-1]}%", "prev": f"{curr_u.values[-1]-prev_u.values[-1]:+.2f}%", "date": parse_tw_date(curr_u.iloc[0])})
        
        res_g = requests.get("https://ws.dgbas.gov.tw/001/Upload/463/opendata/twn/1301010001-1.csv", headers=headers, timeout=5, verify=False)
        res_g.encoding = 'utf-8'
        df_g = pd.read_csv(io.StringIO(res_g.text))
        curr_g, prev_g = df_g.iloc[-1], df_g.iloc[-2]
        data["gdp"].update({"val": f"{curr_g.values[-1]}%", "prev": f"{curr_g.values[-1]-prev_g.values[-1]:+.2f}%", "date": f"{int(str(curr_g.iloc[0])[:3])+1911}Q{str(curr_g.iloc[0])[3:]}"})
        
        res_p = requests.get("https://ods.ndc.gov.tw/download/27/1/5/csv", headers=headers, timeout=5, verify=False)
        res_p.encoding = 'utf-8'
        df_p = pd.read_csv(io.StringIO(res_p.text))
        curr_p, prev_p = df_p.iloc[-1], df_p.iloc[-2]
        val_curr, val_prev = float(curr_p['臺灣製造業採購經理人指數(PMI)']), float(prev_p['臺灣製造業採購經理人指數(PMI)'])
        data["pmi"].update({"val": f"{val_curr}", "prev": f"{val_curr-val_prev:+.1f}", "date": parse_tw_date(curr_p.iloc[0])})
    except: pass

    try:
        twii = yf.Ticker("^TWII").history(period="5d")
        cp, pp = twii['Close'].iloc[-1], twii['Close'].iloc[-2]
        data["stock_index"].update({"val": f"{cp:,.0f}", "prev": f"{cp-pp:+.2f} ({(cp-pp)/pp*100:+.2f}%)", "date": datetime.now().strftime("%Y/%m/%d")})
        
        res_t = requests.get("https://stat.mof.gov.tw/web/Data/OpenData/B01.csv", headers=headers, timeout=5, verify=False)
        res_t.encoding = 'utf-8-sig'
        df_t = pd.read_csv(io.StringIO(res_t.text))
        curr_t = df_t.iloc[-1]
        data["trade_balance"].update({"val": f"{float(curr_t.values[1].replace(',', ''))/100000:.1f} 億", "date": parse_tw_date(curr_t.iloc[0])})
    except: pass

    return data

# ==========================================
# 3. UI 介面設計
# ==========================================
st.set_page_config(page_title="台灣經濟狀況", layout="wide")
macro = fetch_full_macro_data()
tab1, tab2, tab3 = st.tabs(["🏛️ 總體經濟指標看板", "🚢 產業外銷 AI 分析", "📖 台經院景氣動向調查"])

# --- Tab 1: 全方位 14 項指標看板 ---
with tab1:
    st.title("📊 台灣總體經濟戰情室")
    
    st.markdown("#### 💎 國民所得與產出")
    c1, c2 = st.columns(2)
    with c1:
        st.metric(label=f"國內生產毛額 GDP ({macro['gdp']['date']})", value=macro['gdp']['val'], delta=macro['gdp']['prev'])
        st.caption(f"[資料來源：主計總處]({macro['gdp'].get('src', '#')})")
    with c2:
        st.metric(label=f"國民生產毛額 GNP ({macro['gnp']['date']})", value=macro['gnp']['val'], delta=macro['gnp']['prev'])
        st.caption(f"[資料來源：主計總處]({macro['gnp'].get('src', '#')})")

    st.divider()
    st.markdown("#### 💸 物價、通膨與生產者價格")
    c3, c4, c5 = st.columns(3)
    with c3:
        st.metric(label=f"消費者物價指數 CPI ({macro['cpi']['date']})", value=macro['cpi']['val'], delta=macro['cpi']['prev'], delta_color="inverse")
        st.caption(f"[資料來源：主計總處]({macro['cpi'].get('src', '#')})")
    with c4:
        st.metric(label=f"核心 CPI ({macro['core_cpi']['date']})", value=macro['core_cpi']['val'], delta=macro['core_cpi']['prev'], delta_color="inverse")
        st.caption(f"[資料來源：主計總處]({macro['core_cpi'].get('src', '#')})")
    with c5:
        st.metric(label=f"生產者物價指數 PPI ({macro['ppi']['date']})", value=macro['ppi']['val'], delta=macro['ppi']['prev'], delta_color="inverse")
        st.caption(f"[資料來源：主計總處]({macro['ppi'].get('src', '#')})")

    st.divider()
    st.markdown("#### 💼 就業與薪資成長")
    c6, c7 = st.columns(2)
    with c6:
        st.metric(label=f"失業率 ({macro['unemployment']['date']})", value=macro['unemployment']['val'], delta=macro['unemployment']['prev'], delta_color="inverse")
        st.caption(f"[資料來源：主計總處]({macro['unemployment'].get('src', '#')})")
    with c7:
        st.metric(label=f"薪資成長率 ({macro['salary']['date']})", value=macro['salary']['val'], delta=macro['salary']['prev'])
        st.caption(f"[資料來源：勞動部]({macro['salary'].get('src', '#')})")

    st.divider()
    st.markdown("#### 🚀 景氣、燈號與外銷訂單")
    c8, c9, c10 = st.columns(3)
    with c8:
        st.metric(label=f"景氣對策信號 ({macro['score']['date']})", value=macro['score']['val'], delta=macro['score']['prev'])
        st.caption(f"[資料來源：國發會]({macro['score'].get('src', '#')})")
    with c9:
        st.metric(label=f"製造業 PMI ({macro['pmi']['date']})", value=macro['pmi']['val'], delta=macro['pmi']['prev'])
        st.caption(f"[資料來源：國發會]({macro['pmi'].get('src', '#')})")
    with c10:
        st.metric(label=f"外銷訂單概況 ({macro['export_order']['date']})", value=macro['export_order']['val'], delta=macro['export_order']['prev'])
        st.caption(f"[資料來源：經濟部]({macro['export_order'].get('src', '#')})")

    st.divider()
    st.markdown("#### 💹 金融、貨幣供給與貿易收支")
    c11, c12, c13, c14 = st.columns(4)
    with c11:
        st.metric(label=f"股價指數 ({macro['stock_index']['date']})", value=macro['stock_index']['val'], delta=macro['stock_index']['prev'])
        st.caption(f"[資料來源：證交所]({macro['stock_index'].get('src', '#')})")
    with c12:
        st.metric(label=f"貨幣供給 M1B ({macro['m1']['date']})", value=macro['m1']['val'], delta=macro['m1']['prev'])
        st.caption(f"[資料來源：中央銀行]({macro['m1'].get('src', '#')})")
    with c13:
        st.metric(label=f"貨幣供給 M2 ({macro['m2']['date']})", value=macro['m2']['val'], delta=macro['m2']['prev'])
        st.caption(f"[資料來源：中央銀行]({macro['m2'].get('src', '#')})")
    with c14:
        st.metric(label=f"貿易順/逆差 ({macro['trade_balance']['date']})", value=macro['trade_balance']['val'], delta=macro['trade_balance']['prev'])
        st.caption(f"[資料來源：財政部]({macro['trade_balance'].get('src', '#')})")

# --- Tab 2: 產業外銷 AI 分析 ---
with tab2:
    st.subheader("🚢 產業外銷數據解讀 (Gemini AI)")
    
    # 💡 增加來源下載按鈕
    st.info("💡 **資料下載區**：請先至下方官方網站下載對應的 Excel/CSV 檔案，再上傳進行 AI 分析。")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.link_button("📊 下載【外銷訂單】統計", "https://www.moea.gov.tw/MNS/dos/bulletin/Bulletin.aspx?kind=5&html=1&menu_id=6724", use_container_width=True)
    with col_dl2:
        st.link_button("📦 下載【進出口統計】", "https://portal.sw.nat.gov.tw/APGA/GA30", use_container_width=True)
        
    st.write("") # 留白
    
    trade_type = st.radio("選擇分析類型：", ["外銷訂單", "進出口統計"], horizontal=True)
    excel_file = st.file_uploader(f"上傳 {trade_type} Excel/CSV 檔", type=["xls", "xlsx", "csv"])
    
    if excel_file:
        try:
            if excel_file.name.endswith('.csv'): 
                df = pd.read_csv(excel_file)
            else: 
                df = pd.read_excel(excel_file)
                
            st.success("✅ 檔案讀取成功！")
            st.dataframe(df.head(), use_container_width=True)
            
            if st.button(f"🤖 啟動 {trade_type} AI 深度分析"):
                with st.spinner("AI 正在連線中..."):
                    summary = df.to_string(index=False, max_rows=30)
                    analysis = get_gemini_analysis(summary, f"{trade_type}數據")
                    st.markdown("---")
                    st.markdown(f"### 🧠 Gemini AI - {trade_type}分析結果")
                    st.write(analysis)
                    
                    st.download_button(label="📥 下載 AI 分析報告", data=analysis, file_name=f"AI分析_{trade_type}_{datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain")
                    
        except ImportError as ie:
            if 'xlrd' in str(ie):
                st.error("❌ 系統缺少讀取舊版 Excel (.xls) 的套件。請在終端機執行：`pip install xlrd`")
            elif 'openpyxl' in str(ie):
                st.error("❌ 系統缺少讀取新版 Excel (.xlsx) 的套件。請在終端機執行：`pip install openpyxl`")
            else:
                st.error(f"檔案載入失敗: {ie}")
        except Exception as e:
            st.error(f"檔案解析發生不可預期的錯誤: {e}")

# --- Tab 3: 台經院景氣動向調查 ---
with tab3:
    st.subheader("📖 台經院景氣動向調查 (AI 解析)")
    
    # 💡 增加來源下載按鈕
    st.info("💡 **資料下載區**：請先至下方官方網站下載當月發布的景氣動向調查 PDF 報告。")
    st.link_button("📄 前往台經院下載【景氣動向調查報告】", "https://www.tier.org.tw/forecast/forecast.aspx", use_container_width=True)
    
    st.write("") # 留白
    
    c1, c2 = st.columns(2)
    with c1:
        report_year = st.selectbox("選擇報告年度：", ["2026", "2025", "2024"], index=0)
    with c2:
        report_month = st.selectbox("選擇報告月份：", [f"{i}月" for i in range(1, 13)], index=datetime.now().month - 2 if datetime.now().month > 1 else 11)
        
    pdf_file = st.file_uploader(f"上傳 {report_year} {report_month} 台經院 PDF 報告", type=["pdf"])
    
    if pdf_file:
        st.success(f"✅ 報告已就緒：{pdf_file.name}")
        if st.button("🤖 啟動 PDF 內容深度解讀"):
            with st.spinner("正在掃描 PDF 並萃取重點..."):
                pdf_text = extract_text_from_pdf(pdf_file)
                if len(pdf_text) > 50:
                    analysis = get_gemini_analysis(pdf_text, f"台經院{report_year}{report_month}景氣動向報告")
                    st.markdown("---")
                    st.markdown(f"### 🧠 Gemini AI - 報告解讀專區")
                    st.write(analysis)
                    
                    st.download_button(label="📥 下載報告重點摘錄", data=analysis, file_name=f"台經院解析_{report_year}_{report_month}.txt", mime="text/plain")
                else:
                    st.error("無法從 PDF 中提取足夠的文字，請確認該檔案非純影像掃描檔。")