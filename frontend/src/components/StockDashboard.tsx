/**
 * StockDashboard.tsx
 *
 * Architecture
 * ────────────
 * • On ticker change: fires overview + annual-financials + insights in PARALLEL.
 * • Quarterly financials are fetched lazily (only when period selector is toggled),
 *   then cached so switching back to Annual is instant.
 * • NormalizedPETab manages its own fetch (sliders need per-call API params).
 * • React.memo is applied to the heavy table components inside the tabs.
 * • No data is re-fetched when only a tab, slider, or scale changes.
 */
import { useState, useEffect, useRef, memo } from "react";
import GlobalSearchBar from "./GlobalSearchBar";
import { InsightTooltip } from "./InsightTooltip";
import { clearInsightCache } from "../hooks/useInsight";
import type {
  OverviewData, FinancialsData, InsightsData, WaccData,
  FinancialsExtendedData, NormalizedPEResult, Scale, Period,
} from "../types";
import FinancialsTab from "./FinancialsTab";
import InsightsTab   from "./InsightsTab";
import SegmentsTab              from "./SegmentsTab";
import StockPriceChart          from "./StockPriceChart";
import CompanyInsightsFeed      from "./CompanyInsightsFeed";
import CompanyOwnershipChart    from "./CompanyOwnershipChart";
import GrokSentimentBadge from "./GrokSentimentBadge";
import Valueground from "./Valueground";

// ── Palette ───────────────────────────────────────────────────────────────────
const NAVY    = "var(--gv-navy)";
const BLUE    = "var(--gv-blue)";
// const RED_BTN = "#ff4b4b"; // removed — Analyze button replaced by GlobalSearchBar

const C = {
  Y_BG:  "var(--gv-yellow-bg)",  Y_FG:  "var(--gv-yellow-fg)",
  G_BG:  "var(--gv-green-bg)",   G_FG:  "var(--gv-green)",
  D_BG:  "var(--gv-data-bg)",    D_FG:  "var(--gv-data-fg)",
  GN_BG: "var(--gv-green-mid)",  GN_FG: "#14532d",
  RD_BG: "var(--gv-red-mid)",    RD_FG: "#7f1d1d",
  POS_BG:"var(--gv-green-bg)",   POS_FG:"var(--gv-green)",
  NEG_BG:"var(--gv-red-bg)",     NEG_FG:"var(--gv-red)",
};

// ── Formatters ────────────────────────────────────────────────────────────────
const f$ = (v: number | null) =>
  v == null ? "N/A" : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fPct  = (v: number, d = 1) => `${v.toFixed(d)}%`;
const fCagr = (v: number | string | null) =>
  v == null || v === "N/M" ? "N/M" : typeof v === "number" ? `${(v * 100).toFixed(1)}%` : String(v);
const fUpside = (v: number | null) => {
  if (v == null) return { str: "N/A", pos: null };
  const p = v * 100;
  return { str: `${p >= 0 ? "+" : ""}${p.toFixed(1)}%`, pos: p > 0 };
};

// ── Shared atoms ──────────────────────────────────────────────────────────────

