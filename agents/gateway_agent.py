import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).strip('"').strip("'")
        self.base_url_v3 = "https://financialmodelingprep.com/api/v3"
        self.base_url_v4 = "https://financialmodelingprep.com/api/v4"

    def fetch_data(self, path, ticker, is_quarterly=False):
        if not self.api_key: return []
        
        params = {"apikey": self.api_key, "limit": 12}
        if is_quarterly: params["period"] = "quarter"
        
        # רשימת נתיבים לניסיון לפי סדר העדכניות (Stable Documentation)
        endpoints = [
            f"{self.base_url_v3}/{path}/{ticker}",               # Standard v3
            f"{self.base_url_v3}/financial-reports-json",         # New Structured
            f"{self.base_url_v4}/financial-reports-json"          # v4 Stable
        ]

        for url in endpoints:
            try:
                # במידה ומדובר בנתיב financial-reports-json, הפרמטרים שונים
                current_params = params.copy()
                if "financial-reports-json" in url:
                    current_params = {"symbol": ticker, "year": 2024, "period": "FY", "apikey": self.api_key}

                response = requests.get(url, params=current_params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # אם זו לא הודעת שגיאה וזו רשימה עם תוכן - מצאנו!
                    if isinstance(data, list) and len(data) > 0:
                        if "Error Message" not in str(data):
                            return data
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
