import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        # משיכה נקייה של המפתח
        raw_key = st.secrets.get("FMP_API_KEY") or os.getenv("FMP_API_KEY")
        self.api_key = raw_key.strip().replace('"', '').replace("'", "") if raw_key else None
        self.base_url = "https://financialmodelingprep.com/api/v3"
        
        if not self.api_key:
            st.error("❌ API Key is missing!")

    def fetch_statement(self, ticker: str, statement_type: str, period: str = 'annual'):
        url = f"{self.base_url}/{statement_type}/{ticker}"
        params = {"apikey": self.api_key, "limit": 5}
        if period == 'quarter':
            params["period"] = "quarter"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            return []
        except:
            return []

    def fetch_all(self, ticker: str):
        return {
            "annual_income_statement": self.fetch_statement(ticker, "income-statement", "annual"),
            "quarterly_income_statement": self.fetch_statement(ticker, "income-statement", "quarter"),
            "annual_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "annual"),
            "quarterly_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "quarter"),
            "annual_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "annual"),
            "quarterly_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "quarter"),
        }
