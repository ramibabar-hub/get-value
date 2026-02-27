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
        if period_type == 'annual':
            data = self.annual_is[:5]
            headers = ["Item"] + [str(d.get('calendarYear', '')) for d in data] + ["TTM"]
        else:
            data = self.quarterly_is[:5]
            headers = ["Item"] + [f"{d.get('calendarYear')} {d.get('period')}" for d in data] + ["TTM"]
        return headers

    def build_table(self, mapping, period_type='annual'):
        headers = self.get_column_headers(period_type)
        rows = []
        is_list = self.annual_is if period_type == 'annual' else self.quarterly_is
        bs_list = self.annual_bs if period_type == 'annual' else self.quarterly_bs
        cf_list = self.annual_cf if period_type == 'annual' else self.quarterly_cf

        for label, key, calc_fn in mapping:
            row = {"label": label}
            if calc_fn:
                calc_vals = calc_fn(period_type)
                for i, h in enumerate(headers[1:]):
                    row[h] = calc_vals[i] if i < len(calc_vals) else 0
            else:
                vals, ttm_val, found_list = [], 0, None
                if is_list and key in is_list[0]:
                    found_list, ttm_val = is_list, self._get_ttm_value(self.quarterly_is, key)
                elif bs_list and key in bs_list[0]:
                    found_list, ttm_val = bs_list, self._get_latest_value(self.quarterly_bs, key)
                elif cf_list and key in cf_list[0]:
                    found_list, ttm_val = cf_list, self._get_ttm_value(self.quarterly_cf, key)
                
                vals = [d.get(key, 0) or 0 for d in found_list[:5]] if found_list else [0]*5
                for i, v in enumerate(vals): row[headers[i+1]] = v
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
            ops = [d.get('operatingCashFlow', 0) or 0 for d in cf[:5]]
            capex = [d.get('capitalExpenditure', 0) or 0 for d in cf[:5]]
            fcf = [o + c for o, c in zip(ops, capex)]
            ttm_fcf = self._get_ttm_value(self.quarterly_cf, 'operatingCashFlow') + self._get_ttm_value(self.quarterly_cf, 'capitalExpenditure')
            return fcf + [ttm_fcf]

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