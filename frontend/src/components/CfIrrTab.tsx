/**
 * CfIrrTab.tsx
 * Cameron Stewart's CF + IRR Valuation Model — ported from cf_irr_tab.py.
 *
 * Layout (top to bottom):
 *  0. How to use banner + PDF button
 *  1. Dual-path analysis grid — EBITDA (left) | FCF (right)
 *       · Historical table
 *       · Forecast table (editable)
 *       · Price summary
 *  2. Weighting Table (full-width)
 *  3. IRR Analysis — Calculation Table + Sensitivity Matrix
 *  4. Final Output + Quality Checklist
 */
import { useState, useEffect, useRef, memo, useCallback } from "react";
import type { CfIrrData, OverviewData } from "../types";

const NAVY = "var(--gv-navy)";
const BLUE = "var(--gv-blue)";
const CLR_PASS = "var(--gv-green-bg)"; const CLR_PASS_FG = "var(--gv-green)";
const CLR_FAIL = "var(--gv-red-bg)";  const CLR_FAIL_FG = "var(--gv-red)";
const CLR_WARN = "var(--gv-yellow-bg)"; const CLR_WARN_FG = "#92400e";
const CLR_NA   = "var(--gv-data-bg)"; const CLR_NA_FG   = "var(--gv-text-muted)";
// Tricolor data-type legend
const CLR_API_BG  = "#dbeafe"; const CLR_API_FG  = "#1e40af";   // blue  – direct FMP API data
const CLR_CALC_BG = "var(--gv-green-bg)"; const CLR_CALC_FG = "var(--gv-green)"; // green – calculated
const CLR_USER_BG = "var(--gv-yellow-bg)"; const CLR_USER_FG = "var(--gv-yellow-fg)"; // yellow – user input

// ── Formatters ──────────────────────────────────────────────────────────────

const fMM = (v: number | null | string) =>
  v == null || typeof v !== "number" || !isFinite(v) ? "N/A"
  : v < 0 ? `(${Math.abs(v / 1e6).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })})`
  : (v / 1e6).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const f$ = (v: number | null | string) =>
  v == null || typeof v !== "number" || !isFinite(v) ? "N/A"
  : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const fPctNum = (v: number) => `${v.toFixed(1)}%`;

const MONO: React.CSSProperties = {
  fontFamily: "'Courier New', monospace",
  fontVariantNumeric: "tabular-nums",
};

// ── Sub-components ──────────────────────────────────────────────────────────

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: "1.0em", fontWeight: 700, color: "#fff", background: NAVY,
      padding: "6px 15px", borderRadius: 4, marginTop: 24, marginBottom: 8,
    }}>
      {title}
    </div>
  );
}

function SubHeader({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: "0.82em", fontWeight: 700, color: NAVY,
      borderLeft: `3px solid ${NAVY}`, paddingLeft: 8,
      marginTop: 12, marginBottom: 4,
    }}>
      {title}
    </div>
  );
}

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "var(--gv-text-muted)" }}>
      <div style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`, animation: "cfSpin 0.75s linear infinite", flexShrink: 0 }} />
      <span style={{ fontSize: "0.88em" }}>Computing CF + IRR model…</span>
      <style>{`@keyframes cfSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function Legend() {
  return (
    <div style={{ display: "flex", gap: 12, marginBottom: 10 }}>
      {([
        ["API (fetched)", CLR_API_BG, CLR_API_FG],
        ["Calculated",   CLR_CALC_BG, CLR_CALC_FG],
        ["User Input",   CLR_USER_BG, CLR_USER_FG],
      ] as const).map(([label, bg, fg]) => (
        <span key={label} style={{
          fontSize: "0.72em", fontWeight: 600, padding: "2px 8px",
          borderRadius: 3, background: bg, color: fg,
        }}>{label}</span>
      ))}
    </div>
  );
}

// ── Historical table ─────────────────────────────────────────────────────────

/** Strip decimal places from backend-formatted numeric strings: "1,234.5" → "1,235" */
const roundCellVal = (v: string | undefined): string => {
  if (!v) return "—";
  return v.replace(/([\d,]+\.\d+)/g, (match) => {
    const num = parseFloat(match.replace(/,/g, ""));
    return isNaN(num) ? match : Math.round(num).toLocaleString("en-US");
  });
};

/** Keep 2 decimal places in backend-formatted numeric strings: "1,234.567" → "1,234.57" */
const round2CellVal = (v: string | undefined): string => {
  if (!v) return "—";
  return v.replace(/([\d,]+\.\d+)/g, (match) => {
    const num = parseFloat(match.replace(/,/g, ""));
    return isNaN(num) ? match : num.toFixed(2);
  });
};

const TWO_DP_COLS = new Set(["Net Debt/EBITDA", "Adj. FCF/s", "Stock Price"]);

