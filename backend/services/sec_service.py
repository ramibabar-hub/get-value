"""
backend/services/sec_service.py

Filing link resolver — routes by ticker type:
  • US tickers  (no dot)  -> SEC EDGAR iXBRL viewer URLs
  • Intl tickers (dot)    -> EODHD fundamentals for available periods +
                            exchange-specific regulatory-filing portal links

Period labels match the column headers produced by the FinancialsTab:
  Annual    -> "2024", "2023", …
  Quarterly -> "Q1 2024", "Q2 2024", …  (calendar quarter of period-end date)

Public entry-point: get_filing_links(ticker)
"""
from __future__ import annotations

import logging
import time
from datetime import date

import requests

log = logging.getLogger(__name__)

EDGAR_UA    = "getValue/1.0 contact@getvalue.app"   # SEC requires this
EDGAR_BASE  = "https://data.sec.gov"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
EODHD_BASE  = "https://eodhd.com/api"

# ── In-memory CIK lookup table (refreshed hourly) ─────────────────────────────

_cik_map: dict[str, int] = {}
_cik_ts:  float          = 0.0
_CIK_TTL                 = 3600   # seconds


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_UA}


def _refresh_cik_map() -> None:
    global _cik_map, _cik_ts
    now = time.time()
    if _cik_map and now - _cik_ts < _CIK_TTL:
        return
    try:
        r = requests.get(TICKERS_URL, headers=_headers(), timeout=12)
        r.raise_for_status()
        _cik_map = {
            v["ticker"].upper(): int(v["cik_str"])
            for v in r.json().values()
        }
        _cik_ts = now
        log.debug("SEC CIK map refreshed (%d tickers)", len(_cik_map))
    except Exception as exc:
        log.warning("SEC CIK map refresh failed: %s", exc)


def _cik_for(ticker: str) -> int | None:
    _refresh_cik_map()
    return _cik_map.get(ticker.upper())


# ── Period label helpers ───────────────────────────────────────────────────────

def _quarter(month: int) -> int:
    return (month - 1) // 3 + 1


def _period_label(period_str: str, form: str) -> str | None:
    """
    Convert periodOfReport (YYYY-MM-DD) + SEC form type -> FinancialsTab column label.
    Returns None for forms other than 10-K / 10-Q.
    """
    if form not in ("10-K", "10-Q"):
        return None
    try:
        d = date.fromisoformat(period_str)
    except ValueError:
        return None
    if form == "10-K":
        return str(d.year)
    return f"Q{_quarter(d.month)} {d.year}"


# ── Public API ─────────────────────────────────────────────────────────────────

