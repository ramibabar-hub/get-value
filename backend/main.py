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
import io
import builtins

# ── Windows Unicode safety ──────────────────────────────────────────────────
# Uvicorn on Windows uses cp1252 stdout which crashes on non-ASCII print() calls.
# We patch builtins.print so ANY non-encodable character is silently replaced.
# This is the only layer that reliably survives uvicorn's stdout management.
_builtin_print = builtins.print

def _safe_print(*args, **kwargs):
    try:
        _builtin_print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError):
        enc = getattr(getattr(sys.stdout, "encoding", None), "__str__", lambda: "utf-8")()
        safe = tuple(
            str(a).encode(enc or "utf-8", errors="replace").decode(enc or "utf-8")
            for a in args
        )
        try:
            _builtin_print(*safe, **kwargs)
        except Exception:
            pass  # absolute last resort — swallow to prevent HTTP 502

builtins.print = _safe_print
# ────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import datetime
import concurrent.futures as _cf
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Response, Body, BackgroundTasks
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

@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    title="getValue API",
    description=(
        "Financial analysis backend with Smart Gateway (FMP + EODHD). "
        "US stocks use FMP; international stocks use EODHD with cross-source fallback."
    ),
    version="0.3.0",
    lifespan=lifespan,
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

    # Year label from fiscalYear int -> string, fall back to date prefix
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
        print(f"[financials] No data for {ticker} - using skeleton", flush=True)
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
        print(f"[financials_extended] No data for {ticker} - using skeleton", flush=True)
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

    # Convert React checklist dicts -> (label, display, passed, threshold) tuples
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


