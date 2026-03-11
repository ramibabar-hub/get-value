/**
 * IndustryMultipleTab.tsx — Industry Multiple Valuation Model
 *
 * Architecture
 * ────────────
 * • Fetches IMultipleData ONCE per ticker from GET /api/industry-multiple/{ticker}
 * • All valuation math is computed inline in React (no re-fetch on input change)
 * • Exports weighted fair value to parent via onFairValueChange callback
 *
 * Sections
 * ────────
 * 1. Historical Table + Interactive Multiples Chart (side-by-side)
 * 2. By Industry PE    — Avg EPS × Industry PE = Fair Value
 * 3. By Industry EV/EBITDA — (Avg EBITDA × Multiple − Net Debt) / Shares = FV
 * 4. Combined Valuation — 50/50 weighted Fair Value, single MoS, Buy Price
 */

import { useState, useEffect, useMemo, memo } from "react";
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import type { IMultipleData, IMultipleHistRow } from "../types";

// ── Palette ────────────────────────────────────────────────────────────────────
const NAVY     = "#1c2b46";
const BLUE     = "#1d4ed8";
const GREEN    = "#16a34a";
const RED      = "#dc2626";
const AMBER    = "#b45309";
const PE_CLR   = "#1d4ed8";   // deep blue  — PE line
const EVEB_CLR = "#16a34a";   // emerald    — EV/EBITDA line
const MONO: React.CSSProperties = { fontFamily: "'Courier New', monospace", fontVariantNumeric: "tabular-nums" };

// ── Formatters ─────────────────────────────────────────────────────────────────
const fPrice = (v: number | null) =>
  v == null || !isFinite(v) ? "—" : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fEps = (v: number | null) =>
  v == null || !isFinite(v) ? "—" : `$${v.toFixed(2)}`;
const fMult = (v: number | null) =>
  v == null || !isFinite(v) ? "—" : `${v.toFixed(1)}x`;
const fPct = (v: number | null) =>
  v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(1)}%`;
const fMM = (v: number | null) =>
  v == null || !isFinite(v) ? "—" : `$${v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}M`;
const fUpside = (fv: number | null, price: number | null): string => {
  if (!fv || !price || price <= 0) return "—";
  const pct = ((fv / price) - 1) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "#6b7280" }}>
      <div style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`, animation: "imSpin 0.75s linear infinite", flexShrink: 0 }} />
      <span style={{ fontSize: "0.88em" }}>Loading Industry Multiple data…</span>
      <style>{`@keyframes imSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginTop: 24, marginBottom: 8 }}>
      {title}
    </div>
  );
}

// ── Number input row ──────────────────────────────────────────────────────────

function InputRow({ label, value, onChange, prefix = "", step = 0.01, min = 0, note }: {
  label: string; value: number; onChange: (v: number) => void;
  prefix?: string; step?: number; min?: number; note?: string;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: "1px solid #f0f3f7", fontSize: "0.87em" }}>
      <span style={{ color: "#4d6b88", fontWeight: 500 }}>
        {label}
        {note && <span style={{ marginLeft: 6, color: "#9ca3af", fontWeight: 400, fontSize: "0.88em" }}>{note}</span>}
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        {prefix && <span style={{ color: NAVY, fontWeight: 600, ...MONO }}>{prefix}</span>}
        <input
          type="number" value={value} step={step} min={min}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ width: 90, padding: "3px 8px", border: `1px solid #d1d5db`, borderRadius: 4, fontSize: "0.9em", ...MONO, textAlign: "right" }}
        />
      </div>
    </div>
  );
}

// ── Static display row ────────────────────────────────────────────────────────

function DataRow({ label, value, color, bold }: { label: string; value: string; color?: string; bold?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: "1px solid #f0f3f7", fontSize: "0.87em" }}>
      <span style={{ color: "#4d6b88", fontWeight: 500 }}>{label}</span>
      <span style={{ fontWeight: bold ? 700 : 600, color: color ?? NAVY, ...MONO }}>{value}</span>
    </div>
  );
}

// ── On-Sale badge ─────────────────────────────────────────────────────────────

