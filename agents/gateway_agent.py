import os
import requests
import streamlit as st

class GatewayAgent:
    def __init__(self):
        raw_key = st.secrets.get("FMP_API_KEY", "")
        self.api_key = "".join(raw_key.split()).strip('"').strip("'")
        self.base_url = "https://financialmodelingprep.com/api/v4"

    def fetch_data(self, ticker, statement_type):
        if not self.api_key: return []
        
        # שימוש בנתיב ה-Stable החדש (v4) כפי שמופיע בתיעוד שלהם
        url = f"{self.base_url}/financial-reports-json"
        params = {
            "symbol": ticker,
            "year": 2024,
            "period": "FY",
            "apikey": self.api_key
        }
        
        try:
            # אנחנו מנסים קודם את ה-v4 היציב
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # אם קיבלנו דוח, נחזיר אותו (v4 מחזיר אובייקט בודד בדרך כלל)
                return [data] if isinstance(data, dict) else data
            
            # אם v4 נכשל, ננסה את נתיב ה-v3 בפורמט ה-Stable החדש
            v3_url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}"
            response = requests.get(v3_url, params={"apikey": self.api_key, "limit": 10})
            return response.json() if response.status_code == 200 else []
        except:
            return []

    def fetch_all(self, ticker):
        # גרסה מהירה לבדיקת הזרמת נתונים ל-getValue
        res = self.fetch_data(ticker, "income-statement")
        return {
            "annual_income_statement": res,
            "quarterly_income_statement": res,
            "annual_balance_sheet": res,
            "quarterly_balance_sheet": res,
            "annual_cash_flow": res,
            "quarterly_cash_flow": res,
        }
