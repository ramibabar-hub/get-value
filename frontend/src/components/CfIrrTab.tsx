/**
 * CfIrrTab.tsx
 * Cameron Stewart's CF + IRR Valuation Model — ported from cf_irr_tab.py.
 *
 * Sections:
 *  1. Quality Checklist  +  Final Output
 *  2. EBITDA Analysis (historical table + 9-yr forecast)
 *  3. Free Cash Flow Analysis (historical table + 9-yr forecast)
 *  4. IRR Sensitivity Matrix
 */
import { useState, useEffect, useRef, memo, useCallback } from "react";
import type { CfIrrData, OverviewData } from "../types";

const NAVY = "#1c2b46";
const CLR_PASS = "#d1fae5"; const CLR_PASS_FG = "#065f46";
const CLR_FAIL = "#fee2e2"; const CLR_FAIL_FG = "#991b1b";
const CLR_WARN = "#fef9c3"; const CLR_WARN_FG = "#92400e";
const CLR_NA   = "#f3f4f6"; const CLR_NA_FG   = "#6b7280";

// ── Formatters ─────────────────────────────────────────────────────────────────

const fMM  = (v: number | null | string) =>
  v == null || typeof v !== "number" || !isFinite(v) ? "N/A"
  : v < 0 ? `(${Math.abs(v / 1e6).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })})`
  : (v / 1e6).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const f$   = (v: number | null | string) =>
  v == null || typeof v !== "number" || !isFinite(v) ? "N/A"
  : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;


const fPctNum = (v: number) => `${v.toFixed(1)}%`;

const MONO: React.CSSProperties = {
  fontFamily: "'Courier New', monospace",
  fontVariantNumeric: "tabular-nums",
};

// ── Section header ──────────────────────────────────────────────────────────────

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginTop: 24, marginBottom: 8 }}>
      {title}
    </div>
  );
}

function SubHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "0.88em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginTop: 14, marginBottom: 4 }}>
      {title}
    </div>
  );
}

