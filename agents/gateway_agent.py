import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).strip('"').strip("'")
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_data(self, path, ticker, is_quarterly=False):
        if not self.api_key:
            return []
        
        # ניסיון ראשון: הפורמט הסטנדרטי המעודכן
        url = f"{self.base_url}/{path}/{ticker}"
        params = {"apikey": self.api_key, "limit": 12}
        if is_quarterly:
            params["period"] = "quarter"
        
        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            # אם קיבלנו שגיאת Legacy, ננסה את הנתיב ה-Stable החדש (financial-statements/...)
            if isinstance(data, dict) and "Legacy Endpoint" in data.get("Error Message", ""):
                stable_path = f"financial-statements/{path}"
                url = f"{self.base_url}/{stable_path}/{ticker}"
                response = requests.get(url, params=params, timeout=15)
                data = response.json()
            
            return data if isinstance(data, list) else []
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
