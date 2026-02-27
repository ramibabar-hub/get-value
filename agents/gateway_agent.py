import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        # ניקוי מוחלט של המפתח מכל תו מיותר
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).replace('"', '').replace("'", "")
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_statement(self, ticker, statement_type, period='annual'):
        if not self.api_key:
            return []
            
        url = f"{self.base_url}/{statement_type}/{ticker}"
        params = {"apikey": self.api_key, "limit": 5}
        if period == 'quarter':
            params["period"] = "quarter"
        
        # הוספת כותרות שמדמות דפדפן רגיל
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 403:
                # הדפסת הודעת אבחון מפורטת מהשרת
                st.error(f"🔑 שגיאת הרשאה 403. תגובת השרת: {response.text}")
                return []
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            st.error(f"⚠️ שגיאה: {e}")
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
