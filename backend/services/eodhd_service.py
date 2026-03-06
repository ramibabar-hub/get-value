"""
backend/services/eodhd_service.py
EODHD (eodhistoricaldata.com) data service.

Fetches international fundamentals and normalises them to the exact same
canonical dict format that InsightsAgent / logic_engine expects, so the
rest of the stack is completely source-agnostic.

Canonical format keys (mirrors FMP):
  annual_income_statement    quarterly_income_statement
  annual_balance_sheet       quarterly_balance_sheet
  annual_cash_flow           quarterly_cash_flow
  annual_ratios              annual_key_metrics   quarterly_key_metrics
  historical_prices
"""

import requests
from ._key_loader import load_key


# ─────────────────────────────────────────────────────────────────────────────
#  Field-name maps: EODHD → FMP canonical
# ─────────────────────────────────────────────────────────────────────────────

# Income statement
_IS_MAP = {
    "totalRevenue":                   "revenue",
    "grossProfit":                    "grossProfit",
    "costOfGoodsAndServicesSold":     "costOfRevenue",
    "costOfRevenue":                  "costOfRevenue",
    "operatingIncome":                "operatingIncome",
    "ebitda":                         "ebitda",
    "netIncome":                      "netIncome",
    "netIncomeContinuousOperations":  "netIncome",          # fallback
    "interestExpense":                "interestExpense",
    "incomeBeforeTax":                "incomeBeforeTax",
    "incomeTaxExpense":               "incomeTaxExpense",
    # EPS — EODHD may use several names
    "dilutedEPS":                     "epsDiluted",
    "epsDiluted":                     "epsDiluted",
    "eps":                            "eps",
    # Shares
    "dilutedAverageShares":           "weightedAverageShsOutDil",
    "weightedAverageShsOutDil":       "weightedAverageShsOutDil",
    "basicAverageShares":             "weightedAverageShsOut",
    "weightedAverageShsOut":          "weightedAverageShsOut",
}

# Balance sheet
_BS_MAP = {
    "totalAssets":                    "totalAssets",
    "totalCurrentAssets":             "totalCurrentAssets",
    "totalLiab":                      "totalLiabilities",
    "totalCurrentLiabilities":        "totalCurrentLiabilities",
    "totalStockholderEquity":         "totalStockholdersEquity",
    "commonStockSharesOutstanding":   "commonStockSharesOutstanding",
    # Cash
    "cashAndCashEquivalentsAtCarryingValue": "cashAndCashEquivalents",
    "cash":                           "cashAndCashEquivalents",
    # Receivables / inventory / payables
    "netReceivables":                 "netReceivables",
    "inventory":                      "inventory",
    "accountsPayable":                "accountPayables",
    # PP&E
    "propertyPlantEquipmentNet":      "propertyPlantEquipmentNet",
    # Debt — we prefer shortLongTermDebtTotal; fallback computed below
    "shortLongTermDebtTotal":         "totalDebt",
    "longTermDebt":                   "longTermDebt",
    "longTermDebtTotal":              "longTermDebt",
    "shortTermDebt":                  "shortTermDebt",
    "shortLongTermDebt":              "shortLongTermDebt",
}

