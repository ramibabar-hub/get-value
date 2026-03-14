# Financials & Insights Dual-View: By Tables / By Graphs — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "By Tables / By Graphs" toggle to the Financials and Insights tabs, rendering a professional 10-year chart dashboard alongside the existing table view.

**Architecture:** `recharts` (already installed at v3.8.0) powers all charts. A shared `ChartCard` wrapper provides the card UI, responsive container, and per-series customization popover. Series visibility is persisted via an extension to the existing Zustand `layoutStore`. Each tab gets its own "GraphsView" component (`FinancialsGraphsView`, `InsightsGraphsView`) that receives the same props already flowing into the tab components.

**Tech Stack:** React 19, TypeScript, recharts 3.8, Zustand 5, existing `layoutStore` (persisted as `gv_layout_v4`), inline styles (no Tailwind on new components), CSS Grid via injected `<style>` tag for responsive breakpoints.

---

## Codebase Context (read before implementing any task)

### Key file paths
```
frontend/src/
  types.ts                          ← all interfaces (FinancialsData, ExtRow, InsightsData, …)
  store/layoutStore.ts              ← Zustand store (key: "gv_layout_v4")
  components/
    FinancialsTab.tsx               ← receives: data, extData, scale, ticker, period, …
    InsightsTab.tsx                 ← receives: data (InsightsData), waccData, …
    StockDashboard.tsx              ← passes props to both tabs
```

### Data interfaces (from `types.ts`)
```ts
interface FinancialRow  { label: string; [col: string]: number | null | string; }
interface ExtRow        { label: string; fmt: FmtType; [col: string]: number | null | string; }
interface FinancialsData      { columns: string[]; income_statement: FinancialRow[]; balance_sheet: FinancialRow[]; cash_flow: FinancialRow[]; debt: FinancialRow[]; }
interface FinancialsExtendedData { columns: string[]; market_valuation: ExtRow[]; capital_structure: ExtRow[]; profitability: ExtRow[]; returns: ExtRow[]; liquidity: ExtRow[]; dividends: ExtRow[]; efficiency: ExtRow[]; }
interface InsightsGroup { title: string; cols: string[]; is_pct: boolean; rows: InsightsRow[]; }
interface InsightsData  { ticker: string; groups: InsightsGroup[]; }
```

### Column ordering convention for charts
`data.columns` arrives as `["TTM", "2024", "2023", "2022", ...]` (newest-first). For charts, display chronologically oldest-first then TTM last:
```ts
// chartCols: ["2016","2017",...,"2024","TTM"]
const chartCols = [...data.columns.filter(c => c !== "TTM").reverse(), "TTM"];
```

### Design constants (match existing codebase)
```ts
const NAVY   = "#1c2b46";
const BLUE   = "#007bff";
const GREEN  = "#10b981";
const RED    = "#ef4444";
const AMBER  = "#f59e0b";
const PURPLE = "#8b5cf6";
const CYAN   = "#06b6d4";
const PINK   = "#ec4899";
const CHART_COLORS = [BLUE, GREEN, AMBER, PURPLE, CYAN, RED, PINK, NAVY];
```

### Recharts import pattern
```ts
import {
  ResponsiveContainer, ComposedChart, BarChart, LineChart, AreaChart,
  Bar, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine,
} from "recharts";
```

---

## Task 1 — Chart Data Utilities (`chartDataUtils.ts`)

**Files:**
- Create: `frontend/src/utils/chartDataUtils.ts`

**What to build:** Pure helper functions used by every graph component. No React, no side-effects.

```ts
// frontend/src/utils/chartDataUtils.ts

import type { FinancialRow, ExtRow, FmtType, Scale } from "../types";

/**
 * Find a row by exact label. Returns null if not found.
 */
export function findRow(rows: FinancialRow[] | ExtRow[], label: string): FinancialRow | ExtRow | null {
  return rows.find(r => r.label === label) ?? null;
}

/**
 * Build a recharts-compatible data array from columns + multiple row labels.
 * Returns [{col: "2016", Revenue: 1234, "Net Income": 567, …}, …]
 * Missing/null values become null (recharts skips null points on lines).
 *
 * @param columns  - ordered column array (already sorted chronologically, e.g. ["2016","2017","TTM"])
 * @param rows     - array of FinancialRow or ExtRow
 * @param labels   - labels to extract (each becomes a key in the output object)
 * @param divisor  - divide raw values (for scale: K=1e3, MM=1e6, B=1e9)
 */
export function buildChartData(
  columns: string[],
  rows: (FinancialRow | ExtRow)[],
  labels: string[],
  divisor = 1,
): Record<string, string | number | null>[] {
  return columns.map(col => {
    const entry: Record<string, string | number | null> = { col };
    for (const label of labels) {
      const row = rows.find(r => r.label === label);
      const raw = row ? (row[col] as number | null | undefined) : undefined;
      entry[label] = (raw != null && isFinite(raw)) ? raw / divisor : null;
    }
    return entry;
  });
}

/**
 * Build chart data for percentage-format ExtRow (multiply by 100 for display).
 * Use for rows where fmt === "pct".
 */
export function buildPctChartData(
  columns: string[],
  rows: ExtRow[],
  labels: string[],
): Record<string, string | number | null>[] {
  return columns.map(col => {
    const entry: Record<string, string | number | null> = { col };
    for (const label of labels) {
      const row = rows.find(r => r.label === label);
      const raw = row ? (row[col] as number | null | undefined) : undefined;
      // pct rows store as decimal (0.35 = 35%), multiply by 100
      entry[label] = (raw != null && isFinite(raw)) ? +(raw * 100).toFixed(1) : null;
    }
    return entry;
  });
}

/**
 * Scale divisor from Scale type.
 */
export function scaleDivisor(scale: Scale): number {
  return scale === "K" ? 1e3 : scale === "MM" ? 1e6 : 1e9;
}

/**
 * Sorted chart columns: oldest non-TTM columns first, then TTM.
 * Input: ["TTM", "2024", "2023", ...] → ["2016","2017",...,"2024","TTM"]
 */
export function chartColumns(columns: string[]): string[] {
  return [...columns.filter(c => c !== "TTM").reverse(), "TTM"];
}

/**
 * Format a chart axis tick value as a compact number (e.g. 1200 → "1.2K", 1500000 → "1.5M").
 * Values are already divided by scale, so just format the number cleanly.
 */
export function fmtTick(value: number): string {
  if (value == null || !isFinite(value)) return "";
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(1);
}

/**
 * Format a percentage tick (value is already *100).
 */
export function fmtPctTick(value: number): string {
  return `${value.toFixed(1)}%`;
}

/**
 * Format a ratio tick (2 decimal places).
 */
export function fmtRatioTick(value: number): string {
  return value.toFixed(2);
}
```

