import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).replace('"', '').replace("'", "")
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_statement(self, ticker, statement_type, period='annual'):
        if not self.api_key:
            return []
            
        # שימוש בנתיבים החדשים ביותר כדי להימנע משגיאת Legacy
        # בגרסאות החדשות, חלק מהדוחות דורשים סיומת שונה
        url = f"{self.base_url}/{statement_type}/{ticker}"
        
        params = {"apikey": self.api_key, "limit": 5}
        if period == 'quarter':
            params["period"] = "quarter"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code != 200:
                # הדפסת הודעת אבחון רק אם יש שגיאה
                st.sidebar.error(f"Error {response.status_code} on {statement_type}")
                return []
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def fetch_all(self, ticker):
        # הגדרת הנתיבים המדויקים למנויים חדשים
        return {
            "annual_income_statement": self.fetch_statement(ticker, "income-statement", "annual"),
            "quarterly_income_statement": self.fetch_statement(ticker, "income-statement", "quarter"),
            "annual_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "annual"),
            "quarterly_balance_sheet": self.fetch_statement(ticker, "balance-sheet-statement", "quarter"),
            "annual_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "annual"),
            "quarterly_cash_flow": self.fetch_statement(ticker, "cash-flow-statement", "quarter"),
        }
