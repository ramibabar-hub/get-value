/**
 * InsightsTab.tsx
 * Pure presentational — renders all 7 InsightsAgent groups + WACC section.
 * Data passed in as props (fetched + cached by StockDashboard).
 *
 * Groups: Growth (CAGR) | Valuation Multiples | Profitability |
 *         Returns Analysis | Liquidity | Dividends | Efficiency | WACC
 *
 * Each table row owns its own isExpanded state (multiple rows can be open).
 * MiniChart is React.lazy() loaded — only bundled when a row is first expanded.
 */
import { lazy, memo, useState, Suspense, Fragment } from "react";
import type { InsightsData, InsightsGroup, InsightsRow, WaccData } from "../types";
import { IndustryComparisonCell } from "./IndustryComparisonCell";
import { lookupBenchmark } from "../utils/industryBenchmarks";

// ── Lazy chart import ─────────────────────────────────────────────────────────
// MiniChart.tsx is only fetched from the server when the first row is expanded.

const MiniChart = lazy(() => import("./MiniChart"));

const NAVY = "var(--gv-navy)";

// ── Slide-down keyframes (injected once) ──────────────────────────────────────

const SLIDE_STYLE = `
@keyframes gvInsSlideDown {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.gv-ins-chart-wrap { animation: gvInsSlideDown 0.18s ease forwards; }
`;

// ── Icon helpers ──────────────────────────────────────────────────────────────

