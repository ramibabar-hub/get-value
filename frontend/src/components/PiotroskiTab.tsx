/**
 * PiotroskiTab.tsx
 * Piotroski F-Score (9-point) valuation model.
 *
 * Three groups: Profitability (F1-F4) · Leverage & Liquidity (F5-F7) · Operating Efficiency (F8-F9)
 * Score colours: ≥7 green · 4-6 yellow · ≤3 red
 */
import { useState, useEffect, memo } from "react";
import type { PiotroskiData } from "../types";

// ── Palette (matches CfIrrTab / project-wide palette) ─────────────────────────
const NAVY      = "var(--gv-navy)";
const CLR_PASS  = "var(--gv-green-bg)"; const CLR_PASS_FG = "var(--gv-green)";
const CLR_FAIL  = "var(--gv-red-bg)"; const CLR_FAIL_FG = "var(--gv-red)";
const CLR_NA    = "var(--gv-data-bg)"; const CLR_NA_FG   = "var(--gv-text-muted)";

const MONO: React.CSSProperties = {
  fontFamily: "'Courier New', monospace",
  fontVariantNumeric: "tabular-nums",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fPct(v: number | null, dp = 1): string {
  if (v == null) return "N/A";
  return `${v.toFixed(dp)}%`;
}
function fRatio(v: number | null, dp = 2): string {
  if (v == null) return "N/A";
  return v.toFixed(dp);
}
function fBig(v: number | null): string {
  if (v == null) return "N/A";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`;
  return `${sign}$${abs.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: "1.05em", fontWeight: "bold", color: "#fff",
      background: NAVY, padding: "6px 15px", borderRadius: 4,
      marginTop: 24, marginBottom: 0,
    }}>
      {title}
    </div>
  );
}

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 48 }}>
      <div style={{
        width: 32, height: 32,
        border: `3px solid ${NAVY}22`, borderTopColor: NAVY,
        borderRadius: "50%", animation: "piot-spin 0.8s linear infinite",
      }} />
      <style>{`@keyframes piot-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ScoreCard({ score }: { score: number }) {
  const pct  = Math.round((score / 9) * 100);
  const high = score >= 7;
  const mid  = score >= 4 && score < 7;

  const bg    = high ? "var(--gv-green-bg)" : mid ? "var(--gv-yellow-bg)" : "var(--gv-red-bg)";
  const fg    = high ? "var(--gv-green)" : mid ? "#92400e" : "var(--gv-red)";
  const bar   = high ? "#10b981" : mid ? "#f59e0b" : "#ef4444";
  const label = high ? "Strong financial health" : mid ? "Moderate financial health" : "Weak financial health";

  return (
    <div style={{
      background: bg, border: `1.5px solid ${bar}`, borderRadius: 12,
      padding: "20px 28px", marginBottom: 24,
      display: "flex", alignItems: "center", gap: 24,
    }}>
      {/* Big score number */}
      <div style={{ textAlign: "center", flexShrink: 0 }}>
        <div style={{ fontSize: "3em", fontWeight: 900, color: fg, lineHeight: 1, ...MONO }}>
          {score}
        </div>
        <div style={{ fontSize: "0.75em", color: fg, fontWeight: 600, marginTop: 2 }}>out of 9</div>
      </div>

      {/* Bar + label */}
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: "1.15em", fontWeight: 700, color: fg, marginBottom: 8 }}>
          F-Score: {score}/9 &nbsp;·&nbsp; {pct}%
        </div>
        {/* Progress bar */}
        <div style={{ height: 10, background: `${bar}33`, borderRadius: 5, overflow: "hidden" }}>
          <div style={{
            height: "100%", width: `${pct}%`,
            background: bar, borderRadius: 5, transition: "width 0.5s ease",
          }} />
        </div>
        <div style={{ fontSize: "0.82em", color: fg, marginTop: 6, fontWeight: 500 }}>
          {label}
          {score >= 8 && " — high quality value candidate"}
          {score <= 2 && " — potential short or avoid"}
        </div>
        {/* Score pip row */}
        <div style={{ display: "flex", gap: 5, marginTop: 10 }}>
          {Array.from({ length: 9 }, (_, i) => (
            <div key={i} style={{
              width: 22, height: 22, borderRadius: "50%",
              background: i < score ? bar : `${bar}33`,
              border: `2px solid ${bar}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "0.6em", fontWeight: 700, color: i < score ? "#fff" : fg,
              ...MONO,
            }}>
              {i + 1}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface CriterionRowProps {
  label:       string;
  condition:   string;
  tooltip:     string;
  ttmVal:      string;
  prevVal:     string;
  score:       number;
}

