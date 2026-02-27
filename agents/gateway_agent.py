import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class GatewayAgent:
    def __init__(self):
        # משיכה מאובטחת וניקוי רווחים מהמפתח
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).strip('"').strip("'")
        # שימוש בכתובת הבסיס המעודכנת ביותר
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_data(self, path, ticker, is_quarterly=False):
        if not self.api_key:
            return []
        
        # בניית ה-URL בצורה המפורשת ביותר למנויים חדשים
        url = f"{self.base_url}/{path}/{ticker}"
        params = {
            "apikey": self.api_key,
            "limit": 10
        }
        if is_quarterly:
            params["period"] = "quarter"
        
        try:
            # הוספת Headers שמדמים דפדפן מודרני כדי למנוע חסימות Legacy
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # אם קיבלנו הודעת שגיאה בתוך ה-JSON (כמו Legacy Error)
                if isinstance(data, dict) and "Error Message" in data:
                    return []
                return data if isinstance(data, list) else []
            return []
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
