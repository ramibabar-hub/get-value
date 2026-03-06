import { useState, useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { NormalizedPEResult } from "../types";

// ── Color palette (matches normalized_pe_tab.py exactly) ─────────────────────
const C = {
  Y_BG: "#fef9c3", Y_FG: "#78350f",   // yellow  — editable input
  G_BG: "#d1fae5", G_FG: "#065f46",   // green   — formula / computed
  D_BG: "#f3f4f6", D_FG: "#374151",   // grey    — auto-pulled data
  GN_BG: "#86efac", GN_FG: "#14532d", // bright green — ON SALE
  RD_BG: "#fca5a5", RD_FG: "#7f1d1d", // soft red     — NOT ON SALE
  POS_BG: "#d1fae5", POS_FG: "#065f46",
  NEG_BG: "#fee2e2", NEG_FG: "#991b1b",
};
const BLUE = "#007bff";
const NAVY = "#1c2b46";

// ── Formatters ────────────────────────────────────────────────────────────────
function f$(v: number | null): string {
  if (v == null) return "N/A";
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function fPct(v: number, dec = 1): string { return `${v.toFixed(dec)}%`; }
function fCagr(v: number | string | null): string {
  if (v == null || v === "N/M") return "N/M";
  if (typeof v === "number") return `${(v * 100).toFixed(1)}%`;
  return String(v);
}
function fUpside(v: number | null): { str: string; pos: boolean | null } {
  if (v == null) return { str: "N/A", pos: null };
  const pct = v * 100;
  return { str: `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`, pos: pct > 0 };
}

// ── Shared UI atoms ───────────────────────────────────────────────────────────

function SecHeader({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: "1.05em", fontWeight: "bold", color: "#fff",
      background: NAVY, padding: "6px 15px", borderRadius: 4,
      marginTop: 24, marginBottom: 6,
    }}>
      {title}
    </div>
  );
}

function SubHeader({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: "0.88em", fontWeight: 700, color: NAVY,
      borderLeft: `3px solid ${NAVY}`, paddingLeft: 8,
      marginTop: 14, marginBottom: 4,
    }}>
      {title}
    </div>
  );
}

function Legend() {
  return (
    <div style={{ fontSize: "0.75em", color: "#6b7280", marginTop: 6 }}>
      {[
        { bg: C.Y_BG, fg: C.Y_FG, label: "Editable" },
        { bg: C.G_BG, fg: C.G_FG, label: "Formula"  },
        { bg: C.D_BG, fg: C.D_FG, label: "Data"     },
      ].map(({ bg, fg, label }) => (
        <span key={label} style={{ background: bg, padding: "2px 7px", borderRadius: 3, color: fg, marginRight: 8 }}>
          &#9632; {label}
        </span>
      ))}
    </div>
  );
}