**Step 1:** Create the file with the code above.

**Step 2:** Run TypeScript check:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors referencing `chartDataUtils.ts`.

**Step 3:** Commit:
```bash
git add frontend/src/utils/chartDataUtils.ts
git commit -m "feat: add chart data extraction utilities for graph dual-view"
```

---

## Task 2 — Extend Zustand Store for Graph Series Customization

**Files:**
- Modify: `frontend/src/store/layoutStore.ts`

**Context:** The existing store has `hiddenFinancialsSections: string[]` for table section visibility. We add parallel state for graph series visibility. Each chart has a string `chartId`; hidden series labels are stored in a `Record<chartId, string[]>`.

**What to add** to `LayoutState` interface and the `create(...)` call:

```ts
// Add to LayoutState interface:
hiddenGraphSeries: Record<string, string[]>;  // chartId → hidden series labels
toggleGraphSeries: (chartId: string, series: string) => void;
resetGraphSeries:  (chartId?: string) => void;
```

```ts
// Add to create(...) call body (alongside existing state):
hiddenGraphSeries: {},

toggleGraphSeries: (chartId, series) =>
  set((state) => {
    const current = state.hiddenGraphSeries[chartId] ?? [];
    const updated = current.includes(series)
      ? current.filter(s => s !== series)
      : [...current, series];
    return { hiddenGraphSeries: { ...state.hiddenGraphSeries, [chartId]: updated } };
  }),

resetGraphSeries: (chartId?) =>
  set((state) => {
    if (!chartId) return { hiddenGraphSeries: {} };
    const { [chartId]: _, ...rest } = state.hiddenGraphSeries;
    return { hiddenGraphSeries: rest };
  }),
```

Also add `hiddenGraphSeries: {}` to the `resetCustomization` action:
```ts
resetCustomization: () =>
  set({ hiddenFinancialsSections: [], hiddenInsightGroups: [], hiddenTableRows: {}, hiddenGraphSeries: {} }),
```

**Step 1:** Open `frontend/src/store/layoutStore.ts` and apply the three additions above.

**Step 2:** Run TypeScript check:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

**Step 3:** Commit:
```bash
git add frontend/src/store/layoutStore.ts
git commit -m "feat: add graph series customization state to layoutStore"
```

---

## Task 3 — ChartCard Wrapper Component

**Files:**
- Create: `frontend/src/components/ChartCard.tsx`

**What to build:** A reusable card that wraps any recharts chart. Provides:
- Title bar (navy background, white text)
- "Customize" popover to toggle series visibility
- Responsive container (100% width, fixed height)
- Empty/no-data state
- Children = the actual recharts JSX

```tsx
// frontend/src/components/ChartCard.tsx
import { useState } from "react";
import { ResponsiveContainer } from "recharts";
import { useLayoutStore } from "../store/layoutStore";

const NAVY = "#1c2b46";
const BLUE = "#007bff";

interface ChartCardProps {
  chartId:  string;        // unique ID used for series customization storage
  title:    string;        // displayed in the header
  series:   string[];      // all possible series labels (for customize popover)
  colors:   string[];      // parallel to series: color for each series
  height?:  number;        // chart height in px (default 220)
  children: (hiddenSeries: Set<string>) => React.ReactNode;  // render prop
}

export default function ChartCard({ chartId, title, series, colors, height = 220, children }: ChartCardProps) {
  const [showCustomize, setShowCustomize] = useState(false);
  const { hiddenGraphSeries, toggleGraphSeries } = useLayoutStore();
  const hiddenArr = hiddenGraphSeries[chartId] ?? [];
  const hiddenSet = new Set(hiddenArr);

  return (
    <div style={{ background: "#fff", borderRadius: 6, border: "1px solid #e5e7eb", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
      {/* Header */}
      <div style={{ background: NAVY, padding: "7px 12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ color: "#fff", fontWeight: 700, fontSize: "0.82em", letterSpacing: "0.02em" }}>{title}</span>
        <div style={{ position: "relative" }}>
          <button
            onClick={() => setShowCustomize(v => !v)}
            style={{ background: "none", border: "1px solid rgba(255,255,255,0.3)", borderRadius: 4, color: "rgba(255,255,255,0.8)", fontSize: "0.7em", padding: "2px 8px", cursor: "pointer", fontFamily: "inherit" }}
          >
            ⚙ Series
          </button>
          {showCustomize && (
            <>
              {/* backdrop */}
              <div onClick={() => setShowCustomize(false)} style={{ position: "fixed", inset: 0, zIndex: 50 }} />
              {/* popover */}
              <div style={{ position: "absolute", right: 0, top: "calc(100% + 4px)", background: "#fff", border: "1px solid #e5e7eb", borderRadius: 6, padding: "10px 14px", minWidth: 180, zIndex: 51, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}>
                <div style={{ fontSize: "0.72em", fontWeight: 700, color: NAVY, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Toggle Series</div>
                {series.map((s, i) => {
                  const hidden = hiddenSet.has(s);
                  return (
                    <div
                      key={s}
                      onClick={() => toggleGraphSeries(chartId, s)}
                      style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 2px", cursor: "pointer", borderRadius: 3 }}
                    >
                      <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: hidden ? "#d1d5db" : (colors[i] ?? BLUE), flexShrink: 0 }} />
                      <span style={{ fontSize: "0.78em", color: hidden ? "#9ca3af" : NAVY, textDecoration: hidden ? "line-through" : "none" }}>{s}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
      {/* Chart body */}
      <div style={{ padding: "8px 4px 4px" }}>
        <ResponsiveContainer width="100%" height={height}>
          {/* children is a render prop receiving the hiddenSet */}
          {children(hiddenSet) as React.ReactElement}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

**Step 1:** Create the file with the code above.

**Step 2:** Run TypeScript check:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

**Step 3:** Commit:
```bash
git add frontend/src/components/ChartCard.tsx
git commit -m "feat: add ChartCard wrapper with series customization popover"
```

---

## Task 4 — FinancialsGraphsView: Row 0 — Core Financial Statements

**Files:**
- Create: `frontend/src/components/FinancialsGraphsView.tsx` (initial version, Row 0 only)

**Context:** This component receives the same props as FinancialsTab and renders all financial charts. Build it incrementally — this task adds Row 0 (4 charts). Later tasks add Rows 1-3.

**Props interface:**
```ts
import type { FinancialsData, FinancialsExtendedData, Scale } from "../types";

