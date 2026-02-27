import io, sys, os
import streamlit as st
import pandas as pd
import requests
sys.path.insert(0, os.path.dirname(__file__))
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

# הגדרות עמוד
st.set_page_config(page_title="getValue | Financial Analysis", layout="wide", initial_sidebar_state="expanded")

# CSS לשדרוג ה-UX
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .welcome-text { font-size: 24px; font-weight: 500; color: #1c2b46; margin-bottom: 10px; }
    .logo-text { font-family: 'Inter', sans-serif; font-weight: 700; color: #007bff; font-size: 32px; text-align: center; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# סרגל צידי
with st.sidebar:
    st.markdown("<div class='logo-text'>getValue</div>", unsafe_allow_html=True)
    st.info("Professional Investor Platform")
    view_type = st.radio("Select Report Period:", ["Annual", "Quarterly"])
    st.divider()
    
    # כלי אבחון (Debug Mode)
    st.write("🔍 **API Diagnostic:**")
    api_key = st.secrets.get("FMP_API_KEY", "").strip().strip('"').strip("'")
    if st.button("Test API Connection"):
        test_url = f"https://financialmodelingprep.com/api/v3/income-statement/AAPL?apikey={api_key}&limit=1"
        try:
            res = requests.get(test_url, timeout=10)
            st.code(f"Status: {res.status_code}")
            st.json(res.json())
        except Exception as e:
            st.error(f"Error: {e}")

# גוף האתר
st.markdown(f"<div class='welcome-text'>Hi Rami, Let's get Value</div>", unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    ticker = st.text_input("Enter Company Ticker:", "NVDA").upper()
with col2:
    st.write(" ") 
    st.write(" ") 
    analyze_btn = st.button("Run Analysis")

if analyze_btn:
    with st.spinner(f"Analyzing {ticker}..."):
        gateway = GatewayAgent()
        raw = gateway.fetch_all(ticker)
        
        has_data = any(len(v) > 0 for v in raw.values())
        
        if not has_data:
            st.error(f"❌ No data received for {ticker}.")
            st.warning("Please check the Diagnostic tool in the sidebar.")
            st.stop()
            
        norm = DataNormalizer(raw, ticker)
        def fmt(v):
            if v is None or v == 0: return "—"
            if not isinstance(v, (int, float)): return str(v)
            a = abs(v)
            if a >= 1e9: return f"{v/1e9:.2f}B"
            if a >= 1e6: return f"{v/1e6:.2f}M"
            return f"{v:,.2f}"

        p = view_type.lower()
        hdrs = norm.get_column_headers(p)
        tabs = st.tabs(["📈 Income", "💸 Cash Flow", "⚖️ Balance Sheet", "💳 Debt"])

        with tabs[0]:
            st.table(pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_income_statement(p)]).set_index("Item"))
        with tabs[1]:
            st.table(pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_cash_flow(p)]).set_index("Item"))
        with tabs[2]:
            st.table(pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_balance_sheet(p)]).set_index("Item"))
        with tabs[3]:
            st.table(pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_debt_table(p)]).set_index("Item"))

        st.success(f"Analysis for {ticker} completed.")
