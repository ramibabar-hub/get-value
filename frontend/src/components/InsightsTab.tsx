/**
 * InsightsTab.tsx
 * Pure presentational — renders all 7 InsightsAgent groups + WACC section.
 * Data passed in as props (fetched + cached by StockDashboard).
 *
 * Groups: Growth (CAGR) | Valuation Multiples | Profitability |
 *         Returns Analysis | Liquidity | Dividends | Efficiency | WACC
 */
import { memo, useState, Fragment } from "react";
import type { InsightsData, InsightsGroup, InsightsRow, WaccData } from "../types";

const NAVY = "#1c2b46";

// ── Chart helpers ─────────────────────────────────────────────────────────────

const CHART_NAVY = "#1c2b46";

function ChartIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor" style={{ display: "block", flexShrink: 0 }}>
      <rect x="0" y="7" width="3.5" height="6" rx="0.5"/>
      <rect x="4.75" y="3.5" width="3.5" height="9.5" rx="0.5"/>
      <rect x="9.5" y="0.5" width="3.5" height="12.5" rx="0.5"/>
    </svg>
  );
}

function MiniChart({
  cols, vals, isBar,
}: {
  cols: string[];
  vals: (number | null | string)[];
  isBar: boolean;
}) {
  const nums = vals.map(v => (typeof v === "number" && isFinite(v)) ? v : null);
  const nonNull = nums.filter((v): v is number => v !== null);
  if (nonNull.length === 0) {
    return <div style={{ padding: "12px 16px", color: "#9ca3af", fontSize: "0.8em" }}>No chart data</div>;
  }

  const N   = cols.length;
  const VW  = Math.max(N * 55, 280);
  const VH  = 110;
  const PL = 4, PR = 4, PT = 10, PB = 26;
  const cW  = VW - PL - PR;
  const cH  = VH - PT - PB;

  const rawMin = Math.min(...nonNull);
  const rawMax = Math.max(...nonNull);
  const vMin   = Math.min(0, rawMin);
  const vMaxRaw = Math.max(0, rawMax);
  const vMax   = vMaxRaw === vMin ? vMin + 1 : vMaxRaw;
  const range  = vMax - vMin;

  const toY   = (v: number) => PT + cH - ((v - vMin) / range) * cH;
  const zeroY = toY(0);
  const bW    = cW / N;
  const colX  = (i: number) => PL + i * bW;
  const shortLbl = (c: string) => c === "TTM" ? "TTM" : c.length > 4 ? c.slice(-4) : c;

  if (isBar) {
    return (
      <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
        <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="#e5e7eb" strokeWidth="1"/>
        {nums.map((v, i) => {
          if (v === null) return null;
          const isTtm = cols[i] === "TTM";
          const x    = colX(i) + bW * 0.1;
          const w    = bW * 0.8;
          const top  = v >= 0 ? toY(v) : zeroY;
          const h    = Math.max(Math.abs(toY(v) - zeroY), 1);
          const fill = isTtm ? "#3b82f6" : v < 0 ? "#ef4444" : CHART_NAVY;
          return (
            <g key={i}>
              <rect x={x} y={top} width={w} height={h} fill={fill} opacity={isTtm ? 1 : 0.72}/>
              <text x={x + w / 2} y={VH - 4} textAnchor="middle" fontSize="8" fill="#9ca3af">{shortLbl(cols[i])}</text>
            </g>
          );
        })}
      </svg>
    );
  }

  const pts = nums
    .map((v, i) => v !== null ? { x: PL + (i + 0.5) * bW, y: toY(v), col: cols[i] } : null)
    .filter(Boolean) as { x: number; y: number; col: string }[];
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
      <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="#e5e7eb" strokeWidth="1"/>
      {d && <path d={d} fill="none" stroke={CHART_NAVY} strokeWidth="1.5" opacity="0.7"/>}
      {pts.map((p, i) => {
        const isTtm = p.col === "TTM";
        return (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={isTtm ? 4 : 2.5} fill={isTtm ? "#3b82f6" : CHART_NAVY}/>
            <text x={p.x} y={VH - 4} textAnchor="middle" fontSize="8" fill="#9ca3af">{shortLbl(p.col)}</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Cell formatter ────────────────────────────────────────────────────────────

function fCell(v: number | string | null | undefined, is_pct: boolean): string {
  if (v === null || v === undefined) return "N/A";
  if (typeof v === "string")         return v;
  if (!isFinite(v))                  return "N/A";
  if (is_pct) {
    const pct = v * 100;
    return `${pct >= 0 ? "" : ""}${pct.toFixed(1)}%`;
  }
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Memoized group table ──────────────────────────────────────────────────────

const GroupTable = memo(function GroupTable({ group }: { group: InsightsGroup }) {
  const [openRow, setOpenRow] = useState<number | null>(null);

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "7px 12px", border: "1px solid #2d3f5a",
    textAlign: "left", fontSize: "0.82em",
  };
  const thRight: React.CSSProperties = { ...thBase, textAlign: "right", minWidth: 100 };

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{
        fontSize: "1.05em", fontWeight: "bold", color: "#fff",
        background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6,
      }}>
        {group.title}
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
          <thead>
            <tr>
              <th style={{ ...thBase, minWidth: 220 }}>Metric</th>
              {group.cols.map((col) => (
                <th key={col} style={thRight}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {group.rows.map((row: InsightsRow, ri: number) => {
              const isAlt  = ri % 2 === 1;
              const isOpen = openRow === ri;
              const vals   = group.cols.map(col => row[col] as number | string | null);
              return (
                <Fragment key={ri}>
                  <tr style={{ background: isAlt ? "#f8fafc" : "#fff" }}>
                    <td style={{
                      padding: "6px 12px", border: "1px solid #e5e7eb",
                      fontWeight: 600, color: NAVY, whiteSpace: "nowrap",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          onClick={() => setOpenRow(isOpen ? null : ri)}
                          title="Toggle chart"
                          style={{
                            background: "none", border: "none", padding: 2, cursor: "pointer",
                            color: isOpen ? "#3b82f6" : "#9ca3af", lineHeight: 0,
                            borderRadius: 3, flexShrink: 0,
                          }}
                        >
                          <ChartIcon />
                        </button>
                        {row.label}
                      </div>
                    </td>
                    {group.cols.map((col) => {
                      const raw = row[col] as number | string | null;
                      const text = fCell(raw, group.is_pct);
                      const isNeg = typeof raw === "number" && raw < 0;
                      const isNM  = raw === "N/M";
                      return (
                        <td key={col} style={{
                          padding: "6px 12px", border: "1px solid #e5e7eb",
                          textAlign: "right",
                          fontVariantNumeric: "tabular-nums",
                          fontFamily: "'Courier New', monospace",
                          color: isNM ? "#9ca3af" : isNeg ? "#dc2626" : NAVY,
                          fontStyle: isNM ? "italic" : "normal",
                          fontSize: isNM ? "0.92em" : undefined,
                        }}>
                          {text}
                        </td>
                      );
                    })}
                  </tr>
                  {isOpen && (
                    <tr>
                      <td colSpan={group.cols.length + 1} style={{ padding: "8px 16px", border: "1px solid #e5e7eb", background: "#f8fafc" }}>
                        <MiniChart cols={group.cols} vals={vals} isBar={!group.is_pct} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
});

// ── WACC components table ─────────────────────────────────────────────────────

function fPctW(v: number | null, decimals = 2): string {
  if (v == null || !isFinite(v)) return "N/A";
  return `${(v * 100).toFixed(decimals)}%`;
}

interface WaccRow { label: string; value: string; note: string; highlight?: boolean; }

const WaccTable = memo(function WaccTable({ wacc }: { wacc: WaccData }) {
  const rows: WaccRow[] = [
    { label: "Risk-Free Rate (Rf)",           value: fPctW(wacc.rf),                    note: "US 10-yr treasury yield (4.2%)" },
    { label: "Beta (β)",                      value: wacc.beta != null ? wacc.beta.toFixed(2) : "N/A", note: "Market risk vs S&P 500" },
    { label: "Cost of Equity (Re)",           value: fPctW(wacc.cost_of_equity),         note: "CAPM: Rf + β × 4.6% ERP" },
    { label: "Interest Coverage Ratio",       value: wacc.int_coverage != null ? wacc.int_coverage.toFixed(2) + "×" : "N/A", note: "EBITDA / Interest expense" },
    { label: "Credit Spread (Damodaran)",     value: fPctW(wacc.spread),                note: "Lookup from coverage ratio" },
    { label: "Cost of Debt Pre-Tax (Rd)",     value: fPctW(wacc.cost_of_debt_pre_tax),  note: "Rf + Spread" },
    { label: "Effective Tax Rate",            value: fPctW(wacc.tax_rate),               note: "Capped at 50%" },
    { label: "Cost of Debt After-Tax",        value: fPctW(wacc.cost_of_debt_after_tax), note: "Rd × (1 − Tax rate)" },
    { label: "Equity Weight (E/TC)",          value: fPctW(wacc.equity_weight),          note: "Mkt cap / (Mkt cap + Debt)" },
    { label: "Debt Weight (D/TC)",            value: fPctW(wacc.debt_weight),            note: "Total debt / (Mkt cap + Debt)" },
    { label: "Computed WACC",                 value: fPctW(wacc.wacc),                   note: "E/TC × Re + D/TC × Rd(at)", highlight: true },
  ];

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "7px 12px", border: "1px solid #2d3f5a", textAlign: "left", fontSize: "0.82em",
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontSize: "1.05em", fontWeight: "bold", color: "#fff",
        background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6,
      }}>
        WACC  ·  Weighted Average Cost of Capital
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
          <thead>
            <tr>
              <th style={{ ...thBase, minWidth: 240 }}>Component</th>
              <th style={{ ...thBase, textAlign: "right", minWidth: 90 }}>Value</th>
              <th style={{ ...thBase, minWidth: 220 }}>Note</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{
                background: r.highlight ? "#dbeafe" : i % 2 === 1 ? "#f8fafc" : "#fff",
              }}>
                <td style={{
                  padding: "6px 12px", border: "1px solid #e5e7eb",
                  fontWeight: r.highlight ? 700 : 600, color: NAVY,
                }}>
                  {r.label}
                </td>
                <td style={{
                  padding: "6px 12px", border: "1px solid #e5e7eb",
                  textAlign: "right", fontVariantNumeric: "tabular-nums",
                  fontFamily: "'Courier New', monospace",
                  color: r.highlight ? "#1d4ed8" : NAVY, fontWeight: r.highlight ? 700 : 400,
                }}>
                  {r.value}
                </td>
                <td style={{
                  padding: "6px 12px", border: "1px solid #e5e7eb",
                  color: "#6b7280", fontStyle: "italic", fontSize: "0.92em",
                }}>
                  {r.note}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});

// ── Manual WACC selector ──────────────────────────────────────────────────────

function WaccSelector({ computedWacc, manualWacc, onChange }: {
  computedWacc: number | null;
  manualWacc: number;
  onChange: (v: number) => void;
}) {
  const computed = computedWacc != null ? parseFloat((computedWacc * 100).toFixed(2)) : null;

  return (
    <div style={{
      background: "#fffbeb", border: "1.5px solid #fde68a", borderRadius: 8,
      padding: "16px 20px", marginBottom: 28,
    }}>
      <div style={{ fontSize: "0.97em", fontWeight: 700, color: NAVY, marginBottom: 10 }}>
        Manual WACC Override
        <span style={{ fontSize: "0.78em", fontWeight: 500, color: "#6b7280", marginLeft: 10 }}>
          — applies to Valuations tab when "Use WACC" is checked
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>
            WACC: <span style={{ color: "#b45309", fontWeight: 700 }}>{manualWacc.toFixed(1)}%</span>
            {computed != null && (
              <span style={{ color: "#6b7280", fontWeight: 400, marginLeft: 8 }}>
                (computed: {computed.toFixed(2)}%)
              </span>
            )}
          </div>
          <input
            type="range" min={1} max={30} step={0.1} value={manualWacc}
            onChange={(e) => onChange(Number(e.target.value))}
            style={{ accentColor: "#f59e0b", width: "100%", cursor: "pointer" }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68em", color: "#9ca3af" }}>
            <span>1%</span><span>30%</span>
          </div>
        </div>
        {computed != null && (
          <button
            onClick={() => onChange(computed)}
            style={{
              padding: "6px 14px", background: NAVY, color: "#fff", border: "none",
              borderRadius: 5, fontWeight: 600, fontSize: "0.82em", cursor: "pointer",
              fontFamily: "inherit", whiteSpace: "nowrap",
            }}
          >
            Reset to {computed.toFixed(2)}%
          </button>
        )}
      </div>
    </div>
  );
}

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "#6b7280" }}>
      <div style={{
        width: 28, height: 28, borderRadius: "50%",
        border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`,
        animation: "gvInsSpin 0.75s linear infinite", flexShrink: 0,
      }} />
      <span style={{ fontSize: "0.88em" }}>Computing insights…</span>
      <style>{`@keyframes gvInsSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  data: InsightsData | null;
  loading: boolean;
  error: string | null;
  waccData: WaccData | null;
  manualWacc: number;
  onWaccChange: (v: number) => void;
}

export default function InsightsTab({ data, loading, error, waccData, manualWacc, onWaccChange }: Props) {
  if (loading) return <Spinner />;

  if (error) {
    return (
      <div style={{
        background: "#fee2e2", border: "1px solid #fca5a5",
        borderRadius: 8, padding: "12px 16px", color: "#991b1b",
      }}>
        <strong>Error loading insights:</strong> {error}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div>
      {data.groups.map((group) => (
        <GroupTable key={group.title} group={group} />
      ))}
      {waccData && (
        <>
          <WaccTable wacc={waccData} />
          <WaccSelector
            computedWacc={waccData.wacc}
            manualWacc={manualWacc}
            onChange={onWaccChange}
          />
        </>
      )}
    </div>
  );
}
