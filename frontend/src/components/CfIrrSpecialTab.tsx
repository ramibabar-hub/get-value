/**
 * CfIrrSpecialTab.tsx
 * Special Valuation Model: Tangible Book Value (TBV) + EPS
 * REDESIGNED to match CfIrrTab.tsx visual language — zero formula changes.
 *
 * TBV  = Total Assets − (Goodwill & Intangibles) − Total Liabilities
 * Terminal Value = tbvWeight × (TBV₁₀ × P/TBV) + (1−tbvWeight) × (EPS₁₀ × P/E)
 * IRR on: [−price, EPS₁..EPS₉, EPS₁₀ + TerminalValue]
 */
import { useState, useCallback, useEffect, useRef, memo } from "react";
import type { CfIrrSpecialData, CfIrrCheckItem, OverviewData } from "../types";

// ── Palette ───────────────────────────────────────────────────────────────────
const NAVY        = "var(--gv-navy)";
const CLR_API_BG  = "#dbeafe"; const CLR_API_FG  = "#1e40af";
const CLR_CALC_BG = "var(--gv-green-bg)"; const CLR_CALC_FG = "var(--gv-green)";
const CLR_USER_BG = "var(--gv-yellow-bg)"; const CLR_USER_FG = "var(--gv-yellow-fg)";
const CLR_PASS    = "var(--gv-green-bg)"; const CLR_PASS_FG = "var(--gv-green)";
const CLR_FAIL    = "var(--gv-red-bg)";   const CLR_FAIL_FG = "var(--gv-red)";
const CLR_WARN    = "var(--gv-yellow-bg)"; const CLR_WARN_FG = "#92400e";
const CLR_NA      = "var(--gv-data-bg)";  const CLR_NA_FG   = "var(--gv-text-muted)";

const MONO: React.CSSProperties = {
  fontFamily: "'Courier New', monospace",
  fontVariantNumeric: "tabular-nums",
};

// ── Formatters ────────────────────────────────────────────────────────────────
const f$ = (v: number | null | undefined) =>
  v == null || !isFinite(v) ? "N/A"
  : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const fPct = (v: number | null | undefined, decimals = 1) =>
  v == null || !isFinite(v) ? "N/A" : `${(v * 100).toFixed(decimals)}%`;

// ── Sector compatibility check ────────────────────────────────────────────────
const COMPAT_SECTORS    = ["financial", "insurance", "real estate", "financials", "finance", "banking"];
const COMPAT_INDUSTRIES = ["bank", "insurance", "financial institution", "holding", "reit", "real estate", "investment fund", "asset management", "diversified financial", "capital market"];

function isCompatibleSector(ov: OverviewData | null | undefined): boolean | null {
  if (!ov) return null;
  const s = (ov.sector   ?? "").toLowerCase();
  const i = (ov.industry ?? "").toLowerCase();
  return COMPAT_SECTORS.some((x) => s.includes(x)) || COMPAT_INDUSTRIES.some((x) => i.includes(x));
}

// ── IRR solver (Newton-Raphson) — mirrors CfIrrTab ────────────────────────────
function computeIrr(cfs: number[]): number | null {
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

// ── Shared UI atoms ───────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "var(--gv-text-muted)" }}>
      <div style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`, animation: "spSpin 0.75s linear infinite", flexShrink: 0 }} />
      <span style={{ fontSize: "0.88em" }}>Computing Special Model…</span>
      <style>{`@keyframes spSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "1.0em", fontWeight: 700, color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginTop: 24, marginBottom: 8 }}>
      {title}
    </div>
  );
}

function SubHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "0.82em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginTop: 12, marginBottom: 4 }}>
      {title}
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
        <span key={label} style={{ fontSize: "0.72em", fontWeight: 600, padding: "2px 8px", borderRadius: 3, background: bg, color: fg }}>{label}</span>
      ))}
    </div>
  );
}

// ── Sector Alert ──────────────────────────────────────────────────────────────

