/**
 * GrokSentimentBadge.tsx
 *
 * Displays live sentiment from Grok (xAI) as a colour-coded badge.
 * Shows "Why is it moving?" tooltip on hover.
 *
 * - sessionStorage cache: 15 min TTL per ticker
 * - Degrades silently: if API unavailable, renders nothing
 */
import { useState, useEffect } from "react";
import type { GrokSentiment } from "../types";

const SESSION_TTL_MS = 15 * 60 * 1000;

function getCached(ticker: string): GrokSentiment | null {
  try {
    const raw = sessionStorage.getItem(`gv_grok_${ticker}`);
    if (!raw) return null;
    const { data, expires } = JSON.parse(raw);
    if (Date.now() > expires) { sessionStorage.removeItem(`gv_grok_${ticker}`); return null; }
    return data as GrokSentiment;
  } catch { return null; }
}

function setCache(ticker: string, data: GrokSentiment) {
  try {
    sessionStorage.setItem(`gv_grok_${ticker}`, JSON.stringify({ data, expires: Date.now() + SESSION_TTL_MS }));
  } catch { /* storage full — ignore */ }
}

const LABEL_STYLES: Record<string, { bg: string; fg: string; dot: string }> = {
  Bullish:     { bg: "var(--gv-green-bg)",  fg: "var(--gv-green)",  dot: "#22c55e" },
  Bearish:     { bg: "var(--gv-red-bg)",    fg: "var(--gv-red)",    dot: "#ef4444" },
  Neutral:     { bg: "var(--gv-data-bg)",   fg: "var(--gv-data-fg)", dot: "#9ca3af" },
  Unavailable: { bg: "var(--gv-data-bg)",   fg: "var(--gv-text-muted)", dot: "#d1d5db" },
};

export default function GrokSentimentBadge({ ticker }: { ticker: string }) {
  const [data, setData]       = useState<GrokSentiment | null>(getCached(ticker));
  const [loading, setLoading] = useState(!getCached(ticker));
  const [hover, setHover]     = useState(false);

  useEffect(() => {
    const cached = getCached(ticker);
    if (cached) { setData(cached); setLoading(false); return; }

    setLoading(true);
    setData(null);
    const ctrl = new AbortController();

    fetch(`/api/grok/sentiment/${ticker}`, { signal: ctrl.signal })
      .then(r => r.json())
      .then((d: GrokSentiment) => {
        setData(d);
        if (!d.error) setCache(ticker, d);
      })
      .catch(() => { /* silently hide on error */ })
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [ticker]);

  if (loading) {
    return (
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "3px 10px", borderRadius: 20,
        background: "var(--gv-data-bg)", fontSize: "0.75em",
      }}>
        <span style={{
          display: "inline-block", width: 8, height: 8, borderRadius: "50%",
          background: "#d1d5db",
          animation: "gv-pulse 1.2s ease-in-out infinite",
        }} />
        <style>{`@keyframes gv-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }`}</style>
        <span style={{ color: "var(--gv-text-muted)" }}>Analysing…</span>
      </div>
    );
  }

  if (!data || data.error || data.label === "Unavailable") return null;

  const s = LABEL_STYLES[data.label] ?? LABEL_STYLES.Neutral;

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "3px 10px", borderRadius: 20,
          background: s.bg, border: "none", cursor: "pointer",
          fontSize: "0.75em", fontWeight: 600, color: s.fg,
          transition: "opacity 0.15s",
        }}
      >
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.dot, flexShrink: 0 }} />
        {data.label}
        <span style={{ color: "var(--gv-text-muted)", fontWeight: 400 }}> · Why?</span>
      </button>

      {hover && data.reason ? (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", left: 0, zIndex: 50,
          background: "var(--gv-navy)", color: "#fff",
          padding: "10px 14px", borderRadius: "var(--gv-radius-sm)",
          maxWidth: 320, fontSize: "0.8em", lineHeight: 1.55,
          boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
          pointerEvents: "none",
        }}>
          <div style={{ fontWeight: 700, marginBottom: 4, color: "#93c5fd" }}>
            Why is {ticker} moving?
          </div>
          {data.reason}
          <div style={{ marginTop: 6, fontSize: "0.82em", color: "#9ca3af" }}>
            Powered by Grok · {data.cached_until ? `fresh until ${data.cached_until.slice(11, 16)} UTC` : ""}
          </div>
        </div>
      ) : null}
    </div>
  );
}
