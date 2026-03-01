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
#  New helpers — duplicated from app.py to avoid circular import
# ─────────────────────────────────────────────────────────────────────────────

def _damodaran_spread(coverage: float) -> float:
    """Damodaran credit-spread lookup (mirrors app.py — no import to avoid circularity)."""
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


def _cagr_local(end_val, start_val, n_years):
    """CAGR from first to last data point.  n_years = number of elapsed years."""
    ev, sv = _s(end_val), _s(start_val)
    if ev is None or sv is None or n_years <= 0:
        return "N/M"
    if ev <= 0 or sv <= 0:
        return "N/M"
    try:
        result = (ev / sv) ** (1.0 / n_years) - 1.0
        return result if math.isfinite(result) else "N/M"
    except (ZeroDivisionError, OverflowError):
        return "N/M"


def _dec31_price(raw, year_str):
    """Return closing price closest to Dec 31 for the given year from historical_prices."""
    import datetime
    hist = raw.get("historical_prices", [])
    if not hist:
        return None
    yr = str(year_str)
    year_prices = [p for p in hist if isinstance(p, dict) and str(p.get("date", ""))[:4] == yr]
    if not year_prices:
        return None
    try:
        target = datetime.date(int(yr), 12, 31)
        closest = min(year_prices,
                      key=lambda p: abs((datetime.date.fromisoformat(str(p["date"])) - target).days))
        return _s(closest.get("adjClose") or closest.get("close"))
    except Exception:
        return None


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
    hist_disp       list[dict] — pre-formatted display rows (oldest → newest)
    ttm_disp        dict       — TTM display row
    avg_disp        dict       — Average display row
    cagr_disp       dict       — CAGR display row ((latest/earliest)^(1/(n-1))-1)
    nd_ebt_ttm      float|None — TTM Net Debt/EBITDA (for checklist)
    rev_c10         float|str|None
    ebt_c10         float|str|None
    ebt_c5          float|str|None
    ebt_avg_mult    float|None — average historical EV/EBITDA (forecast default)
    base_ebitda     float|None  — most-recent annual EBITDA
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

    # CAGR — 9-yr formula: ((Latest/Earliest)^(1/9))-1, all columns
    cagr_data = ins.get_insights_cagr()
    rev_c10 = next((r.get("10yr") for r in cagr_data if r["CAGR"] == "Revenues"), None)
    rev_c5  = next((r.get("5yr")  for r in cagr_data if r["CAGR"] == "Revenues"), None)
    ebt_c10 = next((r.get("10yr") for r in cagr_data if r["CAGR"] == "EBITDA"),   None)
    ebt_c5  = next((r.get("5yr")  for r in cagr_data if r["CAGR"] == "EBITDA"),   None)

    n_hist = len(raw_hist)
    cagr_n = min(9, n_hist - 1) if n_hist >= 2 else 0

    if cagr_n > 0:
        local_rev_cagr    = _cagr_local(raw_hist[-1]["rev"],    raw_hist[0]["rev"],    cagr_n)
        local_ebt_cagr    = _cagr_local(raw_hist[-1]["ebt"],    raw_hist[0]["ebt"],    cagr_n)
        local_mkt_cagr    = _cagr_local(raw_hist[-1]["mkt"],    raw_hist[0]["mkt"],    cagr_n)
        local_debt_cagr   = _cagr_local(raw_hist[-1]["debt"],   raw_hist[0]["debt"],   cagr_n)
        local_cash_cagr   = _cagr_local(raw_hist[-1]["cash"],   raw_hist[0]["cash"],   cagr_n)
        local_ev_cagr     = _cagr_local(raw_hist[-1]["ev"],     raw_hist[0]["ev"],     cagr_n)
        local_ev_ebt_cagr = _cagr_local(raw_hist[-1]["ev_ebt"], raw_hist[0]["ev_ebt"], cagr_n)
        local_nd_ebt_cagr = _cagr_local(raw_hist[-1]["nd_ebt"], raw_hist[0]["nd_ebt"], cagr_n)
    else:
        (local_rev_cagr, local_ebt_cagr, local_mkt_cagr, local_debt_cagr,
         local_cash_cagr, local_ev_cagr, local_ev_ebt_cagr, local_nd_ebt_cagr) = ("N/M",) * 8

    cagr_disp = {
        "Year":              f"CAGR ({cagr_n}-yr)",
        "Revenues ($MM)":    _f_pct(local_rev_cagr),
        "EBITDA ($MM)":      _f_pct(local_ebt_cagr),
        "Market Cap ($MM)":  _f_pct(local_mkt_cagr),
        "Debt ($MM)":        _f_pct(local_debt_cagr),
        "Cash ($MM)":        _f_pct(local_cash_cagr),
        "EV ($MM)":          _f_pct(local_ev_cagr),
        "EV/EBITDA":         _f_pct(local_ev_ebt_cagr),
        "Net Debt/EBITDA":   _f_pct(local_nd_ebt_cagr),
    }

    # TTM EV/EBITDA (for default exit multiple) and local CAGR (for default growth rate)
    ev_ebt_ttm_numeric = _d(ev_t, ebt_t)
    local_ebt_cagr_num = local_ebt_cagr     # float or "N/M"

    ebt_avg_mult = avg_ev_ebt
    base_ebitda  = (_s(is_l[0].get("ebitda"))
                    if is_l and isinstance(is_l[0], dict) else None)

    return (hist_disp, ttm_disp, avg_disp, cagr_disp,
            nd_ebt_t, rev_c10, ebt_c10, ebt_c5, ebt_avg_mult, base_ebitda,
            ev_ebt_ttm_numeric, local_ebt_cagr_num)


