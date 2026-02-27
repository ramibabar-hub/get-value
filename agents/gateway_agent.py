import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        self.api_key = st.secrets.get("FMP_API_KEY", "").strip().strip('"').strip("'")
        # ניסיון להשתמש ב-v4 במקום v3
        self.base_url = "https://financialmodelingprep.com/api/v4"

    def fetch_data(self, path, ticker):
        if not self.api_key: return []
        # ב-v4 המבנה לפעמים שונה, ננסה את הנתיב הנפוץ
        url = f"{self.base_url}/financial-reports-json"
        params = {"symbol": ticker, "year": 2024, "period": "FY", "apikey": self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=15)
            # אם גם v4 חסום, נחזור לניסיון v3 אחרון בנתיב מפורט
            if response.status_code != 200:
                v3_url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}"
                response = requests.get(v3_url, params={"apikey": self.api_key, "limit": 5})
            
            data = response.json()
            return data if isinstance(data, list) else []
        except:
            return []

    def fetch_all(self, ticker):
        # גרסה פשוטה לבדיקת הזרמת נתונים
        res = self.fetch_data("income-statement", ticker)
        return {
            "annual_income_statement": res,
            "quarterly_income_statement": res,
            "annual_balance_sheet": res,
            "quarterly_balance_sheet": res,
            "annual_cash_flow": res,
            "quarterly_cash_flow": res,
        }