function OnSaleBadge({ onSale }: { onSale: boolean | null }) {
  if (onSale === null) return <span style={{ color: "#9ca3af", fontWeight: 600, fontSize: "0.87em" }}>—</span>;
  return (
    <span style={{
      display: "inline-block", padding: "3px 12px", borderRadius: 20, fontWeight: 700, fontSize: "0.82em",
      background: onSale ? GREEN : RED, color: "#fff",
    }}>
      {onSale ? "✓ ON SALE" : "✗ NOT ON SALE"}
    </span>
  );
}

// ── Historical table ──────────────────────────────────────────────────────────

const HistTable = memo(function HistTable({ hist, ttm, avg10 }: {
  hist: IMultipleHistRow[];
  ttm:  IMultipleHistRow;
  avg10: IMultipleHistRow;
}) {
  // Display: most-recent LEFT → oldest RIGHT, TTM first
  const displayRows = [ttm, ...([...hist].reverse()), avg10];

  // P/S and P/FCF removed per design spec
  const COL_DEFS: { key: keyof IMultipleHistRow; label: string; fmt: (v: IMultipleHistRow[keyof IMultipleHistRow]) => string }[] = [
    { key: "price",        label: "Price",       fmt: (v) => fPrice(v as number | null) },
    { key: "price_growth", label: "Price Gr.",   fmt: (v) => fPct(v as number | null) },
    { key: "eps",          label: "EPS",         fmt: (v) => fEps(v as number | null) },
    { key: "eps_growth",   label: "EPS Gr.",     fmt: (v) => fPct(v as number | null) },
    { key: "pe",           label: "P/E",         fmt: (v) => fMult(v as number | null) },
    { key: "ev_ebitda",    label: "EV/EBITDA",   fmt: (v) => fMult(v as number | null) },
  ];

  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "6px 10px",
    border: "1px solid #2d3f5a", fontSize: "0.77em",
    fontWeight: 700, whiteSpace: "nowrap", textAlign: "right",
  };
  const tdS = (special = false, isAvg = false): React.CSSProperties => ({
    padding: "5px 10px", border: "1px solid #e5e7eb",
    textAlign: "right", fontWeight: special ? 700 : 400,
    color: isAvg ? AMBER : special ? BLUE : NAVY,
    background: isAvg ? "#fefce8" : special ? "#eff6ff" : undefined,
    ...MONO, fontSize: "0.87em",
  });

  return (
    <div style={{ overflowX: "auto", marginBottom: 8 }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.83em", minWidth: "100%" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left", minWidth: 90 }}>Metric</th>
            {displayRows.map((r) => (
              <th key={r.year} style={{ ...thS, minWidth: 90 }}>
                {r.year === "TTM" ? <span style={{ color: "#93c5fd" }}>TTM</span>
                  : r.year === "Avg. 10yr" ? <span style={{ color: "#fde68a" }}>Avg. 10yr</span>
                  : r.year}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {COL_DEFS.map(({ key, label, fmt }) => (
            <tr key={key}>
              <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY, whiteSpace: "nowrap" }}>
                {label}
              </td>
              {displayRows.map((r) => {
                const isTtm  = r.year === "TTM";
                const isAvg  = r.year === "Avg. 10yr";
                const val    = r[key];
                const isPct  = key === "price_growth" || key === "eps_growth";
                const numVal = typeof val === "number" ? val : null;
                const colored = isPct && numVal !== null
                  ? { color: numVal >= 0 ? GREEN : RED }
                  : {};
                return (
                  <td key={r.year} style={{ ...tdS(isTtm, isAvg), ...colored }}>
                    {fmt(val)}
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

// ── Multiples Chart Tooltip ────────────────────────────────────────────────────

function MultTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: { name: string; value: number | null; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
      padding: "8px 12px", boxShadow: "0 4px 16px rgba(0,0,0,0.10)", fontSize: "0.78em",
    }}>
      <div style={{ color: "#7b8899", fontWeight: 600, marginBottom: 5 }}>{label}</div>
      {payload.map((p) => p.value != null && (
        <div key={p.name} style={{ display: "flex", justifyContent: "space-between", gap: 16, color: p.color, fontWeight: 700, marginBottom: 2 }}>
          <span>{p.name}</span>
          <span style={{ fontFamily: "'Courier New', monospace" }}>{p.value.toFixed(1)}x</span>
        </div>
      ))}
    </div>
  );
}

// ── Interactive Multiples Chart ───────────────────────────────────────────────

type ChartView  = "PE" | "EV/EBITDA" | "Both";
type ChartRange = "3Y" | "5Y" | "10Y" | "MAX";

function MultiplesChart({ hist, ttm }: { hist: IMultipleHistRow[]; ttm: IMultipleHistRow }) {
  const [view,  setView]  = useState<ChartView>("Both");
  const [range, setRange] = useState<ChartRange>("10Y");

  // Sort annual history chronologically (oldest first)
  const sortedHist = useMemo(() => [...hist].sort((a, b) => a.year.localeCompare(b.year)), [hist]);

  // Slice based on selected time range, always append TTM
  const slicedData = useMemo(() => {
    const ttmPoint = { ...ttm, year: "TTM" };
    if (range === "MAX") return [...sortedHist, ttmPoint];
    const n = range === "3Y" ? 3 : range === "5Y" ? 5 : 10;
    return [...sortedHist.slice(-n), ttmPoint];
  }, [sortedHist, ttm, range]);

  // Chart-ready data (null-guard)
  const chartData = useMemo(() => slicedData.map(r => ({
    year:      r.year,
    pe:        r.pe        != null && isFinite(r.pe)        ? r.pe        : null,
    ev_ebitda: r.ev_ebitda != null && isFinite(r.ev_ebitda) ? r.ev_ebitda : null,
  })), [slicedData]);

  // Average for selected range
  const avgPe = useMemo(() => {
    const vals = chartData.map(d => d.pe).filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }, [chartData]);

  const avgEvEb = useMemo(() => {
    const vals = chartData.map(d => d.ev_ebitda).filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }, [chartData]);

  const showPe   = view === "PE"        || view === "Both";
  const showEvEb = view === "EV/EBITDA" || view === "Both";

  // Y-axis domain
  const allVals = chartData.flatMap(d => [
    showPe   ? d.pe        : null,
    showEvEb ? d.ev_ebitda : null,
  ]).filter((v): v is number => v != null && v > 0);
  const minV = allVals.length ? Math.min(...allVals) : 0;
  const maxV = allVals.length ? Math.max(...allVals) : 30;
  const pad  = (maxV - minV) * 0.2 || 3;

  // Pill button styles
  const pillStyle = (active: boolean, activeColor: string): React.CSSProperties => ({
    padding: "3px 10px", fontSize: "0.73em", fontWeight: active ? 700 : 500,
    borderRadius: 6, border: `1px solid ${active ? activeColor : "#d1d5db"}`,
    background: active ? activeColor : "#fff", color: active ? "#fff" : "#6b7280",
    cursor: "pointer", transition: "all 0.12s",
  });

  return (
    <div>
      {/* Controls */}
      <div style={{ display: "flex", gap: 10, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
        {/* View selector */}
        <div style={{ display: "flex", gap: 3 }}>
          {(["PE", "EV/EBITDA", "Both"] as ChartView[]).map(v => (
            <button key={v} onClick={() => setView(v)} style={pillStyle(v === view, NAVY)}>{v}</button>
          ))}
        </div>
        <div style={{ width: 1, height: 20, background: "#e5e7eb", flexShrink: 0 }} />
        {/* Range selector */}
        <div style={{ display: "flex", gap: 3 }}>
          {(["3Y", "5Y", "10Y", "MAX"] as ChartRange[]).map(r => (
            <button key={r} onClick={() => setRange(r)} style={pillStyle(r === range, "#2563eb")}>{r}</button>
          ))}
        </div>
      </div>

      {/* Average legend badges */}
      <div style={{ display: "flex", gap: 16, marginBottom: 8, fontSize: "0.74em", flexWrap: "wrap" }}>
        {showPe && avgPe != null && (
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <svg width="18" height="8"><line x1="0" y1="4" x2="18" y2="4" stroke={PE_CLR} strokeWidth="2" strokeDasharray="4 2" /></svg>
            <span style={{ color: PE_CLR, fontWeight: 700 }}>Avg. P/E ({range}): {avgPe.toFixed(1)}x</span>
          </div>
        )}
        {showEvEb && avgEvEb != null && (
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <svg width="18" height="8"><line x1="0" y1="4" x2="18" y2="4" stroke={EVEB_CLR} strokeWidth="2" strokeDasharray="4 2" /></svg>
            <span style={{ color: EVEB_CLR, fontWeight: 700 }}>Avg. EV/EBITDA ({range}): {avgEvEb.toFixed(1)}x</span>
          </div>
        )}
      </div>

      {/* Recharts */}
      <ResponsiveContainer width="100%" height={268}>
        <ComposedChart data={chartData} margin={{ top: 6, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={v => `${(v as number).toFixed(0)}x`}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            axisLine={false}
            tickLine={false}
            width={38}
            domain={[Math.max(0, minV - pad), maxV + pad]}
          />
          <Tooltip content={<MultTooltip />} />

          {/* PE line */}
          {showPe && (
            <Line
              type="monotone"
              dataKey="pe"
              name="P/E"
              stroke={PE_CLR}
              strokeWidth={2.5}
              dot={{ r: 3, fill: PE_CLR, stroke: "#fff", strokeWidth: 1.5 }}
              activeDot={{ r: 5, fill: PE_CLR, stroke: "#fff", strokeWidth: 2 }}
              connectNulls
            />
          )}

          {/* EV/EBITDA line */}
          {showEvEb && (
            <Line
              type="monotone"
              dataKey="ev_ebitda"
              name="EV/EBITDA"
              stroke={EVEB_CLR}
              strokeWidth={2.5}
              dot={{ r: 3, fill: EVEB_CLR, stroke: "#fff", strokeWidth: 1.5 }}
              activeDot={{ r: 5, fill: EVEB_CLR, stroke: "#fff", strokeWidth: 2 }}
              connectNulls
            />
          )}

          {/* Average reference lines */}
          {showPe && avgPe != null && (
            <ReferenceLine y={avgPe} stroke={PE_CLR} strokeDasharray="5 3" strokeWidth={1.5} strokeOpacity={0.65} />
          )}
          {showEvEb && avgEvEb != null && (
            <ReferenceLine y={avgEvEb} stroke={EVEB_CLR} strokeDasharray="5 3" strokeWidth={1.5} strokeOpacity={0.65} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Valuation card (shared layout for PE and EBITDA sections) ─────────────────

function ValCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#f8fafc", border: "1px solid #e5e7eb", borderRadius: 8, padding: "18px 20px", flex: 1, minWidth: 280 }}>
      <div style={{ fontSize: "0.78em", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  ticker:             string;
  onFairValueChange?: (fv: number | null) => void;
}

export default function IndustryMultipleTab({ ticker, onFairValueChange }: Props) {
  const [data,    setData]    = useState<IMultipleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  // ── User-editable inputs ───────────────────────────────────────────────────
  const [avgEps,       setAvgEps]       = useState(0);
  const [industryPe,   setIndustryPe]   = useState(15);
  const [mosPe,        setMosPe]        = useState(10);
  const [avgEbitdaMm,  setAvgEbitdaMm]  = useState(0);
  const [industryEvEb, setIndustryEvEb] = useState(10);
  const [mosEbitda,    setMosEbitda]    = useState(10);
  const [mosCombined,  setMosCombined]  = useState(10);

  const seeded = { current: false };

  // ── Fetch ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    seeded.current = false;
    setData(null); setLoading(true); setError(null);
    const ctrl = new AbortController();
    fetch(`/api/industry-multiple/${encodeURIComponent(ticker)}`, { signal: ctrl.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d: IMultipleData) => {
        setData(d);
        if (!seeded.current) {
          seeded.current = true;
          setAvgEps(     d.avg_eps       ?? 0);
          setAvgEbitdaMm(d.avg_ebitda_mm ?? 0);
        }
        setLoading(false);
      })
      .catch(e => { if (e.name !== "AbortError") { setError(e.message); setLoading(false); } });
    return () => ctrl.abort();
  }, [ticker]);

  // ── Valuation math (pure client-side) ─────────────────────────────────────
  const priceNow = data?.price_now ?? null;

  // Section 1: By Industry PE
  const fvPe       = avgEps > 0 && industryPe > 0 ? avgEps * industryPe : null;
  const buyPricePe = fvPe != null ? fvPe * (1 - mosPe / 100) : null;
  const onSalePe   = fvPe != null && priceNow != null ? priceNow <= buyPricePe! : null;

  // Section 2: By Industry EV/EBITDA
  const avgEbitdaRaw  = avgEbitdaMm * 1e6;
  const netDebtRaw    = data?.net_debt_raw ?? 0;
  const sharesOut     = data?.shares_outstanding ?? null;
  const fvEbitdaRaw   = industryEvEb > 0 && avgEbitdaRaw > 0
    ? avgEbitdaRaw * industryEvEb - netDebtRaw
    : null;
  const fvEbitdaPs    = fvEbitdaRaw != null && sharesOut && sharesOut > 0
    ? fvEbitdaRaw / sharesOut : null;
  const buyPriceEb    = fvEbitdaPs != null ? fvEbitdaPs * (1 - mosEbitda / 100) : null;
  const onSaleEb      = fvEbitdaPs != null && priceNow != null ? priceNow <= buyPriceEb! : null;

  // Combined (50/50)
  const fvCombined  = fvPe != null && fvEbitdaPs != null
    ? 0.5 * fvPe + 0.5 * fvEbitdaPs
    : fvPe ?? fvEbitdaPs;
  const buyPriceComb = fvCombined != null ? fvCombined * (1 - mosCombined / 100) : null;
  const onSaleComb   = fvCombined != null && priceNow != null ? priceNow <= buyPriceComb! : null;

  // ── Export to parent ───────────────────────────────────────────────────────
  useEffect(() => { onFairValueChange?.(fvCombined ?? null); }, [fvCombined, onFairValueChange]);

  // ── Render ─────────────────────────────────────────────────────────────────
  if (loading) return <Spinner />;
  if (error)   return (
    <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#991b1b" }}>
      <strong>Error loading Industry Multiple data:</strong> {error}
    </div>
  );
  if (!data) return null;

  return (
    <div>
      {/* ── Info banner ── */}
      <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, padding: "10px 16px", fontSize: "0.83em", color: "#1e40af", marginBottom: 18 }}>
        <strong>How to use:</strong> Review the historical multiples table to understand how the market
        has valued this company relative to its earnings and EBITDA. Then enter the Damodaran industry
        averages for PE and EV/EBITDA to derive a sector-relative fair value. The combined result
        weighs both methods equally (50/50).
      </div>

      {/* ══ Section 1 — Historical Table + Interactive Chart ═════════════════ */}
      <SecHeader title="1 · Historical Multiples" />
      <div style={{ fontSize: "0.78em", color: "#6b7280", marginBottom: 10 }}>
        Sector: <strong style={{ color: NAVY }}>{data.sector}</strong>
        &nbsp;·&nbsp;Industry: <strong style={{ color: NAVY }}>{data.industry}</strong>
        &nbsp;·&nbsp;Columns ordered most-recent → oldest (left to right)
      </div>

      {/* Side-by-side: table left, chart right */}
      <div style={{ display: "flex", gap: 28, flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* Left: Historical table */}
        <div style={{ flex: "1 1 380px", minWidth: 300 }}>
          <HistTable hist={data.hist} ttm={data.ttm} avg10={data.avg_10yr} />
        </div>

        {/* Right: Multiples Chart */}
        <div style={{ flex: "1.3 1 320px", minWidth: 280, background: "#f8fafc", border: "1px solid #e5e7eb", borderRadius: 10, padding: "16px 18px" }}>
          <div style={{ fontSize: "0.78em", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 }}>
            P/E &amp; EV/EBITDA — Historical Trend
          </div>
          <MultiplesChart hist={data.hist} ttm={data.ttm} />
        </div>
      </div>

      {/* ══ Section 2 — By Industry PE ════════════════════════════════════════ */}
      <SecHeader title="2 · By Industry P/E" />
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <ValCard title="Inputs">
          <InputRow
            label="Average EPS"
            value={avgEps}
            onChange={setAvgEps}
            prefix="$"
            step={0.01}
            note={`10yr avg: $${(data.avg_eps ?? 0).toFixed(2)}`}
          />
          <InputRow
            label="Industry P/E"
            value={industryPe}
            onChange={setIndustryPe}
            step={0.1}
          />
          <div style={{ fontSize: "0.75em", marginTop: 6 }}>
            <a
              href="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/pedata.html"
              target="_blank" rel="noreferrer"
              style={{ color: BLUE, textDecoration: "underline" }}
            >
              Damodaran PE Data Source ↗
            </a>
          </div>
          <InputRow
            label="Margin of Safety"
            value={mosPe}
            onChange={setMosPe}
            step={1}
            min={0}
          />
        </ValCard>

        <ValCard title="Valuation Results">
          <DataRow label="Average EPS" value={fEps(avgEps)} />
          <DataRow label="× Industry P/E" value={`${industryPe.toFixed(1)}x`} />
          <DataRow label="Fair Value per share" value={fPrice(fvPe)} color={GREEN} bold />
          <DataRow label={`Margin of Safety (${mosPe}%)`} value={`${mosPe}%`} />
          <DataRow label="Buy Price" value={fPrice(buyPricePe)} color={AMBER} bold />
          <DataRow label="Current Price" value={fPrice(priceNow)} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0 4px" }}>
            <span style={{ color: "#4d6b88", fontWeight: 500, fontSize: "0.87em" }}>Company on sale?</span>
            <OnSaleBadge onSale={onSalePe} />
          </div>
          {fvPe != null && priceNow != null && (
            <div style={{ display: "flex", gap: 20, fontSize: "0.80em", color: "#6b7280", paddingTop: 6, borderTop: "1px solid #f0f3f7" }}>
              <span>Upside to FV: <strong style={{ color: (fvPe > priceNow ? GREEN : RED) }}>{fUpside(fvPe, priceNow)}</strong></span>
              <span>Upside to Buy: <strong style={{ color: (buyPricePe != null && buyPricePe > priceNow ? GREEN : RED) }}>{fUpside(buyPricePe, priceNow)}</strong></span>
            </div>
          )}
        </ValCard>
      </div>

      {/* ══ Section 3 — By Industry EV/EBITDA ════════════════════════════════ */}
      <SecHeader title="3 · By Industry EV/EBITDA" />
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <ValCard title="Inputs">
          <InputRow
            label="Average EBITDA ($MM)"
            value={avgEbitdaMm}
            onChange={setAvgEbitdaMm}
            step={1}
            note={`10yr avg: $${(data.avg_ebitda_mm ?? 0).toFixed(0)}M`}
          />
          <InputRow
            label="Industry EV/EBITDA"
            value={industryEvEb}
            onChange={setIndustryEvEb}
            step={0.1}
          />
          <div style={{ fontSize: "0.75em", marginTop: 6 }}>
            <a
              href="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/vebitda.html"
              target="_blank" rel="noreferrer"
              style={{ color: BLUE, textDecoration: "underline" }}
            >
              Damodaran EV/EBITDA Data Source ↗
            </a>
          </div>
          <InputRow
            label="Margin of Safety"
            value={mosEbitda}
            onChange={setMosEbitda}
            step={1}
            min={0}
          />
        </ValCard>

        <ValCard title="Valuation Results">
          <DataRow label="Avg EBITDA × EV/EBITDA" value={fMM(avgEbitdaMm > 0 && industryEvEb > 0 ? avgEbitdaMm * industryEvEb : null)} />
          <DataRow label="Less: Net Debt (TTM)" value={fMM(data.net_debt_mm)} />
          <DataRow label="Implied Enterprise Equity" value={fMM(fvEbitdaRaw != null ? fvEbitdaRaw / 1e6 : null)} />
          <DataRow label="÷ Shares Outstanding" value={data.shares_outstanding ? `${(data.shares_outstanding / 1e6).toFixed(0)}M` : "—"} />
          <DataRow label="Fair Value per share" value={fPrice(fvEbitdaPs)} color={GREEN} bold />
          <DataRow label={`Margin of Safety (${mosEbitda}%)`} value={`${mosEbitda}%`} />
          <DataRow label="Buy Price" value={fPrice(buyPriceEb)} color={AMBER} bold />
          <DataRow label="Current Price" value={fPrice(priceNow)} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0 4px" }}>
            <span style={{ color: "#4d6b88", fontWeight: 500, fontSize: "0.87em" }}>Company on sale?</span>
            <OnSaleBadge onSale={onSaleEb} />
          </div>
          {fvEbitdaPs != null && priceNow != null && (
            <div style={{ display: "flex", gap: 20, fontSize: "0.80em", color: "#6b7280", paddingTop: 6, borderTop: "1px solid #f0f3f7" }}>
              <span>Upside to FV: <strong style={{ color: (fvEbitdaPs > priceNow ? GREEN : RED) }}>{fUpside(fvEbitdaPs, priceNow)}</strong></span>
              <span>Upside to Buy: <strong style={{ color: (buyPriceEb != null && buyPriceEb > priceNow ? GREEN : RED) }}>{fUpside(buyPriceEb, priceNow)}</strong></span>
            </div>
          )}
        </ValCard>
      </div>

      {/* ══ Section 4 — Combined Valuation ═══════════════════════════════════ */}
      <SecHeader title="4 · Combined Valuation (50/50 Weighted)" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, maxWidth: 720 }}>
        {/* Step-by-step derivation */}
        <div style={{ background: "#f8fafc", border: "1px solid #e5e7eb", borderRadius: 8, padding: "18px 20px" }}>
          <div style={{ fontSize: "0.78em", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 }}>
            Derivation
          </div>
          <DataRow label="FV by P/E"         value={fPrice(fvPe)} />
          <DataRow label="FV by EV/EBITDA"   value={fPrice(fvEbitdaPs)} />
          <DataRow label="Weight each (50%)"  value="× 0.50 + × 0.50" />
          <DataRow label="Combined Fair Value" value={fPrice(fvCombined)} color={GREEN} bold />
          <div style={{ padding: "10px 0 0", fontSize: "0.80em", color: "#9ca3af", borderTop: "1px dashed #e5e7eb", marginTop: 8 }}>
            {fvPe == null && "P/E fair value unavailable (no EPS data)"}
            {fvEbitdaPs == null && "EV/EBITDA fair value unavailable (no EBITDA or shares data)"}
            {fvPe != null && fvEbitdaPs == null && "Using P/E only (no EBITDA data)"}
            {fvPe == null && fvEbitdaPs != null && "Using EV/EBITDA only (no EPS data)"}
          </div>
        </div>

        {/* Summary card */}
        <div style={{
          borderRadius: 8, padding: "18px 20px",
          background: onSaleComb === true ? "#f0fdf4" : onSaleComb === false ? "#fef2f2" : "#f9fafb",
          border: `1.5px solid ${onSaleComb === true ? "#86efac" : onSaleComb === false ? "#fca5a5" : "#e5e7eb"}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <span style={{ fontSize: "0.78em", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.06em" }}>Final Verdict</span>
            <OnSaleBadge onSale={onSaleComb} />
          </div>

          <DataRow label="Combined Fair Value" value={fPrice(fvCombined)} color={GREEN} bold />

          {/* Combined MoS input inline */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: "1px solid #f0f3f7", fontSize: "0.87em" }}>
            <span style={{ color: "#4d6b88", fontWeight: 500 }}>Margin of Safety</span>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="number" value={mosCombined} step={1} min={0} max={80}
                onChange={(e) => setMosCombined(Number(e.target.value))}
                style={{ width: 64, padding: "2px 6px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.88em", ...MONO, textAlign: "right" }}
              />
              <span style={{ color: "#9ca3af", fontSize: "0.85em" }}>%</span>
            </div>
          </div>

          <DataRow label="Buy Price" value={fPrice(buyPriceComb)} color={AMBER} bold />
          <DataRow label="Current Price" value={fPrice(priceNow)} />

          {fvCombined != null && priceNow != null && (
            <>
              <div style={{ marginTop: 10, paddingTop: 8, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", fontSize: "0.85em" }}>
                <span style={{ color: "#4d6b88" }}>Upside to Fair Value</span>
                <span style={{ fontWeight: 700, color: fvCombined > priceNow ? GREEN : RED, ...MONO }}>
                  {fUpside(fvCombined, priceNow)}
                </span>
              </div>
              <div style={{ paddingTop: 4, display: "flex", justifyContent: "space-between", fontSize: "0.85em" }}>
                <span style={{ color: "#4d6b88" }}>Upside to Buy Price</span>
                <span style={{ fontWeight: 700, color: buyPriceComb != null && buyPriceComb > priceNow ? GREEN : RED, ...MONO }}>
                  {fUpside(buyPriceComb, priceNow)}
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      <div style={{ height: 32 }} />
    </div>
  );
}
