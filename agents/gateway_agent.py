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

    # Exchange short-name → emoji flag (used in search dropdown)
    EXCHANGE_FLAGS = {
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
        if not self.api_key:
            print("[GatewayAgent] WARNING: FMP_API_KEY not found in secrets, env, or .env")
        else:
            print(f"[GatewayAgent] API key loaded (ends: ...{self.api_key[-4:]})")

    # ── internal GET helper ───────────────────────────────────────────────────
    def _get(self, path: str, params: dict, timeout: int = 8):
        """Raw GET, returns parsed JSON or None on error."""
        try:
            res = requests.get(
                f"{self.base_url}/{path}",
                params={**params, "apikey": self.api_key},
                timeout=timeout,
            )
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
        url = f"{self.base_url}/{path}"
        params = {"symbol": ticker, "apikey": self.api_key, "limit": 15}
        if is_quarterly:
            params["period"] = "quarter"
        label = f"{'Q' if is_quarterly else 'A'}/{path}/{ticker}"
        print(f"[GatewayAgent] GET {url} limit=15")
        try:
            res = requests.get(url, params=params, timeout=10)
            body = res.json()
            if not isinstance(body, list):
                print(f"[GatewayAgent] ERROR {label} status={res.status_code}: {body}")
                return []
            if not body:
                print(f"[GatewayAgent] EMPTY {label} (0 records)")
                return []
            first = body[0]
            print(f"[GatewayAgent] OK {label}: {len(body)} records | "
                  f"fiscalYear={first.get('fiscalYear')} calendarYear={first.get('calendarYear')} "
                  f"period={first.get('period')}")
            if not first.get('fiscalYear') and not first.get('calendarYear'):
                print(f"[GatewayAgent] DIAGNOSTIC — first record keys: {list(first.keys())}")
                print(f"[GatewayAgent] DIAGNOSTIC — first record: {json.dumps(first, default=str)}")
            return body
        except Exception as e:
            print(f"[GatewayAgent] EXCEPTION {label}: {e}")
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
        }

    # ── autocomplete search ───────────────────────────────────────────────────
    def search_ticker(self, query: str, limit: int = 10) -> list:
        """Autocomplete: returns [{symbol, name, exchangeShortName, flag, ...}]."""
        if not self.api_key or not query.strip():
            return []
        body = self._get("search", {"query": query.strip(), "limit": limit})
        if not isinstance(body, list):
            return []
        for item in body:
            exch = str(item.get("exchangeShortName") or item.get("stockExchange") or "").upper()
            item["flag"] = self.EXCHANGE_FLAGS.get(exch, "🏳️")
        return body

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

        # ── Merge: profile is the base ────────────────────────────────────────
        data = dict(profile)

        # Quote: prefer for real-time price/volume/pe/eps/earnings
        for field in ("price", "changesPercentage", "change",
                      "eps", "pe", "earningsAnnouncement"):
            if quote.get(field) is not None:
                data[field] = quote[field]
        if quote.get("avgVolume"):
            data["volAvg"] = quote["avgVolume"]   # normalise to profile key name
        if quote.get("marketCap"):
            data["mktCap"] = quote["marketCap"]

        # Key-metrics TTM: fill P/E gap if still missing
        if not data.get("pe") and km.get("peRatioTTM"):
            data["pe"] = km["peRatioTTM"]

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

        # Shares float: short percent if not already in profile
        if not data.get("shortPercent") and sf:
            data["shortPercent"] = sf.get("shortPercent") or sf.get("shortRatio")

        data.setdefault("_latestFiscalYear", "N/A")
        data.setdefault("_eps", None)
        return data
