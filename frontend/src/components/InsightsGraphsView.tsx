import {
  BarChart,
  Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import ChartCard from "./ChartCard";
import { fmtPctTick, fmtRatioTick } from "../utils/chartDataUtils";
import type { InsightsData, InsightsGroup } from "../types";

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
  const ttFmt  = (v: unknown) => [(v != null ? (v as number).toFixed(2) + suffix : "—"), ""] as [string, string];

  const isCAGR = group.title.toLowerCase().includes("cagr") || group.title.toLowerCase().includes("growth");

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

  const growthGroups    = data.groups.filter(g => g.title.toLowerCase().includes("growth") || g.title.toLowerCase().includes("cagr"));
  const valuationGroups = data.groups.filter(g => g.title.toLowerCase().includes("valuation"));
  const profitGroups    = data.groups.filter(g => g.title.toLowerCase().includes("profitability"));
  const returnsGroups   = data.groups.filter(g => g.title.toLowerCase().includes("returns"));
  const row1Groups      = [...growthGroups, ...valuationGroups, ...profitGroups];
  const row2Groups      = [...returnsGroups, ...data.groups.filter(g =>
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
