import streamlit as st
import pandas as pd
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

st.set_page_config(page_title="getValue | Financial Analysis", layout="wide")

st.markdown("""
    <style>
    .section-header { font-size: 1.1em; font-weight: bold; color: #ffffff; background-color: #1c2b46; padding: 6px 15px; border-radius: 4px; margin-top: 25px; }
    .stTable { font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h1 style='color:#007bff;'>getValue</h1>", unsafe_allow_html=True)
    view_type = st.radio("Period:", ["Annual", "Quarterly"])

st.write(f"### Hi Rami, Let's get Value")
ticker = st.text_input("Enter Ticker:", "NVDA").upper()

if st.button("Run Analysis"):
    st.cache_data.clear()  # force fresh fetch on every run
    raw = GatewayAgent().fetch_all(ticker)
    norm = DataNormalizer(raw, ticker)
    
    def fmt(v, is_pct=False):
        if v is None: return "N/A"
        try:
            if pd.isna(v): return "N/A"
        except (TypeError, ValueError):
            pass
        if v == 0: return "N/A"
        if is_pct: return f"{v*100:.2f}%"
        a = abs(v)
        if a >= 1e9: return f"{v/1e9:.2f}B"
        if a >= 1e6: return f"{v/1e6:.2f}M"
        return f"{v:,.2f}"

    p = view_type.lower()
    hdrs = norm.get_column_headers(p)
    # hdrs = ["Item", "TTM", period1, ..., period10] — בדיוק 10 תקופות + TTM
    period_cols = hdrs[1:]  # ["TTM", period1, ..., period10]

    # column_config: רוחב מינימלי 120px לכל עמודת תקופה (גורם לגלילה אופקית במובייל)
    fin_col_config = {col: st.column_config.TextColumn(col, width=120) for col in period_cols}

    tab_fin, tab_ins = st.tabs(["📋 Financials", "💡 Insights"])

    with tab_fin:
        tables = [
            ("Income Statement", norm.get_income_statement),
            ("Cashflow", norm.get_cash_flow),
            ("Balance Sheet", norm.get_balance_sheet),
            ("Debt", norm.get_debt_table)
        ]
        for title, method in tables:
            st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
            data = method(p)
            df = pd.DataFrame([{"Item": r["label"], **{h: fmt(r.get(h)) for h in period_cols}} for r in data])
            st.dataframe(df.set_index("Item"), use_container_width=True, column_config=fin_col_config)

    with tab_ins:
        sections = [
            ("Growth (CAGR)", norm.get_insights_cagr, ["3yr", "5yr", "10yr"], True),
            ("Valuation Multiples", norm.get_insights_valuation, ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
            ("Profitability", norm.get_insights_profitability, ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
            ("Returns Analysis", norm.get_insights_returns, ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
            ("Liquidity", norm.get_insights_liquidity, ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
            ("Dividends", norm.get_insights_dividends, ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
            ("Efficiency", norm.get_insights_efficiency, ["TTM", "Avg. 5yr", "Avg. 10yr"], False)
        ]
        for title, method, cols, is_pct in sections:
            st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
            df = pd.DataFrame(method())
            for c in cols:
                df[c] = df[c].apply(lambda x: fmt(x, is_pct))
            ins_col_config = {col: st.column_config.TextColumn(col, width=120) for col in cols}
            st.dataframe(df.set_index(df.columns[0]), use_container_width=True, column_config=ins_col_config)
