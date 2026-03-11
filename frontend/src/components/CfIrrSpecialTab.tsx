/**
 * CfIrrSpecialTab.tsx
 * Special Valuation Model: Tangible Book Value (TBV) + EPS
 *
 * TBV  = Total Assets − (Goodwill & Intangibles) − Total Liabilities
 * Terminal Value = tbvWeight × (TBV₁₀ × P/TBV) + (1−tbvWeight) × (EPS₁₀ × P/E)
 * IRR on: [−price, EPS₁..EPS₉, EPS₁₀ + TerminalValue]
 *
 * Checklist:
 *   Assets Growth > 4%  |  TBV Growth > 3%  |  Net Margin > 10%
 *   EPS Growth > 10%    |  IRR > 12%
 */
import { useState, useCallback, useEffect, useRef, memo } from "react";
import type { CfIrrSpecialData, CfIrrCheckItem, OverviewData } from "../types";

// ── Palette ───────────────────────────────────────────────────────────────────
const NAVY        = "#1c2b46";
const CLR_API_BG  = "#dbeafe"; const CLR_API_FG  = "#1e40af";  // blue  – fetched
const CLR_CALC_BG = "#d1fae5"; const CLR_CALC_FG = "#065f46";  // green – calculated
const CLR_USER_BG = "#fef9c3"; const CLR_USER_FG = "#78350f";  // yellow – user input
const CLR_PASS    = "#d1fae5"; const CLR_PASS_FG = "#065f46";
const CLR_FAIL    = "#fee2e2"; const CLR_FAIL_FG = "#991b1b";
const CLR_NA      = "#f3f4f6"; const CLR_NA_FG   = "#6b7280";

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


