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
import { memo, useState, Fragment } from "react";
import { ExternalLink } from "lucide-react";
import type {
  FinancialsData, FinancialRow, FinancialsExtendedData, ExtRow, FmtType, Scale, Period,
} from "../types";
import { IndustryComparisonCell } from "./IndustryComparisonCell";
import { lookupBenchmark } from "../utils/industryBenchmarks";
import { TableToolbar, ExpandOverlay } from "./TableToolbar";

const NAVY    = "#1c2b46";
const PERIODS: Period[] = ["annual", "quarterly"];
const SCALES:  Scale[]  = ["K", "MM", "B"];
const EPS_LABELS = new Set(["eps", "epsdiluted", "noi/sh", "ffo/sh"]);

// ── Formatters ────────────────────────────────────────────────────────────────

function isEps(label: string): boolean {
  return EPS_LABELS.has(label.toLowerCase().replace(/[^a-z]/g, ""));
}

function fCell(
  v: number | string | null | undefined,
  label: string,
  scale: Scale,
): { text: string; negative: boolean } {
  if (v == null || v === "") return { text: "—", negative: false };
  if (typeof v === "string")  return { text: v,  negative: false };
  if (!isFinite(v))           return { text: "—", negative: false };
  const neg = v < 0;
  if (isEps(label)) {
    return { text: `$${Math.abs(v).toFixed(2)}`, negative: neg };
  }
  const div = scale === "K" ? 1e3 : scale === "MM" ? 1e6 : 1e9;
  const abs  = Math.abs(v) / div;
  const text = abs.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return { text: neg ? `(${text})` : text, negative: neg };
}

function fExtCell(
  v: number | string | null | undefined,
  fmt: FmtType,
  scale: Scale,
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
      text = scaled.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
      text = neg ? `(${text})` : text;
      break;
    }
    case "pct":
      text = `${(v * 100).toFixed(1)}%`;
      break;
    case "days":
      text = abs.toFixed(1);
      if (neg) text = `(${text})`;
      break;
    case "int":
      text = Math.round(v).toString();
      break;
    default: // ratio
      text = abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      if (neg) text = `(${text})`;
  }
  return { text, negative: neg };
}

// ── Formats an ExtRow value for use as label inside IndustryComparisonCell ────
function fExtLabel(v: number, fmt: FmtType, scale: Scale): string {
  return fExtCell(v, fmt, scale).text;
}

