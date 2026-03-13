"""
normalized_pe_tab.py
Phil Town Rule #1 – Normalized P/E Valuation — Streamlit UI layer.

This module is pure UI: session-state management + widget rendering.
ALL financial computation is delegated to backend.logic_engine.compute_normalized_pe().
"""

import streamlit as st
from backend.logic_engine import compute_normalized_pe


# ─────────────────────────────────────────────────────────────────────────────
#  Display-only helpers  (no computation — formatting strings for the UI)
# ─────────────────────────────────────────────────────────────────────────────

def _f_price(v):
    return f"${v:,.2f}" if v is not None else "N/A"


def _f_pct(v, decimals=1):
    return f"{v:.{decimals}f}%" if v is not None else "N/A"


def _fmt_cagr(v):
    """Fractional CAGR (or 'N/M') → display string."""
    if v is None or v == "N/M":
        return "N/M"
    return f"{v * 100:.1f}%" if isinstance(v, float) else str(v)


def _fmt_upside(fraction):
    """Fraction (e.g. 0.25) → '+25.0%' display string + is_positive flag."""
    if fraction is None:
        return "N/A", None
    pct  = fraction * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%", pct > 0


# ─────────────────────────────────────────────────────────────────────────────
#  Color palette
# ─────────────────────────────────────────────────────────────────────────────

_Y   = "#fef9c3";  _YT  = "#78350f"   # yellow  – editable input
_G   = "#d1fae5";  _GT  = "#065f46"   # green   – formula / computed
_D   = "#f3f4f6";  _DT  = "#374151"   # grey    – auto-pulled data
_GN  = "#86efac";  _GNT = "#14532d"   # bright green – ON SALE
_RD  = "#fca5a5";  _RDT = "#7f1d1d"   # soft red     – NOT ON SALE
_POS_BG = "#d1fae5"; _POS_FG = "#065f46"   # positive upside
_NEG_BG = "#fee2e2"; _NEG_FG = "#991b1b"   # negative (downside)


# ─────────────────────────────────────────────────────────────────────────────
#  Section / sub-header helpers  (match app.py / cf_irr_tab.py style)
# ─────────────────────────────────────────────────────────────────────────────

def _sec(title):
    st.markdown(
        f"<div style='font-size:1.05em;font-weight:bold;color:#ffffff;"
        f"background:#1c2b46;padding:6px 15px;border-radius:4px;"
        f"margin-top:24px;margin-bottom:6px;'>{title}</div>",
        unsafe_allow_html=True,
    )