function Spinner() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "48px 0" }}>
      <div style={{
        width: 34, height: 34,
        border: "3px solid #e5e7eb",
        borderTop: `3px solid ${BLUE}`,
        borderRadius: "50%",
        animation: "gv-spin 0.75s linear infinite",
      }} />
      <span style={{ fontSize: "0.88em", color: "#6b7280" }}>Fetching financial data…</span>
      <style>{`@keyframes gv-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Tab bar ───────────────────────────────────────────────────────────────────

const TABS = ["Normalized PE", "Insights", "DCF / Valuations"] as const;
type Tab = typeof TABS[number];

function TabBar({ active, onSelect }: { active: Tab; onSelect: (t: Tab) => void }) {
  return (
    <div style={{ display: "flex", borderBottom: "2px solid #e5e7eb", marginBottom: 20 }}>
      {TABS.map((t) => {
        const isActive = t === active;
        return (
          <button
            key={t}
            onClick={() => onSelect(t)}
            style={{
              padding: "10px 22px",
              border: "none",
              background: "none",
              cursor: "pointer",
              fontWeight: isActive ? 700 : 500,
              color: isActive ? BLUE : "#6b7280",
              borderBottom: isActive ? `2px solid ${BLUE}` : "2px solid transparent",
              marginBottom: -2,
              fontSize: "0.93em",
              fontFamily: "inherit",
              transition: "color 0.15s",
            }}
          >
            {t}
          </button>
        );
      })}
    </div>
  );
}

// ── Valuation table (Table 1) ─────────────────────────────────────────────────

interface T1Row {
  label: string;
  value: string;
  bg?: string;
  fg?: string;
  kind: "data" | "edit" | "formula" | "special";
  bold?: boolean;
}

function ValuationTable({ rows }: { rows: T1Row[] }) {
  const thStyle: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "7px 12px", textAlign: "left", border: "1px solid #334",
  };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82em" }}>
      <thead>
        <tr>
          <th style={thStyle}>Metric</th>
          <th style={{ ...thStyle, textAlign: "right" }}>Value</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const bg = r.bg ?? (r.kind === "formula" ? C.G_BG : r.kind === "edit" ? C.Y_BG : C.D_BG);
          const fg = r.fg ?? (r.kind === "formula" ? C.G_FG : r.kind === "edit" ? C.Y_FG : C.D_FG);
          return (
            <tr key={i} style={{ background: bg }}>
              <td style={{ padding: "6px 12px", border: "1px solid #e5e7eb", color: fg, fontWeight: 600 }}>
                {r.label}
              </td>
              <td style={{
                padding: "6px 12px", border: "1px solid #e5e7eb", color: fg,
                fontWeight: r.bold ? 700 : 500, textAlign: "right", fontVariantNumeric: "tabular-nums",
              }}>
                {r.value}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── PE breakdown table (Table 2) ──────────────────────────────────────────────

interface T2Row { label: string; value: string; note: string; bg: string; fg: string; }

function PETable({ rows }: { rows: T2Row[] }) {
  const thStyle: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "7px 12px", textAlign: "left", border: "1px solid #334",
  };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82em" }}>
      <thead>
        <tr>
          <th style={thStyle}>Component</th>
          <th style={{ ...thStyle, textAlign: "right" }}>Value</th>
          <th style={thStyle}>Note</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ background: r.bg }}>
            <td style={{ padding: "6px 12px", border: "1px solid #e5e7eb", color: r.fg, fontWeight: 700 }}>{r.label}</td>
            <td style={{ padding: "6px 12px", border: "1px solid #e5e7eb", color: r.fg, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{r.value}</td>
            <td style={{ padding: "6px 12px", border: "1px solid #e5e7eb", color: "#6b7280", fontStyle: "italic", fontSize: "0.93em" }}>{r.note}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Slider input (yellow accent, matching editable color) ─────────────────────

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  disabled?: boolean;
  onChange: (v: number) => void;
}

function SliderInput({ label, value, min, max, step, unit = "", disabled = false, onChange }: SliderProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>
        {label}: <span style={{ color: C.Y_FG, fontWeight: 700 }}>{value}{unit}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ accentColor: "#f59e0b", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1, width: "100%" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68em", color: "#9ca3af" }}>
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

// ── Placeholder tab ───────────────────────────────────────────────────────────

function PlaceholderTab({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div style={{ padding: "56px 0", textAlign: "center", color: "#9ca3af" }}>
      <div style={{ fontSize: "2.8em", marginBottom: 14 }}>{icon}</div>
      <div style={{ fontSize: "1.1em", fontWeight: 700, color: "#6b7280", marginBottom: 8 }}>{title}</div>
      <div style={{ fontSize: "0.88em" }}>{body}</div>
    </div>
  );
}

// ── Sliders state ─────────────────────────────────────────────────────────────

interface Sliders {
  growthPct: number;
  years: number;
  discPct: number;
  mosPct: number;
  useWacc: boolean;
}

// ── Main component ────────────────────────────────────────────────────────────

export interface StockDashboardProps {
  ticker: string;
  onSearch: Dispatch<SetStateAction<string | null>>;
}

export default function StockDashboard({ ticker, onSearch }: StockDashboardProps) {
  const [data, setData]       = useState<NormalizedPEResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("Normalized PE");
  const [sliders, setSliders] = useState<Sliders>({ growthPct: 5, years: 7, discPct: 15, mosPct: 15, useWacc: false });
  const [searchQ, setSearchQ] = useState("");
  const debounce = useRef<ReturnType<typeof setTimeout>>();

  // ── Initial load (default params) ─────────────────────────────────────────
  useEffect(() => {
    setLoading(true);
    setError(null);
    setData(null);
    clearTimeout(debounce.current);

    fetch(`/api/normalized-pe/${ticker}`)
      .then((r) => {
        if (!r.ok) return r.json().then((b) => Promise.reject(b.detail ?? `HTTP ${r.status}`));
        return r.json();
      })
      .then((json: NormalizedPEResult) => {
        setData(json);
        setSliders({
          growthPct: json.growth_pct,
          years:     json.years,
          discPct:   json.disc_pct,
          mosPct:    json.mos_pct,
          useWacc:   json.use_wacc,
        });
      })
      .catch((e: unknown) => setError(typeof e === "string" ? e : "Failed to load data"))
      .finally(() => setLoading(false));
  }, [ticker]);

  // ── Debounced slider update ────────────────────────────────────────────────
  function applySliders(next: Sliders) {
    setSliders(next);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      const qs = new URLSearchParams({
        growth_pct: String(next.growthPct),
        years:      String(next.years),
        disc_pct:   String(next.discPct),
        mos_pct:    String(next.mosPct),
        use_wacc:   String(next.useWacc),
      });
      fetch(`/api/normalized-pe/${ticker}?${qs}`)
        .then((r) => r.json())
        .then(setData)
        .catch(console.error);
    }, 350);
  }

  // ── Handle top search ──────────────────────────────────────────────────────
  function handleSearch() {
    const t = searchQ.trim().toUpperCase();
    if (t) { onSearch(t); setSearchQ(""); }
  }

  // ── Derived display values ─────────────────────────────────────────────────
  const upFv  = fUpside(data?.upside_to_fv  ?? null);
  const upBuy = fUpside(data?.upside_to_buy ?? null);
  const onSale = data?.on_sale ?? null;
  const waccPct = data ? (data.wacc * 100).toFixed(2) : "--";

  const t1Rows: T1Row[] = data ? [
    { label: "EPS (TTM)",              value: f$(data.eps_ttm),                                      kind: "data"    },
    { label: "Est. Future Growth (%)", value: fPct(sliders.growthPct),                               kind: "edit"    },
    { label: "Number of Years",        value: String(sliders.years),                                  kind: "edit"    },
    { label: "Estimated Future EPS",   value: f$(data.future_eps),                                   kind: "formula" },
    { label: "Discount Rate",          value: fPct(data.disc_pct),                                   kind: "edit"    },
    { label: "Discounted EPS",         value: f$(data.discounted_eps),                               kind: "formula" },
    { label: "Estimated PE",           value: data.pe_c != null ? `${data.pe_c.toFixed(1)}\u00d7` : "N/A", kind: "formula" },
    { label: "Fair Value Per Share",   value: f$(data.fair_value),                                   kind: "formula", bold: true },
    { label: "Margin of Safety (%)",   value: fPct(sliders.mosPct, 0),                               kind: "edit"    },
    { label: "Buy Price",              value: f$(data.buy_price),                                    kind: "formula", bold: true },
    { label: "Current Stock Price",    value: f$(data.price_now),                                    kind: "data"    },
    {
      label: "Company on-sale?",
      value: onSale != null ? (onSale ? "ON SALE \u2705" : "NOT ON SALE \u274c") : "N/A",
      kind: "special",
      bg: onSale != null ? (onSale ? C.GN_BG : C.RD_BG) : C.D_BG,
      fg: onSale != null ? (onSale ? C.GN_FG : C.RD_FG) : C.D_FG,
      bold: true,
    },
    {
      label: "Upside to Fair Value",
      value: upFv.str,
      kind: "special",
      bg: upFv.pos === true ? C.POS_BG : upFv.pos === false ? C.NEG_BG : C.D_BG,
      fg: upFv.pos === true ? C.POS_FG : upFv.pos === false ? C.NEG_FG : C.D_FG,
    },
    {
      label: "Upside to Buy Price",
      value: upBuy.str,
      kind: "special",
      bg: upBuy.pos === true ? C.POS_BG : upBuy.pos === false ? C.NEG_BG : C.D_BG,
      fg: upBuy.pos === true ? C.POS_FG : upBuy.pos === false ? C.NEG_FG : C.D_FG,
    },
  ] : [];

  const t2Rows: T2Row[] = data ? [
    {
      label: "(a)  Default PE",
      value: `${data.pe_a.toFixed(1)}\u00d7`,
      note:  `Rule of thumb: 2 \u00d7 Growth Rate  (${sliders.growthPct.toFixed(1)}% \u00d7 2 = ${data.pe_a.toFixed(1)}\u00d7)`,
      bg: C.G_BG, fg: C.G_FG,
    },
    {
      label: "(b)  Historical PE",
      value: data.pe_b != null ? `${data.pe_b.toFixed(1)}\u00d7` : "N/A",
      note:  "10-year average P/E from Valuation Multiples",
      bg: C.D_BG, fg: C.D_FG,
    },
    {
      label: "(c)  Estimated PE",
      value: data.pe_c != null ? `${data.pe_c.toFixed(1)}\u00d7` : "N/A",
      note:  "Conservative PE: MIN(a, b)  \u2014  per Phil Town\u2019s Rule #1",
      bg: C.Y_BG, fg: C.Y_FG,
    },
  ] : [];

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{
      minHeight: "100vh",
      background: "#fff",
      fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
      color: "#1c2b46",
    }}>

      {/* ── Top bar ──────────────────────────────────────────────────────── */}
      <div style={{
        background: "#fff",
        borderBottom: "1px solid #e5e7eb",
        padding: "10px 24px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        position: "sticky",
        top: 0,
        zIndex: 10,
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}>
        <div style={{ flexShrink: 0 }}>
          <span style={{ color: BLUE,  fontWeight: 900, fontSize: "1.35em", letterSpacing: "-0.01em" }}>get</span>
          <span style={{ color: NAVY, fontWeight: 900, fontSize: "1.35em", letterSpacing: "-0.01em" }}>Value</span>
        </div>

        <div style={{ flex: 1, display: "flex", gap: 8, maxWidth: 520 }}>
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Search another company or ticker…"
            style={{
              flex: 1, padding: "8px 14px",
              border: "1.5px solid #d1d5db", borderRadius: 6,
              fontSize: "0.88em", outline: "none", background: "#f9fafb",
              fontFamily: "inherit",
            }}
          />
          <button
            onClick={handleSearch}
            style={{
              padding: "8px 18px", background: BLUE, color: "#fff",
              border: "none", borderRadius: 6, fontWeight: 700,
              fontSize: "0.88em", cursor: "pointer", fontFamily: "inherit",
            }}
          >
            Analyze →
          </button>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div style={{ maxWidth: 1020, margin: "0 auto", padding: "20px 20px 48px" }}>

        {/* ── Company header ─────────────────────────────────────────────── */}
        <div style={{
          display: "flex", alignItems: "center", gap: 14,
          padding: "14px 0 18px",
          borderBottom: `2px solid ${NAVY}`,
          marginBottom: 20,
        }}>
          <div>
            <div style={{ fontSize: "1.5em", fontWeight: 800, color: "#0d1b2a" }}>{ticker}</div>
            {data && (
              <div style={{ fontSize: "0.82em", color: "#4d6b88", marginTop: 3 }}>
                <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: "1.15em", color: "#0d1b2a" }}>
                  {f$(data.price_now)}
                </span>
                <span style={{ marginLeft: 12 }}>
                  Source: <strong>{data.data_source.replace("_fallback", "").toUpperCase()}</strong>
                  {data.data_source.includes("fallback") && (
                    <span style={{ marginLeft: 4, fontSize: "0.9em", color: "#f59e0b" }}>(fallback)</span>
                  )}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ── Tabs ───────────────────────────────────────────────────────── */}
        <TabBar active={activeTab} onSelect={setActiveTab} />

        {/* ══ Tab: Normalized PE ════════════════════════════════════════════ */}
        {activeTab === "Normalized PE" && (
          <div>
            {loading && <Spinner />}

            {error && (
              <div style={{
                background: "#fee2e2", border: "1px solid #fca5a5",
                borderRadius: 8, padding: "12px 16px", color: "#991b1b",
              }}>
                <strong>Error:</strong> {error}
              </div>
            )}

            {data && !loading && (
              <>
                <SecHeader title="Normalized PE  \u00b7  Phil Town Rule #1" />

                {/* Table 1 */}
                <SubHeader title="Table 1  \u00b7  Valuation Results" />
                <ValuationTable rows={t1Rows} />
                <Legend />

                {/* Table 2 */}
                <div style={{ marginTop: 18 }} />
                <SubHeader title="Table 2  \u00b7  Estimated PE  (Conservative P/E Calculation)" />
                <PETable rows={t2Rows} />

                {/* Model Inputs — Sliders */}
                <div style={{ marginTop: 22 }} />
                <SubHeader title="Model Inputs" />
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                  gap: 20,
                  background: "#fffbeb",
                  border: "1.5px solid #fde68a",
                  borderRadius: 8,
                  padding: "16px 20px",
                  marginTop: 6,
                }}>
                  <SliderInput
                    label="Est. Future Growth"
                    value={sliders.growthPct} min={0} max={50} step={0.5} unit="%"
                    onChange={(v) => applySliders({ ...sliders, growthPct: v })}
                  />
                  <SliderInput
                    label="Number of Years"
                    value={sliders.years} min={1} max={20} step={1}
                    onChange={(v) => applySliders({ ...sliders, years: v })}
                  />
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ fontSize: "0.78em", fontWeight: 600, color: NAVY }}>
                      Use WACC
                    </div>
                    <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={sliders.useWacc}
                        onChange={(e) => applySliders({ ...sliders, useWacc: e.target.checked })}
                        style={{ accentColor: BLUE, width: 16, height: 16 }}
                      />
                      <span style={{ fontSize: "0.85em", color: "#374151" }}>
                        WACC = {waccPct}%
                      </span>
                    </label>
                  </div>
                  <SliderInput
                    label="Discount Rate"
                    value={sliders.discPct} min={1} max={40} step={0.5} unit="%"
                    disabled={sliders.useWacc}
                    onChange={(v) => applySliders({ ...sliders, discPct: v })}
                  />
                  <SliderInput
                    label="Margin of Safety"
                    value={sliders.mosPct} min={0} max={80} step={5} unit="%"
                    onChange={(v) => applySliders({ ...sliders, mosPct: v })}
                  />
                </div>

                {/* EPS CAGR strip */}
                <div style={{ marginTop: 22 }} />
                <SubHeader title="EPS CAGR  \u00b7  Used for default growth rate" />
                <div style={{
                  display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
                  border: "1px solid #e5e7eb", borderRadius: 6, overflow: "hidden",
                }}>
                  {[
                    { label: "3-Year CAGR",  value: fCagr(data.eps_3yr)  },
                    { label: "5-Year CAGR",  value: fCagr(data.eps_5yr)  },
                    { label: "10-Year CAGR", value: fCagr(data.eps_10yr) },
                  ].map(({ label, value }, i) => (
                    <div key={label} style={{
                      background: C.D_BG, padding: 16, textAlign: "center",
                      borderRight: i < 2 ? "1px solid #e5e7eb" : "none",
                    }}>
                      <div style={{ fontSize: "0.68em", color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>
                        {label}
                      </div>
                      <div style={{ fontSize: "1.25em", fontWeight: 700, color: C.D_FG }}>
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* ══ Tab: Insights ═════════════════════════════════════════════════ */}
        {activeTab === "Insights" && (
          <PlaceholderTab
            icon="💡"
            title="Insights — Coming Soon"
            body="Growth (CAGR), profitability, returns, liquidity, dividends, efficiency and WACC analysis will appear here."
          />
        )}

        {/* ══ Tab: DCF / Valuations ════════════════════════════════════════ */}
        {activeTab === "DCF / Valuations" && (
          <PlaceholderTab
            icon="💰"
            title="DCF / Valuations — Coming Soon"
            body="Discounted cash flow model and IRR schedule will appear here."
          />
        )}

      </div>
    </div>
  );
}