const CriterionRow = memo(function CriterionRow({
  label, condition, tooltip, ttmVal, prevVal, score,
}: CriterionRowProps) {
  const passed  = score === 1;
  const isNA    = ttmVal === "N/A" || prevVal === "N/A";
  const badgeBg = isNA ? CLR_NA    : passed ? CLR_PASS    : CLR_FAIL;
  const badgeFg = isNA ? CLR_NA_FG : passed ? CLR_PASS_FG : CLR_FAIL_FG;

  return (
    <tr style={{ borderBottom: "1px solid #f0f2f5" }}>
      {/* Criterion name + tooltip */}
      <td style={{ padding: "9px 14px", fontSize: "0.88em", color: NAVY, fontWeight: 600, whiteSpace: "nowrap" }}>
        <span title={tooltip} style={{ cursor: "help", borderBottom: "1px dotted #9ca3af" }}>
          {label}
        </span>
        <span style={{ fontSize: "0.75em", color: "var(--gv-text-muted)", marginLeft: 4 }}>ⓘ</span>
      </td>
      {/* Condition logic */}
      <td style={{ padding: "9px 14px", fontSize: "0.78em", color: "var(--gv-text-muted)", ...MONO, whiteSpace: "nowrap" }}>
        {condition}
      </td>
      {/* TTM value */}
      <td style={{ padding: "9px 14px", fontSize: "0.88em", textAlign: "right", ...MONO, color: NAVY }}>
        {ttmVal}
      </td>
      {/* PREV TTM value */}
      <td style={{ padding: "9px 14px", fontSize: "0.88em", textAlign: "right", ...MONO, color: "var(--gv-text-muted)" }}>
        {prevVal}
      </td>
      {/* Pass/Fail badge */}
      <td style={{ padding: "9px 14px", textAlign: "center" }}>
        <span style={{
          background: badgeBg, color: badgeFg,
          fontSize: "0.72em", fontWeight: 700, letterSpacing: "0.05em",
          padding: "3px 10px", borderRadius: 20,
        }}>
          {isNA ? "N/A" : passed ? "✓ Pass" : "✗ Fail"}
        </span>
      </td>
    </tr>
  );
});

// ── Score criteria table ───────────────────────────────────────────────────────

interface CriteriaTableProps {
  rows: CriterionRowProps[];
}

