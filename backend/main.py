"""
backend/main.py
FastAPI "Brain" — serves financial valuation data to any frontend.

Run locally:
    python -m uvicorn backend.main:app --reload --port 8000

Endpoints
---------
GET /api/normalized-pe/{ticker}
    Phil Town Rule #1 Normalized PE valuation.
    Optional query params: growth_pct, years, disc_pct, mos_pct, use_wacc.

GET /api/routing-info/{ticker}
    Returns which data source (FMP / EODHD) will be used for this ticker.
"""

import os
import sys

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agents.core_agent import DataNormalizer
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
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
#  Shared gateway instance (one per worker process)
# ─────────────────────────────────────────────────────────────────────────────

_gw = SmartGateway()


# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/normalized-pe/{ticker}",
    summary="Phil Town Rule #1 – Normalized PE valuation",
    tags=["Valuation"],
)
def normalized_pe(
    ticker:     str,
    growth_pct: float | None = Query(default=None, description="Annual EPS growth rate (%). Default: avg of 3/5/10-yr EPS CAGRs."),
    years:      int   | None = Query(default=None, description="Forecast horizon in years. Default: 7."),
    disc_pct:   float | None = Query(default=None, description="Discount / hurdle rate (%). Default: 15.0."),
    mos_pct:    float | None = Query(default=None, description="Margin of safety (%). Default: 15.0."),
    use_wacc:   bool         = Query(default=False, description="Use model-computed WACC instead of disc_pct."),
):
    """
    Normalized PE valuation for *ticker* using Phil Town's Rule #1.

    Data is fetched via the **Smart Gateway**:
    - US tickers  → FMP primary, EODHD fallback
    - Intl tickers → EODHD primary, FMP fallback

    All query parameters are optional — omit any to use the model default.
    """
    ticker = ticker.strip().upper()

    try:
        raw_data = _gw.fetch_all(ticker)
        overview = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    if not raw_data.get("annual_income_statement") and \
       not raw_data.get("quarterly_income_statement"):
        raise HTTPException(status_code=404,
                            detail=f"No financial data found for '{ticker}'.")

    norm = DataNormalizer(raw_data, ticker)

    params: dict = {"use_wacc": use_wacc}
    if growth_pct is not None: params["growth_pct"] = growth_pct
    if years      is not None: params["years"]       = years
    if disc_pct   is not None: params["disc_pct"]    = disc_pct
    if mos_pct    is not None: params["mos_pct"]     = mos_pct

    try:
        result = compute_normalized_pe(norm.raw_data, overview, params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Computation failed: {exc}")

    return {
        "ticker":       ticker,
        "data_source":  raw_data.get("_source", "unknown"),
        **result,
    }


@app.get(
    "/api/routing-info/{ticker}",
    summary="Show which data source will be used for a ticker",
    tags=["Meta"],
)
def routing_info(ticker: str):
    """
    Returns routing metadata without fetching any data.
    Useful for debugging or displaying the data source to the user.
    """
    return _gw.routing_info(ticker.strip())


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": app.version}
