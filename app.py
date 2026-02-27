import io, sys, os
import streamlit as st
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

st.set_page_config(page_title="Get Value", layout="wide")
st.title("📊 Get Value — Financial Viewer")

# Debug: בדיקה אם המפתח נקלט
if "FMP_API_KEY" not in st.secrets:
    st.error("❌ API Key not found in Secrets! Please add FMP_API_KEY to Settings -> Secrets.")
else:
    st.sidebar.success("✅ API Key loaded from Secrets")

ticker = st.text_input("Enter Ticker", "NVDA").upper()
view_type = st.selectbox("Select View", ["Annual", "Quarterly"])

if st.button("Analyze", type="primary"):
    with st.spinner(f"Fetching data for {ticker}..."):
        gateway = GatewayAgent()
        raw = gateway.fetch_all(ticker)
        
        # בדיקה אם הנתונים הגיעו
        if not raw["annual_income_statement"]:
            st.error(f"❌ No data received for {ticker}. This usually means the API Key is invalid or restricted.")
            st.info("Tip: Double check your API Key in Streamlit Secrets.")
            st.stop()
            
        norm = DataNormalizer(raw, ticker)
        
        def fmt(v):
            if v is None: return "—"
            if not isinstance(v, (int, float)): return str(v)
            a = abs(v)
            if a >= 1e9: return f"{v/1e9:.2f}B"
            if a >= 1e6: return f"{v/1e6:.2f}M"
            return f"{v:,.0f}"

        def display_section(title, rows, hdrs):
            st.subheader(title)
            df = pd.DataFrame([{ "Item": r["label"], **{h: fmt(r.get(h)) for h in hdrs[1:]} } for r in rows]).set_index("Item")
            st.dataframe(df, use_container_width=True)

        p = view_type.lower()
        hdrs = norm.get_column_headers(p)
        
        display_section("📈 Income Statement", norm.get_income_statement(p), hdrs)
        display_section("💸 Cash Flow", norm.get_cash_flow(p), hdrs)
        display_section("⚖️ Balance Sheet", norm.get_balance_sheet(p), hdrs)
        display_section("💳 Debt Analysis", norm.get_debt_table(p), hdrs)
        st.success("Analysis Complete!")
