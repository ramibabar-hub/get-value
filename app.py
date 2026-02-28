import streamlit as st
import pandas as pd
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer
from agents.profile_agent import ProfileAgent

st.set_page_config(page_title="getValue | Financial Analysis", layout="wide")

st.markdown("""
    <style>
    /* ── Section headers (financial tables) ── */
    .section-header {
        font-size: 1.1em; font-weight: bold; color: #ffffff;
        background-color: #1c2b46; padding: 6px 15px;
        border-radius: 4px; margin-top: 25px;
    }
    .stTable { font-size: 0.85em; }

    /* ── Terminal company header ── */
    .term-header {
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.82em;
        color: #5a7a99;
        text-transform: uppercase;
        letter-spacing: 0.10em;
        padding: 6px 0 10px;
        border-bottom: 1px solid #1c2b46;
        margin-bottom: 2px;
    }

    /* ── Cardinal Overview Table ── */
    .ov-wrap { max-width: 560px; }
    .ov-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.875em;
    }
    .ov-table tr { border-bottom: 1px solid #1a2535; }
    .ov-table tr:last-child { border-bottom: none; }
    .ov-table td {
        padding: 5px 10px;
        vertical-align: middle;
        line-height: 1.4;
    }
    .ov-table td.lbl {
        color: #4d6b88;
        text-transform: uppercase;
        font-size: 0.76em;
        letter-spacing: 0.07em;
        width: 44%;
        white-space: nowrap;
    }
    .ov-table td.val {
        font-family: 'Courier New', Courier, monospace;
        color: #c8d8e8;
    }
    .ov-up   { color: #22c55e !important; }
    .ov-down { color: #ef4444 !important; }
    </style>
    """, unsafe_allow_html=True)

# ── Cached helpers ────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _search(query: str) -> list:
    return GatewayAgent().search_ticker(query)

@st.cache_data(ttl=60, show_spinner=False)
def _overview(ticker: str) -> dict:
    return GatewayAgent().fetch_overview(ticker)

# ── Session-state bootstrap ───────────────────────────────────────────────────
for key, default in [("norm", None), ("norm_ticker", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h1 style='color:#007bff;'>getValue</h1>", unsafe_allow_html=True)
    view_type = st.radio("Period:", ["Annual", "Quarterly"])
    st.divider()
    run_button = st.button("▶  Run Analysis", use_container_width=True, type="primary")

# ── Greeting + Search ─────────────────────────────────────────────────────────
st.write("### Hi Rami, Let's get Value")

search_query = st.text_input(
    "🔍  Search company or ticker:",
    value="NVDA",
    placeholder="e.g. NVDA, Apple, Microsoft…",
    label_visibility="visible",
)

# Autocomplete dropdown (appears as user types)
ticker = search_query.strip().upper()
if len(search_query.strip()) >= 2:
    suggestions = _search(search_query.strip())
    if suggestions:
        labels = [
            f"{s.get('flag', '🏳️')} {s.get('symbol', '')} — "
            f"{s.get('name', '')} ({s.get('exchangeShortName', s.get('stockExchange', ''))})"
            for s in suggestions[:10]
        ]
        chosen = st.selectbox("Select from results:", labels, label_visibility="collapsed")
        # Label format: "🇺🇸 NVDA — NVIDIA Corporation (NASDAQ)"
        # Ticker is the last token before " — "
        ticker = chosen.split(" — ")[0].split()[-1].strip()

# ── Cardinal Overview Table (auto-loads on ticker change) ────────────────────
if ticker:
    raw = _overview(ticker)
    if raw:
        agent = ProfileAgent(raw)
        rows  = agent.get_rows()
        flag  = agent.get_flag()
        name  = raw.get("companyName", ticker)
        exch  = raw.get("exchangeShortName") or raw.get("exchange", "")

        # Compact terminal header line
        st.markdown(
            f"<div class='term-header'>"
            f"{flag}&nbsp;&nbsp;{name.upper()}&nbsp;&nbsp;·&nbsp;&nbsp;"
            f"{ticker}&nbsp;&nbsp;·&nbsp;&nbsp;{exch}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Build the 18-row HTML table
        table_rows_html = ""
        for r in rows:
            if r["color"]:
                val_html = f"<span style='color:{r['color']};'>{r['value']}</span>"
            else:
                val_html = r["value"]
            table_rows_html += (
                f"<tr>"
                f"<td class='lbl'>{r['label']}</td>"
                f"<td class='val'>{val_html}</td>"
                f"</tr>"
            )

        col_table, _ = st.columns([5, 4])
        with col_table:
            st.markdown(
                f"<div class='ov-wrap'>"
                f"<table class='ov-table'><tbody>{table_rows_html}</tbody></table>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.divider()

# ── Run Analysis (financial statements) ──────────────────────────────────────
if run_button and ticker:
    st.cache_data.clear()
    with st.spinner(f"Fetching financials for {ticker}…"):
        raw_fin = GatewayAgent().fetch_all(ticker)
        st.session_state["norm"] = DataNormalizer(raw_fin, ticker)
        st.session_state["norm_ticker"] = ticker

# Show financials only when they belong to the current ticker
if st.session_state["norm"] and st.session_state["norm_ticker"] == ticker:
    norm = st.session_state["norm"]

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
    period_cols = hdrs[1:]
    fin_col_cfg = {col: st.column_config.TextColumn(col, width=120) for col in period_cols}

    tab_fin, tab_ins = st.tabs(["📋 Financials", "💡 Insights"])

    with tab_fin:
        for title, method in [
            ("Income Statement", norm.get_income_statement),
            ("Cashflow",         norm.get_cash_flow),
            ("Balance Sheet",    norm.get_balance_sheet),
            ("Debt",             norm.get_debt_table),
        ]:
            st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
            data = method(p)
            df = pd.DataFrame([
                {"Item": r["label"], **{h: fmt(r.get(h)) for h in period_cols}}
                for r in data
            ])
            st.dataframe(df.set_index("Item"), use_container_width=True, column_config=fin_col_cfg)

    with tab_ins:
        for title, method, cols, is_pct in [
            ("Growth (CAGR)",       norm.get_insights_cagr,         ["3yr", "5yr", "10yr"],             True),
            ("Valuation Multiples", norm.get_insights_valuation,    ["TTM", "Avg. 5yr", "Avg. 10yr"],   False),
            ("Profitability",       norm.get_insights_profitability, ["TTM", "Avg. 5yr", "Avg. 10yr"],   True),
            ("Returns Analysis",    norm.get_insights_returns,       ["TTM", "Avg. 5yr", "Avg. 10yr"],   True),
            ("Liquidity",           norm.get_insights_liquidity,     ["TTM", "Avg. 5yr", "Avg. 10yr"],   False),
            ("Dividends",           norm.get_insights_dividends,     ["TTM", "Avg. 5yr", "Avg. 10yr"],   True),
            ("Efficiency",          norm.get_insights_efficiency,    ["TTM", "Avg. 5yr", "Avg. 10yr"],   False),
        ]:
            st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
            df = pd.DataFrame(method())
            for c in cols:
                df[c] = df[c].apply(lambda x: fmt(x, is_pct))
            ins_col_cfg = {col: st.column_config.TextColumn(col, width=120) for col in cols}
            st.dataframe(df.set_index(df.columns[0]), use_container_width=True, column_config=ins_col_cfg)