def _sub(title):
    st.markdown(
        f"<div style='font-size:0.88em;font-weight:700;color:#1c2b46;"
        f"border-left:3px solid #1c2b46;padding-left:8px;"
        f"margin-top:14px;margin-bottom:2px;'>{title}</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HTML table renderers
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """<style>
.pe-tbl{width:100%;border-collapse:collapse;font-size:0.82em;
        font-family:'Source Sans Pro',sans-serif;}
.pe-tbl th{background:#1c2b46;color:#fff;font-weight:700;
           padding:7px 12px;text-align:left;border:1px solid #334;}
.pe-tbl td{padding:6px 12px;border:1px solid #e5e7eb;vertical-align:middle;}
.pe-tbl .v{text-align:right;font-variant-numeric:tabular-nums;}
.pe-tbl .n{color:#6b7280;font-style:italic;font-size:0.93em;}
</style>"""


def _render_table1(rows):
    """2-column table. rows: (label, value_str, bg, fg, bold_value)"""
    body = ""
    for lbl, val, bg, fg, bv in rows:
        fw = "700" if bv else "500"
        body += (
            f"<tr style='background:{bg};'>"
            f"<td style='color:{fg};font-weight:600;'>{lbl}</td>"
            f"<td class='v' style='color:{fg};font-weight:{fw};'>{val}</td>"
            f"</tr>"
        )
    st.markdown(
        f"{_CSS}<table class='pe-tbl'>"
        f"<tr><th>Metric</th><th>Value</th></tr>{body}</table>",
        unsafe_allow_html=True,
    )


def _render_table2(rows):
    """3-column table. rows: (label, value_str, note, bg, fg)"""
    body = ""
    for lbl, val, note, bg, fg in rows:
        body += (
            f"<tr style='background:{bg};'>"
            f"<td style='color:{fg};font-weight:700;'>{lbl}</td>"
            f"<td class='v' style='color:{fg};'>{val}</td>"
            f"<td class='n'>{note}</td>"
            f"</tr>"
        )
    st.markdown(
        f"{_CSS}<table class='pe-tbl'>"
        f"<tr><th>Component</th><th>Value</th><th>Note</th></tr>{body}</table>",
        unsafe_allow_html=True,
    )


def _legend():
    st.markdown(
        "<div style='font-size:0.75em;color:#6b7280;margin-top:6px;'>"
        "<span style='background:#fef9c3;padding:2px 7px;border-radius:3px;"
        "color:#78350f;margin-right:8px;'>■ Editable</span>"
        "<span style='background:#d1fae5;padding:2px 7px;border-radius:3px;"
        "color:#065f46;margin-right:8px;'>■ Formula</span>"
        "<span style='background:#f3f4f6;padding:2px 7px;border-radius:3px;"
        "color:#374151;'>■ Data</span>"
        "</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Main render function
# ─────────────────────────────────────────────────────────────────────────────

def render_normalized_pe_tab(norm, raw):
    """
    Render the Normalized PE (Phil Town Rule #1) sub-tab.

    Parameters
    ----------
    norm : DataNormalizer  (.raw_data feeds the logic engine)
    raw  : dict            overview from GatewayAgent.fetch_overview()
    """
    _pe_ticker = (raw or {}).get("symbol") or ""
    rf         = float(st.session_state.get("treasury_rate", 0.042))

    # ── Ticker change → reset session state + load defaults from engine ───────
    if st.session_state.get("pe_ticker") != _pe_ticker:
        for k in list(st.session_state.keys()):
            if k.startswith("pe_"):
                del st.session_state[k]
        st.session_state["pe_ticker"] = _pe_ticker

        # One-time call to resolve model defaults for this ticker
        _d = compute_normalized_pe(norm.raw_data, raw, {}, rf=rf)
        st.session_state["pe_growth_pct"]   = _d["growth_pct"]    # = growth_default
        st.session_state["pe_years"]        = _d["years"]         # = 7
        st.session_state["pe_discount_pct"] = _d["disc_pct"]      # = 15.0
        st.session_state["pe_mos_pct"]      = _d["mos_pct"]       # = 15.0
        st.session_state["pe_use_wacc"]     = False

    # ── Read live user overrides from session state ───────────────────────────
    g_pct    = float(st.session_state["pe_growth_pct"])
    years    = int(st.session_state["pe_years"])
    use_wacc = bool(st.session_state["pe_use_wacc"])
    disc_pct = float(st.session_state["pe_discount_pct"])
    mos_pct  = float(st.session_state["pe_mos_pct"])

    # ── Delegate ALL computation to the logic engine ──────────────────────────
    r = compute_normalized_pe(
        norm.raw_data, raw,
        params={
            "growth_pct": g_pct,
            "years":      years,
            "use_wacc":   use_wacc,
            "disc_pct":   disc_pct,
            "mos_pct":    mos_pct,
        },
        rf=rf,
    )

    # ── Unpack result for display ─────────────────────────────────────────────
    eps_ttm      = r["eps_ttm"]
    eps_3yr      = r["eps_3yr"]
    eps_5yr      = r["eps_5yr"]
    eps_10yr     = r["eps_10yr"]
    wacc         = r["wacc"]
    pe_a         = r["pe_a"]
    pe_b         = r["pe_b"]
    pe_c         = r["pe_c"]
    on_sale      = r["on_sale"]

    disc_label = f"{r['disc_pct']:.2f}%  (WACC)" if use_wacc else f"{r['disc_pct']:.2f}%"
    pe_c_str   = f"{pe_c:.1f}×"   if pe_c is not None else "N/A"
    pe_a_str   = f"{pe_a:.1f}×"   if pe_a > 0        else "N/A"
    pe_b_str   = f"{pe_b:.1f}×"   if pe_b is not None else "N/A"

    on_sale_str = "ON SALE ✅"    if on_sale else "NOT ON SALE ❌"
    on_sale_bg  = _GN             if on_sale else _RD
    on_sale_fg  = _GNT            if on_sale else _RDT

    upside_fv_str,  upside_fv_pos  = _fmt_upside(r["upside_to_fv"])
    upside_buy_str, upside_buy_pos = _fmt_upside(r["upside_to_buy"])

    def _upside_color(is_pos):
        if is_pos is True:  return _POS_BG, _POS_FG
        if is_pos is False: return _NEG_BG, _NEG_FG
        return _D, _DT

    # ── Render ────────────────────────────────────────────────────────────────
    _sec("📊 Normalized PE  ·  Phil Town Rule #1")

    # Table 1 — Valuation Results
    _sub("Table 1  ·  Valuation Results")

    t1 = [
        # (label, value_str, bg, fg, bold_value)
        ("EPS (TTM)",              _f_price(eps_ttm),                              _D,         _DT,         False),
        ("Est. Future Growth (%)", _f_pct(g_pct),                                  _Y,         _YT,         False),
        ("Number of Years",        str(years),                                      _Y,         _YT,         False),
        ("Estimated Future EPS",   _f_price(r["future_eps"]),                       _G,         _GT,         False),
        ("Discount Rate",          disc_label,                                      _Y,         _YT,         False),
        ("Discounted EPS",         _f_price(r["discounted_eps"]),                   _G,         _GT,         False),
        ("Estimated PE",           pe_c_str,                                        _G,         _GT,         False),
        ("Fair Value Per Share",   _f_price(r["fair_value"]),                       _G,         _GT,         True),
        ("Margin of Safety (%)",   _f_pct(mos_pct, 0),                             _Y,         _YT,         False),
        ("Buy Price",              _f_price(r["buy_price"]),                        _G,         _GT,         True),
        ("Current Stock Price",    _f_price(r["price_now"]),                        _D,         _DT,         False),
        ("Company on-sale?",       on_sale_str,                                     on_sale_bg, on_sale_fg,  True),
        ("Upside to Fair Value",   upside_fv_str,  *_upside_color(upside_fv_pos),              False),
        ("Upside to Buy Price",    upside_buy_str, *_upside_color(upside_buy_pos),             False),
    ]
    _render_table1(t1)
    _legend()

    # Table 2 — Estimated PE breakdown
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    _sub("Table 2  ·  Estimated PE  (Conservative P/E Calculation)")

    t2 = [
        # (label, value_str, note, bg, fg)
        ("(a)  Default PE",    pe_a_str, f"Rule of thumb: 2 × Growth Rate  ({g_pct:.1f}% × 2 = {pe_a:.1f}×)", _G, _GT),
        ("(b)  Historical PE", pe_b_str, "10-year average P/E from Valuation Multiples  (Insights tab)",        _D, _DT),
        ("(c)  Estimated PE",  pe_c_str, "Conservative PE: MIN(a, b)  —  per Phil Town's Rule #1",              _Y, _YT),
    ]
    _render_table2(t2)

    # Model Inputs — controls
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    _sub("Model Inputs")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.number_input(
            "Est. Future Growth (%)",
            min_value=0.0, max_value=50.0, step=0.5,
            key="pe_growth_pct",
            help=(
                "Annual EPS growth rate.  "
                f"Default = avg of 3yr ({_fmt_cagr(eps_3yr)}), "
                f"5yr ({_fmt_cagr(eps_5yr)}), "
                f"10yr ({_fmt_cagr(eps_10yr)}) EPS CAGRs."
            ),
        )

    with c2:
        st.number_input(
            "Number of Years",
            min_value=1, max_value=20, step=1,
            key="pe_years",
            help="Forecast horizon.  Phil Town typically uses 10 years; default here is 7.",
        )

    with c3:
        st.checkbox(
            f"Use WACC ({wacc * 100:.2f}%)",
            key="pe_use_wacc",
            help="When ON, replaces the manual Discount Rate with the model-computed WACC.",
        )

    with c4:
        st.number_input(
            "Discount Rate (%)",
            min_value=1.0, max_value=40.0, step=0.5,
            disabled=use_wacc,
            key="pe_discount_pct",
            help="Required minimum annual return.  Phil Town recommends 15%.",
        )

    with c5:
        st.number_input(
            "Margin of Safety (%)",
            min_value=0.0, max_value=80.0, step=5.0,
            key="pe_mos_pct",
            help="Buy Price = Fair Value × (1 − MoS%).  Default: 15%.",
        )