function SectorAlert({ ov }: { ov: OverviewData | null | undefined }) {
  const compat = isCompatibleSector(ov);
  if (compat === null) return null;
  if (compat) {
    return (
      <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 8, padding: "10px 16px", marginBottom: 16, fontSize: "0.83em", color: "#15803d" }}>
        ✅ <strong>Compatible Model:</strong> This valuation model is specifically designed for {ov?.sector ?? "Financial"} companies
        {ov?.industry ? ` (${ov.industry})` : ""}. Results should be meaningful and reliable.
      </div>
    );
  }
  return (
    <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, padding: "10px 16px", marginBottom: 16, fontSize: "0.83em", color: "#92400e" }}>
      ⚠️ <strong>Warning:</strong> This model is strictly designed for Financials, Real Estate, and Holding companies.
      It may not provide accurate results for <strong>{ov?.sector ?? "this"}</strong> sector
      {ov?.industry ? ` (${ov.industry})` : ""}. Use with caution.
    </div>
  );
}

// ── Historical table (columns-configurable) ───────────────────────────────────

const ALL_HIST_COLS = ["Year", "Assets ($B)", "GW&I ($B)", "Liab ($B)", "TBV/s", "EPS", "Net Margin"];

const HistTable = memo(function HistTable({ rows, ttm, avg, cagr, columns }: {
  rows:    Record<string, string>[];
  ttm:     Record<string, string>;
  avg:     Record<string, string>;
  cagr:    Record<string, string>;
  columns: string[];
}) {
  if (!rows.length) return null;
  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "5px 8px", border: "1px solid #2d3f5a",
    fontSize: "0.72em", whiteSpace: "nowrap",
  };
  const all = [...rows, cagr, avg, ttm];
  return (
    <div style={{ overflowX: "auto", marginBottom: 12 }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.76em", width: "100%" }}>
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={c} style={{ ...thBase, textAlign: i === 0 ? "left" : "right", minWidth: i === 0 ? 70 : 90 }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {all.map((row, ri) => {
            const yr = row["Year"] ?? "";
            const isSpecial = yr === "TTM" || yr.startsWith("Average") || yr.startsWith("CAGR");
            const rowBg = isSpecial ? CLR_CALC_BG : CLR_API_BG;
            const rowFg = isSpecial ? CLR_CALC_FG : CLR_API_FG;
            return (
              <tr key={ri} style={{ background: rowBg, fontWeight: isSpecial ? 700 : 400 }}>
                {columns.map((col, ci) => {
                  const raw = row[col];
                  const display = ci === 0 ? (raw?.startsWith("CAGR") ? "CAGR" : raw ?? "—") : (raw ?? "—");
                  return (
                    <td key={col} style={{
                      padding: "4px 8px", border: "1px solid #e5e7eb",
                      textAlign: ci === 0 ? "left" : "right",
                      color: ci === 0 ? NAVY : rowFg,
                      fontSize: "0.95em", ...MONO,
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

// ── Forecast table ────────────────────────────────────────────────────────────

function ForecastTable({
  rows, growthRates, onGrowthChange, valueKey, valueLabel, globalRate, onGlobalChange,
}: {
  rows: { Year: string; [k: string]: unknown }[];
  growthRates: number[];
  onGrowthChange: (i: number, v: number) => void;
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
                  {typeof row[valueKey] === "number" ? f$(row[valueKey] as number) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Weighting Table ───────────────────────────────────────────────────────────

function WeightingTable({ tbvTerminal, epsTerminal, avgTarget, tbvWeight, onTbvWeightChange }: {
  tbvTerminal: number | null;
  epsTerminal: number | null;
  avgTarget:   number | null;
  tbvWeight:   number;
  onTbvWeightChange: (w: number) => void;
}) {
  const epsWeight = 100 - tbvWeight;
  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "7px 14px",
    fontSize: "0.78em", border: "1px solid #2d3f5a", fontWeight: 700,
  };
  const rows = [
    { method: "TBV Method  (P/TBV)", weight: tbvWeight, terminal: tbvTerminal, onChange: (v: number) => onTbvWeightChange(Math.min(100, Math.max(0, v))) },
    { method: "P/E Method  (Earnings)", weight: epsWeight, terminal: epsTerminal, onChange: (v: number) => onTbvWeightChange(Math.min(100, Math.max(0, 100 - v))) },
  ];
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left" }}>Valuation Method</th>
            <th style={{ ...thS, textAlign: "center" }}>Weighting</th>
            <th style={{ ...thS, textAlign: "right" }}>Terminal Price</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ method, weight, terminal, onChange }, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#f8fafc" }}>
              <td style={{ padding: "7px 14px", fontWeight: 600, color: NAVY, border: "1px solid #e5e7eb" }}>{method}</td>
              <td style={{ padding: "4px 10px", textAlign: "center", border: "1px solid #e5e7eb", background: CLR_USER_BG }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4 }}>
                  <input
                    type="number" value={weight} min={0} max={100} step={5}
                    onChange={(e) => onChange(Number(e.target.value))}
                    style={{ width: 52, padding: "2px 5px", border: "1px solid #d1d5db", borderRadius: 3, fontSize: "0.88em", fontFamily: "'Courier New', monospace", textAlign: "right", background: CLR_USER_BG, color: CLR_USER_FG, fontWeight: 600 }}
                  />
                  <span style={{ fontSize: "0.85em", color: CLR_USER_FG, fontWeight: 600 }}>%</span>
                </div>
              </td>
              <td style={{ padding: "7px 14px", textAlign: "right", color: CLR_CALC_FG, background: CLR_CALC_BG, border: "1px solid #e5e7eb", ...MONO }}>{f$(terminal)}</td>
            </tr>
          ))}
          <tr style={{ background: CLR_CALC_BG }}>
            <td style={{ padding: "8px 14px", fontWeight: 700, color: CLR_CALC_FG, border: "1px solid #e5e7eb", fontSize: "1.0em" }}>Avg. Target Price</td>
            <td style={{ padding: "8px 14px", textAlign: "center", fontWeight: 700, color: CLR_CALC_FG, border: "1px solid #e5e7eb", ...MONO }}>{tbvWeight + epsWeight}%</td>
            <td style={{ padding: "8px 14px", textAlign: "right", fontWeight: 700, color: CLR_CALC_FG, border: "1px solid #e5e7eb", ...MONO, fontSize: "1.05em" }}>{f$(avgTarget)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ── Checklist ─────────────────────────────────────────────────────────────────

const Checklist = memo(function Checklist({ items }: { items: CfIrrCheckItem[] }) {
  const thS: React.CSSProperties = { background: NAVY, color: "#fff", padding: "7px 12px", fontSize: "0.78em", textAlign: "left", border: "1px solid #2d3f5a" };
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
            const bg   = item.passed === true ? CLR_PASS : item.passed === false ? CLR_FAIL : CLR_NA;
            const fg   = item.passed === true ? CLR_PASS_FG : item.passed === false ? CLR_FAIL_FG : CLR_NA_FG;
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

// ── Final Output (with tricolor) ──────────────────────────────────────────────

function FinalOutput({ data, waccPct, mosPct }: {
  data:    CfIrrSpecialData;
  waccPct: number;
  mosPct:  number;
}) {
  const waccDec   = waccPct / 100;
  const fairValue = data.avg_target != null && waccDec > 0 ? data.avg_target / (1 + waccDec) ** 9 : null;
  const buyPrice  = fairValue != null ? fairValue * (1 - mosPct / 100) : null;
  const onSale    = fairValue != null && data.price_now != null ? fairValue > data.price_now : null;
  const irrVerdict: boolean | null = data.irr != null ? data.irr >= 0.12 : null;

  const delta = (target: number | null, current: number | null) => {
    if (!target || !current || target === 0) return "N/A";
    const pct = (1 - current / target) * 100;
    return `${pct >= 0 ? "Upside" : "Downside"}  ${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
  };

  const rows: [string, string, boolean | null, "api" | "calc" | "user"][] = [
    ["TBV₁₀ × P/TBV Target",      f$(data.tbv_terminal),                                                                                    null,    "calc"],
    ["EPS₁₀ × P/E Target",         f$(data.eps_terminal),                                                                                    null,    "calc"],
    ["Average Target Price",        f$(data.avg_target),                                                                                      null,    "calc"],
    ["WACC",                        `${waccPct.toFixed(2)}%`,                                                                                 null,    "user"],
    ["Fair Value per share",        f$(fairValue),                                                                                            null,    "calc"],
    ["Margin of Safety",            `${mosPct.toFixed(0)}%`,                                                                                  null,    "user"],
    ["Buy Price",                   f$(buyPrice),                                                                                             null,    "calc"],
    ["Current Stock Price",         f$(data.price_now),                                                                                       null,    "api"],
    ["Company on-sale?",            onSale === true ? "✅ ON SALE" : onSale === false ? "❌ NOT ON SALE" : "N/A",                            onSale,  "calc"],
    ["Upside/Downside (vs. FV)",    delta(fairValue, data.price_now),                                                                        null,    "calc"],
    ["Upside/Downside (vs. Buy)",   delta(buyPrice,  data.price_now),                                                                        null,    "calc"],
    ["IRR",                         data.irr != null ? fPct(data.irr) : "N/A",                                                              irrVerdict, "calc"],
  ];

  const thS: React.CSSProperties = { background: NAVY, color: "#fff", padding: "7px 12px", fontSize: "0.78em", border: "1px solid #2d3f5a" };
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

// ── IRR Calculation Table ─────────────────────────────────────────────────────

function IrrCalculationTable({ data, baseYear, frontendIrr }: {
  data:        CfIrrSpecialData;
  baseYear:    number;
  frontendIrr: number | null;
}) {
  if (!data.eps_forecast.length || data.price_now == null || data.avg_target == null) return null;

  const lastIdx   = data.eps_forecast.length - 1;
  const displayIrr = frontendIrr ?? data.irr;
  const irrColor = (v: number | null) =>
    v == null ? CLR_NA_FG : v >= 0.12 ? CLR_PASS_FG : v >= 0.08 ? CLR_WARN_FG : CLR_FAIL_FG;
  const irrBg = (v: number | null) =>
    v == null ? CLR_NA : v >= 0.12 ? CLR_PASS : v >= 0.08 ? CLR_WARN : CLR_FAIL;

  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "6px 12px",
    fontSize: "0.76em", border: "1px solid #2d3f5a", fontWeight: 700,
  };

  // Build rows: Year 0 = entry, Years 1-9 = EPS forecast
  const tableRows: { year: string; isEntry: boolean; isFinal: boolean; eps: number | null; price: number | null }[] = [
    { year: `0  (${baseYear})`, isEntry: true,  isFinal: false, eps: data.eps_forecast[0]?.["Est. EPS"] ?? null, price: data.price_now },
    ...data.eps_forecast.map((r, i) => ({
      year: r.Year, isEntry: false, isFinal: i === lastIdx,
      eps: r["Est. EPS"] ?? null, price: i === lastIdx ? data.avg_target : null,
    })),
  ];

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.81em", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left",  minWidth: 100 }}>Year</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 110 }}>Price (Entry/Exit)</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 90  }}>Est. EPS</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 120 }}>Total Cash Flow</th>
          </tr>
        </thead>
        <tbody>
          {tableRows.map((r, i) => {
            const { isEntry, isFinal } = r;
            // Price column display
            const priceDisplay = isEntry
              ? (r.price != null ? `($${r.price.toFixed(2)})` : "—")
              : isFinal
                ? f$(r.price)
                : "—";
            const priceFg = isEntry ? CLR_API_FG : isFinal ? CLR_CALC_FG : "var(--gv-text-muted)";
            const priceBg = isEntry ? CLR_API_BG : isFinal ? CLR_CALC_BG : "transparent";

            // EPS display (year 0 = entry has no EPS income)
            const epsVal = !isEntry ? r.eps : null;

            // Total CF
            let totalCf: number | null = null;
            if (isEntry && r.price != null) {
              totalCf = (r.eps ?? 0) - r.price;  // first year EPS - entry price
            } else if (isFinal && r.eps != null && r.price != null) {
              totalCf = r.eps + r.price;
            } else {
              totalCf = r.eps;
            }
            // For entry row, show just the negative entry cost (no EPS in year 0 of original model)
            if (isEntry) {
              totalCf = r.price != null ? -r.price : null;
            }

            const totalDisplay = totalCf != null
              ? totalCf < 0 ? `($${Math.abs(totalCf).toFixed(2)})` : `$${totalCf.toFixed(2)}`
              : "—";

            return (
              <tr key={i} style={{
                background: isFinal ? CLR_CALC_BG : isEntry ? CLR_API_BG : i % 2 === 0 ? "#fff" : "#f8fafc",
                fontWeight: (isEntry || isFinal) ? 700 : 400,
              }}>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", color: NAVY, fontWeight: 600 }}>{r.year}</td>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: priceFg, background: priceBg }}>
                  {priceDisplay}
                </td>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: isEntry ? "var(--gv-text-muted)" : CLR_CALC_FG, background: isEntry ? "transparent" : CLR_CALC_BG }}>
                  {epsVal != null ? `$${epsVal.toFixed(2)}` : "—"}
                </td>
                <td style={{ padding: "5px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: CLR_CALC_FG, background: CLR_CALC_BG, fontWeight: (isEntry || isFinal) ? 700 : 400 }}>
                  {totalDisplay}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr style={{ background: irrBg(displayIrr), fontWeight: 700 }}>
            <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", color: irrColor(displayIrr), fontSize: "1.0em" }}>IRR</td>
            <td style={{ border: "1px solid #e5e7eb" }} />
            <td style={{ border: "1px solid #e5e7eb" }} />
            <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: irrColor(displayIrr), fontSize: "1.05em" }}>
              {displayIrr != null ? `${(displayIrr * 100).toFixed(1)}%` : "N/A"}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  ticker:       string;
  externalWacc: number;
  ov?:          OverviewData | null;
}

export default function CfIrrSpecialTab({ ticker, externalWacc, ov }: Props) {
  const [data,    setData]    = useState<CfIrrSpecialData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  // ── User-editable inputs ──────────────────────────────────────────────────
  const [tbvGrowth,  setTbvGrowth]  = useState<number[]>([5, 5, 5, 5, 5, 5, 5, 5, 5]);
  const [tbvGlobal,  setTbvGlobal]  = useState(5);
  const [epsGrowth,  setEpsGrowth]  = useState<number[]>([5, 5, 5, 5, 5, 5, 5, 5, 5]);
  const [epsGlobal,  setEpsGlobal]  = useState(5);
  const [exitPtbv,   setExitPtbv]   = useState(1.5);
  const [exitPe,     setExitPe]     = useState(15.0);
  const [tbvWeight,  setTbvWeight]  = useState(50);
  const [mosPct,     setMosPct]     = useState(10.0);

  const waccPct = externalWacc > 0 ? externalWacc : (data?.wacc_computed ?? 0) * 100;

  const seeded   = useRef(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // ── URL builder (unchanged) ───────────────────────────────────────────────
  const buildUrl = useCallback((opts?: {
    tbv?: number[]; eps?: number[]; ptbv?: number; pe?: number;
    wt?: number; mos?: number;
  }) => {
    const tg = opts?.tbv  ?? tbvGrowth;
    const eg = opts?.eps  ?? epsGrowth;
    const pt = opts?.ptbv ?? exitPtbv;
    const pe = opts?.pe   ?? exitPe;
    const wt = (opts?.wt  ?? tbvWeight) / 100;
    const mp = opts?.mos  ?? mosPct;
    const qs = new URLSearchParams({
      tbv_growth:    tg.join(","),
      eps_growth:    eg.join(","),
      exit_ptbv:     String(pt),
      exit_pe:       String(pe),
      tbv_weight:    String(wt),
      mos_pct:       String(mp),
      wacc_override: String(waccPct),
    });
    return `/api/cf-irr-special/${ticker}?${qs}`;
  }, [ticker, tbvGrowth, epsGrowth, exitPtbv, exitPe, tbvWeight, mosPct, waccPct]);

  // ── Initial load (unchanged) ──────────────────────────────────────────────
  useEffect(() => {
    seeded.current = false;
    setData(null); setError(null); setLoading(true);
    setTbvGrowth([5,5,5,5,5,5,5,5,5]);
    setEpsGrowth([5,5,5,5,5,5,5,5,5]);
    setExitPtbv(1.5); setExitPe(15.0); setTbvWeight(50); setMosPct(10.0);
  }, [ticker]);

  useEffect(() => {
    if (!loading && data) return;
    fetch(buildUrl())
      .then((r) => r.ok ? r.json() : r.json().then((b: { detail?: string }) => Promise.reject(b.detail ?? `HTTP ${r.status}`)))
      .then((d: CfIrrSpecialData) => {
        setData(d);
        if (!seeded.current) {
          seeded.current = true;
          setTbvGrowth(d.tbv_growth_rates);
          setTbvGlobal(d.tbv_growth_rates[0] ?? 5);
          setEpsGrowth(d.eps_growth_rates);
          setEpsGlobal(d.eps_growth_rates[0] ?? 5);
          setExitPtbv(d.exit_ptbv);
          setExitPe(d.exit_pe);
          setTbvWeight(Math.round(d.tbv_weight * 100));
          setMosPct(d.mos_pct);
        }
      })
      .catch((e: unknown) => setError(typeof e === "string" ? e : "Failed to load"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  // ── Debounced refetch (unchanged) ─────────────────────────────────────────
  const refetch = useCallback((opts?: Parameters<typeof buildUrl>[0]) => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      fetch(buildUrl(opts))
        .then((r) => r.ok ? r.json() : r.json().then((b: { detail?: string }) => Promise.reject(b.detail ?? `HTTP ${r.status}`)))
        .then((d: CfIrrSpecialData) => setData(d))
        .catch((e: unknown) => setError(typeof e === "string" ? e : "Refetch failed"));
    }, 350);
  }, [buildUrl]);

  // ── Handlers (unchanged) ──────────────────────────────────────────────────
  const handleTbvGrowth = (i: number, v: number) => { const next = [...tbvGrowth]; next[i] = v; setTbvGrowth(next); refetch({ tbv: next }); };
  const handleTbvGlobal = (v: number) => { setTbvGlobal(v); const next = [...tbvGrowth]; next[0] = v; setTbvGrowth(next); refetch({ tbv: next }); };
  const handleEpsGrowth = (i: number, v: number) => { const next = [...epsGrowth]; next[i] = v; setEpsGrowth(next); refetch({ eps: next }); };
  const handleEpsGlobal = (v: number) => { setEpsGlobal(v); const next = [...epsGrowth]; next[0] = v; setEpsGrowth(next); refetch({ eps: next }); };
  const handleExitPtbv  = (v: number) => { setExitPtbv(v); refetch({ ptbv: v }); };
  const handleExitPe    = (v: number) => { setExitPe(v);   refetch({ pe: v }); };
  const handleTbvWt     = (v: number) => { setTbvWeight(v); refetch({ wt: v }); };
  const handleMos       = (v: number) => { setMosPct(v);   refetch({ mos: v }); };

  if (loading && !data) return <Spinner />;
  if (error) return <div style={{ background: "var(--gv-red-bg)", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "var(--gv-red)" }}><strong>Error:</strong> {error}</div>;
  if (!data) return null;

  const baseYear = data.base_year;

  // ── Frontend IRR from displayed cash flows ────────────────────────────────
  const irrCfs: number[] = [];
  if (data.price_now != null) {
    irrCfs.push(-data.price_now);
    for (let i = 0; i < data.eps_forecast.length; i++) {
      const eps = data.eps_forecast[i]?.["Est. EPS"] ?? 0;
      if (i === data.eps_forecast.length - 1 && data.avg_target != null) {
        irrCfs.push(eps + data.avg_target);
      } else {
        irrCfs.push(eps);
      }
    }
  }
  const frontendIrr = irrCfs.length > 0 ? computeIrr(irrCfs) : null;
  const irr    = frontendIrr ?? data.irr;
  const irrPct = irr != null ? `${(irr * 100).toFixed(1)}%` : "N/A";

  // ── Split hist columns ────────────────────────────────────────────────────
  const tbvHistCols = ALL_HIST_COLS.filter((c) => ["Year", "Assets ($B)", "GW&I ($B)", "Liab ($B)", "TBV/s"].includes(c));
  const epsHistCols = ALL_HIST_COLS.filter((c) => ["Year", "EPS", "Net Margin"].includes(c));

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ paddingBottom: 40 }}>

      {/* ═══ SECTION 0 — Banner ══════════════════════════════════════════════ */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 260, background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, padding: "10px 16px", fontSize: "0.83em", color: "#1e40af" }}>
          <strong>How to use:</strong> Review historical TBV/s and EPS trends, then set per-year growth
          rates and exit multiples. The TBV terminal and EPS terminal values are blended by weight
          to form the Avg. Target Price, which is discounted at WACC to compute Fair Value.
          IRR is calculated from projected EPS cash flows.
        </div>
      </div>

      {/* Sector compatibility alert */}
      <SectorAlert ov={ov} />

      {/* ═══ SECTION 1 — Dual-path Analysis Grid ════════════════════════════ */}
      <Legend />
      <div className="grid grid-cols-2 gap-6">

        {/* ── LEFT: TBV Analysis ─────────────────────────────────────────── */}
        <div>
          <SecHeader title="TBV Analysis" />

          <SubHeader title="1.1 · Tangible Book Value Historical  (values in $B unless noted)" />
          <HistTable
            rows={data.hist} ttm={data.hist_ttm} avg={data.hist_avg} cagr={data.hist_cagr}
            columns={tbvHistCols}
          />

          <SubHeader title={`1.2 · TBV/s Forecast  (${baseYear + 1}–${baseYear + 9})`} />
          <ForecastTable
            rows={data.tbv_forecast}
            growthRates={tbvGrowth}
            onGrowthChange={handleTbvGrowth}
            valueKey="Est. TBV/s"
            valueLabel="Est. TBV/s ($)"
            globalRate={tbvGlobal}
            onGlobalChange={handleTbvGlobal}
          />

          <SubHeader title="Est. Stock Price — TBV Method" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: "0.74em", fontWeight: 600, color: NAVY }}>Exit P/TBV Multiple:</span>
            <input
              type="number" value={exitPtbv} min={0.5} max={10} step={0.1}
              onChange={(e) => handleExitPtbv(Number(e.target.value))}
              style={{ width: 76, padding: "2px 6px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.88em", fontFamily: "inherit", textAlign: "right", background: CLR_USER_BG }}
            />
            <span style={{ fontSize: "0.78em", color: "var(--gv-text-muted)" }}>x</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.81em" }}>
            <tbody>
              {([
                ["Est. P/TBV Multiple",       `${exitPtbv.toFixed(2)}x`,                                  "user"],
                [`TBV/s in ${baseYear + 9}`,  f$(data.tbv_forecast[8]?.["Est. TBV/s"]),                   "calc"],
                ["TBV Terminal Price",         f$(data.tbv_terminal),                                      "calc"],
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

        {/* ── RIGHT: EPS Analysis ────────────────────────────────────────── */}
        <div>
          <SecHeader title="EPS Analysis" />

          <SubHeader title="2.1 · EPS Historical" />
          <HistTable
            rows={data.hist} ttm={data.hist_ttm} avg={data.hist_avg} cagr={data.hist_cagr}
            columns={epsHistCols}
          />

          {/* CAGR Summary Tiles */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, marginBottom: 12 }}>
            {[
              ["Assets CAGR", data.assets_cagr != null ? fPct(data.assets_cagr) : "N/A", data.assets_cagr != null ? data.assets_cagr >= 0.04 : null],
              ["TBV/s CAGR",  data.tbv_ps_cagr != null ? fPct(data.tbv_ps_cagr) : "N/A", data.tbv_ps_cagr != null ? data.tbv_ps_cagr >= 0.03 : null],
              ["EPS CAGR",    data.eps_cagr != null ? fPct(data.eps_cagr) : "N/A", data.eps_cagr != null ? data.eps_cagr >= 0.10 : null],
              ["Avg Margin",  data.margin_avg != null ? fPct(data.margin_avg) : "N/A", data.margin_avg != null ? data.margin_avg >= 0.10 : null],
            ].map(([label, val, passed]) => (
              <div key={label as string} style={{
                background: passed === true ? CLR_PASS : passed === false ? CLR_FAIL : CLR_NA,
                borderRadius: 5, padding: "7px 10px", textAlign: "center",
              }}>
                <div style={{ fontSize: "0.62em", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--gv-text-dim)", marginBottom: 3 }}>{label}</div>
                <div style={{ fontSize: "1.05em", fontWeight: 800, color: passed === true ? CLR_PASS_FG : passed === false ? CLR_FAIL_FG : NAVY }}>{val as string}</div>
              </div>
            ))}
          </div>

          <SubHeader title={`2.2 · EPS Forecast  (${baseYear + 1}–${baseYear + 9})`} />
          <ForecastTable
            rows={data.eps_forecast}
            growthRates={epsGrowth}
            onGrowthChange={handleEpsGrowth}
            valueKey="Est. EPS"
            valueLabel="Est. EPS ($)"
            globalRate={epsGlobal}
            onGlobalChange={handleEpsGlobal}
          />

          <SubHeader title="Est. Stock Price — P/E Method" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: "0.74em", fontWeight: 600, color: NAVY }}>Exit P/E Multiple:</span>
            <input
              type="number" value={exitPe} min={5} max={50} step={0.5}
              onChange={(e) => handleExitPe(Number(e.target.value))}
              style={{ width: 76, padding: "2px 6px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.88em", fontFamily: "inherit", textAlign: "right", background: CLR_USER_BG }}
            />
            <span style={{ fontSize: "0.78em", color: "var(--gv-text-muted)" }}>x</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.81em" }}>
            <tbody>
              {([
                ["Est. P/E Multiple",          `${exitPe.toFixed(1)}x`,                              "user"],
                [`EPS in ${baseYear + 9}`,     f$(data.eps_forecast[8]?.["Est. EPS"]),               "calc"],
                ["EPS Terminal Price",          f$(data.eps_terminal),                                "calc"],
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

      {/* ═══ SECTION 2 — Weighting Table ════════════════════════════════════ */}
      <SecHeader title="2 · Weighting  —  Avg. Target Price" />
      <div style={{ marginBottom: 8, fontSize: "0.79em", color: "var(--gv-text-muted)", lineHeight: 1.5 }}>
        Terminal Value = <strong>{tbvWeight}%</strong> × TBV Terminal ({exitPtbv.toFixed(2)}x P/TBV) + <strong>{100 - tbvWeight}%</strong> × EPS Terminal ({exitPe.toFixed(1)}x P/E)
      </div>
      <WeightingTable
        tbvTerminal={data.tbv_terminal}
        epsTerminal={data.eps_terminal}
        avgTarget={data.avg_target}
        tbvWeight={tbvWeight}
        onTbvWeightChange={handleTbvWt}
      />

      {/* ═══ SECTION 3 — Final Output + Quality Checklist ════════════════════ */}
      <SecHeader title="3 · Final Output  +  Quality Checklist" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>

        {/* LEFT: Final Output */}
        <div>
          <div style={{ fontSize: "0.82em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginBottom: 6 }}>
            Final Output
          </div>
          <FinalOutput data={data} waccPct={waccPct} mosPct={mosPct} />

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
                onChange={(e) => handleMos(Number(e.target.value))}
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
          <Checklist items={data.checklist} />
        </div>
      </div>

      {/* ═══ SECTION 4 — IRR Analysis ════════════════════════════════════════ */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: NAVY, borderRadius: 4, padding: "6px 15px",
        marginTop: 24, marginBottom: 8,
      }}>
        <span style={{ fontSize: "1.0em", fontWeight: 700, color: "#fff" }}>4 · IRR Analysis</span>
        <span style={{
          ...MONO, fontSize: "0.88em", fontWeight: 700,
          color: irr == null ? "#94a3b8" : irr >= 0.12 ? "#22c55e" : irr >= 0.08 ? "#f59e0b" : "#f87171",
          background: "rgba(0,0,0,0.25)", borderRadius: 4, padding: "2px 10px",
        }}>
          IRR: {irrPct}
        </span>
      </div>

      <SubHeader title="IRR Cash Flow Schedule" />
      <IrrCalculationTable data={data} baseYear={baseYear} frontendIrr={frontendIrr} />

      <div style={{ height: 32 }} />
    </div>
  );
}
