import os
import requests
import streamlit as st
from typing import Optional, Literal, Dict, List, Union
from dotenv import load_dotenv

load_dotenv()
api_key = st.secrets.get("FMP_API_KEY") or os.getenv("FMP_API_KEY")

class GatewayAgent:
    def __init__(self):
        self.api_key = api_key
        # שימוש בכתובת הבסיס המעודכנת
        self.base_url = "https://financialmodelingprep.com/api/v3"
        if not self.api_key:
            st.error("Missing API Key!")

    def fetch_statement(self, ticker: str, statement_type: str, period: str = 'annual'):
        # בניית ה-URL לפי הדוקומנטציה החדשה של FMP
        url = f"{self.base_url}/{statement_type}/{ticker}"
        params = {
            "apikey": self.api_key,
            "limit": 10
        }
        if period == 'quarter':
            params["period"] = "quarter"
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            else:
                return []
        except Exception:
            return []

    def fetch_all(self, ticker: str):
        # קריאות ישירות לכל דוח בנפרד (לא דרך אנדפוינט מאוחד שיכול להיחשב Legacy)
        return {
            "annual_income_statement": self.fetch_statement(ticker, "income-statement", "annual"),
            "quarterly_income_statement": self.fetch_statement(ticker, "income-statement", "quarter"),
            "annual_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "annual"),
            "quarterly_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "quarter"),
            "annual_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "annual"),
            "quarterly_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "quarter"),
        }
