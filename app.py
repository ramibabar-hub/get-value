import streamlit as st
import pandas as pd
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer
from agents.profile_agent import ProfileAgent

st.set_page_config(
    page_title="getValue | Financial Analysis",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
    <style>
    /* ── Light theme — force white canvas globally ── */
    .stApp { background-color: #FFFFFF !important; color: #1c2b46 !important; }

    /* ── Hide sidebar and its toggle globally ── */
    section[data-testid="stSidebar"]  { display: none !important; }
    [data-testid="collapsedControl"]  { display: none !important; }

    /* ── Financial table section headers ── */
    .section-header {
        font-size: 1.1em; font-weight: bold; color: #ffffff;
        background-color: #1c2b46; padding: 6px 15px;
        border-radius: 4px; margin-top: 25px;
    }
    .stTable { font-size: 0.85em; }

    /* ── Cardinal Overview Table ── */
    .ov-wrap { max-width: 560px; }
    .ov-table { width: 100%; border: none; font-size: 0.875em; }
    .ov-table tr { border: none; }
    .ov-table td { padding: 8px; border: none; vertical-align: middle; line-height: 1.4; }
    .ov-table td.lbl {
        color: #1c2b46;
        text-transform: uppercase;
        font-size: 0.76em;
        letter-spacing: 0.07em;
        width: 44%;
        white-space: nowrap;
    }
    .ov-table td.val {
        font-family: 'Courier New', Courier, monospace;
        color: #000000;
        font-weight: 900;
        font-size: 1.1em;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Search helper — session-state cache that never stores empty results ────────
def _search(query: str) -> list:
    """
    Caches non-empty results in session_state for the lifetime of the session.
    Empty / error results are NOT cached so the next keystroke retries live.
    """
    key = f"_srch_{query.strip().lower()}"
    if key not in st.session_state:
        results = GatewayAgent().search_ticker(query.strip())
        if results:
            st.session_state[key] = results
        else:
            return []
    return st.session_state[key]

# ── Number formatter ──────────────────────────────────────────────────────────
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
              ("norm", None), ("norm_ticker", None), ("view_type", "Annual")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Shared: build search suggestions and return chosen ticker ─────────────────
def _search_widget(input_key: str, select_key: str, placeholder: str) -> str:
    """
    Renders text_input + optional selectbox. Returns the resolved ticker string.
    The selectbox key includes a query-derived suffix so Streamlit renders a
    fresh widget (index 0) whenever the search text changes — fixing the stale
    selection bug that prevented the dropdown from updating dynamically.
    """
    query = st.text_input(
        input_key,
        key=input_key,
        placeholder=placeholder,
        label_visibility="collapsed",
    )
    candidate = query.strip().upper()
    if len(query.strip()) >= 1:
        hits = _search(query.strip())
        if hits:
            labels = []
            for s in hits[:10]:
                exch = s.get('exchangeShortName', s.get('stockExchange', ''))
                # Replace bare ISO-2 country codes with their flag emoji
                exch_display = (
                    ProfileAgent.COUNTRY_FLAGS.get(exch.upper(), exch)
                    if len(exch) <= 2 else exch
                )
                labels.append(
                    f"{s.get('flag','🏳️')} {s.get('symbol','')} — "
                    f"{s.get('name','')} ({exch_display})"
                )
            # Dynamic key: changes with every new query string, forcing the
            # selectbox to reset to index 0 and show fresh suggestions.
            safe_q  = query.strip()[:24].replace(" ", "_")
            dyn_key = f"{select_key}__{safe_q}"
            chosen  = st.selectbox(
                select_key, labels, key=dyn_key, label_visibility="collapsed"
            )
            candidate = chosen.split(" — ")[0].split()[-1].strip()
    return candidate

# ── Shared: fetch all data and store in session state ─────────────────────────
def _load_ticker(ticker: str):
    gw = GatewayAgent()
    # Set active_ticker first so navigation is committed before data arrives
    st.session_state["active_ticker"] = ticker
    st.session_state["norm_ticker"]   = ticker
    st.session_state["overview_data"] = gw.fetch_overview(ticker)
    st.session_state["norm"]          = DataNormalizer(gw.fetch_all(ticker), ticker)

# ═════════════════════════════════════════════════════════════════════════════
# LANDING PAGE  (active_ticker is None)
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state["active_ticker"] is None:

    st.markdown("<div style='height:60px;'></div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='text-align:center;margin-bottom:10px;'>"
        "<span style='color:#007bff;font-weight:900;font-size:2em;"
        "letter-spacing:-0.02em;'>get</span>"
        "<span style='color:#1c2b46;font-weight:900;font-size:2em;"
        "letter-spacing:-0.02em;'>Value</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='text-align:center;font-size:2.4em;font-weight:700;"
        "margin-bottom:36px;'>Hi Rami, Let's get Value</div>",
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([2, 4, 2])
    with mid:
        candidate = _search_widget(
            "land_q", "land_sel",
            "🔍  Search company or ticker…",
        )
        if candidate:
            if st.button(f"Analyze  {candidate}  →",
                         use_container_width=True, type="primary"):
                with st.spinner(f"Loading {candidate}…"):
                    _load_ticker(candidate)
                st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# COMPANY PAGE  (active_ticker is set)
# ═════════════════════════════════════════════════════════════════════════════
else:
    ticker = st.session_state["active_ticker"]
    raw    = st.session_state["overview_data"] or {}
    norm   = st.session_state["norm"]

    # ── Brand logo + persistent search bar (same row) ────────────────────────
    logo_col, srch_col, btn_col = st.columns([2, 5, 1])
    with logo_col:
        st.markdown(
            "<div style='padding-top:6px;white-space:nowrap;'>"
            "<span style='color:#007bff;font-weight:900;font-size:1.35em;"
            "letter-spacing:-0.01em;'>get</span>"
            "<span style='color:#1c2b46;font-weight:900;font-size:1.35em;"
            "letter-spacing:-0.01em;'>Value</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    with srch_col:
        new_candidate = _search_widget(
            "top_q", "top_sel",
            "🔍  Search another company or ticker…",
        )
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        go = st.button("Analyze →", key="top_go",
                       use_container_width=True, type="primary")

    if go and new_candidate and new_candidate != ticker:
        with st.spinner(f"Loading {new_candidate}…"):
            _load_ticker(new_candidate)
        st.rerun()

    st.divider()

    # ── Dashboard Header: identity + price + 15 cardinal metrics ─────────────
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
    # If FMP returns a bare ISO-2 country code as the exchange name, replace
    # it with the emoji flag so no country code appears as plain text.
    _exch_display = (
        ProfileAgent.COUNTRY_FLAGS.get(exchange.strip().upper(), exchange)
        if len(exchange.strip()) <= 2
        else exchange
    )
    sub_line  = " &nbsp;·&nbsp; ".join(filter(None, [ticker, _exch_display, sector]))

    logo_html = (
        f"<img src='{logo_url}' width='54' height='54' "
        f"style='border-radius:10px;object-fit:contain;background:#eef1f6;padding:4px;' "
        f"onerror=\"this.style.display='none'\">"
        if logo_url
        else f"<span style='font-size:2.4em;line-height:1;'>{flag}</span>"
    )

    # Rows 0-2 (Ticker, Company Name, Price) are shown in the identity block;
    # rows 3-17 become the 15-cell horizontal metrics grid (5 cols × 3 rows).
    ov_rows = agent.get_rows()
    metric_cells = ""
    for r in ov_rows[3:]:
        val_color = r["color"] if r["color"] else "#0d1b2a"
        metric_cells += (
            f"<div style='min-width:0;'>"
            f"<div style='font-size:0.60em;text-transform:uppercase;letter-spacing:0.07em;"
            f"color:#4d6b88;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
            f"margin-bottom:2px;'>{r['label']}</div>"
            f"<div style='font-size:0.86em;font-weight:700;color:{val_color};white-space:nowrap;"
            f"overflow:hidden;text-overflow:ellipsis;'>{r['value']}</div>"
            f"</div>"
        )

    st.markdown(f"""
        <div style="display:flex;align-items:center;gap:18px;
                    padding:14px 0 18px;border-bottom:2px solid #1c2b46;
                    margin-bottom:6px;">
            <div style="flex-shrink:0;padding-top:2px;">{logo_html}</div>
            <div style="flex-shrink:0;min-width:170px;">
                <div style="font-size:1.22em;font-weight:700;white-space:nowrap;
                            overflow:hidden;text-overflow:ellipsis;">
                    {flag}&nbsp;{co_name}
                </div>
                <div style="color:#4d6b88;font-size:0.80em;margin-top:2px;">{sub_line}</div>
                <div style="margin-top:7px;line-height:1.15;">
                    <span style="font-size:1.45em;font-weight:800;color:#0d1b2a;">{price_fmt}</span>
                    &nbsp;
                    <span style="font-size:0.90em;font-weight:700;color:{chg_color};">{chg_fmt}</span>
                </div>
            </div>
            <div style="flex:1;display:grid;grid-template-columns:repeat(5,1fr);
                        gap:10px 12px;padding-left:18px;
                        border-left:1px solid #d0d8e8;">
                {metric_cells}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_ov, tab_fin, tab_ins = st.tabs(["📊 Overview", "📋 Financials", "💡 Insights"])

    # ── Tab 1: Overview — description only (metrics now live in the header) ──
    with tab_ov:
        description = raw.get("description", "")
        if description:
            st.markdown(
                f"<p style='color:#4d6b88;font-size:0.92em;line-height:1.75;"
                f"max-width:900px;margin-top:8px;'>{description}</p>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("No company description available.")

    # ── Tab 2: Financials ─────────────────────────────────────────────────────
    with tab_fin:
        # Period selector lives here; key binds it directly to session state
        st.radio(
            "Period:",
            ["Annual", "Quarterly"],
            key="view_type",
            horizontal=True,
        )
        if norm:
            p           = st.session_state["view_type"].lower()
            hdrs        = norm.get_column_headers(p)
            period_cols = hdrs[1:]
            fin_col_cfg = {col: st.column_config.TextColumn(col, width=120)
                           for col in period_cols}
            for title, method in [
                ("Income Statement", norm.get_income_statement),
                ("Cashflow",         norm.get_cash_flow),
                ("Balance Sheet",    norm.get_balance_sheet),
                ("Debt",             norm.get_debt_table),
            ]:
                st.markdown(f"<div class='section-header'>{title}</div>",
                            unsafe_allow_html=True)
                df = pd.DataFrame([
                    {"Item": rec["label"],
                     **{h: fmt(rec.get(h)) for h in period_cols}}
                    for rec in method(p)
                ])
                st.dataframe(df.set_index("Item"),
                             use_container_width=True, column_config=fin_col_cfg)
        else:
            st.info("Financial data is unavailable for this ticker.")

    # ── Tab 3: Insights ───────────────────────────────────────────────────────
    with tab_ins:
        if norm:
            # Reads the period value set in the Financials tab (or "Annual" default)
            p = st.session_state.get("view_type", "Annual").lower()
            for title, method, cols, is_pct in [
                ("Growth (CAGR)",       norm.get_insights_cagr,
                 ["3yr", "5yr", "10yr"], True),
                ("Valuation Multiples", norm.get_insights_valuation,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
                ("Profitability",       norm.get_insights_profitability,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
                ("Returns Analysis",    norm.get_insights_returns,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
                ("Liquidity",           norm.get_insights_liquidity,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
                ("Dividends",           norm.get_insights_dividends,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
                ("Efficiency",          norm.get_insights_efficiency,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
            ]:
                st.markdown(f"<div class='section-header'>{title}</div>",
                            unsafe_allow_html=True)
                df = pd.DataFrame(method())
                for c in cols:
                    df[c] = df[c].apply(lambda x, p=is_pct: fmt(x, p))
                ins_col_cfg = {col: st.column_config.TextColumn(col, width=120)
                               for col in cols}
                st.dataframe(df.set_index(df.columns[0]),
                             use_container_width=True, column_config=ins_col_cfg)
        else:
            st.info("Insights data is unavailable for this ticker.")
