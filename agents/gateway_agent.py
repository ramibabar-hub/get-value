import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        # משיכה ישירה ומאובטחת
        self.api_key = st.secrets.get("FMP_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_statement(self, ticker, statement_type, period='annual'):
        if not self.api_key:
            return []
            
        url = f"{self.base_url}/{statement_type}/{ticker}"
        params = {"apikey": self.api_key, "limit": 5}
        if period == 'quarter':
            params["period"] = "quarter"
        
        try:
            response = requests.get(url, params=params, timeout=15)
            # אם השרת מחזיר שגיאת הרשאה, נדפיס אותה למסך לצורך אבחון
            if response.status_code == 403:
                st.error("🔑 ה-API Key נדחה ע\"י השרת (403 Forbidden). וודא שהמנוי פעיל.")
                return []
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            st.error(f"⚠️ שגיאת תקשורת: {e}")
            return []

    def fetch_all(self, ticker):
        return {
            "annual_income_statement": self.fetch_statement(ticker, "income-statement", "annual"),
            "quarterly_income_statement": self.fetch_statement(ticker, "income-statement", "quarter"),
            "annual_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "annual"),
            "quarterly_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "quarter"),
            "annual_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "annual"),
            "quarterly_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "quarter"),
        }
