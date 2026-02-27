import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        # ניקוי המפתח מכל שארית
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).strip('"').strip("'")

    def fetch_data(self, path, ticker, is_quarterly=False):
        if not self.api_key:
            return []
        
        # ניסיון 1: v3 הסטנדרטי
        v3_url = f"https://financialmodelingprep.com/api/v3/{path}/{ticker}"
        params = {"apikey": self.api_key, "limit": 12}
        if is_quarterly:
            params["period"] = "quarter"
            
        try:
            response = requests.get(v3_url, params=params, timeout=10)
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data
            
            # ניסיון 2: אם v3 החזיר רשימה ריקה או שגיאה, ננסה v4 (למנויים חדשים)
            v4_url = f"https://financialmodelingprep.com/api/v4/financial-reports-json"
            v4_params = {"symbol": ticker, "year": 2024, "period": "FY", "apikey": self.api_key}
            response = requests.get(v4_url, params=v4_params, timeout=10)
            # v4 מחזיר מבנה מעט שונה, ננסה לחלץ אותו
            return response.json() if response.status_code == 200 else []
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
