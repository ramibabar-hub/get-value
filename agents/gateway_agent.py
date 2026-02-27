from typing import Optional, Literal, Dict, List, Union

# הגדרת הטיפוס שחסר למערכת
StatementType = Literal["income-statement", "balance-sheet-statement", "cash-flow-statement"]import os
import requests
import streamlit as st
from dotenv import load_dotenv

# טעינת המפתח (עובד גם מקומית וגם בענן)
load_dotenv()
api_key = st.secrets.get("FMP_API_KEY") or os.getenv("FMP_API_KEY")

class GatewayAgent:
    def __init__(self):
        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com/api/v3"
        
        if not self.api_key:
            raise ValueError("API Key is missing! Please set FMP_API_KEY in Secrets or .env")


class GatewayAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FMP_API_KEY not found. "
                "Add it to your .env file: FMP_API_KEY=your_key_here"
            )
        self.session = requests.Session()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fetch(self, endpoint: str, params: dict) -> list:
        params = {**params, "apikey": self.api_key}
        url = f"{FMP_BASE_URL}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP error fetching {url}: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection error: {e}") from e

        data = response.json()
        if isinstance(data, dict) and "Error Message" in data:
            raise ValueError(f"FMP API Error: {data['Error Message']}")
        return data if isinstance(data, list) else []

    # ── Public ────────────────────────────────────────────────────────────────

    def fetch_statement(
        self,
        ticker: str,
        statement: StatementType,
        period: str = "annual",
        limit: int = 5,
    ) -> list:
        """
        Fetch one financial statement.

        Args:
            ticker:    Stock symbol, e.g. 'AAPL'
            statement: StatementType enum value
            period:    'annual' or 'quarter'
            limit:     Number of periods to return
        """
        params: dict = {"symbol": ticker.upper(), "limit": limit}
        if period == "quarter":
            params["period"] = "quarter"
        endpoint = statement.value
        return self._fetch(endpoint, params)

    def fetch_all(self, ticker: str) -> dict:
        """
        Fetch all three statements in both annual and quarterly views.

        Free-tier cap is 5 periods per request.

        Returns dict keys:
            annual_INCOME, annual_BALANCE, annual_CASHFLOW
            quarterly_INCOME, quarterly_BALANCE, quarterly_CASHFLOW
        """
        ticker = ticker.upper()
        results: dict = {}

        for stmt in StatementType:
            print(f"  Fetching {stmt.name} (annual)  ...", end=" ", flush=True)
            results[f"annual_{stmt.name}"] = self.fetch_statement(
                ticker, stmt, period="annual", limit=5
            )
            print("OK")

            print(f"  Fetching {stmt.name} (quarterly) ...", end=" ", flush=True)
            results[f"quarterly_{stmt.name}"] = self.fetch_statement(
                ticker, stmt, period="quarter", limit=5
            )
            print("OK")

        return results