function ChartBarIcon() {
  return (
    <svg
      width="13" height="13" viewBox="0 0 13 13" fill="currentColor"
      style={{ display: "block", flexShrink: 0 }}
    >
      <rect x="0"   y="7"   width="3.5" height="6"    rx="0.5" />
      <rect x="4.75" y="3.5" width="3.5" height="9.5"  rx="0.5" />
      <rect x="9.5" y="0.5" width="3.5" height="12.5" rx="0.5" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg
      width="12" height="12" viewBox="0 0 12 12" fill="none"
      style={{ display: "block", flexShrink: 0 }}
    >
      <line x1="2" y1="2" x2="10" y2="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="10" y1="2" x2="2"  y2="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

// ── Chart-type detection ──────────────────────────────────────────────────────
// CAGR / Growth groups → bar chart  (comparing compound rates across periods)
// All other groups     → line chart (trend over time + median reference)

function isBarGroup(group: InsightsGroup): boolean {
  return /cagr|growth/i.test(group.title);
}

// ── Cell formatter ────────────────────────────────────────────────────────────

function fCell(v: number | string | null | undefined, is_pct: boolean): string {
  if (v === null || v === undefined) return "N/A";
  if (typeof v === "string")         return v;
  if (!isFinite(v))                  return "N/A";
  if (is_pct) {
    const pct = v * 100;
    return `${pct.toFixed(1)}%`;
  }
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── MetricRow — owns its own expansion state ──────────────────────────────────
// Each row instance independently tracks whether its chart is shown.
// Multiple rows across any group can be open simultaneously.

interface MetricRowProps {
  row: InsightsRow;
  cols: string[];
  is_pct: boolean;
  isBar: boolean;
  isAlt: boolean;
  totalCols: number; // label col + data cols (+ optional benchmark col)
  showBenchmarkCol: boolean; // whether this group has a Vs. Industry column
}

const MetricRow = memo(function MetricRow({
  row, cols, is_pct, isBar, isAlt, totalCols, showBenchmarkCol,
}: MetricRowProps) {
  // ── Per-row independent expansion state ──────────────────────────────────
  const [isExpanded, setIsExpanded] = useState(false);

  const vals = cols.map(col => row[col] as number | string | null);

  // ── Benchmark lookup (TTM value vs industry avg) ──────────────────────────
  const ttmVal   = cols.includes("TTM") ? row["TTM"] as number | null : null;
  const benchmark = showBenchmarkCol ? lookupBenchmark(row.label) : null;
  const showCell  = benchmark !== null
    && typeof ttmVal === "number"
    && isFinite(ttmVal);

  const tdLabel: React.CSSProperties = {
    padding: "6px 12px",
    border: "1px solid #e5e7eb",
    fontWeight: 600,
    color: NAVY,
    whiteSpace: "nowrap",
  };

  return (
    <Fragment>
      {/* ── Main data row ── */}
      <tr style={{ background: isAlt ? "#f8fafc" : "#fff" }}>
        <td style={tdLabel}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {/* Label text comes FIRST, icon AFTER — per spec */}
            <span>{row.label}</span>

            <button
              onClick={() => setIsExpanded(prev => !prev)}
              title={isExpanded ? "Close chart" : "Show chart"}
              style={{
                background:  isExpanded ? "#eff6ff" : "none",
                border:      isExpanded ? "1px solid #bfdbfe" : "none",
                padding:     2,
                cursor:      "pointer",
                color:       isExpanded ? "#3b82f6" : "var(--gv-text-muted)",
                lineHeight:  0,
                borderRadius: 3,
                flexShrink:  0,
                transition:  "color 0.15s, background 0.15s",
              }}
            >
              {isExpanded ? <XIcon /> : <ChartBarIcon />}
            </button>
          </div>
        </td>

        {cols.map((col) => {
          const raw   = row[col] as number | string | null;
          const text  = fCell(raw, is_pct);
          const isNeg = typeof raw === "number" && raw < 0;
          const isNM  = raw === "N/M";
          return (
            <td
              key={col}
              style={{
                padding: "6px 12px",
                border: "1px solid #e5e7eb",
                textAlign: "right",
                fontVariantNumeric: "tabular-nums",
                fontFamily: "'Courier New', monospace",
                color:     isNM  ? "var(--gv-text-muted)" : isNeg ? "#dc2626" : NAVY,
                fontStyle: isNM  ? "italic"  : "normal",
                fontSize:  isNM  ? "0.92em"  : undefined,
              }}
            >
              {text}
            </td>
          );
        })}

        {/* ── Vs. Industry benchmark cell ── */}
        {showBenchmarkCol && (
          <td style={{
            padding: "4px 8px", border: "1px solid #e5e7eb",
            borderLeft: "2px solid #dbeafe",
            verticalAlign: "middle",
            background: isAlt ? "#f8fafc" : "#fff",
          }}>
            {showCell ? (
              <IndustryComparisonCell
                companyValue={ttmVal as number}
                industryAvg={benchmark!.avg}
                metricName={row.label}
                higherIsBetter={benchmark!.higherIsBetter}
                formatValue={(v) => fCell(v, is_pct)}
              />
            ) : (
              <span style={{ color: "#d1d5db", fontSize: "0.75em", paddingLeft: 4 }}>—</span>
            )}
          </td>
        )}
      </tr>

      {/* ── Expanded chart row (lazy-loaded) ── */}
      {isExpanded && (
        <tr>
          <td
            colSpan={totalCols}
            style={{
              padding:    0,
              border:     "1px solid #e5e7eb",
              borderTop:  "2px solid #3b82f6",
              background: "#f8fafc",
            }}
          >
            <div
              className="gv-ins-chart-wrap"
              style={{
                padding:       "10px 16px 6px",
                height:        156,          // fixed height — fits without breaking table layout
                boxSizing:     "border-box",
                overflow:      "hidden",
              }}
            >
              {/* chart-type badge */}
              <div style={{
                fontSize:      "0.70em",
                fontWeight:    600,
                color:         "var(--gv-text-muted)",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                marginBottom:  4,
              }}>
                {isBar ? "Bar — CAGR by period" : "Trend — with median"}
              </div>

              {/* MiniChart fetched only on first expansion (React.lazy) */}
              <Suspense
                fallback={
                  <div style={{ color: "var(--gv-text-muted)", fontSize: "0.8em", paddingTop: 8 }}>
                    Loading chart…
                  </div>
                }
              >
                <MiniChart cols={cols} vals={vals} isBar={isBar} />
              </Suspense>
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
});

// ── GroupTable — memoized per group ───────────────────────────────────────────

const GroupTable = memo(function GroupTable({ group }: { group: InsightsGroup }) {
  const isBar = isBarGroup(group);

  // Show the Vs. Industry column only for non-CAGR groups that have a TTM column
  // and at least one row with a known benchmark.
  const showBenchmarkCol = !isBar
    && group.cols.includes("TTM")
    && group.rows.some(row => lookupBenchmark(row.label) !== null);

  const totalCols = group.cols.length + 1 + (showBenchmarkCol ? 1 : 0);

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "7px 12px", border: "1px solid #2d3f5a",
    textAlign: "left", fontSize: "0.82em",
  };
  const thRight: React.CSSProperties = { ...thBase, textAlign: "right", minWidth: 100 };

  return (
    <div style={{ marginBottom: 28 }}>
      {/* Keyframes injected once per GroupTable instance */}
      <style>{SLIDE_STYLE}</style>

      {/* Section header */}
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
              {showBenchmarkCol && (
                <th style={{ ...thBase, minWidth: 140, borderLeft: "2px solid #2d4a7a" }}>
                  Vs. Industry
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {group.rows.map((row: InsightsRow, ri: number) => (
              <MetricRow
                key={`${row.label}-${ri}`}
                row={row}
                cols={group.cols}
                is_pct={group.is_pct}
                isBar={isBar}
                isAlt={ri % 2 === 1}
                totalCols={totalCols}
                showBenchmarkCol={showBenchmarkCol}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});

// ── WACC table ────────────────────────────────────────────────────────────────

function fPctW(v: number | null, decimals = 2): string {
  if (v == null || !isFinite(v)) return "N/A";
  return `${(v * 100).toFixed(decimals)}%`;
}

interface WaccRowDef { label: string; value: string; note: string; highlight?: boolean; }

const WaccTable = memo(function WaccTable({ wacc }: { wacc: WaccData }) {
  const rows: WaccRowDef[] = [
    { label: "Risk-Free Rate (Rf)",           value: fPctW(wacc.rf),                     note: "US 10-yr treasury yield (4.2%)" },
    { label: "Beta (β)",                      value: wacc.beta != null ? wacc.beta.toFixed(2) : "N/A", note: "Market risk vs S&P 500" },
    { label: "Cost of Equity (Re)",           value: fPctW(wacc.cost_of_equity),          note: "CAPM: Rf + β × 4.6% ERP" },
    { label: "Interest Coverage Ratio",       value: wacc.int_coverage != null ? wacc.int_coverage.toFixed(2) + "×" : "N/A", note: "EBITDA / Interest expense" },
    { label: "Credit Spread (Damodaran)",     value: fPctW(wacc.spread),                 note: "Lookup from coverage ratio" },
    { label: "Cost of Debt Pre-Tax (Rd)",     value: fPctW(wacc.cost_of_debt_pre_tax),   note: "Rf + Spread" },
    { label: "Effective Tax Rate",            value: fPctW(wacc.tax_rate),                note: "Capped at 50%" },
    { label: "Cost of Debt After-Tax",        value: fPctW(wacc.cost_of_debt_after_tax),  note: "Rd × (1 − Tax rate)" },
    { label: "Equity Weight (E/TC)",          value: fPctW(wacc.equity_weight),           note: "Mkt cap / (Mkt cap + Debt)" },
    { label: "Debt Weight (D/TC)",            value: fPctW(wacc.debt_weight),             note: "Total debt / (Mkt cap + Debt)" },
    { label: "Computed WACC",                 value: fPctW(wacc.wacc),                    note: "E/TC × Re + D/TC × Rd(at)", highlight: true },
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
                  color: "var(--gv-text-muted)", fontStyle: "italic", fontSize: "0.92em",
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

// ── WACC manual selector ──────────────────────────────────────────────────────

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
        <span style={{ fontSize: "0.78em", fontWeight: 500, color: "var(--gv-text-muted)", marginLeft: 10 }}>
          — applies to Valuations tab when "Use WACC" is checked
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>
            WACC: <span style={{ color: "#b45309", fontWeight: 700 }}>{manualWacc.toFixed(1)}%</span>
            {computed != null && (
              <span style={{ color: "var(--gv-text-muted)", fontWeight: 400, marginLeft: 8 }}>
                (computed: {computed.toFixed(2)}%)
              </span>
            )}
          </div>
          <input
            type="range" min={1} max={30} step={0.1} value={manualWacc}
            onChange={(e) => onChange(Number(e.target.value))}
            style={{ accentColor: "#f59e0b", width: "100%", cursor: "pointer" }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68em", color: "var(--gv-text-muted)" }}>
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
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "var(--gv-text-muted)" }}>
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

// ── Main export ───────────────────────────────────────────────────────────────

interface Props {
  data: InsightsData | null;
  loading: boolean;
  error: string | null;
  waccData: WaccData | null;
  manualWacc: number;
  onWaccChange: (v: number) => void;
}

export default function InsightsTab({
  data, loading, error, waccData, manualWacc, onWaccChange,
}: Props) {
  if (loading) return <Spinner />;

  if (error) {
    return (
      <div style={{
        background: "var(--gv-red-bg)", border: "1px solid #fca5a5",
        borderRadius: 8, padding: "12px 16px", color: "var(--gv-red)",
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
      {waccData ? (
        <>
          <WaccTable wacc={waccData} />
          <WaccSelector
            computedWacc={waccData.wacc}
            manualWacc={manualWacc}
            onChange={onWaccChange}
          />
        </>
      ) : null}
    </div>
  );
}
