/**
 * InsightsTab.tsx
 * Pure presentational — renders all 7 InsightsAgent groups + WACC section.
 * Data passed in as props (fetched + cached by StockDashboard).
 *
 * Groups: Growth (CAGR) | Valuation Multiples | Profitability |
 *         Returns Analysis | Liquidity | Dividends | Efficiency | WACC
 */
import { memo } from "react";
import type { InsightsData, InsightsGroup, InsightsRow, WaccData } from "../types";

const NAVY = "#1c2b46";

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
              const isAlt = ri % 2 === 1;
              return (
                <tr key={ri} style={{ background: isAlt ? "#f8fafc" : "#fff" }}>
                  <td style={{
                    padding: "6px 12px", border: "1px solid #e5e7eb",
                    fontWeight: 600, color: NAVY, whiteSpace: "nowrap",
                  }}>
                    {row.label}
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