def get_sec_filing_links(ticker: str) -> dict[str, str]:
    """
    Returns {period_label: iXBRL_viewer_url} for the most recent 10-K and
    10-Q filings (up to ~22 entries covering 10 annual + 12 quarterly periods).

    Returns {} for:
      - International tickers (ticker contains '.')
      - Tickers not found in the SEC company tickers index
      - Any network / parse error
    """
    if "." in ticker:
        return {}   # international — SEC EDGAR not applicable

    cik = _cik_for(ticker.upper())
    if cik is None:
        log.info("SEC: no CIK found for %s", ticker)
        return {}

    cik_padded = str(cik).zfill(10)
    try:
        r = requests.get(
            f"{EDGAR_BASE}/submissions/CIK{cik_padded}.json",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        recent = r.json().get("filings", {}).get("recent", {})
    except Exception as exc:
        log.warning("SEC submissions fetch failed for %s: %s", ticker, exc)
        return {}

    forms   = recent.get("form",            [])
    periods = recent.get("periodOfReport",  [])
    accnums = recent.get("accessionNumber", [])
    docs    = recent.get("primaryDocument", [])

    result: dict[str, str] = {}
    for form, period, acc, doc in zip(forms, periods, accnums, docs):
        label = _period_label(period, form)
        if label is None or label in result:
            continue
        acc_flat = acc.replace("-", "")
        result[label] = (
            f"https://www.sec.gov/ix?doc=/Archives/edgar/data"
            f"/{cik}/{acc_flat}/{doc}"
        )
        if len(result) >= 22:   # cap: ~10 annual + 12 quarterly
            break

    log.debug("SEC filing links for %s: %d periods", ticker, len(result))
    return result


# ══ International tickers — EODHD reports ═════════════════════════════════════

# Exchange suffix -> best available regulatory-filing portal URL.
# {code} is substituted with the ticker code (without exchange suffix).
_EXCHANGE_PORTALS: dict[str, str] = {
    "TA":    "https://www.magna.isa.gov.il/",
    "L":     "https://www.londonstockexchange.com/stock/{code_l}/company-page",
    "IL":    "https://www.londonstockexchange.com/stock/{code_l}/company-page",
    "DE":    "https://www.boerse-frankfurt.de/equity/{code_l}-shares",
    "XETRA": "https://www.boerse-frankfurt.de/equity/{code_l}-shares",
    "PA":    "https://live.euronext.com/en/product/equities/{code}-XPAR",
    "AS":    "https://live.euronext.com/en/product/equities/{code}-XAMS",
    "BR":    "https://live.euronext.com/en/product/equities/{code}-XBRU",
    "MI":    "https://www.borsaitaliana.it/borsa/azioni/scheda/{code}.html",
    "MC":    "https://www.bolsaymercados.es/",
    "SW":    "https://www.six-group.com/en/products-services/the-swiss-stock-exchange.html",
    "HK":    "https://www.hkexnews.hk/",
    "TO":    "https://money.tmx.com/en/quote/{code}",
    "V":     "https://money.tmx.com/en/quote/{code}.V",
    "AU":    "https://www2.asx.com.au/markets/company/{code_l}",
    "SHG":   "https://www.sse.com.cn/",
    "SHE":   "https://www.szse.cn/",
    "KO":    "https://kind.krx.co.kr/",
    "TW":    "https://mops.twse.com.tw/",
    "NS":    "https://www.nseindia.com/",
    "BO":    "https://www.bseindia.com/",
}


def _portal_url(code: str, exchange: str) -> str:
    """Return the best available filing portal URL for this exchange."""
    tmpl = _EXCHANGE_PORTALS.get(
        exchange,
        "https://eodhd.com/financial-history/{code}.{exchange}/",
    )
    return tmpl.format(code=code, code_l=code.lower(), exchange=exchange)


def _eodhd_api_key() -> str | None:
    try:
        from backend.services._key_loader import load_key
        return load_key("EODHD_API_KEY") or None
    except Exception:
        return None


def get_eodhd_filing_links(ticker: str) -> dict[str, str]:
    """
    For international tickers: query EODHD fundamentals (Income Statement
    filter) to discover available annual and quarterly period dates, then
    map them to FinancialsTab column labels and pair with exchange-specific
    regulatory filing portal URLs.

    Returns {} on any error or if the ticker is not international.
    """
    if "." not in ticker:
        return {}

    code, exchange = ticker.rsplit(".", 1)
    api_key = _eodhd_api_key()
    if not api_key:
        log.warning("EODHD_API_KEY not set - cannot fetch filing links for %s", ticker)
        return {}

    try:
        r = requests.get(
            f"{EODHD_BASE}/fundamental/{code}.{exchange}",
            params={"api_token": api_key, "fmt": "json",
                    "filter": "Financials::Income_Statement"},
            headers={"User-Agent": EDGAR_UA},
            timeout=10,
        )
        if r.status_code != 200:
            log.info("EODHD fundamental %s: HTTP %s", ticker, r.status_code)
            return {}
        data: dict = r.json()
    except Exception as exc:
        log.warning("EODHD fundamental fetch failed for %s: %s", ticker, exc)
        return {}

    portal = _portal_url(code, exchange)
    result: dict[str, str] = {}

    # Annual periods — "yearly" dict keys are YYYY-MM-DD fiscal year-end dates
    yearly: dict = data.get("yearly", {})
    for date_key in sorted(yearly.keys(), reverse=True)[:10]:
        try:
            d = date.fromisoformat(date_key)
            label = str(d.year)
            if label not in result:
                result[label] = portal
        except ValueError:
            pass

    # Quarterly periods — "quarterly" dict keys are quarter-end dates
    quarterly: dict = data.get("quarterly", {})
    for date_key in sorted(quarterly.keys(), reverse=True)[:12]:
        try:
            d = date.fromisoformat(date_key)
            label = f"Q{_quarter(d.month)} {d.year}"
            if label not in result:
                result[label] = portal
        except ValueError:
            pass

    log.debug("EODHD filing links for %s: %d periods", ticker, len(result))
    return result


# ══ Public entry-point ════════════════════════════════════════════════════════

def get_filing_links(ticker: str) -> dict[str, str]:
    """
    Route to the correct filing-link source:
      • No dot  -> US ticker -> SEC EDGAR (exact iXBRL viewer URLs)
      • Has dot -> Intl ticker -> EODHD fundamentals + exchange portal links
    """
    if "." in ticker:
        return get_eodhd_filing_links(ticker)
    return get_sec_filing_links(ticker)