@app.get("/api/cf-irr-special/{ticker}", summary="Special TBV+EPS IRR Model", tags=["Valuation"])
def cf_irr_special(
    ticker:       str,
    tbv_growth:   str   = Query(default="5"),
    eps_growth:   str   = Query(default="5"),
    exit_ptbv:    float = Query(default=1.5),
    exit_pe:      float = Query(default=15.0),
    tbv_weight:   float = Query(default=0.5),
    mos_pct:      float = Query(default=10.0),
    wacc_override: float | None = Query(default=None),
):
    """
    Special valuation model using Tangible Book Value (TBV) and EPS.
    TBV = Total Assets − (Goodwill & Intangibles) − Total Liabilities.
    Terminal Value = tbv_weight × (TBV₁₀ × exit_ptbv) + (1−tbv_weight) × (EPS₁₀ × exit_pe).
    IRR on cashflow: [−price, EPS₁..EPS₉, EPS₁₀ + TerminalValue].
    """
    import math as _math

    ticker = ticker.strip().upper()
    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    try:
        from cf_irr_tab import _irr_calc, _s as _sf
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Logic import failed: {exc}")

    # ── Growth-rate arrays ────────────────────────────────────────────────────
    def _parse(s: str, default: float = 5.0) -> list[float]:
        try:
            r = [float(x) for x in s.split(",")]
            while len(r) < 9:
                r.append(default)
            return r[:9]
        except Exception:
            return [default] * 9

    tbv_rates = _parse(tbv_growth, 5.0)
    eps_rates = _parse(eps_growth, 5.0)

    # ── Raw annual data ───────────────────────────────────────────────────────
    bs_l = (raw_data.get("annual_balance_sheet")      or [])[:10]   # newest-first
    is_l = (raw_data.get("annual_income_statement")   or [])[:10]
    n    = min(len(bs_l), len(is_l))

    def _yr(r: dict) -> str:
        d = str(r.get("date") or r.get("calendarYear") or "")
        return d[:4] if len(d) >= 4 else "?"

    def _fB(v) -> str:   # in billions
        f = _sf(v); return "N/A" if f is None else f"{f / 1e9:,.2f}"
    def _fps(v) -> str:  # per-share price
        f = _sf(v); return "N/A" if f is None else f"${f:,.2f}"
    def _fpct(v) -> str:
        f = _sf(v); return "N/A" if f is None else f"{f * 100:.1f}%"
    def _fx(v) -> str:
        f = _sf(v); return "N/A" if f is None else f"{f:.2f}x"
    def _row_clean_sp(r: dict) -> dict:
        return {k: (v if isinstance(v, str) else _strip_nan(v)) for k, v in r.items()}

    hist_raw: list[dict] = []   # numeric, newest-first
    hist_disp: list[dict] = []  # display strings, newest-first

    for i in range(n):
        bs  = bs_l[i]
        iss = is_l[i]
        yr  = _yr(bs)

        assets = _sf(bs.get("totalAssets"))
        gwi    = _sf(bs.get("goodwillAndIntangibleAssets"))
        if gwi is None:
            gwi = (_sf(bs.get("goodwill")) or 0.0) + (_sf(bs.get("intangibleAssets")) or 0.0)
        liab   = _sf(bs.get("totalLiabilities"))
        tbv    = (assets - gwi - liab) if (assets is not None and liab is not None) else None

        shares = _sf(iss.get("weightedAverageShsOutDil") or iss.get("weightedAverageShsOut"))
        tbv_ps = (tbv / shares) if (tbv is not None and shares and shares > 0) else None
        eps    = _sf(iss.get("epsDiluted"))
        ni     = _sf(iss.get("netIncome"))
        rev    = _sf(iss.get("revenue"))
        margin = (ni / rev) if (ni is not None and rev and rev != 0) else None

        hist_raw.append({"yr": yr, "assets": assets, "gwi": gwi, "liab": liab,
                          "tbv_ps": tbv_ps, "eps": eps, "ni": ni, "rev": rev, "margin": margin})
        hist_disp.append({
            "Year":        yr,
            "Assets ($B)": _fB(assets),
            "GW&I ($B)":   _fB(gwi),
            "Liab ($B)":   _fB(liab),
            "TBV/s":       _fps(tbv_ps),
            "EPS":         _fps(eps),
            "Net Margin":  _fpct(margin),
        })

    # ── Summary rows ─────────────────────────────────────────────────────────
    ttm  = hist_raw[0]  if hist_raw else {}
    disp_oldest_first = list(reversed(hist_disp))

    def _avg_col(key):
        vals = [r[key] for r in hist_raw if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    def _cagr_col(key):
        vals = [r[key] for r in reversed(hist_raw) if r.get(key) is not None and r[key] > 0]
        if len(vals) < 2:
            return None
        try:
            return (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
        except Exception:
            return None

    cagr_n      = min(9, max(1, n - 1))
    assets_cagr = _cagr_col("assets")
    tbv_ps_cagr = _cagr_col("tbv_ps")
    eps_cagr    = _cagr_col("eps")
    margin_avg  = _avg_col("margin")

    hist_ttm = {
        "Year": "TTM", "Assets ($B)": _fB(ttm.get("assets")),
        "GW&I ($B)": _fB(ttm.get("gwi")), "Liab ($B)": _fB(ttm.get("liab")),
        "TBV/s": _fps(ttm.get("tbv_ps")), "EPS": _fps(ttm.get("eps")),
        "Net Margin": _fpct(ttm.get("margin")),
    }
    hist_avg = {
        "Year": "Average", "Assets ($B)": _fB(_avg_col("assets")),
        "GW&I ($B)": _fB(_avg_col("gwi")), "Liab ($B)": _fB(_avg_col("liab")),
        "TBV/s": _fps(_avg_col("tbv_ps")), "EPS": _fps(_avg_col("eps")),
        "Net Margin": _fpct(margin_avg),
    }
    hist_cagr = {
        "Year": f"CAGR ({cagr_n}-yr)",
        "Assets ($B)": _fpct(assets_cagr), "GW&I ($B)": "—", "Liab ($B)": "—",
        "TBV/s": _fpct(tbv_ps_cagr), "EPS": _fpct(eps_cagr),
        "Net Margin": _fpct(margin_avg),
    }

    # ── Default growth seeds from CAGRs ──────────────────────────────────────
    def _seed(v, default=5.0) -> float:
        if v is None:
            return default
        pct = v * 100
        return max(-20.0, min(50.0, round(pct, 1)))

    default_tbv_rate = _seed(tbv_ps_cagr, 5.0)
    default_eps_rate = _seed(eps_cagr,    5.0)

    # ── Forecast rows ─────────────────────────────────────────────────────────
    base_year  = int(ttm.get("yr", 2024))
    base_tbv_ps = ttm.get("tbv_ps") or 0.0
    base_eps    = ttm.get("eps")    or 0.0
    price_now   = _sf(ov.get("price"))

    tbv_fc_rows: list[dict] = []
    eps_fc_rows: list[dict] = []
    tbv_run = base_tbv_ps
    eps_run = base_eps

    for y in range(1, 10):
        g_tbv  = tbv_rates[y - 1] / 100.0
        g_eps  = eps_rates[y - 1] / 100.0
        tbv_run = tbv_run * (1 + g_tbv)
        eps_run = eps_run * (1 + g_eps)
        yr_lbl  = str(base_year + y)
        tbv_fc_rows.append({"Year": yr_lbl, "Est. Growth Rate (%)": tbv_rates[y - 1], "Est. TBV/s": tbv_run})
        eps_fc_rows.append({"Year": yr_lbl, "Est. Growth Rate (%)": eps_rates[y - 1], "Est. EPS":   eps_run})

    # ── Terminal value ────────────────────────────────────────────────────────
    tbv_yr9    = tbv_fc_rows[-1]["Est. TBV/s"] if tbv_fc_rows else None
    eps_yr9    = eps_fc_rows[-1]["Est. EPS"]   if eps_fc_rows else None
    tbv_terminal = (tbv_yr9 * exit_ptbv) if tbv_yr9 is not None else None
    eps_terminal = (eps_yr9 * exit_pe)   if eps_yr9 is not None else None

    if tbv_terminal is not None and eps_terminal is not None:
        avg_target = tbv_weight * tbv_terminal + (1.0 - tbv_weight) * eps_terminal
    elif tbv_terminal is not None:
        avg_target = tbv_terminal
    elif eps_terminal is not None:
        avg_target = eps_terminal
    else:
        avg_target = None

    # ── WACC + fair value ─────────────────────────────────────────────────────
    try:
        from backend.logic_engine import compute_wacc
        wacc_computed = compute_wacc(raw_data, ov)
    except Exception:
        wacc_computed = 0.10

    wacc_val   = (wacc_override / 100.0) if wacc_override is not None else wacc_computed
    fair_value = None
    buy_price  = None
    if avg_target is not None and wacc_val > 0:
        fair_value = avg_target / (1.0 + wacc_val) ** 9
        buy_price  = fair_value * (1.0 - mos_pct / 100.0)
    on_sale = (fair_value > price_now) if (fair_value is not None and price_now) else None

    # ── IRR: [−price, EPS₁..EPS₈, EPS₉ + TerminalValue] ────────────────────
    irr_val = None
    if price_now and price_now > 0 and eps_fc_rows and avg_target is not None:
        cashflows = [r["Est. EPS"] for r in eps_fc_rows]
        cashflows[-1] = cashflows[-1] + avg_target
        irr_val = _irr_calc([-price_now] + cashflows)

    # ── Checklist ─────────────────────────────────────────────────────────────
    def _chk(val, threshold, lower=False):
        f = _sf(val)
        if f is None:
            return {"value": None, "display": "N/A", "passed": None}
        passed = (f < threshold) if lower else (f >= threshold)
        return {"value": f, "display": f"{f * 100:.1f}%", "passed": passed}

    checklist = [
        {"label": "Assets Growth (CAGR)",  "threshold": "> 4%",  **_chk(assets_cagr, 0.04)},
        {"label": "TBV/s Growth (CAGR)",   "threshold": "> 3%",  **_chk(tbv_ps_cagr, 0.03)},
        {"label": "Net Inc. Margin (avg)", "threshold": "> 10%", **_chk(margin_avg,  0.10)},
        {"label": "EPS Growth (CAGR)",     "threshold": "> 10%", **_chk(eps_cagr,    0.10)},
        {"label": "IRR",                   "threshold": "> 12%", **_chk(irr_val,     0.12)},
    ]

    return {
        "ticker":           ticker,
        "base_year":        base_year,
        "price_now":        _strip_nan(price_now),
        "base_tbv_ps":      _strip_nan(base_tbv_ps),
        "base_eps":         _strip_nan(base_eps),
        "wacc":             _strip_nan(wacc_val),
        "wacc_computed":    _strip_nan(wacc_computed),
        "exit_ptbv":        exit_ptbv,
        "exit_pe":          exit_pe,
        "tbv_weight":       tbv_weight,
        "mos_pct":          mos_pct,
        "tbv_growth_rates": tbv_rates,
        "eps_growth_rates": eps_rates,
        "default_tbv_rate": default_tbv_rate,
        "default_eps_rate": default_eps_rate,
        "hist":             [_row_clean_sp(r) for r in disp_oldest_first],
        "hist_ttm":         _row_clean_sp(hist_ttm),
        "hist_avg":         _row_clean_sp(hist_avg),
        "hist_cagr":        _row_clean_sp(hist_cagr),
        "tbv_forecast":     [_row_clean_sp(r) for r in tbv_fc_rows],
        "eps_forecast":     [_row_clean_sp(r) for r in eps_fc_rows],
        "tbv_terminal":     _strip_nan(tbv_terminal),
        "eps_terminal":     _strip_nan(eps_terminal),
        "avg_target":       _strip_nan(avg_target),
        "fair_value":       _strip_nan(fair_value),
        "buy_price":        _strip_nan(buy_price),
        "on_sale":          on_sale,
        "irr":              _strip_nan(irr_val),
        "checklist":        checklist,
        "assets_cagr":      _strip_nan(assets_cagr),
        "tbv_ps_cagr":      _strip_nan(tbv_ps_cagr),
        "eps_cagr":         _strip_nan(eps_cagr),
        "margin_avg":       _strip_nan(margin_avg),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  DDM  —  Dividend Discount Model (Gordon Growth)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/ddm/{ticker}", summary="Dividend Discount Model — Gordon Growth", tags=["Valuation"])
def ddm(
    ticker:        str,
    wacc_override: float | None = Query(default=None,
                                         description="Override WACC (pct, e.g. 9.5 -> 9.5%)"),
):
    """
    Returns 10-year DPS history (oldest first), TTM row, DPS CAGR, WACC, and
    terminal-growth default so the React frontend can run the Gordon Growth
    model entirely client-side.
    """
    ticker = ticker.strip().upper()

    # ── Fetch ─────────────────────────────────────────────────────────────────
    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker) or {}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    is_l = raw_data.get("annual_income_statement")   or []
    cf_l = raw_data.get("annual_cash_flow")           or []
    q_is = raw_data.get("quarterly_income_statement") or []
    q_cf = raw_data.get("quarterly_cash_flow")        or []

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _g(lst, key, i):
        if i >= len(lst):
            return None
        v = lst[i].get(key)
        try:
            f = float(v)
            return f if _math.isfinite(f) else None
        except (TypeError, ValueError):
            return None

    def _ttm_q(q_lst, key, n=4):
        vals     = [_g(q_lst, key, i) for i in range(min(n, len(q_lst)))]
        non_null = [v for v in vals if v is not None]
        return sum(non_null) if non_null else None

    # ── Annual history (oldest first) ─────────────────────────────────────────
    n_yrs = min(len(is_l), len(cf_l), 10)
    hist_rows: list[dict] = []

    for i in range(n_yrs - 1, -1, -1):          # index 0 = most recent; reverse for display
        rec    = is_l[i]
        yr_lbl = str(rec.get("calendarYear") or rec.get("date", "")[:4])

        divs   = _g(cf_l, "commonDividendsPaid", i)        # negative = paid out
        shares = (_g(is_l, "weightedAverageShsOutDil", i)
                  or _g(is_l, "weightedAverageShsOut",    i))
        ni     = _g(is_l, "netIncome", i)

        dps    = (abs(divs) / shares
                  if divs is not None and shares and shares > 0 else None)
        payout = (abs(divs) / ni
                  if divs is not None and ni and ni > 0 else None)

        hist_rows.append({
            "year":       yr_lbl,
            "divs_paid":  _strip_nan(divs),
            "shares":     _strip_nan(shares),
            "dps":        _strip_nan(dps),
            "net_income": _strip_nan(ni),
            "payout_pct": _strip_nan(payout),
        })

    # ── TTM ───────────────────────────────────────────────────────────────────
    divs_ttm  = _ttm_q(q_cf, "commonDividendsPaid")
    ni_ttm    = _ttm_q(q_is, "netIncome")
    # DPS uses the most recent quarter's share count (annualising a sum would overcount)
    sh_latest = (_g(q_is, "weightedAverageShsOutDil", 0)
                 or _g(q_is, "weightedAverageShsOut",    0)
                 or _g(is_l, "weightedAverageShsOutDil", 0)
                 or _g(is_l, "weightedAverageShsOut",    0))

    dps_ttm    = (abs(divs_ttm) / sh_latest
                  if divs_ttm is not None and sh_latest and sh_latest > 0 else None)
    payout_ttm = (abs(divs_ttm) / ni_ttm
                  if divs_ttm is not None and ni_ttm and ni_ttm > 0 else None)

    ttm_row = {
        "year":       "TTM",
        "divs_paid":  _strip_nan(divs_ttm),
        "shares":     _strip_nan(sh_latest),
        "dps":        _strip_nan(dps_ttm),
        "net_income": _strip_nan(ni_ttm),
        "payout_pct": _strip_nan(payout_ttm),
    }

    # ── DPS CAGR (oldest hist year -> TTM) ────────────────────────────────────
    dps_series = [r["dps"] for r in hist_rows if r["dps"] is not None and r["dps"] > 0]
    if dps_ttm and dps_ttm > 0:
        dps_series.append(dps_ttm)

    dps_cagr   = None
    cagr_years = 0
    if len(dps_series) >= 2:
        oldest, latest = dps_series[0], dps_series[-1]
        cagr_years = len(dps_series) - 1
        try:
            raw_cagr = (latest / oldest) ** (1.0 / cagr_years) - 1.0
            dps_cagr = raw_cagr if _math.isfinite(raw_cagr) else None
        except Exception:
            dps_cagr = None

    # ── WACC ──────────────────────────────────────────────────────────────────
    try:
        from backend.logic_engine import compute_wacc
        wacc_computed = compute_wacc(raw_data, ov)
        if not wacc_computed or not _math.isfinite(wacc_computed):
            wacc_computed = 0.10
    except Exception:
        wacc_computed = 0.10

    wacc_val = (wacc_override / 100.0) if wacc_override is not None else wacc_computed

    # ── Terminal growth default ────────────────────────────────────────────────
    # Cap at 5 %; floor at 1 %; follow DPS CAGR when in range
    if dps_cagr is not None and _math.isfinite(dps_cagr):
        if dps_cagr > 0.05:
            g_terminal_default = 0.05
        elif dps_cagr > 0.0:
            g_terminal_default = min(dps_cagr, 0.04)
        else:
            g_terminal_default = 0.02
    else:
        g_terminal_default = 0.03

    price_now = _strip_nan(float(ov.get("price") or 0) or None)
    currency  = is_l[0].get("reportedCurrency", "USD") if is_l else "USD"

    return {
        "ticker":             ticker,
        "currency":           currency,
        "price_now":          price_now,
        "hist":               hist_rows,
        "ttm":                ttm_row,
        "dps_cagr":           _strip_nan(dps_cagr),
        "dps_cagr_years":     cagr_years,
        "wacc_computed":      _strip_nan(wacc_computed),
        "wacc":               _strip_nan(wacc_val),
        "default_g_terminal": g_terminal_default,
        "has_dividend":       bool(dps_ttm and dps_ttm > 0),
    }


@app.get("/api/sec-filings/{ticker}", summary="Filing links by period (SEC for US, EODHD portal for intl)", tags=["Filings"])
def sec_filings(ticker: str):
    """
    Returns {period_label: filing_url} for the given ticker.
    • US tickers  -> SEC EDGAR iXBRL viewer URLs (exact filing documents)
    • Intl tickers -> EODHD-derived period list + exchange regulatory portal links
    Period labels match FinancialsTab column headers ("2024", "Q3 2024", …).
    Best-effort — errors are swallowed, never raise to the client.
    """
    try:
        from backend.services.sec_service import get_filing_links
        return get_filing_links(ticker.strip().upper())
    except Exception as exc:
        print(f"[sec_filings] {ticker}: {exc}", flush=True)
        return {}


# ══ Cascade data service ══════════════════════════════════════════════════════

@app.get("/api/cascade/profile/{ticker}",
         summary="Company profile via 4-provider cascade (FMP->EODHD->AlphaVantage->Finnhub)",
         tags=["Cascade"])
def cascade_profile(ticker: str):
    """
    Returns a normalised company profile dict.
    Tries FMP first; falls back to EODHD, then Alpha Vantage, then Finnhub.
    Response always includes `data_source` (which provider succeeded) and
    `providers_tried` (ordered list of all providers attempted).
    """
    try:
        from backend.services.cascade_service import fetch_cascade_profile
        return fetch_cascade_profile(ticker.strip().upper())
    except Exception as exc:
        print(f"[cascade_profile] {ticker}: {exc}", flush=True)
        return {"ticker": ticker.upper(), "error": str(exc), "data_source": "none"}


@app.get("/api/cascade/quote/{ticker}",
         summary="Live price + change via FMP->Finnhub cascade",
         tags=["Cascade"])
def cascade_quote(ticker: str):
    """
    Lightweight quote endpoint — price + % change only.
    Tries FMP first, falls back to Finnhub.
    """
    try:
        from backend.services.cascade_service import fetch_cascade_quote
        return fetch_cascade_quote(ticker.strip().upper())
    except Exception as exc:
        print(f"[cascade_quote] {ticker}: {exc}", flush=True)
        return {"ticker": ticker.upper(), "price": None, "change_pct": None, "data_source": "none"}


# ══ Gemini qualitative analysis ═══════════════════════════════════════════════

class _GeminiAnalysisRequest(BaseModel):
    company_name: str | None = None
    sector:       str | None = None
    industry:     str | None = None
    country:      str | None = None
    market_cap:   float | None = None
    pe_ratio:     float | None = None
    description:  str | None = None


@app.post("/api/gemini/analyze/{ticker}",
          summary="Qualitative company analysis powered by Gemini 1.5 Flash",
          tags=["AI"])
def gemini_analyze(
    ticker: str,
    body: _GeminiAnalysisRequest,
    analysis_type: str = "summary",
):
    """
    Generate qualitative AI analysis for a company.

    **analysis_type** options:
    - `summary`   — 3–5 sentence investment overview (default)
    - `moat`      — economic moat assessment (Wide / Narrow / None)
    - `risks`     — top 3 material investor risks
    - `valuation` — valuation commentary relative to business quality

    Pass company context in the request body (from a prior /api/cascade/profile call).
    """
    try:
        from backend.services.gemini_service import analyze_company
        context = body.model_dump(exclude_none=True)
        return analyze_company(ticker.strip().upper(), context, analysis_type)
    except Exception as exc:
        print(f"[gemini_analyze] {ticker}: {exc}", flush=True)
        return {
            "ticker": ticker.upper(),
            "analysis_type": analysis_type,
            "text": "",
            "model": "gemini-1.5-flash",
            "error": str(exc),
        }


@app.get("/api/industry-multiple/{ticker}", summary="Industry Multiple valuation model", tags=["Valuation"])
def industry_multiple(ticker: str):
    """
    Returns historical annual data (price, EPS, EBITDA, Revenue, FCF, multiples) plus
    TTM values and 10yr averages for the Industry Multiple valuation model.
    The frontend handles all interactive calculations client-side.
    """
    ticker = ticker.strip().upper()
    try:
        raw_data = _gw.fetch_all(ticker)
        ov       = _gw.fetch_overview(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    norm = DataNormalizer(raw_data, ticker)
    is_l = norm.is_l or []
    cf_l = norm.cf_l or []
    bs_l = norm.bs_l or []
    km_l = raw_data.get("annual_key_metrics") or []

    # ── Year-end price lookup ─────────────────────────────────────────────────
    hist_prices_raw = raw_data.get("historical_prices") or []
    _price_by_year: dict[str, float] = {}
    for rec in reversed(hist_prices_raw):          # oldest -> newest so Dec overwrites Jan
        d = str(rec.get("date") or "")
        if len(d) < 4:
            continue
        yr = d[:4]
        p  = _sf(rec.get("close") or rec.get("adjClose"))
        if p:
            _price_by_year[yr] = p

    # ── Build per-year rows (newest first, then reversed) ─────────────────────
    _rows_newest = []
    for i, is_rec in enumerate(is_l[:10]):
        if not isinstance(is_rec, dict):
            continue
        date_str = str(is_rec.get("date") or is_rec.get("calendarYear") or "")
        year  = date_str[:4] if len(date_str) >= 4 else f"Yr{i}"
        eps   = _sf(is_rec.get("eps") or is_rec.get("epsDiluted"))
        ebitda = _sf(is_rec.get("ebitda"))
        revenue = _sf(is_rec.get("revenue"))
        shares  = _sf(is_rec.get("weightedAverageShsOutDil") or is_rec.get("weightedAverageShsOut"))
        if eps is None and shares and shares > 0:
            ni = _sf(is_rec.get("netIncome"))
            if ni is not None:
                eps = ni / shares
        cf_rec = cf_l[i] if i < len(cf_l) and isinstance(cf_l[i], dict) else {}
        fcf    = _sf(cf_rec.get("freeCashFlow"))
        if fcf is None:
            op   = _sf(cf_rec.get("operatingCashFlow"))
            capx = _sf(cf_rec.get("capitalExpenditure"))
            if op is not None and capx is not None:
                fcf = op + capx
        km_rec = km_l[i] if i < len(km_l) and isinstance(km_l[i], dict) else {}
        price  = _price_by_year.get(year)
        if price is None:
            mkt = _sf(km_rec.get("marketCap"))
            if mkt and shares and shares > 0:
                price = mkt / shares
        # Prefer pre-computed multiples from key_metrics; fall back to manual
        pe        = _sf(km_rec.get("peRatio") or km_rec.get("priceEarningsRatio"))
        ev_ebitda = _sf(km_rec.get("enterpriseValueOverEBITDA") or km_rec.get("evToEbitda"))
        ps        = _sf(km_rec.get("priceToSalesRatio"))
        p_fcf     = _sf(km_rec.get("priceToFreeCashFlowsRatio") or km_rec.get("pfcfRatio"))
        if pe is None and price and eps and eps > 0:
            pe = price / eps
        if ps is None and price and revenue and shares and shares > 0:
            ps = price / (revenue / shares)
        if p_fcf is None and price and fcf and shares and shares > 0:
            fps = fcf / shares
            if fps > 0:
                p_fcf = price / fps
        if ev_ebitda is None and price and shares and ebitda and ebitda > 0:
            bs_rec  = bs_l[i] if i < len(bs_l) and isinstance(bs_l[i], dict) else {}
            mkt_cap = _sf(km_rec.get("marketCap")) or (price * shares)
            td      = _sf(bs_rec.get("totalDebt")) or 0.0
            cash    = _sf(bs_rec.get("cashAndCashEquivalents")) or 0.0
            ev_ebitda = (mkt_cap + td - cash) / ebitda
        _rows_newest.append({
            "year": year, "price": _strip_nan(price), "price_growth": None,
            "eps": _strip_nan(eps), "eps_growth": None,
            "ebitda_mm":  _strip_nan(ebitda  / 1e6) if ebitda  is not None else None,
            "revenue_mm": _strip_nan(revenue / 1e6) if revenue is not None else None,
            "fcf_mm":     _strip_nan(fcf     / 1e6) if fcf     is not None else None,
            "pe": _strip_nan(pe), "ev_ebitda": _strip_nan(ev_ebitda),
            "ps": _strip_nan(ps), "p_fcf": _strip_nan(p_fcf),
        })

    rows = list(reversed(_rows_newest))
    for i, row in enumerate(rows):
        if i == 0:
            continue
        prev = rows[i - 1]
        if row["price"] and prev["price"] and prev["price"] > 0:
            row["price_growth"] = _strip_nan(row["price"] / prev["price"] - 1)
        if row["eps"] and prev["eps"] and prev["eps"] > 0:
            row["eps_growth"] = _strip_nan(row["eps"] / prev["eps"] - 1)

    # ── TTM ───────────────────────────────────────────────────────────────────
    q_is4 = (norm.q_is or [])[:4]
    q_cf4 = (norm.q_cf or [])[:4]

    def _ttm_sum(lst, key):
        vals = [_sf(r.get(key)) for r in lst if isinstance(r, dict)]
        return sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None

    eps_ttm     = _ttm_sum(q_is4, "eps") or _ttm_sum(q_is4, "epsDiluted")
    ebitda_ttm  = _ttm_sum(q_is4, "ebitda")
    revenue_ttm = _ttm_sum(q_is4, "revenue")
    fcf_ttm     = _ttm_sum(q_cf4, "freeCashFlow")
    shares_ttm  = _sf((q_is4[0] if q_is4 else {}).get("weightedAverageShsOutDil")
                      or (q_is4[0] if q_is4 else {}).get("weightedAverageShsOut"))
    price_now   = _sf(ov.get("price"))
    if eps_ttm is None and shares_ttm and shares_ttm > 0:
        ni_ttm = _ttm_sum(q_is4, "netIncome")
        if ni_ttm is not None:
            eps_ttm = ni_ttm / shares_ttm
    q_bs0 = (norm.q_bs[0] if norm.q_bs else {})
    td_ttm   = _sf(q_bs0.get("totalDebt")) or 0.0
    cash_ttm = (_sf(q_bs0.get("cashAndCashEquivalents")) or 0.0) + \
               (_sf(q_bs0.get("shortTermInvestments")) or 0.0)
    net_debt_raw = (td_ttm - cash_ttm) if td_ttm else None
    pe_ttm = (price_now / eps_ttm) if (price_now and eps_ttm and eps_ttm > 0) else None
    ps_ttm = (price_now / (revenue_ttm / shares_ttm)) \
             if (price_now and revenue_ttm and shares_ttm and shares_ttm > 0) else None
    fcf_ps_ttm = (fcf_ttm / shares_ttm) if (fcf_ttm and shares_ttm and shares_ttm > 0) else None
    p_fcf_ttm  = (price_now / fcf_ps_ttm) if (price_now and fcf_ps_ttm and fcf_ps_ttm > 0) else None
    ev_ebitda_ttm = None
    if price_now and shares_ttm and ebitda_ttm and ebitda_ttm > 0:
        ev_ttm = price_now * shares_ttm + (net_debt_raw or 0)
        ev_ebitda_ttm = ev_ttm / ebitda_ttm
    ttm_row = {
        "year": "TTM", "price": _strip_nan(price_now), "price_growth": None,
        "eps": _strip_nan(eps_ttm), "eps_growth": None,
        "ebitda_mm":  _strip_nan(ebitda_ttm  / 1e6) if ebitda_ttm  is not None else None,
        "revenue_mm": _strip_nan(revenue_ttm / 1e6) if revenue_ttm is not None else None,
        "fcf_mm":     _strip_nan(fcf_ttm     / 1e6) if fcf_ttm     is not None else None,
        "pe": _strip_nan(pe_ttm), "ev_ebitda": _strip_nan(ev_ebitda_ttm),
        "ps": _strip_nan(ps_ttm), "p_fcf": _strip_nan(p_fcf_ttm),
    }

    # ── 10yr averages ─────────────────────────────────────────────────────────
    hist_10 = rows[-10:] if len(rows) > 10 else rows

    def _avg10(key):
        vals = [r[key] for r in hist_10 if isinstance(r.get(key), (int, float))]
        return sum(vals) / len(vals) if vals else None

    avg_10yr = {
        "year": "Avg. 10yr", "price": _strip_nan(_avg10("price")),
        "price_growth": _strip_nan(_avg10("price_growth")),
        "eps": _strip_nan(_avg10("eps")), "eps_growth": _strip_nan(_avg10("eps_growth")),
        "ebitda_mm": _strip_nan(_avg10("ebitda_mm")), "revenue_mm": _strip_nan(_avg10("revenue_mm")),
        "fcf_mm": _strip_nan(_avg10("fcf_mm")),
        "pe": _strip_nan(_avg10("pe")), "ev_ebitda": _strip_nan(_avg10("ev_ebitda")),
        "ps": _strip_nan(_avg10("ps")), "p_fcf": _strip_nan(_avg10("p_fcf")),
    }
    avg_ebitda_mm  = _avg10("ebitda_mm")
    avg_ebitda_raw = (avg_ebitda_mm * 1e6) if avg_ebitda_mm is not None else None
    return {
        "ticker":             ticker,
        "sector":             str(ov.get("sector")   or ""),
        "industry":           str(ov.get("industry") or ""),
        "currency":           str(ov.get("currency") or "USD"),
        "hist":               rows,
        "ttm":                ttm_row,
        "avg_10yr":           avg_10yr,
        "avg_eps":            _strip_nan(_avg10("eps")),
        "avg_ebitda_mm":      _strip_nan(avg_ebitda_mm),
        "avg_ebitda_raw":     _strip_nan(avg_ebitda_raw),
        "net_debt_mm":        _strip_nan(net_debt_raw / 1e6) if net_debt_raw is not None else None,
        "net_debt_raw":       _strip_nan(net_debt_raw),
        "shares_outstanding": _strip_nan(shares_ttm),
        "price_now":          _strip_nan(price_now),
    }


@app.get("/api/piotroski/{ticker}", tags=["Valuation"])
def piotroski(ticker: str):
    """
    Piotroski F-Score (9-point).
    Uses TTM and PREV TTM quarterly data; balance sheet snapshots for asset denominators.
    """
    raw_data = _gw.fetch_all(ticker)
    q_is = (raw_data.get("quarterly_income_statement") or [])
    q_bs = (raw_data.get("quarterly_balance_sheet")    or [])
    q_cf = (raw_data.get("quarterly_cash_flow")        or [])

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _ttm_sum(src, key, start=0):
        """Sum of 4 quarters starting at `start` (0 = newest)."""
        return _ssum(src[start:start + 4], key)

    def _bs_val(src, idx, key):
        """Balance sheet snapshot at quarterly index `idx`."""
        if idx < len(src) and isinstance(src[idx], dict):
            return _sf(src[idx].get(key))
        return None

    # ── Raw inputs ────────────────────────────────────────────────────────────
    # Income statement TTM / PREV TTM  (sums of 4 qtrs)
    ni_ttm  = _ttm_sum(q_is, "netIncome",    0)
    ni_prev = _ttm_sum(q_is, "netIncome",    4)
    gp_ttm  = _ttm_sum(q_is, "grossProfit",  0)
    gp_prev = _ttm_sum(q_is, "grossProfit",  4)
    rev_ttm = _ttm_sum(q_is, "revenue",      0)
    rev_prev= _ttm_sum(q_is, "revenue",      4)

    # Cash flow TTM / PREV TTM
    ocf_ttm  = _ttm_sum(q_cf, "operatingCashFlow", 0)
    ocf_prev = _ttm_sum(q_cf, "operatingCashFlow", 4)

    # Balance sheet snapshots (most-recent=0, ~1yr ago=4, ~2yr ago=8)
    ta_ttm   = _bs_val(q_bs, 0, "totalAssets")     # end of TTM window
    ta_prev  = _bs_val(q_bs, 4, "totalAssets")     # beginning of TTM (= end of PREV)
    ta_2prev = _bs_val(q_bs, 8, "totalAssets")     # beginning of PREV window
    ltd_ttm  = _bs_val(q_bs, 0, "longTermDebt")
    ltd_prev = _bs_val(q_bs, 4, "longTermDebt")
    ca_ttm   = _bs_val(q_bs, 0, "totalCurrentAssets")
    ca_prev  = _bs_val(q_bs, 4, "totalCurrentAssets")
    cl_ttm   = _bs_val(q_bs, 0, "totalCurrentLiabilities")
    cl_prev  = _bs_val(q_bs, 4, "totalCurrentLiabilities")
    sh_ttm   = _bs_val(q_bs, 0, "weightedAverageShsOutDil") or \
               _ttm_sum(q_is, "weightedAverageShsOutDil", 0)
    sh_prev  = _bs_val(q_bs, 4, "weightedAverageShsOutDil") or \
               _ttm_sum(q_is, "weightedAverageShsOutDil", 4)

    # ── Computed ratios ───────────────────────────────────────────────────────
    def _div(a, b):
        if a is None or b is None or b == 0:
            return None
        return a / b

    roa_ttm   = _div(ni_ttm,  ta_prev)
    roa_prev  = _div(ni_prev, ta_2prev)
    ocfr_ttm  = _div(ocf_ttm,  ta_prev)
    ocfr_prev = _div(ocf_prev, ta_2prev)

    # Leverage = LT Debt / Total Assets (using end-of-period assets)
    lev_ttm  = _div(ltd_ttm,  ta_ttm)
    lev_prev = _div(ltd_prev, ta_prev)

    cr_ttm   = _div(ca_ttm,  cl_ttm)
    cr_prev  = _div(ca_prev, cl_prev)

    gm_ttm   = _div(gp_ttm,  rev_ttm)
    gm_prev  = _div(gp_prev, rev_prev)

    # Asset turnover = Revenue / beginning-of-period assets
    at_ttm   = _div(rev_ttm,  ta_prev)
    at_prev  = _div(rev_prev, ta_2prev)

    # ── Scoring ───────────────────────────────────────────────────────────────
    def _score(condition) -> int:
        return 1 if condition else 0

    f1 = _score(roa_ttm  is not None and roa_ttm  > 0)
    f2 = _score(ocfr_ttm is not None and ocfr_ttm > 0)
    f3 = _score(roa_ttm  is not None and roa_prev  is not None and roa_ttm  > roa_prev)
    f4 = _score(ocfr_ttm is not None and roa_ttm   is not None and ocfr_ttm > roa_ttm)
    f5 = _score(lev_ttm  is not None and lev_prev  is not None and lev_ttm  < lev_prev)
    f6 = _score(cr_ttm   is not None and cr_prev   is not None and cr_ttm   > cr_prev)
    f7 = _score(sh_ttm   is not None and sh_prev   is not None and sh_ttm   <= sh_prev)
    f8 = _score(gm_ttm   is not None and gm_prev   is not None and gm_ttm   > gm_prev)
    f9 = _score(at_ttm   is not None and at_prev   is not None and at_ttm   > at_prev)

    total = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9

    def _pct(v):
        return round(v * 100, 4) if v is not None else None

    return {
        "ticker":   ticker.upper(),
        "currency": (raw_data.get("quarterly_income_statement") or [{}])[0].get("reportedCurrency", "USD"),

        # Raw inputs
        "net_income_ttm":           _strip_nan(ni_ttm),
        "net_income_prev":          _strip_nan(ni_prev),
        "total_assets_ttm":         _strip_nan(ta_ttm),
        "total_assets_prev":        _strip_nan(ta_prev),
        "total_assets_2prev":       _strip_nan(ta_2prev),
        "ocf_ttm":                  _strip_nan(ocf_ttm),
        "ocf_prev":                 _strip_nan(ocf_prev),
        "ltd_ttm":                  _strip_nan(ltd_ttm),
        "ltd_prev":                 _strip_nan(ltd_prev),
        "current_assets_ttm":       _strip_nan(ca_ttm),
        "current_assets_prev":      _strip_nan(ca_prev),
        "current_liabilities_ttm":  _strip_nan(cl_ttm),
        "current_liabilities_prev": _strip_nan(cl_prev),
        "shares_ttm":               _strip_nan(sh_ttm),
        "shares_prev":              _strip_nan(sh_prev),
        "gross_profit_ttm":         _strip_nan(gp_ttm),
        "gross_profit_prev":        _strip_nan(gp_prev),
        "revenue_ttm":              _strip_nan(rev_ttm),
        "revenue_prev":             _strip_nan(rev_prev),

        # Computed ratios (as percentages where applicable)
        "roa_ttm":             _strip_nan(_pct(roa_ttm)),
        "roa_prev":            _strip_nan(_pct(roa_prev)),
        "ocf_ratio_ttm":       _strip_nan(_pct(ocfr_ttm)),
        "ocf_ratio_prev":      _strip_nan(_pct(ocfr_prev)),
        "leverage_ttm":        _strip_nan(_pct(lev_ttm)),
        "leverage_prev":       _strip_nan(_pct(lev_prev)),
        "current_ratio_ttm":   _strip_nan(cr_ttm),
        "current_ratio_prev":  _strip_nan(cr_prev),
        "gross_margin_ttm":    _strip_nan(_pct(gm_ttm)),
        "gross_margin_prev":   _strip_nan(_pct(gm_prev)),
        "asset_turnover_ttm":  _strip_nan(at_ttm),
        "asset_turnover_prev": _strip_nan(at_prev),

        # Scores
        "f1_positive_roa":          f1,
        "f2_positive_ocf":          f2,
        "f3_higher_roa":            f3,
        "f4_accruals":              f4,
        "f5_lower_leverage":        f5,
        "f6_higher_current_ratio":  f6,
        "f7_less_shares":           f7,
        "f8_higher_gross_margin":   f8,
        "f9_higher_asset_turnover": f9,
        "total_score":              total,
    }


@app.get("/api/search", tags=["Meta"])
def search_tickers(q: str = Query("", min_length=1), limit: int = Query(8, le=20)):
    """
    Ticker / company name search.
    Primary: FMP /v3/search. Fallback: EODHD search when FMP returns 0 results.
    Returns list of {ticker, name, exchange, country, type}.
    """
    from backend.services.fmp_service import FMPService as _FMPSvc
    from backend.services.eodhd_service import EODHDService as _EodSvc
    from backend.services._key_loader import load_key as _lk

    # ── 1. FMP primary (stable search-symbol endpoint) ────────────────────────
    _fmp = _FMPSvc()
    raw = _fmp._get(f"{_fmp._STABLE}/search-symbol", {"query": q, "limit": limit})
    if isinstance(raw, list) and raw:
        return [
            {
                "ticker":   item.get("symbol", ""),
                "name":     item.get("name", ""),
                "exchange": item.get("exchange", ""),
                "country":  None,
                "type":     "ETF" if str(item.get("type", "")).lower() in ("etf", "fund") else "Equity",
            }
            for item in raw
            if item.get("symbol")
        ][:limit]

    # ── 2. EODHD fallback (non-US / FMP miss) ────────────────────────────────
    try:
        import requests as _req
        eodhd_key = _lk("EODHD_API_KEY")
        if not eodhd_key:
            return []
        r = _req.get(
            f"https://eodhistoricaldata.com/api/search/{q}",
            params={"api_token": eodhd_key, "limit": limit},
            timeout=6,
        )
        data = r.json() if r.ok else []
        if not isinstance(data, list):
            return []
        results = []
        for item in data:
            code = item.get("Code", "")
            exchange = item.get("Exchange", "")
            if not code:
                continue
            ticker = code if exchange.upper() == "US" else f"{code}.{exchange}"
            type_str = (item.get("Type") or "").lower()
            results.append({
                "ticker":   ticker,
                "name":     item.get("Name", ""),
                "exchange": exchange,
                "country":  item.get("Country"),
                "type":     "ETF" if "etf" in type_str or "fund" in type_str else "Equity",
            })
        return results[:limit]
    except Exception:
        return []


@app.get("/api/price-history/{ticker}", summary="Stock price + volume history", tags=["Profile"])
def get_price_history(ticker: str, range: str = Query("1Y")):
    """
    Returns price + volume series for the given range.
    1D/5D  -> FMP 15-min intraday
    others -> FMP historical-price-full with `from` date filter (direct call, no fetch_all)
    """
    from backend.services.fmp_service import FMPService as _FMPSvc
    _fmp = _FMPSvc()
    range = range.upper()
    today = datetime.date.today()

    try:
        if range in ("1D", "5D"):
            # Intraday 15-min bars
            raw = _fmp._get(f"{_fmp._V3}/historical-chart/15min/{ticker.upper()}", {})
            if not isinstance(raw, list):
                return {"ticker": ticker, "range": range, "points": []}
            raw = sorted(raw, key=lambda x: x.get("date", ""))
            days = 1 if range == "1D" else 5
            cutoff = (today - datetime.timedelta(days=days)).isoformat()
            points = [
                {"date": r["date"], "price": float(r.get("close", 0) or 0), "volume": r.get("volume")}
                for r in raw if r.get("date", "") >= cutoff
            ]
            return {"ticker": ticker, "range": range, "points": points}

        # All daily ranges: use FMPService.fetch_prices() (stable endpoint, proven)
        # fetch_prices returns newest-first; filter by cutoff then reverse to oldest-first
        if range == "1M":
            cutoff = (today - datetime.timedelta(days=35)).isoformat()
        elif range == "6M":
            cutoff = (today - datetime.timedelta(days=190)).isoformat()
        elif range == "YTD":
            cutoff = f"{today.year}-01-01"
        elif range == "1Y":
            cutoff = (today - datetime.timedelta(days=370)).isoformat()
        elif range == "5Y":
            cutoff = (today - datetime.timedelta(days=365 * 5 + 10)).isoformat()
        else:  # 10Y
            cutoff = (today - datetime.timedelta(days=365 * 10 + 10)).isoformat()

        # stable/historical-price-eod/light returns [{date, price, volume}] newest-first
        all_prices = _fmp._get(
            f"{_fmp._STABLE}/historical-price-eod/light",
            {"symbol": ticker.upper()},
        )
        if not isinstance(all_prices, list):
            return {"ticker": ticker, "range": range, "points": []}
        hist = [h for h in all_prices if h.get("date", "") >= cutoff]
        hist = sorted(hist, key=lambda x: x.get("date", ""))
        points = [
            {"date": h["date"], "price": float(h.get("price", 0) or 0), "volume": h.get("volume")}
            for h in hist
        ]
        return {"ticker": ticker, "range": range, "points": points}

    except Exception:
        return {"ticker": ticker, "range": range, "points": []}


@app.post("/api/news-insights/{ticker}", summary="AI news analysis via Claude Haiku", tags=["Profile"])
def get_news_insights(ticker: str, body: dict = Body(default={})):
    """
    Fetches 8 FMP news items, sends them to Claude Haiku with a buy-side analyst
    system prompt, and returns structured NewsInsight objects.
    """
    import json as _json
    from backend.services.fmp_service import FMPService as _FMPSvc
    from backend.services._key_loader import load_key as _lk

    _fmp = _FMPSvc()
    empty = {"ticker": ticker, "insights": []}

    try:
        # 1. Fetch news from FMP stable endpoint
        news_raw = _fmp._get(
            f"{_fmp._STABLE}/news/stock",
            {"symbols": ticker.upper(), "limit": 8},
        )
        if not isinstance(news_raw, list) or not news_raw:
            return empty

        news_items = [
            {
                "headline": item.get("title", ""),
                "date":     (item.get("publishedDate") or item.get("date") or "")[:10],
                "url":      item.get("url", ""),
            }
            for item in news_raw
            if item.get("title")
        ]
        if not news_items:
            return empty

        # 2. Build company context
        company_name = body.get("company_name", ticker)
        sector       = body.get("sector", "")
        industry     = body.get("industry", "")
        description  = body.get("description", "")

        context_str = (
            f"Company: {company_name} ({ticker.upper()})\n"
            f"Sector: {sector} | Industry: {industry}\n"
            f"Description: {description[:400]}"
        )

        user_msg = (
            f"Company context:\n{context_str}\n\n"
            f"Recent news headlines (analyze ALL of them):\n"
            + _json.dumps(news_items, indent=2)
        )

        # 3. Call Claude Haiku
        claude_key = _lk("CLAUDE_API_KEY")
        if not claude_key:
            return empty

        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=claude_key)

        system_prompt = """You are an institutional-grade Equity Research Analyst.

Your task: analyze the provided news headlines for the given company and produce a structured JSON response.

Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{
  "executive_summary": "2-3 sentence high-level strategic overview of the company's current situation based on these events.",
  "events": [
    {
      "headline": "copy the original headline",
      "date": "YYYY-MM-DD",
      "summary": "What happened? 1 clear sentence, investor-focused, present tense, ≤25 words.",
      "model_impact": "2-3 sentences: (1) Name the exact financial statement line affected (Revenue, EBITDA, Net Income, FCF, etc.). (2) Distinguish GAAP vs Non-GAAP if relevant and state whether it is recurring or one-time. (3) Conclude whether this changes the long-term DCF terminal value or is immaterial to the valuation model.",
      "educational_insight": "A 'Did you know?' style tip (1-2 sentences) linking this event to a core investment or accounting principle. Make it educational for a junior analyst.",
      "url": "copy the original url"
    }
  ]
}

Constraints:
- Output MUST be valid JSON. No conversational filler.
- Use precise Wall Street terminology.
- Cover all provided headlines."""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            timeout=30,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw_text = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed = _json.loads(raw_text)

        # Support both new {executive_summary, events} and legacy flat array
        if isinstance(parsed, list):
            return {"ticker": ticker, "executive_summary": "", "insights": parsed}

        events = parsed.get("events") or parsed.get("insights") or []
        return {
            "ticker":             ticker,
            "executive_summary":  parsed.get("executive_summary", ""),
            "insights":           events,
        }

    except Exception:
        return empty


@app.get("/api/ownership/{ticker}", summary="Ownership structure (insider + AI-estimated institutional/retail)", tags=["Profile"])
def get_ownership(ticker: str):
    import json as _json
    from backend.services.fmp_service import FMPService as _FMPSvc
    from backend.services._key_loader import load_key as _lk

    _fmp = _FMPSvc()
    t = ticker.upper()
    empty = {"ticker": ticker, "insider_pct": 0.0, "institutional_pct": 0.0, "retail_pct": 100.0, "power_dynamics": ""}

    try:
        # 1. Real insider % from SEC-sourced shares-float
        sf = _fmp._get(f"{_fmp._STABLE}/shares-float", {"symbol": t})
        if not isinstance(sf, list) or not sf:
            return empty
        row = sf[0]
        free_float = float(row.get("freeFloat", 100) or 100)
        insider_pct = round(100.0 - free_float, 2)

        # 2. Profile context for Claude
        prof = _fmp._get(f"{_fmp._STABLE}/profile", {"symbol": t})
        p = prof[0] if isinstance(prof, list) and prof else {}
        mkt_cap_b = round(float(p.get("marketCap", 0) or 0) / 1e9, 1)
        sector    = p.get("sector", "")
        beta      = float(p.get("beta", 1.0) or 1.0)
        ceo       = p.get("ceo", "")

        # 3. Claude estimates institutional/retail split of the float
        claude_key = _lk("CLAUDE_API_KEY")
        if not claude_key:
            return {**empty, "insider_pct": insider_pct, "retail_pct": round(100 - insider_pct, 2)}

        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=claude_key)

        prompt = (
            f"Company: {t} | Sector: {sector} | Market Cap: ${mkt_cap_b}B | Beta: {beta} | CEO: {ceo}\n"
            f"Known: insider/strategic ownership = {insider_pct:.1f}% (from SEC filings).\n"
            f"The remaining {free_float:.1f}% is public float.\n\n"
            "Estimate how that public float is split between institutional investors and retail investors.\n"
            "Base your estimate on typical ownership patterns for this company's size, sector, and profile.\n\n"
            "Return ONLY valid JSON, no markdown:\n"
            '{"institutional_pct": <number>, "retail_pct": <number>, "power_dynamics": "<2-sentence analysis of what this ownership structure means for investors. Mention insider alignment, institutional conviction, or retail sentiment as appropriate.>"}'
        )

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            timeout=20,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        ai = _json.loads(raw)
        inst  = float(ai.get("institutional_pct", 0) or 0)
        ret   = float(ai.get("retail_pct", 0) or 0)
        dyn   = ai.get("power_dynamics", "")

        # Normalise so all three sum to 100
        total = insider_pct + inst + ret
        if total > 0 and abs(total - 100) > 1:
            scale = 100 / total
            inst  = round(inst  * scale, 1)
            ret   = round(ret   * scale, 1)
            insider_pct = round(100 - inst - ret, 1)

        return {
            "ticker":            ticker,
            "insider_pct":       round(insider_pct, 1),
            "institutional_pct": round(inst, 1),
            "retail_pct":        round(ret, 1),
            "power_dynamics":    dyn,
        }

    except Exception:
        return empty


@app.post("/api/condense-description", summary="AI-condensed company description", tags=["Profile"])
def condense_description(body: dict = Body(default={})):
    import json as _json
    from backend.services._key_loader import load_key as _lk

    ticker      = body.get("ticker", "")
    description = body.get("description", "")
    sector      = body.get("sector", "")
    industry    = body.get("industry", "")

    if not description or len(description) < 100:
        return {"ticker": ticker, "summary": description}

    try:
        claude_key = _lk("CLAUDE_API_KEY")
        if not claude_key:
            return {"ticker": ticker, "summary": description[:400]}

        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=claude_key)

        prompt = (
            f"Company: {ticker} | Sector: {sector} | Industry: {industry}\n\n"
            f"Full description:\n{description}\n\n"
            "Rewrite this as a punchy, professional 3-sentence executive summary for a buy-side investor. "
            "Focus on: (1) core business model, (2) primary revenue drivers, (3) competitive positioning. "
            "Remove all boilerplate. Be direct and specific. Return ONLY the 3-sentence text, no JSON, no labels."
        )

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            timeout=20,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = resp.content[0].text.strip()
        return {"ticker": ticker, "summary": summary}

    except Exception:
        return {"ticker": ticker, "summary": description[:400]}



