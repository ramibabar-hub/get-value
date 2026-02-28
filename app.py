import streamlit as st
import pandas as pd
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer
from agents.profile_agent import ProfileAgent

st.set_page_config(page_title="getValue | Financial Analysis", layout="wide")

st.markdown("""
    <style>
    /* ── Financial table section headers ── */
    .section-header {
        font-size: 1.1em; font-weight: bold; color: #ffffff;
        background-color: #1c2b46; padding: 6px 15px;
        border-radius: 4px; margin-top: 25px;
    }
    .stTable { font-size: 0.85em; }

    /* ── Cardinal Overview Table ── */
    .ov-wrap { max-width: 560px; }
    .ov-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.875em;
    }
    .ov-table tr { border-bottom: 1px solid #1a2535; }
    .ov-table tr:last-child { border-bottom: none; }
    .ov-table td { padding: 5px 10px; vertical-align: middle; line-height: 1.4; }
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
    </style>
    """, unsafe_allow_html=True)

# ── Cached search helper ──────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _search(query: str) -> list:
    return GatewayAgent().search_ticker(query)

# ── Number formatter (financial tables) ──────────────────────────────────────
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

# ── Session-state bootstrap ───────────────────────────────────────────────────
for k, v in [("active_ticker", None), ("overview_data", None),
              ("norm", None), ("norm_ticker", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ═════════════════════════════════════════════════════════════════════════════
# LANDING PAGE  (active_ticker is None)
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state["active_ticker"] is None:

    # Hide sidebar on the landing page for a clean full-screen look
    st.markdown("""
        <style>
        section[data-testid="stSidebar"]  { display: none !important; }
        [data-testid="collapsedControl"]  { display: none !important; }
        </style>""", unsafe_allow_html=True)

    # Vertical breathing room
    st.markdown("<div style='height:80px;'></div>", unsafe_allow_html=True)

    # Brand + greeting
    st.markdown("""
        <div style='text-align:center;margin-bottom:6px;'>
            <span style='color:#007bff;font-size:3em;font-weight:900;
                         letter-spacing:-0.02em;'>
                get<span style='color:#ffffff;'>Value</span>
            </span>
        </div>
        <div style='text-align:center;color:#8899bb;font-size:1.1em;margin-bottom:38px;'>
            Hi Rami, Let's get Value
        </div>
        """, unsafe_allow_html=True)

    # Centered search column
    _, mid, _ = st.columns([2, 4, 2])
    with mid:
        search_query = st.text_input(
            "search",
            value="",
            placeholder="🔍  Search company or ticker…",
            label_visibility="collapsed",
        )

        ticker_candidate = search_query.strip().upper()

        if len(search_query.strip()) >= 2:
            suggestions = _search(search_query.strip())
            if suggestions:
                labels = [
                    f"{s.get('flag','🏳️')} {s.get('symbol','')} — "
                    f"{s.get('name','')} "
                    f"({s.get('exchangeShortName', s.get('stockExchange',''))})"
                    for s in suggestions[:10]
                ]
                chosen = st.selectbox("results", labels, label_visibility="collapsed")
                ticker_candidate = chosen.split(" — ")[0].split()[-1].strip()

        if ticker_candidate:
            if st.button(
                f"Analyze  {ticker_candidate}  →",
                use_container_width=True,
                type="primary",
            ):
                with st.spinner(f"Loading {ticker_candidate}…"):
                    gw          = GatewayAgent()
                    overview    = gw.fetch_overview(ticker_candidate)
                    raw_fin     = gw.fetch_all(ticker_candidate)
                    st.session_state["active_ticker"] = ticker_candidate
                    st.session_state["overview_data"] = overview
                    st.session_state["norm"]          = DataNormalizer(raw_fin, ticker_candidate)
                    st.session_state["norm_ticker"]   = ticker_candidate
                st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# COMPANY PAGE  (active_ticker is set)
# ═════════════════════════════════════════════════════════════════════════════
else:
    ticker = st.session_state["active_ticker"]
    raw    = st.session_state["overview_data"] or {}
    norm   = st.session_state["norm"]

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("<h1 style='color:#007bff;'>getValue</h1>", unsafe_allow_html=True)
        view_type = st.radio("Period:", ["Annual", "Quarterly"])
        st.divider()
        if st.button("← Search Another Stock", use_container_width=True):
            for k in ["active_ticker", "overview_data", "norm", "norm_ticker"]:
                st.session_state[k] = None
            st.rerun()

    # ── Company Header ────────────────────────────────────────────────────────
    agent    = ProfileAgent(raw)
    flag     = agent.get_flag()
    logo_url = raw.get("image", "")
    co_name  = raw.get("companyName", ticker)
    exchange = raw.get("exchangeShortName") or raw.get("exchange", "")
    sector   = raw.get("sector") or ""

    try:
        price_val = float(raw.get("price") or 0)
        chg_raw   = raw.get("changesPercentage", 0) or 0
        chg_pct   = float(str(chg_raw).replace("%", "").strip())
    except (TypeError, ValueError):
        price_val, chg_pct = 0.0, 0.0

    price_fmt = f"${price_val:,.2f}" if price_val else "N/A"
    chg_sign  = "+" if chg_pct >= 0 else ""
    chg_fmt   = f"{chg_sign}{chg_pct:.2f}%"
    chg_color = "#22c55e" if chg_pct >= 0 else "#ef4444"
    sub_line  = " &nbsp;·&nbsp; ".join(filter(None, [ticker, exchange, sector]))

    logo_html = (
        f"<img src='{logo_url}' width='54' height='54' "
        f"style='border-radius:10px;object-fit:contain;background:#0d1b2a;padding:4px;' "
        f"onerror=\"this.style.display='none'\">"
        if logo_url
        else f"<span style='font-size:2.4em;line-height:1;'>{flag}</span>"
    )

    st.markdown(f"""
        <div style="display:flex;align-items:center;gap:20px;
                    padding:14px 0 16px;border-bottom:2px solid #1c2b46;
                    margin-bottom:6px;">
            <div style="flex-shrink:0;">{logo_html}</div>
            <div style="flex:1;min-width:0;">
                <div style="font-size:1.4em;font-weight:700;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                    {flag}&nbsp;&nbsp;{co_name}
                </div>
                <div style="color:#8899bb;font-size:0.88em;margin-top:3px;">
                    {sub_line}
                </div>
            </div>
            <div style="text-align:right;white-space:nowrap;">
                <div style="font-size:1.65em;font-weight:700;">{price_fmt}</div>
                <div style="font-size:1.1em;font-weight:600;color:{chg_color};">
                    {chg_fmt}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_ov, tab_fin, tab_ins = st.tabs(["📊 Overview", "📋 Financials", "💡 Insights"])

    # ── Tab 1: Overview ───────────────────────────────────────────────────────
    with tab_ov:
        ov_rows = agent.get_rows()
        table_html = ""
        for r in ov_rows:
            val_html = (
                f"<span style='color:{r['color']};'>{r['value']}</span>"
                if r["color"] else r["value"]
            )
            table_html += (
                f"<tr>"
                f"<td class='lbl'>{r['label']}</td>"
                f"<td class='val'>{val_html}</td>"
                f"</tr>"
            )
        col_tbl, _ = st.columns([5, 4])
        with col_tbl:
            st.markdown(
                f"<div class='ov-wrap'>"
                f"<table class='ov-table'><tbody>{table_html}</tbody></table>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Tab 2: Financials ─────────────────────────────────────────────────────
    with tab_fin:
        if norm:
            p           = view_type.lower()
            hdrs        = norm.get_column_headers(p)
            period_cols = hdrs[1:]
            fin_col_cfg = {col: st.column_config.TextColumn(col, width=120) for col in period_cols}
            for title, method in [
                ("Income Statement", norm.get_income_statement),
                ("Cashflow",         norm.get_cash_flow),
                ("Balance Sheet",    norm.get_balance_sheet),
                ("Debt",             norm.get_debt_table),
            ]:
                st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
                df = pd.DataFrame([
                    {"Item": rec["label"], **{h: fmt(rec.get(h)) for h in period_cols}}
                    for rec in method(p)
                ])
                st.dataframe(df.set_index("Item"), use_container_width=True, column_config=fin_col_cfg)
        else:
            st.info("Financial data is unavailable for this ticker.")

    # ── Tab 3: Insights ───────────────────────────────────────────────────────
    with tab_ins:
        if norm:
            p = view_type.lower()
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
                    df[c] = df[c].apply(lambda x, p=is_pct: fmt(x, p))
                ins_col_cfg = {col: st.column_config.TextColumn(col, width=120) for col in cols}
                st.dataframe(df.set_index(df.columns[0]), use_container_width=True, column_config=ins_col_cfg)
        else:
            st.info("Insights data is unavailable for this ticker.")