interface Props {
  data:      FinancialsData | null;
  extData:   FinancialsExtendedData | null;
  scale:     Scale;
  ticker:    string;
}
```

**Row 0 charts (4 cards in a 2×2 or 4×1 grid depending on screen):**

### Chart 0-A: Income Statement Highlights (Stacked Bar)
- **chartId:** `"fin-income-stmt"`
- **Series:** `["Revenues", "Gross profit", "Operating income", "Net Income"]`
- **Colors:** `[BLUE, GREEN, AMBER, PURPLE]`
- **Source:** `data.income_statement`
- **Recharts:** `ComposedChart` with stacked `Bar` components. Revenue is the total; use `stackId="a"` for all bars. Show Revenue as a light-opacity bar, overlay the sub-components.

```tsx
// Stacked bars — Revenue is full bar, others are segments
// Because recharts stacks additively, we show: GP, OI overlay NI
// Simplification: show 4 separate grouped bars (easier to read, avoids negative-value stacking issues)
// Use ComposedChart with 4 Bars, no stackId (grouped)
```

### Chart 0-B: Cash Flow Bridge (ComposedChart)
- **chartId:** `"fin-cashflow-bridge"`
- **Series:** `["Operating Cash Flow", "Free Cash Flow", "Adj. FCF"]`
- **Colors:** `[BLUE, GREEN, AMBER]`
- **Source:** `data.cash_flow`
- **Recharts:** `ComposedChart` — `Bar` for OCF, `Line` for FCF (solid), `Line` for Adj. FCF (dashed: `strokeDasharray="5 5"`)

### Chart 0-C: Balance Sheet Snapshot (Area Chart)
- **chartId:** `"fin-balance-sheet"`
- **Series:** `["Total assets", "Total liabilities", "Total Equity"]`
- **Colors:** `[BLUE, RED, GREEN]`
- **Source:** `data.balance_sheet`
- **Recharts:** `AreaChart` with `fillOpacity={0.15}` for Assets and Liabilities. The visual gap between Assets and Liabilities area represents Equity.

### Chart 0-D: Liquidity & Debt (Grouped Bar)
- **chartId:** `"fin-debt-cash"`
- **Series:** `["Total Debt", "Cash & Short-Term Investments"]`
- **Colors:** `[RED, GREEN]`
- **Source:** `data.balance_sheet`
- **Recharts:** `BarChart` with 2 `Bar` components (grouped — no stackId)

**Full Row 0 implementation:**

```tsx
// frontend/src/components/FinancialsGraphsView.tsx
import {
  ComposedChart, BarChart, AreaChart, LineChart,
  Bar, Line, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import ChartCard from "./ChartCard";
import { buildChartData, buildPctChartData, chartColumns, scaleDivisor, fmtTick, fmtPctTick, fmtRatioTick } from "../utils/chartDataUtils";
import type { FinancialsData, FinancialsExtendedData, Scale } from "../types";

const NAVY   = "#1c2b46";
const BLUE   = "#007bff";
const GREEN  = "#10b981";
const RED    = "#ef4444";
const AMBER  = "#f59e0b";
const PURPLE = "#8b5cf6";
const CYAN   = "#06b6d4";
const PINK   = "#ec4899";

const TT_STYLE = { background: "#1c2b46", border: "none", borderRadius: 6, color: "#fff", fontSize: "0.75em" };

interface Props {
  data:    FinancialsData | null;
  extData: FinancialsExtendedData | null;
  scale:   Scale;
  ticker:  string;
}

// Responsive CSS Grid: 4 col → 2 col → 1 col
const GRID_CSS = `
.gv-chart-grid { display:grid; gap:16px; grid-template-columns: repeat(4,1fr); }
@media(max-width:1400px){ .gv-chart-grid { grid-template-columns: repeat(2,1fr); } }
@media(max-width:700px){  .gv-chart-grid { grid-template-columns: 1fr; } }
.gv-chart-grid-3 { display:grid; gap:16px; grid-template-columns: repeat(3,1fr); }
@media(max-width:1100px){ .gv-chart-grid-3 { grid-template-columns: repeat(2,1fr); } }
@media(max-width:600px){  .gv-chart-grid-3 { grid-template-columns: 1fr; } }
.gv-chart-grid-2 { display:grid; gap:16px; grid-template-columns: repeat(2,1fr); }
@media(max-width:700px){ .gv-chart-grid-2 { grid-template-columns: 1fr; } }
`;

function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "0.88em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginBottom: 12, marginTop: 4 }}>
      {title}
    </div>
  );
}

