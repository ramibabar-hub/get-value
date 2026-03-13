/**
 * FilingAuditPanel.tsx
 *
 * Collapsible "10-K Audit" panel powered by Gemini.
 * Lazy-loads on first expand. Module-level cache per ticker.
 * Placed in Overview tab below the metrics grid.
 */
import { useState } from "react";
import type { FilingAudit } from "../types";

const _auditCache = new Map<string, FilingAudit>();

export default function FilingAuditPanel({
  ticker,
  filingUrl,
}: {
  ticker: string;
  filingUrl?: string;
}) {
  const [open, setOpen]       = useState(false);
  const [data, setData]       = useState<FilingAudit | null>(_auditCache.get(ticker) ?? null);
  const [loading, setLoading] = useState(false);

  function toggle() {
    if (!open && !data && !loading) {
      setLoading(true);
      fetch(`/api/gemini/audit/${ticker}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filingUrl ? { filing_url: filingUrl } : {}),
      })
        .then(r => r.json())
        .then((d: FilingAudit) => {
          setData(d);
          if (!d.error) _auditCache.set(ticker, d);
        })
        .catch(() => setData({
          ticker, filing_url: null, summary: "",
          risk_factors: [], red_flags: [], moat_signals: [],
          model: "", error: "Audit unavailable",
        }))
        .finally(() => setLoading(false));
    }
    setOpen(o => !o);
  }

  return (
    <div style={{
      marginTop: 16, border: "1px solid var(--gv-border)",
      borderRadius: "var(--gv-radius)", overflow: "hidden",
      background: "var(--gv-surface)",
    }}>
      <button
        onClick={toggle}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "10px 16px", background: "var(--gv-data-bg)",
          border: "none", cursor: "pointer", textAlign: "left",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: "0.85em", color: "var(--gv-navy)", display: "flex", alignItems: "center", gap: 8 }}>
          📋 10-K Audit{" "}
          <span style={{ fontWeight: 400, fontSize: "0.85em", color: "var(--gv-text-muted)" }}>powered by Gemini</span>
        </span>
        <span style={{ color: "var(--gv-text-muted)", fontSize: "0.8em" }}>{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div style={{ padding: "16px 20px" }}>
          {loading && (
            <div style={{ color: "var(--gv-text-muted)", fontStyle: "italic", fontSize: "0.85em" }}>
              Analysing filing…
            </div>
          )}

          {data?.error && !loading && (
            <div style={{ color: "var(--gv-red)", fontSize: "0.85em" }}>{data.error}</div>
          )}

          {data && !data.error && !loading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {data.summary && (
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.78em", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--gv-text-dim)", marginBottom: 6 }}>Executive Summary</div>
                  <p style={{ fontSize: "0.85em", lineHeight: 1.65, color: "var(--gv-text)", margin: 0 }}>{data.summary}</p>
                </div>
              )}

              {data.risk_factors.length > 0 && (
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.78em", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--gv-red)", marginBottom: 6 }}>⚠ Key Risk Factors</div>
                  <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
                    {data.risk_factors.map((r, i) => (
                      <li key={i} style={{ fontSize: "0.83em", lineHeight: 1.55, color: "var(--gv-text)" }}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {data.red_flags.length > 0 && (
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.78em", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--gv-yellow-fg)", marginBottom: 6 }}>🚩 Red Flags</div>
                  <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
                    {data.red_flags.map((r, i) => (
                      <li key={i} style={{ fontSize: "0.83em", lineHeight: 1.55, color: "var(--gv-text)" }}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {data.moat_signals.length > 0 && (
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.78em", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--gv-green)", marginBottom: 6 }}>🏰 Moat Signals</div>
                  <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
                    {data.moat_signals.map((r, i) => (
                      <li key={i} style={{ fontSize: "0.83em", lineHeight: 1.55, color: "var(--gv-text)" }}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ fontSize: "0.72em", color: "var(--gv-text-muted)", marginTop: 4 }}>
                Powered by {data.model} · Based on most recent 10-K filing
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