// ── Spinner ─────────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "#6b7280" }}>
      <div style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`, animation: "cfSpin 0.75s linear infinite", flexShrink: 0 }} />
      <span style={{ fontSize: "0.88em" }}>Computing CF + IRR model…</span>
      <style>{`@keyframes cfSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Historical table ──────────────────────────────────────────────────────────

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
    padding: "6px 10px", border: "1px solid #2d3f5a",
    fontSize: "0.77em", whiteSpace: "nowrap", textAlign: "right",
  };
  const allRows = [...rows, cagrRow, avgRow, thmRow];
  return (
    <div style={{ overflowX: "auto", marginBottom: 16 }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.79em", minWidth: "100%" }}>
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={c} style={{ ...thBase, textAlign: i === 0 ? "left" : "right", minWidth: i === 0 ? 80 : 100 }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {allRows.map((row, ri) => {
            const isSpecial = row["Year"] === "TTM" || row["Year"]?.startsWith("Average") || row["Year"]?.startsWith("CAGR");
            return (
              <tr key={ri} style={{
                background: isSpecial ? "#eff6ff" : ri % 2 === 0 ? "#fff" : "#f8fafc",
                fontWeight: isSpecial ? 700 : 400,
              }}>
                {columns.map((col, ci) => (
                  <td key={col} style={{
                    padding: "5px 10px", border: "1px solid #e5e7eb",
                    textAlign: ci === 0 ? "left" : "right",
                    ...MONO,
                    color: NAVY,
                    fontSize: "0.97em",
                  }}>
                    {row[col] ?? "—"}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});

// ── Checklist ─────────────────────────────────────────────────────────────────

const Checklist = memo(function Checklist({ items }: { items: CfIrrData["checklist"] }) {
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
            const bg = item.passed === true ? CLR_PASS : item.passed === false ? CLR_FAIL : CLR_NA;
            const fg = item.passed === true ? CLR_PASS_FG : item.passed === false ? CLR_FAIL_FG : CLR_NA_FG;
            const icon = item.passed === true ? "✅" : item.passed === false ? "❌" : "—";
            return (
              <tr key={i} style={{ background: bg }}>
                <td style={{ padding: "7px 12px", fontWeight: 600, color: fg, border: "1px solid #e5e7eb" }}>{item.label}</td>
                <td style={{ padding: "7px 12px", textAlign: "center", color: "#4d6b88", border: "1px solid #e5e7eb" }}>{item.threshold}</td>
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

// ── Final Output ──────────────────────────────────────────────────────────────

function FinalOutput({ data, waccPct, mosPct }: {
  data: CfIrrData;
  waccPct: number;
  mosPct: number;
}) {
  const waccDec = waccPct / 100;
  const fairValue = data.avg_target != null && waccDec > 0
    ? data.avg_target / (1 + waccDec) ** 9 : null;
  const buyPrice  = fairValue != null ? fairValue * (1 - mosPct / 100) : null;
  const onSale    = fairValue != null && data.price_now != null ? fairValue > data.price_now : null;

  const delta = (target: number | null, current: number | null) => {
    if (!target || !current || target === 0) return "N/A";
    const pct = (1 - current / target) * 100;
    return `${pct >= 0 ? "Upside" : "Downside"}  ${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
  };

  const rows: [string, string, boolean | null][] = [
    ["Average Target Price",          f$(data.avg_target),   null],
    ["WACC",                          `${waccPct.toFixed(2)}%`, null],
    ["Fair Value per share",          f$(fairValue),          null],
    [`Margin of Safety`,              `${mosPct.toFixed(0)}%`, null],
    ["Buy Price",                     f$(buyPrice),           null],
    ["Current Stock Price",           f$(data.price_now),     null],
    ["Company on-sale?",              onSale === true ? "✅ ON SALE" : onSale === false ? "❌ NOT ON SALE" : "N/A", onSale],
    ["Upside/Downside (vs. FV)",      delta(fairValue, data.price_now), null],
    ["Upside/Downside (vs. Buy)",     delta(buyPrice,  data.price_now), null],
  ];

  const thS: React.CSSProperties = { background: NAVY, color: "#fff", padding: "7px 12px", fontSize: "0.78em", border: "1px solid #2d3f5a" };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
      <thead><tr><th style={{ ...thS, textAlign: "left" }}>Metric</th><th style={{ ...thS, textAlign: "right" }}>Value</th></tr></thead>
      <tbody>
        {rows.map(([label, val, verdict], i) => {
          const bg = verdict === true ? CLR_PASS : verdict === false ? CLR_FAIL : i % 2 === 0 ? "#fff" : "#f8fafc";
          const fg = verdict === true ? CLR_PASS_FG : verdict === false ? CLR_FAIL_FG : NAVY;
          return (
            <tr key={i} style={{ background: bg }}>
              <td style={{ padding: "6px 12px", fontWeight: 600, color: fg, border: "1px solid #e5e7eb" }}>{label}</td>
              <td style={{ padding: "6px 12px", textAlign: "right", fontWeight: verdict !== null ? 700 : 400, color: fg, border: "1px solid #e5e7eb", ...MONO }}>{val}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Forecast table (editable growth rates) ────────────────────────────────────

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
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <span style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>Global Growth Rate (Yr 1):</span>
        <input
          type="number" value={globalRate} min={-50} max={200} step={0.5}
          onChange={(e) => onGlobalChange(Number(e.target.value))}
          style={{ width: 80, padding: "3px 8px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.83em", fontFamily: "inherit", textAlign: "right" }}
        />
        <span style={{ fontSize: "0.78em", color: "#6b7280" }}>%</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: "0.81em", minWidth: 500 }}>
          <thead>
            <tr>
              {["Year", "Est. Growth Rate (%)", valueLabel].map((h) => (
                <th key={h} style={{ background: NAVY, color: "#fff", padding: "6px 10px", border: "1px solid #2d3f5a", fontSize: "0.77em", textAlign: h === "Year" ? "left" : "right", whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#f8fafc" }}>
                <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", color: NAVY, fontWeight: 600 }}>{row.Year as string}</td>
                <td style={{ padding: "4px 8px", border: "1px solid #e5e7eb" }}>
                  <input
                    type="number" value={growthRates[i] ?? 5} step={0.5} min={-50} max={200}
                    onChange={(e) => onGrowthChange(i, Number(e.target.value))}
                    style={{ width: "100%", padding: "2px 6px", border: "1px solid #d1d5db", borderRadius: 3, fontSize: "0.9em", fontFamily: "'Courier New', monospace", textAlign: "right" }}
                  />
                </td>
                <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: NAVY }}>
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

// ── IRR Sensitivity Matrix ────────────────────────────────────────────────────

const SensitivityMatrix = memo(function SensitivityMatrix({
  rowLabels, colLabels, matrix,
}: {
  rowLabels: string[];
  colLabels: string[];
  matrix: (number | null)[][];
}) {
  const irrColor = (v: number | null): [string, string] => {
    if (v == null)  return [CLR_FAIL, CLR_FAIL_FG];
    if (v >= 0.12)  return [CLR_PASS, CLR_PASS_FG];
    if (v >= 0.08)  return [CLR_WARN, CLR_WARN_FG];
    return [CLR_FAIL, CLR_FAIL_FG];
  };
  const thS: React.CSSProperties = { background: NAVY, color: "#fff", padding: "6px 10px", fontSize: "0.76em", whiteSpace: "nowrap", border: "1px solid #2d3f5a" };
  return (
    <div style={{ overflowX: "auto", marginTop: 6 }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.81em" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left", minWidth: 130 }}>Entry Price</th>
            {colLabels.map((c) => <th key={c} style={{ ...thS, textAlign: "center", minWidth: 70 }}>Exit Yield {c}</th>)}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, ri) => (
            <tr key={ri}>
              <td style={{ padding: "6px 10px", background: "#f8fafc", color: NAVY, fontWeight: 600, fontSize: "0.78em", whiteSpace: "nowrap", border: "1px solid #e5e7eb" }}>
                {rowLabels[ri]}
              </td>
              {row.map((v, ci) => {
                const [bg, fg] = irrColor(v);
                return (
                  <td key={ci} style={{ padding: "6px 10px", background: bg, color: fg, fontWeight: 700, textAlign: "center", border: "1px solid #e5e7eb", ...MONO }}>
                    {v != null ? `${(v * 100).toFixed(1)}%` : "N/A"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  ticker: string;
  externalWacc: number;   // from Insights WACC slider (in %)
  ov?: OverviewData | null;  // company overview from StockDashboard (for PDF metadata)
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
  const [exitMult,  setExitMult]  = useState(15.0);
  const [exitYield, setExitYield] = useState(5.0);
  const [mosPct,    setMosPct]    = useState(10.0);

  // WACC: use external (from slider) if set, else use computed from backend
  const waccPct = externalWacc > 0 ? externalWacc : (data?.wacc_computed ?? 0) * 100;

  const [pdfLoading, setPdfLoading] = useState(false);

  const handleDownloadPdf = async () => {
    if (!data) return;
    setPdfLoading(true);
    try {
      // Derive fair value / buy price locally — identical to FinalOutput component
      // so the PDF exactly mirrors what the user sees on screen.
      const waccDec = waccPct / 100;
      const fv  = data.avg_target != null && waccDec > 0
        ? data.avg_target / Math.pow(1 + waccDec, 9) : null;
      const bp  = fv != null ? fv * (1 - mosPct / 100) : null;
      const os  = fv != null && data.price_now != null ? fv > data.price_now : null;

      const payload = {
        wacc_pct:     waccPct,
        mos_pct:      mosPct,
        exit_mult:    exitMult,
        exit_yield:   exitYield,
        // Company identity — from overview state, avoids extra API call in PDF endpoint
        company:      ov?.company_name  ?? "",
        sector:       ov?.sector        ?? "",
        industry:     ov?.industry      ?? "",
        description:  ov?.description   ?? "",
        // Historical tables — exactly what's rendered on screen
        ebt_hist:     data.ebt_hist,
        ebt_ttm:      data.ebt_ttm,
        ebt_avg:      data.ebt_avg,
        ebt_cagr:     data.ebt_cagr,
        fcf_hist:     data.fcf_hist,
        fcf_ttm:      data.fcf_ttm,
        fcf_avg:      data.fcf_avg,
        fcf_cagr:     data.fcf_cagr,
        // Forecast rows already reflect the user's current growth rate inputs
        ebt_forecast: data.ebt_forecast,
        fcf_forecast: data.fcf_forecast,
        // Checklist from live data
        checklist:    data.checklist,
        // Results — client-computed so they're 100% in sync with sliders
        price_now:    data.price_now,
        avg_target:   data.avg_target,
        fair_value:   fv,
        buy_price:    bp,
        on_sale:      os,
        irr:          data.irr,
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
      // Defer revoke — browser needs the URL alive until the download starts
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
  const handleExitMult  = (val: number) => { setExitMult(val);  refetch({ ebt: ebtGrowth, fcf: fcfGrowth, mult: val,   yld: exitYield, mos: mosPct }); };
  const handleExitYield = (val: number) => { setExitYield(val); refetch({ ebt: ebtGrowth, fcf: fcfGrowth, mult: exitMult, yld: val,   mos: mosPct }); };
  const handleMosPct    = (val: number) => { setMosPct(val);    refetch({ ebt: ebtGrowth, fcf: fcfGrowth, mult: exitMult, yld: exitYield, mos: val }); };

  if (loading) return <Spinner />;
  if (error)   return <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#991b1b" }}><strong>Error:</strong> {error}</div>;
  if (!data)   return null;

  const ebtHistCols = data.ebt_hist.length ? Object.keys(data.ebt_hist[0]) : [];
  const fcfHistCols = data.fcf_hist.length ? Object.keys(data.fcf_hist[0]) : [];

  const irr = data.irr;
  const irrPct = irr != null ? `${(irr * 100).toFixed(1)}%` : "N/A";
  const irrBg  = irr == null ? CLR_NA : irr >= 0.12 ? CLR_PASS : irr >= 0.08 ? CLR_WARN : CLR_FAIL;
  const irrFg  = irr == null ? CLR_NA_FG : irr >= 0.12 ? CLR_PASS_FG : irr >= 0.08 ? CLR_WARN_FG : CLR_FAIL_FG;

  return (
    <div>
      {/* Info banner + PDF download */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 18, flexWrap: "wrap" }}>
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

      {/* ═══ SECTION 1 — Checklist + Final Output ══════════════════════════════ */}
      <SecHeader title="1 · Quality Checklist  +  Final Output" />
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Checklist items={data.checklist} />
          <div style={{ marginTop: 10, padding: "10px 14px", borderRadius: 8, textAlign: "center", fontSize: "0.97em", fontWeight: 700,
            background: irrBg, color: irrFg, border: `1px solid ${irrBg}` }}>
            IRR (FCF method): {irrPct}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "1.0em", fontWeight: "bold", color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6 }}>
            Final Output
          </div>
          <FinalOutput data={data} waccPct={waccPct} mosPct={mosPct} />
          <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 120 }}>
              <div style={{ fontSize: "0.76em", fontWeight: 600, color: NAVY, marginBottom: 3 }}>WACC: <span style={{ color: "#b45309" }}>{waccPct.toFixed(2)}%</span></div>
              <div style={{ fontSize: "0.72em", color: "#6b7280" }}>Set in Insights → WACC slider</div>
            </div>
            <div style={{ flex: 1, minWidth: 100 }}>
              <div style={{ fontSize: "0.76em", fontWeight: 600, color: NAVY, marginBottom: 3 }}>MoS %</div>
              <input type="number" value={mosPct} min={0} max={80} step={1}
                onChange={(e) => handleMosPct(Number(e.target.value))}
                style={{ width: "100%", padding: "4px 8px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.9em", fontFamily: "inherit" }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ═══ SECTION 2 — EBITDA Analysis ══════════════════════════════════════ */}
      <SecHeader title="2 · EBITDA Analysis" />
      <SubHeader title="Table 2.1 · EV/EBITDA Historical  (values in $MM unless noted)" />
      <HistTable rows={data.ebt_hist} thmRow={data.ebt_ttm} avgRow={data.ebt_avg} cagrRow={data.ebt_cagr} columns={ebtHistCols} />

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <SubHeader title={`Table 2.2 · EBITDA Forecast  (${data.base_year + 1}–${data.base_year + 9})`} />
          <ForecastTable
            rows={data.ebt_forecast}
            growthRates={ebtGrowth}
            onGrowthChange={handleEbtGrowth}
            valueKey="Est. EBITDA ($MM)"
            valueLabel="Est. EBITDA ($MM)"
            globalRate={ebtGlobal}
            onGlobalChange={handleEbtGlobal}
          />
        </div>
        <div>
          <SubHeader title="Est. Stock Price — EBITDA Method" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>Exit EV/EBITDA Multiple:</span>
            <input type="number" value={exitMult} min={1} max={100} step={0.5}
              onChange={(e) => handleExitMult(Number(e.target.value))}
              style={{ width: 80, padding: "3px 8px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.9em", fontFamily: "inherit", textAlign: "right" }}
            />
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.81em" }}>
            <tbody>
              {[
                ["Est. EV/EBITDA Multiple", `${exitMult.toFixed(1)}x`],
                [`EV in ${(data.base_year + 9)} ($MM)`,
                  data.ebt_forecast.length
                    ? fMM((data.ebt_forecast[8]?.["Est. EBITDA ($MM)"] ?? 0) * exitMult * 1e6)
                    : "N/A"],
                ["Less: Net Debt TTM ($MM)", fMM(data.net_debt_ttm)],
                ["Est. Stock Price", f$(data.ebitda_price)],
              ].map(([label, val], i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#f8fafc" }}>
                  <td style={{ padding: "5px 10px", fontWeight: 600, color: NAVY, border: "1px solid #e5e7eb", fontSize: "0.9em" }}>{label}</td>
                  <td style={{ padding: "5px 10px", textAlign: "right", border: "1px solid #e5e7eb", ...MONO, color: NAVY }}>{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ═══ SECTION 3 — FCF Analysis ════════════════════════════════════════ */}
      <SecHeader title="3 · Free Cash Flow Analysis" />
      <SubHeader title="Table 3.1 · Adj. FCF/s Historical  (values in $MM unless noted)" />
      <HistTable rows={data.fcf_hist} thmRow={data.fcf_ttm} avgRow={data.fcf_avg} cagrRow={data.fcf_cagr} columns={fcfHistCols} />

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <SubHeader title={`Table 3.2 · Adj. FCF/s Forecast  (${data.base_year + 1}–${data.base_year + 9})`} />
          <ForecastTable
            rows={data.fcf_forecast}
            growthRates={fcfGrowth}
            onGrowthChange={handleFcfGrowth}
            valueKey="Est. Adj. FCF/s"
            valueLabel="Est. Adj. FCF/s ($)"
            globalRate={fcfGlobal}
            onGlobalChange={handleFcfGlobal}
          />
        </div>
        <div>
          <SubHeader title="Est. Stock Price — FCF/s Method" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>Long Term FCF/s Yield:</span>
            <input type="number" value={exitYield} min={0.5} max={50} step={0.5}
              onChange={(e) => handleExitYield(Number(e.target.value))}
              style={{ width: 70, padding: "3px 8px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.9em", fontFamily: "inherit", textAlign: "right" }}
            />
            <span style={{ fontSize: "0.8em", color: "#6b7280" }}>%</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.81em" }}>
            <tbody>
              {[
                ["Long Term FCF/s Yield", fPctNum(exitYield)],
                [`Est. Adj. FCF/s in ${data.base_year + 9}`,
                  data.fcf_forecast.length
                    ? `$${(data.fcf_forecast[8]?.["Est. Adj. FCF/s"] ?? 0).toFixed(2)}`
                    : "N/A"],
                ["Est. Stock Price", f$(data.fcf_price)],
              ].map(([label, val], i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#f8fafc" }}>
                  <td style={{ padding: "5px 10px", fontWeight: 600, color: NAVY, border: "1px solid #e5e7eb", fontSize: "0.9em" }}>{label}</td>
                  <td style={{ padding: "5px 10px", textAlign: "right", border: "1px solid #e5e7eb", ...MONO, color: NAVY }}>{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ═══ SECTION 4 — IRR Sensitivity Matrix ════════════════════════════════ */}
      {data.irr_sensitivity.matrix.length > 0 && (
        <>
          <SecHeader title="4 · IRR Sensitivity Matrix" />
          <SubHeader title="Entry Price vs. Exit FCF Yield  —  IRR ≥ 12% green · 8–12% amber · < 8% red" />
          <SensitivityMatrix
            rowLabels={data.irr_sensitivity.row_labels}
            colLabels={data.irr_sensitivity.col_labels}
            matrix={data.irr_sensitivity.matrix}
          />
        </>
      )}

      <div style={{ height: 32 }} />
    </div>
  );
}
