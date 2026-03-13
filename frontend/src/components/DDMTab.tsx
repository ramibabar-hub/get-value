/**
 * DDMTab.tsx  —  Dividend Discount Model (Gordon Growth)
 *
 * Architecture
 * ────────────
 * • Fetches DdmData ONCE per ticker from  GET /api/ddm/{ticker}
 * • All Gordon Growth math is computed inline in React (no re-fetch on slider change)
 * • Fair value is exported to the parent via onFairValueChange callback
 *
 * Gordon Growth formula
 * ─────────────────────
 *   Fair Value = DPS_TTM × (1 + g_forecast) / (r − g_terminal)
 *   Guard: if (r − g_terminal) ≤ 0 → show "Rate mismatch" warning
 */

import { useState, useEffect, useRef, memo } from "react";
import type { DdmData, DdmHistRow } from "../types";

// ── Palette (matches rest of app) ─────────────────────────────────────────────
const NAVY    = "var(--gv-navy)";
const BLUE    = "#1d4ed8";
const GREEN   = "#16a34a";
const RED     = "#dc2626";
const AMBER   = "#b45309";
const MONO: React.CSSProperties = { fontFamily: "'Courier New', monospace", fontVariantNumeric: "tabular-nums" };

// ── Formatters ────────────────────────────────────────────────────────────────

/** Raw dollars → compact $MM / $B label */
function fMM(v: number | null): string {
  if (v == null || !isFinite(v)) return "—";
  const abs = Math.abs(v) / 1e6;
  return abs >= 1000
    ? `$${(Math.abs(v) / 1e9).toFixed(1)}B`
    : `$${abs.toFixed(0)}M`;
}

/** Raw share count → compact MM / B */
function fSh(v: number | null): string {
  if (v == null || !isFinite(v)) return "—";
  const abs = Math.abs(v);
  return abs >= 1e9
    ? `${(abs / 1e9).toFixed(2)}B`
    : `${(abs / 1e6).toFixed(0)}M`;
}

/** Dollar per share */
function fDps(v: number | null): string {
  if (v == null || !isFinite(v)) return "—";
  return `$${v.toFixed(2)}`;
}

/** Decimal fraction → percentage string */
function fPct(v: number | null, decimals = 1): string {
  if (v == null || !isFinite(v)) return "—";
  return `${(v * 100).toFixed(decimals)}%`;
}

/** Dollar price string */
function fPrice(v: number | null): string {
  if (v == null || !isFinite(v)) return "N/A";
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "var(--gv-text-muted)" }}>
      <div style={{
        width: 28, height: 28, borderRadius: "50%",
        border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`,
        animation: "ddmSpin 0.75s linear infinite", flexShrink: 0,
      }} />
      <span style={{ fontSize: "0.88em" }}>Loading dividend data…</span>
      <style>{`@keyframes ddmSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Section header (matches other tabs) ───────────────────────────────────────

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: "1.05em", fontWeight: "bold", color: "#fff",
      background: NAVY, padding: "6px 15px", borderRadius: 4,
      marginTop: 24, marginBottom: 8,
    }}>
      {title}
    </div>
  );
}

// ── Slider row (identical pattern to CfIrrTab) ────────────────────────────────

interface SliderRowProps {
  label:    string;
  value:    number;
  min:      number;
  max:      number;
  step:     number;
  unit?:    string;
  onChange: (v: number) => void;
  note?:    string;
}

function SliderRow({ label, value, min, max, step, unit = "%", onChange, note }: SliderRowProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3, flex: 1, minWidth: 180 }}>
      <div style={{ fontSize: "0.80em", fontWeight: 700, color: NAVY }}>
        {label}:&nbsp;
        <span style={{ color: AMBER, fontWeight: 800 }}>
          {value.toFixed(step < 1 ? 1 : 0)}{unit}
        </span>
        {note && <span style={{ color: "var(--gv-text-muted)", fontWeight: 400, marginLeft: 6 }}>{note}</span>}
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ accentColor: NAVY, width: "100%", cursor: "pointer" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68em", color: "var(--gv-text-muted)" }}>
        <span>{min}{unit}</span><span>{max}{unit}</span>
      </div>
    </div>
  );
}

// ── Historical table ──────────────────────────────────────────────────────────