# ─────────────────────────────────────────────────────────────────────────────
#  Data builder: Adj. FCF/s Historical (Table 3.1)
# ─────────────────────────────────────────────────────────────────────────────

def _fcf_hist(norm, raw, ins):
    """
    Build display rows for Table 3.1 (Adj. FCF/s Historical).

    Returns
    -------
    hist_disp       list[dict]
    ttm_disp        dict
    avg_disp        dict
    cagr_disp       dict       — CAGR display row ((latest/earliest)^(1/(n-1))-1)
    adj_ps_ttm      float|None — TTM Adj.FCF/share (base for FCF forecast)
    fcf_c10         float|str|None
    fcf_c5          float|str|None
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
        # Use Dec 31 closing price from historical_prices; fall back to key metrics price
        px     = _dec31_price(raw, yr) or _s(rec_km.get("stockPrice"))
        yld    = _d(adj_ps, px)

        raw_hist.append({"adj_ps": adj_ps, "yld": yld,
                         "fcf": fcf, "sbc": sbc, "adj": adj, "sh": sh, "px": px})
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

    # Average row — all columns
    def _avg_col(key):
        vals = [r[key] for r in raw_hist if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    avg_disp = {
        "Year":            "Average",
        "FCF ($MM)":       _f_mm(_avg_col("fcf")),
        "SBC ($MM)":       _f_mm(_avg_col("sbc")),
        "Adj. FCF ($MM)":  _f_mm(_avg_col("adj")),
        "Shares (MM)":     _f_mm(_avg_col("sh")),
        "Adj. FCF/s":      _f_ps(_avg_col("adj_ps")),
        "Stock Price":     _f_price(_avg_col("px")),
        "Adj. FCF Yield":  _f_pct(_avg_col("yld")),
    }

    # CAGR — 9-yr formula: ((Latest/Earliest)^(1/9))-1, all columns
    cagr_data = ins.get_insights_cagr()
    fcf_c10 = next((r.get("10yr") for r in cagr_data if r["CAGR"] == "Adj. FCF"), None)
    fcf_c5  = next((r.get("5yr")  for r in cagr_data if r["CAGR"] == "Adj. FCF"), None)

    n_hist = len(raw_hist)
    cagr_n = min(9, n_hist - 1) if n_hist >= 2 else 0

    if cagr_n > 0:
        local_fcf_cagr   = _cagr_local(raw_hist[-1]["fcf"],    raw_hist[0]["fcf"],    cagr_n)
        local_sbc_cagr   = _cagr_local(raw_hist[-1]["sbc"],    raw_hist[0]["sbc"],    cagr_n)
        local_adj_cagr   = _cagr_local(raw_hist[-1]["adj"],    raw_hist[0]["adj"],    cagr_n)
        local_sh_cagr    = _cagr_local(raw_hist[-1]["sh"],     raw_hist[0]["sh"],     cagr_n)
        local_adjps_cagr = _cagr_local(raw_hist[-1]["adj_ps"], raw_hist[0]["adj_ps"], cagr_n)
        local_px_cagr    = _cagr_local(raw_hist[-1]["px"],     raw_hist[0]["px"],     cagr_n)
        local_yld_cagr   = _cagr_local(raw_hist[-1]["yld"],    raw_hist[0]["yld"],    cagr_n)
    else:
        (local_fcf_cagr, local_sbc_cagr, local_adj_cagr, local_sh_cagr,
         local_adjps_cagr, local_px_cagr, local_yld_cagr) = ("N/M",) * 7

    cagr_disp = {
        "Year":            f"CAGR ({cagr_n}-yr)",
        "FCF ($MM)":       _f_pct(local_fcf_cagr),
        "SBC ($MM)":       _f_pct(local_sbc_cagr),
        "Adj. FCF ($MM)":  _f_pct(local_adj_cagr),
        "Shares (MM)":     _f_pct(local_sh_cagr),
        "Adj. FCF/s":      _f_pct(local_adjps_cagr),
        "Stock Price":     _f_pct(local_px_cagr),
        "Adj. FCF Yield":  _f_pct(local_yld_cagr),
    }

    local_adj_cagr_num = local_adjps_cagr   # float or "N/M"

    return (hist_disp, ttm_disp, avg_disp, cagr_disp,
            adj_ps_t, fcf_c10, fcf_c5, local_adj_cagr_num)


# ─────────────────────────────────────────────────────────────────────────────
#  Forecast builders — YoY growth rate lists
# ─────────────────────────────────────────────────────────────────────────────

def _ebitda_forecast_yoy(base_ebt, growth_rates, base_year):
    """
    9-year EBITDA forecast using per-year growth rates.

    Parameters
    ----------
    growth_rates : list[float]  — YoY growth % for each of the 9 years (e.g. 8.5 for 8.5%)

    Returns list of dicts: Year, Est. Growth Rate (%), Est. EBITDA ($MM).
    Stock-price computation is handled separately in the summary table.
    """
    ebt = _s(base_ebt)
    if ebt is None:
        return []

    rows = []
    ebt_running = ebt
    for y in range(1, 10):
        g = (growth_rates[y - 1] if growth_rates and y - 1 < len(growth_rates) else 10.0) / 100.0
        ebt_running = ebt_running * (1 + g)
        rows.append({
            "Year":                 str(base_year + y),
            "Est. Growth Rate (%)": growth_rates[y - 1] if growth_rates and y - 1 < len(growth_rates) else 10.0,
            "Est. EBITDA ($MM)":    ebt_running / 1e6,
        })
    return rows


def _fcf_forecast_yoy(base_adj_ps, growth_rates, exit_yield_pct, base_year):
    """
    9-year Adj. FCF/s forecast using per-year growth rates.

    Parameters
    ----------
    exit_yield_pct : float — Exit Adj. FCF Yield as a percentage (e.g. 4.0 for 4%)

    Returns (display_rows, irr_cashflows).
    irr_cashflows[i] = FCF/s at year i+1; year 9 includes terminal value.
    """
    base = _s(base_adj_ps)
    if base is None:
        return [], []

    ey = max((exit_yield_pct or 4.0) / 100.0, 0.001)   # guard div/0

    rows = []
    irr_cashflows = []
    adj_ps = base

    for y in range(1, 10):
        g = (growth_rates[y - 1] if growth_rates and y - 1 < len(growth_rates) else 10.0) / 100.0
        adj_ps = adj_ps * (1 + g)
        if y == 9:
            terminal = adj_ps / ey
            irr_cashflows.append(adj_ps + terminal)
        else:
            irr_cashflows.append(adj_ps)
        rows.append({
            "Year":                 str(base_year + y),
            "Est. Growth Rate (%)": growth_rates[y - 1] if growth_rates and y - 1 < len(growth_rates) else 10.0,
            "Est. Adj. FCF/s":      adj_ps,
        })
    return rows, irr_cashflows


# ─────────────────────────────────────────────────────────────────────────────
#  IRR sensitivity matrix builder (yield-based)
# ─────────────────────────────────────────────────────────────────────────────

def _irr_sensitivity_yield(base_adj_ps, growth_rates, exit_yield_pct, current_price):
    """
    Build a 5×5 IRR sensitivity matrix using yield-based terminal value.
    Rows   : entry price variants (−20%, −10%, 0%, +10%, +20% of current_price)
    Columns: exit FCF yield variants (exit_yield_pct −2, −1, 0, +1, +2 pp)
    Returns (row_labels, col_labels, matrix) where matrix[i][j] is IRR float|None.
    """
    px   = _s(current_price)
    base = _s(base_adj_ps)
    ey   = exit_yield_pct or 4.0

    price_factors = [-0.20, -0.10, 0.00, 0.10, 0.20]
    yield_offsets = [-2.0,  -1.0,  0.0,  1.0,  2.0]

    row_labels = [
        f"${px * (1 + f):,.2f} ({'+' if f >= 0 else ''}{int(f * 100)}%)"
        if px else "N/A"
        for f in price_factors
    ]
    col_labels = [f"{max(ey + d, 0.1):.1f}%" for d in yield_offsets]

    matrix = []
    for pf in price_factors:
        entry = (px * (1 + pf)) if px else None
        row   = []
        for yd in yield_offsets:
            y_here = (ey + yd) / 100.0
            if base is None or entry is None or entry <= 0 or y_here <= 0.001:
                row.append(None)
                continue
            cfs   = []
            adj_ps = base
            for i in range(9):
                g = (growth_rates[i] if growth_rates and i < len(growth_rates) else 10.0) / 100.0
                adj_ps = adj_ps * (1 + g)
                if i < 8:
                    cfs.append(adj_ps)
                else:
                    terminal = adj_ps / y_here
                    cfs.append(adj_ps + terminal)
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
    w   = ins.get_wacc_components()

    # ── Build historical data ────────────────────────────────────────────────
    (ebt_hist, ebt_ttm, ebt_avg, ebt_cagr,
     nd_ebt_ttm, rev_c10, ebt_c10, ebt_c5,
     ebt_avg_mult, base_ebitda,
     ev_ebt_ttm_numeric, local_ebt_cagr_num) = _ebitda_hist(norm, raw, ins)

    (fcf_hist, fcf_ttm, fcf_avg, fcf_cagr,
     adj_ps_ttm, fcf_c10, fcf_c5, local_adj_cagr_num) = _fcf_hist(norm, raw, ins)

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

    # Use local 9-yr CAGRs as default growth rates; TTM EV/EBITDA as default exit multiple
    _ebt_g_default = _pct_default(local_ebt_cagr_num, 10.0)
    _fcf_g_default = _pct_default(local_adj_cagr_num, 10.0)
    _exit_mult_def = round(ev_ebt_ttm_numeric, 1) if ev_ebt_ttm_numeric else 15.0

    _init("cfirr_ebitda_growth_yoy",    [_ebt_g_default] * 9)
    _init("cfirr_ebitda_global_growth", _ebt_g_default)
    _init("cfirr_ebitda_exit",          _exit_mult_def)
    _init("cfirr_fcf_growth_yoy",       [_fcf_g_default] * 9)
    _init("cfirr_fcf_global_growth",    _fcf_g_default)
    _init("cfirr_fcf_exit_yield",       _fcf_g_default)
    _init("cfirr_mos",               25.0)
    _init("cfirr_wacc_override",     False)
    _init("cfirr_wacc_rf_rate",      float(st.session_state.get("treasury_rate", 0.042)))
    _init("cfirr_wacc_beta",         float(w["beta"]))
    _init("cfirr_wacc_erp",          0.046)
    _init("cfirr_show_wacc_detail",  False)

    # ── Compute WACC ─────────────────────────────────────────────────────────
    spread = _damodaran_spread(w["int_coverage"])
    rf     = st.session_state["cfirr_wacc_rf_rate"]
    beta   = st.session_state["cfirr_wacc_beta"]
    erp    = st.session_state["cfirr_wacc_erp"]
    cod    = (rf + spread) * (1 - w["tax_rate"])
    coe    = rf + beta * erp
    tc     = w["equity_val"] + w["debt_val"]
    wd     = w["debt_val"]   / tc if tc else 0.0
    we     = w["equity_val"] / tc if tc else 0.0
    wacc   = wd * cod + we * coe

    # ── Read current growth rates / exit inputs from session state ────────────
    ebt_growth_rates = list(st.session_state["cfirr_ebitda_growth_yoy"])
    exit_mult_val    = float(st.session_state.get("cfirr_ebitda_exit", 15.0))
    fcf_growth_rates = list(st.session_state["cfirr_fcf_growth_yoy"])
    exit_yield_pct   = float(st.session_state.get("cfirr_fcf_exit_yield", 10.0))

    # ── Compute forecasts from session state (for IRR & checklist at top) ────
    _ebt_fc_ss = _ebitda_forecast_yoy(base_ebitda, ebt_growth_rates, base_year)
    _fcf_fc_ss, fcf_cashflows = _fcf_forecast_yoy(
        adj_ps_ttm, fcf_growth_rates, exit_yield_pct, base_year)

    ebitda_price_ss = None
    if _ebt_fc_ss:
        _ebt_yr9_mm = _ebt_fc_ss[-1]["Est. EBITDA ($MM)"]
        if _ebt_yr9_mm is not None:
            _ev_ss = _ebt_yr9_mm * 1e6 * exit_mult_val
            ebitda_price_ss = _d(_ev_ss - net_debt_ttm, sh_ttm)

    fcf_price_ss = None
    if _fcf_fc_ss and exit_yield_pct > 0:
        _adj_yr9 = _fcf_fc_ss[-1]["Est. Adj. FCF/s"]
        if _adj_yr9 is not None:
            fcf_price_ss = _adj_yr9 / (exit_yield_pct / 100.0)

    avg_target_ss = None
    if ebitda_price_ss is not None and fcf_price_ss is not None:
        avg_target_ss = (ebitda_price_ss + fcf_price_ss) / 2.0

    # ── IRR ──────────────────────────────────────────────────────────────────
    irr_val = None
    if price_now and price_now > 0 and fcf_cashflows:
        irr_val = _irr_calc([-price_now] + fcf_cashflows)

    # ── Checklist evaluation ─────────────────────────────────────────────────
    def _check(val, threshold, lower_is_better=False):
        if isinstance(val, str):
            return val, None
        f = _s(val)
        if f is None:
            return "N/A", None
        passed = (f < threshold) if lower_is_better else (f >= threshold)
        return _f_pct(f), passed

    rev_disp, rev_p  = _check(rev_c10,      0.07)
    ebt_disp, ebt_p  = _check(ebt_c10,      0.10)
    fcf_disp, fcf_p  = _check(fcf_c10,      0.10)
    fcm_disp, fcm_p  = _check(fcf_margin_t, 0.10)
    nd_disp,  nd_p   = _check(nd_ebt_ttm,   3.0,  lower_is_better=True)
    irr_disp, irr_p  = _check(irr_val,      0.12)

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
    # GUIDANCE INFO BOX
    # ══════════════════════════════════════════════════════════════════════════
    st.info(
        "**Key Steps for Using the Model:**\n"
        "1. **Review:** Examine EV/EBITDA and Adj. FCF/s historical tables.\n"
        "2. **Forecast:** Projects stock price 10 years forward using two methods.\n"
        "3. **Weighting:** The two projections are averaged to a single target price.\n"
        "4. **Fair Value:** Discounts the average target price to today using WACC.\n"
        "5. **Investment Decision:** Compare Fair Value to current price.\n"
        "6. **IRR Calculation:** Expected IRR based on projected cash flow streams."
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — CHECKLIST & RESULT
    # ══════════════════════════════════════════════════════════════════════════
    _sec("1 · Quality Checklist")

    chk_col, badge_col = st.columns([3, 1])
    with chk_col:
        st.markdown(_checklist_html(checklist), unsafe_allow_html=True)

    with badge_col:
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # PASS / FAIL badge
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


    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — EBITDA ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    _sec("2 · EBITDA Analysis")

    # ── Table 2.1: EV/EBITDA Historical ──────────────────────────────────────
    _sub("Table 2.1 · EV/EBITDA Historical  (values in $MM unless noted)")
    all_ebt_rows = ebt_hist + [ebt_cagr, ebt_avg, ebt_ttm]
    df_ebt = pd.DataFrame(all_ebt_rows).set_index("Year")
    st.dataframe(df_ebt, use_container_width=True)

    # ── Table 2.2: EBITDA 9-Year Forecast ────────────────────────────────────
    _sub(f"Table 2.2 · EBITDA Forecast  ({base_year + 1}–{base_year + 9})")

    # Global growth rate — on_change resets all rows
    def _apply_global_ebt():
        rate = st.session_state.get("cfirr_ebitda_global_growth", 10.0)
        st.session_state["cfirr_ebitda_growth_yoy"] = [rate] * 9

    g_col2, _ = st.columns([2, 6])
    with g_col2:
        st.number_input(
            "Global Est. Growth Rate (%)",
            min_value=-50.0, max_value=200.0, step=0.5, format="%.1f",
            key="cfirr_ebitda_global_growth",
            on_change=_apply_global_ebt,
            help="Sets the growth rate for all forecast years at once.",
        )

    # Reload growth rates (may have been updated by on_change callback)
    ebt_growth_rates = list(st.session_state["cfirr_ebitda_growth_yoy"])

    ebt_fc_rows = _ebitda_forecast_yoy(base_ebitda, ebt_growth_rates, base_year)

    if ebt_fc_rows:
        # Build unified table: base row + 9 forecast rows + average row
        base_ebt_val = (base_ebitda / 1e6) if base_ebitda else float("nan")
        base_row = {"Year": str(base_year), "Est. Growth Rate (%)": float("nan"),
                    "Est. EBITDA ($MM)": base_ebt_val}
        ebt_vals = [r["Est. EBITDA ($MM)"] for r in ebt_fc_rows if r["Est. EBITDA ($MM)"] is not None]
        avg_ebt_mm = sum(ebt_vals) / len(ebt_vals) if ebt_vals else None
        avg_row = {"Year": "Average", "Est. Growth Rate (%)": float("nan"),
                   "Est. EBITDA ($MM)": avg_ebt_mm}

        ebt_all_rows = [base_row] + ebt_fc_rows + [avg_row]
        ebt_fc_df = pd.DataFrame(ebt_all_rows)

        edited_ebt_df = st.data_editor(
            ebt_fc_df,
            disabled=["Year", "Est. EBITDA ($MM)"],
            column_config={
                "Year":                 st.column_config.TextColumn("Year", width=80),
                "Est. Growth Rate (%)": st.column_config.NumberColumn(
                    "Est. Growth Rate (%)", min_value=-50.0, max_value=200.0,
                    step=0.5, format="%.1f"),
                "Est. EBITDA ($MM)":    st.column_config.NumberColumn(
                    "Est. EBITDA ($MM)", format="%.1f"),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
        )
        # Extract only the 9 forecast rows (indices 1 through 9), ignore base and average
        new_ebt_rates = edited_ebt_df["Est. Growth Rate (%)"].iloc[1:10].tolist()
        st.session_state["cfirr_ebitda_growth_yoy"] = new_ebt_rates
    else:
        new_ebt_rates = ebt_growth_rates
        st.caption("Insufficient base data to generate forecast.")

    # Recompute with final rates to get year-9 EBITDA
    ebt_fc_now = _ebitda_forecast_yoy(base_ebitda, new_ebt_rates, base_year)

    # ── EBITDA Est. Stock Price Table ─────────────────────────────────────────
    _sub("EBITDA Estimated Stock Price")

    em_col, _ = st.columns([2, 6])
    with em_col:
        st.number_input(
            "Est. EV/EBITDA Multiple",
            min_value=1.0, max_value=100.0, step=0.5, format="%.1f",
            key="cfirr_ebitda_exit",
            help="EV/EBITDA multiple at the end of the forecast. Default = TTM.",
        )
    exit_mult_now = float(st.session_state["cfirr_ebitda_exit"])

    final_yr_ebt = base_year + 9
    ebt_yr9_mm   = ebt_fc_now[-1]["Est. EBITDA ($MM)"] if ebt_fc_now else None
    ev_yr9       = (ebt_yr9_mm * 1e6 * exit_mult_now) if ebt_yr9_mm is not None else None
    debt_v       = debt_ttm or 0.0
    cash_v       = cash_ttm or 0.0
    mktcap_yr9   = (ev_yr9 - debt_v + cash_v) if ev_yr9 is not None else None
    ebitda_price_yr10 = _d(mktcap_yr9, sh_ttm)

    ebt_sum_rows = [
        ["Est. EV/EBITDA Multiple",                   f"{exit_mult_now:.1f}x"],
        [f"EV in {final_yr_ebt} ($MM)",               _f_mm(ev_yr9)],
        ["Less: Debt (TTM) ($MM)",                    _f_mm(debt_v)],
        ["Plus: Cash (TTM) ($MM)",                    _f_mm(cash_v)],
        ["Est. Market Cap ($MM)",                     _f_mm(mktcap_yr9)],
        ["Shares Outstanding — TTM (MM)",             f"{sh_ttm / 1e6:,.1f}" if sh_ttm else "N/A"],
        [f"Est. Stock Price in {final_yr_ebt}",       _f_price(ebitda_price_yr10)],
    ]
    df_ebt_sum = pd.DataFrame(ebt_sum_rows, columns=["Metric", "Value"]).set_index("Metric")
    st.dataframe(df_ebt_sum, use_container_width=True,
                 column_config={"Value": st.column_config.TextColumn("Value", width=200)})

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — FREE CASH FLOW ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    _sec("3 · Free Cash Flow Analysis")

    # ── Table 3.1: Adj. FCF/s Historical ─────────────────────────────────────
    _sub("Table 3.1 · Adj. FCF/s Historical  (values in $MM unless noted)")
    all_fcf_rows = fcf_hist + [fcf_cagr, fcf_avg, fcf_ttm]
    df_fcf = pd.DataFrame(all_fcf_rows).set_index("Year")
    st.dataframe(df_fcf, use_container_width=True)

    # ── Table 3.2: Est. Adj. FCF/s 9-Year Forecast ──────────────────────────
    _sub(f"Table 3.2 · Est. Adj. FCF/s Forecast  ({base_year + 1}–{base_year + 9})")

    # Global growth rate — on_change resets all rows
    def _apply_global_fcf():
        rate = st.session_state.get("cfirr_fcf_global_growth", 10.0)
        st.session_state["cfirr_fcf_growth_yoy"] = [rate] * 9

    fg_col2, _ = st.columns([2, 6])
    with fg_col2:
        st.number_input(
            "Global Est. Growth Rate (%)",
            min_value=-50.0, max_value=200.0, step=0.5, format="%.1f",
            key="cfirr_fcf_global_growth",
            on_change=_apply_global_fcf,
            help="Sets the growth rate for all forecast years at once.",
        )

    # Reload growth rates (may have been updated by on_change callback)
    fcf_growth_rates = list(st.session_state["cfirr_fcf_growth_yoy"])
    # Use session exit yield for cashflow calculations (updated below)
    exit_yield_now = float(st.session_state["cfirr_fcf_exit_yield"])

    fcf_fc_rows_base, _ = _fcf_forecast_yoy(
        adj_ps_ttm, fcf_growth_rates, exit_yield_now, base_year)

    if fcf_fc_rows_base:
        # Build unified table: base row + 9 forecast rows + average row
        fcf_base_row = {"Year": str(base_year), "Est. Growth Rate (%)": float("nan"),
                        "Est. Adj. FCF/s": adj_ps_ttm}
        adj_vals = [r["Est. Adj. FCF/s"] for r in fcf_fc_rows_base if r["Est. Adj. FCF/s"] is not None]
        avg_adj_ps = sum(adj_vals) / len(adj_vals) if adj_vals else None
        fcf_avg_row = {"Year": "Average", "Est. Growth Rate (%)": float("nan"),
                       "Est. Adj. FCF/s": avg_adj_ps}

        fcf_all_rows = [fcf_base_row] + fcf_fc_rows_base + [fcf_avg_row]
        fcf_fc_df_disp = pd.DataFrame(fcf_all_rows)

        edited_fcf_df = st.data_editor(
            fcf_fc_df_disp,
            disabled=["Year", "Est. Adj. FCF/s"],
            column_config={
                "Year":                 st.column_config.TextColumn("Year", width=80),
                "Est. Growth Rate (%)": st.column_config.NumberColumn(
                    "Est. Growth Rate (%)", min_value=-50.0, max_value=200.0,
                    step=0.5, format="%.1f"),
                "Est. Adj. FCF/s":      st.column_config.NumberColumn(
                    "Est. Adj. FCF/s", format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
        )
        # Extract only the 9 forecast rows (indices 1 through 9), ignore base and average
        new_fcf_rates = edited_fcf_df["Est. Growth Rate (%)"].iloc[1:10].tolist()
        st.session_state["cfirr_fcf_growth_yoy"] = new_fcf_rates
    else:
        new_fcf_rates = fcf_growth_rates
        st.caption("Insufficient base data to generate forecast.")

    # ── FCF Est. Stock Price Table ────────────────────────────────────────────
    _sub("FCF Estimated Stock Price")

    lt_col, _ = st.columns([2, 6])
    with lt_col:
        st.number_input(
            "Long Term FCF/s Yield (%)",
            min_value=0.5, max_value=50.0, step=0.5, format="%.1f",
            key="cfirr_fcf_exit_yield",
            help="Est. Stock Price = Est. Adj. FCF/s ÷ Yield.  "
                 "Default = 9-yr CAGR of Adj. FCF/s.",
        )
    exit_yield_now = float(st.session_state["cfirr_fcf_exit_yield"])

    # Recompute with final rates and current yield
    fcf_fc_now, _ = _fcf_forecast_yoy(
        adj_ps_ttm, new_fcf_rates, exit_yield_now, base_year)

    final_yr_fcf = base_year + 9
    adj_ps_yr9   = fcf_fc_now[-1]["Est. Adj. FCF/s"] if fcf_fc_now else None
    fcf_price_yr10 = _d(adj_ps_yr9, exit_yield_now / 100.0) if adj_ps_yr9 and exit_yield_now > 0 else None

    fcf_sum_rows = [
        ["Long Term FCF/s Yield",                   f"{exit_yield_now:.1f}%"],
        [f"Est. Stock Price in {final_yr_fcf}",     _f_price(fcf_price_yr10)],
    ]
    df_fcf_sum = pd.DataFrame(fcf_sum_rows, columns=["Metric", "Value"]).set_index("Metric")
    st.dataframe(df_fcf_sum, use_container_width=True,
                 column_config={"Value": st.column_config.TextColumn("Value", width=200)})

    # ══════════════════════════════════════════════════════════════════════════
    # COMPARISON TABLE
    # ══════════════════════════════════════════════════════════════════════════
    _sec("Comparison — Method 1 vs. Method 2")

    avg_target_now = None
    if ebitda_price_yr10 is not None and fcf_price_yr10 is not None:
        avg_target_now = (ebitda_price_yr10 + fcf_price_yr10) / 2.0

    comp_data = [
        {"Method": "Method 1 — EV/EBITDA",        "Est. Stock Price (Year 10)": _f_price(ebitda_price_yr10)},
        {"Method": "Method 2 — Adj. FCF/s Yield", "Est. Stock Price (Year 10)": _f_price(fcf_price_yr10)},
        {"Method": "Average Target Price",          "Est. Stock Price (Year 10)": _f_price(avg_target_now)},
    ]
    df_comp = pd.DataFrame(comp_data).set_index("Method")
    st.dataframe(df_comp, use_container_width=True,
                 column_config={
                     "Est. Stock Price (Year 10)": st.column_config.TextColumn(
                         "Est. Stock Price (Year 10)", width=200)
                 })

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — FINAL OUTPUT  (immediately after Comparison table)
    # ══════════════════════════════════════════════════════════════════════════
    _sec("5 · Final Output")

    # Editable Margin of Safety — above the summary table
    mos_inp_col, _ = st.columns([2, 6])
    with mos_inp_col:
        st.number_input(
            "Margin of Safety (%)",
            min_value=0.0, max_value=80.0, step=1.0, format="%.0f",
            key="cfirr_mos",
            help="Discount applied to Fair Value to derive the Buy Price.",
        )
    mos_pct_live = float(st.session_state.get("cfirr_mos", 25.0))

    # Compute live values
    fair_value_now = None
    buy_price_now  = None
    on_sale_now    = None
    if avg_target_now is not None and wacc is not None and wacc > -1:
        fair_value_now = avg_target_now / (1 + wacc) ** 9
        buy_price_now  = fair_value_now * (1 - mos_pct_live / 100.0)
        if price_now is not None:
            on_sale_now = price_now < buy_price_now

    def _fmt_delta(target, current):
        if target is None or current is None or current == 0:
            return "N/A"
        delta = (target / current - 1.0) * 100.0
        direction = "Upside" if delta >= 0 else "Downside"
        sign = "+" if delta >= 0 else ""
        return f"{direction}  {sign}{delta:.1f}%"

    on_sale_str = ("ON SALE" if on_sale_now is True
                   else "NOT ON SALE" if on_sale_now is False
                   else "N/A")

    final_rows = [
        ["Fair Value per share",  _f_price(fair_value_now)],
        ["Margin of Safety (%)",  f"{mos_pct_live:.0f}%"],
        ["Buy Price",             _f_price(buy_price_now)],
        ["Current Stock Price",   _f_price(price_now)],
        ["Company on Sale?",      on_sale_str],
        ["To Fair Value",         _fmt_delta(fair_value_now, price_now)],
        ["To Buy Price",          _fmt_delta(buy_price_now,  price_now)],
    ]
    df_final = pd.DataFrame(final_rows, columns=["Metric", "Value"]).set_index("Metric")
    st.dataframe(df_final, use_container_width=True,
                 column_config={"Value": st.column_config.TextColumn("Value", width=220)})

    if fair_value_now is None:
        st.warning("Fair Value requires valid estimates from both models.")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — IRR CALCULATION & SENSITIVITY
    # ══════════════════════════════════════════════════════════════════════════
    _sec("4 · IRR Calculation & Sensitivity")

    # Use the session-state cashflows (irr_val was computed at top)
    _sub("IRR Cash Flow Schedule")
    if price_now and fcf_cashflows:
        irr_rows = [{"Year": "0 (Entry)", "Cash Flow": _f_price(-price_now),
                     "Note": "Entry — Current Market Price"}]
        for idx, cf in enumerate(fcf_cashflows, start=1):
            note = "Adj. FCF/s" if idx < len(fcf_cashflows) else "Adj. FCF/s + Terminal Value (Stock Price)"
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
    _sub("IRR Sensitivity  (Entry Price vs. Exit FCF Yield)")
    if price_now and adj_ps_ttm:
        row_lbl, col_lbl, matrix = _irr_sensitivity_yield(
            adj_ps_ttm,
            st.session_state["cfirr_fcf_growth_yoy"],
            st.session_state["cfirr_fcf_exit_yield"],
            price_now,
        )
        st.markdown(_sensitivity_html(row_lbl, col_lbl, matrix),
                    unsafe_allow_html=True)
        st.caption("Green ≥ 12% · Amber 8–12% · Red < 8%   |   Columns = Exit FCF Yield variants (±2pp)")
    else:
        st.caption("Insufficient data for sensitivity analysis.")

