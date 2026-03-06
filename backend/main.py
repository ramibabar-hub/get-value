"""
backend/main.py
FastAPI "Brain" — serves financial valuation data to any frontend.

Endpoints
---------
GET /api/normalized-pe/{ticker}       Phil Town Rule #1 valuation
GET /api/overview/{ticker}            Company profile + 15-cell metric grid
GET /api/financials/{ticker}          Income Statement + Balance Sheet + Cash Flow
GET /api/insights/{ticker}            7 insight groups (CAGR / Valuation / Profitability / ...)
GET /api/routing-info/{ticker}        Debug: data-source routing info
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agents.core_agent import DataNormalizer
from agents.profile_agent import ProfileAgent
from agents.insights_agent import InsightsAgent
from backend.services.gateway import SmartGateway
from backend.logic_engine import compute_normalized_pe


# ─────────────────────────────────────────────────────────────────────────────
#  App setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="getValue API",
    description=(
        "Financial analysis backend with Smart Gateway (FMP + EODHD). "
        "US stocks use FMP; international stocks use EODHD with cross-source fallback."
    ),
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_gw = SmartGateway()


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _strip_nan(v):
    """Replace float NaN/Inf with None so JSON serialisation never chokes."""
    if v is None:
        return None
    try:
        import math
        f = float(v)
        return None if not math.isfinite(f) else f
    except (TypeError, ValueError):
        return v   # keep strings like "N/M" unchanged


def _clean_rows(rows: list[dict], real_cols: list[str]) -> list[dict]:
    """Serialize a list of DataNormalizer rows, keeping only real_cols."""
    out = []
    for row in rows:
        entry = {"label": row.get("label", "")}
        for col in real_cols:
            entry[col] = _strip_nan(row.get(col))
        out.append(entry)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/normalized-pe/{ticker}", summary="Phil Town Rule #1 – Normalized PE valuation", tags=["Valuation"])
def normalized_pe(
    ticker:     str,
    growth_pct: float | None = Query(default=None),
    years:      int   | None = Query(default=None),
    disc_pct:   float | None = Query(default=None),
    mos_pct:    float | None = Query(default=None),
    use_wacc:   bool         = Query(default=False),
):
    ticker = ticker.strip().upper()
    try:
        raw_data = _gw.fetch_all(ticker)
        overview = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    if not raw_data.get("annual_income_statement") and \
       not raw_data.get("quarterly_income_statement"):
        raise HTTPException(status_code=404, detail=f"No financial data found for '{ticker}'.")

    norm   = DataNormalizer(raw_data, ticker)
    params: dict = {"use_wacc": use_wacc}
    if growth_pct is not None: params["growth_pct"] = growth_pct
    if years      is not None: params["years"]       = years
    if disc_pct   is not None: params["disc_pct"]    = disc_pct
    if mos_pct    is not None: params["mos_pct"]     = mos_pct

    try:
        result = compute_normalized_pe(norm.raw_data, overview, params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Computation failed: {exc}")

    return {"ticker": ticker, "data_source": raw_data.get("_source", "unknown"), **result}


@app.get("/api/routing-info/{ticker}", summary="Data-source routing info", tags=["Meta"])
def routing_info(ticker: str):
    return _gw.routing_info(ticker.strip())


@app.get("/api/overview/{ticker}", summary="Company profile + 15-cell metric grid", tags=["Profile"])
def overview(ticker: str):
    """Identity fields + pre-formatted ProfileAgent metric grid (rows[3:])."""
    ticker = ticker.strip().upper()
    try:
        ov = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Overview fetch failed: {exc}")

    try:
        price = float(ov.get("price") or 0)
        chg   = float(str(ov.get("changesPercentage", 0) or 0).replace("%", "").strip())
    except (TypeError, ValueError):
        price, chg = 0.0, 0.0

    agent    = ProfileAgent(ov)
    all_rows = agent.get_rows()          # 18 rows; [0]=Ticker [1]=Name [2]=Price [3:]=15 metrics

    return {
        "ticker":           ticker,
        "company_name":     ov.get("companyName", ticker),
        "logo_url":         ov.get("image", ""),
        "exchange":         ov.get("exchangeShortName") or ov.get("exchange", ""),
        "sector":           ov.get("sector", ""),
        "industry":         ov.get("industry", ""),
        "currency":         ov.get("currency", "USD"),
        "country":          ov.get("country", ""),
        "flag":             agent.get_flag(),
        "description":      ov.get("description", ""),
        "price":            price,
        "price_change_pct": chg,
        "data_source":      ov.get("_source", "unknown"),
        "metrics": [
            {"label": r["label"], "value": r["value"], "color": r.get("color")}
            for r in all_rows[3:]
        ],
    }


@app.get("/api/financials/{ticker}", summary="Income Statement + Balance Sheet + Cash Flow", tags=["Financials"])
def financials(
    ticker: str,
    period: str = Query(default="annual", description="'annual' or 'quarterly'"),
):
    """
    Returns all three financial statement tables with raw numeric values.
    The frontend handles Scale (K / MM / B) formatting.
    Padding columns (N/A-*) are stripped.
    """
    ticker = ticker.strip().upper()
    p = "annual" if period.lower() == "annual" else "quarterly"

    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    if not raw_data.get("annual_income_statement") and \
       not raw_data.get("quarterly_income_statement"):
        raise HTTPException(status_code=404, detail=f"No financial data found for '{ticker}'.")

    norm        = DataNormalizer(raw_data, ticker)
    all_headers = norm.get_column_headers(p)
    real_cols   = ["TTM"] + [h for h in all_headers[2:] if not h.startswith("N/A-")]

    return {
        "ticker":           ticker,
        "period":           p,
        "currency":         ov.get("currency", "USD"),
        "columns":          real_cols,
        "income_statement": _clean_rows(norm.get_income_statement(p), real_cols),
        "balance_sheet":    _clean_rows(norm.get_balance_sheet(p),    real_cols),
        "cash_flow":        _clean_rows(norm.get_cash_flow(p),        real_cols),
        "debt":             _clean_rows(norm.get_debt_table(p),       real_cols),
    }


@app.get("/api/insights/{ticker}", summary="7 insight groups (CAGR, Valuation, Profitability, …)", tags=["Insights"])
def insights(ticker: str):
    """
    Returns 7 insight groups, each as { title, cols, is_pct, rows[] }.
    Rows use the label as the first field, then each column as a numeric value.
    'N/M' strings are preserved for invalid CAGR inputs.
    """
    ticker = ticker.strip().upper()
    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    ins = InsightsAgent(raw_data, ov)

    CAGR_COLS = ["3yr", "5yr", "10yr"]
    INS_COLS  = ["TTM", "Avg. 5yr", "Avg. 10yr"]

    def norm_rows(rows: list[dict], label_key: str, cols: list[str]) -> list[dict]:
        out = []
        for r in rows:
            entry: dict = {"label": str(r.get(label_key, ""))}
            for c in cols:
                v = r.get(c)
                # preserve "N/M" strings; strip nan/inf from numeric values
                entry[c] = v if isinstance(v, str) else _strip_nan(v)
            out.append(entry)
        return out

    groups = [
        {"title": "Growth (CAGR)",       "cols": CAGR_COLS, "is_pct": True,
         "rows": norm_rows(ins.get_insights_cagr(),           "CAGR",         CAGR_COLS)},
        {"title": "Valuation Multiples", "cols": INS_COLS,  "is_pct": False,
         "rows": norm_rows(ins.get_insights_valuation(),      "Valuation",    INS_COLS)},
        {"title": "Profitability",       "cols": INS_COLS,  "is_pct": True,
         "rows": norm_rows(ins.get_insights_profitability(),  "Profitability",INS_COLS)},
        {"title": "Returns Analysis",    "cols": INS_COLS,  "is_pct": True,
         "rows": norm_rows(ins.get_insights_returns(),        "Returns",      INS_COLS)},
        {"title": "Liquidity",           "cols": INS_COLS,  "is_pct": False,
         "rows": norm_rows(ins.get_insights_liquidity(),      "Liquidity",    INS_COLS)},
        {"title": "Dividends",           "cols": INS_COLS,  "is_pct": True,
         "rows": norm_rows(ins.get_insights_dividends(),      "Dividends",    INS_COLS)},
        {"title": "Efficiency",          "cols": INS_COLS,  "is_pct": False,
         "rows": norm_rows(ins.get_insights_efficiency(),     "Efficiency",   INS_COLS)},
    ]

    return {"ticker": ticker, "groups": groups}


@app.get("/api/wacc/{ticker}", summary="WACC components + computed WACC", tags=["Insights"])
def wacc_endpoint(ticker: str):
    """
    Returns WACC components (beta, cost of equity/debt, weights, tax rate, coverage)
    plus the final computed WACC value.
    """
    ticker = ticker.strip().upper()
    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    from backend.logic_engine import compute_wacc, damodaran_spread

    ins = InsightsAgent(raw_data, ov)
    w   = ins.get_wacc_components()

    rf     = 0.042
    spread = damodaran_spread(w["int_coverage"])
    cod_pre  = rf + spread
    cod_post = cod_pre * (1 - w["tax_rate"])
    coe      = rf + w["beta"] * 0.046
    tc       = w["equity_val"] + w["debt_val"]
    e_wt     = (w["equity_val"] / tc) if tc else 1.0
    d_wt     = (w["debt_val"]   / tc) if tc else 0.0

    try:
        wacc_val = compute_wacc(raw_data, ov, rf)
    except Exception:
        wacc_val = e_wt * coe + d_wt * cod_post

    return {
        "ticker":               ticker,
        "wacc":                 _strip_nan(wacc_val),
        "rf":                   rf,
        "beta":                 _strip_nan(w["beta"]),
        "equity_weight":        _strip_nan(e_wt),
        "debt_weight":          _strip_nan(d_wt),
        "cost_of_equity":       _strip_nan(coe),
        "cost_of_debt_pre_tax": _strip_nan(cod_pre),
        "cost_of_debt_after_tax": _strip_nan(cod_post),
        "tax_rate":             _strip_nan(w["tax_rate"]),
        "int_coverage":         _strip_nan(w["int_coverage"]),
        "spread":               _strip_nan(spread),
    }


@app.get("/api/financials-extended/{ticker}", summary="Market & Valuation + 6 metric groups", tags=["Financials"])
def financials_extended(
    ticker: str,
    period: str = Query(default="annual", description="'annual' or 'quarterly'"),
):
    """
    Returns Market & Valuation, Capital Structure, Profitability (abs),
    Returns, Liquidity, Dividends, Efficiency tables.
    Each row includes a 'fmt' field ('money'|'pct'|'ratio'|'days'|'int').
    """
    ticker = ticker.strip().upper()
    p = "annual" if period.lower() == "annual" else "quarterly"

    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    # Late import to avoid streamlit at module-load time
    try:
        from financials_tab import FinancialExtras
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"FinancialExtras import failed: {exc}")

    norm     = DataNormalizer(raw_data, ticker)
    hdrs     = norm.get_column_headers(p)
    real_cols_ext = [h for h in hdrs[2:] if not h.startswith("N/A-")]
    real_cols = ["TTM"] + real_cols_ext

    def _clean_ext(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            entry: dict = {"label": r.get("label", ""), "fmt": r.get("_fmt", "ratio")}
            for col in real_cols:
                v = r.get(col)
                entry[col] = v if isinstance(v, str) else _strip_nan(v)
            out.append(entry)
        return out

    try:
        ext = FinancialExtras(norm, ov)
        market_val  = ext.get_market_valuation(hdrs, p)
        cap_struct  = ext.get_capital_structure(hdrs, p)
        profitab    = ext.get_profitability(hdrs, p)
        returns     = ext.get_returns(hdrs, p)
        liquidity   = ext.get_liquidity(hdrs, p)
        dividends   = ext.get_dividends(hdrs, p)
        efficiency  = ext.get_efficiency(hdrs, p)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Computation failed: {exc}")

    return {
        "ticker":           ticker,
        "period":           p,
        "columns":          real_cols,
        "market_valuation": _clean_ext(market_val),
        "capital_structure":_clean_ext(cap_struct),
        "profitability":    _clean_ext(profitab),
        "returns":          _clean_ext(returns),
        "liquidity":        _clean_ext(liquidity),
        "dividends":        _clean_ext(dividends),
        "efficiency":       _clean_ext(efficiency),
    }


@app.get("/api/cf-irr/{ticker}", summary="CF + IRR valuation model", tags=["Valuation"])
def cf_irr(
    ticker:        str,
    ebt_growth:    str   = Query(default="5,5,5,5,5,5,5,5,5", description="9 EBITDA growth rates (%) comma-separated"),
    exit_mult:     float = Query(default=15.0),
    fcf_growth:    str   = Query(default="5,5,5,5,5,5,5,5,5", description="9 FCF growth rates (%) comma-separated"),
    exit_yield:    float = Query(default=5.0,  description="Exit FCF yield (%)"),
    mos_pct:       float = Query(default=10.0, description="Margin of safety (%)"),
    wacc_override: float | None = Query(default=None, description="Manual WACC override (%)"),
):
    """
    Returns historical EV/EBITDA and Adj.FCF/s tables plus the full 9-year
    forecasts, IRR calculation, quality checklist, and final output table.
    """
    ticker = ticker.strip().upper()

    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    try:
        from cf_irr_tab import (
            _ebitda_hist, _fcf_hist,
            _ebitda_forecast_yoy, _fcf_forecast_yoy,
            _irr_calc, _irr_sensitivity_yield,
            _ttm_bs, _ttm_flow, _s,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"cf_irr_tab import failed: {exc}")

    # Parse growth-rate arrays
    def _parse_rates(s: str, default: float = 5.0) -> list[float]:
        try:
            rates = [float(x) for x in s.split(",")]
            while len(rates) < 9:
                rates.append(default)
            return rates[:9]
        except Exception:
            return [default] * 9

    ebt_rates = _parse_rates(ebt_growth, 5.0)
    fcf_rates = _parse_rates(fcf_growth, 5.0)

    norm = DataNormalizer(raw_data, ticker)
    ins  = InsightsAgent(raw_data, ov)

    # Compute WACC
    try:
        from backend.logic_engine import compute_wacc, damodaran_spread
        wacc_computed = compute_wacc(raw_data, ov)
    except Exception:
        wacc_computed = 0.10

    wacc_val = (wacc_override / 100.0) if wacc_override is not None else wacc_computed

    # Historical tables
    (ebt_hist, ebt_ttm, ebt_avg, ebt_cagr,
     nd_ebt_ttm, rev_c10, ebt_c10, ebt_c5,
     ebt_avg_mult, base_ebitda,
     ev_ebt_ttm_numeric, local_ebt_cagr_num,
     local_rev_cagr_num) = _ebitda_hist(norm, ov, ins)

    (fcf_hist, fcf_ttm, fcf_avg, fcf_cagr,
     adj_ps_ttm, fcf_c10, fcf_c5,
     local_adj_cagr_num,
     local_fcf_cagr_num) = _fcf_hist(norm, ov, ins)

    # Defaults for exit multiple
    if exit_mult == 15.0 and ev_ebt_ttm_numeric:
        exit_mult = round(ev_ebt_ttm_numeric, 1)

    # Base year
    base_year = 2024
    if norm.is_l and isinstance(norm.is_l[0], dict):
        try:
            from cf_irr_tab import _year_label
            base_year = int(_year_label(norm.is_l[0]))
        except Exception:
            pass

    # Balance sheet TTM values
    debt_ttm    = _ttm_bs(norm.q_bs, "totalDebt") or 0.0
    cash_ttm    = _ttm_bs(norm.q_bs, "cashAndCashEquivalents") or 0.0
    net_debt_ttm = debt_ttm - cash_ttm
    sh_ttm = (_ttm_flow(norm.q_is, "weightedAverageShsOutDil")
              or _ttm_flow(norm.q_is, "weightedAverageShsOut"))
    price_now = _s(ov.get("price"))

    # EBITDA forecast
    ebt_fc = _ebitda_forecast_yoy(base_ebitda, ebt_rates, base_year)
    ebt_yr9_mm = ebt_fc[-1]["Est. EBITDA ($MM)"] if ebt_fc else None
    ev_yr9 = (ebt_yr9_mm * 1e6 * exit_mult) if ebt_yr9_mm is not None else None
    mktcap_yr9 = (ev_yr9 - net_debt_ttm) if ev_yr9 is not None else None
    ebitda_price = _s(mktcap_yr9 / sh_ttm) if (mktcap_yr9 is not None and sh_ttm) else None

    # FCF forecast + IRR cashflows
    fcf_fc, fcf_cashflows = _fcf_forecast_yoy(adj_ps_ttm, fcf_rates, exit_yield, base_year)
    fcf_yr9 = fcf_fc[-1]["Est. Adj. FCF/s"] if fcf_fc else None
    fcf_price = _s(fcf_yr9 / (exit_yield / 100.0)) if (fcf_yr9 and exit_yield > 0) else None

    # Average target
    avg_target = None
    if ebitda_price is not None and fcf_price is not None:
        avg_target = (ebitda_price + fcf_price) / 2.0
    elif ebitda_price is not None:
        avg_target = ebitda_price
    elif fcf_price is not None:
        avg_target = fcf_price

    # Fair value & buy price
    fair_value = None
    buy_price  = None
    if avg_target is not None and wacc_val > 0:
        fair_value = avg_target / (1 + wacc_val) ** 9
        buy_price  = fair_value * (1 - mos_pct / 100.0)
    on_sale = (fair_value > price_now) if (fair_value is not None and price_now) else None

    # IRR
    irr_val = None
    if price_now and price_now > 0 and fcf_cashflows:
        irr_val = _irr_calc([-price_now] + fcf_cashflows)

    # IRR sensitivity matrix
    row_lbls, col_lbls, matrix = _irr_sensitivity_yield(
        adj_ps_ttm, fcf_rates, exit_yield, price_now)

    # Checklist
    def _chk_float(v, threshold, lower=False):
        f = _s(v)
        if f is None or isinstance(v, str):
            return {"value": "N/A", "display": "N/A", "passed": None}
        passed = (f < threshold) if lower else (f >= threshold)
        return {"value": f, "display": f"{f * 100:.1f}%" if not lower else f"{f:.2f}x", "passed": passed}

    checklist = [
        {"label": "Revenue Growth (10yr CAGR)", "threshold": "> 7%",  **_chk_float(local_rev_cagr_num, 0.07)},
        {"label": "EBITDA Growth (10yr CAGR)",  "threshold": "> 10%", **_chk_float(local_ebt_cagr_num, 0.10)},
        {"label": "FCF Growth (10yr CAGR)",     "threshold": "> 10%", **_chk_float(local_fcf_cagr_num, 0.10)},
        {"label": "Net Debt / EBITDA (TTM)",    "threshold": "< 3x",
         **{**_chk_float(nd_ebt_ttm, 3.0, lower=True),
            "display": f"{nd_ebt_ttm:.2f}x" if isinstance(nd_ebt_ttm, (int, float)) else "N/A"}},
        {"label": "IRR",                        "threshold": "> 12%", **_chk_float(irr_val, 0.12)},
    ]

    def _row_clean(r: dict) -> dict:
        return {k: (v if isinstance(v, str) else _strip_nan(v)) for k, v in r.items()}

    return {
        "ticker":          ticker,
        "base_year":       base_year,
        "price_now":       _strip_nan(price_now),
        "wacc":            _strip_nan(wacc_val),
        "wacc_computed":   _strip_nan(wacc_computed),
        "adj_ps_ttm":      _strip_nan(adj_ps_ttm),
        "base_ebitda":     _strip_nan(base_ebitda),
        "net_debt_ttm":    _strip_nan(net_debt_ttm),
        "sh_ttm":          _strip_nan(sh_ttm),
        "exit_mult":       exit_mult,
        "exit_yield":      exit_yield,
        "mos_pct":         mos_pct,
        "ebt_hist":        [_row_clean(r) for r in ebt_hist],
        "ebt_ttm":         _row_clean(ebt_ttm),
        "ebt_avg":         _row_clean(ebt_avg),
        "ebt_cagr":        _row_clean(ebt_cagr),
        "fcf_hist":        [_row_clean(r) for r in fcf_hist],
        "fcf_ttm":         _row_clean(fcf_ttm),
        "fcf_avg":         _row_clean(fcf_avg),
        "fcf_cagr":        _row_clean(fcf_cagr),
        "ebt_forecast":    [_row_clean(r) for r in ebt_fc],
        "fcf_forecast":    [_row_clean(r) for r in fcf_fc],
        "ebt_growth_rates": ebt_rates,
        "fcf_growth_rates": fcf_rates,
        "ebitda_price":    _strip_nan(ebitda_price),
        "fcf_price":       _strip_nan(fcf_price),
        "avg_target":      _strip_nan(avg_target),
        "fair_value":      _strip_nan(fair_value),
        "buy_price":       _strip_nan(buy_price),
        "on_sale":         on_sale,
        "irr":             _strip_nan(irr_val),
        "irr_sensitivity": {
            "row_labels": row_lbls,
            "col_labels": col_lbls,
            "matrix":     [[_strip_nan(v) for v in row] for row in matrix],
        },
        "checklist":       checklist,
        "ev_ebt_ttm":      _strip_nan(ev_ebt_ttm_numeric),
        "ebt_avg_mult":    _strip_nan(ebt_avg_mult),
    }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": app.version}
