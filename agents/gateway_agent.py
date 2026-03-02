import os
import json
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor

def _load_api_key():
    """
    Priority: st.secrets → os.environ → .env file.
    This ensures the key is found both in Streamlit Cloud and in local dev
    even when .streamlit/secrets.toml doesn't exist yet.
    """
    # 1. Streamlit secrets (Cloud / .streamlit/secrets.toml)
    try:
        raw = st.secrets.get("FMP_API_KEY", "")
        if raw:
            return "".join(raw.split()).strip('"').strip("'")
    except Exception:
        pass
    # 2. Environment variable
    raw = os.environ.get("FMP_API_KEY", "")
    if raw:
        return raw.strip()
    # 3. Read .env file directly
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("FMP_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


class GatewayAgent:

    # Exchange short-name → emoji flag (used in search dropdown).
    # ISO-2 country codes are included as fallbacks so that when FMP
    # returns a bare country code (e.g. "IL", "US") instead of an exchange
    # short-name, the flag lookup still resolves to the correct emoji.
    EXCHANGE_FLAGS = {
        # ── ISO-2 country-code fallbacks ──────────────────────────────────────
        "US": "🇺🇸", "GB": "🇬🇧", "IL": "🇮🇱", "DE": "🇩🇪", "FR": "🇫🇷",
        "CN": "🇨🇳", "JP": "🇯🇵", "CA": "🇨🇦", "AU": "🇦🇺", "IN": "🇮🇳",
        "KR": "🇰🇷", "SE": "🇸🇪", "CH": "🇨🇭", "NL": "🇳🇱", "SG": "🇸🇬",
        "BR": "🇧🇷", "TW": "🇹🇼", "HK": "🇭🇰", "NO": "🇳🇴", "DK": "🇩🇰",
        "FI": "🇫🇮", "IE": "🇮🇪", "IT": "🇮🇹", "ES": "🇪🇸", "MX": "🇲🇽",
        "ZA": "🇿🇦", "RU": "🇷🇺", "SA": "🇸🇦", "AR": "🇦🇷", "CL": "🇨🇱",
        "PT": "🇵🇹", "BE": "🇧🇪", "AT": "🇦🇹", "NZ": "🇳🇿", "TH": "🇹🇭",
        "ID": "🇮🇩", "MY": "🇲🇾", "PH": "🇵🇭", "PK": "🇵🇰",
        # ── Exchange short-names ───────────────────────────────────────────────
        # United States
        "NASDAQ": "🇺🇸", "NYSE": "🇺🇸", "AMEX": "🇺🇸", "NYSEARCA": "🇺🇸",
        "NYSEMKT": "🇺🇸", "OTC": "🇺🇸", "OTCBB": "🇺🇸", "PINK": "🇺🇸", "CBOE": "🇺🇸",
        # Israel
        "TASE": "🇮🇱",
        # United Kingdom
        "LSE": "🇬🇧", "AIM": "🇬🇧",
        # Germany
        "XETRA": "🇩🇪", "FSE": "🇩🇪", "FWB": "🇩🇪",
        # Canada
        "TSX": "🇨🇦", "TSXV": "🇨🇦", "CNQ": "🇨🇦",
        # Australia
        "ASX": "🇦🇺",
        # Japan
        "TSE": "🇯🇵", "OSE": "🇯🇵", "TYO": "🇯🇵",
        # South Korea
        "KSE": "🇰🇷", "KOSDAQ": "🇰🇷", "KRX": "🇰🇷",
        # Hong Kong
        "HKEX": "🇭🇰", "HKSE": "🇭🇰",
        # Singapore
        "SGX": "🇸🇬",
        # India
        "NSE": "🇮🇳", "BSE": "🇮🇳", "NSEI": "🇮🇳",
        # Switzerland
        "SIX": "🇨🇭",
        # Norway
        "OSL": "🇳🇴",
        # Sweden
        "OMX": "🇸🇪", "STO": "🇸🇪",
        # Finland
        "HEL": "🇫🇮",
        # Denmark
        "CPH": "🇩🇰",
        # China
        "SHH": "🇨🇳", "SHZ": "🇨🇳", "SSE": "🇨🇳", "SZSE": "🇨🇳",
        # Taiwan
        "TWSE": "🇹🇼", "TPE": "🇹🇼",
        # Italy
        "BIT": "🇮🇹", "MIL": "🇮🇹",
        # Spain
        "BME": "🇪🇸", "MCE": "🇪🇸",
        # Netherlands
        "AMS": "🇳🇱",
        # France
        "PAR": "🇫🇷",
        # Brazil
        "BOVESPA": "🇧🇷", "B3": "🇧🇷",
        # South Africa
        "JSE": "🇿🇦",
        # Russia
        "MCX": "🇷🇺", "MOEX": "🇷🇺",
        # Saudi Arabia
        "SAU": "🇸🇦", "TADAWUL": "🇸🇦",
        # Mexico
        "BMV": "🇲🇽",
        # Belgium
        "BRU": "🇧🇪",
        # Portugal
        "LIS": "🇵🇹",
        # Austria
        "VIE": "🇦🇹",
        # New Zealand
        "NZX": "🇳🇿",
        # Thailand
        "SET": "🇹🇭",
        # Indonesia
        "IDX": "🇮🇩",
        # Malaysia
        "KLS": "🇲🇾", "KLSE": "🇲🇾",
        # Philippines
        "PSE": "🇵🇭",
        # Argentina
        "BCBA": "🇦🇷",
        # Chile
        "BCS": "🇨🇱",
        # Euronext (generic)
        "EURONEXT": "🇪🇺",
    }

    def __init__(self):
        self.api_key = _load_api_key()
        # FMP deprecated /api/v3 on Aug 31 2025 — use /stable
        self.base_url = "https://financialmodelingprep.com/stable"
        print(f"[GatewayAgent] base_url={self.base_url}")
        if not self.api_key:
            print("[GatewayAgent] WARNING: FMP_API_KEY not found in secrets, env, or .env")
        else:
            print(f"[GatewayAgent] API key loaded (ends: ...{self.api_key[-4:]})")

    # ── internal GET helper ───────────────────────────────────────────────────
    def _get(self, path: str, params: dict, timeout: int = 8):
        """Raw GET, returns parsed JSON or None on error."""
        try:
            full_url = f"{self.base_url}/{path}"
            safe_params = {k: v for k, v in params.items() if k != "apikey"}
            print(f"[GatewayAgent] GET {full_url} params={safe_params}")
            res = requests.get(
                full_url,
                params={**params, "apikey": self.api_key},
                timeout=timeout,
            )
            print(f"[GatewayAgent] RESPONSE status={res.status_code} body_preview={str(res.text)[:200]}")
            return res.json()
        except Exception as e:
            print(f"[GatewayAgent] GET /{path} ERROR: {e}")
            return None

    def _first(self, body) -> dict:
        """Return first item from list, or the dict itself, or {}."""
        if isinstance(body, list) and body:
            return body[0]
        if isinstance(body, dict) and body:
            return body
        return {}

    # ── financial statement bulk fetch ────────────────────────────────────────
    def fetch_data(self, path, ticker, is_quarterly=False):
        if not self.api_key:
            print(f"[GatewayAgent] No API key — skipping {path}/{ticker}")
            return []
        params = {"symbol": ticker, "apikey": self.api_key, "limit": 15}
        if is_quarterly:
            params["period"] = "quarter"
        label = f"{'Q' if is_quarterly else 'A'}/{path}/{ticker}"

        # Try 1: /stable endpoint
        url = f"{self.base_url}/{path}"
        print(f"[GatewayAgent] FETCH {label} via stable")
        try:
            res = requests.get(url, params=params, timeout=10)
            body = res.json()
            if isinstance(body, list) and body:
                print(f"[GatewayAgent] OK stable {label}: {len(body)} records")
                return body
            print(f"[GatewayAgent] EMPTY stable {label} status={res.status_code} — trying v3")
        except Exception as e:
            print(f"[GatewayAgent] ERROR stable {label}: {e}")

        # Try 2: /api/v3 fallback — required for non-US tickers (.TA, .L, .DE etc.)
        try:
            v3_url = f"https://financialmodelingprep.com/api/v3/{path}"
            print(f"[GatewayAgent] FETCH {label} via v3")
            res = requests.get(v3_url, params=params, timeout=10)
            body = res.json()
            if isinstance(body, list) and body:
                print(f"[GatewayAgent] OK v3 {label}: {len(body)} records")
                return body
            print(f"[GatewayAgent] EMPTY v3 {label} status={res.status_code}")
        except Exception as e:
            print(f"[GatewayAgent] ERROR v3 {label}: {e}")

        return []

    def fetch_historical_prices(self, ticker: str) -> list:
        """Fetch daily historical prices for a ticker.

        Returns a flat list of dicts: [{date, open, high, low, close, adjClose, ...}].
        FMP wraps the list under {"historical": [...]} — this method unwraps it.
        Tries the /stable endpoint first, falls back to /api/v3.
        """
        if not self.api_key:
            return []

        def _extract(body):
            if isinstance(body, list) and body:
                return body
            if isinstance(body, dict):
                hist = body.get("historical") or body.get("historicalStockList", [])
                if isinstance(hist, list) and hist:
                    return hist
            return []

        # Try 1: stable
        try:
            url  = f"{self.base_url}/historical-price-full"
            res  = requests.get(url, params={"symbol": ticker, "apikey": self.api_key},
                                timeout=15)
            data = _extract(res.json())
            if data:
                print(f"[GatewayAgent] historical-prices stable {ticker}: {len(data)} records")
                return data
            print(f"[GatewayAgent] historical-prices stable {ticker}: empty — trying v3")
        except Exception as e:
            print(f"[GatewayAgent] historical-prices stable {ticker} ERROR: {e}")

        # Try 2: v3 (ticker in path)
        try:
            url  = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}"
            res  = requests.get(url, params={"apikey": self.api_key}, timeout=15)
            data = _extract(res.json())
            if data:
                print(f"[GatewayAgent] historical-prices v3 {ticker}: {len(data)} records")
                return data
            print(f"[GatewayAgent] historical-prices v3 {ticker}: empty")
        except Exception as e:
            print(f"[GatewayAgent] historical-prices v3 {ticker} ERROR: {e}")

        return []

    def fetch_all(self, ticker):
        return {
            "annual_income_statement":    self.fetch_data("income-statement",       ticker),
            "quarterly_income_statement": self.fetch_data("income-statement",       ticker, True),
            "annual_balance_sheet":       self.fetch_data("balance-sheet-statement",ticker),
            "quarterly_balance_sheet":    self.fetch_data("balance-sheet-statement",ticker, True),
            "annual_cash_flow":           self.fetch_data("cash-flow-statement",    ticker),
            "quarterly_cash_flow":        self.fetch_data("cash-flow-statement",    ticker, True),
            "annual_ratios":              self.fetch_data("ratios",                 ticker),
            # key-metrics: per-period price, market cap, employees, and pre-computed multiples
            "annual_key_metrics":         self.fetch_data("key-metrics",            ticker),
            "quarterly_key_metrics":      self.fetch_data("key-metrics",            ticker, True),
            # daily price history — used by cf_irr_tab for Dec-31 stock prices in Table 3.1
            "historical_prices":          self.fetch_historical_prices(ticker),
        }

    # ── autocomplete search ───────────────────────────────────────────────────

    # Exchange suffix → FMP exchangeShortName (used only when user explicitly
    # types a suffix like NICE.TA or BMW.DE — NOT for fallback guessing)
    SUFFIX_TO_EXCHANGE = {
        "TA": "TASE", "L": "LSE", "DE": "XETRA", "PA": "PAR",
        "AS": "AMS",  "MI": "BIT", "MC": "BME",  "SW": "SIX",
        "TO": "TSX",  "AX": "ASX", "HK": "HKEX", "T":  "TSE",
        "KS": "KSE",  "NS": "NSE", "BO": "BSE",  "SI": "SGX",
    }

    def search_ticker(self, query: str, limit: int = 20) -> list:
        """
        Autocomplete: returns [{symbol, name, exchangeShortName, flag}].
        - If user typed an explicit suffix (e.g. NICE.TA): profile lookup first.
        - Otherwise: plain FMP /search with limit=20. No suffix guessing —
          that caused European-only results (AAPL.L, AAPL.DE) for US tickers.
        """
        if not self.api_key or not query.strip():
            return []

        results = []
        seen    = set()
        q       = query.strip()

        def _add(items):
            if not isinstance(items, list):
                return
            for item in items:
                sym = str(item.get("symbol", "")).upper()
                if sym and sym not in seen:
                    seen.add(sym)
                    exch = str(item.get("exchangeShortName") or
                               item.get("stockExchange") or "").upper()
                    item["flag"] = self.EXCHANGE_FLAGS.get(exch, "🏳️")
                    results.append(item)

        # Step 1: explicit suffix (NICE.TA / BMW.DE) → profile lookup first
        if "." in q:
            suffix = q.rsplit(".", 1)[-1].upper()
            if suffix in self.SUFFIX_TO_EXCHANGE:
                profile = self._get("profile", {"symbol": q.upper()})
                if isinstance(profile, list) and profile:
                    p = profile[0]
                    _add([{
                        "symbol":            p.get("symbol", q.upper()),
                        "name":              p.get("companyName", ""),
                        "exchangeShortName": p.get("exchangeShortName",
                                                self.SUFFIX_TO_EXCHANGE[suffix]),
                        "stockExchange":     p.get("exchange", ""),
                        "currency":         p.get("currency", ""),
                    }])

        # Step 2: FMP stable uses "search-ticker" not "search"
        body = self._get("search-ticker", {"query": q, "limit": limit})
        print(f"[DEBUG] search-ticker result count: {len(body) if isinstance(body, list) else body}")
        if not isinstance(body, list) or len(body) == 0:
            body = self._get("search", {"query": q, "limit": limit})
            print(f"[DEBUG] search fallback result count: {len(body) if isinstance(body, list) else body}")
        _add(body if isinstance(body, list) else [])

        return results

    # ── single-endpoint fetchers (used by fetch_overview) ────────────────────
    def fetch_profile(self, ticker: str) -> dict:
        """Base company profile — name, sector, country, beta, volAvg, etc."""
        if not self.api_key or not ticker.strip():
            return {}
        return self._first(self._get("profile", {"symbol": ticker.upper()}))

    def _fetch_quote(self, ticker: str) -> dict:
        """Real-time quote — price, changesPercentage, avgVolume, eps, pe, earningsAnnouncement."""
        return self._first(self._get("quote", {"symbol": ticker}))

    def _fetch_income_latest(self, ticker: str) -> dict:
        """Most-recent annual income statement (1 record) — fiscalYear, epsDiluted."""
        body = self._get("income-statement", {"symbol": ticker, "limit": 1})
        return self._first(body)

    def _fetch_key_metrics_ttm(self, ticker: str) -> dict:
        """Key metrics TTM — peRatioTTM, netIncomePerShareTTM, dividendYieldTTM, etc."""
        return self._first(self._get("key-metrics-ttm", {"symbol": ticker}))

    def _fetch_shares_float(self, ticker: str) -> dict:
        """Shares float — shortPercent, floatShares, outstandingShares."""
        return self._first(self._get("shares-float", {"symbol": ticker}))

    # ── combined overview fetch (parallel) ────────────────────────────────────
    def fetch_treasury_rate(self) -> float:
        """Fetch 10-year Treasury yield (^TNX). Returns decimal (e.g. 0.042). Defaults to 4.2%."""
        body = self._get("quote", {"symbol": "^TNX"})
        if isinstance(body, list) and body:
            try:
                price = float(body[0].get("price") or 0)
                if price > 0:
                    return price / 100
            except (TypeError, ValueError):
                pass
        return 0.042

    def fetch_overview(self, ticker: str) -> dict:
        """
        Merges 5 FMP endpoints in parallel to minimise N/A values:
          /profile · /quote · /income-statement(1) · /key-metrics-ttm · /shares-float

        Private keys (prefixed _) carry enrichment data for ProfileAgent:
          _latestFiscalYear  — most recent fiscal year string
          _eps               — best available EPS figure
        """
        t = ticker.strip().upper()
        if not self.api_key or not t:
            return {}

        # Fire all 5 requests concurrently
        with ThreadPoolExecutor(max_workers=5) as ex:
            f_profile = ex.submit(self.fetch_profile,          t)
            f_quote   = ex.submit(self._fetch_quote,           t)
            f_income  = ex.submit(self._fetch_income_latest,   t)
            f_km      = ex.submit(self._fetch_key_metrics_ttm, t)
            f_sf      = ex.submit(self._fetch_shares_float,    t)

        profile = f_profile.result() or {}
        quote   = f_quote.result()   or {}
        income  = f_income.result()  or {}
        km      = f_km.result()      or {}
        sf      = f_sf.result()      or {}

        # ── Diagnostic: log what each endpoint returned ───────────────────────
        print(f"[fetch_overview/{t}] profile keys: {list(profile.keys())[:10]}")
        print(f"[fetch_overview/{t}] mktCap={profile.get('mktCap')} volAvg={profile.get('volAvg')} "
              f"beta={profile.get('beta')} pe={profile.get('pe')} "
              f"heldByInsiders={profile.get('heldByInsiders')} shortRatio={profile.get('shortRatio')}")
        print(f"[fetch_overview/{t}] quote: price={quote.get('price')} marketCap={quote.get('marketCap')} "
              f"avgVolume={quote.get('avgVolume')} pe={quote.get('pe')} eps={quote.get('eps')}")
        print(f"[fetch_overview/{t}] km: peRatioTTM={km.get('peRatioTTM')} "
              f"netIncomePerShareTTM={km.get('netIncomePerShareTTM')}")
        print(f"[fetch_overview/{t}] sf: shortPercentOfFloat={sf.get('shortPercentOfFloat')} "
              f"shortPercent={sf.get('shortPercent')} shortRatio={sf.get('shortRatio')}")
        print(f"[fetch_overview/{t}] profile: heldByInstitutions={profile.get('heldByInstitutions')} "
              f"institutionalHolderProp={profile.get('institutionalHolderProp')} "
              f"heldByInsiders={profile.get('heldByInsiders')}")

        # ── Merge: profile is the base ────────────────────────────────────────
        data = dict(profile)

        # Quote: prefer for real-time price/volume/pe/eps/earnings
        for field in ("price", "changesPercentage", "change", "eps", "pe"):
            if quote.get(field) is not None:
                data[field] = quote[field]
        if quote.get("avgVolume"):
            data["volAvg"] = quote["avgVolume"]   # normalise to profile key name
        if quote.get("marketCap"):
            data["mktCap"] = quote["marketCap"]

        # Earnings announcement — /stable may use either field name
        data["earningsAnnouncement"] = (
            quote.get("earningsAnnouncement")
            or quote.get("nextEarningsDate")
            or data.get("earningsAnnouncement")
        )

        # Ex-dividend date — /stable profile may use either field name
        if not data.get("exDividendDate"):
            data["exDividendDate"] = (
                data.get("exDividend")
                or data.get("lastDiv")
            )

        # Key-metrics TTM: fill P/E and beta gaps if still missing or negative
        _pe = data.get("pe")
        if (not _pe or _pe < 0) and km.get("peRatioTTM") and km["peRatioTTM"] > 0:
            data["pe"] = km["peRatioTTM"]
        if not data.get("beta") and km.get("beta"):
            data["beta"] = km["beta"]

        # Institutional holdings — /stable profile may use either field name
        if not data.get("heldByInstitutions") and data.get("institutionalHolderProp"):
            data["heldByInstitutions"] = data["institutionalHolderProp"]

        # Income statement: fiscal year label + best EPS
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

        # Short interest — check all known FMP field names; primary is shortPercentOfFloat
        if not data.get("shortPercent"):
            data["shortPercent"] = (
                sf.get("shortPercentOfFloat")
                or sf.get("shortPercent")
                or sf.get("shortRatio")
                or data.get("shortRatio")
            )

        data.setdefault("_latestFiscalYear", "N/A")
        data.setdefault("_eps", None)
        return data
