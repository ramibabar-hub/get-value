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


def _load_eodhd_key():
    """Same priority chain as _load_api_key() but for EODHD_API_KEY."""
    try:
        raw = st.secrets.get("EODHD_API_KEY", "")
        if raw:
            return "".join(raw.split()).strip('"').strip("'")
    except Exception:
        pass
    raw = os.environ.get("EODHD_API_KEY", "")
    if raw:
        return raw.strip()
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("EODHD_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


# ── EODHD → FMP canonical field maps ─────────────────────────────────────────
# Mirrors backend/services/eodhd_service.py so both stacks stay in sync.

_EODHD_IS_MAP = {
    "totalRevenue":                   "revenue",
    "grossProfit":                    "grossProfit",
    "costOfGoodsAndServicesSold":     "costOfRevenue",
    "costOfRevenue":                  "costOfRevenue",
    "operatingIncome":                "operatingIncome",
    "ebitda":                         "ebitda",
    "netIncome":                      "netIncome",
    "netIncomeContinuousOperations":  "netIncome",
    "interestExpense":                "interestExpense",
    "incomeBeforeTax":                "incomeBeforeTax",
    "incomeTaxExpense":               "incomeTaxExpense",
    "dilutedEPS":                     "epsDiluted",
    "epsDiluted":                     "epsDiluted",
    "eps":                            "eps",
    "dilutedAverageShares":           "weightedAverageShsOutDil",
    "weightedAverageShsOutDil":       "weightedAverageShsOutDil",
    "basicAverageShares":             "weightedAverageShsOut",
    "weightedAverageShsOut":          "weightedAverageShsOut",
}

_EODHD_BS_MAP = {
    "totalAssets":                              "totalAssets",
    "totalCurrentAssets":                       "totalCurrentAssets",
    "totalLiab":                                "totalLiabilities",
    "totalCurrentLiabilities":                  "totalCurrentLiabilities",
    "totalStockholderEquity":                   "totalStockholdersEquity",
    "commonStockSharesOutstanding":             "commonStockSharesOutstanding",
    "cashAndCashEquivalentsAtCarryingValue":    "cashAndCashEquivalents",
    "cash":                                     "cashAndCashEquivalents",
    "netReceivables":                           "netReceivables",
    "inventory":                                "inventory",
    "accountsPayable":                          "accountPayables",
    "propertyPlantEquipmentNet":                "propertyPlantEquipmentNet",
    "shortLongTermDebtTotal":                   "totalDebt",
    "longTermDebt":                             "longTermDebt",
    "longTermDebtTotal":                        "longTermDebt",
    "shortTermDebt":                            "shortTermDebt",
    "shortLongTermDebt":                        "shortLongTermDebt",
}

_EODHD_CF_MAP = {
    "totalCashFromOperatingActivities": "operatingCashFlow",
    "capitalExpenditures":              "capitalExpenditure",
    "freeCashFlow":                     "freeCashFlow",
    "stockBasedCompensation":           "stockBasedCompensation",
    "commonDividendsPaid":              "commonDividendsPaid",
    "commonStockRepurchased":           "commonStockRepurchased",
}


def _eodhd_safe_num(v):
    """Coerce to float or None (NaN-safe)."""
    if v is None or v == "None":
        return None
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _eodhd_remap(raw: dict, field_map: dict) -> dict:
    """Re-key an EODHD record using field_map; first mapped name wins."""
    out: dict = {}
    for eodhd_key, fmp_key in field_map.items():
        if eodhd_key in raw and fmp_key not in out:
            out[fmp_key] = _eodhd_safe_num(raw[eodhd_key])
    return out


def _eodhd_normalize_statements(period_dict: dict, field_map: dict,
                                 is_quarterly: bool) -> list:
    """
    Convert EODHD's period dict:
        {"2024-09-30": {fields…}, …}
    → FMP-compatible list (newest first):
        [{"date": "2024-09-30", "fiscalYear": "2024", …fields…}, …]
    """
    if not isinstance(period_dict, dict):
        return []
    records = []
    for date_str, raw in period_dict.items():
        if not isinstance(raw, dict):
            continue
        rec = _eodhd_remap(raw, field_map)
        rec["date"]         = date_str
        rec["fiscalYear"]   = str(date_str)[:4]
        rec["calendarYear"] = str(date_str)[:4]
        rec["period"]       = "Q" if is_quarterly else "FY"
        records.append(rec)
    records.sort(key=lambda r: r.get("date", ""), reverse=True)

    # Derived fields
    for rec in records:
        if rec.get("totalDebt") is None:
            s = _eodhd_safe_num(rec.get("shortTermDebt") or rec.get("shortLongTermDebt") or 0)
            l = _eodhd_safe_num(rec.get("longTermDebt") or 0)
            if s is not None or l is not None:
                rec["totalDebt"] = (s or 0.0) + (l or 0.0)
        if rec.get("freeCashFlow") is None:
            ocf  = _eodhd_safe_num(rec.get("operatingCashFlow"))
            capx = _eodhd_safe_num(rec.get("capitalExpenditure"))
            if ocf is not None and capx is not None:
                rec["freeCashFlow"] = ocf + capx
    return records


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

    # EODHD exchange codes that this gateway routes to EODHD
    # Key = ticker suffix (after '.'), value = EODHD exchange code
    _EODHD_SUFFIX_MAP = {
        "TA": "TA",   # Tel Aviv Stock Exchange (Israel)
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

        # EODHD — secondary data provider for Israeli (.TA) tickers
        self.eodhd_key  = _load_eodhd_key()
        self._eodhd_base = "https://eodhd.com/api"
        if self.eodhd_key:
            print(f"[GatewayAgent] EODHD key loaded (ends: ...{self.eodhd_key[-4:]})")
        else:
            print("[GatewayAgent] INFO: EODHD_API_KEY not found - .TA tickers will fall back to FMP")

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
            print(f"[GatewayAgent] No API key - skipping {path}/{ticker}")
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
            print(f"[GatewayAgent] EMPTY stable {label} status={res.status_code} - trying v3")
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
            print(f"[GatewayAgent] historical-prices stable {ticker}: empty - trying v3")
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

    # ── EODHD routing helpers ─────────────────────────────────────────────────

    def _is_eodhd_ticker(self, ticker: str) -> bool:
        """Return True when ticker suffix maps to an EODHD-routed exchange."""
        if "." not in ticker:
            return False
        suffix = ticker.rsplit(".", 1)[-1].upper()
        return suffix in self._EODHD_SUFFIX_MAP

    def _parse_eodhd_ticker(self, ticker: str):
        """Return (symbol, eodhd_exchange_code) from a dotted ticker string."""
        parts = ticker.rsplit(".", 1)
        symbol   = parts[0].upper()
        suffix   = parts[1].upper() if len(parts) == 2 else ""
        exchange = self._EODHD_SUFFIX_MAP.get(suffix, suffix)
        return symbol, exchange

    def _eodhd_get(self, path: str, params: dict | None = None, timeout: int = 15):
        """Raw GET against the EODHD API base. Returns parsed JSON or None."""
        if not self.eodhd_key:
            return None
        params = params or {}
        try:
            url = f"{self._eodhd_base}/{path}"
            res = requests.get(
                url,
                params={**params, "api_token": self.eodhd_key, "fmt": "json"},
                timeout=timeout,
            )
            print(f"[GatewayAgent/EODHD] GET {path} status={res.status_code}")
            res.raise_for_status()
            return res.json()
        except Exception as exc:
            print(f"[GatewayAgent/EODHD] ERROR {path}: {exc}")
            return None

    def _fetch_eodhd_fundamentals(self, symbol: str, exchange: str) -> dict:
        """Fetch EODHD fundamentals mega-endpoint. Returns raw dict or {}."""
        data = self._eodhd_get(f"fundamentals/{symbol}.{exchange}")
        if isinstance(data, dict) and data:
            print(f"[GatewayAgent/EODHD] fundamentals {symbol}.{exchange}: OK")
            return data
        print(f"[GatewayAgent/EODHD] fundamentals {symbol}.{exchange}: empty/failed")
        return {}

    def _fetch_historical_prices_eodhd(self, symbol: str, exchange: str) -> list:
        """
        Fetch EODHD daily price history; normalise to FMP-compatible keys:
          date, open, high, low, close, adjClose, volume.
        Returns list newest-first (matches FMP historical-price-full format).
        """
        data = self._eodhd_get(f"eod/{symbol}.{exchange}", {"order": "d", "limit": 2000})
        if not isinstance(data, list):
            return []
        out = []
        for bar in data:
            if not isinstance(bar, dict):
                continue
            out.append({
                "date":     bar.get("date", ""),
                "open":     _eodhd_safe_num(bar.get("open")),
                "high":     _eodhd_safe_num(bar.get("high")),
                "low":      _eodhd_safe_num(bar.get("low")),
                "close":    _eodhd_safe_num(bar.get("close")),
                "adjClose": _eodhd_safe_num(bar.get("adjusted_close")),
                "volume":   bar.get("volume"),
            })
        print(f"[GatewayAgent/EODHD] historical {symbol}.{exchange}: {len(out)} bars")
        return out

    def _fetch_all_eodhd(self, ticker: str) -> dict:
        """
        Full data fetch for EODHD-routed tickers (.TA etc.).
        Returns the same canonical dict shape as fetch_all() so all downstream
        agents (InsightsAgent, core_agent, cf_irr_tab) remain unmodified.
        """
        symbol, exchange = self._parse_eodhd_ticker(ticker)
        fund = self._fetch_eodhd_fundamentals(symbol, exchange)

        fin = fund.get("Financials") or {}

        # ── Financial statements ─────────────────────────────────────────────
        annual_is = _eodhd_normalize_statements(
            (fin.get("Income_Statement") or {}).get("annual") or {}, _EODHD_IS_MAP, False)
        quarterly_is = _eodhd_normalize_statements(
            (fin.get("Income_Statement") or {}).get("quarterly") or {}, _EODHD_IS_MAP, True)
        annual_bs = _eodhd_normalize_statements(
            (fin.get("Balance_Sheet") or {}).get("annual") or {}, _EODHD_BS_MAP, False)
        quarterly_bs = _eodhd_normalize_statements(
            (fin.get("Balance_Sheet") or {}).get("quarterly") or {}, _EODHD_BS_MAP, True)
        annual_cf = _eodhd_normalize_statements(
            (fin.get("Cash_Flow") or {}).get("annual") or {}, _EODHD_CF_MAP, False)
        quarterly_cf = _eodhd_normalize_statements(
            (fin.get("Cash_Flow") or {}).get("quarterly") or {}, _EODHD_CF_MAP, True)

        # ── Key metrics: synthesise per-year market cap / price from highlights ─
        # EODHD doesn't supply per-year key_metrics, so we build minimal stubs
        # that prevent NoneType errors in InsightsAgent.
        annual_km = []
        for rec in annual_is:
            yr = rec.get("fiscalYear", "")
            annual_km.append({
                "date":        rec.get("date", ""),
                "fiscalYear":  yr,
                "calendarYear": yr,
                "period":      "FY",
            })
        quarterly_km = []
        for rec in quarterly_is:
            quarterly_km.append({
                "date":        rec.get("date", ""),
                "fiscalYear":  rec.get("fiscalYear", ""),
                "calendarYear": rec.get("calendarYear", ""),
                "period":      rec.get("period", ""),
            })

        # annual_ratios: also empty stubs (InsightsAgent handles missing fields)
        annual_ratios = []

        # ── Historical prices ────────────────────────────────────────────────
        historical_prices = self._fetch_historical_prices_eodhd(symbol, exchange)

        print(f"[GatewayAgent/EODHD] {ticker}: "
              f"IS={len(annual_is)} BS={len(annual_bs)} CF={len(annual_cf)} "
              f"prices={len(historical_prices)}")

        return {
            "annual_income_statement":    annual_is,
            "quarterly_income_statement": quarterly_is,
            "annual_balance_sheet":       annual_bs,
            "quarterly_balance_sheet":    quarterly_bs,
            "annual_cash_flow":           annual_cf,
            "quarterly_cash_flow":        quarterly_cf,
            "annual_ratios":              annual_ratios,
            "annual_key_metrics":         annual_km,
            "quarterly_key_metrics":      quarterly_km,
            "historical_prices":          historical_prices,
        }

    def fetch_all(self, ticker):
        """
        Fetch all financial data for a ticker.
        Routes .TA tickers to EODHD when an EODHD key is present;
        all other tickers use FMP (unchanged behaviour).
        """
        if self._is_eodhd_ticker(ticker) and self.eodhd_key:
            print(f"[GatewayAgent] {ticker} -> EODHD route")
            return self._fetch_all_eodhd(ticker)

        # Default: FMP
        print(f"[GatewayAgent] {ticker} -> FMP route")
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
