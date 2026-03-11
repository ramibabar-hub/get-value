"""
backend/services/cascade_service.py

4-provider cascade data service for company profile / quote requests.

Priority order (automatic fallback on empty or error):
  1. FMP          (Financial Modeling Prep)
  2. EODHD        (EOD Historical Data)
  3. Alpha Vantage
  4. Finnhub

All providers are normalised to a common CascadeProfile dict.
`data_source` and `providers_tried` fields in every response let callers
(and the frontend console) track which provider actually fulfilled the request.

Public entry-points:
  fetch_cascade_profile(ticker)  ->  CascadeProfile dict
  fetch_cascade_quote(ticker)    ->  CascadeQuote dict (price + change only)
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from ._key_loader import load_key

log = logging.getLogger(__name__)

# ── API base URLs ──────────────────────────────────────────────────────────────
_AV_BASE      = "https://www.alphavantage.co/query"
_FINNHUB_BASE = "https://finnhub.io/api/v1"
_UA           = "getValue/1.0"

# ── Key cache (loaded once) ────────────────────────────────────────────────────
_keys: dict[str, str] = {}

def _key(name: str) -> str:
    if name not in _keys:
        _keys[name] = load_key(name)
    return _keys[name]


# ─────────────────────────────────────────────────────────────────────────────
#  Normalised output shapes
# ─────────────────────────────────────────────────────────────────────────────

def _empty_profile(ticker: str) -> dict:
    return {
        "ticker":          ticker,
        "company_name":    "",
        "exchange":        "",
        "sector":          "",
        "industry":        "",
        "currency":        "",
        "country":         "",
        "description":     "",
        "price":           None,
        "market_cap":      None,
        "pe_ratio":        None,
        "logo_url":        "",
        "website":         "",
        "data_source":     "none",
        "providers_tried": [],
    }


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
        return f if f == f else None      # NaN guard
    except (TypeError, ValueError):
        return None


def _non_empty(d: dict) -> bool:
    """Return True when the dict has at least a company name or price."""
    return bool(d.get("company_name") or d.get("price") is not None)


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 1 — FMP
# ─────────────────────────────────────────────────────────────────────────────

def _try_fmp(ticker: str) -> dict | None:
    api_key = _key("FMP_API_KEY")
    if not api_key:
        return None
    try:
        from backend.services.fmp_service import FMPService
        svc  = FMPService()
        raw  = svc.fetch_overview(ticker)
        if not raw:
            return None
        return {
            "company_name": raw.get("companyName") or raw.get("name") or "",
            "exchange":     raw.get("exchangeShortName") or raw.get("exchange") or "",
            "sector":       raw.get("sector") or "",
            "industry":     raw.get("industry") or "",
            "currency":     raw.get("currency") or "USD",
            "country":      raw.get("country") or "",
            "description":  raw.get("description") or "",
            "price":        _safe_float(raw.get("price")),
            "market_cap":   _safe_float(raw.get("mktCap") or raw.get("marketCap")),
            "pe_ratio":     _safe_float(raw.get("pe") or raw.get("priceEarningsRatio")),
            "logo_url":     raw.get("image") or raw.get("logo") or "",
            "website":      raw.get("website") or "",
        }
    except Exception as exc:
        log.warning("[cascade] FMP failed for %s: %s", ticker, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 2 — EODHD
# ─────────────────────────────────────────────────────────────────────────────

def _try_eodhd(ticker: str) -> dict | None:
    api_key = _key("EODHD_API_KEY")
    if not api_key:
        return None
    try:
        from backend.services.gateway import SmartGateway
        gw  = SmartGateway()
        raw = gw.fetch_overview(ticker)
        if not raw:
            return None
        return {
            "company_name": raw.get("companyName") or raw.get("name") or "",
            "exchange":     raw.get("exchangeShortName") or raw.get("exchange") or "",
            "sector":       raw.get("sector") or "",
            "industry":     raw.get("industry") or "",
            "currency":     raw.get("currency") or "",
            "country":      raw.get("country") or "",
            "description":  raw.get("description") or "",
            "price":        _safe_float(raw.get("price")),
            "market_cap":   _safe_float(raw.get("mktCap") or raw.get("marketCap")),
            "pe_ratio":     _safe_float(raw.get("pe") or raw.get("priceEarningsRatio")),
            "logo_url":     raw.get("image") or raw.get("logo") or "",
            "website":      raw.get("website") or "",
        }
    except Exception as exc:
        log.warning("[cascade] EODHD failed for %s: %s", ticker, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 3 — Alpha Vantage
# ─────────────────────────────────────────────────────────────────────────────

def _try_alpha_vantage(ticker: str) -> dict | None:
    # Note: key name in .env is ALPHA_VINTAGE_API_KEY (typo preserved from .env)
    api_key = _key("ALPHA_VINTAGE_API_KEY")
    if not api_key:
        return None
    # Strip exchange suffix for AV (only handles US/simple symbols)
    symbol = ticker.split(".")[0] if "." in ticker else ticker
    try:
        r = requests.get(
            _AV_BASE,
            params={"function": "OVERVIEW", "symbol": symbol, "apikey": api_key},
            headers={"User-Agent": _UA},
            timeout=10,
        )
        data: dict = r.json()
        # AV returns {"Information": "..."} when rate-limited, or empty dict on miss
        if not data or "Information" in data or "Note" in data or not data.get("Symbol"):
            return None
        return {
            "company_name": data.get("Name") or "",
            "exchange":     data.get("Exchange") or "",
            "sector":       data.get("Sector") or "",
            "industry":     data.get("Industry") or "",
            "currency":     data.get("Currency") or "USD",
            "country":      data.get("Country") or "",
            "description":  data.get("Description") or "",
            "price":        None,    # AV OVERVIEW has no live price
            "market_cap":   _safe_float(data.get("MarketCapitalization")),
            "pe_ratio":     _safe_float(data.get("PERatio")),
            "logo_url":     "",      # AV doesn't provide logos
            "website":      data.get("OfficialSite") or "",
        }
    except Exception as exc:
        log.warning("[cascade] Alpha Vantage failed for %s: %s", ticker, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 4 — Finnhub
# ─────────────────────────────────────────────────────────────────────────────

def _try_finnhub(ticker: str) -> dict | None:
    api_key = _key("FINNHUB_API_KEY")
    if not api_key:
        return None
    symbol = ticker.split(".")[0] if "." in ticker else ticker
    try:
        r = requests.get(
            f"{_FINNHUB_BASE}/stock/profile2",
            params={"symbol": symbol, "token": api_key},
            headers={"User-Agent": _UA},
            timeout=10,
        )
        data: dict = r.json()
        if not data or not data.get("name"):
            return None
        return {
            "company_name": data.get("name") or "",
            "exchange":     data.get("exchange") or "",
            "sector":       "",               # Finnhub profile2 has no sector
            "industry":     data.get("finnhubIndustry") or "",
            "currency":     data.get("currency") or "",
            "country":      data.get("country") or "",
            "description":  "",               # Finnhub profile2 has no description
            "price":        None,             # use /quote endpoint for live price
            "market_cap":   _safe_float(data.get("marketCapitalization")),
            "pe_ratio":     None,
            "logo_url":     data.get("logo") or "",
            "website":      data.get("weburl") or "",
        }
    except Exception as exc:
        log.warning("[cascade] Finnhub failed for %s: %s", ticker, exc)
        return None


def _try_finnhub_quote(ticker: str) -> float | None:
    """Supplement Finnhub profile with live price from /quote."""
    api_key = _key("FINNHUB_API_KEY")
    if not api_key:
        return None
    symbol = ticker.split(".")[0] if "." in ticker else ticker
    try:
        r = requests.get(
            f"{_FINNHUB_BASE}/quote",
            params={"symbol": symbol, "token": api_key},
            headers={"User-Agent": _UA},
            timeout=8,
        )
        data: dict = r.json()
        return _safe_float(data.get("c"))   # "c" = current price
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Public: fetch_cascade_profile
# ─────────────────────────────────────────────────────────────────────────────

_PROVIDERS = [
    ("fmp",           _try_fmp),
    ("eodhd",         _try_eodhd),
    ("alpha_vantage", _try_alpha_vantage),
    ("finnhub",       _try_finnhub),
]


def fetch_cascade_profile(ticker: str) -> dict:
    """
    Try each provider in priority order; return the first non-empty result.
    The returned dict always includes `data_source` and `providers_tried`.

    Logging:
      - INFO  on each provider attempt
      - INFO  when a provider succeeds
      - WARNING when a provider fails (also logged inside each _try_ function)
    """
    t = ticker.strip().upper()
    tried: list[str] = []

    for name, fn in _PROVIDERS:
        log.info("[cascade] %s - trying %s", t, name)
        tried.append(name)
        result = fn(t)
        if result and _non_empty(result):
            log.info("[cascade] %s - fulfilled by %s", t, name)
            # If Finnhub profile has no price, supplement with /quote
            if name == "finnhub" and result.get("price") is None:
                result["price"] = _try_finnhub_quote(t)
            out = _empty_profile(t)
            out.update(result)
            out["data_source"]     = name
            out["providers_tried"] = tried
            return out

    log.warning("[cascade] %s - all providers exhausted", t)
    out = _empty_profile(t)
    out["providers_tried"] = tried
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Public: fetch_cascade_quote  (price + change only — lightweight)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_cascade_quote(ticker: str) -> dict:
    """
    Return a minimal price/change dict using the fastest available provider.
    Useful for refreshing live prices without a full profile fetch.
    """
    t = ticker.strip().upper()

    # FMP quote
    try:
        fmp_key = _key("FMP_API_KEY")
        if fmp_key:
            r = requests.get(
                "https://financialmodelingprep.com/stable/quote",
                params={"symbol": t, "apikey": fmp_key},
                headers={"User-Agent": _UA},
                timeout=8,
            )
            data = r.json()
            if isinstance(data, list) and data:
                q = data[0]
                return {
                    "ticker": t, "price": _safe_float(q.get("price")),
                    "change_pct": _safe_float(q.get("changesPercentage") or q.get("changePercentage")),
                    "data_source": "fmp",
                }
    except Exception:
        pass

    # Finnhub quote
    try:
        fh_key = _key("FINNHUB_API_KEY")
        if fh_key:
            symbol = t.split(".")[0]
            r = requests.get(
                f"{_FINNHUB_BASE}/quote",
                params={"symbol": symbol, "token": fh_key},
                headers={"User-Agent": _UA},
                timeout=8,
            )
            data = r.json()
            price = _safe_float(data.get("c"))
            prev  = _safe_float(data.get("pc"))
            chg   = ((price - prev) / prev * 100) if price and prev and prev != 0 else None
            if price:
                return {"ticker": t, "price": price, "change_pct": chg, "data_source": "finnhub"}
    except Exception:
        pass

    return {"ticker": t, "price": None, "change_pct": None, "data_source": "none"}
