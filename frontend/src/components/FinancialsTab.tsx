/**
 * FinancialsTab.tsx
 * Pure presentational component — all data is passed in as props.
 * Shows Income Statement, Balance Sheet, Cash Flow, Debt Schedule,
 * then Market & Valuation, Capital Structure, Profitability, Returns,
 * Liquidity, Dividends, Efficiency.
 *
 * Each table has a toolbar (search / download CSV / copy TSV / expand).
 * Period column headers show a hover ExternalLink icon when a filing URL
 * is available in the `filingLinks` prop.
 */
import { memo, useState, useMemo, Fragment, useEffect } from "react";
import { ExternalLink } from "lucide-react";
import type {
  FinancialsData, FinancialRow, FinancialsExtendedData, ExtRow, FmtType, Scale, Period,
} from "../types";
import { IndustryComparisonCell } from "./IndustryComparisonCell";
import { lookupBenchmark } from "../utils/industryBenchmarks";
import { TableToolbar, ExpandOverlay } from "./TableToolbar";
import MetricsCatalogModal from "./MetricsCatalogModal";
import TableRowCustomizer from "./TableRowCustomizer";
import { useLayoutStore } from "../store/layoutStore";
import { getDefaultHiddenRows } from "../constants/financialsRegistry";

const NAVY    = "var(--gv-navy)";
const PERIODS: Period[] = ["annual", "quarterly"];
const SCALES:  Scale[]  = ["K", "MM", "B"];
const DECIMALS_OPTIONS = ["0", "1", "2"] as const;
type DecimalsOpt = typeof DECIMALS_OPTIONS[number];
const EPS_LABELS = new Set(["eps", "epsdiluted", "noi/sh", "ffo/sh"]);

// ── Formatters ────────────────────────────────────────────────────────────────

function isEps(label: string): boolean {
  return EPS_LABELS.has(label.toLowerCase().replace(/[^a-z]/g, ""));
}

function fCell(
  v: number | string | null | undefined,
  label: string,
  scale: Scale,
  decimals = 1,
): { text: string; negative: boolean } {
  if (v == null || v === "") return { text: "—", negative: false };
  if (typeof v === "string")  return { text: v,  negative: false };
  if (!isFinite(v))           return { text: "—", negative: false };
  const neg = v < 0;
  if (isEps(label)) {
    return { text: `$${Math.abs(v).toFixed(Math.max(decimals, 2))}`, negative: neg };
  }
  const div = scale === "K" ? 1e3 : scale === "MM" ? 1e6 : 1e9;
  const abs  = Math.abs(v) / div;
  const text = abs.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return { text: neg ? `(${text})` : text, negative: neg };
}

function fExtCell(
  v: number | string | null | undefined,
  fmt: FmtType,
  scale: Scale,
  decimals = 1,
): { text: string; negative: boolean } {
  if (v == null || v === "") return { text: "—", negative: false };
  if (typeof v === "string") return { text: v,   negative: false };
  if (!isFinite(v))          return { text: "—", negative: false };
  const neg = v < 0;
  const abs = Math.abs(v);
  let text: string;
  switch (fmt) {
    case "money": {
      const div = scale === "K" ? 1e3 : scale === "MM" ? 1e6 : 1e9;
      const scaled = abs / div;
      text = scaled.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
      text = neg ? `(${text})` : text;
      break;
    }
    case "pct":
      text = `${(v * 100).toFixed(decimals)}%`;
      break;
    case "days":
      text = abs.toFixed(decimals);
      if (neg) text = `(${text})`;
      break;
    case "int":
      text = Math.round(v).toString();
      break;
    default: // ratio
      text = abs.toLocaleString("en-US", { minimumFractionDigits: Math.max(decimals, 2), maximumFractionDigits: Math.max(decimals, 2) });
      if (neg) text = `(${text})`;
  }
  return { text, negative: neg };
}

// ── Formats an ExtRow value for use as label inside IndustryComparisonCell ────
function fExtLabel(v: number, fmt: FmtType, scale: Scale, decimals = 1): string {
  return fExtCell(v, fmt, scale, decimals).text;
}


