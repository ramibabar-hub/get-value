"""
backend/logic_engine.py
Pure-Python computation engine — no Streamlit, no HTTP, no side-effects.

Functions here are framework-agnostic and can be called by:
  • Streamlit widgets  (normalized_pe_tab.py)
  • FastAPI endpoints  (backend/main.py)
  • CLI scripts / unit tests
"""

import math
import os
import sys

# Make the workspace root importable when this module is run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.insights_agent import InsightsAgent


# ─────────────────────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _s(v):
    """Safe float coercion — returns None on invalid / non-finite values."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  WACC helpers  (public — reusable by other logic modules)
# ─────────────────────────────────────────────────────────────────────────────

def damodaran_spread(coverage: float) -> float:
    """Damodaran interest-coverage -> credit-spread lookup table."""
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


def compute_wacc(raw_data: dict, overview: dict, rf: float = 0.042) -> float:
    """
    Compute WACC (Damodaran credit-spread + CAPM).

    Parameters
    ----------
    raw_data : dict   from GatewayAgent.fetch_all()
    overview : dict   from GatewayAgent.fetch_overview()
    rf       : float  risk-free rate as a decimal (default: 4.2 %)

    Returns
    -------
    float : WACC as a decimal (e.g. 0.09 == 9 %)
    """
    ins    = InsightsAgent(raw_data, overview)
    w      = ins.get_wacc_components()
    spread = damodaran_spread(w["int_coverage"])
    cod    = (rf + spread) * (1 - w["tax_rate"])          # cost of debt (after-tax)
    coe    = rf + w["beta"] * 0.046                        # cost of equity (CAPM, ERP = 4.6 %)
    tc     = w["equity_val"] + w["debt_val"]
    if tc:
        return w["debt_val"] / tc * cod + w["equity_val"] / tc * coe
    return coe


# ─────────────────────────────────────────────────────────────────────────────
#  Normalised PE — Phil Town Rule #1
# ─────────────────────────────────────────────────────────────────────────────

def compute_normalized_pe(
    raw_data: dict,
    overview: dict,
    params:   dict  | None = None,
    rf:       float        = 0.042,
) -> dict:
    """
    Phil Town Rule #1 – Normalized PE valuation engine.

    Parameters
    ----------
    raw_data : dict   from GatewayAgent.fetch_all()
    overview : dict   from GatewayAgent.fetch_overview()
    params   : dict   optional user overrides (any key may be None / omitted):
                        growth_pct  float  annual EPS growth rate (%)
                        years       int    forecast horizon
                        disc_pct    float  discount rate (%)
                        mos_pct     float  margin of safety (%)
                        use_wacc    bool   replace disc_pct with WACC
    rf       : float  risk-free rate, decimal (default 4.2 %)

    Returns
    -------
    dict with keys:

      # ── source data ───────────────────────────────────────────────────────
      eps_ttm        float | None
      eps_3yr        float | "N/M" | None    (fractional CAGR)
      eps_5yr        float | "N/M" | None
      eps_10yr       float | "N/M" | None
      hist_pe_10yr   float | None
      price_now      float | None
      wacc           float              (decimal)
      growth_default float              (%, auto-detected from EPS CAGRs)

      # ── resolved inputs (effective values used in the calculation) ────────
      growth_pct     float  (%)
      years          int
      disc_pct       float  (%)   effective rate (= WACC % when use_wacc=True)
      mos_pct        float  (%)
      use_wacc       bool

      # ── computed valuation ────────────────────────────────────────────────
      future_eps     float | None
      discounted_eps float | None
      pe_a           float              (2 × growth_pct)
      pe_b           float | None       (10-yr historical avg PE)
      pe_c           float | None       (MIN of valid pe_a / pe_b)
      fair_value     float | None
      buy_price      float | None
      on_sale        bool  | None
      upside_to_fv   float | None       (fraction, e.g. 0.25 = +25 %)
      upside_to_buy  float | None       (fraction)
    """
    params = params or {}

    ins = InsightsAgent(raw_data, overview)

    # ── Source data ───────────────────────────────────────────────────────────
    eps_ttm = ins._ttm_flow(ins.q_is, "epsDiluted")

    cagr_rows    = ins.get_insights_cagr()
    eps_cagr_row = next((r for r in cagr_rows if r.get("CAGR") == "EPS Diluted"), {})
    eps_3yr      = eps_cagr_row.get("3yr")
    eps_5yr      = eps_cagr_row.get("5yr")
    eps_10yr     = eps_cagr_row.get("10yr")

    val_rows     = ins.get_insights_valuation()
    pe_vrow      = next((r for r in val_rows if r.get("Valuation") == "P/E"), {})
    hist_pe_10yr = _s(pe_vrow.get("Avg. 10yr"))

    price_now = _s(ins.ov.get("price"))

    # ── WACC ──────────────────────────────────────────────────────────────────
    wacc = compute_wacc(raw_data, overview, rf=rf)

    # ── Default growth: average of valid 3 / 5 / 10-yr EPS CAGRs ─────────────
    def _valid_pct(v):
        return round(v * 100, 2) if (isinstance(v, float) and math.isfinite(v) and v > 0) else None

    valid_gs       = [c for c in [_valid_pct(eps_3yr), _valid_pct(eps_5yr), _valid_pct(eps_10yr)]
                      if c is not None]
    growth_default = round(sum(valid_gs) / len(valid_gs), 2) if valid_gs else 10.0
    growth_default = min(growth_default, 30.0)

    # ── Resolve inputs — None -> fall back to model defaults ──────────────────
    use_wacc   = bool(params.get("use_wacc", False))

    _gp = params.get("growth_pct")
    growth_pct = float(_gp) if _gp is not None else growth_default

    _yr = params.get("years")
    years = int(_yr) if _yr is not None else 7

    _mp = params.get("mos_pct")
    mos_pct = float(_mp) if _mp is not None else 15.0

    _dp = params.get("disc_pct")
    disc_pct = (wacc * 100) if use_wacc else (float(_dp) if _dp is not None else 15.0)

    # ── Calculations ──────────────────────────────────────────────────────────
    g              = growth_pct / 100
    disc           = disc_pct  / 100

    future_eps     = (eps_ttm * (1 + g) ** years)       if eps_ttm is not None else None
    discounted_eps = (future_eps / (1 + disc) ** years)  if future_eps is not None else None

    pe_a   = growth_pct * 2                                    # (a) 2 × growth rate
    pe_b   = hist_pe_10yr                                      # (b) 10-yr historical avg PE
    cands  = [x for x in [pe_a, pe_b] if x is not None and x > 0]
    pe_c   = min(cands) if cands else None                     # (c) Conservative PE = MIN(a, b)

    fair_value = (discounted_eps * pe_c)            if (discounted_eps is not None and pe_c is not None) else None
    buy_price  = (fair_value * (1 - mos_pct / 100)) if fair_value  is not None else None

    on_sale = (
        (price_now < buy_price)
        if (price_now is not None and buy_price is not None)
        else None
    )

    def _upside(target, current):
        if target is None or current is None or current == 0:
            return None
        return (target / current) - 1

    return {
        # source data
        "eps_ttm":        eps_ttm,
        "eps_3yr":        eps_3yr,
        "eps_5yr":        eps_5yr,
        "eps_10yr":       eps_10yr,
        "hist_pe_10yr":   hist_pe_10yr,
        "price_now":      price_now,
        "wacc":           wacc,
        "growth_default": growth_default,
        # resolved inputs
        "growth_pct":     growth_pct,
        "years":          years,
        "disc_pct":       disc_pct,
        "mos_pct":        mos_pct,
        "use_wacc":       use_wacc,
        # computed
        "future_eps":     future_eps,
        "discounted_eps": discounted_eps,
        "pe_a":           pe_a,
        "pe_b":           pe_b,
        "pe_c":           pe_c,
        "fair_value":     fair_value,
        "buy_price":      buy_price,
        "on_sale":        on_sale,
        "upside_to_fv":   _upside(fair_value, price_now),
        "upside_to_buy":  _upside(buy_price,  price_now),
    }