// ── Chart helpers ─────────────────────────────────────────────────────────────

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

  const toY    = (v: number) => PT + cH - ((v - vMin) / range) * cH;
  const zeroY  = toY(0);
  const bW     = cW / N;
  const colX   = (i: number) => PL + i * bW;
  const shortLbl = (c: string) => c === "TTM" ? "TTM" : c.length > 4 ? c.slice(-4) : c;

  if (isBar) {
    return (
      <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
        <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="#e5e7eb" strokeWidth="1"/>
        {nums.map((v, i) => {
          if (v === null) return null;
          const isTtm = cols[i] === "TTM";
          const x  = colX(i) + bW * 0.1;
          const w  = bW * 0.8;
          const top = v >= 0 ? toY(v) : zeroY;
          const h   = Math.max(Math.abs(toY(v) - zeroY), 1);
          const fill = isTtm ? "#3b82f6" : v < 0 ? "#ef4444" : NAVY;
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

  // Line chart
  const pts = nums
    .map((v, i) => v !== null ? { x: PL + (i + 0.5) * bW, y: toY(v), col: cols[i] } : null)
    .filter(Boolean) as { x: number; y: number; col: string }[];
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
      <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="#e5e7eb" strokeWidth="1"/>
      {d && <path d={d} fill="none" stroke={NAVY} strokeWidth="1.5" opacity="0.7"/>}
      {pts.map((p, i) => {
        const isTtm = p.col === "TTM";
        return (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={isTtm ? 4 : 2.5} fill={isTtm ? "#3b82f6" : NAVY}/>
            <text x={p.x} y={VH - 4} textAnchor="middle" fontSize="8" fill="#9ca3af">{shortLbl(p.col)}</text>
          </g>
        );
      })}
    </svg>
  );
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
      <span style={{ fontSize: "0.78em", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.06em" }}>
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
                color: active ? "#fff" : "#374151",
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
  title, columns, rows, scale, ticker, filingLinks,
}: {
  title:         string;
  columns:       string[];
  rows:          FinancialRow[];
  scale:         Scale;
  ticker:        string;
  filingLinks?:  Record<string, string>;
}) {
  const [openRow,      setOpenRow]      = useState<string | null>(null);
  const [search,       setSearch]       = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [expanded,     setExpanded]     = useState(false);

  const filteredRows = search
    ? rows.filter(r => r.label.toLowerCase().includes(search.toLowerCase()))
    : rows;

  function getExportData() {
    return {
      headers: ["Item", ...columns],
      rows:    filteredRows.map(row => [
        row.label,
        ...columns.map(col => fCell(row[col] as number | null, row.label, scale).text),
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
          {filteredRows.map((row, ri) => {
            const isOpen = openRow === row.label;
            const vals   = columns.map(col => row[col] as number | null);
            return (
              <Fragment key={row.label}>
                <tr style={{ background: ri % 2 === 1 ? "#f8fafc" : "#fff" }}>
                  <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY, whiteSpace: "nowrap" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <button
                        onClick={() => setOpenRow(isOpen ? null : row.label)}
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
                  {columns.map((col) => {
                    const { text, negative } = fCell(row[col] as number | null, row.label, scale);
                    return (
                      <td key={col} style={{
                        padding: "7px 12px", border: "1px solid #e5e7eb",
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
                {isOpen && (
                  <tr>
                    <td colSpan={columns.length + 1} style={{ padding: "8px 16px", border: "1px solid #e5e7eb", background: "#f8fafc" }}>
                      <MiniChart cols={columns} vals={vals} isBar={true} />
                    </td>
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
      <div style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6 }}>
        {title}
      </div>
      {toolbar}
      {tableEl}
    </div>
  );
});

// ── Extended metric table (Market & Val, Cap Structure, etc.) ─────────────────

const ExtTable = memo(function ExtTable({
  title, columns, rows, scale, ticker, filingLinks,
}: {
  title:        string;
  columns:      string[];
  rows:         ExtRow[];
  scale:        Scale;
  ticker:       string;
  filingLinks?: Record<string, string>;
}) {
  const [openRow,      setOpenRow]      = useState<number | null>(null);
  const [search,       setSearch]       = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [expanded,     setExpanded]     = useState(false);

  const filteredRows = search
    ? rows.filter(r => r.label.toLowerCase().includes(search.toLowerCase()))
    : rows;

  // Only show Vs. Industry column when the table has at least one comparable row
  const hasBenchmark = rows.some(row => {
    const fmt = row.fmt as FmtType;
    if (fmt === "money" || fmt === "int") return false;
    return lookupBenchmark(row.label) !== null;
  });

  // Total columns for chart colSpan: label + data cols + (optional benchmark col)
  const totalSpan = columns.length + 1 + (hasBenchmark ? 1 : 0);

  function getExportData() {
    return {
      headers: ["Metric", ...columns],
      rows:    filteredRows.map(row => [
        row.label,
        ...columns.map(col => fExtCell(row[col] as number | string | null, row.fmt as FmtType, scale).text),
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
            const isOpen  = openRow === ri;
            const fmt     = row.fmt as FmtType;
            const isBar   = fmt === "money" || fmt === "int";
            const vals    = columns.map(col => row[col] as number | string | null);

            // Benchmark lookup — only for ratio / pct / days rows
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
                  {columns.map((col) => {
                    const { text, negative } = fExtCell(
                      row[col] as number | string | null,
                      fmt,
                      scale,
                    );
                    return (
                      <td key={col} style={{
                        padding: "7px 12px", border: "1px solid #e5e7eb",
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
                          formatValue={(v) => fExtLabel(v, fmt, scale)}
                        />
                      ) : (
                        <span style={{ color: "#d1d5db", fontSize: "0.75em", paddingLeft: 4 }}>—</span>
                      )}
                    </td>
                  )}
                </tr>
                {isOpen && (
                  <tr>
                    <td colSpan={totalSpan} style={{ padding: "8px 16px", border: "1px solid #e5e7eb", background: "#f8fafc" }}>
                      <MiniChart cols={columns} vals={vals} isBar={isBar} />
                    </td>
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
      <div style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6 }}>
        {title}
      </div>
      {toolbar}
      {tableEl}
    </div>
  );
});

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "#6b7280" }}>
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
        {data && (
          <span style={{ fontSize: "0.78em", color: "#6b7280", marginLeft: "auto" }}>
            Currency: <strong>{data.currency}</strong>
            &nbsp;·&nbsp;values in <strong>{scale}</strong>
          </span>
        )}
      </div>

      {loading && <Spinner label="Loading financials…" />}

      {data && !loading && (
        <>
          <FinTable title="Income Statement" columns={data.columns} rows={data.income_statement} scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <FinTable title="Balance Sheet"    columns={data.columns} rows={data.balance_sheet}    scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <FinTable title="Cash Flow"        columns={data.columns} rows={data.cash_flow}        scale={scale} ticker={ticker} filingLinks={filingLinks} />
          {data.debt && data.debt.length > 0 && (
            <FinTable title="Debt Schedule"  columns={data.columns} rows={data.debt}             scale={scale} ticker={ticker} filingLinks={filingLinks} />
          )}
        </>
      )}

      {extLoading && !loading && <Spinner label="Loading metric tables…" />}

      {extData && !extLoading && (
        <>
          <ExtTable title="Market & Valuation"  columns={extData.columns} rows={extData.market_valuation}  scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <ExtTable title="Capital Structure"    columns={extData.columns} rows={extData.capital_structure} scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <ExtTable title="Profitability"        columns={extData.columns} rows={extData.profitability}     scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <ExtTable title="Returns"              columns={extData.columns} rows={extData.returns}           scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <ExtTable title="Liquidity"            columns={extData.columns} rows={extData.liquidity}         scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <ExtTable title="Dividends"            columns={extData.columns} rows={extData.dividends}         scale={scale} ticker={ticker} filingLinks={filingLinks} />
          <ExtTable title="Efficiency"           columns={extData.columns} rows={extData.efficiency}        scale={scale} ticker={ticker} filingLinks={filingLinks} />
        </>
      )}
    </div>
  );
}
