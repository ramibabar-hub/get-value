"""
cf_irr_tab.py
Cameron Stewart's Cashflow Valuation & IRR Model.

Standalone module — zero coupling to Financials or Insights tabs.
Called from app.py inside the "💰 Valuations" → "📈 CF + IRR" sub-tab.
"""

import math
import pandas as pd
import streamlit as st
from agents.insights_agent import InsightsAgent


# ─────────────────────────────────────────────────────────────────────────────
#  Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def _s(v):
    """Safe coercion to float; returns None on invalid / non-finite values."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _d(a, b):
    """Safe division — None on zero or None denominator."""
    a, b = _s(a), _s(b)
    if a is None or b is None or b == 0:
        return None
    return a / b


def _year_label(rec):
    """Extract a 4-char year string from an FMP statement record."""
    if not isinstance(rec, dict):
        return "N/A"
    return (
        str(rec.get("fiscalYear")    or "")
        or str(rec.get("calendarYear") or "")
        or str(rec.get("date")        or "")[:4]
        or "N/A"
    )


def _irr_calc(cashflows, tol=1e-7, max_iter=300):
    """
    Newton-Raphson IRR.  cashflows[0] must be negative (initial investment).
    Returns None when the calculation fails to converge or produces an
    unreasonable result.
    """
    if not cashflows or _s(cashflows[0]) is None or cashflows[0] >= 0:
        return None
    r = 0.10
    for _ in range(max_iter):
        try:
            npv  = sum(cf / (1 + r) ** t for t, cf in enumerate(cashflows))
            dnpv = sum(-t * cf / (1 + r) ** (t + 1)
                       for t, cf in enumerate(cashflows))
        except (ZeroDivisionError, OverflowError):
            return None
        if abs(dnpv) < 1e-12:
            break
        r_new = r - npv / dnpv
        if abs(r_new - r) < tol:
            return r_new if (math.isfinite(r_new) and -1 < r_new < 10) else None
        r = r_new
    return r if (math.isfinite(r) and -1 < r < 10) else None


# ── TTM helpers ───────────────────────────────────────────────────────────────

def _ttm_flow(q_list, key):
    """Sum of last 4 quarters for flow-statement items (IS / CF)."""
    if not q_list:
        return None
    vals = [_s(q.get(key)) for q in q_list[:4] if isinstance(q, dict)]
    clean = [v for v in vals if v is not None]
    return sum(clean) if clean else None


def _ttm_bs(q_bs, key):
    """Most-recent quarter for balance-sheet items."""
    if not q_bs or not isinstance(q_bs[0], dict):
        return None
    return _s(q_bs[0].get(key))


# ── Display formatters ────────────────────────────────────────────────────────

def _f_mm(v):
    """Format as $MM with 1 decimal place."""
    f = _s(v)
    return "N/A" if f is None else f"{f / 1e6:,.1f}"


def _f_pct(v):
    """Format 0-to-1 ratio as percentage (1 dp)."""
    if isinstance(v, str):        # pass "N/M" through unchanged
        return v
    f = _s(v)
    return "N/A" if f is None else f"{f * 100:.1f}%"


def _f_x(v):
    """Format as a 'Xx' multiple."""
    if isinstance(v, str):
        return v
    f = _s(v)
    return "N/A" if f is None else f"{f:.1f}x"


def _f_price(v):
    """Format as a dollar price."""
    f = _s(v)
    return "N/A" if f is None else f"${f:,.2f}"


def _f_ps(v):
    """Format per-share value (2 dp)."""
    f = _s(v)
    return "N/A" if f is None else f"{f:,.2f}"


def _pct_default(v, fallback):
    """Convert a 0–1 CAGR float to a %-display default for number_input."""
    if isinstance(v, str):
        return fallback
    f = _s(v)
    if f is not None and math.isfinite(f) and -1.0 < f < 10.0:
        return round(f * 100.0, 1)
    return fallback


# ─────────────────────────────────────────────────────────────────────────────
#  UI helpers (match app.py section-header style)
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
#  Data builder: EV/EBITDA Historical (Table 2.1)
# ─────────────────────────────────────────────────────────────────────────────

def _ebitda_hist(norm, raw, ins):
    """
    Build display rows for Table 2.1 (EV/EBITDA Historical).

    Returns
    -------
    hist_disp   list[dict] — pre-formatted display rows (oldest → newest)
    ttm_disp    dict       — TTM display row
    avg_disp    dict       — Average display row
    cagr_disp   dict       — CAGR display row (10yr / 5yr)
    nd_ebt_ttm  float|None — TTM Net Debt/EBITDA (for checklist)
    rev_c10     float|str|None
    ebt_c10     float|str|None
    ebt_avg_mult float|None — average historical EV/EBITDA (forecast default)
    base_ebitda float|None  — most-recent annual EBITDA
    """
    is_l = norm.is_l
    bs_l = norm.bs_l
    km_l = norm.km_l

    COLS = ["Year", "Revenues ($MM)", "EBITDA ($MM)", "Market Cap ($MM)",
            "Debt ($MM)", "Cash ($MM)", "EV ($MM)", "EV/EBITDA", "Net Debt/EBITDA"]

    raw_hist = []   # numeric for computing averages
    hist_disp = []
    for i in range(min(len(is_l), 10)):
        rec_is = is_l[i] if isinstance(is_l[i], dict) else {}
        rec_bs = bs_l[i] if i < len(bs_l) and isinstance(bs_l[i], dict) else {}
        rec_km = km_l[i] if i < len(km_l) and isinstance(km_l[i], dict) else {}

        yr   = _year_label(rec_is)
        rev  = _s(rec_is.get("revenue"))
        ebt  = _s(rec_is.get("ebitda"))
        mkt  = _s(rec_km.get("marketCap"))
        debt = _s(rec_bs.get("totalDebt"))
        cash = _s(rec_bs.get("cashAndCashEquivalents"))
        ev   = (mkt + (debt or 0) - (cash or 0)) if mkt is not None else None
        ev_ebt  = _d(ev, ebt)
        nd_ebt  = _d(((debt or 0) - (cash or 0)) if debt is not None else None, ebt)

        raw_hist.append({"rev": rev, "ebt": ebt, "mkt": mkt,
                         "debt": debt, "cash": cash, "ev": ev,
                         "ev_ebt": ev_ebt, "nd_ebt": nd_ebt})
        hist_disp.append({
            "Year": yr,
            "Revenues ($MM)":    _f_mm(rev),
            "EBITDA ($MM)":      _f_mm(ebt),
            "Market Cap ($MM)":  _f_mm(mkt),
            "Debt ($MM)":        _f_mm(debt),
            "Cash ($MM)":        _f_mm(cash),
            "EV ($MM)":          _f_mm(ev),
            "EV/EBITDA":         _f_x(ev_ebt),
            "Net Debt/EBITDA":   _f_x(nd_ebt),
        })

    # Oldest → newest for display
    hist_disp.reverse()
    raw_hist.reverse()

    # TTM row
    rev_t  = _ttm_flow(norm.q_is, "revenue")
    ebt_t  = _ttm_flow(norm.q_is, "ebitda")
    mkt_t  = _s(raw.get("mktCap"))
    debt_t = _ttm_bs(norm.q_bs, "totalDebt")
    cash_t = _ttm_bs(norm.q_bs, "cashAndCashEquivalents")
    ev_t   = (mkt_t + (debt_t or 0) - (cash_t or 0)) if mkt_t is not None else None
    nd_ebt_t = _d(((debt_t or 0) - (cash_t or 0)) if debt_t is not None else None, ebt_t)

    ttm_disp = {
        "Year":              "TTM",
        "Revenues ($MM)":    _f_mm(rev_t),
        "EBITDA ($MM)":      _f_mm(ebt_t),
        "Market Cap ($MM)":  _f_mm(mkt_t),
        "Debt ($MM)":        _f_mm(debt_t),
        "Cash ($MM)":        _f_mm(cash_t),
        "EV ($MM)":          _f_mm(ev_t),
        "EV/EBITDA":         _f_x(_d(ev_t, ebt_t)),
        "Net Debt/EBITDA":   _f_x(nd_ebt_t),
    }

    # Average row (numeric → format)
    def _avg_col(key):
        vals = [r[key] for r in raw_hist if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    avg_ev_ebt = _avg_col("ev_ebt")
    avg_disp = {
        "Year":              "Average",
        "Revenues ($MM)":    _f_mm(_avg_col("rev")),
        "EBITDA ($MM)":      _f_mm(_avg_col("ebt")),
        "Market Cap ($MM)":  _f_mm(_avg_col("mkt")),
        "Debt ($MM)":        _f_mm(_avg_col("debt")),
        "Cash ($MM)":        _f_mm(_avg_col("cash")),
        "EV ($MM)":          _f_mm(_avg_col("ev")),
        "EV/EBITDA":         _f_x(avg_ev_ebt),
        "Net Debt/EBITDA":   _f_x(_avg_col("nd_ebt")),
    }

    # CAGR row (from InsightsAgent — 10yr primary, 5yr secondary)
    cagr_data = ins.get_insights_cagr()
    rev_c10 = next((r.get("10yr") for r in cagr_data if r["CAGR"] == "Revenues"), None)
    rev_c5  = next((r.get("5yr")  for r in cagr_data if r["CAGR"] == "Revenues"), None)
    ebt_c10 = next((r.get("10yr") for r in cagr_data if r["CAGR"] == "EBITDA"),   None)
    ebt_c5  = next((r.get("5yr")  for r in cagr_data if r["CAGR"] == "EBITDA"),   None)

    cagr_disp = {
        "Year":              "CAGR (10yr / 5yr)",
        "Revenues ($MM)":    f"{_f_pct(rev_c10)} / {_f_pct(rev_c5)}",
        "EBITDA ($MM)":      f"{_f_pct(ebt_c10)} / {_f_pct(ebt_c5)}",
        "Market Cap ($MM)":  "—",
        "Debt ($MM)":        "—",
        "Cash ($MM)":        "—",
        "EV ($MM)":          "—",
        "EV/EBITDA":         "—",
        "Net Debt/EBITDA":   "—",
    }

    # For forecast defaults
    ebt_avg_mult = avg_ev_ebt
    base_ebitda = (_s(is_l[0].get("ebitda"))
                   if is_l and isinstance(is_l[0], dict) else None)

    return (hist_disp, ttm_disp, avg_disp, cagr_disp,
            nd_ebt_t, rev_c10, ebt_c10, ebt_c5, ebt_avg_mult, base_ebitda)


# ─────────────────────────────────────────────────────────────────────────────
#  Data builder: Adj. FCF/s Historical (Table 3.1)
# ─────────────────────────────────────────────────────────────────────────────

def _fcf_hist(norm, raw, ins):
    """
    Build display rows for Table 3.1 (Adj. FCF/s Historical).

    Returns
    -------
    hist_disp   list[dict]
    ttm_disp    dict
    avg_disp    dict
    cagr_disp   dict
    adj_ps_ttm  float|None — TTM Adj.FCF/share (base for FCF forecast)
    fcf_c10     float|str|None
    fcf_c5      float|str|None
    """
    is_l = norm.is_l
    cf_l = norm.cf_l
    km_l = norm.km_l

    raw_hist  = []
    hist_disp = []
    for i in range(min(len(cf_l), 10)):
        rec_cf = cf_l[i] if isinstance(cf_l[i], dict) else {}
        rec_is = is_l[i] if i < len(is_l) and isinstance(is_l[i], dict) else {}
        rec_km = km_l[i] if i < len(km_l) and isinstance(km_l[i], dict) else {}

        yr     = _year_label(rec_is) if rec_is else "N/A"
        fcf    = _s(rec_cf.get("freeCashFlow"))
        sbc    = _s(rec_cf.get("stockBasedCompensation"))
        adj    = (fcf - (sbc or 0)) if fcf is not None else None
        sh     = (_s(rec_is.get("weightedAverageShsOutDil"))
                  or _s(rec_is.get("weightedAverageShsOut")))
        adj_ps = _d(adj, sh)
        px     = _s(rec_km.get("stockPrice"))
        yld    = _d(adj_ps, px)

        raw_hist.append({"adj_ps": adj_ps, "yld": yld})
        hist_disp.append({
            "Year":            yr,
            "FCF ($MM)":       _f_mm(fcf),
            "SBC ($MM)":       _f_mm(sbc),
            "Adj. FCF ($MM)":  _f_mm(adj),
            "Shares (MM)":     _f_mm(sh),
            "Adj. FCF/s":      _f_ps(adj_ps),
            "Stock Price":     _f_price(px),
            "Adj. FCF Yield":  _f_pct(yld),
        })

    hist_disp.reverse()
    raw_hist.reverse()

    # TTM row
    fcf_t   = _ttm_flow(norm.q_cf, "freeCashFlow")
    sbc_t   = _ttm_flow(norm.q_cf, "stockBasedCompensation")
    adj_t   = (fcf_t - (sbc_t or 0)) if fcf_t is not None else None
    sh_t    = (_ttm_flow(norm.q_is, "weightedAverageShsOutDil")
               or _ttm_flow(norm.q_is, "weightedAverageShsOut"))
    px_t    = _s(raw.get("price"))
    adj_ps_t = _d(adj_t, sh_t)
    yld_t   = _d(adj_ps_t, px_t)

    ttm_disp = {
        "Year":            "TTM",
        "FCF ($MM)":       _f_mm(fcf_t),
        "SBC ($MM)":       _f_mm(sbc_t),
        "Adj. FCF ($MM)":  _f_mm(adj_t),
        "Shares (MM)":     _f_mm(sh_t),
        "Adj. FCF/s":      _f_ps(adj_ps_t),
        "Stock Price":     _f_price(px_t),
        "Adj. FCF Yield":  _f_pct(yld_t),
    }

    # Average row
    def _avg_col(key):
        vals = [r[key] for r in raw_hist if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    avg_disp = {
        "Year":            "Average",
        "FCF ($MM)":       "—",
        "SBC ($MM)":       "—",
        "Adj. FCF ($MM)":  "—",
        "Shares (MM)":     "—",
        "Adj. FCF/s":      _f_ps(_avg_col("adj_ps")),
        "Stock Price":     "—",
        "Adj. FCF Yield":  _f_pct(_avg_col("yld")),
    }

    # CAGR row
    cagr_data = ins.get_insights_cagr()
    fcf_c10 = next((r.get("10yr") for r in cagr_data if r["CAGR"] == "Adj. FCF"), None)
    fcf_c5  = next((r.get("5yr")  for r in cagr_data if r["CAGR"] == "Adj. FCF"), None)

    cagr_disp = {
        "Year":            "CAGR (10yr / 5yr)",
        "FCF ($MM)":       "—",
        "SBC ($MM)":       "—",
        "Adj. FCF ($MM)":  f"{_f_pct(fcf_c10)} / {_f_pct(fcf_c5)}",
        "Shares (MM)":     "—",
        "Adj. FCF/s":      "—",
        "Stock Price":     "—",
        "Adj. FCF Yield":  "—",
    }

    return hist_disp, ttm_disp, avg_disp, cagr_disp, adj_ps_t, fcf_c10, fcf_c5


# ─────────────────────────────────────────────────────────────────────────────
#  Forecast builders
# ─────────────────────────────────────────────────────────────────────────────

def _ebitda_forecast(base_ebt, growth_pct, exit_mult, net_debt, shares, base_year):
    """
    10-year EBITDA forecast.
    Returns list of display-ready dicts.
    """
    g   = (growth_pct or 0.0) / 100.0
    m   = exit_mult or 15.0
    nd  = _s(net_debt) or 0.0
    sh  = _s(shares)
    ebt = _s(base_ebt)

    rows = []
    for y in range(1, 11):
        if ebt is None:
            break
        ebt_y = ebt * (1 + g) ** y
        ev_y  = ebt_y * m
        fv_sh = _d(ev_y - nd, sh)
        rows.append({
            "Year":              str(base_year + y),
            "EBITDA ($MM)":      _f_mm(ebt_y),
            "YoY Growth":        _f_pct(g),
            "EV ($MM)":          _f_mm(ev_y),
            "Fair Value/share":  _f_price(fv_sh),
        })
    return rows


def _fcf_forecast(base_adj_ps, growth_pct, exit_mult, base_year):
    """
    10-year Adj. FCF/s forecast.
    Returns (display_rows, cashflows_for_irr).
    cashflows_for_irr excludes t=0 entry price.
    """
    g    = (growth_pct or 0.0) / 100.0
    m    = exit_mult or 20.0
    base = _s(base_adj_ps)

    rows         = []
    irr_cashflows = []   # year 1..10, terminal included at year 10

    for y in range(1, 11):
        if base is None:
            break
        af_s  = base * (1 + g) ** y
        terminal = af_s * m if y == 10 else 0.0
        irr_cashflows.append(af_s + terminal)

        rows.append({
            "Year":                    str(base_year + y),
            "Adj. FCF/s":              _f_ps(af_s),
            "YoY Growth":              _f_pct(g),
            "Exit Fair Value/share":   _f_price(af_s * m) if y == 10 else "—",
        })
    return rows, irr_cashflows


# ─────────────────────────────────────────────────────────────────────────────
#  IRR sensitivity matrix builder
# ─────────────────────────────────────────────────────────────────────────────

def _irr_sensitivity(base_adj_ps, growth_pct, exit_mult, current_price):
    """
    Build a 5×5 IRR sensitivity matrix.
    Rows   : entry price variants (−20%, −10%, 0%, +10%, +20% of current_price)
    Columns: exit P/FCF multiples (exit_mult −10, −5, 0, +5, +10)
    Returns (row_labels, col_labels, matrix) where matrix[i][j] is IRR float|None.
    """
    g   = (growth_pct or 0.0) / 100.0
    px  = _s(current_price)
    em  = _s(exit_mult) or 20.0

    price_factors = [-0.20, -0.10, 0.00, 0.10, 0.20]
    mult_offsets  = [-10,   -5,    0,    5,    10  ]
    base          = _s(base_adj_ps)

    row_labels = [
        f"${px * (1 + f):,.2f} ({'+' if f >= 0 else ''}{int(f*100)}%)"
        if px else "N/A"
        for f in price_factors
    ]
    col_labels = [f"{em + d:.0f}x" for d in mult_offsets]

    matrix = []
    for pf in price_factors:
        entry = (px * (1 + pf)) if px else None
        row   = []
        for md in mult_offsets:
            m_here = em + md
            if base is None or entry is None or entry <= 0 or m_here <= 0:
                row.append(None)
                continue
            cfs = []
            for y in range(1, 11):
                af_s = base * (1 + g) ** y
                terminal = af_s * m_here if y == 10 else 0.0
                cfs.append(af_s + terminal)
            row.append(_irr_calc([-entry] + cfs))
        matrix.append(row)

    return row_labels, col_labels, matrix


# ─────────────────────────────────────────────────────────────────────────────
#  HTML rendering helpers
# ─────────────────────────────────────────────────────────────────────────────

_CLR_PASS = "#d1fae5"   # green tint
_CLR_FAIL = "#fee2e2"   # red tint
_CLR_NA   = "#f3f4f6"   # grey tint
_CLR_TEXT_PASS = "#065f46"
_CLR_TEXT_FAIL = "#991b1b"


def _checklist_html(checklist):
    """
    Build an HTML table for the 6-item checklist.
    checklist: [(label, value_str, pass_bool_or_None, threshold_str), ...]
    """
    rows_html = ""
    for label, val, passed, threshold in checklist:
        if passed is True:
            bg, fg, icon = _CLR_PASS, _CLR_TEXT_PASS, "✅"
        elif passed is False:
            bg, fg, icon = _CLR_FAIL, _CLR_TEXT_FAIL, "❌"
        else:
            bg, fg, icon = _CLR_NA, "#6b7280", "—"
        rows_html += (
            f"<tr style='background:{bg};'>"
            f"<td style='padding:8px 12px;font-size:0.85em;color:{fg};font-weight:600;'>{label}</td>"
            f"<td style='padding:8px 12px;font-size:0.85em;color:#4d6b88;text-align:center;'>{threshold}</td>"
            f"<td style='padding:8px 12px;font-size:0.85em;color:{fg};font-weight:700;text-align:center;'>{val}</td>"
            f"<td style='padding:8px 12px;font-size:1.1em;text-align:center;'>{icon}</td>"
            f"</tr>"
        )
    return (
        "<div style='overflow-x:auto;'>"
        "<table style='width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;'>"
        "<thead><tr style='background:#1c2b46;'>"
        "<th style='padding:8px 12px;color:#fff;font-size:0.78em;text-align:left;'>Metric</th>"
        "<th style='padding:8px 12px;color:#fff;font-size:0.78em;text-align:center;'>Threshold</th>"
        "<th style='padding:8px 12px;color:#fff;font-size:0.78em;text-align:center;'>Value (10yr CAGR / TTM)</th>"
        "<th style='padding:8px 12px;color:#fff;font-size:0.78em;text-align:center;'>Status</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )


def _sensitivity_html(row_labels, col_labels, matrix):
    """
    Build a colour-coded HTML sensitivity matrix.
    IRR ≥ 12% → green, 8–12% → amber, < 8% or None → red.
    """
    def _irr_color(v):
        if v is None:
            return "#fee2e2", _CLR_TEXT_FAIL
        if v >= 0.12:
            return _CLR_PASS, _CLR_TEXT_PASS
        if v >= 0.08:
            return "#fef9c3", "#92400e"
        return "#fee2e2", _CLR_TEXT_FAIL

    header = "".join(
        f"<th style='padding:7px 10px;background:#1c2b46;color:#fff;"
        f"font-size:0.76em;white-space:nowrap;text-align:center;'>{c}</th>"
        for c in col_labels
    )
    rows_html = ""
    for i, row_lbl in enumerate(row_labels):
        cells = ""
        for j, irr in enumerate(matrix[i]):
            bg, fg = _irr_color(irr)
            txt = f"{irr*100:.1f}%" if irr is not None else "N/A"
            cells += (
                f"<td style='padding:7px 10px;background:{bg};color:{fg};"
                f"font-weight:700;font-size:0.83em;text-align:center;"
                f"white-space:nowrap;'>{txt}</td>"
            )
        rows_html += (
            f"<tr><td style='padding:7px 10px;background:#f8fafc;font-size:0.78em;"
            f"white-space:nowrap;color:#1c2b46;font-weight:600;'>{row_lbl}</td>"
            f"{cells}</tr>"
        )
    return (
        "<div style='overflow-x:auto;margin-top:6px;'>"
        "<table style='border-collapse:collapse;'>"
        "<thead><tr>"
        "<th style='padding:7px 10px;background:#1c2b46;color:#fff;font-size:0.76em;"
        "white-space:nowrap;text-align:left;'>Entry Price</th>"
        f"{header}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Main render function
# ─────────────────────────────────────────────────────────────────────────────

def render_cf_irr_tab(norm, raw):
    """
    Render Cameron Stewart's CF + IRR Valuation Model.
    Entry point called from app.py inside the Valuations tab.
    """
    if not norm:
        st.info("Financial data is unavailable for this ticker.")
        return

    # ── Build InsightsAgent ──────────────────────────────────────────────────
    ins = InsightsAgent(norm.raw_data, raw)

    # ── Build historical data ────────────────────────────────────────────────
    (ebt_hist, ebt_ttm, ebt_avg, ebt_cagr,
     nd_ebt_ttm, rev_c10, ebt_c10, ebt_c5,
     ebt_avg_mult, base_ebitda) = _ebitda_hist(norm, raw, ins)

    (fcf_hist, fcf_ttm, fcf_avg, fcf_cagr,
     adj_ps_ttm, fcf_c10, fcf_c5) = _fcf_hist(norm, raw, ins)

    # ── Pull profitability TTM (Adj. FCF margin) ─────────────────────────────
    prof_rows    = ins.get_insights_profitability()
    fcf_margin_t = next(
        (r.get("TTM") for r in prof_rows if r.get("Profitability") == "Adj. FCF"),
        None,
    )

    # ── Base year for forecasts ──────────────────────────────────────────────
    base_year = 2024
    if norm.is_l and isinstance(norm.is_l[0], dict):
        try:
            base_year = int(_year_label(norm.is_l[0]))
        except ValueError:
            pass

    # ── TTM balance-sheet for EBITDA forecast ───────────────────────────────
    debt_ttm = _ttm_bs(norm.q_bs, "totalDebt")
    cash_ttm = _ttm_bs(norm.q_bs, "cashAndCashEquivalents")
    net_debt_ttm = ((debt_ttm or 0) - (cash_ttm or 0)) if debt_ttm is not None else 0.0

    sh_ttm = (_ttm_flow(norm.q_is, "weightedAverageShsOutDil")
              or _ttm_flow(norm.q_is, "weightedAverageShsOut"))

    price_now = _s(raw.get("price"))

    # ── Session-state defaults (one-time init, prefixed cfirr_) ─────────────
    def _init(key, val):
        if key not in st.session_state:
            st.session_state[key] = val

    _init("cfirr_ebitda_growth", _pct_default(ebt_c5,  10.0))
    _init("cfirr_ebitda_exit",   round(ebt_avg_mult, 1) if ebt_avg_mult else 15.0)
    _init("cfirr_fcf_growth",    _pct_default(fcf_c5,  10.0))
    _init("cfirr_fcf_exit",      20.0)
    _init("cfirr_mos",           25.0)

    # ── Compute forecasts (reactive — re-runs on any input change) ───────────
    ebt_forecast = _ebitda_forecast(
        base_ebitda,
        st.session_state["cfirr_ebitda_growth"],
        st.session_state["cfirr_ebitda_exit"],
        net_debt_ttm,
        sh_ttm,
        base_year,
    )

    fcf_forecast, fcf_cashflows = _fcf_forecast(
        adj_ps_ttm,
        st.session_state["cfirr_fcf_growth"],
        st.session_state["cfirr_fcf_exit"],
        base_year,
    )

    # ── IRR ──────────────────────────────────────────────────────────────────
    irr_val = None
    if price_now and price_now > 0 and fcf_cashflows:
        irr_val = _irr_calc([-price_now] + fcf_cashflows)

    # ── Checklist evaluation ─────────────────────────────────────────────────
    def _check(val, threshold, lower_is_better=False):
        """Returns (display_str, pass_bool|None)."""
        if isinstance(val, str):            # "N/M" from _cagr
            return val, None
        f = _s(val)
        if f is None:
            return "N/A", None
        passed = (f < threshold) if lower_is_better else (f >= threshold)
        return _f_pct(f), passed

    rev_disp,  rev_p  = _check(rev_c10,       0.07)
    ebt_disp,  ebt_p  = _check(ebt_c10,       0.10)
    fcf_disp,  fcf_p  = _check(fcf_c10,       0.10)
    fcm_disp,  fcm_p  = _check(fcf_margin_t,  0.10)
    nd_disp,   nd_p   = _check(nd_ebt_ttm,    3.0,  lower_is_better=True)
    irr_disp,  irr_p  = _check(irr_val,       0.12)

    # For Net Debt/EBITDA display, format as "Xx" not "%"
    if nd_ebt_ttm is not None and not isinstance(nd_ebt_ttm, str):
        nd_disp = _f_x(nd_ebt_ttm)

    checklist = [
        ("Revenue Growth (10yr CAGR)",    rev_disp,  rev_p,  "> 7%"),
        ("EBITDA Growth (10yr CAGR)",     ebt_disp,  ebt_p,  "> 10%"),
        ("FCF Growth (10yr CAGR)",        fcf_disp,  fcf_p,  "> 10%"),
        ("Adj. FCF Margin (TTM)",         fcm_disp,  fcm_p,  "> 10%"),
        ("Net Debt / EBITDA (TTM)",       nd_disp,   nd_p,   "< 3x"),
        ("IRR — 10yr FCF Model",          irr_disp,  irr_p,  "> 12%"),
    ]

    all_pass = all(p is True  for _, _, p, _ in checklist)
    any_fail = any(p is False for _, _, p, _ in checklist)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — CHECKLIST & RESULT
    # ══════════════════════════════════════════════════════════════════════════
    _sec("1 · Quality Checklist")

    chk_col, badge_col = st.columns([3, 1])
    with chk_col:
        st.markdown(_checklist_html(checklist), unsafe_allow_html=True)

    with badge_col:
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        if all_pass:
            res_bg, res_txt, res_lbl = "#22c55e", "#fff", "PASS"
            res_sub = "All criteria met"
        elif any_fail:
            res_bg, res_txt, res_lbl = "#ef4444", "#fff", "FAIL"
            res_sub = "One or more criteria not met"
        else:
            res_bg, res_txt, res_lbl = "#94a3b8", "#fff", "INCOMPLETE"
            res_sub = "Insufficient data"

        st.markdown(
            f"<div style='text-align:center;padding:18px 10px;border-radius:10px;"
            f"background:{res_bg};margin-bottom:10px;'>"
            f"<div style='font-size:1.6em;font-weight:900;color:{res_txt};'>{res_lbl}</div>"
            f"<div style='font-size:0.75em;color:{res_txt};margin-top:4px;'>{res_sub}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        # ON SALE badge (N/A until WACC)
        st.markdown(
            "<div style='text-align:center;padding:14px 10px;border-radius:10px;"
            "background:#f1f5f9;border:2px dashed #94a3b8;'>"
            "<div style='font-size:1.1em;font-weight:900;color:#94a3b8;'>N/A</div>"
            "<div style='font-size:0.7em;color:#94a3b8;margin-top:3px;'>ON SALE<br>"
            "WACC pending</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — EBITDA ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    _sec("2 · EBITDA Analysis")

    # ── Table 2.1: EV/EBITDA Historical ──────────────────────────────────────
    _sub("Table 2.1 · EV/EBITDA Historical  (values in $MM unless noted)")
    all_ebt_rows = ebt_hist + [ebt_cagr, ebt_avg, ebt_ttm]
    df_ebt = pd.DataFrame(all_ebt_rows).set_index("Year")
    st.dataframe(df_ebt, use_container_width=True)

    # ── Inputs for forecast ───────────────────────────────────────────────────
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    inp_a, inp_b, _ = st.columns([2, 2, 4])
    with inp_a:
        st.number_input(
            "EBITDA Growth Rate (%/yr)",
            min_value=-50.0, max_value=100.0, step=0.5, format="%.1f",
            key="cfirr_ebitda_growth",
            help="Annual EBITDA growth applied to the 10-year forecast.",
        )
    with inp_b:
        st.number_input(
            "Exit EV/EBITDA Multiple",
            min_value=1.0, max_value=100.0, step=0.5, format="%.1f",
            key="cfirr_ebitda_exit",
            help="EV/EBITDA multiple assumed at the end of the forecast period.",
        )

    # ── Table 2.2: EBITDA 10-Year Forecast ───────────────────────────────────
    _sub(f"Table 2.2 · EBITDA 10-Year Forecast  ({base_year + 1}–{base_year + 10})")
    if ebt_forecast:
        df_ebt_fc = pd.DataFrame(ebt_forecast).set_index("Year")
        st.dataframe(df_ebt_fc, use_container_width=True)
    else:
        st.caption("Insufficient base data to generate forecast.")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — FREE CASH FLOW ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    _sec("3 · Free Cash Flow Analysis")

    # ── Table 3.1: Adj. FCF/s Historical ─────────────────────────────────────
    _sub("Table 3.1 · Adj. FCF/s Historical  (values in $MM unless noted)")
    all_fcf_rows = fcf_hist + [fcf_cagr, fcf_avg, fcf_ttm]
    df_fcf = pd.DataFrame(all_fcf_rows).set_index("Year")
    st.dataframe(df_fcf, use_container_width=True)

    # ── Inputs for forecast ───────────────────────────────────────────────────
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    inp_c, inp_d, _ = st.columns([2, 2, 4])
    with inp_c:
        st.number_input(
            "Adj. FCF/s Growth Rate (%/yr)",
            min_value=-50.0, max_value=100.0, step=0.5, format="%.1f",
            key="cfirr_fcf_growth",
            help="Annual growth rate applied to Adj. FCF per share in the forecast.",
        )
    with inp_d:
        st.number_input(
            "Exit P/FCF Multiple",
            min_value=1.0, max_value=150.0, step=1.0, format="%.1f",
            key="cfirr_fcf_exit",
            help="P/Adj.FCF multiple assumed at year 10 to compute terminal value.",
        )

    # ── Table 3.2: Adj. FCF/s 10-Year Forecast ───────────────────────────────
    _sub(f"Table 3.2 · Adj. FCF/s 10-Year Forecast  ({base_year + 1}–{base_year + 10})")
    if fcf_forecast:
        df_fcf_fc = pd.DataFrame(fcf_forecast).set_index("Year")
        st.dataframe(df_fcf_fc, use_container_width=True)
    else:
        st.caption("Insufficient base data to generate forecast.")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — IRR CALCULATION & SENSITIVITY
    # ══════════════════════════════════════════════════════════════════════════
    _sec("4 · IRR Calculation & Sensitivity")

    # ── IRR Calculation table ────────────────────────────────────────────────
    _sub("IRR Cash Flow Schedule")
    if price_now and fcf_cashflows:
        irr_rows = [{"Year": "0 (Entry)", "Cash Flow": _f_price(-price_now),
                     "Note": "Entry — Current Market Price"}]
        for idx, cf in enumerate(fcf_cashflows, start=1):
            note = "Adj. FCF/s" if idx < 10 else "Adj. FCF/s + Terminal Value"
            irr_rows.append({"Year": str(base_year + idx),
                             "Cash Flow": _f_price(cf), "Note": note})
        df_irr = pd.DataFrame(irr_rows).set_index("Year")
        st.dataframe(df_irr, use_container_width=True)

        irr_color = "#22c55e" if (irr_val and irr_val >= 0.12) else "#ef4444"
        irr_text  = f"{irr_val * 100:.2f}%" if irr_val is not None else "N/A"
        st.markdown(
            f"<div style='margin-top:8px;padding:10px 18px;border-radius:8px;"
            f"background:{irr_color};display:inline-block;'>"
            f"<span style='color:#fff;font-size:1.05em;font-weight:800;'>"
            f"IRR = {irr_text}</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("Insufficient data to compute IRR.")

    # ── IRR Sensitivity matrix ────────────────────────────────────────────────
    _sub("IRR Sensitivity  (Entry Price vs. Exit P/FCF Multiple)")
    if price_now and adj_ps_ttm:
        row_lbl, col_lbl, matrix = _irr_sensitivity(
            adj_ps_ttm,
            st.session_state["cfirr_fcf_growth"],
            st.session_state["cfirr_fcf_exit"],
            price_now,
        )
        st.markdown(_sensitivity_html(row_lbl, col_lbl, matrix),
                    unsafe_allow_html=True)
        st.caption("Green ≥ 12% · Amber 8–12% · Red < 8%")
    else:
        st.caption("Insufficient data for sensitivity analysis.")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — FINAL OUTPUT
    # ══════════════════════════════════════════════════════════════════════════
    _sec("5 · Final Output")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Fair Value / Share", "N/A",
                  help="Will be available once WACC is implemented.")
    with c2:
        st.metric("Current Price", _f_price(price_now))
    with c3:
        st.number_input(
            "Margin of Safety (%)",
            min_value=0.0, max_value=80.0, step=1.0, format="%.0f",
            key="cfirr_mos",
            help="Discount applied to Fair Value to derive the Buy Price.",
        )
    with c4:
        st.metric("Buy Price", "N/A",
                  help="Fair Value × (1 − MOS). Available once WACC is implemented.")

    st.markdown(
        "<div style='margin-top:10px;padding:8px 14px;border-radius:6px;"
        "background:#fef9c3;color:#92400e;font-size:0.80em;'>"
        "⚠️  <strong>Fair Value</strong> and <strong>Buy Price</strong> require WACC — "
        "these will be populated in a future update. "
        "The IRR model and all historical / forecast tables are fully active.</div>",
        unsafe_allow_html=True,
    )