// ── Shared UI atoms ───────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "#6b7280" }}>
      <div style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`, animation: "spSpin 0.75s linear infinite", flexShrink: 0 }} />
      <span style={{ fontSize: "0.88em" }}>Computing Special Model…</span>
      <style>{`@keyframes spSpin { to { transform: rotate(360deg); } }`}</style>
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

function SubHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "0.88em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginTop: 14, marginBottom: 4 }}>
      {title}
    </div>
  );
}

function Legend() {
  return (
    <div style={{ display: "flex", gap: 16, marginTop: 6, marginBottom: 2 }}>
      {([["API (fetched)", CLR_API_BG, CLR_API_FG], ["Calculated", CLR_CALC_BG, CLR_CALC_FG], ["User Input", CLR_USER_BG, CLR_USER_FG]] as const).map(([label, bg, fg]) => (
        <span key={label} style={{ fontSize: "0.72em", fontWeight: 600, padding: "2px 8px", borderRadius: 3, background: bg, color: fg }}>{label}</span>
      ))}
    </div>
  );
}

// ── Historical table ──────────────────────────────────────────────────────────

const HIST_COLS = ["Year", "Assets ($B)", "GW&I ($B)", "Liab ($B)", "TBV/s", "EPS", "Net Margin"];

const HistTable = memo(function HistTable({ rows, ttm, avg, cagr }: {
  rows:  Record<string, string>[];
  ttm:   Record<string, string>;
  avg:   Record<string, string>;
  cagr:  Record<string, string>;
}) {
  if (!rows.length) return null;
  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "6px 10px", border: "1px solid #2d3f5a",
    fontSize: "0.77em", whiteSpace: "nowrap",
  };
  const all = [...rows, cagr, avg, ttm];
  return (
    <div style={{ overflowX: "auto", marginBottom: 16 }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.79em", minWidth: "100%" }}>
        <thead>
          <tr>
            {HIST_COLS.map((c, i) => (
              <th key={c} style={{ ...thBase, textAlign: i === 0 ? "left" : "right", minWidth: i === 0 ? 80 : 100 }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {all.map((row, ri) => {
            const yr = row["Year"] ?? "";
            const isSpecial = yr === "TTM" || yr.startsWith("Average") || yr.startsWith("CAGR");
            return (
              <tr key={ri} style={{ background: isSpecial ? "#eff6ff" : ri % 2 === 0 ? "#fff" : "#f8fafc", fontWeight: isSpecial ? 700 : 400 }}>
                {HIST_COLS.map((col, ci) => (
                  <td key={col} style={{ padding: "5px 10px", border: "1px solid #e5e7eb", textAlign: ci === 0 ? "left" : "right", color: NAVY, fontSize: "0.97em", ...MONO }}>
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
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <span style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>Global Growth Rate (Yr 1):</span>
        <input type="number" value={globalRate} min={-50} max={200} step={0.5}
          onChange={(e) => onGlobalChange(Number(e.target.value))}
          style={{ width: 80, padding: "3px 8px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.83em", fontFamily: "inherit", textAlign: "right", background: CLR_USER_BG }} />
        <span style={{ fontSize: "0.78em", color: "#6b7280" }}>%</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: "0.81em", minWidth: 460 }}>
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
                <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", fontWeight: 600, background: CLR_API_BG, color: CLR_API_FG }}>{row.Year as string}</td>
                <td style={{ padding: "4px 8px", border: "1px solid #e5e7eb", background: CLR_USER_BG }}>
                  <input type="number" value={growthRates[i] ?? 5} step={0.5} min={-50} max={200}
                    onChange={(e) => onGrowthChange(i, Number(e.target.value))}
                    style={{ width: "100%", padding: "2px 6px", border: "1px solid #fbbf24", borderRadius: 3, fontSize: "0.9em", fontFamily: "'Courier New', monospace", textAlign: "right", background: "transparent" }} />
                </td>
                <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: CLR_CALC_FG, background: CLR_CALC_BG, fontWeight: 600 }}>
                  {typeof row[valueKey] === "number"
                    ? f$(row[valueKey] as number)
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
  data:    CfIrrSpecialData;
  waccPct: number;
  mosPct:  number;
}) {
  const waccDec  = waccPct / 100;
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
    ["TBV₁₀ × P/TBV Target",     f$(data.tbv_terminal),   null],
    ["EPS₁₀ × P/E Target",        f$(data.eps_terminal),   null],
    ["Average Target Price",       f$(data.avg_target),     null],
    ["WACC",                       `${waccPct.toFixed(2)}%`, null],
    ["Fair Value per share",       f$(fairValue),           null],
    ["Margin of Safety",           `${mosPct.toFixed(0)}%`, null],
    ["Buy Price",                  f$(buyPrice),            null],
    ["Current Stock Price",        f$(data.price_now),      null],
    ["Company on-sale?",           onSale === true ? "✅ ON SALE" : onSale === false ? "❌ NOT ON SALE" : "N/A", onSale],
    ["Upside/Downside (vs. FV)",   delta(fairValue, data.price_now), null],
    ["Upside/Downside (vs. Buy)",  delta(buyPrice,  data.price_now), null],
    ["IRR",                        data.irr != null ? fPct(data.irr) : "N/A", data.irr != null ? data.irr >= 0.12 : null],
  ];

  const thS: React.CSSProperties = { background: NAVY, color: "#fff", padding: "7px 12px", fontSize: "0.78em", border: "1px solid #2d3f5a" };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
      <thead><tr>
        <th style={{ ...thS, textAlign: "left" }}>Metric</th>
        <th style={{ ...thS, textAlign: "right" }}>Value</th>
      </tr></thead>
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

// ── Slider row ────────────────────────────────────────────────────────────────

function SliderRow({ label, value, min, max, step, onChange, suffix = "" }: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; suffix?: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: "0.72em", fontWeight: 600, color: NAVY, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input type="range" min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ flex: 1, accentColor: NAVY }} />
        <input type="number" min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ width: 68, padding: "3px 6px", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.82em", fontFamily: "inherit", textAlign: "right", background: CLR_USER_BG }} />
        {suffix && <span style={{ fontSize: "0.78em", color: "#6b7280", flexShrink: 0 }}>{suffix}</span>}
      </div>
    </div>
  );
}

// ── IRR cashflow table ────────────────────────────────────────────────────────

function IrrTable({ data, baseYear }: { data: CfIrrSpecialData; baseYear: number }) {
  if (!data.eps_forecast.length || data.price_now == null || data.avg_target == null) return null;
  const rows = [];
  rows.push({ year: `0  (${baseYear})`, eps: "", terminal: "", total: f$(-data.price_now) });
  for (let i = 0; i < data.eps_forecast.length - 1; i++) {
    const r = data.eps_forecast[i];
    rows.push({ year: r.Year, eps: f$(r["Est. EPS"]), terminal: "", total: f$(r["Est. EPS"]) });
  }
  const last = data.eps_forecast[data.eps_forecast.length - 1];
  rows.push({
    year: last.Year,
    eps: f$(last["Est. EPS"]),
    terminal: f$(data.avg_target),
    total: f$((last["Est. EPS"] ?? 0) + (data.avg_target ?? 0)),
  });

  const thS: React.CSSProperties = { background: NAVY, color: "#fff", padding: "6px 10px", fontSize: "0.76em", border: "1px solid #2d3f5a", whiteSpace: "nowrap" };
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.81em" }}>
        <thead>
          <tr>
            <th style={{ ...thS, textAlign: "left", minWidth: 110 }}>Year</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 90 }}>Est. EPS</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 110 }}>Terminal Value</th>
            <th style={{ ...thS, textAlign: "right", minWidth: 120 }}>Total Cash Flow</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ background: i === 0 ? CLR_FAIL : i === rows.length - 1 ? CLR_CALC_BG : i % 2 === 0 ? "#fff" : "#f8fafc" }}>
              <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY }}>{r.year}</td>
              <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: CLR_CALC_FG }}>{r.eps || "—"}</td>
              <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, color: CLR_API_FG, fontWeight: r.terminal ? 700 : 400 }}>{r.terminal || "—"}</td>
              <td style={{ padding: "5px 10px", border: "1px solid #e5e7eb", textAlign: "right", ...MONO, fontWeight: 700, color: i === 0 ? CLR_FAIL_FG : CLR_CALC_FG }}>{r.total}</td>
            </tr>
          ))}
        </tbody>
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

export default function CfIrrSpecialTab({ ticker, externalWacc }: Props) {
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
  const [tbvWeight,  setTbvWeight]  = useState(50);  // percentage of TBV weight (50 = 50%)
  const [mosPct,     setMosPct]     = useState(10.0);

  const waccPct = externalWacc > 0 ? externalWacc : (data?.wacc_computed ?? 0) * 100;

  const seeded = useRef(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // ── URL builder ───────────────────────────────────────────────────────────
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

  // ── Initial load ──────────────────────────────────────────────────────────
  useEffect(() => {
    seeded.current = false;
    setData(null); setError(null); setLoading(true);
    setTbvGrowth([5,5,5,5,5,5,5,5,5]);
    setEpsGrowth([5,5,5,5,5,5,5,5,5]);
    setExitPtbv(1.5); setExitPe(15.0); setTbvWeight(50); setMosPct(10.0);
  }, [ticker]);

  useEffect(() => {
    if (!loading && data) return;   // already loaded
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

  // ── Debounced refetch ─────────────────────────────────────────────────────
  const refetch = useCallback((opts?: Parameters<typeof buildUrl>[0]) => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      setLoading(true);
      fetch(buildUrl(opts))
        .then((r) => r.ok ? r.json() : r.json().then((b: { detail?: string }) => Promise.reject(b.detail ?? `HTTP ${r.status}`)))
        .then((d: CfIrrSpecialData) => setData(d))
        .catch((e: unknown) => setError(typeof e === "string" ? e : "Refetch failed"))
        .finally(() => setLoading(false));
    }, 350);
  }, [buildUrl]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleTbvGrowth = (i: number, v: number) => {
    const next = [...tbvGrowth]; next[i] = v; setTbvGrowth(next);
    refetch({ tbv: next });
  };
  const handleTbvGlobal = (v: number) => {
    setTbvGlobal(v); const next = [...tbvGrowth]; next[0] = v; setTbvGrowth(next);
    refetch({ tbv: next });
  };
  const handleEpsGrowth = (i: number, v: number) => {
    const next = [...epsGrowth]; next[i] = v; setEpsGrowth(next);
    refetch({ eps: next });
  };
  const handleEpsGlobal = (v: number) => {
    setEpsGlobal(v); const next = [...epsGrowth]; next[0] = v; setEpsGrowth(next);
    refetch({ eps: next });
  };
  const handleExitPtbv = (v: number) => { setExitPtbv(v);  refetch({ ptbv: v }); };
  const handleExitPe   = (v: number) => { setExitPe(v);    refetch({ pe: v }); };
  const handleTbvWt    = (v: number) => { setTbvWeight(v); refetch({ wt: v }); };
  const handleMos      = (v: number) => { setMosPct(v);    refetch({ mos: v }); };

  if (loading && !data) return <Spinner />;
  if (error)            return <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#991b1b" }}><strong>Error:</strong> {error}</div>;
  if (!data)            return null;

  const baseYear = data.base_year;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ paddingBottom: 40 }}>

      {/* ══ Section 0: Model Inputs ══════════════════════════════════════════ */}
      <SecHeader title="0 · Model Inputs" />
      <Legend />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 20, background: "#fffbeb", border: "1.5px solid #fde68a", borderRadius: 8, padding: "16px 20px", marginTop: 10 }}>
        <SliderRow label="Exit P/TBV Multiple" value={exitPtbv}  min={0.5} max={10}  step={0.1} onChange={handleExitPtbv} suffix="x" />
        <SliderRow label="Exit P/E Multiple"    value={exitPe}   min={5}   max={50}  step={0.5} onChange={handleExitPe}   suffix="x" />
        <SliderRow label="TBV Weight"           value={tbvWeight} min={0}   max={100} step={5}   onChange={handleTbvWt}    suffix="%" />
        <SliderRow label="Margin of Safety"     value={mosPct}   min={0}   max={50}  step={1}   onChange={handleMos}      suffix="%" />
      </div>

      <div style={{ marginTop: 10, padding: "10px 14px", background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: 6, fontSize: "0.80em", color: "#0c4a6e", lineHeight: 1.6 }}>
        <strong>Model Logic:</strong>&nbsp;
        TBV = Total Assets − (Goodwill &amp; Intangibles) − Total Liabilities.&nbsp;
        Terminal Value = <strong>{tbvWeight}%</strong> × (TBV₁₀ × {exitPtbv.toFixed(1)}x P/TBV) +&nbsp;
        <strong>{100 - tbvWeight}%</strong> × (EPS₁₀ × {exitPe.toFixed(1)}x P/E).&nbsp;
        IRR on: [−CurrentPrice, EPS₁..EPS₉, EPS₁₀ + TerminalValue].
      </div>

      {/* ══ Section 1: Checklist + Final Output ═════════════════════════════ */}
      <SecHeader title="1 · Quality Checklist & Final Output" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>
        <div>
          <SubHeader title="Quality Checklist" />
          <Checklist items={data.checklist} />
        </div>
        <div>
          <SubHeader title="Final Output" />
          <FinalOutput data={data} waccPct={waccPct} mosPct={mosPct} />
        </div>
      </div>

      {/* ══ Section 2: Historical ════════════════════════════════════════════ */}
      <SecHeader title="2 · Historical Analysis (TBV + EPS)" />
      <SubHeader title={`Historical Balance Sheet & EPS  (values in $B unless noted)`} />
      <HistTable rows={data.hist} ttm={data.hist_ttm} avg={data.hist_avg} cagr={data.hist_cagr} />

      {/* CAGR summary boxes */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 8, marginBottom: 16 }}>
        {[
          ["Assets CAGR",    data.assets_cagr != null ? fPct(data.assets_cagr) : "N/A", data.assets_cagr != null ? data.assets_cagr >= 0.04 : null],
          ["TBV/s CAGR",     data.tbv_ps_cagr != null ? fPct(data.tbv_ps_cagr) : "N/A", data.tbv_ps_cagr != null ? data.tbv_ps_cagr >= 0.03 : null],
          ["EPS CAGR",       data.eps_cagr != null ? fPct(data.eps_cagr) : "N/A", data.eps_cagr != null ? data.eps_cagr >= 0.10 : null],
          ["Avg Net Margin", data.margin_avg != null ? fPct(data.margin_avg) : "N/A", data.margin_avg != null ? data.margin_avg >= 0.10 : null],
        ].map(([label, val, passed]) => (
          <div key={label as string} style={{
            background: passed === true ? CLR_PASS : passed === false ? CLR_FAIL : CLR_NA,
            borderRadius: 6, padding: "10px 14px", textAlign: "center",
          }}>
            <div style={{ fontSize: "0.65em", textTransform: "uppercase", letterSpacing: "0.07em", color: "#4d6b88", marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: "1.25em", fontWeight: 800, color: passed === true ? CLR_PASS_FG : passed === false ? CLR_FAIL_FG : NAVY }}>{val}</div>
          </div>
        ))}
      </div>

      {/* ══ Section 3: Forecasts ════════════════════════════════════════════ */}
      <SecHeader title="3 · 10-Year Projection" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, alignItems: "start" }}>

        {/* Left: TBV/s Forecast */}
        <div>
          <SubHeader title={`Table 3.1 · TBV/s Forecast  (${baseYear + 1}–${baseYear + 9})`} />
          <ForecastTable
            rows={data.tbv_forecast}
            growthRates={tbvGrowth}
            onGrowthChange={handleTbvGrowth}
            valueKey="Est. TBV/s"
            valueLabel="Est. TBV/s ($)"
            globalRate={tbvGlobal}
            onGlobalChange={handleTbvGlobal}
          />
          {/* TBV summary box */}
          <div style={{ marginTop: 12, background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: 6, padding: "10px 14px", fontSize: "0.82em" }}>
            {[
              [`Est. TBV/s in ${baseYear + 9}`, f$(data.tbv_forecast[8]?.["Est. TBV/s"])],
              [`× P/TBV Multiple`, `${exitPtbv.toFixed(1)}x`],
              [`TBV Terminal Price`, f$(data.tbv_terminal)],
            ].map(([label, val], i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: i < 2 ? "1px solid #e0f2fe" : "none" }}>
                <span style={{ color: "#0c4a6e" }}>{label}</span>
                <span style={{ fontWeight: 700, color: NAVY, ...MONO }}>{val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: EPS Forecast */}
        <div>
          <SubHeader title={`Table 3.2 · EPS Forecast  (${baseYear + 1}–${baseYear + 9})`} />
          <ForecastTable
            rows={data.eps_forecast}
            growthRates={epsGrowth}
            onGrowthChange={handleEpsGrowth}
            valueKey="Est. EPS"
            valueLabel="Est. EPS ($)"
            globalRate={epsGlobal}
            onGlobalChange={handleEpsGlobal}
          />
          {/* EPS summary box */}
          <div style={{ marginTop: 12, background: "#f0fff4", border: "1px solid #bbf7d0", borderRadius: 6, padding: "10px 14px", fontSize: "0.82em" }}>
            {[
              [`Est. EPS in ${baseYear + 9}`,  f$(data.eps_forecast[8]?.["Est. EPS"])],
              [`× P/E Multiple`,               `${exitPe.toFixed(1)}x`],
              [`EPS Terminal Price`,            f$(data.eps_terminal)],
            ].map(([label, val], i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: i < 2 ? "1px solid #dcfce7" : "none" }}>
                <span style={{ color: "#14532d" }}>{label}</span>
                <span style={{ fontWeight: 700, color: NAVY, ...MONO }}>{val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Terminal value blend */}
      <div style={{ marginTop: 16, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, padding: "12px 16px" }}>
        <div style={{ fontSize: "0.80em", fontWeight: 700, color: NAVY, marginBottom: 8 }}>
          Average Target Price (Weighted Terminal Value)
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {[
            [`${tbvWeight}% TBV Terminal`,       f$(data.tbv_terminal),  CLR_API_BG,  CLR_API_FG],
            [`${100 - tbvWeight}% EPS Terminal`,  f$(data.eps_terminal),  CLR_CALC_BG, CLR_CALC_FG],
            [`Average Target Price`,              f$(data.avg_target),    NAVY,        "#fff"],
          ].map(([label, val, bg, fg]) => (
            <div key={label as string} style={{ background: bg as string, borderRadius: 6, padding: "10px 14px", textAlign: "center" }}>
              <div style={{ fontSize: "0.68em", color: bg === NAVY ? "#94a3b8" : "#4d6b88", marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: "1.35em", fontWeight: 800, color: fg as string, ...MONO }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ══ Section 4: IRR Analysis ══════════════════════════════════════════ */}
      <SecHeader title="4 · IRR Analysis" />
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, alignItems: "start" }}>
        <div>
          <SubHeader title="IRR Cash Flow Table" />
          <div style={{ fontSize: "0.78em", color: "#4d6b88", marginBottom: 8, lineHeight: 1.5 }}>
            Entry cost = current stock price. Annual income = projected EPS.
            Year {baseYear + 9}: EPS + Average Target Price (terminal exit value).
          </div>
          <IrrTable data={data} baseYear={baseYear} />
        </div>
        <div>
          <SubHeader title="IRR Summary" />
          {[
            ["Current Price (Entry)",    f$(data.price_now),                              null],
            ["IRR",                      data.irr != null ? fPct(data.irr) : "N/A",       data.irr != null ? data.irr >= 0.12 : null],
            ["IRR ≥ 12% target?",        data.irr != null ? (data.irr >= 0.12 ? "✅ YES" : "❌ NO") : "N/A", data.irr != null ? data.irr >= 0.12 : null],
            ["Average Target Price",     f$(data.avg_target),                             null],
            ["Fair Value (WACC disc.)",  (() => { const fv = data.avg_target != null && waccPct > 0 ? data.avg_target / (1 + waccPct / 100) ** 9 : null; return f$(fv); })(), null],
            ["Buy Price",                (() => { const fv = data.avg_target != null && waccPct > 0 ? data.avg_target / (1 + waccPct / 100) ** 9 : null; const bp = fv != null ? fv * (1 - mosPct / 100) : null; return f$(bp); })(), null],
          ].map(([label, val, verdict], i) => {
            const bg = verdict === true ? CLR_PASS : verdict === false ? CLR_FAIL : i % 2 === 0 ? "#fff" : "#f8fafc";
            const fg = verdict === true ? CLR_PASS_FG : verdict === false ? CLR_FAIL_FG : NAVY;
            return (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "7px 12px", background: bg, borderBottom: "1px solid #e5e7eb", fontSize: "0.83em" }}>
                <span style={{ fontWeight: 600, color: fg }}>{label}</span>
                <span style={{ fontWeight: 700, color: fg, ...MONO }}>{val}</span>
              </div>
            );
          })}

          <div style={{ marginTop: 18, padding: "12px 14px", background: "#f0f9ff", borderRadius: 6, fontSize: "0.78em", color: "#0c4a6e", lineHeight: 1.6 }}>
            <strong>About the Special Model:</strong> Unlike the standard CF+IRR model
            (which uses EBITDA and FCF), this model values a company primarily through its
            <strong> Tangible Book Value</strong> — what shareholders would own after removing
            goodwill, intangibles, and all liabilities. Ideal for banks, insurance companies,
            and asset-heavy businesses.
          </div>
        </div>
      </div>

      {/* ── Note ────────────────────────────────────────────────────────────── */}
      <div style={{ marginTop: 28, padding: "10px 14px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: "0.78em", color: "#64748b", lineHeight: 1.6 }}>
        <strong>Key Steps:</strong>&nbsp;
        1. Review historical TBV/s and EPS growth.&nbsp;
        2. Set growth rate assumptions for the 9-year projection.&nbsp;
        3. Adjust the exit P/TBV and P/E multiples to reflect your expected valuation at exit.&nbsp;
        4. Tune the TBV/EPS weight to match the company's business model.&nbsp;
        5. Check that IRR ≥ 12% and the stock is trading below Fair Value.
      </div>
    </div>
  );
}