const HistTable = memo(function HistTable({
  rows, thmRow, avgRow, cagrRow, columns,
}: {
  rows: Record<string, string>[];
  thmRow: Record<string, string>;
  avgRow: Record<string, string>;
  cagrRow: Record<string, string>;
  columns: string[];
}) {
  if (!rows.length) return null;
  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "5px 8px", border: "1px solid #2d3f5a",
    fontSize: "0.72em", whiteSpace: "nowrap", textAlign: "right",
  };
  const allRows = [...rows, cagrRow, avgRow, thmRow];
  return (
    <div style={{ overflowX: "auto", marginBottom: 12 }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.76em", width: "100%" }}>
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={c} style={{ ...thBase, textAlign: i === 0 ? "left" : "right", minWidth: i === 0 ? 70 : 80 }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {allRows.map((row, ri) => {
            const isSpecial = row["Year"] === "TTM" || row["Year"]?.startsWith("Average") || row["Year"]?.startsWith("CAGR");
            // Summary rows (CAGR/Avg/TTM) are calculated; regular rows are direct API data
            const rowBg  = isSpecial ? CLR_CALC_BG : CLR_API_BG;
            const rowFg  = isSpecial ? CLR_CALC_FG : CLR_API_FG;
            return (
              <tr key={ri} style={{ background: rowBg, fontWeight: isSpecial ? 700 : 400 }}>
                {columns.map((col, ci) => {
                  const raw = row[col];
                  const display = ci === 0
                    ? (raw?.startsWith("CAGR") ? "CAGR" : raw ?? "—")
                    : TWO_DP_COLS.has(col) ? round2CellVal(raw) : roundCellVal(raw);
                  return (
                    <td key={col} style={{
                      padding: "4px 8px", border: "1px solid #e5e7eb",
                      textAlign: ci === 0 ? "left" : "right",
                      ...MONO,
                      color: ci === 0 ? NAVY : rowFg,
                      fontSize: "0.95em",
                    }}>
                      {display}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});

// ── Forecast table ──────────────────────────────────────────────────────────

function ForecastTable({
  rows, growthRates, onGrowthChange, valueKey, valueLabel, globalRate, onGlobalChange,
}: {
  rows: { Year: string; [k: string]: unknown }[];
  growthRates: number[];
  onGrowthChange: (idx: number, val: number) => void;
  valueKey: string;
  valueLabel: string;
  globalRate: number;
  onGlobalChange: (v: number) => void;
}) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: "0.74em", fontWeight: 600, color: NAVY }}>Global Rate (Yr 1):</span>
        <input
          type="number" value={globalRate} min={-50} max={200} step={0.5}
          onChange={(e) => onGlobalChange(Number(e.target.value))}
          style={{ width: 72, padding: "2px 6px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.8em", fontFamily: "inherit", textAlign: "right", background: CLR_USER_BG }}
        />
        <span style={{ fontSize: "0.74em", color: "var(--gv-text-muted)" }}>%</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: "0.77em", width: "100%" }}>
          <thead>
            <tr>
              {["Year", "Growth %", valueLabel].map((h) => (
                <th key={h} style={{
                  background: NAVY, color: "#fff", padding: "5px 8px", border: "1px solid #2d3f5a",
                  fontSize: "0.75em", textAlign: h === "Year" ? "left" : "right", whiteSpace: "nowrap",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td style={{ padding: "4px 8px", border: "1px solid #e5e7eb", color: NAVY, fontWeight: 600, fontSize: "0.95em" }}>{row.Year as string}</td>
                <td style={{ padding: "3px 6px", border: "1px solid #e5e7eb", background: CLR_USER_BG }}>
                  <input
                    type="number" value={growthRates[i] ?? 5} step={0.5} min={-50} max={200}
                    onChange={(e) => onGrowthChange(i, Number(e.target.value))}
                    style={{ width: "100%", padding: "2px 5px", border: "1px solid #d1d5db", borderRadius: 3, fontSize: "0.9em", fontFamily: "'Courier New', monospace", textAlign: "right", background: CLR_USER_BG }}
                  />
                </td>
                <td style={{ padding: "4px 8px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: CLR_CALC_FG, background: CLR_CALC_BG, fontWeight: 600 }}>
                  {typeof row[valueKey] === "number"
                    ? (row[valueKey] as number).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 2 })
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Weighting Table ─────────────────────────────────────────────────────────

function WeightingTable({ ebitdaPrice, fcfPrice, avgTarget, ebitdaWeight, onEbitdaWeightChange }: {
  ebitdaPrice: number | null;
  fcfPrice: number | null;
  avgTarget: number | null;
  ebitdaWeight: number;
  onEbitdaWeightChange: (w: number) => void;
}) {
  const fcfWeight = 100 - ebitdaWeight;
  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "7px 14px",
    fontSize: "0.78em", border: "1px solid #2d3f5a", fontWeight: 700,
  };
  const rows = [
    { method: "EV/EBITDA Method", weight: ebitdaWeight, price: ebitdaPrice, onChange: (v: number) => onEbitdaWeightChange(Math.min(100, Math.max(0, v))) },
    { method: "FCF Yield Method",  weight: fcfWeight,   price: fcfPrice,    onChange: (v: number) => onEbitdaWeightChange(Math.min(100, Math.max(0, 100 - v))) },
  ];
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left" }}>Valuation Method</th>
            <th style={{ ...thS, textAlign: "center" }}>Weighting</th>
            <th style={{ ...thS, textAlign: "right" }}>Est. Stock Price</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ method, weight, price, onChange }, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#f8fafc" }}>
              <td style={{ padding: "7px 14px", fontWeight: 600, color: NAVY, border: "1px solid #e5e7eb" }}>{method}</td>
              <td style={{ padding: "4px 10px", textAlign: "center", border: "1px solid #e5e7eb", background: CLR_USER_BG }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4 }}>
                  <input
                    type="number" value={weight} min={0} max={100} step={1}
                    onChange={(e) => onChange(Number(e.target.value))}
                    style={{ width: 52, padding: "2px 5px", border: "1px solid #d1d5db", borderRadius: 3, fontSize: "0.88em", fontFamily: "'Courier New', monospace", textAlign: "right", background: CLR_USER_BG, color: CLR_USER_FG, fontWeight: 600 }}
                  />
                  <span style={{ fontSize: "0.85em", color: CLR_USER_FG, fontWeight: 600 }}>%</span>
                </div>
              </td>
              <td style={{ padding: "7px 14px", textAlign: "right", color: CLR_CALC_FG, background: CLR_CALC_BG, border: "1px solid #e5e7eb", ...MONO }}>{f$(price)}</td>
            </tr>
          ))}
          {/* Footer row — Avg. Target */}
          <tr style={{ background: CLR_CALC_BG }}>
            <td style={{ padding: "8px 14px", fontWeight: 700, color: CLR_CALC_FG, border: "1px solid #e5e7eb", fontSize: "1.0em" }}>
              Avg. Target Price
            </td>
            <td style={{ padding: "8px 14px", textAlign: "center", fontWeight: 700, color: CLR_CALC_FG, border: "1px solid #e5e7eb", ...MONO }}>
              {ebitdaWeight + fcfWeight}%
            </td>
            <td style={{ padding: "8px 14px", textAlign: "right", fontWeight: 700, color: CLR_CALC_FG, border: "1px solid #e5e7eb", ...MONO, fontSize: "1.05em" }}>
              {f$(avgTarget)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ── IRR solver (Newton-Raphson) ──────────────────────────────────────────────

function computeIrr(cfs: number[]): number | null {
  // Requires at least one sign change (negative entry, positive later)
  if (!cfs.length) return null;
  let r = 0.1;
  for (let iter = 0; iter < 1000; iter++) {
    let npv = 0, dnpv = 0;
    for (let t = 0; t < cfs.length; t++) {
      const d = Math.pow(1 + r, t);
      npv  += cfs[t] / d;
      dnpv -= t * cfs[t] / (d * (1 + r));
    }
    if (Math.abs(npv) < 1e-8) break;
    if (Math.abs(dnpv) < 1e-15) return null;
    const rNext = r - npv / dnpv;
    if (rNext <= -1) { r = r / 2; continue; }
    r = rNext;
  }
  return isFinite(r) && r > -1 && Math.abs(r) < 10 ? r : null;
}

// ── IRR Calculation Table ───────────────────────────────────────────────────

function IrrCalculationTable({ fcfForecast, avgTarget, priceNow, irr }: {
  fcfForecast: { Year: string; "Est. Adj. FCF/s": number }[];
  avgTarget: number | null;
  priceNow: number | null;
  irr: number | null;
}) {
  if (!fcfForecast.length) return null;
  const lastIdx = fcfForecast.length - 1;

  // Compute IRR from the exact cash flows shown in this table
  const tableCfs = fcfForecast.map((row, i) => {
    const fcfs = row["Est. Adj. FCF/s"];
    if (i === 0 && priceNow != null)          return fcfs - priceNow;
    if (i === lastIdx && avgTarget != null)    return fcfs + avgTarget;
    return fcfs;
  });
  const tableIrr = computeIrr(tableCfs);
  // Use table-computed IRR for the footer; fall back to backend irr for colour only
  const displayIrr = tableIrr ?? irr;
  const irrColor = (v: number | null) =>
    v == null ? CLR_NA_FG : v >= 0.12 ? CLR_PASS_FG : v >= 0.08 ? CLR_WARN_FG : CLR_FAIL_FG;
  const irrBg = (v: number | null) =>
    v == null ? CLR_NA : v >= 0.12 ? CLR_PASS : v >= 0.08 ? CLR_WARN : CLR_FAIL;

  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "6px 12px",
    fontSize: "0.76em", border: "1px solid #2d3f5a", fontWeight: 700,
  };
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.81em", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left", minWidth: 60 }}>Year</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 100 }}>Price</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 90 }}>Est. FCF/s</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 120 }}>Total Cash Flow</th>
          </tr>
        </thead>
        <tbody>
          {fcfForecast.map((row, i) => {
            const fcfs = row["Est. Adj. FCF/s"];
            const isFirst = i === 0;
            const isFinal = i === lastIdx;

            // First row: entry — investor pays current price (negative cash flow)
            const priceDisplay = isFirst
              ? (priceNow != null ? `($${priceNow.toFixed(2)})` : "—")
              : isFinal
                ? f$(avgTarget)
                : "—";

            // Total CF:
            //   First row: FCF/s received − entry price paid
            //   Middle rows: FCF/s only
            //   Final row: FCF/s + exit (avg_target)
            const totalCf = isFirst && priceNow != null
              ? fcfs - priceNow
              : isFinal && avgTarget != null
                ? fcfs + avgTarget
                : fcfs;

            const priceFg = isFirst ? CLR_API_FG  : isFinal ? CLR_CALC_FG : "var(--gv-text-muted)";
            const priceBg = isFirst ? CLR_API_BG  : isFinal ? CLR_CALC_BG : "transparent";
            const totalDisplay = typeof totalCf === "number"
              ? totalCf < 0 ? `($${Math.abs(totalCf).toFixed(2)})` : `$${totalCf.toFixed(2)}`
              : "—";

            return (
              <tr key={i} style={{
                background: isFinal
                  ? CLR_CALC_BG
                  : isFirst
                    ? CLR_API_BG
                    : i % 2 === 0 ? "#fff" : "#f8fafc",
                fontWeight: (isFirst || isFinal) ? 700 : 400,
              }}>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", color: NAVY, fontWeight: 600 }}>{row.Year}</td>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: priceFg, background: priceBg }}>
                  {priceDisplay}
                </td>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: CLR_CALC_FG, background: CLR_CALC_BG }}>
                  {typeof fcfs === "number" ? `$${fcfs.toFixed(2)}` : "—"}
                </td>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: CLR_CALC_FG, background: CLR_CALC_BG, fontWeight: (isFirst || isFinal) ? 700 : 400 }}>
                  {totalDisplay}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr style={{ background: irrBg(displayIrr), fontWeight: 700 }}>
            <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", color: irrColor(displayIrr), fontSize: "1.0em" }}>
              IRR
            </td>
            <td style={{ border: "1px solid #e5e7eb" }} />
            <td style={{ border: "1px solid #e5e7eb" }} />
            <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: irrColor(displayIrr), fontSize: "1.05em", letterSpacing: "0.01em" }}>
              {displayIrr != null ? `${(displayIrr * 100).toFixed(1)}%` : "N/A"}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ── IRR Sensitivity Matrix ──────────────────────────────────────────────────

