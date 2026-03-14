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
import { memo, useState } from "react";
import type { InsightsData, InsightsGroup, InsightsRow, WaccData } from "../types";
import { IndustryComparisonCell } from "./IndustryComparisonCell";
import { lookupBenchmark } from "../utils/industryBenchmarks";
import MetricsCatalogModal from "./MetricsCatalogModal";
import InsightsGraphsView from "./InsightsGraphsView";
import TableRowCustomizer from "./TableRowCustomizer";
import { useLayoutStore } from "../store/layoutStore";

const NAVY = "var(--gv-navy)";

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

interface MetricRowProps {
  row: InsightsRow;
  cols: string[];
  is_pct: boolean;
  isAlt: boolean;
  showBenchmarkCol: boolean;
}

const MetricRow = memo(function MetricRow({
  row, cols, is_pct, isAlt, showBenchmarkCol,
}: MetricRowProps) {
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
    <tr style={{ background: isAlt ? "#f8fafc" : "#fff" }}>
        <td style={tdLabel}>
          <span>{row.label}</span>
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
  );
});

// ── GroupTable — memoized per group ───────────────────────────────────────────

const GroupTable = memo(function GroupTable({ group }: { group: InsightsGroup }) {
  const isBar = isBarGroup(group);

  const { hiddenTableRows } = useLayoutStore();
  const hiddenRows  = hiddenTableRows[group.title] ?? [];
  const visibleRows = group.rows.filter(r => !hiddenRows.includes(r.label));

  // Show the Vs. Industry column only for non-CAGR groups that have a TTM column
  // and at least one row with a known benchmark.
  const showBenchmarkCol = !isBar
    && group.cols.includes("TTM")
    && visibleRows.some(row => lookupBenchmark(row.label) !== null);

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "7px 12px", border: "1px solid #2d3f5a",
    textAlign: "left", fontSize: "0.82em",
  };
  const thRight: React.CSSProperties = { ...thBase, textAlign: "right", minWidth: 100 };

  return (
    <div style={{ marginBottom: 28 }}>
      {/* Section header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6,
      }}>
        <span style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff" }}>{group.title}</span>
        <TableRowCustomizer tableId={group.title} allRows={group.rows.map(r => r.label)} />
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
            {visibleRows.map((row: InsightsRow, ri: number) => (
              <MetricRow
                key={`${row.label}-${ri}`}
                row={row}
                cols={group.cols}
                is_pct={group.is_pct}
                isAlt={ri % 2 === 1}
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
  const [showCatalog, setShowCatalog] = useState(false);
  const [graphView,   setGraphView]   = useState(false);
  const { hiddenInsightGroups } = useLayoutStore();

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

  const visibleGroups = data.groups.filter(
    (g) => !hiddenInsightGroups.some(
      (hidden) =>
        g.title.toLowerCase().includes(hidden.toLowerCase()) ||
        hidden.toLowerCase().includes(g.title.toLowerCase())
    )
  );

  return (
    <div>
      {/* Controls bar: view toggle + customize */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        {/* View toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {(["By Tables", "By Graphs"] as const).map(v => {
            const active = (v === "By Graphs") === graphView;
            return (
              <button
                key={v}
                onClick={() => setGraphView(v === "By Graphs")}
                style={{
                  padding: "4px 12px",
                  border: `1px solid ${active ? "var(--gv-navy)" : "#d1d5db"}`,
                  borderRadius: 4,
                  background: active ? "var(--gv-navy)" : "#fff",
                  color: active ? "#fff" : "var(--gv-data-fg)",
                  fontWeight: active ? 700 : 500,
                  fontSize: "0.82em",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "all 0.12s",
                }}
              >
                {v}
              </button>
            );
          })}
        </div>
        {!graphView && (
          <button
            onClick={() => setShowCatalog(true)}
            style={{ fontFamily: "var(--gv-font-mono)", fontSize: "0.75em", color: "var(--gv-text-muted)", background: "none", border: "1px solid var(--gv-border)", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}
          >
            ⚙ Customize
          </button>
        )}
      </div>

      {/* ── Tables View ── */}
      {!graphView && (
        <>
          {visibleGroups.map((group) => (
            <GroupTable key={group.title} group={group} />
          ))}
          {showCatalog ? <MetricsCatalogModal tab="value_drivers" onClose={() => setShowCatalog(false)} /> : null}
        </>
      )}

      {/* ── Graphs View ── */}
      {graphView && <InsightsGraphsView data={data} />}

      {/* WACC — always visible in both views */}
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
