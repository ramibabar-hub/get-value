import pandas as pd
import numpy as np

class DataNormalizer:
    def __init__(self, raw_data, ticker):
        self.raw_data = raw_data
        self.ticker = ticker
        self.annual_is = raw_data.get('annual_income_statement', [])
        self.quarterly_is = raw_data.get('quarterly_income_statement', [])
        self.annual_bs = raw_data.get('annual_balance_sheet', [])
        self.quarterly_bs = raw_data.get('quarterly_balance_sheet', [])
        self.annual_cf = raw_data.get('annual_cash_flow', [])
        self.quarterly_cf = raw_data.get('quarterly_cash_flow', [])

    def _get_ttm_value(self, quarterly_list, key):
        if not quarterly_list: return 0
        return sum(q.get(key, 0) or 0 for q in quarterly_list[:4])

    def _get_latest_value(self, quarterly_list, key):
        if not quarterly_list: return 0
        return quarterly_list[0].get(key, 0) or 0

    def get_column_headers(self, period_type='annual'):
        # לוקחים את הרשימה הרלוונטית כדי לחלץ כותרות
        is_list = self.annual_is if period_type == 'annual' else self.quarterly_is
        
        # אם אין נתונים ב-IS, ננסה ב-BS
        if not is_list:
            is_list = self.annual_bs if period_type == 'annual' else self.quarterly_bs

        if period_type == 'annual':
            dates = [str(d.get('calendarYear', '')) for d in is_list[:5]]
        else:
            dates = [f"{d.get('calendarYear', '')} {d.get('period', '')}" for d in is_list[:5]]
        
        # הבטחה שתמיד יהיו כותרות כדי למנוע טבלה ריקה
        if not dates:
            dates = ["N/A 1", "N/A 2", "N/A 3", "N/A 4", "N/A 5"]
            
        return ["Item"] + dates + ["TTM"]

    def build_table(self, mapping, period_type='annual'):
        headers = self.get_column_headers(period_type)
        rows = []
        
        is_list = self.annual_is if period_type == 'annual' else self.quarterly_is
        bs_list = self.annual_bs if period_type == 'annual' else self.quarterly_bs
        cf_list = self.annual_cf if period_type == 'annual' else self.quarterly_cf

        for label, key, calc_fn in mapping:
            row = {"label": label}
            # אתחול עמודות ב-0
            for h in headers[1:]:
                row[h] = 0

            if calc_fn:
                calc_vals = calc_fn(period_type)
                # calc_vals should be [v1, v2, v3, v4, v5, ttm]
                for i, h in enumerate(headers[1:]):
                    if i < len(calc_vals):
                        row[h] = calc_vals[i]
            else:
                found_list = None
                ttm_val = 0
                
                # חיפוש היכן המפתח (Key) נמצא
                if is_list and len(is_list) > 0 and key in is_list[0]:
                    found_list = is_list
                    ttm_val = self._get_ttm_value(self.quarterly_is, key)
                elif bs_list and len(bs_list) > 0 and key in bs_list[0]:
                    found_list = bs_list
                    ttm_val = self._get_latest_value(self.quarterly_bs, key)
                elif cf_list and len(cf_list) > 0 and key in cf_list[0]:
                    found_list = cf_list
                    ttm_val = self._get_ttm_value(self.quarterly_cf, key)
                
                if found_list:
                    for i, d in enumerate(found_list[:5]):
                        if i + 1 < len(headers):
                            col_name = headers[i+1]
                            row[col_name] = d.get(key, 0) or 0
                
                row["TTM"] = ttm_val
            
            rows.append(row)
        return rows

    def get_income_statement(self, period_type='annual'):
        mapping = [
            ("Revenues", "revenue", None),
            ("Gross profit", "grossProfit", None),
            ("Operating income", "operatingIncome", None),
            ("EBITDA", "ebitda", None),
            ("Interest Expense", "interestExpense", None),
            ("Income Tax", "incomeTaxExpense", None),
            ("Net Income", "netIncome", None),
            ("EPS", "eps", None),
        ]
        return self.build_table(mapping, period_type)

    def get_cash_flow(self, period_type='annual'):
        def calc_fcf(p):
            cf = self.annual_cf if p=='annual' else self.quarterly_cf
            fcf = [(d.get('operatingCashFlow', 0) or 0) + (d.get('capitalExpenditure', 0) or 0) for d in cf[:5]]
            ttm = self._get_ttm_value(self.quarterly_cf, 'operatingCashFlow') + self._get_ttm_value(self.quarterly_cf, 'capitalExpenditure')
            return fcf + [ttm]

        mapping = [
            ("Cash flow from operations", "operatingCashFlow", None),
            ("Capital expenditures", "capitalExpenditure", None),
            ("Free Cash flow", None, calc_fcf),
            ("Stock based compensation", "stockBasedCompensation", None),
            ("Depreciation & Amortization", "depreciationAndAmortization", None),
            ("Change in Working Capital", "changeInWorkingCapital", None),
            ("Dividend paid", "dividendsPaid", None),
            ("Repurchase of Common Stock", "commonStockRepurchased", None),
        ]
        return self.build_table(mapping, period_type)

    def get_balance_sheet(self, period_type='annual'):
        mapping = [
            ("Cash and Cash Equivalents", "cashAndCashEquivalents", None),
            ("Current Assets", "totalCurrentAssets", None),
            ("Total Assets", "totalAssets", None),
            ("Total Current Liabilities", "totalCurrentLiabilities", None),
            ("Debt", "totalDebt", None),
            ("Equity value", "totalStockholdersEquity", None),
            ("Shares Outstanding", "weightedAverageShsOut", None),
        ]
        return self.build_table(mapping, period_type)

    def get_debt_table(self, period_type='annual'):
        mapping = [
            ("Long-Term Debt", "longTermDebt", None),
            ("Total Debt", "totalDebt", None),
            ("Net Debt", "netDebt", None),
        ]
        return self.build_table(mapping, period_type)
