"""
backend/services/grok_service.py
Grok (xAI) sentiment service — "Why is it moving?" badge.

Uses the xAI API which is OpenAI-compatible.
Key: GROK_API_KEY in .env
Cache: in-memory, 15 minutes per ticker.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from ._key_loader import load_key

log = logging.getLogger(__name__)

_BASE_URL = "https://api.x.ai/v1/chat/completions"
_MODEL    = "grok-3-latest"
_CACHE: dict[str, dict[str, Any]] = {}   # ticker -> {data, expires_at}
_TTL = 900   # 15 minutes


def _is_fresh(entry: dict) -> bool:
    return time.time() < entry.get("expires_at", 0)


def get_sentiment(ticker: str) -> dict:
    """
    Return a sentiment dict for *ticker*.

    Response shape:
      {
        "ticker":        str,
        "score":         float,   # 0.0 (very bearish) – 1.0 (very bullish)
        "label":         str,     # "Bullish" | "Neutral" | "Bearish"
        "reason":        str,     # 1-sentence plain-English explanation
        "source":        "grok",
        "cached_until":  str,     # ISO timestamp
        "error":         str | None
      }
    """
    t = ticker.strip().upper()

    # Cache hit
    if t in _CACHE and _is_fresh(_CACHE[t]):
        log.info("[grok] cache hit for %s", t)
        return _CACHE[t]["data"]

    api_key = load_key("GROK_API_KEY")
    if not api_key:
        return _error_response(t, "GROK_API_KEY not configured")

    prompt = (
        f"You are a financial sentiment analyst. "
        f"For the stock ticker {t}, provide a one-sentence explanation of "
        f"the current market sentiment and the primary reason driving it. "
        f"Also rate the sentiment on a scale from 0.0 (very bearish) to 1.0 (very bullish). "
        f"Respond in JSON only with keys: score (float), label (Bullish|Neutral|Bearish), reason (string)."
    )

    try:
        resp = requests.post(
            _BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":    _MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
            timeout=15,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        import json as _json
        parsed = _json.loads(content)

        score = float(parsed.get("score", 0.5))
        score = max(0.0, min(1.0, score))   # clamp to [0,1]

        label = parsed.get("label", "Neutral")
        if label not in ("Bullish", "Neutral", "Bearish"):
            label = "Neutral"

        reason = str(parsed.get("reason", ""))[:300]   # max 300 chars

        expires_at = time.time() + _TTL
        data = {
            "ticker":       t,
            "score":        round(score, 3),
            "label":        label,
            "reason":       reason,
            "source":       "grok",
            "cached_until": _iso(expires_at),
            "error":        None,
        }
        _CACHE[t] = {"data": data, "expires_at": expires_at}
        log.info("[grok] sentiment for %s: %s (%.2f)", t, label, score)
        return data

    except requests.exceptions.Timeout:
        return _error_response(t, "Grok API timeout")
    except Exception as exc:
        log.warning("[grok] error for %s: %s", t, exc)
        return _error_response(t, str(exc)[:120])


def _error_response(ticker: str, msg: str) -> dict:
    return {
        "ticker": ticker, "score": None, "label": "Unavailable",
        "reason": "", "source": "grok",
        "cached_until": None, "error": msg,
    }


def _iso(ts: float) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
