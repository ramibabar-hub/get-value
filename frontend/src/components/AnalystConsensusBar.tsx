/**
 * AnalystConsensusBar.tsx
 *
 * Compact Buy/Hold/Sell bar + price target display for the Overview tab.
 * Data comes from /api/analyst/{ticker} (FMP analyst-estimates).
 */
import { useEffect, useState } from "react";
import type { AnalystConsensus } from "../types";

const NAVY = "var(--gv-navy)";

const CONSENSUS_STYLE: Record<string, { bg: string; fg: string }> = {
  Buy:   { bg: "var(--gv-green-bg)",  fg: "var(--gv-green)" },
  Hold:  { bg: "var(--gv-yellow-bg)", fg: "var(--gv-yellow-fg)" },
  Sell:  { bg: "var(--gv-red-bg)",    fg: "var(--gv-red)" },
  "N/A": { bg: "var(--gv-data-bg)",   fg: "var(--gv-text-muted)" },
};

interface Props {
  ticker: string;
}

export default function AnalystConsensusBar({ ticker }: Props) {
  const [data, setData]       = useState<AnalystConsensus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setData(null);
    setLoading(true);
    const ctrl = new AbortController();
    fetch(`/api/analyst/${ticker}`, { signal: ctrl.signal })
      .then((r) => r.json())
      .then((d: AnalystConsensus) => setData(d))
      .catch(() => { /* silently ignore */ })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [ticker]);

  if (loading) {
    return (
      <div
        style={{
          height: 36,
          width: 200,
          background: "var(--gv-data-bg)",
          borderRadius: 6,
          animation: "pulse 1.4s infinite",
        }}
      />
    );
  }

  if (!data || data.consensus === "N/A" || data.num_analysts === 0) {
    return null; // render nothing if no data
  }

  const {
    buy, hold, sell, num_analysts, consensus,
    price_target_avg, price_target_low, price_target_high,
  } = data;
  const cs = CONSENSUS_STYLE[consensus] ?? CONSENSUS_STYLE["N/A"];

  const buyPct  = num_analysts > 0 ? (buy  / num_analysts) * 100 : 0;
  const holdPct = num_analysts > 0 ? (hold / num_analysts) * 100 : 0;
  const sellPct = num_analysts > 0 ? (sell / num_analysts) * 100 : 0;

  const fUSD = (v: number | null) =>
    v != null ? `$${v.toFixed(2)}` : null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "10px 14px",
        background: "var(--gv-bg)",
        border: "1px solid var(--gv-border)",
        borderRadius: 8,
        minWidth: 220,
      }}
    >
      {/* Consensus badge + analyst count */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontWeight: 700,
            fontSize: "0.78em",
            padding: "2px 10px",
            borderRadius: 20,
            background: cs.bg,
            color: cs.fg,
          }}
        >
          {consensus}
        </span>
        <span style={{ fontSize: "0.73em", color: "var(--gv-text-muted)" }}>
          {num_analysts} analyst{num_analysts !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Buy/Hold/Sell bar */}
      <div
        style={{
          display: "flex",
          height: 6,
          borderRadius: 3,
          overflow: "hidden",
          gap: 1,
        }}
      >
        {buyPct > 0  ? <div style={{ flex: buyPct,  background: "var(--gv-green)" }} /> : null}
        {holdPct > 0 ? <div style={{ flex: holdPct, background: "var(--gv-yellow-fg)" }} /> : null}
        {sellPct > 0 ? <div style={{ flex: sellPct, background: "var(--gv-red)" }} /> : null}
      </div>

      {/* Bar labels */}
      <div style={{ display: "flex", gap: 12, fontSize: "0.7em" }}>
        <span style={{ color: "var(--gv-green)" }}>▲ {buy} Buy</span>
        <span style={{ color: "var(--gv-yellow-fg)" }}>● {hold} Hold</span>
        <span style={{ color: "var(--gv-red)" }}>▼ {sell} Sell</span>
      </div>

      {/* Price target */}
      {price_target_avg != null ? (
        <div
          style={{
            borderTop: "1px solid var(--gv-border)",
            paddingTop: 8,
            fontSize: "0.75em",
          }}
        >
          <span style={{ color: "var(--gv-text-muted)" }}>Price Target: </span>
          <span style={{ fontWeight: 700, color: NAVY }}>{fUSD(price_target_avg)}</span>
          {price_target_low != null && price_target_high != null ? (
            <span style={{ color: "var(--gv-text-muted)", marginLeft: 6 }}>
              ({fUSD(price_target_low)} – {fUSD(price_target_high)})
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
