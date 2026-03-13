import { useState } from "react";
import type { OverviewData } from "../types";

const FONT_MONO = "var(--gv-font-mono)";
const NAVY = "var(--gv-navy)";
const BLUE = "var(--gv-blue)";

interface PortfolioImpactProps {
  ov: OverviewData | null;
}

export default function PortfolioImpact({ ov }: PortfolioImpactProps) {
  const [shares, setShares] = useState<string>("");

  // OverviewData.price is the current price field (see types.ts line 116)
  const priceNow: number | null = ov ? (ov.price ?? null) : null;

  const sharesNum = parseFloat(shares) || 0;
  const positionValue = priceNow != null ? sharesNum * priceNow : null;
  const portfolioImpact = positionValue != null ? (positionValue / 100_000) * 100 : null;

  const fUSD = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fPct = (v: number) => `${v.toFixed(2)}%`;

  return (
    <div style={{ maxWidth: 480, padding: "32px 24px" }}>
      <h3 style={{ fontFamily: FONT_MONO, color: NAVY, marginBottom: 4, fontSize: "1em", fontWeight: 700, letterSpacing: "0.02em" }}>
        Portfolio Impact Calculator
      </h3>
      <p style={{ fontFamily: FONT_MONO, color: "var(--gv-text-muted)", fontSize: "0.78em", marginBottom: 28, lineHeight: 1.5 }}>
        How much of a $100,000 portfolio does this position represent?
      </p>

      {/* Current price display */}
      <div style={{ marginBottom: 20 }}>
        <label style={{ fontFamily: FONT_MONO, fontSize: "0.75em", fontWeight: 600, color: "var(--gv-text-muted)", letterSpacing: "0.05em", textTransform: "uppercase", display: "block", marginBottom: 6 }}>
          Current Price
        </label>
        <div style={{ fontFamily: FONT_MONO, fontSize: "1.4em", fontWeight: 700, color: NAVY }}>
          {priceNow != null ? fUSD(priceNow) : "—"}
        </div>
      </div>

      {/* Shares input */}
      <div style={{ marginBottom: 28 }}>
        <label style={{ fontFamily: FONT_MONO, fontSize: "0.75em", fontWeight: 600, color: "var(--gv-text-muted)", letterSpacing: "0.05em", textTransform: "uppercase", display: "block", marginBottom: 6 }}>
          Shares Owned
        </label>
        <input
          type="number"
          min="0"
          value={shares}
          onChange={(e) => setShares(e.target.value)}
          placeholder="Enter number of shares"
          style={{
            fontFamily: FONT_MONO,
            fontSize: "1em",
            padding: "10px 14px",
            border: `1.5px solid var(--gv-border)`,
            borderRadius: 6,
            width: "100%",
            boxSizing: "border-box",
            outline: "none",
            color: NAVY,
            background: "var(--gv-surface)",
          }}
        />
      </div>

      {/* Results */}
      {sharesNum > 0 && priceNow != null ? (
        <div style={{ background: "var(--gv-bg)", border: `1px solid var(--gv-border)`, borderRadius: 8, padding: "20px 20px", display: "flex", flexDirection: "column", gap: 16 }}>
          <ResultRow label="Position Value" value={fUSD(positionValue!)} />
          <div style={{ height: 1, background: "var(--gv-border)" }} />
          <ResultRow label="% of $100k Portfolio" value={fPct(portfolioImpact!)} accent />
          <PortfolioBar pct={Math.min(portfolioImpact!, 100)} />
        </div>
      ) : null}

      {priceNow == null ? (
        <p style={{ fontFamily: FONT_MONO, fontSize: "0.8em", color: "var(--gv-text-muted)" }}>
          Load a stock first to see the current price.
        </p>
      ) : null}
    </div>
  );
}

function ResultRow({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
      <span style={{ fontFamily: FONT_MONO, fontSize: "0.78em", color: "var(--gv-text-muted)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
        {label}
      </span>
      <span style={{ fontFamily: FONT_MONO, fontSize: accent ? "1.5em" : "1.1em", fontWeight: 700, color: accent ? BLUE : NAVY }}>
        {value}
      </span>
    </div>
  );
}

function PortfolioBar({ pct }: { pct: number }) {
  return (
    <div>
      <div style={{ height: 6, background: "var(--gv-border)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: BLUE, borderRadius: 3, transition: "width 0.3s ease" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
        <span style={{ fontFamily: FONT_MONO, fontSize: "0.68em", color: "var(--gv-text-muted)" }}>0%</span>
        <span style={{ fontFamily: FONT_MONO, fontSize: "0.68em", color: "var(--gv-text-muted)" }}>100%</span>
      </div>
    </div>
  );
}
