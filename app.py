import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

st.set_page_config(page_title="getValue | Financial Analysis", layout="wide")

# CSS
st.markdown("<style>.section-header { font-size: 1.5em; font-weight: bold; color: #007bff; border-bottom: 2px solid #007bff; margin: 1em 0; }</style>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>getValue</h2>", unsafe_allow_html=True)
    view_type = st.radio("Select Period:", ["Annual", "Quarterly"])

st.markdown(f"### Hi Rami, Let's get Value")
ticker = st.text_input("Ticker:", "NVDA").upper()

if st.button("Run Analysis"):
    raw = GatewayAgent().fetch_all(ticker)
    norm = DataNormalizer(raw, ticker)
    
    def fmt(v, is_pct=False):
        if v is None: return "—"
        return f"{v*100:.2f}%" if is_pct else f"{v:,.2f}"

    tabs = st.tabs(["📊 Performance", "💡 Insights", "📋 Financials"])
    
    with tabs[1]:
        st.markdown("<div class='section-header'>Growth (CAGR)</div>", unsafe_allow_html=True)
        df_cagr = pd.DataFrame(norm.get_insights_cagr())
        for col in ["3yr", "5yr", "10yr"]: df_cagr[col] = df_cagr[col].apply(lambda x: fmt(x, True))
        st.table(df_cagr.set_index("CAGR"))
        
        st.markdown("<div class='section-header'>Valuation Multiples</div>", unsafe_allow_html=True)
        df_val = pd.DataFrame(norm.get_insights_valuation())
        for col in ["TTM", "Avg. 5yr", "Avg. 10yr"]: df_val[col] = df_val[col].apply(lambda x: fmt(x))
        st.table(df_val.set_index("Valuation"))
