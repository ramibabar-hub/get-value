"""
backend/services/gateway.py
SmartGateway — exchange-aware data router.

Routing rules:
  US tickers   (no suffix, or non-international suffix) → FMP primary, EODHD fallback
  Intl tickers (recognised exchange suffix)             → EODHD primary, FMP fallback

Both services return the same canonical dict format, so logic_engine
receives identical data structures regardless of source.
"""

from .fmp_service   import FMPService
from .eodhd_service import EODHDService


# ── Exchange suffix tables ────────────────────────────────────────────────────

# Suffixes that unambiguously identify a non-US exchange.
# Key = FMP suffix (after the dot)  →  Value = EODHD exchange code.
_FMP_SUFFIX_TO_EODHD: dict[str, str] = {
    # Europe
    "L":   "LSE",    # London Stock Exchange
    "DE":  "XETRA",  # Deutsche Börse / Xetra
    "PA":  "PA",     # Euronext Paris
    "AS":  "AS",     # Euronext Amsterdam
    "MI":  "MI",     # Borsa Italiana (Milan)
    "MC":  "MC",     # Bolsa de Madrid
    "SW":  "SW",     # SIX Swiss Exchange
    "BE":  "BE",     # Berlin Stock Exchange
    "F":   "F",      # Frankfurt Stock Exchange
    "BR":  "BR",     # Euronext Brussels
    "LI":  "LI",     # Lisbon
    "VI":  "VI",     # Vienna
    "HE":  "HE",     # Helsinki
    "ST":  "ST",     # Stockholm
    "CO":  "CO",     # Copenhagen
    "OL":  "OL",     # Oslo
    # Asia-Pacific
    "HK":  "HK",     # Hong Kong Stock Exchange
    "T":   "T",      # Tokyo Stock Exchange
    "KS":  "KS",     # Korea Stock Exchange
    "AX":  "AU",     # ASX Australia  (FMP .AX → EODHD .AU)
    "NZ":  "NZ",     # NZX New Zealand
    "SI":  "SI",     # SGX Singapore
    "NS":  "NSE",    # NSE India       (FMP .NS → EODHD .NSE)
    "BO":  "BSE",    # BSE India       (FMP .BO → EODHD .BSE)
    "TW":  "TW",     # TWSE Taiwan
    "BK":  "BK",     # Thailand SET
    "JK":  "JK",     # Indonesia IDX
    "KL":  "KLSE",   # Malaysia KLSE
    # Middle East / Africa
    "TA":  "TA",     # Tel Aviv Stock Exchange (Israel)
    "SA":  "SA",     # São Paulo B3 (Brazil)
    "JO":  "JSE",    # Johannesburg Stock Exchange
    # Americas (non-US)
    "TO":  "TO",     # Toronto Stock Exchange
    "V":   "V",      # TSX Venture
    "MX":  "MX",     # Mexican Exchange (BMV)
}

# Set of suffixes that indicate international routing
_INTL_SUFFIXES: frozenset[str] = frozenset(_FMP_SUFFIX_TO_EODHD.keys())


def _has_data(fetch_all_result: dict) -> bool:
    """Return True if at least one statement list is non-empty."""
    return bool(
        fetch_all_result.get("annual_income_statement")
        or fetch_all_result.get("quarterly_income_statement")
    )


# ─────────────────────────────────────────────────────────────────────────────
#  SmartGateway
# ─────────────────────────────────────────────────────────────────────────────

