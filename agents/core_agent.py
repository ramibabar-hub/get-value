import pandas as pd

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

    def _get_ttm_value(self, q_list, key):
        if not q_list: return 0
        return sum(q.get(key, 0) or 0 for q in q_list[:4])

    def get_column_headers(self, p_type='annual'):
        is_list = self.annual_is if p_type == 'annual' else self.quarterly_is
        if not is_list: return ["Item", "TTM"]
        dates = [str(d.get('calendarYear', '')) if p_type=='annual' else f"{d.get('calendarYear')} {d.get('period')}" for d in is_list[:5]]
        return ["Item"] + dates + ["TTM"]

    def build_table(self, mapping, p_type='annual'):
        headers = self.get_column_headers(p_type)
        rows = []
        is_l = self.annual_is if p_type == 'annual' else self.quarterly_is
        bs_l = self.annual_bs if p_type == 'annual' else self.quarterly_bs
        cf_l = self.annual_cf if p_type == 'annual' else self.quarterly_cf

        for label, key, calc_fn in mapping:
            row = {"label": label}
            # Initialize with 0
            for h in headers[1:]: row[h] = 0
            
            if calc_fn:
                vals = calc_fn(p_type)
                for i, h in enumerate(headers[1:]):
                    row[h] = vals[i] if i < len(vals) else 0
            else:
                # Find which list contains the key
                found = None
                if is_l and key in is_l[0]: found = is_l
                elif bs_l and key in bs_l[0]: found = bs_l
                elif cf_l and key in cf_l[0]: found = cf_l
                
                if found:
                    for i, d in enumerate(found[:5]):
                        if i+1 < len(headers): row[headers[i+1]] = d.get(key, 0) or 0
                    
                    # TTM Calculation
                    if found == bs_l:
                        row["TTM"] = self.quarterly_bs[0].get(key, 0) if self.quarterly_bs else 0
                    elif found == is_l:
                        row["TTM"] = self._get_ttm_value(self.quarterly_is, key)
                    elif found == cf_l:
                        row["TTM"] = self._get_ttm_value(self.quarterly_cf, key)
            rows.append(row)
        return rows

    def get_income_statement(self, p):
        mapping = [("Revenues","revenue",None),("Gross profit","grossProfit",None),("Operating income","operatingIncome",None),("EBITDA","ebitda",None),("Net Income","netIncome",None),("EPS","eps",None)]
        return self.build_table(mapping, p)

    def get_cash_flow(self, p):
        def calc_fcf(pt):
            cf = self.annual_cf if pt=='annual' else self.quarterly_cf
            fcf = [(d.get('operatingCashFlow',0) or 0) + (d.get('capitalExpenditure',0) or 0) for d in cf[:5]]
            ttm = self._get_ttm_value(self.quarterly_cf,'operatingCashFlow') + self._get_ttm_value(self.quarterly_cf,'capitalExpenditure')
            return fcf + [ttm]
        mapping = [("Cash from Ops","operatingCashFlow",None),("Capital Expenditure","capitalExpenditure",None),("Free Cash Flow",None,calc_fcf)]
        return self.build_table(mapping, p)

    def get_balance_sheet(self, p):
        mapping = [("Total Assets","totalAssets",None),("Total Liabilities","totalLiabilities",None),("Total Equity","totalStockholdersEquity",None),("Cash and Equivalents","cashAndCashEquivalents",None)]
        return self.build_table(mapping, p)

    def get_debt_table(self, p):
        mapping = [("Total Debt","totalDebt",None),("Net Debt","netDebt",None)]
        return self.build_table(mapping, p)
