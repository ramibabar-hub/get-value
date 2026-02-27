import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        # ניקוי המפתח מכל שארית של גרשיים או רווחים
        self.api_key = st.secrets.get("FMP_API_KEY", "").strip().strip('"').strip("'")
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_data(self, endpoint, ticker, is_quarterly=False):
        if not self.api_key:
            return []
        url = f"{self.base_url}/{endpoint}/{ticker}"
        params = {"apikey": self.api_key, "limit": 10}
        if is_quarterly:
            params["period"] = "quarter"
        
        try:
            # הוספת Headers מינימליים למניעת חסימות
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []

    def fetch_all(self, ticker):
        return {
            "annual_income_statement": self.fetch_data("income-statement", ticker),
            "quarterly_income_statement": self.fetch_data("income-statement", ticker, True),
            "annual_balance_sheet": self.fetch_data("balance-sheet-statement", ticker),
            "quarterly_balance_sheet": self.fetch_data("balance-sheet-statement", ticker, True),
            "annual_cash_flow": self.fetch_data("cash-flow-statement", ticker),
            "quarterly_cash_flow": self.fetch_data("cash-flow-statement", ticker, True),
        }