function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "48px 0", color: "var(--gv-text-muted)" }}>
      <div style={{ width: 30, height: 30, borderRadius: "50%", border: "3px solid var(--gv-border)", borderTop: `3px solid ${BLUE}`, animation: "gvSD 0.75s linear infinite", flexShrink: 0 }} />
      <span style={{ fontSize: "0.88em" }}>{label}</span>
      <style>{`@keyframes gvSD { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ErrBox({ msg }: { msg: string }) {
  return (
    <div style={{ background: "var(--gv-red-bg)", border: "1px solid var(--gv-red-mid)", borderRadius: 8, padding: "12px 16px", color: "var(--gv-red)" }}>
      <strong>Error:</strong> {msg}
    </div>
  );
}

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "1.05em", fontWeight: "bold", color: "var(--gv-surface)", background: NAVY, padding: "6px 15px", borderRadius: 4, marginTop: 24, marginBottom: 6 }}>
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
function DescriptionSkeleton() {
  return (
    <div>
      <style>{`@keyframes ds{0%{background-position:-200% 0}100%{background-position:200% 0}}.ds{background:linear-gradient(90deg,#f0f2f5 25%,#e2e6ea 50%,#f0f2f5 75%);background-size:200% 100%;animation:ds 1.4s infinite;border-radius:4px;}`}</style>
      {[90, 75, 85].map((w, i) => (
        <div key={i} className="ds" style={{ height: 13, width: `${w}%`, marginBottom: 8 }} />
      ))}
    </div>
  );
}

function Legend() {
  return (
    <div style={{ fontSize: "0.75em", color: "var(--gv-text-muted)", marginTop: 6 }}>
      {[{ bg: C.Y_BG, fg: C.Y_FG, lbl: "Editable" }, { bg: C.G_BG, fg: C.G_FG, lbl: "Formula" }, { bg: C.D_BG, fg: C.D_FG, lbl: "Data" }].map(({ bg, fg, lbl }) => (
        <span key={lbl} style={{ background: bg, padding: "2px 7px", borderRadius: 3, color: fg, marginRight: 8 }}>&#9632; {lbl}</span>
      ))}
    </div>
  );
}

// ── Tab bars ──────────────────────────────────────────────────────────────────

const MAIN_TABS = ["Overview", "Financials", "Insights", "Valueground"] as const;
type MainTab = typeof MAIN_TABS[number];

function TabBar({ tabs, active, onSelect, size = "md", scrollable = false }: {
  tabs: readonly string[];
  active: string;
  onSelect: (t: string) => void;
  size?: "md" | "sm";
  scrollable?: boolean;
}) {
  return (
    <div style={{
      display: "flex",
      borderBottom: `2px solid var(--gv-border)`,
      marginBottom: size === "md" ? 20 : 12,
      overflowX: scrollable ? "auto" : undefined,
      scrollbarWidth: "none",
    }}>
      {tabs.map((t) => {
        const active_ = t === active;
        return (
          <button key={t} onClick={() => onSelect(t)} style={{
            padding: size === "md" ? "10px 22px" : "7px 16px",
            border: "none", background: "none", cursor: "pointer",
            fontWeight: active_ ? 700 : 500,
            color: active_ ? BLUE : "var(--gv-text-muted)",
            borderBottom: active_ ? `2px solid ${BLUE}` : "2px solid transparent",
            marginBottom: -2,
            fontSize: size === "md" ? "0.93em" : "0.86em",
            fontFamily: "inherit", whiteSpace: "nowrap",
            transition: "color 0.12s",
          }}>
            {t}
          </button>
        );
      })}
    </div>
  );
}

// ── Slider ────────────────────────────────────────────────────────────────────

function SliderInput({ label, value, min, max, step, unit = "", disabled = false, onChange }: {
  label: string; value: number; min: number; max: number; step: number;
  unit?: string; disabled?: boolean; onChange: (v: number) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>
        {label}: <span style={{ color: C.Y_FG, fontWeight: 700 }}>{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ accentColor: "#f59e0b", width: "100%", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1 }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68em", color: "var(--gv-text-muted)" }}>
        <span>{min}{unit}</span><span>{max}{unit}</span>
      </div>
    </div>
  );
}

// ── Valuation tables ──────────────────────────────────────────────────────────

interface T1Row { label: string; value: string; bg?: string; fg?: string; kind: "data"|"edit"|"formula"|"special"; bold?: boolean; }
interface T2Row { label: string; value: string; note: string; bg: string; fg: string; }

const ValTable1 = memo(function ValTable1({ rows }: { rows: T1Row[] }) {
  const th: React.CSSProperties = { background: NAVY, color: "var(--gv-surface)", fontWeight: 700, padding: "7px 12px", border: "1px solid #334" };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82em" }}>
      <thead><tr><th style={{ ...th, textAlign: "left" }}>Metric</th><th style={{ ...th, textAlign: "right" }}>Value</th></tr></thead>
      <tbody>
        {rows.map((r, i) => {
          const bg = r.bg ?? (r.kind === "formula" ? C.G_BG : r.kind === "edit" ? C.Y_BG : C.D_BG);
          const fg = r.fg ?? (r.kind === "formula" ? C.G_FG : r.kind === "edit" ? C.Y_FG : C.D_FG);
          return (
            <tr key={i} style={{ background: bg }}>
              <td style={{ padding: "6px 12px", border: "1px solid var(--gv-border)", color: fg, fontWeight: 600 }}>{r.label}</td>
              <td style={{ padding: "6px 12px", border: "1px solid var(--gv-border)", color: fg, fontWeight: r.bold ? 700 : 500, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{r.value}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
});

const ValTable2 = memo(function ValTable2({ rows }: { rows: T2Row[] }) {
  const th: React.CSSProperties = { background: NAVY, color: "var(--gv-surface)", fontWeight: 700, padding: "7px 12px", border: "1px solid #334", textAlign: "left" };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82em" }}>
      <thead><tr><th style={th}>Component</th><th style={{ ...th, textAlign: "right" }}>Value</th><th style={th}>Note</th></tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ background: r.bg }}>
            <td style={{ padding: "6px 12px", border: "1px solid var(--gv-border)", color: r.fg, fontWeight: 700 }}>{r.label}</td>
            <td style={{ padding: "6px 12px", border: "1px solid var(--gv-border)", color: r.fg, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{r.value}</td>
            <td style={{ padding: "6px 12px", border: "1px solid var(--gv-border)", color: "var(--gv-text-muted)", fontStyle: "italic", fontSize: "0.93em" }}>{r.note}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
});

// ── Normalized PE tab (self-contained: manages sliders + own fetch) ───────────

interface Sliders { growthPct: number; years: number; discPct: number; mosPct: number; useWacc: boolean; }

function NormalizedPETab({ ticker, externalWacc }: { ticker: string; externalWacc?: number }) {
  const [data, setData]       = useState<NormalizedPEResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [sliders, setSliders] = useState<Sliders>({ growthPct: 5, years: 7, discPct: 15, mosPct: 15, useWacc: false });
  const debounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    setLoading(true); setError(null); setData(null);
    clearTimeout(debounce.current);
    fetch(`/api/normalized-pe/${ticker}`)
      .then((r) => { if (!r.ok) return r.json().then((b) => Promise.reject(b.detail ?? `HTTP ${r.status}`)); return r.json(); })
      .then((json: NormalizedPEResult) => { setData(json); setSliders({ growthPct: json.growth_pct, years: json.years, discPct: json.disc_pct, mosPct: json.mos_pct, useWacc: json.use_wacc }); })
      .catch((e: unknown) => setError(typeof e === "string" ? e : "Failed to load valuation"))
      .finally(() => setLoading(false));
  }, [ticker]);

  function applySliders(next: Sliders) {
    setSliders(next);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      // When useWacc is on and caller supplied an external manual WACC, pass it as disc_pct
      const effectiveDisc = (next.useWacc && externalWacc != null && externalWacc > 0)
        ? externalWacc
        : next.discPct;
      const qs = new URLSearchParams({
        growth_pct: String(next.growthPct), years: String(next.years),
        disc_pct: String(effectiveDisc), mos_pct: String(next.mosPct),
        use_wacc: String(next.useWacc),
      });
      fetch(`/api/normalized-pe/${ticker}?${qs}`).then((r) => r.json()).then(setData).catch(console.error);
    }, 350);
  }

  if (loading) return <Spinner label="Computing valuation…" />;
  if (error)   return <ErrBox msg={error} />;
  if (!data)   return null;

  const upFv  = fUpside(data.upside_to_fv);
  const upBuy = fUpside(data.upside_to_buy);
  const onSale = data.on_sale;
  // Show manual WACC if provided, otherwise fall back to API-computed WACC
  const effectiveWaccPct = (externalWacc != null && externalWacc > 0)
    ? externalWacc.toFixed(1)
    : (data.wacc * 100).toFixed(2);

  const t1: T1Row[] = [
    { label: "EPS (TTM)",              value: f$(data.eps_ttm),                                              kind: "data"    },
    { label: "Est. Future Growth (%)", value: fPct(sliders.growthPct),                                        kind: "edit"    },
    { label: "Number of Years",        value: String(sliders.years),                                          kind: "edit"    },
    { label: "Estimated Future EPS",   value: f$(data.future_eps),                                           kind: "formula" },
    { label: "Discount Rate",          value: fPct(data.disc_pct),                                           kind: "edit"    },
    { label: "Discounted EPS",         value: f$(data.discounted_eps),                                       kind: "formula" },
    { label: "Estimated PE",           value: data.pe_c != null ? `${data.pe_c.toFixed(1)}\u00d7` : "N/A",  kind: "formula" },
    { label: "Fair Value Per Share",   value: f$(data.fair_value),                                           kind: "formula", bold: true },
    { label: "Margin of Safety (%)",   value: fPct(sliders.mosPct, 0),                                       kind: "edit"    },
    { label: "Buy Price",              value: f$(data.buy_price),                                            kind: "formula", bold: true },
    { label: "Current Stock Price",    value: f$(data.price_now),                                            kind: "data"    },
    { label: "Company on-sale?",       value: onSale != null ? (onSale ? "ON SALE \u2705" : "NOT ON SALE \u274c") : "N/A",
      kind: "special", bold: true,
      bg: onSale != null ? (onSale ? C.GN_BG : C.RD_BG) : C.D_BG,
      fg: onSale != null ? (onSale ? C.GN_FG : C.RD_FG) : C.D_FG },
    { label: "Upside to Fair Value",   value: upFv.str,  kind: "special",
      bg: upFv.pos  === true ? C.POS_BG : upFv.pos  === false ? C.NEG_BG : C.D_BG,
      fg: upFv.pos  === true ? C.POS_FG : upFv.pos  === false ? C.NEG_FG : C.D_FG },
    { label: "Upside to Buy Price",    value: upBuy.str, kind: "special",
      bg: upBuy.pos === true ? C.POS_BG : upBuy.pos === false ? C.NEG_BG : C.D_BG,
      fg: upBuy.pos === true ? C.POS_FG : upBuy.pos === false ? C.NEG_FG : C.D_FG },
  ];

  const t2: T2Row[] = [
    { label: "(a)  Default PE",    value: `${data.pe_a.toFixed(1)}\u00d7`,                              note: `Rule of thumb: 2 \u00d7 Growth Rate  (${sliders.growthPct.toFixed(1)}% \u00d7 2 = ${data.pe_a.toFixed(1)}\u00d7)`, bg: C.G_BG, fg: C.G_FG },
    { label: "(b)  Historical PE", value: data.pe_b != null ? `${data.pe_b.toFixed(1)}\u00d7` : "N/A", note: "10-year average P/E from Valuation Multiples",                                                                          bg: C.D_BG, fg: C.D_FG },
    { label: "(c)  Estimated PE",  value: data.pe_c != null ? `${data.pe_c.toFixed(1)}\u00d7` : "N/A", note: "Conservative PE: MIN(a, b)  \u2014  per Phil Town\u2019s Rule #1",                                                     bg: C.Y_BG, fg: C.Y_FG },
  ];

  return (
    <>
      <SecHeader title="Normalized PE  \u00b7  Phil Town Rule #1" />
      <SubHeader title="Table 1  \u00b7  Valuation Results" />
      <ValTable1 rows={t1} />
      <Legend />

      <div style={{ marginTop: 18 }} />
      <SubHeader title="Table 2  \u00b7  Estimated PE  (Conservative P/E Calculation)" />
      <ValTable2 rows={t2} />

      <div style={{ marginTop: 22 }} />
      <SubHeader title="Model Inputs" />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 20, background: "#fffbeb", border: "1.5px solid #fde68a", borderRadius: 8, padding: "16px 20px", marginTop: 6 }}>
        <SliderInput label="Est. Future Growth" value={sliders.growthPct} min={0}  max={50} step={0.5} unit="%" onChange={(v) => applySliders({ ...sliders, growthPct: v })} />
        <SliderInput label="Number of Years"    value={sliders.years}     min={1}  max={20} step={1}   onChange={(v) => applySliders({ ...sliders, years: v })} />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>Use WACC</div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, cursor: "pointer" }}>
            <input type="checkbox" checked={sliders.useWacc} onChange={(e) => applySliders({ ...sliders, useWacc: e.target.checked })} style={{ accentColor: BLUE, width: 16, height: 16 }} />
            <span style={{ fontSize: "0.85em", color: "var(--gv-data-fg)" }}>WACC = {effectiveWaccPct}%</span>
          </label>
        </div>
        <SliderInput label="Discount Rate"    value={sliders.discPct} min={1}  max={40} step={0.5} unit="%" disabled={sliders.useWacc} onChange={(v) => applySliders({ ...sliders, discPct: v })} />
        <SliderInput label="Margin of Safety" value={sliders.mosPct}  min={0}  max={80} step={5}   unit="%" onChange={(v) => applySliders({ ...sliders, mosPct: v })} />
      </div>

      <div style={{ marginTop: 22 }} />
      <SubHeader title="EPS CAGR  \u00b7  Used for default growth rate" />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", border: "1px solid var(--gv-border)", borderRadius: 6, overflow: "hidden" }}>
        {[{ lbl: "3-Year", val: fCagr(data.eps_3yr) }, { lbl: "5-Year", val: fCagr(data.eps_5yr) }, { lbl: "10-Year", val: fCagr(data.eps_10yr) }].map(({ lbl, val }, i) => (
          <div key={lbl} style={{ background: C.D_BG, padding: 16, textAlign: "center", borderRight: i < 2 ? "1px solid var(--gv-border)" : "none" }}>
            <div style={{ fontSize: "0.68em", color: "var(--gv-text-muted)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>{lbl} CAGR</div>
            <div style={{ fontSize: "1.25em", fontWeight: 700, color: C.D_FG }}>{val}</div>
          </div>
        ))}
      </div>
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export interface StockDashboardProps {
  ticker: string;
  onSearch: (t: string | null) => void;
}

export default function StockDashboard({ ticker, onSearch }: StockDashboardProps) {

  // ── Overview ──────────────────────────────────────────────────────────────
  const [ov,         setOv]         = useState<OverviewData | null>(null);
  const [ovErr,      setOvErr]      = useState<string | null>(null);
  const [ovLoad,     setOvLoad]     = useState(true);
  const [descSummary,setDescSummary]= useState<string | null>(null);
  const [descLoad,   setDescLoad]   = useState(false);

  // ── Financials (annual cached at load; quarterly lazy) ────────────────────
  const [finA,    setFinA]    = useState<FinancialsData | null>(null);
  const [finQ,    setFinQ]    = useState<FinancialsData | null>(null);
  const [finLoad, setFinLoad] = useState(true);
  const [finQLoad,setFinQLoad]= useState(false);

  // ── Financials Extended ───────────────────────────────────────────────────
  const [finExt,    setFinExt]    = useState<FinancialsExtendedData | null>(null);
  const [finExtLoad,setFinExtLoad]= useState(true);

  // ── Insights ──────────────────────────────────────────────────────────────
  const [ins,     setIns]     = useState<InsightsData | null>(null);
  const [insErr,  setInsErr]  = useState<string | null>(null);
  const [insLoad, setInsLoad] = useState(true);

  // ── WACC ──────────────────────────────────────────────────────────────────
  const [waccData,    setWaccData]    = useState<WaccData | null>(null);
  const [manualWacc,  setManualWacc]  = useState<number>(10);

  // ── Filing links: SEC iXBRL for US, EODHD portal URLs for intl ───────────
  const [filingLinks, setFilingLinks] = useState<Record<string, string>>({});

  // ── UI state ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab]   = useState<MainTab>(() => {
    // Restore the last active tab so a browser refresh keeps the user in place
    const saved = sessionStorage.getItem("gv_tab") as MainTab | null;
    return saved && (MAIN_TABS as readonly string[]).includes(saved) ? saved : "Overview";
  });
  const [period,    setPeriod]      = useState<Period>("annual");
  const [scale,     setScale]       = useState<Scale>("MM");
  const [, setSearchQ] = useState("");
  // Fair values exported from individual valuation tabs (for future Outlook summary)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_ddmFairValue, setDdmFairValue] = useState<number | null>(null);

  // ── Parallel fetch on ticker change ──────────────────────────────────────
  useEffect(() => {
    clearInsightCache();
    setOv(null);          setOvErr(null);   setOvLoad(true);
    setDescSummary(null); setDescLoad(false);
    setFinA(null);     setFinQ(null);    setFinLoad(true);
    setFinExt(null);   setFinExtLoad(true);
    setIns(null);      setInsErr(null);  setInsLoad(true);
    setWaccData(null);
    setFilingLinks({});
    setPeriod("annual");

    const load = <T,>(url: string, set: (d: T) => void, setErr: (e: string | null) => void, setLoading: (b: boolean) => void) =>
      fetch(url)
        .then((r) => { if (!r.ok) return r.json().then((b) => Promise.reject(b.detail ?? `HTTP ${r.status}`)); return r.json(); })
        .then((d: T) => { console.log(`[API] ${url}`, d); set(d); })
        .catch((e: unknown) => { console.error(`[API] ${url} FAILED:`, e); setErr(typeof e === "string" ? e : "Failed to load"); })
        .finally(() => setLoading(false));

    load<OverviewData>          (`/api/overview/${ticker}`,                          setOv,    setOvErr,  setOvLoad);
    load<FinancialsData>        (`/api/financials/${ticker}?period=annual`,          setFinA,  () => {},  setFinLoad);
    load<FinancialsExtendedData>(`/api/financials-extended/${ticker}?period=annual`, setFinExt,() => {},  setFinExtLoad);
    load<InsightsData>          (`/api/insights/${ticker}`,                          setIns,   setInsErr, setInsLoad);

    // Fetch filing links (US → SEC EDGAR iXBRL; intl → EODHD portal; non-critical)
    fetch(`/api/sec-filings/${encodeURIComponent(ticker)}`)
      .then(r => r.ok ? r.json() : {})
      .then((d: Record<string, string>) => setFilingLinks(d))
      .catch(() => { /* best-effort */ });

    // Description condensing triggered by ov load (see separate useEffect below)

    // Fetch WACC components (non-critical — silently ignore errors)
    fetch(`/api/wacc/${ticker}`)
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((d: WaccData) => {
        setWaccData(d);
        // Seed manual slider with computed WACC (converted to %)
        if (d.wacc != null && d.wacc > 0) {
          setManualWacc(parseFloat((d.wacc * 100).toFixed(2)));
        }
      })
      .catch(() => { /* WACC is best-effort */ });
  }, [ticker]);

  // ── Condense description once ov loads ───────────────────────────────────
  useEffect(() => {
    if (!ov?.description || ov.description.length < 100) return;
    setDescLoad(true);
    fetch("/api/condense-description", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker:      ov.ticker,
        description: ov.description,
        sector:      ov.sector,
        industry:    ov.industry,
      }),
    })
      .then(r => r.json())
      .then(d => setDescSummary(d.summary ?? null))
      .catch(() => setDescSummary(null))
      .finally(() => setDescLoad(false));
  }, [ov?.ticker]);

  // ── Lazy-fetch quarterly financials ──────────────────────────────────────
  function handlePeriodChange(p: Period) {
    setPeriod(p);
    if (p === "quarterly" && !finQ) {
      setFinQLoad(true);
      fetch(`/api/financials/${ticker}?period=quarterly`)
        .then((r) => r.json())
        .then((d: FinancialsData) => setFinQ(d))
        .catch(console.error)
        .finally(() => setFinQLoad(false));
    }
  }

  const currentFin   = period === "annual" ? finA : finQ;
  const currentFinLoad = period === "annual" ? finLoad : finQLoad;

  // ── Price display ─────────────────────────────────────────────────────────
  const price    = ov?.price ?? null;
  const chg      = ov?.price_change_pct ?? 0;
  const priceFmt = price != null && price !== 0
    ? `$${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : "N/A";
  const chgFmt   = `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%`;
  const chgColor = chg >= 0 ? "#22c55e" : "#ef4444";

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: "100vh", background: "var(--gv-surface)", fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif", color: NAVY }}>

      {/* ════ TOP BAR ════════════════════════════════════════════════════════ */}
      <div style={{
        background: "var(--gv-surface)", borderBottom: "1px solid var(--gv-border)",
        padding: "10px 24px", display: "flex", alignItems: "center", gap: 16,
        position: "sticky", top: 0, zIndex: 20,
        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
      }}>
        <div style={{ flexShrink: 0 }}>
          <img src="/logo.svg" alt="getValue" style={{ height: 38, display: "block" }} />
        </div>
        <div style={{ flex: 1, maxWidth: 560, margin: "0 auto" }}>
          <GlobalSearchBar onSelect={(t) => { onSearch(t); setSearchQ(""); }} />
        </div>
      </div>

      {/* ════ MAIN CONTENT ═══════════════════════════════════════════════════ */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 20px" }}>

        {/* ── Company header strip ─────────────────────────────────────────── */}
        {ovLoad && <Spinner label={`Loading ${ticker}…`} />}
        {ovErr  && <div style={{ padding: "16px 0" }}><ErrBox msg={ovErr} /></div>}

        {ov && !ovLoad && (
          <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "16px 0 20px", borderBottom: `2px solid ${NAVY}`, marginBottom: 6 }}>

            {/* Logo */}
            <div style={{ flexShrink: 0 }}>
              {ov.logo_url ? (
                <img src={ov.logo_url} alt={ov.company_name} width={54} height={54}
                  style={{ borderRadius: 10, objectFit: "contain", background: "#eef1f6", padding: 4 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <div style={{ width: 54, height: 54, background: "#eef1f6", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.8em" }}>
                  {ov.flag || "🏳️"}
                </div>
              )}
            </div>

            {/* Identity: flag + name + ticker + exchange + price */}
            <div style={{ flexShrink: 0, minWidth: 190 }}>
              <div style={{ fontSize: "1.22em", fontWeight: 700, color: "#0d1b2a", lineHeight: 1.2 }}>
                {ov.flag}&nbsp;{ov.company_name}
              </div>
              <div style={{ fontSize: "0.80em", color: "var(--gv-text-dim)", marginTop: 3 }}>
                {[ticker, ov.exchange, ov.sector].filter(Boolean).join(" · ")}
              </div>
              <div style={{ marginTop: 8 }}>
                <span style={{ fontSize: "1.45em", fontWeight: 800, color: "#0d1b2a", fontFamily: "monospace" }}>
                  {priceFmt}
                </span>
                {" "}
                <span style={{ fontSize: "0.90em", fontWeight: 700, color: chgColor }}>{chgFmt}</span>
              </div>
            </div>

            {/* 15-cell metric grid (5 cols × 3 rows) */}
            {ov.metrics.length > 0 && (
              <div style={{ flex: 1, display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "10px 12px", paddingLeft: 20, borderLeft: "1px solid var(--gv-border-dark)" }}>
                {ov.metrics.map((m) => (
                  <div key={m.label} style={{ minWidth: 0 }}>
                    <div style={{ fontSize: "0.60em", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--gv-text-dim)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginBottom: 2 }}>
                      {m.label}
                    </div>
                    <div style={{ fontSize: "0.86em", fontWeight: 700, color: m.color ?? "var(--gv-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "flex", alignItems: "center", gap: 2 }}>
                      {m.value}
                      <InsightTooltip
                        metric={m.label}
                        value={m.value}
                        ticker={ticker}
                        context={{ sector: ov.sector, industry: ov.industry, company_name: ov.company_name }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ════ TABS ═══════════════════════════════════════════════════════════ */}
        {!ovLoad && (
          <>
            <TabBar tabs={MAIN_TABS} active={activeTab} onSelect={(t) => {
              const tab = t as MainTab;
              setActiveTab(tab);
              sessionStorage.setItem("gv_tab", tab);
            }} />

            {/* ══ Overview ══ */}
            {activeTab === "Overview" && (
              ov
                ? <div style={{ maxWidth: 960, marginTop: 8 }}>

                    {/* Grok sentiment badge */}
                    <div style={{ marginTop: 10, marginBottom: 8, display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: "0.72em", color: "var(--gv-text-dim)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em" }}>
                        Sentiment
                      </span>
                      <GrokSentimentBadge ticker={ticker} />
                    </div>

                    {/* Row 1: AI Description (left) + Price Chart (right) */}
                    <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-start" }}>

                      {/* Left: Condensed About */}
                      <div style={{ flex: 1, minWidth: 280 }}>
                        <h4 style={{ fontSize: "0.72em", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--gv-text-dim)", margin: "0 0 8px" }}>
                          About
                        </h4>
                        {descLoad ? (
                          <DescriptionSkeleton />
                        ) : (descSummary || ov.description) ? (
                          <p style={{ color: "var(--gv-text-dim)", fontSize: "0.91em", lineHeight: 1.75, margin: 0 }}>
                            {descSummary || ov.description}
                          </p>
                        ) : (
                          <p style={{ color: "var(--gv-text-muted)", fontStyle: "italic", margin: 0 }}>No description available.</p>
                        )}
                      </div>

                      {/* Right: Price Chart */}
                      <div style={{ flex: "1.4 1 360px", minWidth: 340 }}>
                        <h4 style={{ fontSize: "0.72em", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--gv-text-dim)", margin: "0 0 8px" }}>
                          Price History
                        </h4>
                        <StockPriceChart ticker={ticker} />
                      </div>
                    </div>

                    {/* Row 2: Ownership Structure */}
                    <CompanyOwnershipChart ticker={ticker} />

                    {/* Row 3: News & Insights feed */}
                    <CompanyInsightsFeed ticker={ticker} ov={ov} />

                    <SegmentsTab ticker={ticker} />
                  </div>
                : null
            )}

            {/* ══ Financials ══ */}
            {activeTab === "Financials" && (
              <FinancialsTab
                ticker={ticker}
                data={currentFin}
                loading={currentFinLoad}
                extData={finExt}
                extLoading={finExtLoad}
                period={period}
                scale={scale}
                onPeriodChange={handlePeriodChange}
                onScaleChange={setScale}
                filingLinks={filingLinks}
              />
            )}

            {/* ══ Insights ══ */}
            {activeTab === "Insights" && (
              <InsightsTab
                data={ins}
                loading={insLoad}
                error={insErr}
                waccData={waccData}
                manualWacc={manualWacc}
                onWaccChange={setManualWacc}
              />
            )}

            {/* ══ Valueground ══ */}
            {activeTab === "Valueground" && (
              <Valueground
                ticker={ticker}
                externalWacc={manualWacc ?? 0}
                ov={ov}
                onDdmFairValue={setDdmFairValue}
                NormalizedPENode={<NormalizedPETab ticker={ticker} externalWacc={manualWacc ?? 0} />}
              />
            )}
          </>
        )}

        <div style={{ height: 48 }} />
      </div>
    </div>
  );
}