class SmartGateway:
    """
    Single entry point for all data fetching.

    Usage:
        gw = SmartGateway()
        raw_data = gw.fetch_all("AAPL")          # US → FMP
        raw_data = gw.fetch_all("NICE.TA")       # Israel → EODHD
        overview = gw.fetch_overview("VOD.L")    # UK → EODHD
    """

    def __init__(self):
        self._fmp  = FMPService()
        self._eod  = EODHDService()

    # ── ticker parsing ────────────────────────────────────────────────────────

    @staticmethod
    def parse_ticker(ticker: str) -> tuple[str, str | None, bool]:
        """
        Decompose a ticker string.

        Returns
        -------
        (base, suffix, is_us)
          base    : the part before the dot  (e.g. "NICE", "AAPL")
          suffix  : uppercase suffix after dot, or None  (e.g. "TA", None)
          is_us   : True when no recognised international suffix is found
        """
        t = ticker.strip().upper()
        if "." in t:
            base, suffix = t.rsplit(".", 1)
            is_us = suffix not in _INTL_SUFFIXES
            return base, suffix, is_us
        return t, None, True

    def _eodhd_coords(self, base: str,
                      suffix: str | None) -> tuple[str, str]:
        """Return (ticker_base, eodhd_exchange_code)."""
        if suffix is None:
            return base, "US"
        return base, _FMP_SUFFIX_TO_EODHD.get(suffix, suffix)

    def _source_label(self, ticker: str) -> str:
        """Human-readable routing label for logging."""
        _, _, is_us = self.parse_ticker(ticker)
        return "FMP→EODHD" if is_us else "EODHD→FMP"

    # ── public fetch_all ──────────────────────────────────────────────────────

    def fetch_all(self, ticker: str) -> dict:
        """
        Fetch all financial statements for *ticker*.

        Returns the canonical dict:
          annual_income_statement, quarterly_income_statement,
          annual_balance_sheet,    quarterly_balance_sheet,
          annual_cash_flow,        quarterly_cash_flow,
          annual_ratios,           annual_key_metrics,
          quarterly_key_metrics,   historical_prices
        """
        base, suffix, is_us = self.parse_ticker(ticker)
        fmp_ticker = ticker.strip().upper()
        eod_base, eod_exchange = self._eodhd_coords(base, suffix)

        print(f"[SmartGateway] fetch_all {ticker!r}  route={self._source_label(ticker)}")

        if is_us:
            data = self._fmp.fetch_all(fmp_ticker)
            if _has_data(data):
                data["_source"] = "fmp"
                return data
            print(f"[SmartGateway] FMP empty for {ticker} — falling back to EODHD")
            data = self._eod.fetch_all(eod_base, eod_exchange)
            data["_source"] = "eodhd_fallback"
            return data
        else:
            data = self._eod.fetch_all(eod_base, eod_exchange)
            if _has_data(data):
                data["_source"] = "eodhd"
                return data
            print(f"[SmartGateway] EODHD empty for {ticker} — falling back to FMP")
            data = self._fmp.fetch_all(fmp_ticker)
            data["_source"] = "fmp_fallback"
            return data

    # ── public fetch_overview ─────────────────────────────────────────────────

    def fetch_overview(self, ticker: str) -> dict:
        """
        Fetch the company overview / profile dict.

        Returns a flat dict with canonical keys:
          symbol, companyName, price, mktCap, beta, pe, eps,
          sector, industry, country, currency, …
        """
        base, suffix, is_us = self.parse_ticker(ticker)
        fmp_ticker = ticker.strip().upper()
        eod_base, eod_exchange = self._eodhd_coords(base, suffix)

        print(f"[SmartGateway] fetch_overview {ticker!r}  route={self._source_label(ticker)}")

        if is_us:
            ov = self._fmp.fetch_overview(fmp_ticker)
            if ov:
                ov.setdefault("_source", "fmp")
                return ov
            print(f"[SmartGateway] FMP overview empty for {ticker} — falling back to EODHD")
            ov = self._eod.fetch_overview(eod_base, eod_exchange)
            ov["_source"] = "eodhd_fallback"
            return ov
        else:
            ov = self._eod.fetch_overview(eod_base, eod_exchange)
            if ov:
                ov.setdefault("_source", "eodhd")
                return ov
            print(f"[SmartGateway] EODHD overview empty for {ticker} — falling back to FMP")
            ov = self._fmp.fetch_overview(fmp_ticker)
            ov.setdefault("_source", "fmp_fallback")
            return ov

    # ── convenience: routing info ─────────────────────────────────────────────

    def routing_info(self, ticker: str) -> dict:
        """
        Return routing metadata for a ticker without fetching any data.
        Useful for debugging or displaying the data source to the user.
        """
        base, suffix, is_us = self.parse_ticker(ticker)
        eod_base, eod_exchange = self._eodhd_coords(base, suffix)
        primary = "fmp" if is_us else "eodhd"
        fallback = "eodhd" if is_us else "fmp"
        return {
            "ticker":        ticker.strip().upper(),
            "base":          base,
            "suffix":        suffix,
            "is_us":         is_us,
            "primary":       primary,
            "fallback":      fallback,
            "fmp_ticker":    ticker.strip().upper(),
            "eodhd_ticker":  f"{eod_base}.{eod_exchange}",
        }
