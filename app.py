import streamlit as st
import pandas as pd
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer
from agents.profile_agent import ProfileAgent

st.set_page_config(page_title="getValue | Financial Analysis", layout="wide")

st.markdown("""
    <style>
    /* ── Section headers ── */
    .section-header {
        font-size: 1.1em; font-weight: bold; color: #ffffff;
        background-color: #1c2b46; padding: 6px 15px;
        border-radius: 4px; margin-top: 25px;
    }
    .stTable { font-size: 0.85em; }

    /* ── Company header ── */
    .company-header {
        padding: 10px 0 8px;
        border-bottom: 1px solid #1c2b46;
        margin-bottom: 14px;
    }

    /* ── Metric cards ── */
    .metric-card {
        background: #1c2b46;
        border-radius: 8px;
        padding: 11px 14px;
        height: 100%;
    }
    .metric-label {
        font-size: 0.70em;
        color: #8899bb;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 5px;
    }
    .metric-value      { font-size: 1.05em; font-weight: 600; color: #e8edf5; }
    .metric-value-up   { font-size: 1.05em; font-weight: 600; color: #22c55e; }
    .metric-value-down { font-size: 1.05em; font-weight: 600; color: #ef4444; }

    /* ── Group labels ── */
    .group-label {
        font-size: 0.72em;
        color: #5577aa;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin: 14px 0 4px;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Cached helpers (minimize API calls) ──────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _search(query: str) -> list:
    return GatewayAgent().search_ticker(query)

@st.cache_data(ttl=60, show_spinner=False)
def _profile(ticker: str) -> dict:
    return GatewayAgent().fetch_profile(ticker)

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

# Autocomplete suggestions
ticker = search_query.strip().upper()
if len(search_query.strip()) >= 2:
    suggestions = _search(search_query.strip())
    if suggestions:
        labels = [
            f"{s.get('symbol','')} — {s.get('name','')} ({s.get('exchangeShortName', s.get('stockExchange',''))})"
            for s in suggestions[:10]
        ]
        chosen = st.selectbox(
            "Select from results:",
            labels,
            label_visibility="collapsed",
        )
        ticker = chosen.split(" — ")[0].strip()

# ── Profile Dashboard (auto-updates on ticker change) ────────────────────────
def _card(label: str, value: str, css_class: str = "metric-value") -> str:
    return (
        f"<div class='metric-card'>"
        f"<div class='metric-label'>{label}</div>"
        f"<div class='{css_class}'>{value}</div>"
        f"</div>"
    )

if ticker:
    raw_profile = _profile(ticker)
    if raw_profile:
        m = ProfileAgent(raw_profile).get_metrics()
        price_cls = "metric-value-up" if m["change_positive"] else "metric-value-down"

        # Company name bar
        st.markdown(
            f"<div class='company-header'>"
            f"<span style='font-size:1.55em;font-weight:700;'>"
            f"{m['flag']} {m['company_name']}"
            f"</span>"
            f"&nbsp;&nbsp;"
            f"<span style='color:#8899bb;font-size:0.95em;'>"
            f"{m['ticker']} · {m['exchange']}"
            f"</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── Valuation row ──
        st.markdown("<div class='group-label'>Valuation</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(_card("Price",      m["price"],   price_cls),  unsafe_allow_html=True)
        with c2: st.markdown(_card("Change %",   m["change_pct"], price_cls), unsafe_allow_html=True)
        with c3: st.markdown(_card("Market Cap", m["mkt_cap"]),              unsafe_allow_html=True)
        with c4: st.markdown(_card("P / E",      m["pe"]),                   unsafe_allow_html=True)

        # ── Basic Info row ──
        st.markdown("<div class='group-label'>Basic Info</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(_card("Sector",        m["sector"]),         unsafe_allow_html=True)
        with c2: st.markdown(_card("Industry",      m["industry"]),       unsafe_allow_html=True)
        with c3: st.markdown(_card("Next Earnings", m["next_earnings"]),  unsafe_allow_html=True)
        with c4: st.markdown(_card("Employees",     m["employees"]),      unsafe_allow_html=True)

        # ── Ownership + Risk/Short row ──
        st.markdown("<div class='group-label'>Ownership &amp; Risk</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(_card("Insider Own.",  m["insider_own"]),   unsafe_allow_html=True)
        with c2: st.markdown(_card("Inst. Own.",    m["inst_own"]),      unsafe_allow_html=True)
        with c3: st.markdown(_card("Beta",          m["beta"]),          unsafe_allow_html=True)
        with c4: st.markdown(_card("Short Float",   m["short_float"]),   unsafe_allow_html=True)

        st.divider()

# ── Run Analysis (financial statements) ──────────────────────────────────────
if run_button and ticker:
    st.cache_data.clear()
    with st.spinner(f"Fetching financials for {ticker}…"):
        raw = GatewayAgent().fetch_all(ticker)
        st.session_state["norm"] = DataNormalizer(raw, ticker)
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
            ("Growth (CAGR)",        norm.get_insights_cagr,          ["3yr", "5yr", "10yr"],             True),
            ("Valuation Multiples",  norm.get_insights_valuation,     ["TTM", "Avg. 5yr", "Avg. 10yr"],   False),
            ("Profitability",        norm.get_insights_profitability,  ["TTM", "Avg. 5yr", "Avg. 10yr"],   True),
            ("Returns Analysis",     norm.get_insights_returns,        ["TTM", "Avg. 5yr", "Avg. 10yr"],   True),
            ("Liquidity",            norm.get_insights_liquidity,      ["TTM", "Avg. 5yr", "Avg. 10yr"],   False),
            ("Dividends",            norm.get_insights_dividends,      ["TTM", "Avg. 5yr", "Avg. 10yr"],   True),
            ("Efficiency",           norm.get_insights_efficiency,     ["TTM", "Avg. 5yr", "Avg. 10yr"],   False),
        ]:
            st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
            df = pd.DataFrame(method())
            for c in cols:
                df[c] = df[c].apply(lambda x: fmt(x, is_pct))
            ins_col_cfg = {col: st.column_config.TextColumn(col, width=120) for col in cols}
            st.dataframe(df.set_index(df.columns[0]), use_container_width=True, column_config=ins_col_cfg)
