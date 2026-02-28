import os
import json
import requests
import streamlit as st

def _load_api_key():
    """
    Priority: st.secrets → os.environ → .env file.
    This ensures the key is found both in Streamlit Cloud and in local dev
    even when .streamlit/secrets.toml doesn't exist yet.
    """
    # 1. Streamlit secrets (Cloud / .streamlit/secrets.toml)
    try:
        raw = st.secrets.get("FMP_API_KEY", "")
        if raw:
            return "".join(raw.split()).strip('"').strip("'")
    except Exception:
        pass
    # 2. Environment variable
    raw = os.environ.get("FMP_API_KEY", "")
    if raw:
        return raw.strip()
    # 3. Read .env file directly
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("FMP_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

class GatewayAgent:
    def __init__(self):
        self.api_key = _load_api_key()
        # FMP deprecated /api/v3 on Aug 31 2025 — use /stable
        self.base_url = "https://financialmodelingprep.com/stable"
        if not self.api_key:
            print("[GatewayAgent] WARNING: FMP_API_KEY not found in secrets, env, or .env")
        else:
            print(f"[GatewayAgent] API key loaded (ends: ...{self.api_key[-4:]})")

    def fetch_data(self, path, ticker, is_quarterly=False):
        if not self.api_key:
            print(f"[GatewayAgent] No API key — skipping {path}/{ticker}")
            return []
        url = f"{self.base_url}/{path}"
        # limit=15 ensures 10+ historical records (verified in params below)
        params = {"symbol": ticker, "apikey": self.api_key, "limit": 15}
        if is_quarterly:
            params["period"] = "quarter"
        label = f"{'Q' if is_quarterly else 'A'}/{path}/{ticker}"
        print(f"[GatewayAgent] GET {url} params={list(params.keys())} limit={params['limit']}")
        try:
            res = requests.get(url, params=params, timeout=10)
            body = res.json()
            if not isinstance(body, list):
                print(f"[GatewayAgent] ERROR {label} status={res.status_code}: {body}")
                return []
            if not body:
                print(f"[GatewayAgent] EMPTY {label} (0 records)")
                return []
            first = body[0]
            print(f"[GatewayAgent] OK {label}: {len(body)} records | "
                  f"fiscalYear={first.get('fiscalYear')} calendarYear={first.get('calendarYear')} "
                  f"period={first.get('period')}")
            # Diagnostic: print first record keys if year fields are both missing
            if not first.get('fiscalYear') and not first.get('calendarYear'):
                print(f"[GatewayAgent] DIAGNOSTIC — first record keys: {list(first.keys())}")
                print(f"[GatewayAgent] DIAGNOSTIC — first record: {json.dumps(first, default=str)}")
            return body
        except Exception as e:
            print(f"[GatewayAgent] EXCEPTION {label}: {e}")
            return []

    def fetch_all(self, ticker):
        return {
            "annual_income_statement":    self.fetch_data("income-statement",       ticker),
            "quarterly_income_statement": self.fetch_data("income-statement",       ticker, True),
            "annual_balance_sheet":       self.fetch_data("balance-sheet-statement",ticker),
            "quarterly_balance_sheet":    self.fetch_data("balance-sheet-statement",ticker, True),
            "annual_cash_flow":           self.fetch_data("cash-flow-statement",    ticker),
            "quarterly_cash_flow":        self.fetch_data("cash-flow-statement",    ticker, True),
            "annual_ratios":              self.fetch_data("ratios",                 ticker),
        }
