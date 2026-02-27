import io, sys, os
import streamlit as st
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

# הגדרות עמוד
st.set_page_config(page_title="getValue | Financial Analysis", layout="wide", initial_sidebar_state="expanded")

# CSS לשדרוג ה-UX והעיצוב
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .welcome-text {
        font-size: 24px;
        font-weight: 500;
        color: #1c2b46;
        margin-bottom: 10px;
    }
    .logo-text {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: #007bff;
        font-size: 32px;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
        font-weight: bold;
    }
    /* עיצוב הטאבים */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# סרגל צידי עם הלוגו החדש
with st.sidebar:
    st.markdown("<div class='logo-text'>getValue</div>", unsafe_allow_html=True)
    st.info("Professional Investor Platform")
    view_type = st.radio("Select Report Period:", ["Annual", "Quarterly"])
    st.divider()
    if "FMP_API_KEY" in st.secrets:
        st.success("API Status: Connected")
    else:
        st.error("API Status: Disconnected")

# גוף האתר - ברכה אישית
st.markdown(f"<div class='welcome-text'>Hi Rami, Let's get Value</div>", unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    ticker = st.text_input("Enter Company Ticker:", "NVDA", placeholder="e.g. AAPL, MSFT").upper()
with col2:
    st.write(" ") 
    st.write(" ") 
    analyze_btn = st.button("Run Analysis")

if analyze_btn:
    with st.spinner(f"Analyzing {ticker} financials..."):
        gateway = GatewayAgent()
        raw = gateway.fetch_all(ticker)
        
        if not raw.get("annual_income_statement"):
            st.error(f"Waiting for API activation for {ticker} (Legacy Error check)...")
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

        tab1, tab2, tab3, tab4 = st.tabs(["📈 Income", "💸 Cash Flow", "⚖️ Balance Sheet", "💳 Debt"])

        with tab1:
            st.subheader("Income Statement")
            df_is = pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_income_statement(p)]).set_index("Item")
            st.table(df_is)
            
        with tab2:
            st.subheader("Cash Flow")
            df_cf = pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_cash_flow(p)]).set_index("Item")
            st.table(df_cf)

        with tab3:
            st.subheader("Balance Sheet")
            df_bs = pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_balance_sheet(p)]).set_index("Item")
            st.table(df_bs)
            
        with tab4:
            st.subheader("Debt Analysis")
            df_debt = pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in norm.get_debt_table(p)]).set_index("Item")
            st.table(df_debt)

        st.success(f"Analysis for {ticker} completed.")
