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

  // ── Row 1: Valuation & Returns ────────────────────────────────────────────

  const vmCols = extData ? chartColumns(extData.columns) : [];

  // 1-A: Valuation Multiples
  const VM_SERIES = ["P/E", "P/S", "P/B", "P/Adj. FCF"];
  const VM_COLORS = [BLUE, GREEN, AMBER, PURPLE];
  const vmData    = extData ? buildChartData(vmCols, extData.market_valuation, VM_SERIES) : [];

  // 1-B: Debt Coverage
  const DC2_SERIES = ["Net Debt / EBITDA", "Interest Coverage"];
  const DC2_COLORS = [RED, GREEN];
  const dc2Data    = extData ? buildChartData(vmCols, extData.capital_structure, DC2_SERIES) : [];

  // 1-C: Profitability Margins
  const MARGIN_SERIES = ["Gross Margin", "EBITDA Margin", "Operating Margin", "Net Margin"];
  const MARGIN_COLORS = [BLUE, GREEN, AMBER, PURPLE];
  const marginData    = extData ? buildPctChartData(vmCols, extData.profitability, MARGIN_SERIES) : [];

  // 1-D: Returns on Capital
  const RET_SERIES = ["ROIC", "ROE", "ROA"];
  const RET_COLORS = [BLUE, GREEN, AMBER];
  const retData    = extData ? buildPctChartData(vmCols, extData.returns, RET_SERIES) : [];

  // ── Row 2: Capital Structure & Efficiency ────────────────────────────────

  // 2-A: Capital Structure ratios
  const CAP_SERIES = ["Debt/Equity", "Net Debt / EBITDA", "Debt / Adj. FCF"];
  const CAP_COLORS = [RED, AMBER, PINK];
  const capData    = extData ? buildChartData(vmCols, extData.capital_structure, CAP_SERIES) : [];

  // 2-B: Liquidity ratios
  const LIQ_SERIES = ["Current Ratio", "Quick Ratio", "Cash Ratio"];
  const LIQ_COLORS = [BLUE, GREEN, AMBER];
  const liqData    = extData ? buildChartData(vmCols, extData.liquidity, LIQ_SERIES) : [];

  // 2-C: Operating Cycle (days) — rename long labels
  const EFF_SERIES = ["Average receivables collection day", "Average days inventory in stock", "Average days payables outstanding"];
  const EFF_LABELS = ["Receivables Days", "Inventory Days", "Payables Days"];
  const EFF_COLORS = [BLUE, AMBER, GREEN];
  const effData    = extData ? buildChartData(vmCols, extData.efficiency, EFF_SERIES).map(d => {
    const out: Record<string, string | number | null> = { col: d.col };
    EFF_SERIES.forEach((s, i) => { out[EFF_LABELS[i]] = d[s]; });
    return out;
  }) : [];

  const scaleLabel = `(${scale})`;

  // Suppress unused variable warning for CYAN/NAVY (used in colors arrays below if extended)
  void CYAN; void NAVY;

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

      {/* ── Row 1: Valuation & Returns ── */}
      {extData && (
        <>
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
        </>
      )}

    </div>
  );
}