export default function FinancialsGraphsView({ data, extData, scale }: Props) {
  if (!data) return null;
  const div  = scaleDivisor(scale);
  const cols = chartColumns(data.columns);

  // ── Row 0: Core Financial Statements ────────────────────────────────────────

  // 0-A Income Statement
  const IS_SERIES   = ["Revenues", "Gross profit", "Operating income", "Net Income"];
  const IS_COLORS   = [BLUE, GREEN, AMBER, PURPLE];
  const isData      = buildChartData(cols, data.income_statement, IS_SERIES, div);

  // 0-B Cash Flow Bridge
  const CF_SERIES   = ["Operating Cash Flow", "Free Cash Flow", "Adj. FCF"];
  const CF_COLORS   = [BLUE, GREEN, AMBER];
  const cfData      = buildChartData(cols, data.cash_flow, CF_SERIES, div);

  // 0-C Balance Sheet Snapshot
  const BS_SERIES   = ["Total assets", "Total liabilities", "Total Equity"];
  const BS_COLORS   = [BLUE, RED, GREEN];
  const bsData      = buildChartData(cols, data.balance_sheet, BS_SERIES, div);

  // 0-D Debt vs Cash
  const DC_SERIES   = ["Total Debt", "Cash & Short-Term Investments"];
  const DC_COLORS   = [RED, GREEN];
  const dcData      = buildChartData(cols, data.balance_sheet, DC_SERIES, div);

  const scaleLabel = `(${scale})`;

  return (
    <div>
      <style>{GRID_CSS}</style>

      {/* ── Row 0: Core Financial Statements ── */}
      <SectionHeader title="Core Financial Statements" />
      <div className="gv-chart-grid" style={{ marginBottom: 24 }}>

        {/* 0-A: Income Statement */}
        <ChartCard chartId="fin-income-stmt" title={`Income Statement ${scaleLabel}`} series={IS_SERIES} colors={IS_COLORS}>
          {(hidden) => (
            <ComposedChart data={isData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
              <YAxis tickFormatter={fmtTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={48} />
              <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [fmtTick(v), ""]} />
              <Legend wrapperStyle={{ fontSize: "0.72em" }} />
              {IS_SERIES.map((s, i) => hidden.has(s) ? null : (
                <Bar key={s} dataKey={s} fill={IS_COLORS[i]} opacity={i === 0 ? 0.45 : 0.85} radius={[2,2,0,0]} />
              ))}
            </ComposedChart>
          )}
        </ChartCard>

        {/* 0-B: Cash Flow Bridge */}
        <ChartCard chartId="fin-cashflow-bridge" title={`Cash Flow Bridge ${scaleLabel}`} series={CF_SERIES} colors={CF_COLORS}>
          {(hidden) => (
            <ComposedChart data={cfData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
              <YAxis tickFormatter={fmtTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={48} />
              <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [fmtTick(v), ""]} />
              <Legend wrapperStyle={{ fontSize: "0.72em" }} />
              {!hidden.has("Operating Cash Flow") && <Bar dataKey="Operating Cash Flow" fill={BLUE} opacity={0.7} radius={[2,2,0,0]} />}
              {!hidden.has("Free Cash Flow")       && <Line dataKey="Free Cash Flow" stroke={GREEN} strokeWidth={2} dot={{ r: 2 }} />}
              {!hidden.has("Adj. FCF")             && <Line dataKey="Adj. FCF" stroke={AMBER} strokeWidth={2} strokeDasharray="5 5" dot={{ r: 2 }} />}
            </ComposedChart>
          )}
        </ChartCard>

        {/* 0-C: Balance Sheet Snapshot */}
        <ChartCard chartId="fin-balance-sheet" title={`Balance Sheet ${scaleLabel}`} series={BS_SERIES} colors={BS_COLORS}>
          {(hidden) => (
            <AreaChart data={bsData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
              <YAxis tickFormatter={fmtTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={48} />
              <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [fmtTick(v), ""]} />
              <Legend wrapperStyle={{ fontSize: "0.72em" }} />
              {!hidden.has("Total assets")      && <Area dataKey="Total assets"      stroke={BLUE}  fill={BLUE}  fillOpacity={0.15} strokeWidth={2} />}
              {!hidden.has("Total liabilities") && <Area dataKey="Total liabilities" stroke={RED}   fill={RED}   fillOpacity={0.15} strokeWidth={2} />}
              {!hidden.has("Total Equity")      && <Area dataKey="Total Equity"      stroke={GREEN} fill={GREEN} fillOpacity={0.1}  strokeWidth={2} strokeDasharray="4 4" />}
            </AreaChart>
          )}
        </ChartCard>

        {/* 0-D: Debt vs Cash */}
        <ChartCard chartId="fin-debt-cash" title={`Debt vs. Cash ${scaleLabel}`} series={DC_SERIES} colors={DC_COLORS}>
          {(hidden) => (
            <BarChart data={dcData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
              <YAxis tickFormatter={fmtTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={48} />
              <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [fmtTick(v), ""]} />
              <Legend wrapperStyle={{ fontSize: "0.72em" }} />
              {!hidden.has("Total Debt")                    && <Bar dataKey="Total Debt"                    fill={RED}   radius={[2,2,0,0]} />}
              {!hidden.has("Cash & Short-Term Investments") && <Bar dataKey="Cash & Short-Term Investments" fill={GREEN} radius={[2,2,0,0]} />}
            </BarChart>
          )}
        </ChartCard>

      </div>

    </div>
  );
}
```

**Step 1:** Create the file with the complete code above (Row 0 section only — Rows 1-3 added in subsequent tasks).

**Step 2:** Run TypeScript check:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

**Step 3:** Commit:
```bash
git add frontend/src/components/FinancialsGraphsView.tsx
git commit -m "feat: FinancialsGraphsView Row 0 — Core Financial Statements (4 charts)"
```

---

## Task 5 — FinancialsGraphsView: Rows 1–3 (Remaining Charts)

**Files:**
- Modify: `frontend/src/components/FinancialsGraphsView.tsx`

**Add the following three sections** after Row 0 inside the `return (...)` block.

### Row 1: Valuation & Shareholder Yield (from `extData.market_valuation`, `extData.capital_structure`, `extData.returns`)

```tsx
// ── Row 1: Valuation & Shareholder Yield ──────────────────────────────────

// 1-A: Valuation Multiples (ratio rows from market_valuation — no divisor)
const VM_SERIES = ["P/E", "P/S", "P/B", "P/Adj. FCF"];
const VM_COLORS = [BLUE, GREEN, AMBER, PURPLE];
const vmCols    = extData ? chartColumns(extData.columns) : [];
const vmData    = extData ? buildChartData(vmCols, extData.market_valuation, VM_SERIES) : [];

// 1-B: Debt Coverage (capital_structure)
const DC2_SERIES = ["Net Debt / EBITDA", "Interest Coverage"];
const DC2_COLORS = [RED, GREEN];
const dc2Data    = extData ? buildChartData(vmCols, extData.capital_structure, DC2_SERIES) : [];

// 1-C: Profitability Margins (profitability — pct rows)
const MARGIN_SERIES = ["Gross Margin", "EBITDA Margin", "Operating Margin", "Net Margin"];
const MARGIN_COLORS = [BLUE, GREEN, AMBER, PURPLE];
const marginData    = extData ? buildPctChartData(vmCols, extData.profitability, MARGIN_SERIES) : [];

// 1-D: Returns on Capital (returns — pct rows)
const RET_SERIES = ["ROIC", "ROE", "ROA"];
const RET_COLORS = [BLUE, GREEN, AMBER];
const retData    = extData ? buildPctChartData(vmCols, extData.returns, RET_SERIES) : [];
```

```tsx
{/* ── Row 1: Valuation & Returns ── */}
<SectionHeader title="Valuation Multiples & Returns" />
<div className="gv-chart-grid" style={{ marginBottom: 24 }}>

  {/* 1-A: Valuation Multiples */}
  <ChartCard chartId="fin-valuation" title="Valuation Multiples (×)" series={VM_SERIES} colors={VM_COLORS}>
    {(hidden) => (
      <BarChart data={vmData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tickFormatter={fmtRatioTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={40} />
        <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [v?.toFixed(1) + "×", ""]} />
        <Legend wrapperStyle={{ fontSize: "0.72em" }} />
        {VM_SERIES.map((s, i) => hidden.has(s) ? null : (
          <Bar key={s} dataKey={s} fill={VM_COLORS[i]} radius={[2,2,0,0]} />
        ))}
      </BarChart>
    )}
  </ChartCard>

  {/* 1-B: Debt Coverage */}
  <ChartCard chartId="fin-debt-coverage" title="Debt Coverage (×)" series={DC2_SERIES} colors={DC2_COLORS}>
    {(hidden) => (
      <ComposedChart data={dc2Data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tickFormatter={fmtRatioTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={40} />
        <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [v?.toFixed(2) + "×", ""]} />
        <Legend wrapperStyle={{ fontSize: "0.72em" }} />
        {!hidden.has("Net Debt / EBITDA") && <Bar  dataKey="Net Debt / EBITDA" fill={RED}   radius={[2,2,0,0]} />}
        {!hidden.has("Interest Coverage") && <Line dataKey="Interest Coverage" stroke={GREEN} strokeWidth={2} dot={{ r: 2 }} />}
      </ComposedChart>
    )}
  </ChartCard>

  {/* 1-C: Profitability Margins */}
  <ChartCard chartId="fin-margins" title="Profitability Margins (%)" series={MARGIN_SERIES} colors={MARGIN_COLORS}>
    {(hidden) => (
      <LineChart data={marginData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tickFormatter={fmtPctTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={44} />
        <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [v?.toFixed(1) + "%", ""]} />
        <Legend wrapperStyle={{ fontSize: "0.72em" }} />
        {MARGIN_SERIES.map((s, i) => hidden.has(s) ? null : (
          <Line key={s} dataKey={s} stroke={MARGIN_COLORS[i]} strokeWidth={2} dot={{ r: 2 }} />
        ))}
      </LineChart>
    )}
  </ChartCard>

  {/* 1-D: Returns on Capital */}
  <ChartCard chartId="fin-returns" title="Returns on Capital (%)" series={RET_SERIES} colors={RET_COLORS}>
    {(hidden) => (
      <LineChart data={retData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tickFormatter={fmtPctTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={44} />
        <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [v?.toFixed(1) + "%", ""]} />
        <Legend wrapperStyle={{ fontSize: "0.72em" }} />
        {RET_SERIES.map((s, i) => hidden.has(s) ? null : (
          <Line key={s} dataKey={s} stroke={RET_COLORS[i]} strokeWidth={2} dot={{ r: 2 }} />
        ))}
      </LineChart>
    )}
  </ChartCard>

</div>
```

### Row 2: Capital Structure (3 charts — use `gv-chart-grid-3`)

```tsx
// Row 2 data
// 2-A: Capital Structure ratios
const CAP_SERIES = ["Debt/Equity", "Net Debt / EBITDA", "Debt / Adj. FCF"];
const CAP_COLORS = [RED, AMBER, PINK];
const capData    = extData ? buildChartData(vmCols, extData.capital_structure, CAP_SERIES) : [];

// 2-B: Liquidity ratios
const LIQ_SERIES = ["Current Ratio", "Quick Ratio", "Cash Ratio"];
const LIQ_COLORS = [BLUE, GREEN, AMBER];
const liqData    = extData ? buildChartData(vmCols, extData.liquidity, LIQ_SERIES) : [];

// 2-C: Operating Cycle (days)
const EFF_SERIES = ["Average receivables collection day", "Average days inventory in stock", "Average days payables outstanding"];
const EFF_LABELS = ["Receivables Days", "Inventory Days", "Payables Days"];  // short names for legend
const EFF_COLORS = [BLUE, AMBER, GREEN];
const effCols    = extData ? chartColumns(extData.columns) : [];
// Build with original labels, then rename for display
const effData    = extData ? buildChartData(effCols, extData.efficiency, EFF_SERIES).map(d => {
  const out: Record<string, string | number | null> = { col: d.col };
  EFF_SERIES.forEach((s, i) => { out[EFF_LABELS[i]] = d[s]; });
  return out;
}) : [];
```

```tsx
{/* ── Row 2: Capital Structure & Efficiency ── */}
<SectionHeader title="Capital Structure & Operating Efficiency" />
<div className="gv-chart-grid-3" style={{ marginBottom: 24 }}>

  {/* 2-A: Capital Structure */}
  <ChartCard chartId="fin-capital-struct" title="Capital Structure (×)" series={CAP_SERIES} colors={CAP_COLORS}>
    {(hidden) => (
      <LineChart data={capData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tickFormatter={fmtRatioTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={40} />
        <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [v?.toFixed(2) + "×", ""]} />
        <Legend wrapperStyle={{ fontSize: "0.72em" }} />
        {CAP_SERIES.map((s, i) => hidden.has(s) ? null : (
          <Line key={s} dataKey={s} stroke={CAP_COLORS[i]} strokeWidth={2} dot={{ r: 2 }} />
        ))}
      </LineChart>
    )}
  </ChartCard>

  {/* 2-B: Liquidity Ratios */}
  <ChartCard chartId="fin-liquidity" title="Liquidity Ratios (×)" series={LIQ_SERIES} colors={LIQ_COLORS}>
    {(hidden) => (
      <LineChart data={liqData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tickFormatter={fmtRatioTick} tick={{ fontSize: 10, fill: "#6b7280" }} width={40} />
        <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [v?.toFixed(2) + "×", ""]} />
        <Legend wrapperStyle={{ fontSize: "0.72em" }} />
        {LIQ_SERIES.map((s, i) => hidden.has(s) ? null : (
          <Line key={s} dataKey={s} stroke={LIQ_COLORS[i]} strokeWidth={2} dot={{ r: 2 }} />
        ))}
      </LineChart>
    )}
  </ChartCard>

  {/* 2-C: Operating Cycle (days) */}
  <ChartCard chartId="fin-eff-days" title="Operating Cycle (Days)" series={EFF_LABELS} colors={EFF_COLORS}>
    {(hidden) => (
      <BarChart data={effData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="col" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} width={36} />
        <Tooltip contentStyle={TT_STYLE} formatter={(v: number) => [v?.toFixed(0) + "d", ""]} />
        <Legend wrapperStyle={{ fontSize: "0.72em" }} />
        {EFF_LABELS.map((s, i) => hidden.has(s) ? null : (
          <Bar key={s} dataKey={s} stackId="eff" fill={EFF_COLORS[i]} radius={i === EFF_LABELS.length - 1 ? [2,2,0,0] : undefined} />
        ))}
      </BarChart>
    )}
  </ChartCard>

</div>
```

**Step 1:** Add the Row 1 and Row 2 data derivations (const declarations) after the Row 0 declarations inside the component function body.

**Step 2:** Add the `{/* Row 1 */}` and `{/* Row 2 */}` JSX blocks inside the `return (...)` after the existing Row 0 block.

**Step 3:** Run TypeScript check:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

**Step 4:** Commit:
```bash
git add frontend/src/components/FinancialsGraphsView.tsx
git commit -m "feat: FinancialsGraphsView Rows 1–2 — Valuation, Returns, Capital Structure, Efficiency"
```

---

## Task 6 — InsightsGraphsView Component

**Files:**
- Create: `frontend/src/components/InsightsGraphsView.tsx`

**Context:** `InsightsData.groups` is an array of `InsightsGroup`. Each group has `title`, `cols`, `is_pct`, and `rows`. The columns for CAGR groups are things like `["3yr","5yr","10yr"]`; for valuation groups: `["TTM","Avg. 5yr","Avg. 10yr"]`.

**Architecture:** Build a generic `InsightsGroupChart` component that maps any group to the appropriate chart type based on group title. Then assemble all groups into a grid.

**Chart type mapping:**
| Group title contains | Chart type | Notes |
|---|---|---|
| "Growth (CAGR)" | Grouped Bar | cols = ["3yr","5yr","10yr"], each row is a metric |
| "Valuation" | ComposedChart: Bar for TTM + ReferenceLine for avgs | TTM vs historical |
| "Profitability" | LineChart | Margin trends: TTM vs 5yr vs 10yr avg |
| "Returns" | LineChart | ROE/ROA/ROIC: TTM vs historical |
| "Liquidity" | BarChart grouped | Current TTM vs historical averages |
| "Dividends" | ComposedChart | Bar + Lines |
| "Efficiency" | BarChart grouped | Days-based metrics |

**Full implementation:**

```tsx
// frontend/src/components/InsightsGraphsView.tsx
import {
  ComposedChart, BarChart, LineChart,
  Bar, Line, ReferenceLine,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import ChartCard from "./ChartCard";
import { fmtTick, fmtPctTick, fmtRatioTick } from "../utils/chartDataUtils";
import type { InsightsData, InsightsGroup, InsightsRow } from "../types";

const NAVY   = "#1c2b46";
const BLUE   = "#007bff";
const GREEN  = "#10b981";
const RED    = "#ef4444";
const AMBER  = "#f59e0b";
const PURPLE = "#8b5cf6";
const CYAN   = "#06b6d4";
const PINK   = "#ec4899";
const CHART_COLORS = [BLUE, GREEN, AMBER, PURPLE, CYAN, RED, PINK];

const TT_STYLE = { background: "#1c2b46", border: "none", borderRadius: 6, color: "#fff", fontSize: "0.75em" };

const GRID_CSS = `
.gv-ins-grid { display:grid; gap:16px; grid-template-columns: repeat(3,1fr); }
@media(max-width:1100px){ .gv-ins-grid { grid-template-columns: repeat(2,1fr); } }
@media(max-width:600px){  .gv-ins-grid { grid-template-columns: 1fr; } }
`;

interface Props {
  data: InsightsData | null;
}

/**
 * Build recharts data from a group where each row becomes a bar group.
 * For CAGR groups: rows = metrics, cols = time periods.
 * Output: [{col: "3yr", Revenue: 12.5, EBITDA: 9.3, ...}, ...]
 */
function buildGroupData(group: InsightsGroup): Record<string, string | number | null>[] {
  return group.cols.map(col => {
    const entry: Record<string, string | number | null> = { col };
    for (const row of group.rows) {
      const raw = row[col] as number | null | undefined;
      const val = (raw != null && isFinite(raw))
        ? group.is_pct ? +(raw * 100).toFixed(2) : +raw.toFixed(2)
        : null;
      entry[row.label] = val;
    }
    return entry;
  });
}

/**
 * For valuation/comparison groups: rows = metrics, cols = [TTM, Avg.5yr, Avg.10yr].
 * Output: [{col: metric_label, TTM: v, "Avg. 5yr": v, "Avg. 10yr": v}, ...]
 * (transposed — rows become X-axis, cols become series)
 */
function buildTransposedData(group: InsightsGroup): Record<string, string | number | null>[] {
  return group.rows.map(row => {
    const entry: Record<string, string | number | null> = { col: row.label };
    for (const col of group.cols) {
      const raw = row[col] as number | null | undefined;
      entry[col] = (raw != null && isFinite(raw))
        ? group.is_pct ? +(raw * 100).toFixed(2) : +raw.toFixed(2)
        : null;
    }
    return entry;
  });
}

function InsightsGroupChart({ group, chartId }: { group: InsightsGroup; chartId: string }) {
  const labels = group.rows.map(r => r.label);
  const colors = labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);
  const fmt    = group.is_pct ? fmtPctTick : fmtRatioTick;
  const suffix = group.is_pct ? "%" : "×";
  const ttFmt  = (v: number) => [v != null ? v.toFixed(2) + suffix : "—", ""];

  // CAGR groups: rows are metrics, cols are periods (3yr, 5yr, 10yr)
  // Valuation/other: use transposed layout for readability
  const isCAGR       = group.title.toLowerCase().includes("cagr") || group.title.toLowerCase().includes("growth");
  const isValuation  = group.title.toLowerCase().includes("valuation");

  const data = isCAGR ? buildGroupData(group) : buildTransposedData(group);
  const series = isCAGR ? labels : group.cols;
  const seriesColors = isCAGR ? colors : group.cols.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);

  return (
    <ChartCard chartId={chartId} title={group.title} series={series} colors={seriesColors} height={210}>
      {(hidden) => (
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="col" tick={{ fontSize: 9, fill: "#6b7280" }} interval={0} />
          <YAxis tickFormatter={fmt} tick={{ fontSize: 10, fill: "#6b7280" }} width={44} />
          <Tooltip contentStyle={TT_STYLE} formatter={ttFmt} />
          <Legend wrapperStyle={{ fontSize: "0.7em" }} />
          {series.map((s, i) => hidden.has(s) ? null : (
            <Bar key={s} dataKey={s} fill={seriesColors[i]} radius={[2,2,0,0]} />
          ))}
        </BarChart>
      )}
    </ChartCard>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{ fontSize: "0.88em", fontWeight: 700, color: NAVY, borderLeft: `3px solid ${NAVY}`, paddingLeft: 8, marginBottom: 12, marginTop: 4 }}>
      {title}
    </div>
  );
}

export default function InsightsGraphsView({ data }: Props) {
  if (!data || !data.groups.length) return null;

  const growthGroups      = data.groups.filter(g => g.title.toLowerCase().includes("growth") || g.title.toLowerCase().includes("cagr"));
  const valuationGroups   = data.groups.filter(g => g.title.toLowerCase().includes("valuation"));
  const profitGroups      = data.groups.filter(g => g.title.toLowerCase().includes("profitability"));
  const returnsGroups     = data.groups.filter(g => g.title.toLowerCase().includes("returns"));
  const row1Groups        = [...growthGroups, ...valuationGroups, ...profitGroups];
  const row2Groups        = [...returnsGroups, ...data.groups.filter(g =>
    !g.title.toLowerCase().includes("growth") &&
    !g.title.toLowerCase().includes("cagr") &&
    !g.title.toLowerCase().includes("valuation") &&
    !g.title.toLowerCase().includes("profitability") &&
    !g.title.toLowerCase().includes("returns")
  )];

  return (
    <div>
      <style>{GRID_CSS}</style>

      {row1Groups.length > 0 && (
        <>
          <SectionHeader title="Growth, Valuation & Profitability" />
          <div className="gv-ins-grid" style={{ marginBottom: 24 }}>
            {row1Groups.map((g, i) => (
              <InsightsGroupChart key={g.title} group={g} chartId={`ins-${g.title.replace(/\W/g,"-").toLowerCase()}-${i}`} />
            ))}
          </div>
        </>
      )}

      {row2Groups.length > 0 && (
        <>
          <SectionHeader title="Returns, Liquidity & Efficiency" />
          <div className="gv-ins-grid" style={{ marginBottom: 24 }}>
            {row2Groups.map((g, i) => (
              <InsightsGroupChart key={g.title} group={g} chartId={`ins-${g.title.replace(/\W/g,"-").toLowerCase()}-r2-${i}`} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

**Step 1:** Create the file with the code above.

**Step 2:** Run TypeScript check:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

**Step 3:** Commit:
```bash
git add frontend/src/components/InsightsGraphsView.tsx
git commit -m "feat: InsightsGraphsView — generic group chart renderer for all 7 insight groups"
```

---

## Task 7 — Wire Toggle into FinancialsTab

**Files:**
- Modify: `frontend/src/components/FinancialsTab.tsx`

**What to add:**

1. **Import** `FinancialsGraphsView` and `useState` (already imported).

2. **Add state** inside `FinancialsTab` export function:
```ts
const [graphView, setGraphView] = useState(false);
```

3. **Add "By Tables / By Graphs" toggle button** into the existing controls bar (the flex div with Period, Scale, Decimals, Δ%, Dates controls). Add it at the start of the controls bar:

```tsx
{/* View toggle */}
<div style={{ display: "flex", alignItems: "center", gap: 4 }}>
  {(["By Tables", "By Graphs"] as const).map(v => {
    const active = (v === "By Graphs") === graphView;
    return (
      <button
        key={v}
        onClick={() => setGraphView(v === "By Graphs")}
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
        }}
      >
        {v}
      </button>
    );
  })}
</div>
```

4. **Conditional render** — after the `</div>` closing the controls bar, wrap the existing table content in `{!graphView && (...)}` and add the graphs view below:

```tsx
{/* ── Tables View ── */}
{!graphView && (
  <>
    {loading ? <Spinner label="Loading financials…" /> : null}
    {data && !loading ? ( ... existing FinTable blocks ... ) : null}
    {extLoading && !loading ? <Spinner label="Loading metric tables…" /> : null}
    {extData && !extLoading ? ( ... existing ExtTable blocks ... ) : null}
    {showCatalog ? <MetricsCatalogModal tab="financials" onClose={() => setShowCatalog(false)} /> : null}
  </>
)}

{/* ── Graphs View ── */}
{graphView && (data || extData) && (
  <FinancialsGraphsView
    data={data}
    extData={extData}
    scale={scale}
    ticker={ticker}
  />
)}
{graphView && !data && !loading && (
  <div style={{ padding: "40px 0", textAlign: "center", color: "var(--gv-text-muted)", fontSize: "0.88em" }}>
    Search for a ticker to view charts.
  </div>
)}
```

5. **Import** at top of file:
```ts
import FinancialsGraphsView from "./FinancialsGraphsView";
```

**Step 1:** Add the import for `FinancialsGraphsView`.

**Step 2:** Add `graphView` state inside `FinancialsTab`.

**Step 3:** Add the "By Tables / By Graphs" toggle buttons to the controls bar.

**Step 4:** Wrap existing table rendering in `{!graphView && (...)}`.

**Step 5:** Add the `{graphView && ...}` block for the graphs view.

**Step 6:** Run TypeScript check:
```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

**Step 7:** Run full build:
```
cd frontend && npm run build 2>&1 | tail -10
```
Expected: `✓ built in X.XXs`

**Step 8:** Commit:
```bash
git add frontend/src/components/FinancialsTab.tsx
git commit -m "feat: add By Tables / By Graphs toggle to FinancialsTab"
```

---

## Task 8 — Wire Toggle into InsightsTab

**Files:**
- Modify: `frontend/src/components/InsightsTab.tsx`

**What to add:**

1. **Import** `InsightsGraphsView`:
```ts
import InsightsGraphsView from "./InsightsGraphsView";
```

2. **Add state** inside `InsightsTab` export function (or main component):
```ts
const [graphView, setGraphView] = useState(false);
```
Note: `useState` is already imported in InsightsTab.

3. **Add "By Tables / By Graphs" toggle** — add it at the top of the JSX returned by `InsightsTab`, before the existing content (or before the group tables). Use the same button pattern as Task 7.

4. **Conditional render** — wrap the existing group table rendering (the `data.groups.map(...)` block) in `{!graphView && (...)}` and add:
```tsx
{graphView && <InsightsGraphsView data={data} />}
```
The WACC section should remain visible in both views (do NOT wrap the WACC section in the toggle).

**Step 1:** Add the import.

**Step 2:** Add `graphView` state.

**Step 3:** Add toggle buttons at the top of the insights content area.

**Step 4:** Wrap existing group tables in `{!graphView && (...)}`.

**Step 5:** Add `{graphView && <InsightsGraphsView data={data} />}`.

**Step 6:** Run full build:
```
cd frontend && npm run build 2>&1 | tail -10
```
Expected: `✓ built in X.XXs`

**Step 7:** Commit:
```bash
git add frontend/src/components/InsightsTab.tsx
git commit -m "feat: add By Tables / By Graphs toggle to InsightsTab"
```

---

## Task 9 — Final Build Verification & Polish

**Files:**
- Read-only check of all modified files.

**Step 1:** Run full TypeScript + Vite build:
```
cd frontend && npm run build 2>&1
```
Expected: `✓ built in X.XXs` with no TypeScript errors. Bundle size warnings are acceptable.

**Step 2:** Run lint:
```
cd frontend && npm run lint 2>&1 | head -30
```
Expected: no errors (warnings OK).

**Step 3:** Visual sanity-check checklist:
- [ ] "By Tables" / "By Graphs" toggle appears in Financials tab controls bar
- [ ] Switching to "By Graphs" hides the tables and shows charts
- [ ] Charts render when a ticker is loaded (e.g., AAPL or MSFT)
- [ ] "⚙ Series" button on each chart opens series toggle popover
- [ ] Toggling a series off removes it from the chart
- [ ] Toggled series state persists when switching tabs and back (Zustand persists to localStorage)
- [ ] "By Tables" / "By Graphs" toggle appears in Insights tab
- [ ] Insights charts render all groups
- [ ] WACC section still visible in Insights graph view
- [ ] Responsive: charts reflow to 2-col on narrow window

**Step 4:** Final commit:
```bash
git add -A
git commit -m "feat: Financials & Insights dual-view (By Tables / By Graphs) — complete"
```

---

## Summary of Files Created/Modified

| File | Action |
|---|---|
| `frontend/src/utils/chartDataUtils.ts` | **CREATE** — data extraction utilities |
| `frontend/src/store/layoutStore.ts` | **MODIFY** — add `hiddenGraphSeries` state |
| `frontend/src/components/ChartCard.tsx` | **CREATE** — reusable chart card with series toggle |
| `frontend/src/components/FinancialsGraphsView.tsx` | **CREATE** — all financial charts (Rows 0–2) |
| `frontend/src/components/InsightsGraphsView.tsx` | **CREATE** — all insight group charts |
| `frontend/src/components/FinancialsTab.tsx` | **MODIFY** — add view toggle, wrap tables, render graphs |
| `frontend/src/components/InsightsTab.tsx` | **MODIFY** — add view toggle, wrap tables, render graphs |

## Notes for Implementer

- **recharts is already installed** (`"recharts": "^3.8.0"` in `package.json`). No `npm install` needed.
- **Row labels are case-sensitive** — use exact strings (e.g., `"Revenues"`, `"Total assets"` with lowercase 'a').
- **Missing rows** are handled gracefully: `buildChartData` returns `null` for missing rows and recharts skips null points on lines/areas.
- **Scale toggle** — Financials charts divide by `scaleDivisor(scale)` so switching scale in the Financials controls bar updates chart Y-axis values. When `graphView` is true, pass `scale` prop from the parent state.
- **Don't re-fetch** — graphs read from the same `data`/`extData` already in memory. No new API calls.
- **Zustand persistence** — `hiddenGraphSeries` is added to the `gv_layout_v4` key automatically via `persist` middleware. No migration needed.
