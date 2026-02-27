import pandas as pd

class DataNormalizer:
    def __init__(self, raw_data, ticker):
        self.raw_data = raw_data
        self.annual_is = raw_data.get('annual_income_statement', [])
        self.annual_cf = raw_data.get('annual_cash_flow', [])
        self.annual_ratios = raw_data.get('annual_ratios', [])
        self.quarterly_is = raw_data.get('quarterly_income_statement', [])

    def get_column_headers(self, p_type='annual'):
        is_list = self.annual_is if p_type == 'annual' else self.quarterly_is
        dates = [str(d.get('calendarYear', '')) if p_type=='annual' else f"{d.get('calendarYear')} {d.get('period')}" for d in is_list[:10]]
        return ["Item"] + dates + ["TTM"]

    def _calculate_cagr(self, values, years):
        if len(values) <= years or values[years] <= 0 or values[0] <= 0: return None
        return (values[0] / values[years])**(1/years) - 1

    def _calculate_avg(self, values, years):
        sub = values[:years]
        return sum(sub) / len(sub) if sub else None

    def get_insights_cagr(self):
        revs = [x.get('revenue', 0) for x in self.annual_is]
        ebitda = [x.get('ebitda', 0) for x in self.annual_is]
        eps = [x.get('eps', 0) for x in self.annual_is]
        return [
            {"CAGR": "Revenues", "3yr": self._calculate_cagr(revs, 3), "5yr": self._calculate_cagr(revs, 5), "10yr": self._calculate_cagr(revs, 10)},
            {"CAGR": "EBITDA", "3yr": self._calculate_cagr(ebitda, 3), "5yr": self._calculate_cagr(ebitda, 5), "10yr": self._calculate_cagr(ebitda, 10)},
            {"CAGR": "EPS", "3yr": self._calculate_cagr(eps, 3), "5yr": self._calculate_cagr(eps, 5), "10yr": self._calculate_cagr(eps, 10)}
        ]

    def get_insights_valuation(self):
        pe = [x.get('priceEarningsRatio', 0) for x in self.annual_ratios]
        ps = [x.get('priceToSalesRatio', 0) for x in self.annual_ratios]
        return [
            {"Valuation": "P/E", "TTM": pe[0] if pe else None, "Avg. 5yr": self._calculate_avg(pe, 5), "Avg. 10yr": self._calculate_avg(pe, 10)},
            {"Valuation": "P/S", "TTM": ps[0] if ps else None, "Avg. 5yr": self._calculate_avg(ps, 5), "Avg. 10yr": self._calculate_avg(ps, 10)}
        ]

    def build_table(self, mapping, p_type='annual'):
        # ... logic as before ...
        return [] # Simplified for now to focus on insights
