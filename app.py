import io, sys, os
import streamlit as st
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

st.set_page_config(page_title="Get Value", layout="wide")
st.title("📊 Get Value — Financial Viewer")

ticker = st.text_input("Enter Ticker (e.g. NVDA)", "NVDA").upper()
view_type = st.selectbox("Select View", ["Annual", "Quarterly"])

if st.button("Analyze", type="primary"):
    with st.spinner(f"Analyzing {ticker}..."):
        try:
            raw = GatewayAgent().fetch_all(ticker)
            norm = DataNormalizer(raw, ticker)
        except Exception as e:
            st.error(f"Error: {e}"); st.stop()
        
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

        # Excel Export with tabs
        import xlsxwriter
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        def add_sheet(name, rows, hdrs):
            ws = wb.add_worksheet(name)
            for c, h in enumerate(hdrs): ws.write(0, c, h)
            for r_idx, row in enumerate(rows, 1):
                ws.write(r_idx, 0, row["label"])
                for c_idx, h in enumerate(hdrs[1:], 1): ws.write(r_idx, c_idx, fmt(row.get(h)))
        
        add_sheet("Income Statement", norm.get_income_statement(p), hdrs)
        add_sheet("Cash Flow", norm.get_cash_flow(p), hdrs)
        add_sheet("Balance Sheet", norm.get_balance_sheet(p), hdrs)
        add_sheet("Debt", norm.get_debt_table(p), hdrs)
        wb.close()
        st.download_button("📥 Download Excel Report", buf.getvalue(), f"{ticker}_report.xlsx")