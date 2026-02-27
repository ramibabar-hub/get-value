import streamlit as st
import pandas as pd
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

st.set_page_config(page_title="getValue | Insights", layout="wide")

st.markdown("""
    <style>
    .section-header { font-size: 1.2em; font-weight: bold; color: #ffffff; background-color: #007bff; padding: 5px 15px; border-radius: 5px; margin-top: 20px; }
    table { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("getValue")
    view_type = st.radio("Period:", ["Annual", "Quarterly"])

st.write(f"### Hi Rami, Let's get Value")
ticker = st.text_input("Ticker:", "NVDA").upper()

if st.button("Run Analysis"):
    raw = GatewayAgent().fetch_all(ticker)
    norm = DataNormalizer(raw, ticker)
    
    def fmt(v, is_pct=False):
        if v is None: return "N/A"
        return f"{v*100:.2f}%" if is_pct else f"{v:,.2f}"

    tab_ins, tab_fin = st.tabs(["💡 Insights", "📋 Financials"])

    with tab_ins:
        # סקציות לפי הסדר שביקשת
        sections = [
            ("CAGR", norm.get_insights_cagr, ["3yr", "5yr", "10yr"], True),
            ("Valuation", norm.get_insights_valuation, ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
            ("Profitability", norm.get_insights_profitability, ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
            ("Returns", norm.get_insights_returns, ["TTM", "Avg. 5yr", "Avg. 10yr"], True)
        ]

        for title, method, cols, is_pct in sections:
            st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
            df = pd.DataFrame(method())
            for c in cols: df[c] = df[c].apply(lambda x: fmt(x, is_pct))
            st.table(df.set_index(df.columns[0]))

    with tab_fin:
        st.write("Financial Statements will be displayed here.")
