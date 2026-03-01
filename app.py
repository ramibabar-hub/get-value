import streamlit as st
import pandas as pd
from agents.gateway_agent import GatewayAgent
from agents.core_agent import DataNormalizer
from agents.profile_agent import ProfileAgent
from agents.insights_agent import InsightsAgent
from financials_tab import render_financials_tab
from cf_irr_tab import render_cf_irr_tab

def _damodaran_spread(coverage: float) -> float:
    if coverage > 8.5:  return 0.0067
    if coverage > 6.5:  return 0.0082
    if coverage > 5.5:  return 0.0103
    if coverage > 4.25: return 0.0114
    if coverage > 3.0:  return 0.0129
    if coverage > 2.5:  return 0.0159
    if coverage > 2.25: return 0.0193
    if coverage > 2.0:  return 0.0223
    if coverage > 1.75: return 0.0330
    if coverage > 1.5:  return 0.0405
    if coverage > 1.25: return 0.0486
    if coverage > 0.8:  return 0.0632
    if coverage > 0.65: return 0.0801
    return 0.1000


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
    q = query.strip()
    if not q:
        return []
    return GatewayAgent().search_ticker(q)

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
for k, v in [
    # ── Core app keys ──────────────────────────────────────────────────────────
    ("active_ticker",            None),
    ("overview_data",            None),
    ("norm",                     None),
    ("norm_ticker",              None),
    ("view_type",                "Annual"),
    ("fin_scale",                "MM"),
    ("treasury_rate",            0.042),
    # ── CF + IRR tab — WACC "Verify Source" panel ─────────────────────────────
    ("cfirr_show_wacc_detail",   False),
    ("cfirr_wacc_override",      False),
    ("cfirr_wacc_rf_rate",       0.042),
    ("cfirr_wacc_beta",          1.0),
    ("cfirr_wacc_erp",           0.046),
    # ── CF + IRR tab — YoY growth-rate editors (populated per-ticker) ─────────
    ("cfirr_ebitda_growth_yoy",  []),
    ("cfirr_fcf_growth_yoy",     []),
    # ── CF + IRR tab — global growth-rate overrides ───────────────────────────
    ("cfirr_ebitda_global_growth", None),   # None → use historical CAGR
    ("cfirr_fcf_global_growth",    None),   # None → use historical CAGR
    # ── CF + IRR tab — exit / MoS inputs ─────────────────────────────────────
    ("cfirr_ebitda_exit",        15.0),
    ("cfirr_fcf_exit_yield",     4.0),
    ("cfirr_mos",                25.0),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Shared: session-state default helper ─────────────────────────────────────
def _ss_default(key, val):
    if key not in st.session_state:
        st.session_state[key] = val

# ── Shared: build search suggestions and return chosen ticker ─────────────────
def _search_widget(input_key: str, select_key: str, placeholder: str) -> str:
    """
    Renders text_input + optional selectbox. Returns the resolved ticker string.
    on_change fires when the user stops typing (Enter / focus-loss) and stores
    search results in session_state so the dropdown appears on the next render.
    Reading the query directly from st.session_state[input_key] (the widget
    value) avoids the stale-key bug where a separate query_key stayed "".
    """
    results_key = f"_hits_{input_key}"

    def _on_change():
        q = st.session_state.get(input_key, "").strip()
        st.session_state[results_key] = _search(q) if q else []

    _ss_default(input_key, "")
    _ss_default(results_key, [])

    st.text_input(
        input_key,
        key=input_key,
        placeholder=placeholder,
        label_visibility="collapsed",
        on_change=_on_change,
    )

    query = st.session_state.get(input_key, "").strip()
    hits  = st.session_state.get(results_key, [])
    candidate = query.upper()

    if query:
        if hits:
            labels = []
            for s in hits[:15]:
                exch = s.get('exchangeShortName', s.get('stockExchange', ''))
                exch_display = (
                    ProfileAgent.COUNTRY_FLAGS.get(exch.upper(), exch)
                    if len(exch) <= 2 else exch
                )
                labels.append(
                    f"{s.get('flag','🏳️')} {s.get('symbol','')} — "
                    f"{s.get('name','')} ({exch_display})"
                )
            safe_q  = query[:24].replace(" ", "_")
            dyn_key = f"{select_key}__{safe_q}"
            chosen  = st.selectbox(
                select_key, labels, key=dyn_key, label_visibility="collapsed"
            )
            candidate = chosen.split(" — ")[0].split()[-1].strip()
        else:
            st.caption(
                "⚠️ לא נמצאו תוצאות. "
                "לבורסות מחוץ לארה\"ב הוסף suffix: "
                "**NICE.TA** (ישראל) · **BMW.DE** (גרמניה) · **VOD.L** (לונדון)"
            )
    return candidate

# ── Shared: fetch all data and store in session state ─────────────────────────
def _load_ticker(ticker: str):
    gw = GatewayAgent()
    # Set active_ticker first so navigation is committed before data arrives
    st.session_state["active_ticker"] = ticker
    st.session_state["norm_ticker"]   = ticker
    st.session_state["overview_data"] = gw.fetch_overview(ticker)
    st.session_state["norm"]          = DataNormalizer(gw.fetch_all(ticker), ticker)
    st.session_state["treasury_rate"] = gw.fetch_treasury_rate()

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
    tab_ov, tab_fin, tab_ins, tab_val = st.tabs(
        ["📊 Overview", "📋 Financials", "💡 Insights", "💰 Valuations"]
    )

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
        render_financials_tab(norm, raw)

    # ── Tab 3: Insights ───────────────────────────────────────────────────────
    with tab_ins:
        if norm:
            ins = InsightsAgent(norm.raw_data, raw)

            def fmt_ins(v, is_pct=False):
                """Like fmt() but passes 'N/M' strings through and guards complex."""
                if isinstance(v, str):
                    return v
                if isinstance(v, complex):   # guard against stray complex numbers
                    return "N/M"
                return fmt(v, is_pct)

            for title, method, cols, is_pct in [
                ("Growth (CAGR)",       ins.get_insights_cagr,
                 ["3yr", "5yr", "10yr"], True),
                ("Valuation Multiples", ins.get_insights_valuation,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
                ("Profitability",       ins.get_insights_profitability,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
                ("Returns Analysis",    ins.get_insights_returns,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
                ("Liquidity",           ins.get_insights_liquidity,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
                ("Dividends",           ins.get_insights_dividends,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], True),
                ("Efficiency",          ins.get_insights_efficiency,
                 ["TTM", "Avg. 5yr", "Avg. 10yr"], False),
            ]:
                st.markdown(f"<div class='section-header'>{title}</div>",
                            unsafe_allow_html=True)
                df = pd.DataFrame(method())
                for c in cols:
                    df[c] = df[c].apply(lambda x, p=is_pct: fmt_ins(x, p))
                ins_col_cfg = {col: st.column_config.TextColumn(col, width=120)
                               for col in cols}
                st.dataframe(df.set_index(df.columns[0]),
                             use_container_width=True, column_config=ins_col_cfg)
            # ── WACC ──────────────────────────────────────────────────────────
            w = ins.get_wacc_components()

            st.markdown("<div class='section-header'>WACC</div>", unsafe_allow_html=True)

            # Sensitivity Analysis — lets the user override live inputs
            with st.expander("⚙️ Sensitivity Analysis — Adjust Inputs"):
                sa_col1, sa_col2, sa_col3 = st.columns(3)
                with sa_col1:
                    rf_rate = st.number_input(
                        "Risk-Free Rate (10y Treasury)",
                        min_value=0.0, max_value=0.20,
                        value=float(st.session_state.get("treasury_rate", 0.042)),
                        step=0.001, format="%.3f",
                        key="wacc_rf_rate",
                    )
                with sa_col2:
                    beta_adj = st.number_input(
                        "Beta",
                        min_value=0.0, max_value=5.0,
                        value=float(w["beta"]),
                        step=0.01, format="%.2f",
                        key="wacc_beta",
                    )
                with sa_col3:
                    erp_adj = st.number_input(
                        "Equity Risk Premium (ERP)",
                        min_value=0.0, max_value=0.20,
                        value=0.046,
                        step=0.001, format="%.3f",
                        key="wacc_erp",
                    )

            spread = _damodaran_spread(w["int_coverage"])
            cod    = (rf_rate + spread) * (1 - w["tax_rate"])
            coe    = rf_rate + (beta_adj * erp_adj)
            tc     = w["equity_val"] + w["debt_val"]
            wd     = w["debt_val"]   / tc if tc else 0.0
            we     = w["equity_val"] / tc if tc else 0.0
            wacc   = wd * cod + we * coe

            col_d, col_e = st.columns(2)

            with col_d:
                st.caption("Cost of Debt")
                cod_df = pd.DataFrame([
                    ["Interest Expense",         fmt(w["int_expense"])],
                    ["Interest Coverage",        f"{w['int_coverage']:.2f}x"],
                    ["Credit Spread",            f"{spread:.2%}"],
                    ["Risk-Free Rate (10y)",     f"{rf_rate:.2%}"],
                    ["Corporate Tax Rate",       f"{w['tax_rate']:.2%}"],
                    ["Cost of Debt (after-tax)", f"{cod:.2%}"],
                ], columns=["Component", "Value"])
                st.dataframe(cod_df.set_index("Component"), use_container_width=True,
                             column_config={"Value": st.column_config.TextColumn("Value", width=120)})

            with col_e:
                st.caption("Cost of Equity (CAPM)")
                coe_df = pd.DataFrame([
                    ["Risk-Free Rate (10y)", f"{rf_rate:.2%}"],
                    ["Beta",                 f"{beta_adj:.2f}"],
                    ["Equity Risk Premium",  f"{erp_adj:.2%}"],
                    ["Cost of Equity",       f"{coe:.2%}"],
                ], columns=["Component", "Value"])
                st.dataframe(coe_df.set_index("Component"), use_container_width=True,
                             column_config={"Value": st.column_config.TextColumn("Value", width=120)})

            st.caption("Capital Structure & WACC")
            cap_df = pd.DataFrame({
                "":              ["Value", "Weight", "Cost", "WACC Contribution"],
                "Debt":          [fmt(w["debt_val"]),   f"{wd:.2%}", f"{cod:.2%}", f"{wd*cod:.2%}"],
                "Equity":        [fmt(w["equity_val"]), f"{we:.2%}", f"{coe:.2%}", f"{we*coe:.2%}"],
                "Total Capital": [fmt(tc),              "100.00%",   "—",          f"{wacc:.2%}"],
            }).set_index("")
            col_cfg = {c: st.column_config.TextColumn(c, width=120) for c in cap_df.columns}
            st.dataframe(cap_df, use_container_width=True, column_config=col_cfg)

        else:
            st.info("Insights data is unavailable for this ticker.")

    # ── Tab 4: Valuations ─────────────────────────────────────────────────────
    with tab_val:
        (sub_cf_irr,) = st.tabs(["📈 CF + IRR"])
        with sub_cf_irr:
            if norm:
                render_cf_irr_tab(norm, raw)
            else:
                st.info("Load a ticker to see the valuation model.")
