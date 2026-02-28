"""
financials_tab.py
Renders the full Financials tab: existing 4 tables + 7 new metric groups appended after Debt.
Reacts to the Period (Annual/Quarterly) and Scale (B/MM/K) selectors already in session state.
"""
import math
import pandas as pd
import streamlit as st

# ── module-level helpers ──────────────────────────────────────────────────────

def _safe(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _d(a, b):
    """Safe division — None on zero/None denominator."""
    a, b = _safe(a), _safe(b)
    if a is None or b is None or b == 0:
        return None
    return a / b


def _fmt(v, fmt_type, div):
    """
    Format a single cell value.
    fmt_type: "money" | "ratio" | "pct" | "days" | "int"
    div: scale divisor (only applied to "money")
    Sentinel strings (e.g. "N/M") are passed through unchanged.
    """
    if isinstance(v, str):      # sentinel strings like "N/M"
        return v
    if v is None:
        return "N/A"
    f = _safe(v)
    if f is None or f == 0:
        return "N/A"
    if fmt_type == "money":
        return f"{f / div:,.2f}"
    if fmt_type == "pct":
        return f"{f * 100:.2f}%"
    if fmt_type == "int":
        return str(int(round(f)))
    if fmt_type == "days":
        return f"{f:.1f}"
    return f"{f:,.2f}"          # "ratio" — plain 2dp number


def _filing_url_fallback(ticker: str, exchange: str, col_label: str,
                         period_type: str) -> str:
    """
    Return a best-effort filing portal URL when FMP's finalLink/link are absent.

    ticker      : FMP symbol, e.g. "AAPL", "TEVA"
    exchange    : FMP exchangeShortName, e.g. "NASDAQ", "TASE", "LSE"
    col_label   : column header, e.g. "2023" or "2023 Q3"
    period_type : "annual" | "quarterly"

    Returns "" when the exchange has no supported mapping.
    """
    exch = (exchange or "").upper().strip()
    tkr  = (ticker  or "").strip()
    if not tkr:
        return ""

    # Extract 4-digit year ("2023" → 2023, "2023 Q3" → 2023)
    try:
        year = int(col_label.strip()[:4])
    except (ValueError, IndexError):
        year = None

    # ── US exchanges → SEC EDGAR ──────────────────────────────────────────
    _US = {
        "NASDAQ", "NYSE", "AMEX", "NYSE ARCA", "NYSEARCA", "NYSEMKT",
        "BATS", "OTC", "OTCQB", "OTCQX", "PINK", "CBOE",
    }
    if not exch or exch in _US:
        form = "10-K" if period_type == "annual" else "10-Q"
        # dateb = first day of the *next* year so the target filing appears at top
        dateb_param = f"&dateb={year + 1}0101" if year else ""
        return (
            f"https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcompany&CIK={tkr}&type={form}"
            f"{dateb_param}&owner=include&count=10"
        )

    # ── Israel / TASE ─────────────────────────────────────────────────────
    if exch in {"TASE", "TLV", "TA", "TAL"}:
        return f"https://maya.tase.co.il/company/{tkr}/reports"

    # ── London Stock Exchange / AIM ────────────────────────────────────────
    if exch in {"LSE", "LON", "AIM", "XLON"}:
        return f"https://www.londonstockexchange.com/stock/{tkr.upper()}/company-page"

    # ── Toronto Stock Exchange ─────────────────────────────────────────────
    if exch in {"TSX", "TSXV", "TSX-V", "CVE"}:
        return (
            f"https://www.sedar.com/FindCompany.do"
            f"?lang=EN&company_search={tkr}&SEARCH_BUTTON=Search+Now&bprofile=y"
        )

    # ── Australian Securities Exchange ────────────────────────────────────
    if exch in {"ASX", "XASX"}:
        return f"https://www.asx.com.au/markets/company/{tkr.lower()}"

    return ""


def _build_link_map(src_list, hist_col_headers,
                    ticker="", exchange="", period_type="annual"):
    """
    Build {col_label: url} for historical columns only.
    Primary  : FMP 'finalLink' or 'link' field from the statement record.
    Fallback : _filing_url_fallback() when both primary fields are absent.
    hist_col_headers: hdrs[2:] — the year/quarter labels in order.
    """
    link_map = {}
    for i, label in enumerate(hist_col_headers):
        if i < len(src_list) and isinstance(src_list[i], dict):
            rec = src_list[i]
            url = rec.get("finalLink") or rec.get("link") or ""
            if not url:
                url = _filing_url_fallback(ticker, exchange, label, period_type)
            if url:
                link_map[label] = url
    return link_map


def _render_filing_row(link_map: dict, hdrs: list) -> None:
    """
    Render a compact 1-row st.dataframe whose year/quarter cells are
    st.column_config.LinkColumn links to SEC filings.

    Columns with a URL  → LinkColumn(display_text="📄 View Report")
    TTM and columns without URL → TextColumn (empty cell, no link)
    Shown only when at least one filing URL exists.
    """
    if not link_map:
        return

    row = {"Item": "📄 SEC Filing"}
    col_cfg = {}

    # TTM — never a filing link
    row["TTM"] = None
    col_cfg["TTM"] = st.column_config.TextColumn("TTM", width=120)

    for col in hdrs[2:]:
        url = link_map.get(col)
        row[col] = url or None
        if url:
            col_cfg[col] = st.column_config.LinkColumn(
                col, display_text="📄 View Report", width=120
            )
        else:
            col_cfg[col] = st.column_config.TextColumn(col, width=120)

    df = pd.DataFrame([row]).set_index("Item")
    st.dataframe(df, use_container_width=True, column_config=col_cfg, height=80)


# ═════════════════════════════════════════════════════════════════════════════
class FinancialExtras:
    """
    Computes the 7 appended metric groups for the Financials tab.
    Each get_* method returns a list of row-dicts:
        {"label": str, "TTM": value, col1: value, ..., "_fmt": fmt_type}
    """

    def __init__(self, norm, overview):
        self.ov   = overview or {}
        self.is_l = norm.is_l
        self.bs_l = norm.bs_l
        self.cf_l = norm.cf_l
        self.q_is = norm.q_is
        self.q_bs = norm.q_bs
        self.q_cf = norm.q_cf
        self.rt_l = norm.raw_data.get("annual_ratios",      []) or []
        # key-metrics: end-of-period price, market cap, employees, pre-computed multiples
        self.km_l = norm.raw_data.get("annual_key_metrics",    []) or []
        self.q_km = norm.raw_data.get("quarterly_key_metrics", []) or []

    # ── data accessors ────────────────────────────────────────────────────────

    def _g(self, src, key, i):
        """Safe field getter: return float or None."""
        if not src or i >= len(src):
            return None
        rec = src[i]
        return _safe(rec.get(key)) if isinstance(rec, dict) else None

    def _src(self, stmt, p):
        """Return the appropriate data list for (statement, period)."""
        return {
            ("is", "annual"):    self.is_l,
            ("is", "quarterly"): self.q_is,
            ("bs", "annual"):    self.bs_l,
            ("bs", "quarterly"): self.q_bs,
            ("cf", "annual"):    self.cf_l,
            ("cf", "quarterly"): self.q_cf,
            ("rt", "annual"):    self.rt_l,
            ("rt", "quarterly"): [],          # ratios are annual-only
            ("km", "annual"):    self.km_l,   # key-metrics (price, mktcap, employees)
            ("km", "quarterly"): self.q_km,
        }.get((stmt, p), [])

    def _hist(self, stmt, key, i, p):
        """Historical value for (statement, key) at index i for period p."""
        return self._g(self._src(stmt, p), key, i)

    # ── TTM helpers ───────────────────────────────────────────────────────────

    def _ttm_q(self, q_list, key):
        """Sum of last 4 quarters (flow-statement items)."""
        if not q_list:
            return None
        vals = [_safe(q.get(key)) for q in q_list[:4] if isinstance(q, dict)]
        clean = [v for v in vals if v is not None]
        return sum(clean) if clean else None

    def _ttm_b(self, key):
        """Most-recent quarter (balance-sheet items)."""
        return self._g(self.q_bs, key, 0)

    # ── Adj. FCF helpers ──────────────────────────────────────────────────────

    def _adj_fcf_ttm(self):
        fcf = self._ttm_q(self.q_cf, "freeCashFlow")
        sbc = self._ttm_q(self.q_cf, "stockBasedCompensation")
        if fcf is None:
            return None
        return fcf - (_safe(sbc) or 0)

    def _adj_fcf_hist(self, i, p="annual"):
        fcf = self._hist("cf", "freeCashFlow", i, p)
        sbc = self._hist("cf", "stockBasedCompensation", i, p)
        if fcf is None:
            return None
        return fcf - (_safe(sbc) or 0)

    # ── row builder ───────────────────────────────────────────────────────────

    def _row(self, label, ttm_val, fn, hdrs, fmt="ratio"):
        """
        Build one row dict.
        hdrs[0]="Item", hdrs[1]="TTM", hdrs[2:]= historical columns.
        fn(i) returns the value for historical column at index i (0 = most recent).
        """
        row = {"label": label, "TTM": ttm_val, "_fmt": fmt}
        for i, col in enumerate(hdrs[2:]):
            try:
                row[col] = fn(i)
            except Exception:
                row[col] = None
        return row

    # ── Piotroski F-Score ─────────────────────────────────────────────────────

    def _piotroski_at(self, i):
        """9-point Piotroski score at annual index i (compares i vs i+1)."""
        if i + 1 >= len(self.is_l) or i + 1 >= len(self.bs_l) or i + 1 >= len(self.cf_l):
            return None
        score = 0
        ni   = self._g(self.is_l, "netIncome",           i)
        cfo  = self._g(self.cf_l, "operatingCashFlow",   i)
        ta0  = self._g(self.bs_l, "totalAssets",          i)
        ta1  = self._g(self.bs_l, "totalAssets",          i + 1)
        ni1  = self._g(self.is_l, "netIncome",            i + 1)
        roa0 = _d(ni,  ta0)
        roa1 = _d(ni1, ta1)
        if roa0 is not None and roa0 > 0:              score += 1
        if cfo  is not None and cfo  > 0:              score += 1
        if roa0 is not None and roa1 is not None and roa0 > roa1: score += 1
        if ni is not None and cfo is not None and cfo > ni:        score += 1
        ltd0 = self._g(self.bs_l, "longTermDebt",             i)
        ltd1 = self._g(self.bs_l, "longTermDebt",             i + 1)
        ca0  = self._g(self.bs_l, "totalCurrentAssets",       i)
        cl0  = self._g(self.bs_l, "totalCurrentLiabilities",  i)
        ca1  = self._g(self.bs_l, "totalCurrentAssets",       i + 1)
        cl1  = self._g(self.bs_l, "totalCurrentLiabilities",  i + 1)
        cr0  = _d(ca0, cl0)
        cr1  = _d(ca1, cl1)
        if ltd0 is not None and ltd1 is not None and ltd0 < ltd1: score += 1
        if cr0  is not None and cr1  is not None and cr0  > cr1:  score += 1
        sh0  = (self._g(self.is_l, "weightedAverageShsOutDil", i)
                or self._g(self.is_l, "weightedAverageShsOut", i))
        sh1  = (self._g(self.is_l, "weightedAverageShsOutDil", i + 1)
                or self._g(self.is_l, "weightedAverageShsOut", i + 1))
        if sh0 is not None and sh1 is not None and sh0 <= sh1: score += 1
        gm0 = _d(self._g(self.is_l, "grossProfit", i),     self._g(self.is_l, "revenue", i))
        gm1 = _d(self._g(self.is_l, "grossProfit", i + 1), self._g(self.is_l, "revenue", i + 1))
        at0 = _d(self._g(self.is_l, "revenue", i),     ta0)
        at1 = _d(self._g(self.is_l, "revenue", i + 1), ta1)
        if gm0 is not None and gm1 is not None and gm0 > gm1: score += 1
        if at0 is not None and at1 is not None and at0 > at1: score += 1
        return score

    # ══════════════════════════════════════════════════════════════════════════
    # 1. MARKET & VALUATION
    # ══════════════════════════════════════════════════════════════════════════

    def get_market_valuation(self, hdrs, p):
        # ── TTM values (always from live overview + trailing quarters) ────────
        mkt      = _safe(self.ov.get("mktCap"))
        price    = _safe(self.ov.get("price"))
        emp      = _safe(self.ov.get("fullTimeEmployees"))
        ni_ttm   = self._ttm_q(self.q_is, "netIncome")
        rev_ttm  = self._ttm_q(self.q_is, "revenue")
        af_ttm   = self._adj_fcf_ttm()
        div_ttm  = self._ttm_q(self.q_cf, "commonDividendsPaid")
        rp_ttm   = self._ttm_q(self.q_cf, "commonStockRepurchased")
        book_ttm = self._ttm_b("totalStockholdersEquity")
        div_abs  = abs(div_ttm) if div_ttm is not None else 0
        rp_abs   = abs(rp_ttm)  if rp_ttm  is not None else 0

        # km_src: key-metrics list matching the current period
        km_src = self.q_km if p == "quarterly" else self.km_l

        # ── helpers using end-of-period price / market cap from key-metrics ──
        def _km(key, i):
            """End-of-period value from key-metrics for historical column i."""
            return self._g(km_src, key, i)

        def _mkt_h(i):
            return _km("marketCap", i)

        def _pe_h(i):
            # Primary: pre-computed end-of-period P/E from key-metrics
            pe = _km("peRatio", i)
            if pe is not None:
                return pe
            # Fallback: Price / EPS Diluted — return "N/M" when EPS ≤ 0
            px  = _price_h(i)
            eps = self._hist("is", "epsDiluted", i, p)
            if eps is None or eps <= 0:
                return "N/M"
            return _d(px, eps)

        def _ps_h(i):
            return (_km("priceToSalesRatio", i)
                    or self._g(self.rt_l, "priceToSalesRatio", i))

        def _pb_h(i):
            return (_km("pbRatio", i)
                    or self._g(self.rt_l, "priceToBookRatio", i))

        def _paf_h(i):
            """P/Adj.FCF = end-of-period market cap / Adj.FCF for that period."""
            return _d(_mkt_h(i), self._adj_fcf_hist(i, p))

        def _by_h(i):
            """Buyback yield = repurchases / end-of-period market cap."""
            rp = self._hist("cf", "commonStockRepurchased", i, p)
            mc = _mkt_h(i)
            return _d(abs(rp) if rp else None, mc)

        def _tsy_h(i):
            """Total shareholder yield = (div + repurch) / end-of-period market cap."""
            d  = self._hist("cf", "commonDividendsPaid",   i, p)
            rp = self._hist("cf", "commonStockRepurchased", i, p)
            mc = _mkt_h(i)
            return _d((abs(d) if d else 0) + (abs(rp) if rp else 0), mc)

        def _dr_h(i):
            """Div.&Repurch./Adj.FCF for period i."""
            d  = self._hist("cf", "commonDividendsPaid",   i, p)
            rp = self._hist("cf", "commonStockRepurchased", i, p)
            af = self._adj_fcf_hist(i, p)
            return _d((abs(d) if d else 0) + (abs(rp) if rp else 0), af)

        def _dil_h(i):
            src = self._src("is", p)
            a = (self._g(src, "weightedAverageShsOutDil", i)
                 or self._g(src, "weightedAverageShsOut", i))
            b = (self._g(src, "weightedAverageShsOutDil", i + 1)
                 or self._g(src, "weightedAverageShsOut", i + 1))
            return _d((a - b) if (a and b) else None, b)

        def _rev_emp_h(i):
            rev = self._hist("is", "revenue", i, p)
            e   = _km("numberOfEmployees", i)
            return _d(rev, e)

        def _ni_emp_h(i):
            ni = self._hist("is", "netIncome", i, p)
            e  = _km("numberOfEmployees", i)
            return _d(ni, e)

        # ── Share counts for TTM dilution ─────────────────────────────────────
        sh0 = (self._g(self.is_l, "weightedAverageShsOutDil", 0)
               or self._g(self.is_l, "weightedAverageShsOut", 0))
        sh1 = (self._g(self.is_l, "weightedAverageShsOutDil", 1)
               or self._g(self.is_l, "weightedAverageShsOut", 1))
        by_ttm  = _d(rp_abs or None, mkt)
        dil_ttm = _d((sh0 - sh1) if (sh0 and sh1) else None, sh1)
        byd_ttm = (by_ttm / dil_ttm
                   if (by_ttm is not None and dil_ttm and dil_ttm != 0) else None)

        def _price_h(i):
            # Prefer stockPrice from key-metrics; derive from mktCap÷shares when absent
            px = _km("stockPrice", i)
            if px is None:
                mc = _km("marketCap", i)
                sh = (self._hist("is", "weightedAverageShsOutDil", i, p)
                      or self._hist("is", "weightedAverageShsOut",    i, p))
                px = _d(mc, sh)
            return px

        rows = [
            self._row("Price",
                      price,
                      _price_h,                                           hdrs),
            self._row("Market Cap",
                      mkt,
                      _mkt_h,                                             hdrs, "money"),
            self._row("P/E",
                      _d(mkt, ni_ttm),
                      _pe_h,                                              hdrs),
            self._row("P/S",
                      _d(mkt, rev_ttm),
                      _ps_h,                                              hdrs),
            self._row("P/B",
                      _d(mkt, book_ttm),
                      _pb_h,                                              hdrs),
            self._row("P/Adj. FCF",
                      _d(mkt, af_ttm),
                      _paf_h,                                             hdrs),
            self._row("Buyback Yield",
                      by_ttm,
                      _by_h,                                              hdrs, "pct"),
            self._row("Dilution",
                      dil_ttm,
                      _dil_h,                                             hdrs, "pct"),
            self._row("Buyback Yield / (Dilution)",
                      byd_ttm,
                      lambda i: None,                                     hdrs),
            self._row("Div.&Repurch./ Adj. FCF",
                      _d(div_abs + rp_abs, af_ttm),
                      _dr_h,                                              hdrs),
            self._row("Total shareholder yield",
                      _d(div_abs + rp_abs, mkt),
                      _tsy_h,                                             hdrs, "pct"),
            self._row("Piotroski score",
                      self._piotroski_at(0),
                      lambda i: self._piotroski_at(i),                   hdrs, "int"),
            self._row("5 Yr Beta",
                      _safe(self.ov.get("beta")),
                      lambda i: None,                                     hdrs),
            self._row("WACC",
                      None,
                      lambda i: None,                                     hdrs),
            self._row("Num. of Employees",
                      emp,
                      lambda i: _km("numberOfEmployees", i),              hdrs, "int"),
            self._row("Revenue / Employee",
                      _d(rev_ttm, emp),
                      _rev_emp_h,                                         hdrs),
            self._row("Net Income / Employee",
                      _d(ni_ttm, emp),
                      _ni_emp_h,                                          hdrs),
        ]
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # 2. CAPITAL STRUCTURE & RATIOS
    # ══════════════════════════════════════════════════════════════════════════

    def get_capital_structure(self, hdrs, p):
        debt_ttm   = self._ttm_b("totalDebt")
        eq_ttm     = self._ttm_b("totalStockholdersEquity")
        cash_ttm   = self._ttm_b("cashAndCashEquivalents")
        ebitda_ttm = self._ttm_q(self.q_is, "ebitda")
        ebit_ttm   = self._ttm_q(self.q_is, "operatingIncome")
        int_ttm    = self._ttm_q(self.q_is, "interestExpense")
        sbc_ttm    = self._ttm_q(self.q_cf, "stockBasedCompensation")
        fcf_ttm    = self._ttm_q(self.q_cf, "freeCashFlow")
        af_ttm     = self._adj_fcf_ttm()
        nd_ttm     = ((debt_ttm or 0) - (cash_ttm or 0)) if debt_ttm is not None else None

        def _de_h(i):
            return self._g(self.rt_l, "debtEquityRatio", i)

        def _deb_h(i):
            return _d(self._g(self.bs_l, "totalDebt", i),
                      self._g(self.is_l, "ebitda", i))

        def _ndeb_h(i):
            d  = self._g(self.bs_l, "totalDebt", i)
            c  = self._g(self.bs_l, "cashAndCashEquivalents", i)
            eb = self._g(self.is_l, "ebitda", i)
            nd = (d - c) if (d is not None and c is not None) else d
            return _d(nd, eb)

        def _daf_h(i):
            return _d(self._g(self.bs_l, "totalDebt", i),
                      self._adj_fcf_hist(i))

        def _ic_h(i):
            ie = self._g(self.is_l, "interestExpense", i)
            return (self._g(self.rt_l, "interestCoverage", i)
                    or _d(self._g(self.is_l, "operatingIncome", i),
                          abs(ie) if ie else None))

        def _sbcfcf_h(i):
            # SBC / FCF (no abs — formula is literal SBC ÷ FCF)
            sbc = self._g(self.is_l, "stockBasedCompensation", i)
            fcf = self._g(self.cf_l, "freeCashFlow", i)
            return _d(sbc, fcf)

        rows = [
            self._row("Debt / Equity",
                      _d(debt_ttm, eq_ttm),       _de_h,     hdrs),
            self._row("Debt / EBITDA",
                      _d(debt_ttm, ebitda_ttm),   _deb_h,    hdrs),
            self._row("Net Debt / EBITDA",
                      _d(nd_ttm, ebitda_ttm),     _ndeb_h,   hdrs),
            self._row("Debt / Adj. FCF",
                      _d(debt_ttm, af_ttm),       _daf_h,    hdrs),
            self._row("Interest Coverage (EBIT/Interest)",
                      _d(ebit_ttm,
                         abs(int_ttm) if int_ttm else None), _ic_h, hdrs),
            self._row("SBC / FCF",
                      _d(sbc_ttm, fcf_ttm),       _sbcfcf_h, hdrs),
            self._row("ROIC / WACC",              None, lambda i: None, hdrs),
        ]
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # 3. PROFITABILITY  (absolute values — scale applies)
    # ══════════════════════════════════════════════════════════════════════════

    def get_profitability(self, hdrs, p):
        rows = [
            self._row("Gross Profit",
                      self._ttm_q(self.q_is, "grossProfit"),
                      lambda i: self._hist("is", "grossProfit",      i, "annual"), hdrs, "money"),
            self._row("EBIT",
                      self._ttm_q(self.q_is, "operatingIncome"),
                      lambda i: self._hist("is", "operatingIncome",  i, "annual"), hdrs, "money"),
            self._row("EBITDA",
                      self._ttm_q(self.q_is, "ebitda"),
                      lambda i: self._hist("is", "ebitda",           i, "annual"), hdrs, "money"),
            self._row("Net Income",
                      self._ttm_q(self.q_is, "netIncome"),
                      lambda i: self._hist("is", "netIncome",        i, "annual"), hdrs, "money"),
            self._row("Adj. FCF",
                      self._adj_fcf_ttm(),
                      lambda i: self._adj_fcf_hist(i),                             hdrs, "money"),
        ]
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # 4. RETURNS  (as percentages)
    # ══════════════════════════════════════════════════════════════════════════

    def get_returns(self, hdrs, p):
        ni_ttm   = self._ttm_q(self.q_is, "netIncome")
        ebit_ttm = self._ttm_q(self.q_is, "operatingIncome")
        tax_ttm  = self._ttm_q(self.q_is, "incomeTaxExpense")
        ebt_ttm  = self._ttm_q(self.q_is, "incomeBeforeTax")
        cfo_ttm  = self._ttm_q(self.q_cf, "operatingCashFlow")
        capx_ttm = self._ttm_q(self.q_cf, "capitalExpenditure")
        eq_ttm   = self._ttm_b("totalStockholdersEquity")
        eq_ann0  = self._g(self.bs_l, "totalStockholdersEquity", 0)
        ta_ttm   = self._ttm_b("totalAssets")
        ta_ann0  = self._g(self.bs_l, "totalAssets", 0)
        debt_ttm = self._ttm_b("totalDebt")
        cl_ttm   = self._ttm_b("totalCurrentLiabilities")

        def _avg2(a, b):
            vals = [v for v in [a, b] if v is not None]
            return sum(vals) / len(vals) if vals else None

        avg_eq  = _avg2(eq_ttm, eq_ann0)
        avg_ta  = _avg2(ta_ttm, ta_ann0)
        tr = (max(0.0, min(tax_ttm / ebt_ttm, 0.5))
              if (ebt_ttm and ebt_ttm != 0 and tax_ttm is not None) else 0.21)
        nopat = ebit_ttm * (1 - tr) if ebit_ttm is not None else None
        ic    = ((eq_ttm or 0) + (debt_ttm or 0)) if (eq_ttm or debt_ttm) else None

        roic_ttm   = _d(nopat, ic)
        fcfroc_ttm = _d(cfo_ttm - abs(capx_ttm or 0) if cfo_ttm else None, ic)
        roe_ttm    = _d(ni_ttm, avg_eq)
        roa_ttm    = _d(ni_ttm, avg_ta)
        cap_emp    = (ta_ttm - (cl_ttm or 0)) if ta_ttm is not None else None
        roce_ttm   = _d(ebit_ttm, cap_emp)

        def _roic_h(i):
            eb  = self._g(self.is_l, "operatingIncome", i)
            ebt = self._g(self.is_l, "incomeBeforeTax",  i)
            tx  = self._g(self.is_l, "incomeTaxExpense", i)
            tr  = (max(0.0, min(tx / ebt, 0.5))
                   if (ebt and ebt != 0 and tx is not None) else 0.21)
            np_ = eb * (1 - tr) if eb else None
            eq_ = self._g(self.bs_l, "totalStockholdersEquity", i)
            d_  = self._g(self.bs_l, "totalDebt", i)
            ic_ = ((eq_ or 0) + (d_ or 0)) if (eq_ or d_) else None
            return _d(np_, ic_)

        def _roce_h(i):
            eb = self._g(self.is_l, "operatingIncome",       i)
            ta = self._g(self.bs_l, "totalAssets",            i)
            cl = self._g(self.bs_l, "totalCurrentLiabilities", i)
            return _d(eb, (ta - (cl or 0)) if ta else None)

        rows = [
            self._row("ROIC",    roic_ttm,
                      _roic_h,                                              hdrs, "pct"),
            self._row("FCF ROC", fcfroc_ttm,
                      lambda i: None,                                       hdrs, "pct"),
            self._row("ROE",     roe_ttm,
                      lambda i: self._g(self.rt_l, "returnOnEquity", i),   hdrs, "pct"),
            self._row("ROA",     roa_ttm,
                      lambda i: self._g(self.rt_l, "returnOnAssets", i),   hdrs, "pct"),
            self._row("ROCE",    roce_ttm,
                      lambda i: (self._g(self.rt_l, "returnOnCapitalEmployed", i)
                                 or _roce_h(i)),                            hdrs, "pct"),
        ]
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # 5. LIQUIDITY
    # ══════════════════════════════════════════════════════════════════════════

    def get_liquidity(self, hdrs, p):
        ca_ttm   = self._ttm_b("totalCurrentAssets")
        cl_ttm   = self._ttm_b("totalCurrentLiabilities")
        cash_ttm = self._ttm_b("cashAndCashEquivalents")
        debt_ttm = self._ttm_b("totalDebt")
        nwc_ttm  = ((ca_ttm or 0) - (cl_ttm or 0)) if ca_ttm is not None else None

        def _cr_h(i):
            return (self._g(self.rt_l, "currentRatio", i)
                    or _d(self._g(self.bs_l, "totalCurrentAssets",      i),
                          self._g(self.bs_l, "totalCurrentLiabilities", i)))

        def _c2d_h(i):
            return _d(self._g(self.bs_l, "cashAndCashEquivalents", i),
                      self._g(self.bs_l, "totalDebt", i))

        def _nwc_h(i):
            ca = self._g(self.bs_l, "totalCurrentAssets",      i)
            cl = self._g(self.bs_l, "totalCurrentLiabilities", i)
            return (ca - (cl or 0)) if ca is not None else None

        rows = [
            self._row("Current Ratio",
                      _d(ca_ttm, cl_ttm),    _cr_h,  hdrs),
            self._row("Cash to Debt",
                      _d(cash_ttm, debt_ttm), _c2d_h, hdrs),
            self._row("Net Working Capital (NWC)",
                      nwc_ttm,               _nwc_h, hdrs, "money"),
        ]
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # 6. DIVIDENDS
    # ══════════════════════════════════════════════════════════════════════════

    def get_dividends(self, hdrs, p):
        mkt      = _safe(self.ov.get("mktCap"))
        div_ttm  = self._ttm_q(self.q_cf, "commonDividendsPaid")
        ni_ttm   = self._ttm_q(self.q_is, "netIncome")
        sh_ttm   = (self._ttm_q(self.q_is, "weightedAverageShsOutDil")
                    or self._ttm_q(self.q_is, "weightedAverageShsOut"))
        div_abs  = abs(div_ttm) if div_ttm is not None else None

        def _dps_h(i):
            d  = self._g(self.cf_l, "commonDividendsPaid", i)
            sh = (self._g(self.is_l, "weightedAverageShsOutDil", i)
                  or self._g(self.is_l, "weightedAverageShsOut", i))
            return _d(abs(d) if d else None, sh)

        def _po_h(i):
            return (self._g(self.rt_l, "payoutRatio", i)
                    or _d(abs(self._g(self.cf_l, "commonDividendsPaid", i) or 0),
                          self._g(self.is_l, "netIncome", i)))

        rows = [
            self._row("Yield",
                      _d(div_abs, mkt),
                      lambda i: self._g(self.rt_l, "dividendYield", i), hdrs, "pct"),
            self._row("Payout",
                      _d(div_abs, ni_ttm),
                      _po_h,                                             hdrs, "pct"),
            self._row("DPS",
                      _d(div_abs, sh_ttm),
                      _dps_h,                                            hdrs),
        ]
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # 7. EFFICIENCY
    # ══════════════════════════════════════════════════════════════════════════

    def get_efficiency(self, hdrs, p):
        rev_ttm  = self._ttm_q(self.q_is, "revenue")
        cogs_ttm = self._ttm_q(self.q_is, "costOfRevenue")

        def _bs_avg(key):
            v0 = self._ttm_b(key)
            v1 = self._g(self.bs_l, key, 0)
            vals = [v for v in [v0, v1] if v is not None]
            return sum(vals) / len(vals) if vals else None

        ar  = _bs_avg("netReceivables")
        inv = _bs_avg("inventory")
        ap  = _bs_avg("accountPayables")
        ta  = _bs_avg("totalAssets")
        ppe = _bs_avg("propertyPlantEquipmentNet")
        ca  = _bs_avg("totalCurrentAssets")
        cl  = _bs_avg("totalCurrentLiabilities")
        nwc = ((ca or 0) - (cl or 0)) if ca is not None else None

        rt  = _d(rev_ttm, ar)
        it  = _d(cogs_ttm or rev_ttm, inv)
        pt  = _d(cogs_ttm or rev_ttm, ap)
        dso = (365 / rt) if rt and rt != 0 else None
        dio = (365 / it) if it and it != 0 else None
        dpo = (365 / pt) if pt and pt != 0 else None
        opc = (dso or 0) + (dio or 0) if (dso is not None or dio is not None) else None
        ccc = (opc - (dpo or 0)) if (opc is not None and dpo is not None) else None
        wct = _d(rev_ttm, nwc)
        fat = _d(rev_ttm, ppe)
        at  = _d(rev_ttm, ta)

        def _rt_field(key, i):
            return self._g(self.rt_l, key, i)

        rows = [
            self._row("Receivable turnover",
                      rt,  lambda i: _rt_field("receivablesTurnover",     i), hdrs),
            self._row("Average receivables collection day",
                      dso, lambda i: _rt_field("daysOfSalesOutstanding",  i), hdrs, "days"),
            self._row("Inventory turnover",
                      it,  lambda i: _rt_field("inventoryTurnover",        i), hdrs),
            self._row("Average days inventory in stock",
                      dio, lambda i: _rt_field("daysOfInventoryOutstanding", i), hdrs, "days"),
            self._row("Payables turnover",
                      pt,  lambda i: _rt_field("payablesTurnover",         i), hdrs),
            self._row("Average days payables outstanding",
                      dpo, lambda i: _rt_field("daysOfPayablesOutstanding", i), hdrs, "days"),
            self._row("Operating cycle",
                      opc, lambda i: _rt_field("operatingCycle",           i), hdrs, "days"),
            self._row("Cash cycle",
                      ccc, lambda i: _rt_field("cashConversionCycle",      i), hdrs, "days"),
            self._row("Working capital turnover",
                      wct, lambda i: None,                                     hdrs),
            self._row("Fixed asset turnover",
                      fat, lambda i: _rt_field("fixedAssetTurnover",       i), hdrs),
            self._row("Asset turnover",
                      at,  lambda i: _rt_field("assetTurnover",            i), hdrs),
        ]
        return rows


# ═════════════════════════════════════════════════════════════════════════════
# Public entry point — called from app.py
# ═════════════════════════════════════════════════════════════════════════════

def render_financials_tab(norm, raw):
    """
    Renders the complete Financials tab.
    Reads Period and Scale from st.session_state.
    Existing 4 tables are rendered first (unchanged), then 7 new groups below.
    """
    # ── Controls row: Period | Scale | Currency ───────────────────────────────
    ctrl_l, ctrl_m, ctrl_r = st.columns([3, 3, 4])
    with ctrl_l:
        st.radio("Period:", ["Annual", "Quarterly"], key="view_type", horizontal=True)
    with ctrl_m:
        st.radio("Scale:", ["B", "MM", "K"], key="fin_scale", horizontal=True)
    with ctrl_r:
        _currency = ""
        if norm and norm.is_l and isinstance(norm.is_l[0], dict):
            _currency = norm.is_l[0].get("reportedCurrency", "")
        if not _currency:
            _currency = raw.get("currency") or "N/A"
        st.markdown(
            f"<div style='padding-top:28px;color:#4d6b88;font-size:0.85em;'>"
            f"Currency: <strong>{_currency}</strong></div>",
            unsafe_allow_html=True,
        )

    if not norm:
        st.info("Financial data is unavailable for this ticker.")
        return

    p     = st.session_state["view_type"].lower()
    scale = st.session_state.get("fin_scale", "MM")
    div   = {"B": 1e9, "MM": 1e6, "K": 1e3}[scale]

    # fmt_fin: scale monetary values (used by the original 4 tables)
    def fmt_fin(v):
        if v is None:
            return "N/A"
        try:
            if pd.isna(v):
                return "N/A"
        except (TypeError, ValueError):
            pass
        if v == 0:
            return "N/A"
        return f"{v / div:,.2f}"

    hdrs        = norm.get_column_headers(p)
    period_cols = hdrs[1:]
    fin_col_cfg = {col: st.column_config.TextColumn(col, width=120) for col in period_cols}

    # ── Original 4 tables ─────────────────────────────────────────────────────
    ticker_sym = raw.get("symbol", "?")

    # Source lists for building SEC filing link maps (annual vs quarterly)
    stmt_src = {
        "Income Statement": norm.is_l if p == "annual" else norm.q_is,
        "Cashflow":         norm.cf_l if p == "annual" else norm.q_cf,
        "Balance Sheet":    norm.bs_l if p == "annual" else norm.q_bs,
    }

    for title, method in [
        ("Income Statement", norm.get_income_statement),
        ("Cashflow",         norm.get_cash_flow),
        ("Balance Sheet",    norm.get_balance_sheet),
        ("Debt",             norm.get_debt_table),
    ]:
        lmap = {}  # reset for each table
        st.markdown(f"<div class='section-header'>{title}</div>",
                    unsafe_allow_html=True)
        if title != "Debt":
            src  = stmt_src[title]
            lmap = _build_link_map(
                src, hdrs[2:],
                ticker=ticker_sym,
                exchange=raw.get("exchangeShortName") or raw.get("exchange", ""),
                period_type=p,
            )

        rows_data = method(p)

        # Debug: verify raw EPS values before any formatting
        if title == "Income Statement":
            eps_row = next((r for r in rows_data if r.get("label") == "EPS"), None)
            if eps_row:
                for col in hdrs[2:]:
                    print(f"DEBUG: Ticker: {ticker_sym}, Year: {col}, Raw EPS: {eps_row.get(col)}")

        table_rows = []
        for rec in rows_data:
            label = rec["label"]
            record = {"Item": label}
            for h in period_cols:
                raw_v = rec.get(h)
                if label == "EPS":
                    # EPS is a per-share decimal — never divide by scale
                    f = _safe(raw_v)
                    record[h] = f"{f:,.2f}" if (f is not None and f != 0) else "N/A"
                else:
                    record[h] = fmt_fin(raw_v)
            table_rows.append(record)

        df = pd.DataFrame(table_rows)
        if title != "Debt":
            _render_filing_row(lmap, hdrs)
        st.dataframe(df.set_index("Item"),
                     use_container_width=True, column_config=fin_col_cfg)

    # ── 7 new metric groups — appended strictly after Debt ────────────────────
    fe = FinancialExtras(norm, raw)
    sections = [
        ("Market & Valuation",         fe.get_market_valuation(hdrs, p)),
        ("Capital Structure & Ratios",  fe.get_capital_structure(hdrs, p)),
        ("Profitability",               fe.get_profitability(hdrs, p)),
        ("Returns",                     fe.get_returns(hdrs, p)),
        ("Liquidity",                   fe.get_liquidity(hdrs, p)),
        ("Dividends",                   fe.get_dividends(hdrs, p)),
        ("Efficiency",                  fe.get_efficiency(hdrs, p)),
    ]
    for title, rows in sections:
        st.markdown(f"<div class='section-header'>{title}</div>",
                    unsafe_allow_html=True)
        table_data = []
        for row in rows:
            record = {"Item": row["label"]}
            fmt_type = row.get("_fmt", "ratio")
            for col in period_cols:
                record[col] = _fmt(row.get(col), fmt_type, div)
            table_data.append(record)
        df = pd.DataFrame(table_data)
        st.dataframe(df.set_index("Item"),
                     use_container_width=True, column_config=fin_col_cfg)
