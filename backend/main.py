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

import datetime
import concurrent.futures as _cf
from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel

# Shared executor for lightweight background fetches (e.g. chart prices).
# Not shut down per-request — avoids blocking on thread completion after timeout.
_bg_executor = _cf.ThreadPoolExecutor(max_workers=4, thread_name_prefix="bg_fetch")
from typing import Any
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
#  REIT helpers
# ─────────────────────────────────────────────────────────────────────────────

import math as _math

def _sf(v):
    """Safe float coercion."""
    if v is None: return None
    try:
        f = float(v)
        return f if _math.isfinite(f) else None
    except Exception:
        return None


def _ssum(recs, key):
    """Sum all finite numeric values for key across a list of dicts."""
    vals = [_sf(r.get(key)) for r in recs if isinstance(r, dict)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


# Industries that trigger REIT-specific metrics
_REIT_INDUSTRIES: frozenset = frozenset({
    "REIT—Residential", "REIT—Office", "REIT—Retail",
    "REIT—Industrial", "REIT—Healthcare Facilities",
    "REIT—Hotel & Motel", "REIT—Specialty", "REIT—Diversified",
    "Real Estate—Development", "Real Estate Services",
    "Real Estate—Diversified", "Residential Construction",
    # FMP uses em-dash or regular dash; include both
    "REIT - Residential", "REIT - Office", "REIT - Retail",
    "REIT - Industrial", "REIT - Healthcare Facilities",
    "REIT - Hotel & Motel", "REIT - Specialty", "REIT - Diversified",
    "Real Estate - Development", "Real Estate - Diversified",
})


def _is_reit(ov: dict) -> bool:
    """Return True when the company is a REIT / Real-Estate entity."""
    industry = str(ov.get("industry") or "").strip()
    if industry in _REIT_INDUSTRIES:
        return True
    # Broad fallback: any industry containing "REIT" or "Real Estate"
    il = industry.lower()
    return "reit" in il or "real estate" in il


def _reit_da(is_recs: list, cf_recs: list):
    """D&A: from CF records first; fall back to EBITDA − operatingIncome."""
    da = _ssum(cf_recs, "depreciationAndAmortization")
    if da:
        return da
    ebit = _ssum(is_recs, "ebitda")
    oi   = _ssum(is_recs, "operatingIncome")
    if ebit is not None and oi is not None:
        return ebit - oi
    return None


def _reit_is_rows(norm, real_cols: list[str], p: str) -> list[dict]:
    """
    Build 5 REIT income-statement rows (raw numbers): NOI, NOI/Sh, FFO, FFO/Sh, AFFO.
    Injected after EPS in the IS table.
    """
    def _compute(is_recs, cf_recs):
        oi   = _ssum(is_recs, "operatingIncome")
        ni   = _ssum(is_recs, "netIncome")
        capx = _ssum(cf_recs, "capitalExpenditure")   # typically negative
        sh   = (_ssum(is_recs, "weightedAverageShsOutDil")
                or _ssum(is_recs, "weightedAverageShsOut"))
        da   = _reit_da(is_recs, cf_recs)

        noi    = (oi + da)    if (oi  is not None and da is not None) else None
        noi_sh = (noi / sh)   if (noi is not None and sh and sh > 0)  else None
        ffo    = (ni + da)    if (ni  is not None and da is not None) else None
        ffo_sh = (ffo / sh)   if (ffo is not None and sh and sh > 0)  else None
        affo   = (ffo + capx) if (ffo is not None and capx is not None) else None

        return noi, noi_sh, ffo, ffo_sh, affo

    labels = ["NOI", "NOI/Sh", "FFO", "FFO/Sh", "AFFO"]
    rows = [{"label": lbl} for lbl in labels]

    # TTM — last 4 quarters
    q_is4 = (norm.q_is or [])[:4]
    q_cf4 = (norm.q_cf or [])[:4]
    for row, v in zip(rows, _compute(q_is4, q_cf4)):
        row["TTM"] = _strip_nan(v)

    # Historical periods
    is_src = norm.is_l if p == "annual" else norm.q_is
    cf_src = norm.cf_l if p == "annual" else norm.q_cf
    for col in real_cols:
        if col == "TTM" or col.startswith("N/A"):
            continue
        yr_idx = real_cols.index(col) - 1
        is_rec = [is_src[yr_idx]] if yr_idx < len(is_src) else []
        cf_rec = [cf_src[yr_idx]] if yr_idx < len(cf_src) else []
        for row, v in zip(rows, _compute(is_rec, cf_rec)):
            row[col] = _strip_nan(v)

    return rows


def _reit_prof_rows(norm, real_cols: list[str]) -> list[dict]:
    """
    Build 1 REIT profitability row: FFO / Total Revenue (%).
    Injected after 'Adj. FCF' in the Profitability table.
    """
    def _compute(is_recs, cf_recs):
        ni  = _ssum(is_recs, "netIncome")
        rev = _ssum(is_recs, "revenue")
        da  = _reit_da(is_recs, cf_recs)
        ffo = (ni + da) if (ni is not None and da is not None) else None
        return (ffo / rev) if (ffo is not None and rev and rev > 0) else None

    row: dict = {"label": "FFO / Total Revenue (%)", "fmt": "pct"}

    row["TTM"] = _strip_nan(_compute((norm.q_is or [])[:4], (norm.q_cf or [])[:4]))

    for col in real_cols:
        if col == "TTM" or col.startswith("N/A"):
            continue
        yr_idx = real_cols.index(col) - 1
        is_rec = [norm.is_l[yr_idx]] if yr_idx < len(norm.is_l) else []
        cf_rec = [norm.cf_l[yr_idx]] if yr_idx < len(norm.cf_l) else []
        row[col] = _strip_nan(_compute(is_rec, cf_rec))

    return [row]


def _reit_mval_rows(norm, raw_data: dict, real_cols: list[str], ov: dict) -> list[dict]:
    """
    Build 2 REIT Market & Valuation rows: P/FFO and FFO Payout Ratio.
    Injected after 'P/Adj. FCF' in the Market & Valuation table.
    """
    km_l    = raw_data.get("annual_key_metrics") or []
    mkt_ttm = _sf(ov.get("mktCap"))

    def _ffo(is_recs, cf_recs):
        ni = _ssum(is_recs, "netIncome")
        da = _reit_da(is_recs, cf_recs)
        return (ni + da) if (ni is not None and da is not None) else None

    ffo_ttm   = _ffo((norm.q_is or [])[:4], (norm.q_cf or [])[:4])
    div_ttm   = _ssum((norm.q_cf or [])[:4], "commonDividendsPaid")
    div_abs   = abs(div_ttm) if div_ttm is not None else None

    p_ffo_row: dict = {
        "label": "P/FFO",
        "fmt": "ratio",
        "TTM": _strip_nan((mkt_ttm / ffo_ttm) if (mkt_ttm and ffo_ttm and ffo_ttm > 0) else None),
    }
    payout_row: dict = {
        "label": "FFO Payout Ratio",
        "fmt": "pct",
        "TTM": _strip_nan((div_abs / ffo_ttm) if (div_abs is not None and ffo_ttm and ffo_ttm > 0) else None),
    }

    for col in real_cols:
        if col == "TTM" or col.startswith("N/A"):
            continue
        yr_idx = real_cols.index(col) - 1
        is_rec = [norm.is_l[yr_idx]] if yr_idx < len(norm.is_l) else []
        cf_rec = [norm.cf_l[yr_idx]] if yr_idx < len(norm.cf_l) else []
        ffo_yr = _ffo(is_rec, cf_rec)
        mkt_yr = _sf(km_l[yr_idx].get("marketCap")) if (yr_idx < len(km_l) and isinstance(km_l[yr_idx], dict)) else None
        div_yr = _ssum(cf_rec, "commonDividendsPaid")
        div_abs_yr = abs(div_yr) if div_yr is not None else None
        p_ffo_row[col]  = _strip_nan((mkt_yr / ffo_yr) if (mkt_yr and ffo_yr and ffo_yr > 0) else None)
        payout_row[col] = _strip_nan((div_abs_yr / ffo_yr) if (div_abs_yr is not None and ffo_yr and ffo_yr > 0) else None)

    return [p_ffo_row, payout_row]


def _reit_capstruct_row(norm, real_cols: list[str]) -> list[dict]:
    """
    Build 1 REIT capital-structure row: FFO Interest Coverage.
    Injected after 'Interest Coverage (EBIT/Interest)' in the Capital Structure table.
    """
    def _compute(is_recs, cf_recs):
        ni   = _ssum(is_recs, "netIncome")
        intx = _ssum(is_recs, "interestExpense")
        da   = _reit_da(is_recs, cf_recs)
        ffo  = (ni + da) if (ni is not None and da is not None) else None
        int_abs = abs(intx) if (intx is not None and intx != 0) else None
        return ((ffo + int_abs) / int_abs) if (ffo is not None and int_abs) else None

    row: dict = {"label": "FFO Interest Coverage", "fmt": "ratio"}

    row["TTM"] = _strip_nan(_compute((norm.q_is or [])[:4], (norm.q_cf or [])[:4]))

    for col in real_cols:
        if col == "TTM" or col.startswith("N/A"):
            continue
        yr_idx = real_cols.index(col) - 1
        is_rec = [norm.is_l[yr_idx]] if yr_idx < len(norm.is_l) else []
        cf_rec = [norm.cf_l[yr_idx]] if yr_idx < len(norm.cf_l) else []
        row[col] = _strip_nan(_compute(is_rec, cf_rec))

    return [row]


# ─────────────────────────────────────────────────────────────────────────────
#  Skeleton data (zero-filled 10-year statements when no source has data)
# ─────────────────────────────────────────────────────────────────────────────

_SKELETON_YEARS = list(range(2025, 2015, -1))   # newest-first: 2025 … 2016


def _skeleton_raw_data() -> dict:
    """
    Return a zero-filled 10-year financial dataset in FMP canonical format.
    Used when both EODHD and FMP are blocked by subscription limits.
    Keeps FinancialsTab columns visible instead of showing a 404 error.
    """
    def _recs(fields: list) -> list:
        rows = []
        for yr in _SKELETON_YEARS:
            rec: dict = {
                "date": f"{yr}-12-31",
                "fiscalYear": str(yr), "calendarYear": str(yr), "period": "FY",
            }
            for f in fields:
                rec[f] = 0
            rows.append(rec)
        return rows

    return {
        "annual_income_statement": _recs([
            "revenue", "grossProfit", "costOfRevenue", "operatingIncome",
            "netIncome", "ebitda", "eps", "epsDiluted",
            "weightedAverageShsOut", "weightedAverageShsOutDil", "interestExpense",
        ]),
        "quarterly_income_statement": [],
        "annual_balance_sheet": _recs([
            "totalAssets", "totalCurrentAssets", "totalLiabilities",
            "totalCurrentLiabilities", "totalStockholdersEquity",
            "cashAndCashEquivalents", "totalDebt", "longTermDebt",
            "commonStockSharesOutstanding", "netReceivables", "inventory",
        ]),
        "quarterly_balance_sheet": [],
        "annual_cash_flow": _recs([
            "operatingCashFlow", "capitalExpenditure", "freeCashFlow",
            "stockBasedCompensation", "commonDividendsPaid",
        ]),
        "quarterly_cash_flow": [],
        "annual_ratios":         [],
        "annual_key_metrics":    [],
        "quarterly_key_metrics": [],
        "historical_prices":     [],
        "_is_skeleton":          True,   # flag for downstream logging
    }


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


@app.get("/api/segments/{ticker}", summary="Revenue by business segment (up to 5 years)", tags=["Profile"])
def segments_endpoint(ticker: str):
    """
    Returns product-segment revenue breakdown from FMP stable API.

    The stable endpoint returns nested records:
      {"fiscalYear": 2024, "period": "FY", "date": "...", "data": {"Seg": value, ...}}

    Years are newest-first; segments sorted by total revenue descending.
    Returns empty lists when no segment data is available (international tickers).
    """
    t = ticker.strip().upper()
    raw = _gw.fetch_segments(t)
    if not raw:
        return {"ticker": t, "years": [], "segments": []}

    # Keep only annual (FY) records — the endpoint may include quarterly rows
    annual = [r for r in raw if str(r.get("period") or "").upper() in ("FY", "ANNUAL")]
    if not annual:
        annual = raw  # fallback: use everything if no FY tag found

    rows = annual[:5]  # cap at 5 most-recent annual years

    # Year label from fiscalYear int → string, fall back to date prefix
    def _year(r: dict) -> str:
        fy = r.get("fiscalYear")
        if fy is not None:
            return str(int(fy))
        return (r.get("date") or "")[:4]

    years = [_year(r) for r in rows]

    # Collect segment names from the nested "data" dicts (preserve insertion order)
    seg_names: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in (r.get("data") or {}):
            if k not in seen:
                seg_names.append(k)
                seen.add(k)

    # Drop segments with no revenue across all years
    def _total(name: str) -> float:
        return sum(abs(float((r.get("data") or {}).get(name) or 0)) for r in rows)

    seg_names = [s for s in seg_names if _total(s) > 0]
    seg_names.sort(key=_total, reverse=True)

    segs = []
    for name in seg_names:
        rev_by_year: dict = {}
        for r in rows:
            yr = _year(r)
            v = (r.get("data") or {}).get(name)
            rev_by_year[yr] = _strip_nan(float(v)) if v is not None else None
        segs.append({
            "name": name,
            "revenue_by_year": rev_by_year,
            "operating_income_by_year": {},
            "assets_by_year": {},
        })

    return {"ticker": t, "years": years, "segments": segs}


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
        print(f"[financials] No data for {ticker} — using skeleton", flush=True)
        raw_data = _skeleton_raw_data()

    norm        = DataNormalizer(raw_data, ticker)
    all_headers = norm.get_column_headers(p)
    real_cols   = ["TTM"] + [h for h in all_headers[2:] if not h.startswith("N/A-")]

    is_rows = _clean_rows(norm.get_income_statement(p), real_cols)

    # Inject REIT-specific IS rows after EPS
    if _is_reit(ov):
        reit_rows = _reit_is_rows(norm, real_cols, p)
        eps_idx = next(
            (i for i, r in enumerate(is_rows) if r.get("label") == "EPS"),
            len(is_rows) - 1,
        )
        is_rows = is_rows[:eps_idx + 1] + reit_rows + is_rows[eps_idx + 1:]

    return {
        "ticker":           ticker,
        "period":           p,
        "currency":         ov.get("currency", "USD"),
        "columns":          real_cols,
        "income_statement": is_rows,
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

    # REIT-specific insight rows
    if _is_reit(ov):
        is_l  = raw_data.get("annual_income_statement") or []
        cf_l  = raw_data.get("annual_cash_flow")        or []
        km_l  = raw_data.get("annual_key_metrics")      or []
        q_is4 = (raw_data.get("quarterly_income_statement") or [])[:4]
        q_cf4 = (raw_data.get("quarterly_cash_flow")        or [])[:4]

        def _ffo_reit(is_recs, cf_recs):
            ni = _ssum(is_recs, "netIncome")
            da = _reit_da(is_recs, cf_recs)
            return (ni + da) if (ni is not None and da is not None) else None

        def _ffo_at(i):
            return _ffo_reit(
                [is_l[i]] if i < len(is_l) else [],
                [cf_l[i]] if i < len(cf_l) else [],
            )

        def _p_ffo_at(i):
            ffo = _ffo_at(i)
            mkt = _sf(km_l[i].get("marketCap")) if i < len(km_l) and isinstance(km_l[i], dict) else None
            return (mkt / ffo) if (mkt and ffo and ffo > 0) else None

        def _ffo_payout_at(i):
            ffo = _ffo_at(i)
            d   = _ssum([cf_l[i]] if i < len(cf_l) else [], "commonDividendsPaid")
            d_abs = abs(d) if d is not None else None
            return (d_abs / ffo) if (d_abs is not None and ffo and ffo > 0) else None

        def _avg_vals(vals):
            v = [x for x in vals if x is not None]
            return sum(v) / len(v) if v else None

        # P/FFO (TTM)
        ffo_ttm = _ffo_reit(q_is4, q_cf4)
        mkt_ttm = _sf(ov.get("mktCap"))
        p_ffo_ttm = (mkt_ttm / ffo_ttm) if (mkt_ttm and ffo_ttm and ffo_ttm > 0) else None

        p_ffo_row = {
            "label": "P/FFO (TTM)",
            "TTM":       _strip_nan(p_ffo_ttm),
            "Avg. 5yr":  _strip_nan(_avg_vals([_p_ffo_at(i) for i in range(5)])),
            "Avg. 10yr": _strip_nan(_avg_vals([_p_ffo_at(i) for i in range(10)])),
        }

        # FFO Payout Ratio (%)
        div_ttm   = _ssum(q_cf4, "commonDividendsPaid")
        div_abs   = abs(div_ttm) if div_ttm is not None else None
        ffo_pay_ttm = (div_abs / ffo_ttm) if (div_abs is not None and ffo_ttm and ffo_ttm > 0) else None

        ffo_payout_row = {
            "label": "FFO Payout Ratio (%)",
            "TTM":       _strip_nan(ffo_pay_ttm),
            "Avg. 5yr":  _strip_nan(_avg_vals([_ffo_payout_at(i) for i in range(5)])),
            "Avg. 10yr": _strip_nan(_avg_vals([_ffo_payout_at(i) for i in range(10)])),
        }

        for grp in groups:
            if grp["title"] == "Valuation Multiples":
                ev_idx = next(
                    (i for i, r in enumerate(grp["rows"]) if r.get("label") == "EV / EBITDA"),
                    0,
                )
                grp["rows"].insert(ev_idx, p_ffo_row)
            elif grp["title"] == "Dividends":
                pr_idx = next(
                    (i for i, r in enumerate(grp["rows"]) if r.get("label") == "Payout Ratio"),
                    None,
                )
                if pr_idx is not None:
                    grp["rows"].insert(pr_idx + 1, ffo_payout_row)
                else:
                    grp["rows"].append(ffo_payout_row)

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

    if not raw_data.get("annual_income_statement") and \
       not raw_data.get("quarterly_income_statement"):
        print(f"[financials_extended] No data for {ticker} — using skeleton", flush=True)
        raw_data = _skeleton_raw_data()

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

    mval_rows   = _clean_ext(market_val)
    prof_rows   = _clean_ext(profitab)
    capst_rows  = _clean_ext(cap_struct)

    # Inject REIT-specific rows
    if _is_reit(ov):
        # Market & Valuation: P/FFO and FFO Payout Ratio after "P/Adj. FCF"
        reit_mval = _reit_mval_rows(norm, raw_data, real_cols, ov)
        padj_idx = next(
            (i for i, r in enumerate(mval_rows) if r.get("label") == "P/Adj. FCF"),
            None,
        )
        if padj_idx is not None:
            mval_rows = mval_rows[:padj_idx + 1] + reit_mval + mval_rows[padj_idx + 1:]
        else:
            mval_rows.extend(reit_mval)

        # Profitability: FFO / Total Revenue (%) after "Adj. FCF"
        reit_prof = _reit_prof_rows(norm, real_cols)
        adj_fcf_idx = next(
            (i for i, r in enumerate(prof_rows) if r.get("label") == "Adj. FCF"),
            None,
        )
        if adj_fcf_idx is not None:
            prof_rows = prof_rows[:adj_fcf_idx + 1] + reit_prof + prof_rows[adj_fcf_idx + 1:]
        else:
            prof_rows.extend(reit_prof)

        # Capital Structure: FFO Interest Coverage after "Interest Coverage (EBIT/Interest)"
        reit_cs = _reit_capstruct_row(norm, real_cols)
        ic_idx = next(
            (i for i, r in enumerate(capst_rows)
             if r.get("label") == "Interest Coverage (EBIT/Interest)"),
            None,
        )
        if ic_idx is not None:
            capst_rows = capst_rows[:ic_idx + 1] + reit_cs + capst_rows[ic_idx + 1:]
        else:
            capst_rows.extend(reit_cs)

    return {
        "ticker":           ticker,
        "period":           p,
        "columns":          real_cols,
        "market_valuation": mval_rows,
        "capital_structure": capst_rows,
        "profitability":    prof_rows,
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


# ── Request body for PDF generation ──────────────────────────────────────────

class _CfIrrPdfBody(BaseModel):
    """Full live state from React — exactly what the user sees on screen."""
    wacc_pct:     float
    mos_pct:      float
    exit_mult:    float
    exit_yield:   float
    # Company identity (passed from React overview state — avoids extra API call)
    company:      str = ""
    sector:       str = ""
    industry:     str = ""
    description:  str = ""
    # Historical tables
    ebt_hist:     list[dict[str, Any]]
    ebt_ttm:      dict[str, Any]
    ebt_avg:      dict[str, Any]
    ebt_cagr:     dict[str, Any]
    fcf_hist:     list[dict[str, Any]]
    fcf_ttm:      dict[str, Any]
    fcf_avg:      dict[str, Any]
    fcf_cagr:     dict[str, Any]
    # Forecast rows (already reflect user's current growth inputs)
    ebt_forecast: list[dict[str, Any]]
    fcf_forecast: list[dict[str, Any]]
    # Computed results (from React's live FinalOutput derivation)
    price_now:    float | None
    avg_target:   float | None
    fair_value:   float | None
    buy_price:    float | None
    on_sale:      bool | None
    irr:          float | None
    # Checklist items as {label, threshold, display, passed, value}
    checklist:    list[dict[str, Any]]


@app.post("/api/cf-irr/{ticker}/pdf", summary="Download CF+IRR One-Pager PDF", tags=["Valuation"])
def cf_irr_pdf(ticker: str, body: _CfIrrPdfBody):
    """
    Accepts the full live React state and returns a dynamic analyst-style PDF.
    Only fetches overview + historical prices from the API (needed for chart +
    company metadata). All financial table data comes directly from the request body.
    """
    ticker = ticker.strip().upper()

    try:
        from backend.services.pdf_service import generate_cfirr_pdf
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF service unavailable: {exc}")

    # Company metadata comes from the React body — no API call needed for that.
    company     = body.company     or ticker
    sector      = body.sector      or ""
    industry    = body.industry    or ""
    description = body.description or ""

    # Fetch only historical prices for the chart — single lightweight API call.
    # Uses a shared module-level executor so we never block waiting for the
    # thread to finish after a timeout (unlike "with ThreadPoolExecutor(...)").
    hist_prices: list = []
    try:
        _fut = _bg_executor.submit(_gw.fetch_hist_prices, ticker)
        hist_prices = _fut.result(timeout=12)
    except Exception:
        hist_prices = []   # chart omitted — PDF still generated

    # Convert React checklist dicts → (label, display, passed, threshold) tuples
    checklist_pdf = [
        (
            item.get("label",     ""),
            item.get("display",   "N/A"),
            item.get("passed"),
            item.get("threshold", ""),
        )
        for item in body.checklist
    ]

    def _fp(v):
        return "N/A" if v is None else f"${v:,.2f}"

    def _fmt_delta(target, current):
        if not target or not current or target == 0:
            return "N/A"
        pct = (1.0 - current / target) * 100.0
        return f"{'Upside' if pct >= 0 else 'Downside'}  {'+' if pct >= 0 else ''}{pct:.1f}%"

    final_rows = [
        ("Average Target Price",   _fp(body.avg_target),                        None),
        ("WACC",                   f"{body.wacc_pct:.2f}%",                     None),
        ("Fair Value per share",   _fp(body.fair_value),                        None),
        ("Margin of Safety (%)",   f"{body.mos_pct:.0f}%",                      None),
        ("Buy Price",              _fp(body.buy_price),                         None),
        ("Current Stock Price",    _fp(body.price_now),                         None),
        ("Company on-sale?",
         "ON SALE" if body.on_sale else "NOT ON SALE" if body.on_sale is False else "N/A",
         body.on_sale),
        ("Upside (vs Fair Value)", _fmt_delta(body.fair_value, body.price_now), None),
        ("Upside (vs Buy Price)",  _fmt_delta(body.buy_price,  body.price_now), None),
    ]

    try:
        pdf_bytes = generate_cfirr_pdf(
            ticker            = ticker,
            company           = company,
            sector            = sector,
            industry          = industry,
            description       = description,
            historical_prices = hist_prices,
            ebt_hist          = body.ebt_hist,
            ebt_cagr          = body.ebt_cagr,
            ebt_avg           = body.ebt_avg,
            ebt_ttm           = body.ebt_ttm,
            fcf_hist          = body.fcf_hist,
            fcf_cagr          = body.fcf_cagr,
            fcf_avg           = body.fcf_avg,
            fcf_ttm           = body.fcf_ttm,
            ebt_fc_rows       = body.ebt_forecast,
            fcf_fc_rows       = body.fcf_forecast,
            checklist         = checklist_pdf,
            final_rows        = final_rows,
            price_now         = body.price_now,
            avg_target_ss     = body.avg_target,
            irr_val           = body.irr,
            fair_value_now    = body.fair_value,
            buy_price_now     = body.buy_price,
            on_sale_now       = body.on_sale,
        )
        return Response(
            content=pdf_bytes,      # already bytes from pdf_service
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{ticker}_One_Pager.pdf"'},
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()       # full stack trace to uvicorn log
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": app.version}
