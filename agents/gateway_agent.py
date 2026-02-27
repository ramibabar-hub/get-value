import os
import requests
import streamlit as st
from typing import Optional, Literal, Dict, List, Union
from dotenv import load_dotenv

StatementType = Literal["income-statement", "balance-sheet-statement", "cash-flow-statement"]

load_dotenv()
api_key = st.secrets.get("FMP_API_KEY") or os.getenv("FMP_API_KEY")

class GatewayAgent:
    def __init__(self):
        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com/api/v3"
        if not self.api_key:
            st.error("Missing API Key! Please set FMP_API_KEY in Secrets.")

    def fetch_statement(self, ticker: str, statement: str, period: str = 'annual'):
        url = f"{self.base_url}/{statement}/{ticker}"
        params = {"apikey": self.api_key, "limit": 10}
        if period == 'quarter': 
            params["period"] = "quarter"
        
        try:
            response = requests.get(url, params=params)
            if response.status_code != 200:
                return []
            data = response.json()
            # FMP מחזיר לפעמים רשימה ריקה אם הטיקר לא נמצא
            return data if isinstance(data, list) else []
        except Exception:
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
