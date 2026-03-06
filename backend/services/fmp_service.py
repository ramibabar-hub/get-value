"""
backend/services/fmp_service.py
Financial Modeling Prep data service — no Streamlit dependency.

Provides fetch_all() and fetch_overview() returning the canonical
data format consumed by InsightsAgent / logic_engine.
"""

import requests
from concurrent.futures import ThreadPoolExecutor

from ._key_loader import load_key


class FMPService:
    _STABLE = "https://financialmodelingprep.com/stable"
    _V3     = "https://financialmodelingprep.com/api/v3"

    def __init__(self):
        self.api_key = load_key("FMP_API_KEY")
        if not self.api_key:
            print("[FMPService] WARNING: FMP_API_KEY not found")

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get(self, url: str, params: dict, timeout: int = 10):
        """GET → parsed JSON or None."""
        try:
            res = requests.get(url, params={**params, "apikey": self.api_key},
                               timeout=timeout)
            return res.json()
        except Exception as exc:
            print(f"[FMPService] GET {url} ERROR: {exc}")
            return None

    def _first(self, body) -> dict:
        if isinstance(body, list) and body:
            return body[0]
        if isinstance(body, dict) and body:
            return body
        return {}

    # ── financial statements ──────────────────────────────────────────────────

    def fetch_statements(self, endpoint: str, ticker: str,
                         quarterly: bool = False, limit: int = 15) -> list:
        """
        Fetch one financial statement endpoint with stable → v3 fallback.

        Returns a list of period dicts (newest first) or [].
        """
        if not self.api_key:
            return []

        params: dict = {"symbol": ticker, "limit": limit}
        if quarterly:
            params["period"] = "quarter"

        # Try 1: stable
        body = self._get(f"{self._STABLE}/{endpoint}", params)
        if isinstance(body, list) and body:
            return body

        # Try 2: v3 fallback (required for some non-US tickers)
        body = self._get(f"{self._V3}/{endpoint}", params)
        if isinstance(body, list) and body:
            return body

        return []

    def fetch_historical_prices(self, ticker: str) -> list:
        """Return flat list of daily price dicts with stable → v3 fallback."""
        if not self.api_key:
            return []

        def _unwrap(body):
            if isinstance(body, list) and body:
                return body
            if isinstance(body, dict):
                h = body.get("historical") or body.get("historicalStockList") or []
                if isinstance(h, list) and h:
                    return h
            return []

        body = self._get(f"{self._STABLE}/historical-price-full",
                         {"symbol": ticker})
        data = _unwrap(body)
        if data:
            return data

        body = self._get(f"{self._V3}/historical-price-full/{ticker}", {})
        return _unwrap(body)

    # ── overview (parallel fetch) ─────────────────────────────────────────────

    def _fetch_quote(self, ticker: str) -> dict:
        return self._first(self._get(f"{self._STABLE}/quote", {"symbol": ticker}))

    def _fetch_profile(self, ticker: str) -> dict:
        return self._first(self._get(f"{self._STABLE}/profile", {"symbol": ticker}))

    def _fetch_income_latest(self, ticker: str) -> dict:
        body = self._get(f"{self._STABLE}/income-statement",
                         {"symbol": ticker, "limit": 1})
        return self._first(body)

    def _fetch_key_metrics_ttm(self, ticker: str) -> dict:
        return self._first(self._get(f"{self._STABLE}/key-metrics-ttm",
                                     {"symbol": ticker}))

    def _fetch_shares_float(self, ticker: str) -> dict:
        return self._first(self._get(f"{self._STABLE}/shares-float",
                                     {"symbol": ticker}))

    def fetch_overview(self, ticker: str) -> dict:
        """
        Merge profile + quote + income + key-metrics-ttm + shares-float
        in parallel. Returns a flat dict with normalised field names.
        """
        t = ticker.strip().upper()
        if not self.api_key or not t:
            return {}

        with ThreadPoolExecutor(max_workers=5) as ex:
            f_prof  = ex.submit(self._fetch_profile,          t)
            f_quote = ex.submit(self._fetch_quote,            t)
            f_inc   = ex.submit(self._fetch_income_latest,    t)
            f_km    = ex.submit(self._fetch_key_metrics_ttm,  t)
            f_sf    = ex.submit(self._fetch_shares_float,     t)

        profile = f_prof.result()  or {}
        quote   = f_quote.result() or {}
        income  = f_inc.result()   or {}
        km      = f_km.result()    or {}
        sf      = f_sf.result()    or {}

        data = dict(profile)

        # Normalise profile field names (FMP profile uses different names than quote)
        # These are fallbacks — the quote block below will override with live data if available
        if not data.get("mktCap"):
            data["mktCap"] = data.get("marketCap")
        if not data.get("volAvg"):
            data["volAvg"] = data.get("averageVolume") or data.get("avgVolume")
        if not data.get("changesPercentage"):
            data["changesPercentage"] = data.get("changePercentage") or 0

        # Quote overrides for live price / pe / eps
        # New stable API uses "changePercentage" (no 's'); handle both
        for field in ("price", "changesPercentage", "change", "eps", "pe"):
            if quote.get(field) is not None:
                data[field] = quote[field]
        if quote.get("changePercentage") is not None:
            data["changesPercentage"] = quote["changePercentage"]
        if quote.get("avgVolume"):
            data["volAvg"] = quote["avgVolume"]
        if quote.get("marketCap"):
            data["mktCap"] = quote["marketCap"]

        data["earningsAnnouncement"] = (
            quote.get("earningsAnnouncement")
            or quote.get("nextEarningsDate")
            or data.get("earningsAnnouncement")
        )

        # Fill P/E gap — try key-metrics earningsYieldTTM, then price÷EPS
        _pe = data.get("pe")
        if (not _pe or _pe < 0) and km.get("peRatioTTM") and km["peRatioTTM"] > 0:
            data["pe"] = km["peRatioTTM"]
        if not data.get("pe") or data["pe"] < 0:
            ey = km.get("earningsYieldTTM")
            try:
                if ey and float(ey) > 0:
                    data["pe"] = round(1.0 / float(ey), 2)
            except (TypeError, ValueError):
                pass
        if not data.get("beta") and km.get("beta"):
            data["beta"] = km["beta"]

        # Shares float / short interest
        if not data.get("shortPercent"):
            data["shortPercent"] = (
                sf.get("shortPercentOfFloat")
                or sf.get("shortPercent")
                or sf.get("shortRatio")
                or data.get("shortRatio")
            )

        # Institutional / insider ownership — FMP profile may include these as decimals
        def _pct_from_decimal(raw) -> float | None:
            if raw is None:
                return None
            try:
                f = float(raw)
                return round(f * 100, 4) if f < 1.5 else f
            except (TypeError, ValueError):
                return None

        if not data.get("heldByInsiders"):
            data["heldByInsiders"] = _pct_from_decimal(
                data.get("institutionalHolderProportion")
                or data.get("insiderOwnership")
            )
        if not data.get("heldByInstitutions"):
            data["heldByInstitutions"] = _pct_from_decimal(
                data.get("institutionalOwnershipProportion")
                or data.get("institutionalHolderProportion")
            )

        # Fiscal year + best EPS
        fy = (str(income.get("fiscalYear")    or "")
              or str(income.get("calendarYear") or "")
              or str(income.get("date")         or "")[:4])
        data["_latestFiscalYear"] = fy or "N/A"
        data["_eps"] = (
            data.get("eps")
            or income.get("epsDiluted")
            or income.get("eps")
            or km.get("netIncomePerShareTTM")
        )
        data.setdefault("_latestFiscalYear", "N/A")
        data.setdefault("_eps", None)
        return data

    # ── bulk fetch ────────────────────────────────────────────────────────────

    def fetch_all(self, ticker: str) -> dict:
        """Return the canonical data dict consumed by InsightsAgent."""
        t = ticker.strip().upper()
        return {
            "annual_income_statement":    self.fetch_statements("income-statement",        t),
            "quarterly_income_statement": self.fetch_statements("income-statement",        t, True),
            "annual_balance_sheet":       self.fetch_statements("balance-sheet-statement", t),
            "quarterly_balance_sheet":    self.fetch_statements("balance-sheet-statement", t, True),
            "annual_cash_flow":           self.fetch_statements("cash-flow-statement",     t),
            "quarterly_cash_flow":        self.fetch_statements("cash-flow-statement",     t, True),
            "annual_ratios":              self.fetch_statements("ratios",                  t),
            "annual_key_metrics":         self.fetch_statements("key-metrics",             t),
            "quarterly_key_metrics":      self.fetch_statements("key-metrics",             t, True),
            "historical_prices":          self.fetch_historical_prices(t),
        }
