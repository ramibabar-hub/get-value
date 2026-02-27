import pandas as pd
import numpy as np

class DataNormalizer:
    def __init__(self, raw_data, ticker):
        self.raw_data = raw_data
        self.ticker = ticker
        self.is_l = raw_data.get('annual_income_statement', [])
        self.bs_l = raw_data.get('annual_balance_sheet', [])
        self.cf_l = raw_data.get('annual_cash_flow', [])
        self.ratios = raw_data.get('annual_ratios', [])
        self.metrics = raw_data.get('annual_key_metrics', [])
        self.ev = raw_data.get('annual_enterprise_values', [])

    def _safe_get(self, data_list, key, index=0):
        try:
            val = data_list[index].get(key)
            return val if val is not None else None
        except: return None

    def _calc_avg(self, data_list, key, years):
        vals = [d.get(key) for d in data_list[:years] if d.get(key) is not None]
        return sum(vals)/len(vals) if vals else None

    def _calc_cagr(self, data_list, key, years):
        try:
            v_now = data_list[0].get(key)
            v_past = data_list[years].get(key)
            if v_now > 0 and v_past > 0:
                return (v_now / v_past)**(1/years) - 1
        except: pass
        return None

    def get_insights_cagr(self):
        keys = [("Revenues","revenue"), ("Operating income","operatingIncome"), ("EBITDA","ebitda"), ("EPS","eps")]
        return [{"CAGR": n, "3yr": self._calc_cagr(self.is_l, k, 3), "5yr": self._calc_cagr(self.is_l, k, 5), "10yr": self._calc_cagr(self.is_l, k, 10)} for n, k in keys]

    def get_insights_valuation(self):
        # מבנה קבוע לפי הבקשה שלך
        rows = ["EV / EBITDA", "EV / Adj. FCF", "P/E", "P/S", "P/B", "P/FCF", "PEG", "Earnings Yield"]
        # כאן תיווסף הלוגיקה לשליפת הנתונים מה-Ratios/Metrics
        return [{"Valuation": r, "TTM": None, "Avg. 5yr": None, "Avg. 10yr": None} for r in rows]

    def get_insights_profitability(self):
        rows = ["Gross profit", "EBIT", "EBITDA", "Net Income", "FCF"]
        return [{"Profitability": r, "TTM": None, "Avg. 5yr": None, "Avg. 10yr": None} for r in rows]

    def get_insights_returns(self):
        rows = ["ROIC", "FCF ROC", "ROE", "ROA", "ROCE", "ROIC/WACC"]
        return [{"Returns": r, "TTM": None, "Avg. 5yr": None, "Avg. 10yr": None} for r in rows]
    
    def get_column_headers(self, p):
        is_list = self.is_l if p == 'annual' else self.raw_data.get('quarterly_income_statement', [])
        dates = [str(d.get('calendarYear', '')) if p=='annual' else f"{d.get('calendarYear')} {d.get('period')}" for d in is_list[:10]]
        return ["Item"] + dates + ["TTM"]
