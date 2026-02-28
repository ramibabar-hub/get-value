class InsightsAgent:
    """
    Computes all Insights tab metrics from raw financial statement data.

    Data sources:
      - annual_income_statement, annual_balance_sheet, annual_cash_flow
      - quarterly_income_statement, quarterly_balance_sheet, quarterly_cash_flow
      - annual_ratios (for pre-computed ratios like dividendYield, payoutRatio)
      - overview dict (mktCap, price, fullTimeEmployees, pe, eps, etc.)
    """

    def __init__(self, raw_data: dict, overview: dict):
        self.is_l = raw_data.get("annual_income_statement", []) or []
        self.bs_l = raw_data.get("annual_balance_sheet", []) or []
        self.cf_l = raw_data.get("annual_cash_flow", []) or []
        self.q_is = raw_data.get("quarterly_income_statement", []) or []
        self.q_bs = raw_data.get("quarterly_balance_sheet", []) or []
        self.q_cf = raw_data.get("quarterly_cash_flow", []) or []
        self.rt_l = raw_data.get("annual_ratios", []) or []
        self.km_l = raw_data.get("annual_key_metrics", []) or []
        self.ov   = overview or {}

    # ── helpers ──────────────────────────────────────────────────────────────

    def _safe(self, v):
        """Return float or None."""
        if v is None:
            return None
        try:
            f = float(v)
            return f if f == f else None   # NaN guard
        except (TypeError, ValueError):
            return None

    def _ttm_flow(self, q_list, key):
        """Sum last 4 quarters for flow-statement items (IS/CF)."""
        if not q_list:
            return None
        vals = [self._safe(q.get(key)) for q in q_list[:4]]
        if all(v is None for v in vals):
            return None
        return sum(v or 0 for v in vals)

    def _ttm_bs(self, key):
        """Most recent quarter for balance-sheet items."""
        if not self.q_bs:
            return None
        return self._safe(self.q_bs[0].get(key))

    def _ann(self, src_list, key, idx):
        """Annual value at index idx (0 = most recent)."""
        if not src_list or idx >= len(src_list):
            return None
        rec = src_list[idx]
        if not isinstance(rec, dict):
            return None
        return self._safe(rec.get(key))

    def _avg(self, values):
        """Average of non-None values."""
        clean = [v for v in values if v is not None]
        return sum(clean) / len(clean) if clean else None

    def _div(self, a, b):
        """Safe division — returns None on zero/None denominator."""
        a = self._safe(a)
        b = self._safe(b)
        if a is None or b is None or b == 0:
            return None
        return a / b

    def _cagr(self, end_val, start_val, years):
        """CAGR = (end/start)^(1/years) - 1. Returns 'N/M' for invalid inputs.

        Both end and start must be strictly positive — a negative or zero
        value in either position makes the ratio negative, which raises a
        complex number when taken to a fractional power.
        """
        e = self._safe(end_val)
        s = self._safe(start_val)
        if e is None or s is None or years <= 0:
            return "N/M"
        if e <= 0 or s <= 0:   # negative/zero → complex number territory
            return "N/M"
        try:
            result = (e / s) ** (1.0 / years) - 1
            # Final safety net: reject anything that isn't a plain real float
            if not isinstance(result, float):
                return "N/M"
            return result
        except (ZeroDivisionError, ValueError, TypeError):
            return "N/M"

    def _avg_annual(self, src_list, key, n):
        """Average of first n annual values."""
        vals = [self._ann(src_list, key, i) for i in range(n)]
        return self._avg([v for v in vals if v is not None])

    def _ratio_field(self, key, idx=0):
        """Pull a pre-computed field from annual ratios list."""
        if not self.rt_l or idx >= len(self.rt_l):
            return None
        return self._safe(self.rt_l[idx].get(key))

    def _ratio_avg(self, key, n):
        """Average of first n ratios records."""
        vals = [self._safe(r.get(key)) for r in self.rt_l[:n] if isinstance(r, dict)]
        return self._avg([v for v in vals if v is not None])

    def _km_avg(self, key, n):
        """Average of first n annual key-metrics records for field key."""
        vals = [self._safe(r.get(key)) for r in self.km_l[:n] if isinstance(r, dict)]
        return self._avg([v for v in vals if v is not None])

    # ── Adj. FCF = Free Cash Flow - SBC ──────────────────────────────────────

    def _adj_fcf(self, src_cf, src_is, idx):
        """Adj. FCF = Free Cash Flow - Stock Based Compensation."""
        fcf = self._ann(src_cf, "freeCashFlow", idx)
        sbc = self._ann(src_is, "stockBasedCompensation", idx)
        if fcf is None:
            return None
        return fcf - (self._safe(sbc) or 0)

    def _ttm_adj_fcf(self):
        """TTM Adj. FCF = TTM Free Cash Flow - TTM Stock Based Compensation."""
        fcf = self._ttm_flow(self.q_cf, "freeCashFlow")
        sbc = self._ttm_flow(self.q_is, "stockBasedCompensation")
        if fcf is None:
            return None
        return fcf - (self._safe(sbc) or 0)

    # ── EV helper ─────────────────────────────────────────────────────────────

    def _ev(self):
        """Enterprise Value = mktCap + totalDebt - cash (TTM balance-sheet)."""
        mkt  = self._safe(self.ov.get("mktCap"))
        debt = self._ttm_bs("totalDebt")
        cash = self._ttm_bs("cashAndCashEquivalents")
        if mkt is None:
            return None
        return mkt + (debt or 0) - (cash or 0)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. CAGR
    # ══════════════════════════════════════════════════════════════════════════

    def get_insights_cagr(self):
        """3yr / 5yr / 10yr CAGR for key line items."""
        def row(label, fn_end, fn_3, fn_5, fn_10):
            return {
                "CAGR":  label,
                "3yr":   self._cagr(fn_end(), fn_3(),  3),
                "5yr":   self._cagr(fn_end(), fn_5(),  5),
                "10yr":  self._cagr(fn_end(), fn_10(), 10),
            }

        # helpers to extract annual values
        def is_val(key, idx):  return self._ann(self.is_l, key, idx)
        def cf_val(key, idx):  return self._ann(self.cf_l, key, idx)

        rows = [
            row("Revenues",
                lambda: is_val("revenue", 0),
                lambda: is_val("revenue", 3),
                lambda: is_val("revenue", 5),
                lambda: is_val("revenue", 10)),
            row("Operating income",
                lambda: is_val("operatingIncome", 0),
                lambda: is_val("operatingIncome", 3),
                lambda: is_val("operatingIncome", 5),
                lambda: is_val("operatingIncome", 10)),
            row("EBITDA",
                lambda: is_val("ebitda", 0),
                lambda: is_val("ebitda", 3),
                lambda: is_val("ebitda", 5),
                lambda: is_val("ebitda", 10)),
            row("EPS Diluted",
                lambda: is_val("epsDiluted", 0),
                lambda: is_val("epsDiluted", 3),
                lambda: is_val("epsDiluted", 5),
                lambda: is_val("epsDiluted", 10)),
            row("Adj. FCF",
                lambda: self._adj_fcf(self.cf_l, self.is_l, 0),
                lambda: self._adj_fcf(self.cf_l, self.is_l, 3),
                lambda: self._adj_fcf(self.cf_l, self.is_l, 5),
                lambda: self._adj_fcf(self.cf_l, self.is_l, 10)),
            row("Shares outs.",
                lambda: is_val("weightedAverageShsOutDil", 0) or is_val("weightedAverageShsOut", 0),
                lambda: is_val("weightedAverageShsOutDil", 3) or is_val("weightedAverageShsOut", 3),
                lambda: is_val("weightedAverageShsOutDil", 5) or is_val("weightedAverageShsOut", 5),
                lambda: is_val("weightedAverageShsOutDil", 10) or is_val("weightedAverageShsOut", 10)),
        ]
        return rows

    # ══════════════════════════════════════════════════════════════════════════
    # 2. Valuation Multiples
    # ══════════════════════════════════════════════════════════════════════════

    def get_insights_valuation(self):
        ev       = self._ev()
        mkt      = self._safe(self.ov.get("mktCap"))
        price    = self._safe(self.ov.get("price"))

        # TTM income items
        rev_ttm    = self._ttm_flow(self.q_is, "revenue")
        ebitda_ttm = self._ttm_flow(self.q_is, "ebitda")
        ni_ttm     = self._ttm_flow(self.q_is, "netIncome")
        fcf_ttm    = self._ttm_flow(self.q_cf, "freeCashFlow")
        adj_fcf_t  = self._ttm_adj_fcf()
        eps_ttm    = self._ttm_flow(self.q_is, "epsDiluted")

        # TTM balance-sheet
        book_ttm   = self._ttm_bs("totalStockholdersEquity")
        shares_ttm = (self._ttm_bs("commonStock")
                      or self._ttm_flow(self.q_is, "weightedAverageShsOutDil")
                      or self._ttm_flow(self.q_is, "weightedAverageShsOut"))

        # Derived TTM
        ev_ebitda_t = self._div(ev, ebitda_ttm)
        ev_adjfcf_t = self._div(ev, adj_fcf_t)
        pe_ttm      = self._div(mkt, ni_ttm)
        ps_ttm      = self._div(mkt, rev_ttm)
        pb_ttm      = self._div(mkt, book_ttm)
        pfcf_ttm    = self._div(mkt, fcf_ttm)

        # PEG: P/E ÷ 3yr EPS CAGR * 100
        cagr_rows   = self.get_insights_cagr()
        eps_3yr     = next((r["3yr"] for r in cagr_rows if r["CAGR"] == "EPS Diluted"), None)
        peg_ttm     = None
        if pe_ttm is not None and isinstance(eps_3yr, float) and eps_3yr > 0:
            peg_ttm = pe_ttm / (eps_3yr * 100)

        earn_yield  = self._div(ni_ttm, mkt)
        adjfcf_yield = self._div(adj_fcf_t, mkt)

        # Piotroski F-Score (annual)
        piotroski = self._piotroski()

        # 5yr / 10yr averages from key-metrics (end-of-period per-year values)
        return [
            {"Valuation": "EV / EBITDA",        "TTM": ev_ebitda_t,  "Avg. 5yr": self._km_avg("enterpriseValueMultiple", 5),  "Avg. 10yr": self._km_avg("enterpriseValueMultiple", 10)},
            {"Valuation": "EV / Adj. FCF",       "TTM": ev_adjfcf_t,  "Avg. 5yr": None,                                        "Avg. 10yr": None},
            {"Valuation": "P/E",                 "TTM": pe_ttm,       "Avg. 5yr": self._km_avg("peRatio", 5),                  "Avg. 10yr": self._km_avg("peRatio", 10)},
            {"Valuation": "P/S",                 "TTM": ps_ttm,       "Avg. 5yr": self._km_avg("priceToSalesRatio", 5),        "Avg. 10yr": self._km_avg("priceToSalesRatio", 10)},
            {"Valuation": "P/B",                 "TTM": pb_ttm,       "Avg. 5yr": self._km_avg("pbRatio", 5),                  "Avg. 10yr": self._km_avg("pbRatio", 10)},
            {"Valuation": "P/FCF",               "TTM": pfcf_ttm,     "Avg. 5yr": self._km_avg("pfcfRatio", 5),               "Avg. 10yr": self._km_avg("pfcfRatio", 10)},
            {"Valuation": "PEG",                 "TTM": peg_ttm,      "Avg. 5yr": None,                                        "Avg. 10yr": None},
            {"Valuation": "Earnings Yield",      "TTM": earn_yield,   "Avg. 5yr": None,                                        "Avg. 10yr": None},
            {"Valuation": "Adj. FCF Yield",      "TTM": adjfcf_yield, "Avg. 5yr": None,                                        "Avg. 10yr": None},
            {"Valuation": "Piotroski F-Score",   "TTM": piotroski,    "Avg. 5yr": None,                                        "Avg. 10yr": None},
        ]

    def _piotroski(self):
        """9-point Piotroski F-Score using the most recent two annual periods."""
        if len(self.is_l) < 2 or len(self.bs_l) < 2 or len(self.cf_l) < 2:
            return None
        score = 0
        # Profitability
        ni    = self._ann(self.is_l, "netIncome", 0)
        cfo   = self._ann(self.cf_l, "operatingCashFlow", 0)
        roa0  = self._div(ni, self._ann(self.bs_l, "totalAssets", 0))
        roa1  = self._div(self._ann(self.is_l, "netIncome", 1), self._ann(self.bs_l, "totalAssets", 1))
        if roa0 is not None and roa0 > 0:                      score += 1
        if cfo  is not None and cfo  > 0:                      score += 1
        if roa0 is not None and roa1 is not None and roa0 > roa1: score += 1
        if ni is not None and cfo is not None and cfo > ni:    score += 1
        # Leverage / Liquidity
        ltd0  = self._ann(self.bs_l, "longTermDebt", 0)
        ltd1  = self._ann(self.bs_l, "longTermDebt", 1)
        ca0   = self._ann(self.bs_l, "totalCurrentAssets", 0)
        cl0   = self._ann(self.bs_l, "totalCurrentLiabilities", 0)
        ca1   = self._ann(self.bs_l, "totalCurrentAssets", 1)
        cl1   = self._ann(self.bs_l, "totalCurrentLiabilities", 1)
        cr0   = self._div(ca0, cl0)
        cr1   = self._div(ca1, cl1)
        sh0   = self._ann(self.is_l, "weightedAverageShsOut", 0)
        sh1   = self._ann(self.is_l, "weightedAverageShsOut", 1)
        if ltd0 is not None and ltd1 is not None and ltd0 < ltd1: score += 1
        if cr0  is not None and cr1  is not None and cr0  > cr1:  score += 1
        if sh0  is not None and sh1  is not None and sh0  <= sh1: score += 1
        # Efficiency
        gm0   = self._div(self._ann(self.is_l, "grossProfit", 0), self._ann(self.is_l, "revenue", 0))
        gm1   = self._div(self._ann(self.is_l, "grossProfit", 1), self._ann(self.is_l, "revenue", 1))
        at0   = self._div(self._ann(self.is_l, "revenue", 0), self._ann(self.bs_l, "totalAssets", 0))
        at1   = self._div(self._ann(self.is_l, "revenue", 1), self._ann(self.bs_l, "totalAssets", 1))
        if gm0 is not None and gm1 is not None and gm0 > gm1: score += 1
        if at0 is not None and at1 is not None and at0 > at1: score += 1
        return score

    # ══════════════════════════════════════════════════════════════════════════
    # 3. Profitability
    # ══════════════════════════════════════════════════════════════════════════

    def get_insights_profitability(self):
        rev_ttm  = self._ttm_flow(self.q_is, "revenue")
        gp_ttm   = self._ttm_flow(self.q_is, "grossProfit")
        ebit_ttm = self._ttm_flow(self.q_is, "operatingIncome")
        ebitda_t = self._ttm_flow(self.q_is, "ebitda")
        ni_ttm   = self._ttm_flow(self.q_is, "netIncome")
        fcf_ttm  = self._ttm_flow(self.q_cf, "freeCashFlow")
        adj_fcf  = self._ttm_adj_fcf()

        def margin(num, den):
            return self._div(num, den)

        gm_ttm   = margin(gp_ttm,   rev_ttm)
        em_ttm   = margin(ebit_ttm, rev_ttm)
        ebm_ttm  = margin(ebitda_t, rev_ttm)
        nm_ttm   = margin(ni_ttm,   rev_ttm)
        fcfm_ttm = margin(fcf_ttm,  rev_ttm)
        afm_ttm  = margin(adj_fcf,  rev_ttm)

        def ann_margin(is_key, n):
            vals = []
            for i in range(n):
                rev = self._ann(self.is_l, "revenue", i)
                num = self._ann(self.is_l, is_key,    i)
                m   = self._div(num, rev)
                if m is not None:
                    vals.append(m)
            return self._avg(vals)

        def cf_margin(cf_key, n):
            vals = []
            for i in range(n):
                rev = self._ann(self.is_l, "revenue", i)
                num = self._ann(self.cf_l, cf_key,    i)
                m   = self._div(num, rev)
                if m is not None:
                    vals.append(m)
            return self._avg(vals)

        def adj_fcf_margin(n):
            vals = []
            for i in range(n):
                rev = self._ann(self.is_l, "revenue", i)
                af  = self._adj_fcf(self.cf_l, self.is_l, i)
                m   = self._div(af, rev)
                if m is not None:
                    vals.append(m)
            return self._avg(vals)

        return [
            {"Profitability": "Gross profit",  "TTM": gm_ttm,   "Avg. 5yr": ann_margin("grossProfit",    5), "Avg. 10yr": ann_margin("grossProfit",    10)},
            {"Profitability": "EBIT",           "TTM": em_ttm,   "Avg. 5yr": ann_margin("operatingIncome",5), "Avg. 10yr": ann_margin("operatingIncome",10)},
            {"Profitability": "EBITDA",         "TTM": ebm_ttm,  "Avg. 5yr": ann_margin("ebitda",         5), "Avg. 10yr": ann_margin("ebitda",         10)},
            {"Profitability": "Net Income",     "TTM": nm_ttm,   "Avg. 5yr": ann_margin("netIncome",      5), "Avg. 10yr": ann_margin("netIncome",      10)},
            {"Profitability": "FCF",            "TTM": fcfm_ttm, "Avg. 5yr": cf_margin("freeCashFlow",    5), "Avg. 10yr": cf_margin("freeCashFlow",    10)},
            {"Profitability": "Adj. FCF",       "TTM": afm_ttm,  "Avg. 5yr": adj_fcf_margin(5),              "Avg. 10yr": adj_fcf_margin(10)},
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # 4. Returns Analysis
    # ══════════════════════════════════════════════════════════════════════════

    def get_insights_returns(self):
        ni_ttm   = self._ttm_flow(self.q_is, "netIncome")
        cfo_ttm  = self._ttm_flow(self.q_cf, "operatingCashFlow")
        capx_ttm = self._ttm_flow(self.q_cf, "capitalExpenditure")
        ebit_ttm = self._ttm_flow(self.q_is, "operatingIncome")
        tax_ttm  = self._ttm_flow(self.q_is, "incomeTaxExpense")
        ebt_ttm  = self._ttm_flow(self.q_is, "incomeBeforeTax")

        eq0  = self._ttm_bs("totalStockholdersEquity")
        eq1  = self._ann(self.bs_l, "totalStockholdersEquity", 0)
        eq2  = self._ann(self.bs_l, "totalStockholdersEquity", 1)
        ta0  = self._ttm_bs("totalAssets")
        ta1  = self._ann(self.bs_l, "totalAssets", 0)
        ta2  = self._ann(self.bs_l, "totalAssets", 1)
        cl0  = self._ttm_bs("totalCurrentLiabilities")
        debt0 = self._ttm_bs("totalDebt")

        avg_eq  = self._avg([eq0, eq1]) if eq0 or eq1 else None
        avg_ta  = self._avg([ta0, ta1]) if ta0 or ta1 else None

        # NOPAT = EBIT × (1 - tax_rate)
        tax_rate = None
        if ebt_ttm and ebt_ttm != 0 and tax_ttm is not None:
            tax_rate = max(0, min(tax_ttm / ebt_ttm, 0.5))
        nopat = ebit_ttm * (1 - (tax_rate or 0.21)) if ebit_ttm is not None else None

        # Invested Capital = total equity + total debt
        ic = None
        if eq0 is not None or debt0 is not None:
            ic = (eq0 or 0) + (debt0 or 0)

        roic = self._div(nopat, ic)
        fcf_roc = self._div(
            cfo_ttm - abs(capx_ttm or 0) if cfo_ttm is not None else None,
            ic
        )
        roe  = self._div(ni_ttm, avg_eq)
        roa  = self._div(ni_ttm, avg_ta)
        # ROCE = EBIT / (Total Assets - Current Liabilities)
        cap_employed = (ta0 - (cl0 or 0)) if ta0 is not None else None
        roce = self._div(ebit_ttm, cap_employed)

        def _avg_returns(key, n):
            return self._ratio_avg(key, n)

        return [
            {"Returns": "ROIC",     "TTM": roic,    "Avg. 5yr": _avg_returns("returnOnInvestedCapitalTTM", 5),  "Avg. 10yr": _avg_returns("returnOnInvestedCapitalTTM", 10)},
            {"Returns": "FCF ROC",  "TTM": fcf_roc, "Avg. 5yr": None,                                           "Avg. 10yr": None},
            {"Returns": "ROE",      "TTM": roe,     "Avg. 5yr": _avg_returns("returnOnEquityTTM", 5),            "Avg. 10yr": _avg_returns("returnOnEquityTTM", 10)},
            {"Returns": "ROA",      "TTM": roa,     "Avg. 5yr": _avg_returns("returnOnAssetsTTM", 5),            "Avg. 10yr": _avg_returns("returnOnAssetsTTM", 10)},
            {"Returns": "ROCE",     "TTM": roce,    "Avg. 5yr": None,                                           "Avg. 10yr": None},
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # 5. Liquidity
    # ══════════════════════════════════════════════════════════════════════════

    def get_insights_liquidity(self):
        ca   = self._ttm_bs("totalCurrentAssets")
        cl   = self._ttm_bs("totalCurrentLiabilities")
        cash = self._ttm_bs("cashAndCashEquivalents")
        debt = self._ttm_bs("totalDebt")
        ebitda_ttm = self._ttm_flow(self.q_is, "ebitda")
        int_exp    = self._ttm_flow(self.q_is, "interestExpense")
        net_debt   = (debt - cash) if (debt is not None and cash is not None) else None

        cr   = self._div(ca, cl)
        de   = self._div(debt, self._ttm_bs("totalStockholdersEquity"))
        d_eb = self._div(debt, ebitda_ttm)
        nd_eb = self._div(net_debt, ebitda_ttm)
        int_cov = self._div(ebitda_ttm, abs(int_exp) if int_exp else None)
        c2d  = self._div(cash, debt)

        def ann_ratio(fn, n):
            vals = []
            for i in range(n):
                vals.append(fn(i))
            return self._avg([v for v in vals if v is not None])

        def cr_ann(i):
            return self._div(
                self._ann(self.bs_l, "totalCurrentAssets", i),
                self._ann(self.bs_l, "totalCurrentLiabilities", i)
            )
        def de_ann(i):
            return self._div(
                self._ann(self.bs_l, "totalDebt", i),
                self._ann(self.bs_l, "totalStockholdersEquity", i)
            )
        def c2d_ann(i):
            return self._div(
                self._ann(self.bs_l, "cashAndCashEquivalents", i),
                self._ann(self.bs_l, "totalDebt", i)
            )
        def d_eb_ann(i):
            return self._div(
                self._ann(self.bs_l, "totalDebt", i),
                self._ann(self.is_l, "ebitda", i)
            )

        return [
            {"Liquidity": "Current Ratio",      "TTM": cr,       "Avg. 5yr": ann_ratio(cr_ann, 5),  "Avg. 10yr": ann_ratio(cr_ann, 10)},
            {"Liquidity": "D/E",                 "TTM": de,       "Avg. 5yr": ann_ratio(de_ann, 5),  "Avg. 10yr": ann_ratio(de_ann, 10)},
            {"Liquidity": "D/EBITDA",            "TTM": d_eb,     "Avg. 5yr": ann_ratio(d_eb_ann, 5),"Avg. 10yr": ann_ratio(d_eb_ann, 10)},
            {"Liquidity": "Net D/EBITDA",        "TTM": nd_eb,    "Avg. 5yr": None,                  "Avg. 10yr": None},
            {"Liquidity": "Interest Coverage",   "TTM": int_cov,  "Avg. 5yr": self._ratio_avg("interestCoverageTTM", 5), "Avg. 10yr": self._ratio_avg("interestCoverageTTM", 10)},
            {"Liquidity": "Cash to Debt",        "TTM": c2d,      "Avg. 5yr": ann_ratio(c2d_ann, 5), "Avg. 10yr": ann_ratio(c2d_ann, 10)},
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # 6. Dividends
    # ══════════════════════════════════════════════════════════════════════════

    def get_insights_dividends(self):
        mkt    = self._safe(self.ov.get("mktCap"))
        price  = self._safe(self.ov.get("price"))
        ni_ttm = self._ttm_flow(self.q_is, "netIncome")
        fcf_ttm = self._ttm_flow(self.q_cf, "freeCashFlow")
        div_ttm = self._ttm_flow(self.q_cf, "commonDividendsPaid")
        rp_ttm  = self._ttm_flow(self.q_cf, "commonStockRepurchased")
        shares  = (self._ttm_flow(self.q_is, "weightedAverageShsOutDil")
                   or self._ttm_flow(self.q_is, "weightedAverageShsOut"))

        # Dividends paid is usually negative in CF statement — normalise
        div_abs = abs(div_ttm) if div_ttm is not None else None
        rp_abs  = abs(rp_ttm)  if rp_ttm  is not None else None

        div_yield     = self._div(div_abs, mkt)
        payout_ratio  = self._div(div_abs, ni_ttm)
        buyback_yield = self._div(rp_abs, mkt)
        total_sh_yield = (
            (div_abs or 0) + (rp_abs or 0)
        ) / mkt if mkt else None
        dr_fcf = self._div((div_abs or 0) + (rp_abs or 0), fcf_ttm)

        dps_ttm = self._div(div_abs, shares) if shares else None

        def div_yield_ann(i):
            d  = self._ann(self.cf_l, "commonDividendsPaid", i)
            mc = (self._safe(self.km_l[i].get("marketCap"))
                  if i < len(self.km_l) and isinstance(self.km_l[i], dict) else None)
            return self._div(abs(d) if d else None, mc)

        def payout_ann(i):
            d = self._ann(self.cf_l, "commonDividendsPaid", i)
            n = self._ann(self.is_l, "netIncome", i)
            return self._div(abs(d) if d else None, n)

        return [
            {"Dividends": "Dividend Yield",         "TTM": div_yield,      "Avg. 5yr": self._km_avg("dividendYield", 5), "Avg. 10yr": self._km_avg("dividendYield", 10)},
            {"Dividends": "Payout Ratio",           "TTM": payout_ratio,   "Avg. 5yr": self._avg([payout_ann(i)   for i in range(5)]), "Avg. 10yr": self._avg([payout_ann(i)   for i in range(10)])},
            {"Dividends": "Buyback Yield",          "TTM": buyback_yield,  "Avg. 5yr": None,                                            "Avg. 10yr": None},
            {"Dividends": "Total Shareholder Yield","TTM": total_sh_yield, "Avg. 5yr": None,                                            "Avg. 10yr": None},
            {"Dividends": "Div.&Repurch./FCF",      "TTM": dr_fcf,         "Avg. 5yr": None,                                            "Avg. 10yr": None},
            {"Dividends": "DPS",                    "TTM": dps_ttm,        "Avg. 5yr": None,                                            "Avg. 10yr": None},
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # 7. Efficiency
    # ══════════════════════════════════════════════════════════════════════════

    def get_insights_efficiency(self):
        rev_ttm  = self._ttm_flow(self.q_is, "revenue")
        cogs_ttm = self._ttm_flow(self.q_is, "costOfRevenue")
        sbc_ttm  = self._ttm_flow(self.q_is, "stockBasedCompensation")
        fcf_ttm  = self._ttm_flow(self.q_cf, "freeCashFlow")

        # Balance sheet averages (TTM + prior year annual)
        def _bs_avg(key):
            v0 = self._ttm_bs(key)
            v1 = self._ann(self.bs_l, key, 0)
            return self._avg([v for v in [v0, v1] if v is not None])

        ar_avg   = _bs_avg("netReceivables")
        inv_avg  = _bs_avg("inventory")
        ap_avg   = _bs_avg("accountPayables")
        ta_avg   = _bs_avg("totalAssets")
        ppe_avg  = _bs_avg("propertyPlantEquipmentNet")
        ca_avg   = _bs_avg("totalCurrentAssets")
        cl_avg   = _bs_avg("totalCurrentLiabilities")
        nwc_avg  = ((ca_avg or 0) - (cl_avg or 0)) if ca_avg is not None else None

        employees = self._safe(self.ov.get("fullTimeEmployees"))

        rt  = self._div(rev_ttm, ar_avg)
        it  = self._div(cogs_ttm or rev_ttm, inv_avg)
        pt  = self._div(cogs_ttm or rev_ttm, ap_avg)
        dso = (365 / rt)  if rt  and rt  != 0 else None
        dio = (365 / it)  if it  and it  != 0 else None
        dpo = (365 / pt)  if pt  and pt  != 0 else None

        op_cycle   = (dso or 0) + (dio or 0) if (dso is not None or dio is not None) else None
        cash_cycle = (op_cycle or 0) - (dpo or 0) if (op_cycle is not None and dpo is not None) else None

        wc_t   = self._div(rev_ttm, nwc_avg)
        fat    = self._div(rev_ttm, ppe_avg)
        at     = self._div(rev_ttm, ta_avg)
        sbc_fcf = self._div(sbc_ttm, fcf_ttm)
        rev_emp = self._div(rev_ttm, employees) if employees else None

        return [
            {"Efficiency": "Receivable turnover",                     "TTM": rt,         "Avg. 5yr": self._ratio_avg("receivablesTurnoverTTM", 5),  "Avg. 10yr": self._ratio_avg("receivablesTurnoverTTM", 10)},
            {"Efficiency": "Avg. receivables collection day (DSO)",   "TTM": dso,        "Avg. 5yr": self._ratio_avg("daysSalesOutstandingTTM", 5),  "Avg. 10yr": self._ratio_avg("daysSalesOutstandingTTM", 10)},
            {"Efficiency": "Inventory turnover",                      "TTM": it,         "Avg. 5yr": self._ratio_avg("inventoryTurnoverTTM", 5),      "Avg. 10yr": self._ratio_avg("inventoryTurnoverTTM", 10)},
            {"Efficiency": "Avg. days inventory in stock (DIO)",      "TTM": dio,        "Avg. 5yr": self._ratio_avg("daysOfInventoryOnHandTTM", 5),  "Avg. 10yr": self._ratio_avg("daysOfInventoryOnHandTTM", 10)},
            {"Efficiency": "Payables turnover",                       "TTM": pt,         "Avg. 5yr": self._ratio_avg("payablesTurnoverTTM", 5),       "Avg. 10yr": self._ratio_avg("payablesTurnoverTTM", 10)},
            {"Efficiency": "Avg. days payables outstanding (DPO)",    "TTM": dpo,        "Avg. 5yr": self._ratio_avg("daysPayableOutstandingTTM", 5), "Avg. 10yr": self._ratio_avg("daysPayableOutstandingTTM", 10)},
            {"Efficiency": "Operating cycle",                         "TTM": op_cycle,   "Avg. 5yr": None,                                            "Avg. 10yr": None},
            {"Efficiency": "Cash cycle (CCC)",                        "TTM": cash_cycle, "Avg. 5yr": None,                                            "Avg. 10yr": None},
            {"Efficiency": "Working capital turnover",                "TTM": wc_t,       "Avg. 5yr": None,                                            "Avg. 10yr": None},
            {"Efficiency": "Fixed asset turnover",                    "TTM": fat,        "Avg. 5yr": self._ratio_avg("fixedAssetTurnoverTTM", 5),     "Avg. 10yr": self._ratio_avg("fixedAssetTurnoverTTM", 10)},
            {"Efficiency": "Asset turnover",                          "TTM": at,         "Avg. 5yr": self._ratio_avg("assetTurnoverTTM", 5),          "Avg. 10yr": self._ratio_avg("assetTurnoverTTM", 10)},
            {"Efficiency": "SBC / FCF",                               "TTM": sbc_fcf,    "Avg. 5yr": None,                                            "Avg. 10yr": None},
            {"Efficiency": "Revenue / Employee",                      "TTM": rev_emp,    "Avg. 5yr": None,                                            "Avg. 10yr": None},
        ]