const HistTable = memo(function HistTable({
  hist, ttm, dps_cagr, dps_cagr_years,
}: {
  hist:           DdmHistRow[];
  ttm:            DdmHistRow;
  dps_cagr:       number | null;
  dps_cagr_years: number;
}) {
  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "7px 12px",
    border: "1px solid #2d3f5a", fontSize: "0.80em",
    fontWeight: 700, whiteSpace: "nowrap",
  };
  const tdS = (right = false, bold = false, color?: string): React.CSSProperties => ({
    padding: "6px 12px", border: "1px solid #e5e7eb",
    textAlign: right ? "right" : "left",
    fontWeight: bold ? 700 : 400,
    color: color ?? NAVY,
    ...MONO,
  });

  const ALL_ROWS = [...hist, ttm];

  // ── Per-column CAGR (oldest hist row → TTM) ───────────────────────────────
  const n      = hist.length;          // number of years
  const oldest = hist[0] ?? null;

  function cagrOf(oldVal: number | null, newVal: number | null, useAbs = false): number | null {
    if (oldVal == null || newVal == null || n <= 0) return null;
    const o = useAbs ? Math.abs(oldVal) : oldVal;
    const v = useAbs ? Math.abs(newVal) : newVal;
    if (!isFinite(o) || !isFinite(v) || o <= 0) return null;
    return Math.pow(v / o, 1 / n) - 1;
  }

  const cagrDivsPaid  = oldest ? cagrOf(oldest.divs_paid,  ttm.divs_paid,  true)  : null;
  const cagrShares    = oldest ? cagrOf(oldest.shares,     ttm.shares,     false) : null;
  const cagrNetIncome = oldest ? cagrOf(oldest.net_income, ttm.net_income, false) : null;
  const cagrPayout    = oldest ? cagrOf(oldest.payout_pct, ttm.payout_pct, false) : null;

  function CagrTd({ v }: { v: number | null }) {
    if (v == null) return <td style={{ ...tdS(true), color: "var(--gv-text-muted)" }}>N/A</td>;
    return (
      <td style={{ ...tdS(true, true, v >= 0 ? GREEN : RED) }}>
        {fPct(v)}
      </td>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
        <thead>
          <tr>
            {["Year", "Divs Paid", "Shares", "DPS", "Net Income", "Payout %"].map((h, i) => (
              <th key={h} style={{ ...thS, textAlign: i === 0 ? "left" : "right" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ALL_ROWS.map((row, ri) => {
            const isTtm = row.year === "TTM";
            const bg    = isTtm ? "#eff6ff" : ri % 2 === 0 ? "#fff" : "#f8fafc";
            return (
              <tr key={row.year} style={{ background: bg }}>
                <td style={{ ...tdS(false, isTtm, isTtm ? BLUE : NAVY) }}>
                  {isTtm ? <span style={{ color: BLUE, fontWeight: 800 }}>TTM</span> : row.year}
                </td>
                <td style={{ ...tdS(true, isTtm) }}>{fMM(row.divs_paid)}</td>
                <td style={{ ...tdS(true, isTtm) }}>{fSh(row.shares)}</td>
                <td style={{ ...tdS(true, true, isTtm ? BLUE : NAVY) }}>{fDps(row.dps)}</td>
                <td style={{ ...tdS(true, isTtm) }}>{fMM(row.net_income)}</td>
                <td style={{ ...tdS(true, isTtm) }}>{fPct(row.payout_pct)}</td>
              </tr>
            );
          })}

          {/* CAGR row — all columns */}
          <tr style={{ background: "#fefce8", borderTop: "2px solid #fde68a" }}>
            <td style={{ ...tdS(false, true, AMBER), fontSize: "0.90em" }}>
              CAGR ({dps_cagr_years}yr)
            </td>
            <CagrTd v={cagrDivsPaid} />
            <CagrTd v={cagrShares} />
            <td style={{ ...tdS(true, true, dps_cagr == null ? "var(--gv-text-muted)" : dps_cagr >= 0 ? GREEN : RED) }}>
              {dps_cagr != null ? fPct(dps_cagr) : "N/A"}
            </td>
            <CagrTd v={cagrNetIncome} />
            <CagrTd v={cagrPayout} />
          </tr>
        </tbody>
      </table>
    </div>
  );
});

// ── Gordon Growth calculation display ─────────────────────────────────────────

interface CalcDisplayProps {
  dps:        number;
  gForecast:  number;  // decimal
  r:          number;  // decimal
  gTerminal:  number;  // decimal
  mosPct:     number;  // percentage (10 = 10%)
  priceNow:   number | null;
  fairValue:  number | null;
  buyPrice:   number | null;
  modelValid: boolean;
}

function CalcDisplay({
  dps, gForecast, r, gTerminal, mosPct, priceNow, fairValue, buyPrice, modelValid,
}: CalcDisplayProps) {
  const dpsNext    = dps * (1 + gForecast);
  const denominator = r - gTerminal;
  const onSale     = fairValue != null && priceNow != null ? fairValue > priceNow : null;
  const upsideToFv = fairValue != null && priceNow != null && priceNow > 0
    ? ((fairValue / priceNow) - 1) * 100 : null;

  const ROW: React.CSSProperties = {
    display: "flex", justifyContent: "space-between", alignItems: "baseline",
    padding: "6px 0", borderBottom: "1px solid #f0f3f7",
    fontSize: "0.87em",
  };
  const LABEL: React.CSSProperties = { color: "var(--gv-text-dim)", fontWeight: 500 };
  const VAL:   React.CSSProperties = { fontWeight: 700, color: NAVY, ...MONO };

  if (!modelValid || fairValue == null) {
    return (
      <div style={{
        background: "#fef2f2", border: "1.5px solid #fca5a5",
        borderRadius: 8, padding: "16px 20px",
      }}>
        <div style={{ fontWeight: 700, color: RED, fontSize: "0.95em", marginBottom: 6 }}>
          ⚠ Rate Mismatch — Model Invalid
        </div>
        <div style={{ color: "#7f1d1d", fontSize: "0.83em", lineHeight: 1.6 }}>
          {dps <= 0
            ? "Company is not paying a dividend. DDM requires a positive DPS."
            : `The discount rate (r = ${(r * 100).toFixed(1)}%) must exceed the terminal growth rate (g = ${(gTerminal * 100).toFixed(1)}%).`
          }
          {denominator <= 0 && dps > 0 && " Reduce the terminal growth rate or raise WACC."}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
      {/* Step-by-step derivation */}
      <div style={{ background: "#f8fafc", borderRadius: 8, padding: "16px 20px", border: "1px solid #e5e7eb" }}>
        <div style={{ fontSize: "0.80em", fontWeight: 700, color: "var(--gv-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 10 }}>
          Gordon Growth Derivation
        </div>
        <div style={ROW}>
          <span style={LABEL}>DPS (TTM)</span>
          <span style={VAL}>{fDps(dps)}</span>
        </div>
        <div style={ROW}>
          <span style={LABEL}>× (1 + g<sub>forecast</sub>)</span>
          <span style={{ ...VAL, color: "var(--gv-text-dim)" }}>× {(1 + gForecast).toFixed(3)}</span>
        </div>
        <div style={{ ...ROW, borderTop: "1.5px solid #dbeafe", marginTop: 2, paddingTop: 8 }}>
          <span style={{ ...LABEL, fontWeight: 700 }}>= DPS Next Year</span>
          <span style={{ ...VAL, color: BLUE }}>{fDps(dpsNext)}</span>
        </div>
        <div style={{ ...ROW, marginTop: 8 }}>
          <span style={LABEL}>÷ (r − g<sub>terminal</sub>)</span>
          <span style={{ ...VAL, color: "var(--gv-text-dim)" }}>÷ {(denominator * 100).toFixed(2)}%</span>
        </div>
        <div style={{ ...ROW, borderTop: "1.5px solid #bbf7d0", marginTop: 2, paddingTop: 8 }}>
          <span style={{ ...LABEL, fontWeight: 700 }}>= Intrinsic Fair Value</span>
          <span style={{ ...VAL, color: GREEN, fontSize: "1.05em" }}>{fPrice(fairValue)}</span>
        </div>
        <div style={ROW}>
          <span style={LABEL}>× (1 − MoS {mosPct.toFixed(0)}%)</span>
          <span style={{ ...VAL, color: AMBER }}>× {((1 - mosPct / 100) * 100).toFixed(0)}%</span>
        </div>
        <div style={{ ...ROW, borderTop: "2px solid #fde68a", marginTop: 2, paddingTop: 8 }}>
          <span style={{ ...LABEL, fontWeight: 700 }}>= Buy Price</span>
          <span style={{ ...VAL, color: AMBER, fontSize: "1.05em" }}>{fPrice(buyPrice)}</span>
        </div>
      </div>

      {/* Summary box */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Price vs Fair Value */}
        <div style={{
          borderRadius: 8, padding: "16px 20px",
          background: onSale === true ? "#f0fdf4" : onSale === false ? "#fef2f2" : "#f9fafb",
          border: `1.5px solid ${onSale === true ? "var(--gv-green-mid)" : onSale === false ? "var(--gv-red-mid)" : "var(--gv-border)"}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: "0.80em", fontWeight: 700, color: "var(--gv-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Price vs Fair Value
            </span>
            <span style={{
              fontSize: "0.78em", fontWeight: 700, padding: "3px 10px", borderRadius: 20,
              background: onSale === true ? GREEN : onSale === false ? RED : "var(--gv-text-muted)",
              color: "#fff",
            }}>
              {onSale === true ? "✓ On Sale" : onSale === false ? "✗ Overpriced" : "—"}
            </span>
          </div>
          {[
            ["Current Price",  fPrice(priceNow),  NAVY],
            ["Fair Value",     fPrice(fairValue),  GREEN],
            ["Buy Price",      fPrice(buyPrice),   AMBER],
          ].map(([lbl, val, clr]) => (
            <div key={lbl as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 5, fontSize: "0.87em" }}>
              <span style={{ color: "var(--gv-text-dim)" }}>{lbl}</span>
              <span style={{ fontWeight: 700, color: clr as string, ...MONO }}>{val}</span>
            </div>
          ))}
          {upsideToFv != null && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", fontSize: "0.87em" }}>
              <span style={{ color: "var(--gv-text-dim)" }}>Upside to Fair Value</span>
              <span style={{ fontWeight: 700, color: upsideToFv >= 0 ? GREEN : RED, ...MONO }}>
                {upsideToFv >= 0 ? "+" : ""}{upsideToFv.toFixed(1)}%
              </span>
            </div>
          )}
        </div>

        {/* Yield on fair value */}
        <div style={{ background: "#f8fafc", borderRadius: 8, padding: "14px 18px", border: "1px solid #e5e7eb", fontSize: "0.85em" }}>
          <div style={{ color: "var(--gv-text-muted)", fontWeight: 600, marginBottom: 6, textTransform: "uppercase", fontSize: "0.75em", letterSpacing: "0.06em" }}>
            Implied Yield at Fair Value
          </div>
          <span style={{ fontWeight: 800, color: NAVY, fontSize: "1.2em", ...MONO }}>
            {fPrice(dps)}&thinsp;/&thinsp;{fPrice(fairValue)}&nbsp;=&nbsp;
            {fairValue ? fPct(dps / fairValue, 2) : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Checklist ─────────────────────────────────────────────────────────────────

function Checklist({
  hasDividend, dps_cagr, payoutTtm, r, gTerminal,
}: {
  hasDividend: boolean;
  dps_cagr:    number | null;
  payoutTtm:   number | null;
  r:           number;
  gTerminal:   number;
}) {
  const items: { label: string; threshold: string; pass: boolean | null; display: string }[] = [
    {
      label: "Pays a dividend",
      threshold: "DPS TTM > 0",
      pass:      hasDividend,
      display:   hasDividend ? "Yes" : "No",
    },
    {
      label:    "DPS CAGR",
      threshold: "≥ 5%",
      pass:     dps_cagr != null ? dps_cagr >= 0.05 : null,
      display:  dps_cagr != null ? fPct(dps_cagr) : "N/A",
    },
    {
      label:    "Payout Ratio (TTM)",
      threshold: "< 70%",
      pass:     payoutTtm != null ? payoutTtm < 0.70 : null,
      display:  payoutTtm != null ? fPct(payoutTtm) : "N/A",
    },
    {
      label:    "r > g_terminal",
      threshold: "Required for DDM",
      pass:     r > gTerminal,
      display:  `${(r * 100).toFixed(1)}% > ${(gTerminal * 100).toFixed(1)}%`,
    },
  ];

  const PASS_BG  = "#f0fdf4"; const PASS_FG  = GREEN;
  const FAIL_BG  = "#fef2f2"; const FAIL_FG  = RED;
  const NA_BG    = "#f9fafb"; const NA_FG    = "var(--gv-text-muted)";

  const thS: React.CSSProperties = {
    background: NAVY, color: "#fff", padding: "7px 12px",
    fontSize: "0.78em", textAlign: "left", border: "1px solid #2d3f5a",
  };

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
        <thead>
          <tr>
            <th style={thS}>Check</th>
            <th style={{ ...thS, textAlign: "center" }}>Threshold</th>
            <th style={{ ...thS, textAlign: "center" }}>Value</th>
            <th style={{ ...thS, textAlign: "center" }}>Result</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const bg  = item.pass === true ? PASS_BG : item.pass === false ? FAIL_BG : NA_BG;
            const fg  = item.pass === true ? PASS_FG : item.pass === false ? FAIL_FG : NA_FG;
            const icon = item.pass === true ? "✅" : item.pass === false ? "❌" : "—";
            return (
              <tr key={item.label} style={{ background: bg }}>
                <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", fontWeight: 600, color: fg }}>{item.label}</td>
                <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", textAlign: "center", color: "var(--gv-text-dim)" }}>{item.threshold}</td>
                <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", textAlign: "center", fontWeight: 700, color: fg, ...MONO }}>{item.display}</td>
                <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", textAlign: "center", fontSize: "1.1em" }}>{icon}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  ticker:              string;
  externalWacc:        number;   // percentage (9.2 = 9.2%)
  onFairValueChange?:  (fv: number | null) => void;
}

export default function DDMTab({ ticker, externalWacc, onFairValueChange }: Props) {
  const [data,    setData]    = useState<DdmData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  // Slider state (all in percentage points for display; convert to decimal for math)
  const [waccPct,      setWaccPct]      = useState(9.2);
  const [gForecastPct, setGForecastPct] = useState(5.0);
  const [gTerminalPct, setGTerminalPct] = useState(3.0);
  const [mosPct,       setMosPct]       = useState(10.0);

  const seeded = useRef(false);

  // ── Fetch on ticker change ─────────────────────────────────────────────────
  useEffect(() => {
    seeded.current = false;
    setData(null);
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    fetch(`/api/ddm/${encodeURIComponent(ticker)}`, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d: DdmData) => { setData(d); setLoading(false); })
      .catch(e => { if (e.name !== "AbortError") { setError(e.message); setLoading(false); } });

    return () => controller.abort();
  }, [ticker]);

  // ── Seed sliders from API data (once per ticker) ──────────────────────────
  useEffect(() => {
    if (!data || seeded.current) return;
    seeded.current = true;

    const wDefault = externalWacc > 0
      ? externalWacc
      : parseFloat(((data.wacc_computed ?? 0.092) * 100).toFixed(2));
    setWaccPct(wDefault);

    const cagr = data.dps_cagr;
    setGForecastPct(cagr != null ? parseFloat((cagr * 100).toFixed(1)) : 5.0);
    setGTerminalPct(parseFloat((data.default_g_terminal * 100).toFixed(1)));
  }, [data, externalWacc]);

  // ── Gordon Growth (pure derivation — no API call needed) ──────────────────
  const r         = waccPct      / 100;
  const gForecast = gForecastPct / 100;
  const gTerminal = gTerminalPct / 100;
  const dps       = data?.ttm.dps ?? 0;

  const modelValid  = r > gTerminal && dps > 0 && (data?.has_dividend ?? false);
  const denominator = r - gTerminal;
  const dpsNext     = dps * (1 + gForecast);
  const fairValue   = modelValid && denominator > 0 ? dpsNext / denominator : null;
  const buyPrice    = fairValue != null ? fairValue * (1 - mosPct / 100) : null;

  // ── Export fair value to parent ───────────────────────────────────────────
  useEffect(() => {
    onFairValueChange?.(fairValue);
  }, [fairValue, onFairValueChange]);

  // ── Render ────────────────────────────────────────────────────────────────
  if (loading) return <Spinner />;

  if (error) {
    return (
      <div style={{
        background: "var(--gv-red-bg)", border: "1px solid #fca5a5",
        borderRadius: 8, padding: "12px 16px", color: "var(--gv-red)",
      }}>
        <strong>Error loading DDM data:</strong> {error}
      </div>
    );
  }

  if (!data) return null;

  // ── No-dividend notice (still show historical table) ──────────────────────
  const noDivBanner = !data.has_dividend && (
    <div style={{
      background: "#fffbeb", border: "1.5px solid #fde68a",
      borderRadius: 8, padding: "10px 16px", marginBottom: 16,
      fontSize: "0.85em", color: AMBER,
    }}>
      <strong>Note:</strong> {ticker} does not currently pay a dividend.
      The DDM Gordon Growth model requires a positive DPS to produce a fair value.
    </div>
  );

  return (
    <div>

      {/* ══ Section 1: About the Model ══ */}
      <SecHeader title="About the Model" />
      <div style={{
        background: "#f8fafc", borderRadius: 8, padding: "14px 18px",
        border: "1px solid #e5e7eb", fontSize: "0.83em", color: "var(--gv-text-dim)",
        lineHeight: 1.75,
      }}>
        <strong style={{ color: NAVY }}>Gordon Growth Model (Dividend Discount Model)</strong>
        &nbsp;values a stock as the present value of all future dividends, assuming they grow at a constant rate forever.
        It is most reliable for mature, stable dividend-paying companies (utilities, REITs, large-cap consumer staples).
        <br /><br />
        <strong style={{ color: RED }}>
          Note: This model is only suitable for companies with a consistent dividend distribution history.
          If the company does not pay dividends, this model is not applicable.
        </strong>
        <br /><br />
        <strong style={{ color: NAVY }}>Key assumptions:</strong>
        <ul style={{ margin: "6px 0 0 18px", padding: 0, lineHeight: 2 }}>
          <li><strong>r</strong> — your required rate of return (WACC or personal hurdle rate)</li>
          <li><strong>g_forecast</strong> — expected near-term dividend growth; defaults to the historical DPS CAGR</li>
          <li><strong>g_terminal</strong> — long-run sustainable growth; should not exceed GDP growth (~3–5%)</li>
          <li>The model breaks down when <strong>r ≤ g_terminal</strong> or when the company pays no dividend</li>
        </ul>
      </div>

      {/* ══ Section 2: Quality Checklist ══ */}
      <SecHeader title="DDM Quality Checklist" />
      <Checklist
        hasDividend={data.has_dividend}
        dps_cagr={data.dps_cagr}
        payoutTtm={data.ttm.payout_pct}
        r={r}
        gTerminal={gTerminal}
      />

      {/* ══ Section 3: Historical Data ══ */}
      <SecHeader title="Historical Dividend Data" />
      {noDivBanner}
      <HistTable
        hist={data.hist}
        ttm={data.ttm}
        dps_cagr={data.dps_cagr}
        dps_cagr_years={data.dps_cagr_years}
      />

      {/* ══ Section 4: Model Inputs ══ */}
      <SecHeader title="Model Inputs" />
      <div style={{
        background: "#fffbeb", border: "1.5px solid #fde68a",
        borderRadius: 8, padding: "16px 20px", marginBottom: 8,
      }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "16px 28px",
        }}>
          <SliderRow
            label="Discount Rate (r / WACC)"
            value={waccPct} min={2} max={25} step={0.1}
            onChange={setWaccPct}
            note={`computed: ${((data.wacc_computed ?? 0) * 100).toFixed(2)}%`}
          />
          <SliderRow
            label="Forecast DPS Growth (g)"
            value={gForecastPct} min={0} max={30} step={0.5}
            onChange={setGForecastPct}
            note={data.dps_cagr != null ? `CAGR: ${fPct(data.dps_cagr)}` : undefined}
          />
          <SliderRow
            label="Terminal Growth (g_terminal)"
            value={gTerminalPct} min={0} max={7} step={0.25}
            onChange={setGTerminalPct}
            note="max 5% recommended"
          />
          <SliderRow
            label="Margin of Safety"
            value={mosPct} min={0} max={40} step={1}
            onChange={setMosPct}
          />
        </div>

        {/* Live formula display */}
        <div style={{
          marginTop: 14, paddingTop: 12, borderTop: "1px solid #fde68a",
          fontSize: "0.82em", color: AMBER, fontFamily: "'Courier New', monospace",
          letterSpacing: "0.01em",
        }}>
          Fair Value = {fDps(dps)} × (1 + {gForecastPct.toFixed(1)}%) / ({waccPct.toFixed(1)}% − {gTerminalPct.toFixed(1)}%)
          {modelValid && fairValue != null && (
            <span style={{ marginLeft: 14, fontWeight: 800, color: GREEN }}>
              = {fPrice(fairValue)}
            </span>
          )}
          {!modelValid && (
            <span style={{ marginLeft: 14, fontWeight: 700, color: RED }}>
              = ⚠ Invalid
            </span>
          )}
        </div>
      </div>

      {/* ══ Section 5: Valuation Output ══ */}
      <SecHeader title="Gordon Growth Valuation" />
      <CalcDisplay
        dps={dps}
        gForecast={gForecast}
        r={r}
        gTerminal={gTerminal}
        mosPct={mosPct}
        priceNow={data.price_now}
        fairValue={fairValue}
        buyPrice={buyPrice}
        modelValid={modelValid}
      />
    </div>
  );
}