@app.get("/api/grok/sentiment/{ticker}", summary="Grok live sentiment badge", tags=["AI"])
def grok_sentiment(ticker: str):
    """
    Returns live sentiment analysis for *ticker* via Grok (xAI).
    Cached 15 minutes in memory.
    Never raises HTTP 5xx — returns error field on failure instead.
    """
    try:
        from backend.services.grok_service import get_sentiment
        return get_sentiment(ticker.strip().upper())
    except Exception as exc:
        # Swallow all errors — badge degrades gracefully
        return {
            "ticker": ticker.strip().upper(),
            "score": None, "label": "Unavailable",
            "reason": "", "source": "grok",
            "cached_until": None, "error": str(exc)[:120],
        }


@app.post("/api/gemini/audit/{ticker}", summary="Gemini 10-K filing auditor", tags=["AI"])
def gemini_audit(ticker: str, body: dict = None):
    """
    Runs Gemini analysis on the most recent 10-K filing for *ticker*.
    Optionally accepts { "filing_url": "..." } in the request body.
    Cached 1 hour in memory.
    """
    filing_url = (body or {}).get("filing_url")
    try:
        from backend.services.pdf_auditor_service import audit_filing
        return audit_filing(ticker.strip().upper(), filing_url)
    except Exception as exc:
        return {
            "ticker": ticker.strip().upper(), "filing_url": filing_url,
            "summary": "", "risk_factors": [], "red_flags": [], "moat_signals": [],
            "model": "gemini-1.5-flash", "error": str(exc)[:200],
        }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": app.version}
