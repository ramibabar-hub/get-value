"""
backend/services/gemini_service.py

Gemini API integration for qualitative financial analysis.
Uses the Gemini REST API directly (no google-generativeai package required).

Model: gemini-1.5-flash  (fast, cost-efficient, 1M context)
Key:   REACT_APP_GEMINI_API_KEY  (as stored in .env)

Public entry-point:
  analyze_company(ticker, context)  ->  GeminiAnalysis dict
"""
from __future__ import annotations

import logging

import requests

from ._key_loader import load_key

log = logging.getLogger(__name__)

_GEMINI_BASE  = "https://generativelanguage.googleapis.com/v1beta"
_MODEL        = "gemini-1.5-flash"
_TIMEOUT      = 20   # seconds
_MAX_TOKENS   = 512


def _api_key() -> str:
    return load_key("REACT_APP_GEMINI_API_KEY")


# ─────────────────────────────────────────────────────────────────────────────
#  Prompt builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(ticker: str, context: dict) -> str:
    """
    Build a concise prompt that gives Gemini enough financial context to
    produce a useful 3–5 sentence qualitative summary.
    """
    name    = context.get("company_name") or ticker
    sector  = context.get("sector")        or "Unknown"
    industry = context.get("industry")     or "Unknown"
    country = context.get("country")       or "Unknown"
    mktcap  = context.get("market_cap")
    pe      = context.get("pe_ratio")
    desc    = context.get("description")   or ""

    cap_str = f"${mktcap / 1e9:.1f}B market cap" if mktcap else "unknown market cap"
    pe_str  = f"P/E {pe:.1f}x"                    if pe     else "P/E unavailable"

    # Trim description to avoid blowing the context window
    short_desc = (desc[:600] + "…") if len(desc) > 600 else desc

    return f"""You are a senior equity research analyst. Write a concise 3–5 sentence qualitative summary for the following company. Focus on: business model strength, competitive position, key risks, and whether the current valuation appears reasonable. Be direct and analytical — avoid generic platitudes.

Company: {name} ({ticker})
Sector / Industry: {sector} / {industry}
Country: {country}
Size: {cap_str}  |  {pe_str}

Business description: {short_desc}

Summary:"""


# ─────────────────────────────────────────────────────────────────────────────
#  Predefined analysis prompts (callable by type)
# ─────────────────────────────────────────────────────────────────────────────

_ANALYSIS_PROMPTS: dict[str, str] = {
    "summary": "Provide a concise 3–5 sentence investment summary covering business model, competitive moat, and key risks.",
    "moat":    "Assess the company's economic moat (competitive advantage). Rate it as Wide / Narrow / None and explain why in 2–3 sentences.",
    "risks":   "List the top 3 material risks for this company as an investor, with one sentence explaining each.",
    "valuation": "Comment on whether the current valuation (based on the metrics provided) appears cheap, fair, or expensive relative to the business quality.",
}


def _build_typed_prompt(ticker: str, analysis_type: str, context: dict) -> str:
    instruction = _ANALYSIS_PROMPTS.get(analysis_type, _ANALYSIS_PROMPTS["summary"])
    name    = context.get("company_name") or ticker
    sector  = context.get("sector")        or "Unknown"
    mktcap  = context.get("market_cap")
    pe      = context.get("pe_ratio")
    desc    = context.get("description")   or ""

    cap_str  = f"${mktcap / 1e9:.1f}B" if mktcap else "N/A"
    pe_str   = f"{pe:.1f}x"            if pe      else "N/A"
    short_desc = (desc[:400] + "…")    if len(desc) > 400 else desc

    return (
        f"Company: {name} ({ticker}) | Sector: {sector} | "
        f"Market Cap: {cap_str} | P/E: {pe_str}\n"
        f"Description: {short_desc}\n\n"
        f"Task: {instruction}\nResponse:"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Public: analyze_company
# ─────────────────────────────────────────────────────────────────────────────

def analyze_company(
    ticker: str,
    context: dict,
    analysis_type: str = "summary",
) -> dict:
    """
    Call Gemini to generate qualitative analysis for a company.

    Args:
        ticker:        e.g. "AAPL"
        context:       dict with keys from CascadeProfile (company_name, sector,
                       industry, market_cap, pe_ratio, description, …)
        analysis_type: "summary" | "moat" | "risks" | "valuation"

    Returns:
        {
            "ticker":        str,
            "analysis_type": str,
            "text":          str,   # Gemini's response
            "model":         str,   # model used
            "error":         str | None,
        }
    """
    api_key = _api_key()
    result_base = {
        "ticker":        ticker.upper(),
        "analysis_type": analysis_type,
        "text":          "",
        "model":         _MODEL,
        "error":         None,
    }

    if not api_key:
        log.warning("[gemini] REACT_APP_GEMINI_API_KEY not set")
        result_base["error"] = "Gemini API key not configured"
        return result_base

    prompt = _build_typed_prompt(ticker.upper(), analysis_type, context)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": _MAX_TOKENS,
            "temperature":     0.4,   # factual, low creativity
            "topP":            0.8,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    try:
        r = requests.post(
            f"{_GEMINI_BASE}/models/{_MODEL}:generateContent",
            params={"key": api_key},
            json=payload,
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            log.warning("[gemini] HTTP %s for %s: %s", r.status_code, ticker, r.text[:200])
            result_base["error"] = f"Gemini HTTP {r.status_code}"
            return result_base

        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            result_base["error"] = "Gemini returned no candidates"
            return result_base

        text = (
            candidates[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        result_base["text"] = text
        log.info("[gemini] %s (%s): %d chars", ticker, analysis_type, len(text))
        return result_base

    except Exception as exc:
        log.warning("[gemini] Error for %s: %s", ticker, exc)
        result_base["error"] = str(exc)
        return result_base
