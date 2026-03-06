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


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": app.version}
