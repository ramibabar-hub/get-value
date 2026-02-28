import pandas as pd

class DataNormalizer:
    def __init__(self, raw_data, ticker):
        self.raw_data = raw_data
        self.ticker = ticker
        self.is_l = raw_data.get('annual_income_statement', [])
        self.bs_l = raw_data.get('annual_balance_sheet', [])
        self.cf_l = raw_data.get('annual_cash_flow', [])
        self.q_is = raw_data.get('quarterly_income_statement', [])
        self.q_bs = raw_data.get('quarterly_balance_sheet', [])
        self.q_cf = raw_data.get('quarterly_cash_flow', [])

    def _get_ttm_value(self, q_list, key):
        if not q_list: return 0
        return sum(q.get(key, 0) or 0 for q in q_list[:4])

    def get_column_headers(self, p_type='annual'):
        source = self.is_l if p_type == 'annual' else self.q_is
        dates = []
        if source and isinstance(source, list):
            for d in source[:10]:
                if not isinstance(d, dict):
                    continue
                # Priority 1: fiscalYear (FMP /stable API)
                # Priority 2: calendarYear (FMP /api/v3 legacy)
                # Priority 3: extract year from 'date' field (e.g. '2025-06-30')
                year = (str(d.get('fiscalYear') or '')
                        or str(d.get('calendarYear') or '')
                        or str(d.get('date') or '')[:4])
                period = str(d.get('period') or '')
                if p_type == 'annual':
                    dates.append(year if year else f"Y{len(dates)+1}")
                else:
                    label = f"{year} {period}".strip()
                    dates.append(label if label else f"Q{len(dates)+1}")

        # Debug: if we still have no dates, print the first record's keys
        if not dates and source and isinstance(source, list) and source:
            first = source[0] if isinstance(source[0], dict) else {}
            print(f"[DataNormalizer] WARNING: could not extract period labels for '{p_type}'")
            print(f"[DataNormalizer] First record keys: {list(first.keys())}")
            print(f"[DataNormalizer] First record: {first}")

        # Guarantee exactly 10 historical columns (pad if fewer records exist)
        while len(dates) < 10:
            dates.append(f"N/A-{len(dates) + 1}")
        return ["Item", "TTM"] + dates

    def build_table(self, mapping, p_type='annual'):
        headers = self.get_column_headers(p_type)
        rows = []
        # בחירת מקור הנתונים לפי תקופה
        is_src = self.is_l if p_type == 'annual' else self.q_is
        bs_src = self.bs_l if p_type == 'annual' else self.q_bs
        cf_src = self.cf_l if p_type == 'annual' else self.q_cf
        
        for label, key in mapping:
            row = {"label": label}
            # חיפוש המפתח בדוחות השונים
            found = None
            if is_src and key in is_src[0]: found = is_src
            elif bs_src and key in bs_src[0]: found = bs_src
            elif cf_src and key in cf_src[0]: found = cf_src
            
            if found:
                # חישוב TTM (במאזן לוקחים דוח אחרון, ברווח והפסד/תזרים סוכמים 4 רבעונים)
                if found in [bs_src, self.bs_l, self.q_bs]:
                    row["TTM"] = self.q_bs[0].get(key, 0) if self.q_bs else found[0].get(key, 0)
                else:
                    q_source = self.q_is if found in [is_src, self.is_l] else self.q_cf
                    row["TTM"] = self._get_ttm_value(q_source, key)

                # מילוי עמודות היסטוריות — טיפול בזהירות בכל רשומה
                for i, d in enumerate(found[:10]):
                    if i + 2 < len(headers):
                        try:
                            row[headers[i+2]] = d.get(key, 0) if isinstance(d, dict) else 0
                        except Exception:
                            row[headers[i+2]] = 0
            rows.append(row)
        return rows

    def get_income_statement(self, p):
        return self.build_table([
            ("Revenues","revenue"), ("Gross profit","grossProfit"), ("Operating income","operatingIncome"),
            ("EBITDA","ebitda"), ("Interest Expense","interestExpense"), ("Income Tax","incomeTaxExpense"),
            ("Net Income","netIncome"), ("EPS","eps")
        ], p)

    def get_cash_flow(self, p):
        # חישוב Adj. FCF יבוצע בעתיד, כרגע מוצג כסעיף קבוע
        return self.build_table([
            ("Cash flow from operations","operatingCashFlow"), ("Capital expenditures","capitalExpenditure"),
            ("Free Cash flow","freeCashFlow"), ("Stock based compensation","stockBasedCompensation"),
            ("Adj. FCF","freeCashFlow"), ("Depreciation & Amortization","depreciationAndAmortization"),
            ("Change in Working Capital (inc) / dec","changeInWorkingCapital"), ("Dividend paid","commonDividendsPaid"),
            ("Repurchase of Common Stock","weightedAverageShsOut") # דורש מיפוי ייעודי
        ], p)

    def get_balance_sheet(self, p):
        return self.build_table([
            ("Cash and Cash Equivalents","cashAndCashEquivalents"), ("Current Assets","totalCurrentAssets"),
            ("Total Assets","totalAssets"), ("Total Current Liabilities","totalCurrentLiabilities"),
            ("Debt","totalDebt"), ("Equity value","totalStockholdersEquity"), ("Shares Outstandnig","weightedAverageShsOut"),
            ("Minority Interest","minorityInterest"), ("Preferred Stock","preferredStock"),
            ("Avg. Equity","totalStockholdersEquity"), ("Avg. Assets","totalAssets")
        ], p)

    def get_debt_table(self, p):
        return self.build_table([
            ("Current Portion of Long-Term Debt","shortTermDebt"), ("Current Portion of Capital Lease Obligations","capitalLeaseObligations"),
            ("Long-Term Debt","longTermDebt"), ("Capital Leases","capitalLeaseObligations"),
            ("Total Debt","totalDebt"), ("Cash and Cash Equivalents","cashAndCashEquivalents"), ("Net Debt","netDebt")
        ], p)

    # מיפוי Insight (נשאר קבוע כפי שביקשת)
    def get_insights_cagr(self): return [{"CAGR": n, "3yr": None, "5yr": None, "10yr": None} for n in ["Revenues", "Operating income", "EBITDA", "EPS", "Adj. FCF", "Shares outs."]]
    def get_template_data(self, rows, label): return [{label: r, "TTM": None, "Avg. 5yr": None, "Avg. 10yr": None} for r in rows]
    def get_insights_valuation(self): return self.get_template_data(["EV / EBITDA", "EV / Adj. FCF", "P/E", "P/S", "P/B", "P/FCF", "PEG", "Earnings Yield"], "Valuation")
    def get_insights_profitability(self): return self.get_template_data(["Gross profit", "EBIT", "EBITDA", "Net Income", "FCF"], "Profitability")
    def get_insights_returns(self): return self.get_template_data(["ROIC", "FCF ROC", "ROE", "ROA", "ROCE", "ROIC/WACC"], "Returns")
    def get_insights_liquidity(self): return self.get_template_data(["Current Ratio", "Cash to Debt", "Net Working Capital (NWC)"], "Liquidity")
    def get_insights_dividends(self): return self.get_template_data(["Yield", "Payout", "DPS"], "Dividends")
    def get_insights_efficiency(self): return self.get_template_data(["Receivable turnover", "Average receivables collection day", "Inventory turnover", "Average days inventory in stock", "Payables turnover", "Average days payables outstanding", "Operating cycle", "Cash cycle", "Working capital turnover", "Fixed asset turnover", "Asset turnover", "SBC/ FCF", "Revenue/ Employee"], "Efficiency")