const SensitivityMatrix = memo(function SensitivityMatrix({
  rowLabels, colLabels, matrix, highlightRow,
}: {
  rowLabels: string[];
  colLabels: string[];
  matrix: (number | null)[][];
  highlightRow?: number;
}) {
  const irrColor = (v: number | null): [string, string] => {
    if (v == null) return [CLR_FAIL, CLR_FAIL_FG];
    if (v >= 0.12) return [CLR_PASS, CLR_PASS_FG];
    if (v >= 0.08) return [CLR_WARN, CLR_WARN_FG];
    return [CLR_FAIL, CLR_FAIL_FG];
  };
  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "6px 10px",
    fontSize: "0.76em", whiteSpace: "nowrap", border: "1px solid #2d3f5a",
  };
  return (
    <div style={{ overflowX: "auto", marginTop: 6 }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.81em" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left", minWidth: 130 }}>Entry Price</th>
            {colLabels.map((c) => (
              <th key={c} style={{ ...thS, textAlign: "center", minWidth: 70 }}>Exit Yield {c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, ri) => {
            const isCurrent = ri === highlightRow;
            return (
              <tr key={ri} style={isCurrent ? { outline: `2px solid ${BLUE}`, outlineOffset: -1 } : undefined}>
                <td style={{
                  padding: "6px 10px",
                  background: isCurrent ? "color-mix(in srgb, var(--gv-blue) 10%, white)" : "#f8fafc",
                  color: isCurrent ? BLUE : NAVY,
                  fontWeight: isCurrent ? 700 : 600,
                  fontSize: "0.78em",
                  whiteSpace: "nowrap",
                  border: "1px solid #e5e7eb",
                  borderLeft: isCurrent ? `3px solid ${BLUE}` : "1px solid #e5e7eb",
                }}>
                  {isCurrent && (
                    <span style={{ marginRight: 5, fontSize: "0.85em", fontWeight: 700 }}>▶</span>
                  )}
                  {rowLabels[ri]}
                  {isCurrent && (
                    <span style={{
                      marginLeft: 6, fontSize: "0.72em", fontWeight: 700,
                      color: BLUE, background: "color-mix(in srgb, var(--gv-blue) 15%, white)",
                      borderRadius: 3, padding: "1px 5px",
                    }}>
                      current
                    </span>
                  )}
                </td>
                {row.map((v, ci) => {
                  const [bg, fg] = irrColor(v);
                  return (
                    <td key={ci} style={{
                      padding: "6px 10px", background: bg, color: fg,
                      fontWeight: isCurrent ? 800 : 700,
                      textAlign: "center", border: "1px solid #e5e7eb",
                      fontSize: isCurrent ? "1.02em" : "1em",
                      ...MONO,
                    }}>
                      {v != null ? `${(v * 100).toFixed(1)}%` : "N/A"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});

// ── Quality Checklist ───────────────────────────────────────────────────────

const Checklist = memo(function Checklist({ items }: { items: CfIrrData["checklist"] }) {
  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "7px 12px",
    fontSize: "0.78em", textAlign: "left", border: "1px solid #2d3f5a",
  };
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
        <thead>
          <tr>
            <th style={thS}>Metric</th>
            <th style={{ ...thS, textAlign: "center" }}>Threshold</th>
            <th style={{ ...thS, textAlign: "center" }}>Value</th>
            <th style={{ ...thS, textAlign: "center" }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => {
            const bg = item.passed === true ? CLR_PASS : item.passed === false ? CLR_FAIL : CLR_NA;
            const fg = item.passed === true ? CLR_PASS_FG : item.passed === false ? CLR_FAIL_FG : CLR_NA_FG;
            const icon = item.passed === true ? "✅" : item.passed === false ? "❌" : "—";
            return (
              <tr key={i} style={{ background: bg }}>
                <td style={{ padding: "7px 12px", fontWeight: 600, color: fg, border: "1px solid #e5e7eb" }}>{item.label}</td>
                <td style={{ padding: "7px 12px", textAlign: "center", color: "var(--gv-text-dim)", border: "1px solid #e5e7eb" }}>{item.threshold}</td>
                <td style={{ padding: "7px 12px", textAlign: "center", fontWeight: 700, color: fg, border: "1px solid #e5e7eb", ...MONO }}>{item.display}</td>
                <td style={{ padding: "7px 12px", textAlign: "center", fontSize: "1.1em", border: "1px solid #e5e7eb" }}>{icon}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});

// ── Final Output ────────────────────────────────────────────────────────────

function FinalOutput({ data, waccPct, mosPct, avgTarget }: {
  data: CfIrrData;
  waccPct: number;
  mosPct: number;
  avgTarget: number | null;
}) {
  const waccDec = waccPct / 100;
  const fairValue = avgTarget != null && waccDec > 0
    ? avgTarget / (1 + waccDec) ** 9 : null;
  const buyPrice = fairValue != null ? fairValue * (1 - mosPct / 100) : null;
  const onSale   = fairValue != null && data.price_now != null ? fairValue > data.price_now : null;

  const delta = (target: number | null, current: number | null) => {
    if (!target || !current || target === 0) return "N/A";
    const pct = (1 - current / target) * 100;
    return `${pct >= 0 ? "Upside" : "Downside"}  ${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
  };

  const rows: [string, string, boolean | null, "api" | "calc" | "user"][] = [
    ["Average Target Price",        f$(avgTarget),                                                                      null, "calc"],
    ["WACC",                        `${waccPct.toFixed(2)}%`,                                                           null, "user"],
    ["Fair Value per share",        f$(fairValue),                                                                      null, "calc"],
    ["Margin of Safety",            `${mosPct.toFixed(0)}%`,                                                            null, "user"],
    ["Buy Price",                   f$(buyPrice),                                                                       null, "calc"],
    ["Current Stock Price",         f$(data.price_now),                                                                 null, "api"],
    ["Company on-sale?",            onSale === true ? "✅ ON SALE" : onSale === false ? "❌ NOT ON SALE" : "N/A",       onSale, "calc"],
    ["Upside / Downside (vs. FV)",  delta(fairValue, data.price_now),                                                  null, "calc"],
    ["Upside / Downside (vs. Buy)", delta(buyPrice,  data.price_now),                                                  null, "calc"],
  ];

  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "7px 12px",
    fontSize: "0.78em", border: "1px solid #2d3f5a",
  };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
      <thead>
        <tr>
          <th style={{ ...thS, textAlign: "left" }}>Metric</th>
          <th style={{ ...thS, textAlign: "right" }}>Value</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, val, verdict, colorType]) => {
          const bg = verdict === true  ? CLR_PASS
                   : verdict === false ? CLR_FAIL
                   : colorType === "api"  ? CLR_API_BG
                   : colorType === "calc" ? CLR_CALC_BG
                   : colorType === "user" ? CLR_USER_BG
                   : "#fff";
          const fg = verdict === true  ? CLR_PASS_FG
                   : verdict === false ? CLR_FAIL_FG
                   : colorType === "api"  ? CLR_API_FG
                   : colorType === "calc" ? CLR_CALC_FG
                   : colorType === "user" ? CLR_USER_FG
                   : NAVY;
          return (
            <tr key={label} style={{ background: bg }}>
              <td style={{ padding: "6px 12px", fontWeight: 600, color: fg, border: "1px solid #e5e7eb" }}>{label}</td>
              <td style={{ padding: "6px 12px", textAlign: "right", fontWeight: 700, color: fg, border: "1px solid #e5e7eb", ...MONO }}>{val}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

interface Props {
  ticker: string;
  externalWacc: number;
  ov?: OverviewData | null;
}

export default function CfIrrTab({ ticker, externalWacc, ov }: Props) {
  const [data,    setData]    = useState<CfIrrData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  // User-editable inputs
  const [ebtGrowth, setEbtGrowth] = useState<number[]>([5, 5, 5, 5, 5, 5, 5, 5, 5]);
  const [ebtGlobal, setEbtGlobal] = useState(5);
  const [fcfGrowth, setFcfGrowth] = useState<number[]>([5, 5, 5, 5, 5, 5, 5, 5, 5]);
  const [fcfGlobal, setFcfGlobal] = useState(5);
  const [exitMult,     setExitMult]     = useState(15.0);
  const [exitYield,    setExitYield]    = useState(5.0);
  const [mosPct,       setMosPct]       = useState(10.0);
  const [ebitdaWeight, setEbitdaWeight] = useState(50);

  // WACC: use external (from slider) if set, else use computed from backend
  const waccPct = externalWacc > 0 ? externalWacc : (data?.wacc_computed ?? 0) * 100;

  const [pdfLoading, setPdfLoading] = useState(false);

  const handleDownloadPdf = async () => {
    if (!data) return;
    setPdfLoading(true);
    try {
      const waccDec = waccPct / 100;
      const fv  = weightedAvgTarget != null && waccDec > 0
        ? weightedAvgTarget / Math.pow(1 + waccDec, 9) : null;
      const bp  = fv != null ? fv * (1 - mosPct / 100) : null;
      const os  = fv != null && data.price_now != null ? fv > data.price_now : null;

      const payload = {
        wacc_pct:     waccPct,
        mos_pct:      mosPct,
        exit_mult:    exitMult,
        exit_yield:   exitYield,
        company:      ov?.company_name  ?? "",
        sector:       ov?.sector        ?? "",
        industry:     ov?.industry      ?? "",
        description:  ov?.description   ?? "",
        ebt_hist:     data.ebt_hist,
        ebt_ttm:      data.ebt_ttm,
        ebt_avg:      data.ebt_avg,
        ebt_cagr:     data.ebt_cagr,
        fcf_hist:     data.fcf_hist,
        fcf_ttm:      data.fcf_ttm,
        fcf_avg:      data.fcf_avg,
        fcf_cagr:     data.fcf_cagr,
        ebt_forecast: data.ebt_forecast,
        fcf_forecast: adjustedFcfForecast,   // frontend-recomputed from last hist year
        checklist:    checklistItems,         // includes frontend IRR override
        price_now:    data.price_now,
        avg_target:   weightedAvgTarget,
        ebitda_price: data.ebitda_price,
        fcf_price:    data.fcf_price,
        fair_value:   fv,
        buy_price:    bp,
        on_sale:      os,
        irr:          frontendIrr ?? data.irr,
        irr_sensitivity: {
          row_labels: data.irr_sensitivity.row_labels,
          col_labels: data.irr_sensitivity.col_labels,
          matrix:     frontendMatrix,
        },
      };

      const ctrl = new AbortController();
      const timeoutId = setTimeout(() => ctrl.abort(), 90_000);
      const resp = await fetch(`/api/cf-irr/${ticker}/pdf`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(payload),
        signal:  ctrl.signal,
      });
      clearTimeout(timeoutId);

      if (!resp.ok) {
        const msg = await resp.text().catch(() => `HTTP ${resp.status}`);
        throw new Error(msg);
      }

      const blob = await resp.blob();
      const url  = window.URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `${ticker}_One_Pager.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => window.URL.revokeObjectURL(url), 5_000);
    } catch (err) {
      console.error("PDF download failed:", err);
      const msg = err instanceof Error ? err.message : String(err);
      alert(`PDF generation failed: ${msg}`);
    } finally {
      setPdfLoading(false);
    }
  };

  const debounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const seeded   = useRef(false);

  const buildUrl = useCallback((rates?: { ebt: number[]; fcf: number[]; mult: number; yld: number; mos: number }) => {
    const eg = rates?.ebt ?? ebtGrowth;
    const fg = rates?.fcf ?? fcfGrowth;
    const em = rates?.mult ?? exitMult;
    const ey = rates?.yld  ?? exitYield;
    const mp = rates?.mos  ?? mosPct;
    const qs = new URLSearchParams({
      ebt_growth:    eg.join(","),
      fcf_growth:    fg.join(","),
      exit_mult:     String(em),
      exit_yield:    String(ey),
      mos_pct:       String(mp),
      wacc_override: String(waccPct),
    });
    return `/api/cf-irr/${ticker}?${qs}`;
  }, [ticker, ebtGrowth, fcfGrowth, exitMult, exitYield, mosPct, waccPct]);

  // Initial load
  useEffect(() => {
    seeded.current = false;
    setLoading(true); setError(null); setData(null);
    fetch(`/api/cf-irr/${ticker}`)
      .then((r) => r.ok ? r.json() : r.json().then((b) => Promise.reject(b.detail ?? `HTTP ${r.status}`)))
      .then((d: CfIrrData) => {
        setData(d);
        if (!seeded.current) {
          seeded.current = true;
          setEbtGrowth(d.ebt_growth_rates);
          setFcfGrowth(d.fcf_growth_rates);
          setEbtGlobal(d.ebt_growth_rates[0] ?? 5);
          setFcfGlobal(d.fcf_growth_rates[0] ?? 5);
          setExitMult(d.exit_mult);
          setExitYield(d.exit_yield);
          setMosPct(d.mos_pct);
        }
      })
      .catch((e: unknown) => setError(typeof e === "string" ? e : "Failed to load CF+IRR data"))
      .finally(() => setLoading(false));
  }, [ticker]);

  // Re-fetch when inputs change (debounced)
  const refetch = useCallback((overrides?: Parameters<typeof buildUrl>[0]) => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      fetch(buildUrl(overrides))
        .then((r) => r.json())
        .then(setData)
        .catch(console.error);
    }, 400);
  }, [buildUrl]);

  // Handlers
  const handleEbtGrowth = (idx: number, val: number) => {
    const next = [...ebtGrowth]; next[idx] = val; setEbtGrowth(next); refetch({ ebt: next, fcf: fcfGrowth, mult: exitMult, yld: exitYield, mos: mosPct });
  };
  const handleEbtGlobal = (val: number) => {
    setEbtGlobal(val); const next = [...ebtGrowth]; next[0] = val; setEbtGrowth(next); refetch({ ebt: next, fcf: fcfGrowth, mult: exitMult, yld: exitYield, mos: mosPct });
  };
  const handleFcfGrowth = (idx: number, val: number) => {
    const next = [...fcfGrowth]; next[idx] = val; setFcfGrowth(next); refetch({ ebt: ebtGrowth, fcf: next, mult: exitMult, yld: exitYield, mos: mosPct });
  };
  const handleFcfGlobal = (val: number) => {
    setFcfGlobal(val); const next = [...fcfGrowth]; next[0] = val; setFcfGrowth(next); refetch({ ebt: ebtGrowth, fcf: next, mult: exitMult, yld: exitYield, mos: mosPct });
  };
  const handleExitMult  = (val: number) => { setExitMult(val);  refetch({ ebt: ebtGrowth, fcf: fcfGrowth, mult: val,      yld: exitYield, mos: mosPct }); };
  const handleExitYield = (val: number) => { setExitYield(val); refetch({ ebt: ebtGrowth, fcf: fcfGrowth, mult: exitMult, yld: val,       mos: mosPct }); };
  const handleMosPct    = (val: number) => { setMosPct(val);    refetch({ ebt: ebtGrowth, fcf: fcfGrowth, mult: exitMult, yld: exitYield, mos: val }); };

  if (loading) return <Spinner />;
  if (error)   return <div style={{ background: "var(--gv-red-bg)", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "var(--gv-red)" }}><strong>Error:</strong> {error}</div>;
  if (!data)   return null;

  // ── Weighted Avg. Target (user-adjustable) ────────────────────────────────
  const fcfWeight = 100 - ebitdaWeight;
  const weightedAvgTarget: number | null =
    data.ebitda_price != null && data.fcf_price != null
      ? (ebitdaWeight / 100) * data.ebitda_price + (fcfWeight / 100) * data.fcf_price
      : data.avg_target;

  const ebtHistCols = data.ebt_hist.length ? Object.keys(data.ebt_hist[0]) : [];
  const fcfHistCols = data.fcf_hist.length ? Object.keys(data.fcf_hist[0]) : [];

  // ── Recompute FCF forecast from last historical year (not TTM) ─────────────
  // Parse the "Adj. FCF/s" string from the last annual row in fcf_hist
  const lastFcfHistRow = data.fcf_hist.length > 0 ? data.fcf_hist[data.fcf_hist.length - 1] : null;
  const lastHistFcfsStr = lastFcfHistRow?.["Adj. FCF/s"] as string | undefined;
  const lastHistFcfs = lastHistFcfsStr
    ? parseFloat(lastHistFcfsStr.replace(/[^0-9.\-]/g, "")) || null
    : null;

  const adjustedFcfForecast: { Year: string; "Est. Adj. FCF/s": number }[] =
    lastHistFcfs != null && data.fcf_forecast.length > 0
      ? (data.fcf_forecast as { Year: string; "Est. Adj. FCF/s": number }[]).map((row, i) => {
          let base = lastHistFcfs;
          for (let j = 0; j <= i; j++) {
            base = base * (1 + (fcfGrowth[j] ?? 5) / 100);
          }
          return { ...row, "Est. Adj. FCF/s": base };
        })
      : (data.fcf_forecast as { Year: string; "Est. Adj. FCF/s": number }[]);

  // ── Frontend IRR — computed from the exact cash flows shown in the table ──
  const fcfForecastTyped = adjustedFcfForecast;
  const frontendIrrCfs = fcfForecastTyped.map((row, i) => {
    const fcfs = row["Est. Adj. FCF/s"];
    if (i === 0 && data.price_now != null)                                  return fcfs - data.price_now;
    if (i === fcfForecastTyped.length - 1 && weightedAvgTarget != null)    return fcfs + weightedAvgTarget;
    return fcfs;
  });
  const frontendIrr = computeIrr(frontendIrrCfs) ?? data.irr;

  const irr    = frontendIrr;
  const irrPct = irr != null ? `${(irr * 100).toFixed(1)}%` : "N/A";

  // ── Override checklist IRR item with frontend-computed value ─────────────
  const checklistItems = data.checklist.map((item) => {
    if (/irr/i.test(item.label) && frontendIrr != null) {
      const pct = frontendIrr * 100;
      return {
        ...item,
        display: `${pct.toFixed(1)}%`,
        passed:  frontendIrr >= 0.12 ? true : frontendIrr < 0.08 ? false : null,
      };
    }
    return item;
  });

  // ── Recompute sensitivity matrix using frontend IRR solver ────────────────
  // Rows = entry prices, Cols = exit FCF yields; terminal = FCF_year9 / exit_yield
  const fcfYear9 = fcfForecastTyped.length > 0
    ? fcfForecastTyped[fcfForecastTyped.length - 1]["Est. Adj. FCF/s"] : null;
  const parsePx = (s: string) => { const n = parseFloat(s.replace(/[^0-9.]/g, "")); return isNaN(n) ? null : n; };
  const parseYf = (s: string) => { const n = parseFloat(s.replace(/[^0-9.]/g, "")); return isNaN(n) || n <= 0 ? null : n / 100; };

  // Find the sensitivity row whose entry price is closest to current price
  const highlightRow = data.price_now != null && data.irr_sensitivity.row_labels.length > 0
    ? data.irr_sensitivity.row_labels.reduce((bestIdx, label, i) => {
        const p = parsePx(label);
        const bestP = parsePx(data.irr_sensitivity.row_labels[bestIdx]);
        if (p == null) return bestIdx;
        if (bestP == null) return i;
        return Math.abs(p - data.price_now!) < Math.abs(bestP - data.price_now!) ? i : bestIdx;
      }, 0)
    : undefined;

  const frontendMatrix: (number | null)[][] = data.irr_sensitivity.row_labels.map((rowLabel) => {
    const entryPrice = parsePx(rowLabel);
    return data.irr_sensitivity.col_labels.map((colLabel) => {
      const exitYield = parseYf(colLabel);
      if (entryPrice == null || exitYield == null || fcfYear9 == null) return null;
      const terminal = fcfYear9 / exitYield;
      const cfs = fcfForecastTyped.map((r, i) => {
        const fcfs = r["Est. Adj. FCF/s"];
        if (i === 0)                            return fcfs - entryPrice;
        if (i === fcfForecastTyped.length - 1) return fcfs + terminal;
        return fcfs;
      });
      return computeIrr(cfs);
    });
  });

  return (
    <div>

      {/* ═══ SECTION 0 — Banner + PDF ══════════════════════════════════════════ */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 260, background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, padding: "10px 16px", fontSize: "0.83em", color: "#1e40af" }}>
          <strong>How to use:</strong> Review the historical EV/EBITDA and Adj. FCF/s tables, then adjust
          the per-year growth rates and exit assumptions. The two stock-price projections are averaged,
          discounted at WACC to compute Fair Value, and compared to the current price.
          IRR is calculated from the projected FCF/s cash flow stream.
        </div>
        <button
          onClick={handleDownloadPdf}
          disabled={pdfLoading || !data}
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "8px 16px", borderRadius: 6, fontSize: "0.83em", fontWeight: 600,
            background: pdfLoading ? "#64748b" : NAVY,
            color: "#fff", border: "none",
            cursor: pdfLoading || !data ? "not-allowed" : "pointer",
            flexShrink: 0, whiteSpace: "nowrap",
            opacity: pdfLoading || !data ? 0.7 : 1,
          }}
        >
          {pdfLoading ? "⏳ Generating…" : "📄 Download PDF One-Pager"}
        </button>
      </div>

      {/* ═══ SECTION 1 — Dual-path Analysis Grid ══════════════════════════════ */}
      <Legend />
      <div className="grid grid-cols-2 gap-6">

        {/* ── LEFT: EBITDA Analysis ───────────────────────────────────────────── */}
        <div>
          <SecHeader title="EBITDA Analysis" />

          <SubHeader title={`2.1 · EV/EBITDA Historical  (values in $MM unless noted)`} />
          <HistTable
            rows={data.ebt_hist}
            thmRow={data.ebt_ttm}
            avgRow={data.ebt_avg}
            cagrRow={data.ebt_cagr}
            columns={ebtHistCols}
          />

          <SubHeader title={`2.2 · EBITDA Forecast  (${data.base_year + 1}–${data.base_year + 9})`} />
          <ForecastTable
            rows={data.ebt_forecast}
            growthRates={ebtGrowth}
            onGrowthChange={handleEbtGrowth}
            valueKey="Est. EBITDA ($MM)"
            valueLabel="Est. EBITDA ($MM)"
            globalRate={ebtGlobal}
            onGlobalChange={handleEbtGlobal}
          />

          <SubHeader title="Est. Stock Price — EBITDA Method" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: "0.74em", fontWeight: 600, color: NAVY }}>Exit EV/EBITDA Multiple:</span>
            <input
              type="number" value={exitMult} min={1} max={100} step={0.5}
              onChange={(e) => handleExitMult(Number(e.target.value))}
              style={{ width: 76, padding: "2px 6px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.88em", fontFamily: "inherit", textAlign: "right", background: CLR_USER_BG }}
            />
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.81em" }}>
            <tbody>
              {([
                ["Est. EV/EBITDA Multiple", `${exitMult.toFixed(1)}x`,                                                           "user"],
                [`EV in ${data.base_year + 9} ($MM)`,
                  data.ebt_forecast.length ? fMM((data.ebt_forecast[8]?.["Est. EBITDA ($MM)"] ?? 0) * exitMult * 1e6) : "N/A",  "calc"],
                ["Less: Net Debt TTM ($MM)", fMM(data.net_debt_ttm),                                                              "api"],
                ["Est. Stock Price",         f$(data.ebitda_price),                                                               "calc"],
              ] as [string, string, "user" | "calc" | "api"][]).map(([label, val, type]) => {
                const bg = type === "user" ? CLR_USER_BG : type === "calc" ? CLR_CALC_BG : CLR_API_BG;
                const fg = type === "user" ? CLR_USER_FG : type === "calc" ? CLR_CALC_FG : CLR_API_FG;
                return (
                  <tr key={label} style={{ background: bg }}>
                    <td style={{ padding: "5px 10px", fontWeight: 600, color: NAVY, border: "1px solid #e5e7eb", fontSize: "0.9em" }}>{label}</td>
                    <td style={{ padding: "5px 10px", textAlign: "right", border: "1px solid #e5e7eb", ...MONO, color: fg, fontWeight: type === "calc" ? 700 : 400 }}>{val}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* ── RIGHT: FCF Analysis ─────────────────────────────────────────────── */}
        <div>
          <SecHeader title="Free Cash Flow Analysis" />

          <SubHeader title={`3.1 · Adj. FCF/s Historical  (values in $MM unless noted)`} />
          <HistTable
            rows={data.fcf_hist}
            thmRow={data.fcf_ttm}
            avgRow={data.fcf_avg}
            cagrRow={data.fcf_cagr}
            columns={fcfHistCols}
          />

          <SubHeader title={`3.2 · Adj. FCF/s Forecast  (${data.base_year + 1}–${data.base_year + 9})`} />
          <ForecastTable
            rows={adjustedFcfForecast}
            growthRates={fcfGrowth}
            onGrowthChange={handleFcfGrowth}
            valueKey="Est. Adj. FCF/s"
            valueLabel="Est. Adj. FCF/s ($)"
            globalRate={fcfGlobal}
            onGlobalChange={handleFcfGlobal}
          />

          <SubHeader title="Est. Stock Price — FCF/s Method" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: "0.74em", fontWeight: 600, color: NAVY }}>Long Term FCF/s Yield:</span>
            <input
              type="number" value={exitYield} min={0.5} max={50} step={0.5}
              onChange={(e) => handleExitYield(Number(e.target.value))}
              style={{ width: 68, padding: "2px 6px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.88em", fontFamily: "inherit", textAlign: "right", background: CLR_USER_BG }}
            />
            <span style={{ fontSize: "0.78em", color: "var(--gv-text-muted)" }}>%</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.81em" }}>
            <tbody>
              {([
                ["Long Term FCF/s Yield",          fPctNum(exitYield),                                                                                       "user"],
                [`Est. Adj. FCF/s in ${data.base_year + 9}`,
                  adjustedFcfForecast.length ? `$${(adjustedFcfForecast[8]?.["Est. Adj. FCF/s"] ?? 0).toFixed(2)}` : "N/A",                                 "calc"],
                ["Est. Stock Price",               f$(data.fcf_price),                                                                                       "calc"],
              ] as [string, string, "user" | "calc"][]).map(([label, val, type]) => {
                const bg = type === "user" ? CLR_USER_BG : CLR_CALC_BG;
                const fg = type === "user" ? CLR_USER_FG : CLR_CALC_FG;
                return (
                  <tr key={label} style={{ background: bg }}>
                    <td style={{ padding: "5px 10px", fontWeight: 600, color: NAVY, border: "1px solid #e5e7eb", fontSize: "0.9em" }}>{label}</td>
                    <td style={{ padding: "5px 10px", textAlign: "right", border: "1px solid #e5e7eb", ...MONO, color: fg, fontWeight: type === "calc" ? 700 : 400 }}>{val}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ═══ SECTION 2 — Weighting Table ═══════════════════════════════════════ */}
      <SecHeader title="2 · Weighting  —  Avg. Target Price" />
      <WeightingTable
        ebitdaPrice={data.ebitda_price}
        fcfPrice={data.fcf_price}
        avgTarget={weightedAvgTarget}
        ebitdaWeight={ebitdaWeight}
        onEbitdaWeightChange={setEbitdaWeight}
      />

      {/* ═══ SECTION 3 — Final Output + Quality Checklist ══════════════════════ */}
      <SecHeader title="3 · Final Output  +  Quality Checklist" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>

        {/* LEFT: Final Output */}
        <div>
          <div style={{ fontSize: "0.82em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginBottom: 6 }}>
            Final Output
          </div>
          <FinalOutput data={data} waccPct={waccPct} mosPct={mosPct} avgTarget={weightedAvgTarget} />

          {/* WACC + MoS inputs */}
          <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 120 }}>
              <div style={{ fontSize: "0.74em", fontWeight: 600, color: NAVY, marginBottom: 3 }}>
                WACC: <span style={{ color: "#b45309" }}>{waccPct.toFixed(2)}%</span>
              </div>
              <div style={{ fontSize: "0.70em", color: "var(--gv-text-muted)" }}>Set in Insights → WACC slider</div>
            </div>
            <div style={{ flex: 1, minWidth: 100 }}>
              <div style={{ fontSize: "0.74em", fontWeight: 600, color: NAVY, marginBottom: 3 }}>MoS %</div>
              <input
                type="number" value={mosPct} min={0} max={80} step={1}
                onChange={(e) => handleMosPct(Number(e.target.value))}
                style={{ width: "100%", padding: "4px 8px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.88em", fontFamily: "inherit", background: CLR_USER_BG }}
              />
            </div>
          </div>
        </div>

        {/* RIGHT: Quality Checklist */}
        <div>
          <div style={{ fontSize: "0.82em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginBottom: 6 }}>
            Quality Checklist
          </div>
          <Checklist items={checklistItems} />
        </div>
      </div>

      {/* ═══ SECTION 4 — IRR Analysis ══════════════════════════════════════════ */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: NAVY, borderRadius: 4, padding: "6px 15px",
        marginTop: 24, marginBottom: 8,
      }}>
        <span style={{ fontSize: "1.0em", fontWeight: 700, color: "#fff" }}>
          4 · IRR Analysis
        </span>
        <span style={{
          ...MONO, fontSize: "0.88em", fontWeight: 700,
          color: irr == null ? "#94a3b8" : irr >= 0.12 ? "#22c55e" : irr >= 0.08 ? "#f59e0b" : "#f87171",
          background: "rgba(0,0,0,0.25)", borderRadius: 4, padding: "2px 10px",
        }}>
          IRR: {irrPct}
        </span>
      </div>

      <SubHeader title="IRR Cash Flow Schedule" />
      <IrrCalculationTable
        fcfForecast={adjustedFcfForecast}
        avgTarget={weightedAvgTarget}
        priceNow={data.price_now}
        irr={data.irr}
      />

      {data.irr_sensitivity.matrix.length > 0 && (
        <>
          <SubHeader title="IRR Sensitivity — Entry Price vs. Exit FCF Yield  ·  ≥ 12% green · 8–12% amber · < 8% red" />
          <SensitivityMatrix
            rowLabels={data.irr_sensitivity.row_labels}
            colLabels={data.irr_sensitivity.col_labels}
            matrix={frontendMatrix}
            highlightRow={highlightRow}
          />
        </>
      )}

      <div style={{ height: 32 }} />
    </div>
  );
}
