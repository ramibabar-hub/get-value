"""
backend/services/pdf_auditor_service.py

Gemini-powered 10-K / annual report auditor.
Given a ticker, uses Gemini to extract key risk factors, revenue drivers, and red flags.

Public entry-point:
  audit_filing(ticker, filing_url=None) -> AuditResult dict
"""
from __future__ import annotations

import logging
import time
from typing import Any

from ._key_loader import load_key

log = logging.getLogger(__name__)

_CACHE: dict[str, dict[str, Any]] = {}
_TTL = 3600  # 1 hour — filings don't change intraday


def _is_fresh(entry: dict) -> bool:
    return time.time() < entry.get("expires_at", 0)


def audit_filing(ticker: str, filing_url: str | None = None) -> dict:
    """
    Audit a 10-K filing for *ticker* using Gemini.

    Response shape:
      {
        "ticker":        str,
        "filing_url":    str | None,
        "summary":       str,
        "risk_factors":  list[str],
        "red_flags":     list[str],
        "moat_signals":  list[str],
        "model":         str,
        "error":         str | None
      }
    """
    t = ticker.strip().upper()
    cache_key = f"{t}:{filing_url or 'latest'}"

    if cache_key in _CACHE and _is_fresh(_CACHE[cache_key]):
        log.info("[pdf_auditor] cache hit for %s", t)
        return _CACHE[cache_key]["data"]

    api_key = load_key("GEMINI_API_KEY")
    if not api_key:
        return _error_response(t, filing_url, "GEMINI_API_KEY not configured")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        if filing_url:
            prompt = (
                f"You are a senior financial analyst performing a 10-K audit for {t}. "
                f"The filing is available at: {filing_url}\n\n"
                f"Based on your knowledge of this company's most recent 10-K filing, provide:\n"
                f"1. A 3-5 sentence executive summary of the business and key developments\n"
                f"2. The top 3 risk factors investors should monitor\n"
                f"3. Any accounting or operational red flags\n"
                f"4. Key competitive moat signals\n\n"
                f"Respond in JSON with keys: summary (string), risk_factors (array of 3 strings), "
                f"red_flags (array of strings, empty if none), moat_signals (array of strings)."
            )
        else:
            prompt = (
                f"You are a senior financial analyst. Based on your knowledge of {t}'s most recent "
                f"annual report (10-K), provide:\n"
                f"1. A 3-5 sentence executive summary\n"
                f"2. Top 3 risk factors\n"
                f"3. Any accounting or operational red flags\n"
                f"4. Key competitive moat signals\n\n"
                f"Respond in JSON with keys: summary (string), risk_factors (array of 3 strings), "
                f"red_flags (array of strings, empty if none), moat_signals (array of strings)."
            )

        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )

        import json as _json
        parsed = _json.loads(response.text)

        data = {
            "ticker":       t,
            "filing_url":   filing_url,
            "summary":      str(parsed.get("summary", ""))[:1000],
            "risk_factors": [str(r)[:300] for r in parsed.get("risk_factors", [])[:5]],
            "red_flags":    [str(r)[:300] for r in parsed.get("red_flags", [])[:5]],
            "moat_signals": [str(r)[:300] for r in parsed.get("moat_signals", [])[:5]],
            "model":        "gemini-1.5-flash",
            "error":        None,
        }

        expires_at = time.time() + _TTL
        _CACHE[cache_key] = {"data": data, "expires_at": expires_at}
        log.info("[pdf_auditor] audit complete for %s", t)
        return data

    except Exception as exc:
        log.warning("[pdf_auditor] error for %s: %s", t, exc)
        return _error_response(t, filing_url, str(exc)[:200])


def _error_response(ticker: str, filing_url: str | None, msg: str) -> dict:
    return {
        "ticker": ticker, "filing_url": filing_url,
        "summary": "", "risk_factors": [], "red_flags": [], "moat_signals": [],
        "model": "gemini-1.5-flash", "error": msg,
    }