const CriteriaTable = memo(function CriteriaTable({ rows }: CriteriaTableProps) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9em" }}>
      <thead>
        <tr style={{ background: "#f8f9fb", borderBottom: "2px solid #e5e7eb" }}>
          <th style={{ padding: "7px 14px", textAlign: "left",   fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>Criterion</th>
          <th style={{ padding: "7px 14px", textAlign: "left",   fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>Test Logic</th>
          <th style={{ padding: "7px 14px", textAlign: "right",  fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>TTM</th>
          <th style={{ padding: "7px 14px", textAlign: "right",  fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>Prev TTM</th>
          <th style={{ padding: "7px 14px", textAlign: "center", fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>Score</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => <CriterionRow key={r.label} {...r} />)}
      </tbody>
    </table>
  );
});

// ── Main component ────────────────────────────────────────────────────────────

interface PiotroskiTabProps {
  ticker: string;
}

export default function PiotroskiTab({ ticker }: PiotroskiTabProps) {
  const [data,    setData]    = useState<PiotroskiData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    setData(null);

    const ctrl = new AbortController();
    fetch(`/api/piotroski/${encodeURIComponent(ticker)}`, { signal: ctrl.signal })
      .then(r => {
        if (!r.ok) return r.json().then(b => Promise.reject(b.detail ?? "Failed"));
        return r.json();
      })
      .then((d: PiotroskiData) => setData(d))
      .catch(e => { if (e?.name !== "AbortError") setError(String(e)); })
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [ticker]);

  if (loading) return <Spinner />;
  if (error)   return <div style={{ color: "#ef4444", padding: 24, fontSize: "0.9em" }}>Error: {error}</div>;
  if (!data)   return null;

  const d = data;

  // ── Build row definitions ─────────────────────────────────────────────────

  const profitRows: CriterionRowProps[] = [
    {
      label:     "Positive ROA",
      condition: "ROA (TTM) > 0",
      tooltip:   "Net income divided by total assets at the beginning of the year. Score 1 if positive, 0 if negative.",
      ttmVal:    fPct(d.roa_ttm),
      prevVal:   fPct(d.roa_prev),
      score:     d.f1_positive_roa,
    },
    {
      label:     "Positive OCF/Assets",
      condition: "OCF / Assets (TTM) > 0",
      tooltip:   "Operating cash flow divided by total assets at the beginning of the year. Score 1 if positive, 0 if negative.",
      ttmVal:    fPct(d.ocf_ratio_ttm),
      prevVal:   fPct(d.ocf_ratio_prev),
      score:     d.f2_positive_ocf,
    },
    {
      label:     "Higher ROA YoY",
      condition: "ROA (TTM) > ROA (Prev)",
      tooltip:   "Compare this year's return on assets to last year's return on assets. Score 1 if it's higher, 0 if lower.",
      ttmVal:    fPct(d.roa_ttm),
      prevVal:   fPct(d.roa_prev),
      score:     d.f3_higher_roa,
    },
    {
      label:     "Accruals (OCF > ROA)",
      condition: "OCF/Assets > ROA",
      tooltip:   "Compare cash flow return on assets to ROA. Score 1 if OCF/Assets > ROA — signals earnings are backed by real cash, not accruals.",
      ttmVal:    `OCF: ${fPct(d.ocf_ratio_ttm)}`,
      prevVal:   `ROA: ${fPct(d.roa_ttm)}`,
      score:     d.f4_accruals,
    },
  ];

  const leverageRows: CriterionRowProps[] = [
    {
      label:     "Lower Leverage YoY",
      condition: "LT Debt/Assets (TTM) < Prev",
      tooltip:   "Compare this year's leverage (long-term debt divided by total assets) to last year's. Score 1 if gearing is lower, 0 if higher.",
      ttmVal:    fPct(d.leverage_ttm),
      prevVal:   fPct(d.leverage_prev),
      score:     d.f5_lower_leverage,
    },
    {
      label:     "Higher Current Ratio YoY",
      condition: "Current Ratio (TTM) > Prev",
      tooltip:   "Compare this year's current ratio (current assets ÷ current liabilities) to last year's. Score 1 if this year's is higher.",
      ttmVal:    fRatio(d.current_ratio_ttm),
      prevVal:   fRatio(d.current_ratio_prev),
      score:     d.f6_higher_current_ratio,
    },
    {
      label:     "No Share Dilution YoY",
      condition: "Shares (TTM) ≤ Shares (Prev)",
      tooltip:   "Compare shares outstanding this year to last year. Score 1 if shares are the same or fewer (no dilution), 0 if more shares were issued.",
      ttmVal:    fBig(d.shares_ttm),
      prevVal:   fBig(d.shares_prev),
      score:     d.f7_less_shares,
    },
  ];

  const efficiencyRows: CriterionRowProps[] = [
    {
      label:     "Higher Gross Margin YoY",
      condition: "Gross Margin (TTM) > Prev",
      tooltip:   "Compare this year's gross margin (gross profit ÷ revenue) to last year's. Score 1 if this year's gross margin is higher.",
      ttmVal:    fPct(d.gross_margin_ttm),
      prevVal:   fPct(d.gross_margin_prev),
      score:     d.f8_higher_gross_margin,
    },
    {
      label:     "Higher Asset Turnover YoY",
      condition: "Asset Turnover (TTM) > Prev",
      tooltip:   "Compare this year's asset turnover (revenue ÷ beginning assets) to last year's. Score 1 if this year's ratio is higher — signals improving operational efficiency.",
      ttmVal:    fRatio(d.asset_turnover_ttm),
      prevVal:   fRatio(d.asset_turnover_prev),
      score:     d.f9_higher_asset_turnover,
    },
  ];

  const groupScore = (rows: CriterionRowProps[]) =>
    rows.reduce((s, r) => s + r.score, 0);

  return (
    <div style={{ paddingTop: 16 }}>

      {/* ── Score Card ── */}
      <ScoreCard score={d.total_score} />

      {/* ── Profitability ── */}
      <SecHeader title={`Profitability  ·  ${groupScore(profitRows)}/4`} />
      <CriteriaTable rows={profitRows} />

      {/* ── Leverage & Liquidity ── */}
      <SecHeader title={`Leverage & Liquidity  ·  ${groupScore(leverageRows)}/3`} />
      <CriteriaTable rows={leverageRows} />

      {/* ── Operating Efficiency ── */}
      <SecHeader title={`Operating Efficiency  ·  ${groupScore(efficiencyRows)}/2`} />
      <CriteriaTable rows={efficiencyRows} />

      {/* ── Legend ── */}
      <div style={{
        marginTop: 20, padding: "10px 16px",
        background: "#f8f9fb", borderRadius: 8, fontSize: "0.76em", color: "var(--gv-text-muted)",
        display: "flex", flexWrap: "wrap", gap: "6px 20px",
      }}>
        <span><strong style={{ color: NAVY }}>TTM</strong> = trailing twelve months (sum of last 4 quarters)</span>
        <span><strong style={{ color: NAVY }}>Prev TTM</strong> = same window one year prior</span>
        <span><strong style={{ color: NAVY }}>Assets denominator</strong> = beginning-of-period total assets</span>
        <span>Hover <strong>ⓘ</strong> criterion labels for full descriptions</span>
      </div>
    </div>
  );
}
