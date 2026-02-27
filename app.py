import io
import sys
import os
import streamlit as st

# Ensuring path visibility
sys.path.insert(0, os.path.dirname(__file__))
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer

st.set_page_config(page_title="Get Value", layout="wide")
st.title("📊 Get Value — Financial Statement Viewer")

# --- Inputs ---
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    ticker = st.text_input("Ticker", placeholder="e.g. NVDA, AAPL").strip().upper()
with col2:
    view = st.selectbox("View", ["Both", "Annual", "Quarterly"])
with col3:
    st.write(""); st.write("")
    run = st.button("Fetch", use_container_width=True, type="primary")

if not run or not ticker:
    st.stop()

# --- Execution ---
with st.spinner(f"Fetching {ticker}..."):
    try:
        raw_data = GatewayAgent().fetch_all(ticker)
        normalizer = DataNormalizer(raw_data, ticker)
    except Exception as e:
        st.error(str(e)); st.stop()

def fmt(val):
    if val is None: return "—"
    if not isinstance(val, float): return str(val)
    from math import isnan
    if isnan(val): return "—"
    a = abs(val)
    if a >= 1e12: return f"{val/1e12:.2f}T"
    if a >= 1e9:  return f"{val/1e9:.2f}B"
    if a >= 1e6:  return f"{val/1e6:.2f}M"
    return f"{val:,.0f}"

def show(title, rows, headers):
    import pandas as pd
    st.subheader(title)
    recs = [{"Item": r.get("label","")} | {h: fmt(r.get(h)) for h in headers[1:]} for r in rows]
    st.dataframe(pd.DataFrame(recs).set_index("Item"), use_container_width=True)

annual_rows = quarterly_rows = annual_hdrs = quarterly_hdrs = None
if view in ("Both", "Annual"):
    annual_hdrs = normalizer.get_column_headers("annual")
    annual_rows = normalizer.build_annual_table()
    show(f"Annual (5Y + TTM)", annual_rows, annual_hdrs)

if view in ("Both", "Quarterly"):
    quarterly_hdrs = normalizer.get_column_headers("quarterly")
    quarterly_rows = normalizer.build_quarterly_table()
    show(f"Quarterly (5Q + TTM)", quarterly_rows, quarterly_hdrs)

# --- Excel ---
st.divider()
if st.button("Export to Excel"):
    import xlsxwriter
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1a1a2e", "font_color": "#ffffff", "border": 1})
    cel = wb.add_format({"border": 1})
    def ws(name, rows, hdrs):
        s = wb.add_worksheet(name)
        s.set_column(0,0,30)
        for c, h in enumerate(hdrs): s.write(0, c, h, hdr)
        for r, row in enumerate(rows, 1):
            s.write(r, 0, row.get("label",""), cel)
            for c, h in enumerate(hdrs[1:], 1): s.write(r, c, fmt(row.get(h)), cel)
    if annual_rows: ws("Annual", annual_rows, annual_hdrs)
    if quarterly_rows: ws("Quarterly", quarterly_rows, quarterly_hdrs)
    wb.close(); buf.seek(0)
    st.download_button("Download Excel", buf, f"{ticker}_report.xlsx")