import pandas as pd

class DataNormalizer:
    def __init__(self, raw_data, ticker):
        self.raw_data = raw_data
        self.ticker = ticker
        self.is_l = raw_data.get('annual_income_statement', [])
        self.bs_l = raw_data.get('annual_balance_sheet', [])
        self.cf_l = raw_data.get('annual_cash_flow', [])

    def _calc_cagr(self, data_list, key, years):
        try:
            v_now = data_list[0].get(key, 0)
            v_past = data_list[years].get(key, 0)
            if v_now > 0 and v_past > 0:
                return (v_now / v_past)**(1/years) - 1
        except: pass
        return None

    def get_insights_cagr(self):
        keys = [("Revenues","revenue"), ("Operating income","operatingIncome"), ("EBITDA","ebitda"), 
                ("EPS","eps"), ("Adj. FCF","freeCashFlow"), ("Shares outs.","weightedAverageShsOut")]
        return [{"CAGR": n, "3yr": self._calc_cagr(self.is_l, k, 3), "5yr": self._calc_cagr(self.is_l, k, 5), "10yr": self._calc_cagr(self.is_l, k, 10)} for n, k in keys]

    def get_template_data(self, rows, label):
        return [{label: r, "TTM": None, "Avg. 5yr": None, "Avg. 10yr": None} for r in rows]

    def get_insights_valuation(self):
        return self.get_template_data(["EV / EBITDA", "EV / Adj. FCF", "P/E", "P/S", "P/B", "P/FCF", "PEG", "Earnings Yield"], "Valuation")

    def get_insights_profitability(self):
        return self.get_template_data(["Gross profit", "EBIT", "EBITDA", "Net Income", "FCF"], "Profitability")

    def get_insights_returns(self):
        return self.get_template_data(["ROIC", "FCF ROC", "ROE", "ROA", "ROCE", "ROIC/WACC"], "Returns")

    def get_insights_liquidity(self):
        return self.get_template_data(["Current Ratio", "Cash to Debt", "Net Working Capital (NWC)"], "Liquidity")

    def get_insights_dividends(self):
        return self.get_template_data(["Yield", "Payout", "DPS"], "Dividends")

    def get_insights_efficiency(self):
        rows = ["Receivable turnover", "Average receivables collection day", "Inventory turnover", 
                "Average days inventory in stock", "Payables turnover", "Average days payables outstanding",
                "Operating cycle", "Cash cycle", "Working capital turnover", "Fixed asset turnover", 
                "Asset turnover", "SBC/ FCF", "Revenue/ Employee"]
        return self.get_template_data(rows, "Efficiency")
    
    def get_column_headers(self, p):
        is_list = self.is_l if p == 'annual' else self.raw_data.get('quarterly_income_statement', [])
        dates = [str(d.get('calendarYear', '')) if p=='annual' else f"{d.get('calendarYear')} {d.get('period')}" for d in is_list[:10]]
        return ["Item"] + dates + ["TTM"]
