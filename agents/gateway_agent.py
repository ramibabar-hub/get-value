import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).strip('"').strip("'")
        # שימוש בבסיס הנתונים היציב החדש
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_data(self, path, ticker, is_quarterly=False):
        if not self.api_key: return []
        
        # רשימת נתיבי Stable לפי הדוקומנטציה החדשה של 2026
        # הוספנו את המבנה של financial-statements/ כפי שהם דורשים כיום
        endpoints = [
            f"{self.base_url}/financial-statements/{path}/{ticker}",
            f"{self.base_url}/{path}/{ticker}"
        ]
        
        params = {"apikey": self.api_key, "limit": 12}
        if is_quarterly:
            params["period"] = "quarter"
        
        for url in endpoints:
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # אם קיבלנו רשימה ויש בה תוכן - הצלחנו
                    if isinstance(data, list) and len(data) > 0:
                        return data
                    # אם קיבלנו דיקט עם שגיאת Legacy - נמשיך לנתיב הבא
                    if isinstance(data, dict) and "Legacy" in data.get("Error Message", ""):
                        continue
            except:
                continue
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