// ── Radio strip ───────────────────────────────────────────────────────────────

function RadioGroup<T extends string>({
  label, options, value, onChange, formatter,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  formatter?: (v: T) => string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </span>
      <div style={{ display: "flex", gap: 4 }}>
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              onClick={() => onChange(opt)}
              style={{
                padding: "4px 12px",
                border: `1px solid ${active ? NAVY : "#d1d5db"}`,
                borderRadius: 4,
                background: active ? NAVY : "#fff",
                color: active ? "#fff" : "var(--gv-data-fg)",
                fontWeight: active ? 700 : 500,
                fontSize: "0.82em",
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "all 0.12s",
                textTransform: "capitalize",
              }}
            >
              {formatter ? formatter(opt) : opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Export helpers ────────────────────────────────────────────────────────────

/**
 * Export table data to a properly formatted .xlsx file using SheetJS.
 * xlsx is imported dynamically so it only loads on first click (~280 KB chunk).
 * - Auto-sized column widths (min 10, max 32 chars)
 * - First row frozen (header stays visible when scrolling in Excel)
 */
async function downloadXlsx(title: string, headers: string[], rows: string[][]) {
  const XLSX = await import("xlsx");
  const aoa  = [headers, ...rows];
  const ws   = XLSX.utils.aoa_to_sheet(aoa);

  // Column widths: max char length across header + all rows, clamped to [10, 32]
  ws["!cols"] = headers.map((h, ci) => ({
    wch: Math.min(32, Math.max(10, h.length, ...rows.map(r => String(r[ci] ?? "").length))),
  }));

  // Freeze the header row so it stays visible when scrolling in Excel
  ws["!freeze"] = { xSplit: 0, ySplit: 1 };

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, title.slice(0, 31)); // Excel sheet name ≤ 31 chars
  XLSX.writeFile(wb, `${title.replace(/[\s/\\?*[\]:]/g, "_")}.xlsx`);
}

async function copyTsv(headers: string[], rows: string[][]) {
  const tsv = [headers, ...rows].map(r => r.join("\t")).join("\n");
  try {
    await navigator.clipboard.writeText(tsv);
  } catch {
    // Clipboard not available in some contexts — silently fail
  }
}

/**
 * Client-side EDGAR link generator.
 * Returns a direct EDGAR company search URL filtered by form type and filing
 * date for the given column label (e.g. "2024" or "Q2 2024").
 * Returns null for international tickers (contain ".") or unrecognised labels.
 */
function generateSECLink(ticker: string, col: string): string | null {
  if (!ticker || ticker.includes(".") || col === "TTM") return null;

  const annualMatch = col.match(/^(\d{4})$/);
  if (annualMatch) {
    const year = parseInt(annualMatch[1]);
    // dateb: 6 months after fiscal year end to catch late filers
    const dateb = `${year + 1}0630`;
    return `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${encodeURIComponent(ticker)}&type=10-K&dateb=${dateb}&owner=include&count=4`;
  }

  const quarterMatch = col.match(/^Q(\d)\s+(\d{4})$/);
  if (quarterMatch) {
    const q    = parseInt(quarterMatch[1]);
    const year = parseInt(quarterMatch[2]);
    // End-of-quarter month + 2-month buffer for late filers
    const [endMon, endYear] = ([
      ["05", year], ["08", year], ["11", year], ["02", year + 1],
    ] as [string, number][])[q - 1];
    const dateb = `${endYear}${endMon}15`;
    return `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${encodeURIComponent(ticker)}&type=10-Q&dateb=${dateb}&owner=include&count=4`;
  }

  return null;
}

// ── Core financial table (IS/BS/CF/Debt) ──────────────────────────────────────

const FinTable = memo(function FinTable({
  title, columns, allColumns, rows, scale, ticker, filingLinks, decimals, showChangePct,
}: {
  title:          string;
  columns:        string[];   // display order (may be reversed)
  allColumns:     string[];   // original order — used for Δ% prev-period lookup
  rows:           FinancialRow[];
  scale:          Scale;
  ticker:         string;
  filingLinks?:   Record<string, string>;
  decimals:       number;
  showChangePct:  boolean;
}) {
  const [search,       setSearch]       = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [expanded,     setExpanded]     = useState(false);

  const { hiddenTableRows, initTableRows } = useLayoutStore();

  // Seed default-hidden rows on first visit (no-op if already customized)
  useEffect(() => {
    const defaults = getDefaultHiddenRows(title, rows.map(r => r.label));
    initTableRows(title, defaults);
  }, [title]); // eslint-disable-line react-hooks/exhaustive-deps

  const hidden = hiddenTableRows[title] ?? [];
  const visibleRows = rows.filter(r => !hidden.includes(r.label));

  const filteredRows = search
    ? visibleRows.filter(r => r.label.toLowerCase().includes(search.toLowerCase()))
    : visibleRows;

  // Δ% helper: change of `col` vs previous period in original column order
  function getChangePct(row: FinancialRow, col: string): number | null {
    const idx = allColumns.indexOf(col);
    if (idx <= 0) return null;
    const prevCol = allColumns[idx - 1];
    const curr = row[col]    as number | null;
    const prev = row[prevCol] as number | null;
    if (curr == null || prev == null || prev === 0 || !isFinite(curr) || !isFinite(prev)) return null;
    return (curr - prev) / Math.abs(prev) * 100;
  }

  function getExportData() {
    return {
      headers: ["Item", ...columns],
      rows:    filteredRows.map(row => [
        row.label,
        ...columns.map(col => fCell(row[col] as number | null, row.label, scale, decimals).text),
      ]),
    };
  }

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "8px 12px", border: "1px solid #2d3f5a",
    fontSize: "0.82em", whiteSpace: "nowrap",
  };

  const toolbar = (
    <TableToolbar
      title={title}
      searchActive={searchActive}
      searchValue={search}
      onToggleSearch={() => { setSearchActive(a => !a); if (searchActive) setSearch(""); }}
      onSearchChange={setSearch}
      onDownload={() => { const { headers, rows: r } = getExportData(); downloadXlsx(title, headers, r); }}
      onCopy={async () => { const { headers, rows: r } = getExportData(); await copyTsv(headers, r); }}
      onToggleExpand={() => setExpanded(e => !e)}
      isExpanded={expanded}
    />
  );

  const tableEl = (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
        <thead>
          <tr>
            <th style={{ ...thBase, textAlign: "left", minWidth: 200 }}>Item</th>
            {columns.map((col) => {
              const filingUrl = filingLinks?.[col] ?? generateSECLink(ticker, col);
              return (
                <th key={col} className="gv-fin-th" style={{ ...thBase, textAlign: "right", minWidth: 88 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 3 }}>
                    {col === "TTM" ? <span style={{ color: "#93c5fd" }}>TTM</span> : col}
                    {filingUrl && (
                      <a
                        href={filingUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="gv-fil-link"
                        title={col.startsWith("Q") ? "View SEC 10-Q filing" : "View SEC 10-K filing"}
                        style={{ color: "#93c5fd", lineHeight: 0, display: "inline-flex", flexShrink: 0 }}
                        onClick={e => e.stopPropagation()}
                      >
                        <ExternalLink size={10} strokeWidth={2.5} />
                      </a>
                    )}
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {filteredRows.map((row, ri) => (
            <Fragment key={row.label}>
              <tr style={{ background: ri % 2 === 1 ? "#f8fafc" : "#fff" }}>
                <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY, whiteSpace: "nowrap" }}>
                  {row.label}
                </td>
                {columns.map((col) => {
                  const { text, negative } = fCell(row[col] as number | null, row.label, scale, decimals);
                  return (
                    <td key={col} style={{
                      padding: "5px 12px", border: "1px solid #e5e7eb",
                      textAlign: "right", fontVariantNumeric: "tabular-nums",
                      fontFamily: "'Courier New', monospace",
                      color: negative ? "#dc2626" : NAVY,
                      fontWeight: col === "TTM" ? 700 : 400,
                      background: col === "TTM" ? "#eff6ff" : undefined,
                    }}>
                      {text}
                    </td>
                  );
                })}
              </tr>
              {showChangePct && (
                <tr style={{ background: ri % 2 === 1 ? "#eef6ff" : "#f5f9ff" }}>
                  <td style={{ padding: "1px 12px", border: "1px solid #e5e7eb", fontSize: "0.7em", color: "var(--gv-text-muted)", fontStyle: "italic" }}>
                    Δ% vs prior
                  </td>
                  {columns.map((col) => {
                    const chg = getChangePct(row, col);
                    return (
                      <td key={col} style={{
                        padding: "1px 12px", border: "1px solid #e5e7eb",
                        textAlign: "right", fontFamily: "'Courier New', monospace",
                        fontSize: "0.7em", fontWeight: 500,
                        color: chg == null ? "var(--gv-text-muted)" : chg >= 0 ? "#10b981" : "#ef4444",
                      }}>
                        {chg == null ? "—" : `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%`}
                      </td>
                    );
                  })}
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );

  if (expanded) {
    return (
      <ExpandOverlay title={title} onClose={() => setExpanded(false)}>
        {toolbar}
        {tableEl}
      </ExpandOverlay>
    );
  }

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6 }}>
        <span style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff" }}>{title}</span>
        <TableRowCustomizer tableId={title} allRows={rows.map(r => r.label)} />
      </div>
      {toolbar}
      {tableEl}
    </div>
  );
});

// ── Extended metric table (Market & Val, Cap Structure, etc.) ─────────────────

const ExtTable = memo(function ExtTable({
  title, columns, allColumns, rows, scale, ticker, filingLinks, decimals, showChangePct,
}: {
  title:         string;
  columns:       string[];
  allColumns:    string[];
  rows:          ExtRow[];
  scale:         Scale;
  ticker:        string;
  filingLinks?:  Record<string, string>;
  decimals:      number;
  showChangePct: boolean;
}) {
  const [search,       setSearch]       = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [expanded,     setExpanded]     = useState(false);

  const { hiddenTableRows, initTableRows } = useLayoutStore();

  // Seed default-hidden rows on first visit (no-op if already customized)
  useEffect(() => {
    const defaults = getDefaultHiddenRows(title, rows.map(r => r.label));
    initTableRows(title, defaults);
  }, [title]); // eslint-disable-line react-hooks/exhaustive-deps

  const hidden = hiddenTableRows[title] ?? [];
  const visibleRows = rows.filter(r => !hidden.includes(r.label));

  const filteredRows = search
    ? visibleRows.filter(r => r.label.toLowerCase().includes(search.toLowerCase()))
    : visibleRows;

  // Only show Vs. Industry column when the table has at least one comparable row
  const hasBenchmark = useMemo(() => rows.some(row => {
    const fmt = row.fmt as FmtType;
    if (fmt === "money" || fmt === "int") return false;
    return lookupBenchmark(row.label) !== null;
  }), [rows]);

  function getChangePct(row: ExtRow, col: string): number | null {
    const idx = allColumns.indexOf(col);
    if (idx <= 0) return null;
    const prevCol = allColumns[idx - 1];
    const curr = row[col]     as number | null;
    const prev = row[prevCol]  as number | null;
    if (curr == null || prev == null || prev === 0 || !isFinite(curr) || !isFinite(prev)) return null;
    return (curr - prev) / Math.abs(prev) * 100;
  }

  function getExportData() {
    return {
      headers: ["Metric", ...columns],
      rows:    filteredRows.map(row => [
        row.label,
        ...columns.map(col => fExtCell(row[col] as number | string | null, row.fmt as FmtType, scale, decimals).text),
      ]),
    };
  }

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "8px 12px", border: "1px solid #2d3f5a",
    fontSize: "0.82em", whiteSpace: "nowrap",
  };

  const toolbar = (
    <TableToolbar
      title={title}
      searchActive={searchActive}
      searchValue={search}
      onToggleSearch={() => { setSearchActive(a => !a); if (searchActive) setSearch(""); }}
      onSearchChange={setSearch}
      onDownload={() => { const { headers, rows: r } = getExportData(); downloadXlsx(title, headers, r); }}
      onCopy={async () => { const { headers, rows: r } = getExportData(); await copyTsv(headers, r); }}
      onToggleExpand={() => setExpanded(e => !e)}
      isExpanded={expanded}
    />
  );

  const tableEl = (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
        <thead>
          <tr>
            <th style={{ ...thBase, textAlign: "left", minWidth: 240 }}>Metric</th>
            {columns.map((col) => {
              const filingUrl = filingLinks?.[col] ?? generateSECLink(ticker, col);
              return (
                <th key={col} className="gv-fin-th" style={{ ...thBase, textAlign: "right", minWidth: 88 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 3 }}>
                    {col === "TTM" ? <span style={{ color: "#93c5fd" }}>TTM</span> : col}
                    {filingUrl && (
                      <a
                        href={filingUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="gv-fil-link"
                        title={col.startsWith("Q") ? "View SEC 10-Q filing" : "View SEC 10-K filing"}
                        style={{ color: "#93c5fd", lineHeight: 0, display: "inline-flex", flexShrink: 0 }}
                        onClick={e => e.stopPropagation()}
                      >
                        <ExternalLink size={10} strokeWidth={2.5} />
                      </a>
                    )}
                  </div>
                </th>
              );
            })}
            {hasBenchmark && (
              <th style={{ ...thBase, textAlign: "left", minWidth: 140, borderLeft: "2px solid #2d4a7a" }}>
                Vs. Industry
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {filteredRows.map((row, ri) => {
            const fmt          = row.fmt as FmtType;
            const canBenchmark = fmt !== "money" && fmt !== "int";
            const benchmark    = canBenchmark ? lookupBenchmark(row.label) : null;
            const ttmVal       = row["TTM"] as number | null | undefined;
            const showCell     = benchmark !== null
              && typeof ttmVal === "number"
              && isFinite(ttmVal);

            return (
              <Fragment key={ri}>
                <tr style={{ background: ri % 2 === 1 ? "#f8fafc" : "#fff" }}>
                  <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY, whiteSpace: "nowrap" }}>
                    {row.label}
                  </td>
                  {columns.map((col) => {
                    const { text, negative } = fExtCell(
                      row[col] as number | string | null,
                      fmt,
                      scale,
                      decimals,
                    );
                    return (
                      <td key={col} style={{
                        padding: "5px 12px", border: "1px solid #e5e7eb",
                        textAlign: "right", fontVariantNumeric: "tabular-nums",
                        fontFamily: "'Courier New', monospace",
                        color: negative ? "#dc2626" : NAVY,
                        fontWeight: col === "TTM" ? 700 : 400,
                        background: col === "TTM" ? "#eff6ff" : undefined,
                      }}>
                        {text}
                      </td>
                    );
                  })}
                  {hasBenchmark && (
                    <td style={{
                      padding: "4px 8px", border: "1px solid #e5e7eb",
                      borderLeft: "2px solid #dbeafe",
                      verticalAlign: "middle",
                      background: ri % 2 === 1 ? "#f8fafc" : "#fff",
                    }}>
                      {showCell ? (
                        <IndustryComparisonCell
                          companyValue={ttmVal as number}
                          industryAvg={benchmark!.avg}
                          metricName={row.label}
                          higherIsBetter={benchmark!.higherIsBetter}
                          formatValue={(v) => fExtLabel(v, fmt, scale, decimals)}
                        />
                      ) : (
                        <span style={{ color: "#d1d5db", fontSize: "0.75em", paddingLeft: 4 }}>—</span>
                      )}
                    </td>
                  )}
                </tr>
                {showChangePct && (
                  <tr style={{ background: ri % 2 === 1 ? "#eef6ff" : "#f5f9ff" }}>
                    <td style={{ padding: "1px 12px", border: "1px solid #e5e7eb", fontSize: "0.7em", color: "var(--gv-text-muted)", fontStyle: "italic" }}>
                      Δ% vs prior
                    </td>
                    {columns.map((col) => {
                      const chg = fmt !== "pct" ? getChangePct(row, col) : null;
                      return (
                        <td key={col} style={{
                          padding: "1px 12px", border: "1px solid #e5e7eb",
                          textAlign: "right", fontFamily: "'Courier New', monospace",
                          fontSize: "0.7em", fontWeight: 500,
                          color: chg == null ? "var(--gv-text-muted)" : chg >= 0 ? "#10b981" : "#ef4444",
                        }}>
                          {chg == null ? "—" : `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%`}
                        </td>
                      );
                    })}
                    {hasBenchmark && (
                      <td style={{ border: "1px solid #e5e7eb", borderLeft: "2px solid #dbeafe" }} />
                    )}
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  if (expanded) {
    return (
      <ExpandOverlay title={title} onClose={() => setExpanded(false)}>
        {toolbar}
        {tableEl}
      </ExpandOverlay>
    );
  }

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6 }}>
        <span style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff" }}>{title}</span>
        <TableRowCustomizer tableId={title} allRows={rows.map(r => r.label)} />
      </div>
      {toolbar}
      {tableEl}
    </div>
  );
});

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "var(--gv-text-muted)" }}>
      <div style={{
        width: 28, height: 28, borderRadius: "50%",
        border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`,
        animation: "gvFinSpin 0.75s linear infinite", flexShrink: 0,
      }} />
      <span style={{ fontSize: "0.88em" }}>{label}</span>
      <style>{`@keyframes gvFinSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export interface FinancialsTabProps {
  ticker:         string;
  data:           FinancialsData | null;
  loading:        boolean;
  extData:        FinancialsExtendedData | null;
  extLoading:     boolean;
  period:         Period;
  scale:          Scale;
  onPeriodChange: (p: Period) => void;
  onScaleChange:  (s: Scale)  => void;
  /** SEC iXBRL filing links: {period_label: url} — populated for US tickers */
  filingLinks?:   Record<string, string>;
}

export default function FinancialsTab({
  ticker, data, loading, extData, extLoading, period, scale, onPeriodChange, onScaleChange,
  filingLinks,
}: FinancialsTabProps) {
  const [showCatalog,    setShowCatalog]    = useState(false);
  const [decimals,       setDecimals]       = useState<DecimalsOpt>("0");
  const [showChangePct,  setShowChangePct]  = useState(false);
  const [reverseCols,    setReverseCols]    = useState(false);
  const { hiddenFinancialsSections } = useLayoutStore();

  // Derive display column order — optionally reversed
  const finColumns    = data     ? (reverseCols ? [...data.columns].reverse()    : data.columns)    : [];
  const extColumns    = extData  ? (reverseCols ? [...extData.columns].reverse() : extData.columns) : [];
  const decNum        = Number(decimals);

  return (
    <div>
      {/* Filing link hover CSS — injected once at component root */}
      <style>{`
        .gv-fin-th { position: relative; }
        .gv-fil-link { opacity: 0; transition: opacity 0.15s ease; }
        .gv-fin-th:hover .gv-fil-link { opacity: 1; }
      `}</style>

      {/* Controls bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap",
        marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid #e5e7eb",
      }}>
        <RadioGroup<Period>
          label="Period"
          options={PERIODS}
          value={period}
          onChange={onPeriodChange}
          formatter={(v) => v === "annual" ? "Annual" : "Quarterly"}
        />
        <RadioGroup<Scale>
          label="Scale"
          options={SCALES}
          value={scale}
          onChange={onScaleChange}
        />
        <RadioGroup<DecimalsOpt>
          label="Decimals"
          options={DECIMALS_OPTIONS}
          value={decimals}
          onChange={setDecimals}
        />
        {/* Change% toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Δ%
          </span>
          <button
            onClick={() => setShowChangePct(v => !v)}
            style={{
              padding: "4px 12px", border: `1px solid ${showChangePct ? NAVY : "#d1d5db"}`,
              borderRadius: 4, background: showChangePct ? NAVY : "#fff",
              color: showChangePct ? "#fff" : "var(--gv-data-fg)",
              fontWeight: showChangePct ? 700 : 500, fontSize: "0.82em",
              cursor: "pointer", fontFamily: "inherit", transition: "all 0.12s",
            }}
          >
            {showChangePct ? "On" : "Off"}
          </button>
        </div>
        {/* Reverse dates toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "0.78em", fontWeight: 700, color: "var(--gv-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Dates
          </span>
          <button
            onClick={() => setReverseCols(v => !v)}
            style={{
              padding: "4px 12px", border: `1px solid ${reverseCols ? NAVY : "#d1d5db"}`,
              borderRadius: 4, background: reverseCols ? NAVY : "#fff",
              color: reverseCols ? "#fff" : "var(--gv-data-fg)",
              fontWeight: reverseCols ? 700 : 500, fontSize: "0.82em",
              cursor: "pointer", fontFamily: "inherit", transition: "all 0.12s",
            }}
          >
            {reverseCols ? "Newest →" : "Oldest →"}
          </button>
        </div>
        {data ? (
          <span style={{ fontSize: "0.78em", color: "var(--gv-text-muted)", marginLeft: "auto" }}>
            Currency: <strong>{data.currency}</strong>
            &nbsp;·&nbsp;values in <strong>{scale}</strong>
          </span>
        ) : null}
      </div>

      {loading ? <Spinner label="Loading financials…" /> : null}

      {data && !loading ? (
        <>
          <FinTable title="Income Statement" columns={finColumns} allColumns={data.columns} rows={data.income_statement} scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} />
          <FinTable title="Balance Sheet"    columns={finColumns} allColumns={data.columns} rows={data.balance_sheet}    scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} />
          <FinTable title="Cash Flow"        columns={finColumns} allColumns={data.columns} rows={data.cash_flow}        scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} />
          {data.debt && data.debt.length > 0 ? (
            <FinTable title="Debt Schedule"  columns={finColumns} allColumns={data.columns} rows={data.debt}             scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} />
          ) : null}
        </>
      ) : null}

      {extLoading && !loading ? <Spinner label="Loading metric tables…" /> : null}

      {extData && !extLoading ? (
        <>
          {/* Extended metrics header + customize button */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 28, marginBottom: 8 }}>
            <div style={{ fontSize: "0.88em", fontWeight: 700, color: NAVY, borderLeft: "3px solid var(--gv-navy)", paddingLeft: 8 }}>
              Extended Metrics
            </div>
            <button
              onClick={() => setShowCatalog(true)}
              style={{ fontFamily: "var(--gv-font-mono)", fontSize: "0.75em", color: "var(--gv-text-muted)", background: "none", border: "1px solid var(--gv-border)", borderRadius: 4, padding: "4px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
            >
              ⚙ Customize
            </button>
          </div>

          {!hiddenFinancialsSections.includes("market_valuation")  ? <ExtTable title="Market & Valuation"  columns={extColumns} allColumns={extData.columns} rows={extData.market_valuation}  scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} /> : null}
          {!hiddenFinancialsSections.includes("capital_structure") ? <ExtTable title="Capital Structure"   columns={extColumns} allColumns={extData.columns} rows={extData.capital_structure} scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} /> : null}
          {!hiddenFinancialsSections.includes("profitability")     ? <ExtTable title="Profitability"       columns={extColumns} allColumns={extData.columns} rows={extData.profitability}     scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} /> : null}
          {!hiddenFinancialsSections.includes("returns")           ? <ExtTable title="Returns"             columns={extColumns} allColumns={extData.columns} rows={extData.returns}           scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} /> : null}
          {!hiddenFinancialsSections.includes("liquidity")         ? <ExtTable title="Liquidity"           columns={extColumns} allColumns={extData.columns} rows={extData.liquidity}         scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} /> : null}
          {!hiddenFinancialsSections.includes("dividends")         ? <ExtTable title="Dividends"           columns={extColumns} allColumns={extData.columns} rows={extData.dividends}         scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} /> : null}
          {!hiddenFinancialsSections.includes("efficiency")        ? <ExtTable title="Efficiency"          columns={extColumns} allColumns={extData.columns} rows={extData.efficiency}        scale={scale} ticker={ticker} filingLinks={filingLinks} decimals={decNum} showChangePct={showChangePct} /> : null}
        </>
      ) : null}

      {showCatalog ? <MetricsCatalogModal tab="financials" onClose={() => setShowCatalog(false)} /> : null}
    </div>
  );
}