# Cash flow
_CF_MAP = {
    "totalCashFromOperatingActivities": "operatingCashFlow",
    "capitalExpenditures":              "capitalExpenditure",
    "freeCashFlow":                     "freeCashFlow",
    "stockBasedCompensation":           "stockBasedCompensation",
    "commonDividendsPaid":              "commonDividendsPaid",
    "commonStockRepurchased":           "commonStockRepurchased",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(v):
    """Coerce to float or None."""
    if v is None or v == "None":
        return None
    try:
        f = float(v)
        return f if f == f else None   # NaN guard
    except (TypeError, ValueError):
        return None


def _year(date_str: str) -> str:
    """Extract 4-digit year string from 'YYYY-MM-DD'."""
    return str(date_str)[:4] if date_str else ""


def _quarter_label(date_str: str) -> str:
    """
    Map a date string → FMP-style period label (Q1/Q2/Q3/Q4).
    Uses the month of the period-end date (standard calendar quarters).
    """
    try:
        month = int(str(date_str)[5:7])
    except (ValueError, IndexError):
        return ""
    return {1: "Q1", 2: "Q1", 3: "Q1",
            4: "Q2", 5: "Q2", 6: "Q2",
            7: "Q3", 8: "Q3", 9: "Q3",
            10: "Q4", 11: "Q4", 12: "Q4"}.get(month, "")


def _remap(raw: dict, field_map: dict) -> dict:
    """
    Remap raw EODHD record → FMP canonical field names.
    Priority: first mapped name wins; unmapped keys are dropped.
    """
    out: dict = {}
    for eodhd_key, fmp_key in field_map.items():
        if eodhd_key in raw and fmp_key not in out:
            out[fmp_key] = _safe_float(raw[eodhd_key])
    return out


def _normalize_statements(period_dict: dict, field_map: dict,
                           is_quarterly: bool) -> list:
    """
    Convert EODHD's period dict:
        {"2024-09-30": {fields…}, "2023-09-30": {fields…}, …}
    → FMP-style list (newest first):
        [{"date": "2024-09-30", "fiscalYear": "2024", …fields…}, …]
    """
    if not isinstance(period_dict, dict):
        return []

    records = []
    for date_str, raw in period_dict.items():
        if not isinstance(raw, dict):
            continue
        rec = _remap(raw, field_map)
        rec["date"]         = date_str
        rec["fiscalYear"]   = _year(date_str)
        rec["calendarYear"] = _year(date_str)
        if is_quarterly:
            rec["period"] = _quarter_label(date_str)
        else:
            rec["period"] = "FY"
        records.append(rec)

    # Sort newest → oldest
    records.sort(key=lambda r: r.get("date", ""), reverse=True)

    # ── Post-process: derived fields ──────────────────────────────────────────
    for rec in records:
        # totalDebt fallback: shortTermDebt + longTermDebt
        if rec.get("totalDebt") is None:
            short = rec.get("shortTermDebt") or rec.get("shortLongTermDebt") or 0.0
            long_ = rec.get("longTermDebt") or 0.0
            s = _safe_float(short)
            l = _safe_float(long_)
            if s is not None or l is not None:
                rec["totalDebt"] = (s or 0.0) + (l or 0.0)

        # freeCashFlow fallback: operatingCashFlow + capitalExpenditure
        if rec.get("freeCashFlow") is None:
            ocf  = _safe_float(rec.get("operatingCashFlow"))
            capx = _safe_float(rec.get("capitalExpenditure"))
            if ocf is not None and capx is not None:
                rec["freeCashFlow"] = ocf + capx   # capex is typically negative

    return records


# ─────────────────────────────────────────────────────────────────────────────
#  EODHDService
# ─────────────────────────────────────────────────────────────────────────────

class EODHDService:
    _BASE = "https://eodhd.com/api"

    def __init__(self):
        self.api_key = load_key("EODHD_API_KEY")
        if not self.api_key:
            print("[EODHDService] WARNING: EODHD_API_KEY not found")

    # ── internal GET ─────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None,
             timeout: int = 15):
        """GET → parsed JSON or None."""
        params = params or {}
        try:
            res = requests.get(
                f"{self._BASE}/{path}",
                params={**params, "api_token": self.api_key, "fmt": "json"},
                timeout=timeout,
            )
            res.raise_for_status()
            return res.json()
        except Exception as exc:
            print(f"[EODHDService] GET {path} ERROR: {exc}")
            return None

    # ── raw fetchers ─────────────────────────────────────────────────────────

    def fetch_fundamentals(self, ticker: str, exchange: str) -> dict:
        """
        Fetch the EODHD fundamentals mega-endpoint.
        Returns the full JSON or {} on failure.
        """
        if not self.api_key:
            return {}
        data = self._get(f"fundamentals/{ticker}.{exchange}")
        if isinstance(data, dict) and data:
            print(f"[EODHDService] fundamentals {ticker}.{exchange}: OK")
            return data
        print(f"[EODHDService] fundamentals {ticker}.{exchange}: empty/failed")
        return {}

    def fetch_real_time(self, ticker: str, exchange: str) -> dict:
        """
        Fetch real-time quote.
        Returns dict with keys: close, open, high, low, change, change_p, volume, …
        """
        if not self.api_key:
            return {}
        data = self._get(f"real-time/{ticker}.{exchange}")
        return data if isinstance(data, dict) else {}

    def fetch_historical_prices(self, ticker: str, exchange: str,
                                limit: int = 2000) -> list:
        """
        Fetch daily historical prices (newest first).
        Normalises to FMP-compatible keys: date, open, high, low, close, adjClose, volume.
        """
        if not self.api_key:
            return []
        data = self._get(f"eod/{ticker}.{exchange}",
                         {"order": "d", "limit": limit})
        if not isinstance(data, list):
            return []

        out = []
        for rec in data:
            if not isinstance(rec, dict):
                continue
            out.append({
                "date":     rec.get("date", ""),
                "open":     _safe_float(rec.get("open")),
                "high":     _safe_float(rec.get("high")),
                "low":      _safe_float(rec.get("low")),
                "close":    _safe_float(rec.get("close")),
                "adjClose": _safe_float(rec.get("adjusted_close") or rec.get("close")),
                "volume":   rec.get("volume"),
            })
        return out

    # ── normalization ─────────────────────────────────────────────────────────

    def _normalize_financials(self, fund: dict) -> dict:
        """
        Extract and normalise the Financials section of the fundamentals blob
        into the canonical InsightsAgent-compatible format.
        """
        fin = fund.get("Financials") or {}

        def _stmts(section_key: str, is_q: bool) -> list:
            section = fin.get(section_key) or {}
            period_key = "quarterly" if is_q else "yearly"
            raw_periods = section.get(period_key) or {}
            field_map = (
                _IS_MAP if "Income" in section_key else
                _BS_MAP if "Balance" in section_key else
                _CF_MAP
            )
            return _normalize_statements(raw_periods, field_map, is_q)

        return {
            "annual_income_statement":    _stmts("Income_Statement", False),
            "quarterly_income_statement": _stmts("Income_Statement", True),
            "annual_balance_sheet":       _stmts("Balance_Sheet",    False),
            "quarterly_balance_sheet":    _stmts("Balance_Sheet",    True),
            "annual_cash_flow":           _stmts("Cash_Flow",        False),
            "quarterly_cash_flow":        _stmts("Cash_Flow",        True),
            # EODHD doesn't provide pre-computed ratios or key-metrics per year;
            # InsightsAgent handles empty lists gracefully (shows N/A for averages)
            "annual_ratios":              [],
            "annual_key_metrics":         [],
            "quarterly_key_metrics":      [],
        }

    def _normalize_overview(self, fund: dict, rt: dict,
                             ticker: str, exchange: str) -> dict:
        """
        Build an FMP-compatible overview dict from EODHD fundamentals + real-time.
        """
        gen  = fund.get("General")      or {}
        hi   = fund.get("Highlights")   or {}
        val  = fund.get("Valuation")    or {}
        tech = fund.get("Technicals")   or {}
        sh   = fund.get("SharesStats")  or {}

        # Current price: prefer real-time close, fall back to Highlights
        price = (_safe_float(rt.get("close"))
                 or _safe_float(hi.get("LastTradePrice"))
                 or _safe_float(hi.get("previousClose")))

        mkt_cap = (_safe_float(hi.get("MarketCapitalization"))
                   or _safe_float(gen.get("MarketCapitalization")))

        # Build shares outstanding from SharesStats or compute from market cap + price
        shares = _safe_float(sh.get("SharesOutstanding") or sh.get("CommonStockSharesOutstanding"))
        if shares is None and mkt_cap and price and price > 0:
            shares = mkt_cap / price

        beta = _safe_float(tech.get("Beta"))

        pe = (_safe_float(val.get("TrailingPE"))
              or _safe_float(hi.get("PERatio")))

        eps = (_safe_float(hi.get("EarningsShare"))
               or _safe_float(hi.get("EPSEstimateCurrentYear")))

        div_yield = _safe_float(hi.get("DividendYield"))

        return {
            # Identity
            "symbol":           f"{ticker}.{exchange}",
            "companyName":      gen.get("Name", ""),
            "exchange":         gen.get("Exchange", exchange),
            "exchangeShortName": gen.get("Exchange", exchange),
            "currency":         gen.get("CurrencyCode", ""),
            "country":          gen.get("CountryISO2", ""),
            "sector":           gen.get("Sector", ""),
            "industry":         gen.get("Industry", ""),
            "description":      gen.get("Description", ""),
            "website":          gen.get("WebURL", ""),
            # Financials
            "price":            price,
            "mktCap":           mkt_cap,
            "beta":             beta,
            "pe":               pe,
            "eps":              eps,
            "dividendYield":    div_yield,
            # Ratios
            "priceToBook":      _safe_float(val.get("PriceBookMRQ")),
            "priceToSales":     _safe_float(val.get("PriceSalesTTM")),
            # Enrichment for downstream agents
            "sharesOutstanding": shares,
            "_latestFiscalYear": gen.get("FiscalYearEnd", "N/A"),
            "_eps":              eps,
            "_source":          "eodhd",
        }

    # ── public interface ──────────────────────────────────────────────────────

    def fetch_all(self, ticker: str, exchange: str) -> dict:
        """
        Fetch and normalise all financial data for ticker.exchange.
        Returns the canonical dict consumed by InsightsAgent.
        """
        fund = self.fetch_fundamentals(ticker, exchange)
        if not fund:
            return {k: [] for k in (
                "annual_income_statement", "quarterly_income_statement",
                "annual_balance_sheet",    "quarterly_balance_sheet",
                "annual_cash_flow",        "quarterly_cash_flow",
                "annual_ratios",           "annual_key_metrics",
                "quarterly_key_metrics",   "historical_prices",
            )}

        result = self._normalize_financials(fund)
        result["historical_prices"] = self.fetch_historical_prices(ticker, exchange)
        return result

    def fetch_overview(self, ticker: str, exchange: str) -> dict:
        """
        Fetch real-time + fundamentals and return an FMP-compatible overview dict.
        """
        fund = self.fetch_fundamentals(ticker, exchange)
        rt   = self.fetch_real_time(ticker, exchange)
        if not fund and not rt:
            return {}
        return self._normalize_overview(fund, rt, ticker, exchange)
