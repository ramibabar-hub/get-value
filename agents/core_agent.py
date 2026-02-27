import pandas as pd

class DataNormalizer:
    def __init__(self, raw_data, ticker):
        self.raw_data = raw_data
        self.ticker = ticker
        self.is_l = raw_data.get('annual_income_statement', [])
        self.bs_l = raw_data.get('annual_balance_sheet', [])
        self.cf_l = raw_data.get('annual_cash_flow', [])
        self.ratios = raw_data.get('annual_ratios', [])

    def _get_ttm_value(self, q_list, key):
        return sum(q.get(key, 0) or 0 for q in q_list[:4]) if q_list else 0

    def get_column_headers(self, p_type='annual'):
        source = self.is_l if p_type == 'annual' else self.raw_data.get('quarterly_income_statement', [])
        if not source: return ["Item", "TTM"]
        dates = [str(d.get('calendarYear', '')) if p_type=='annual' else f"{d.get('calendarYear')} {d.get('period')}" for d in source[:10]]
        return ["Item"] + dates + ["TTM"]

    def build_table(self, mapping, p_type='annual'):
        headers = self.get_column_headers(p_type)
        rows = []
        is_l = self.is_l if p_type == 'annual' else self.raw_data.get('quarterly_income_statement', [])
        bs_l = self.bs_l if p_type == 'annual' else self.raw_data.get('quarterly_balance_sheet', [])
        cf_l = self.cf_l if p_type == 'annual' else self.raw_data.get('quarterly_cash_flow', [])

        for label, key in mapping:
            row = {"label": label}
            found = is_l if is_l and key in is_l[0] else bs_l if bs_l and key in bs_l[0] else cf_l if cf_l and key in cf_l[0] else None
            if found:
                for i, d in enumerate(found[:10]):
                    if i+1 < len(headers): row[headers[i+1]] = d.get(key, 0)
                row["TTM"] = d.get(key, 0) if found == bs_l else self._get_ttm_value(found, key)
            rows.append(row)
        return rows

    def get_income_statement(self, p):
        return self.build_table([("Revenues","revenue"),("Gross Profit","grossProfit"),("Operating Income","operatingIncome"),("EBITDA","ebitda"),("Net Income","netIncome"),("EPS","eps")], p)

    def get_balance_sheet(self, p):
        return self.build_table([("Cash & Equiv.","cashAndCashEquivalents"),("Total Assets","totalAssets"),("Total Debt","totalDebt"),("Total Equity","totalStockholdersEquity")], p)

    def get_cash_flow(self, p):
        return self.build_table([("Operating Cash Flow","operatingCashFlow"),("CapEx","capitalExpenditure"),("Free Cash Flow","freeCashFlow")], p)

    # מבנה ה-Insight הקשיח
    def get_insights_cagr(self):
        return [{"CAGR": n, "3yr": None, "5yr": None, "10yr": None} for n in ["Revenues", "Operating income", "EBITDA", "EPS", "Adj. FCF", "Shares outs."]]
    
    def get_template_data(self, rows, label):
        return [{label: r, "TTM": None, "Avg. 5yr": None, "Avg. 10yr": None} for r in rows]

    def get_insights_valuation(self): return self.get_template_data(["EV / EBITDA", "EV / Adj. FCF", "P/E", "P/S", "P/B", "P/FCF", "PEG", "Earnings Yield"], "Valuation")
    def get_insights_profitability(self): return self.get_template_data(["Gross profit", "EBIT", "EBITDA", "Net Income", "FCF"], "Profitability")
    def get_insights_returns(self): return self.get_template_data(["ROIC", "FCF ROC", "ROE", "ROA", "ROCE", "ROIC/WACC"], "Returns")
    def get_insights_liquidity(self): return self.get_template_data(["Current Ratio", "Cash to Debt", "Net Working Capital (NWC)"], "Liquidity")
    def get_insights_dividends(self): return self.get_template_data(["Yield", "Payout", "DPS"], "Dividends")
    def get_insights_efficiency(self): return self.get_template_data(["Receivable turnover", "Average receivables collection day", "Inventory turnover", "Average days inventory in stock", "Payables turnover", "Average days payables outstanding", "Operating cycle", "Cash cycle", "Working capital turnover", "Fixed asset turnover", "Asset turnover", "SBC/ FCF", "Revenue/ Employee"], "Efficiency")
