/**
 * SegmentsTab.tsx
 *
 * Self-contained component: fetches /api/segments/{ticker} and renders:
 *   Top row  — Stacked Bar Chart (65%) │ Donut Chart (35%)
 *   Bottom   — Interactive Revenue Table (full width)
 *
 * Shared `selected` state wires donut clicks → bar highlighting + table filter.
 * Returns null silently when segment data is unavailable.
 */
import { useState, useEffect, useCallback, memo, Fragment } from "react";
import type { SegmentsData, Segment } from "../types";

const NAVY = "var(--gv-navy)";

// ── Color palette ─────────────────────────────────────────────────────────────

const SEG_COLORS = [
  "var(--gv-blue)",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
  "#f97316",
  "var(--gv-navy)",
];

const segColor = (i: number) => SEG_COLORS[i % SEG_COLORS.length];

// ── Formatters ────────────────────────────────────────────────────────────────

function fRev(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  const neg = v < 0;
  const abs = Math.abs(v);
  let s: string;
  if      (abs >= 1e12) s = `${(abs / 1e12).toFixed(1)}T`;
  else if (abs >= 1e9)  s = `${(abs / 1e9).toFixed(1)}B`;
  else if (abs >= 1e6)  s = `${(abs / 1e6).toFixed(1)}M`;
  else if (abs >= 1e3)  s = `${(abs / 1e3).toFixed(0)}K`;
  else                  s = abs.toFixed(0);
  return neg ? `($${s})` : `$${s}`;
}

function calcYoy(
  curr: number | null,
  prev: number | null,
): { str: string; pos: boolean | null } {
  if (curr == null || prev == null || prev === 0) return { str: "—", pos: null };
  const pct = ((curr - prev) / Math.abs(prev)) * 100;
  const pos = pct >= 0;
  return { str: `${pos ? "↑" : "↓"} ${Math.abs(pct).toFixed(1)}%`, pos };
}

// ── SVG Donut helpers ─────────────────────────────────────────────────────────

function polarXY(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function donutArcPath(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
  startDeg: number,
  endDeg: number,
  gapDeg: number,
): string {
  const s = startDeg + gapDeg / 2;
  const e = endDeg - gapDeg / 2;
  if (e - s < 0.5) return "";
  const large = e - s > 180 ? 1 : 0;
  const o1 = polarXY(cx, cy, outerR, s);
  const o2 = polarXY(cx, cy, outerR, e);
  const i1 = polarXY(cx, cy, innerR, e);
  const i2 = polarXY(cx, cy, innerR, s);
  return [
    `M ${o1.x} ${o1.y}`,
    `A ${outerR} ${outerR} 0 ${large} 1 ${o2.x} ${o2.y}`,
    `L ${i1.x} ${i1.y}`,
    `A ${innerR} ${innerR} 0 ${large} 0 ${i2.x} ${i2.y}`,
    "Z",
  ].join(" ");
}

// ── Stacked Bar Chart ─────────────────────────────────────────────────────────

interface BarRect {
  x: number;
  y: number;
  h: number;
  si: number;
}

const StackedBarChart = memo(function StackedBarChart({
  data,
  selected,
}: {
  data: SegmentsData;
  selected: string | null;
}) {
  const { years, segments } = data;
  const chartYears = [...years].reverse(); // oldest → newest (left → right)
  if (chartYears.length === 0 || segments.length === 0) return null;

  const VW = 500, VH = 220;
  const PL = 52, PR = 10, PT = 12, PB = 30;
  const cW = VW - PL - PR;
  const cH = VH - PT - PB;
  const n     = chartYears.length;
  const slotW = cW / n;
  const barW  = slotW * 0.55;
  const barOff = (slotW - barW) / 2;

  const totals = chartYears.map((yr) =>
    segments.reduce((sum, s) => sum + Math.max(s.revenue_by_year[yr] ?? 0, 0), 0),
  );
  const maxTotal = Math.max(...totals, 1);
  const toY = (v: number) => PT + cH - (v / maxTotal) * cH;

  const barRects: BarRect[] = [];
  chartYears.forEach((yr, xi) => {
    const x = PL + xi * slotW + barOff;
    let cumH = 0;
    segments.forEach((seg, si) => {
      const val = Math.max(seg.revenue_by_year[yr] ?? 0, 0);
      const h   = (val / maxTotal) * cH;
      if (h > 0.4) {
        barRects.push({ x, y: PT + cH - cumH - h, h, si });
      }
      cumH += h;
    });
  });

  const yTicks = [0, 0.25, 0.5, 0.75, 1.0].map((f) => ({
    raw: maxTotal * f,
    y:   toY(maxTotal * f),
  }));

  return (
    <svg
      viewBox={`0 0 ${VW} ${VH}`}
      className="w-full h-auto"
      style={{ display: "block", overflow: "visible" }}
    >
      {/* Grid lines */}
      {yTicks.map(({ y }, i) => (
        <line
          key={i}
          x1={PL} x2={VW - PR} y1={y} y2={y}
          stroke="var(--gv-border)"
          strokeWidth={i === 0 ? 1.5 : 0.7}
          strokeDasharray={i > 0 ? "3 3" : undefined}
        />
      ))}

      {/* Y-axis labels */}
      {yTicks.map(({ raw, y }, i) => (
        <text
          key={i}
          x={PL - 6} y={y + 3.5}
          textAnchor="end" fontSize={9} fill="var(--gv-text-muted)"
          fontFamily="system-ui, sans-serif"
        >
          {raw === 0 ? "0" : fRev(raw).replace("$", "")}
        </text>
      ))}

      {/* Bars — dim when a different segment is selected */}
      {barRects.map((r, i) => {
        const segName  = segments[r.si]?.name;
        const dimmed   = selected !== null && selected !== segName;
        return (
          <rect
            key={i}
            x={r.x} y={r.y} width={barW} height={r.h}
            fill={segColor(r.si)}
            opacity={dimmed ? 0.18 : 0.90}
            rx={1.5}
            style={{ transition: "opacity 0.2s" }}
          />
        );
      })}

      {/* X-axis year labels */}
      {chartYears.map((yr, xi) => (
        <text
          key={yr}
          x={PL + xi * slotW + slotW / 2}
          y={VH - PB + 16}
          textAnchor="middle" fontSize={10} fill="var(--gv-text-muted)"
          fontFamily="system-ui, sans-serif"
        >
          {yr}
        </text>
      ))}
    </svg>
  );
});

// ── Donut Chart ───────────────────────────────────────────────────────────────

interface DonutSlice {
  name: string;
  value: number;
  pct: number;
  startDeg: number;
  endDeg: number;
  colorIdx: number;
}

const DonutChart = memo(function DonutChart({
  data,
  selected,
  onSelect,
}: {
  data: SegmentsData;
  selected: string | null;
  onSelect: (name: string | null) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);

  const latestYear = data.years[0] ?? "";
  const total = data.segments.reduce(
    (sum, s) => sum + Math.max(s.revenue_by_year[latestYear] ?? 0, 0),
    0,
  );

  if (total === 0) return null;

  const slices: DonutSlice[] = [];
  let cursor = 0;
  data.segments.forEach((seg, i) => {
    const val = Math.max(seg.revenue_by_year[latestYear] ?? 0, 0);
    if (val === 0) return;
    const pct  = val / total;
    const span = pct * 360;
    slices.push({ name: seg.name, value: val, pct, startDeg: cursor, endDeg: cursor + span, colorIdx: i });
    cursor += span;
  });

  const cx = 100, cy = 100, outerR = 86, innerR = 52;
  const GAP = slices.length > 1 ? 2.5 : 0;

  const activeLabel = hovered ?? selected;

  return (
    <svg
      viewBox="0 0 200 200"
      className="w-full h-auto"
      style={{ display: "block", overflow: "visible" }}
    >
      {slices.map((sl) => {
        const isHighlighted = activeLabel === null || activeLabel === sl.name;
        const isSelected    = selected === sl.name;
        const isHovered     = hovered === sl.name;
        const scale = (isHovered || isSelected) ? 1.05 : 1;
        const path  = donutArcPath(cx, cy, outerR, innerR, sl.startDeg, sl.endDeg, GAP);
        if (!path) return null;
        return (
          <path
            key={sl.name}
            d={path}
            fill={segColor(sl.colorIdx)}
            opacity={isHighlighted ? 0.95 : 0.25}
            style={{
              cursor: "pointer",
              transform: scale !== 1 ? `scale(${scale})` : undefined,
              transformOrigin: `${cx}px ${cy}px`,
              transition: "opacity 0.15s, transform 0.12s",
            }}
            onClick={() => onSelect(selected === sl.name ? null : sl.name)}
            onMouseEnter={() => setHovered(sl.name)}
            onMouseLeave={() => setHovered(null)}
          />
        );
      })}

      {/* Center label */}
      {activeLabel === null ? (
        <>
          <text x={cx} y={cy - 7} textAnchor="middle" fontSize={12} fontWeight={700} fill={NAVY} fontFamily="system-ui, sans-serif">
            {fRev(total)}
          </text>
          <text x={cx} y={cy + 9} textAnchor="middle" fontSize={8.5} fill="var(--gv-text-muted)" fontFamily="system-ui, sans-serif">
            {latestYear} Total Revenue
          </text>
        </>
      ) : (() => {
        const sl = slices.find((s) => s.name === activeLabel);
        if (!sl) return null;
        return (
          <>
            <text x={cx} y={cy - 8} textAnchor="middle" fontSize={11.5} fontWeight={700} fill={NAVY} fontFamily="system-ui, sans-serif">
              {fRev(sl.value)}
            </text>
            <text x={cx} y={cy + 7} textAnchor="middle" fontSize={8.5} fill="var(--gv-text-muted)" fontFamily="system-ui, sans-serif">
              {(sl.pct * 100).toFixed(1)}% of total
            </text>
          </>
        );
      })()}
    </svg>
  );
});

// ── Revenue Table ─────────────────────────────────────────────────────────────

function SegmentsTable({
  data,
  selected,
  onSelect,
}: {
  data: SegmentsData;
  selected: string | null;
  onSelect: (name: string | null) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const { years, segments } = data;

  const latestYear = years[0] ?? "";
  const prevYear   = years[1] ?? "";

  const totalRev = segments.reduce(
    (sum, s) => sum + Math.max(s.revenue_by_year[latestYear] ?? 0, 0),
    0,
  );
  const hasOI     = segments.some((s) => s.operating_income_by_year?.[latestYear] != null);
  const hasAssets = segments.some((s) => s.assets_by_year?.[latestYear] != null);
  const totalOI   = segments.reduce((sum, s) => sum + (s.operating_income_by_year?.[latestYear] ?? 0), 0);
  const totalAssets = segments.reduce((sum, s) => sum + (s.assets_by_year?.[latestYear] ?? 0), 0);

  const thStyle: React.CSSProperties = {
    background: NAVY,
    color: "#fff",
    fontWeight: 700,
    padding: "7px 10px",
    fontSize: "0.73em",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    whiteSpace: "nowrap",
    textAlign: "left",
    border: "none",
  };

  const tdBase: React.CSSProperties = {
    padding: "7px 10px",
    fontSize: "0.82em",
    color: NAVY,
    border: "none",
    borderBottom: "1px solid #f0f2f5",
  };

  function toggle(name: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  const colSpanTotal = 4 + (hasOI ? 1 : 0) + (hasAssets ? 1 : 0) + 1;

  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ ...thStyle, width: 22, padding: "7px 4px 7px 8px" }} />
          <th style={{ ...thStyle }}>Segment</th>
          <th style={{ ...thStyle, textAlign: "right" }}>Revenue ({latestYear})</th>
          <th style={{ ...thStyle, textAlign: "right" }}>YoY</th>
          {hasOI     && <th style={{ ...thStyle, textAlign: "right" }}>Op. Income</th>}
          {hasAssets && <th style={{ ...thStyle, textAlign: "right" }}>Assets</th>}
          <th style={{ ...thStyle, width: 26, textAlign: "center" }} />
        </tr>
      </thead>
      <tbody>
        {segments.map((seg: Segment, si: number) => {
          const curr    = seg.revenue_by_year[latestYear] ?? null;
          const prev    = seg.revenue_by_year[prevYear]   ?? null;
          const yoy     = calcYoy(curr, prev);
          const oi      = seg.operating_income_by_year?.[latestYear] ?? null;
          const assets  = seg.assets_by_year?.[latestYear] ?? null;
          const isOpen  = expanded.has(seg.name);
          const isSelected = selected === seg.name;
          const dimmed  = selected !== null && !isSelected;
          const share   = totalRev > 0 && curr != null
            ? ((Math.max(curr, 0) / totalRev) * 100).toFixed(0)
            : null;
          const rowBg   = si % 2 === 0 ? "#fff" : "#f9fafb";

          return (
            <Fragment key={seg.name}>
              <tr style={{ background: rowBg, opacity: dimmed ? 0.35 : 1, transition: "opacity 0.2s" }}>

                {/* Swatch — toggles segment filter */}
                <td
                  style={{ ...tdBase, padding: "7px 4px 7px 8px", textAlign: "center", cursor: "pointer" }}
                  onClick={() => onSelect(isSelected ? null : seg.name)}
                >
                  <div style={{
                    width: 9, height: 9, borderRadius: 2,
                    background: segColor(si), display: "inline-block",
                    outline: isSelected ? `2px solid ${segColor(si)}` : "none",
                    outlineOffset: 2,
                  }} />
                </td>

                {/* Name */}
                <td style={{ ...tdBase, cursor: "pointer" }} onClick={() => toggle(seg.name)}>
                  <span style={{ fontWeight: 600 }}>{seg.name}</span>
                  {share && (
                    <span style={{ marginLeft: 6, fontSize: "0.80em", color: "var(--gv-text-muted)" }}>
                      {share}%
                    </span>
                  )}
                </td>

                {/* Revenue */}
                <td
                  style={{ ...tdBase, textAlign: "right", fontFamily: "monospace", fontVariantNumeric: "tabular-nums", cursor: "pointer" }}
                  onClick={() => toggle(seg.name)}
                >
                  {fRev(curr)}
                </td>

                {/* YoY */}
                <td
                  style={{
                    ...tdBase,
                    textAlign: "right",
                    fontVariantNumeric: "tabular-nums",
                    fontWeight: yoy.pos !== null ? 600 : 400,
                    color: yoy.pos === true ? "#16a34a" : yoy.pos === false ? "#dc2626" : "var(--gv-text-muted)",
                    cursor: "pointer",
                  }}
                  onClick={() => toggle(seg.name)}
                >
                  {yoy.str}
                </td>

                {hasOI && (
                  <td
                    style={{ ...tdBase, textAlign: "right", fontFamily: "monospace", fontVariantNumeric: "tabular-nums", color: oi != null && oi < 0 ? "#dc2626" : NAVY, cursor: "pointer" }}
                    onClick={() => toggle(seg.name)}
                  >
                    {fRev(oi)}
                  </td>
                )}

                {hasAssets && (
                  <td
                    style={{ ...tdBase, textAlign: "right", fontFamily: "monospace", fontVariantNumeric: "tabular-nums", cursor: "pointer" }}
                    onClick={() => toggle(seg.name)}
                  >
                    {fRev(assets)}
                  </td>
                )}

                {/* Expand chevron */}
                <td
                  style={{ ...tdBase, textAlign: "center", color: "var(--gv-text-muted)", fontSize: "0.70em", cursor: "pointer" }}
                  onClick={() => toggle(seg.name)}
                >
                  {isOpen ? "▲" : "▼"}
                </td>
              </tr>

              {/* Expanded history sub-row */}
              {isOpen && (
                <tr>
                  <td
                    colSpan={colSpanTotal}
                    style={{ padding: 0, background: "#f0f4f9", borderBottom: "1px solid #e5e7eb" }}
                  >
                    <div style={{ padding: "10px 14px 10px 28px" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                          <tr>
                            {years.map((yr) => (
                              <th
                                key={yr}
                                style={{ ...thStyle, background: "#dde3ec", color: NAVY, padding: "4px 8px", fontSize: "0.72em", textAlign: "right" }}
                              >
                                {yr}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            {years.map((yr, yi) => {
                              const v  = seg.revenue_by_year[yr] ?? null;
                              const p  = seg.revenue_by_year[years[yi + 1]] ?? null;
                              const yy = calcYoy(v, p);
                              return (
                                <td
                                  key={yr}
                                  style={{ padding: "6px 8px", textAlign: "right", fontFamily: "monospace", fontSize: "0.84em", color: NAVY, border: "none", background: "transparent" }}
                                >
                                  <div>{fRev(v)}</div>
                                  {yy.str !== "—" && (
                                    <div style={{ fontSize: "0.80em", marginTop: 2, color: yy.pos === true ? "#16a34a" : "#dc2626" }}>
                                      {yy.str}
                                    </div>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}

        {/* Totals row — hidden when filtered to single segment */}
        {selected === null && (
          <tr style={{ background: "#f0f4f9" }}>
            <td style={{ ...tdBase, padding: "7px 4px 7px 8px" }} />
            <td style={{ ...tdBase, fontWeight: 700 }}>Total</td>
            <td style={{ ...tdBase, textAlign: "right", fontFamily: "monospace", fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>
              {fRev(totalRev)}
            </td>
            <td style={{ ...tdBase }} />
            {hasOI && (
              <td style={{ ...tdBase, textAlign: "right", fontFamily: "monospace", fontVariantNumeric: "tabular-nums", fontWeight: 700, color: totalOI < 0 ? "#dc2626" : NAVY }}>
                {fRev(totalOI)}
              </td>
            )}
            {hasAssets && (
              <td style={{ ...tdBase, textAlign: "right", fontFamily: "monospace", fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>
                {fRev(totalAssets)}
              </td>
            )}
            <td style={{ ...tdBase }} />
          </tr>
        )}
      </tbody>
    </table>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function SegmentsTab({ ticker }: { ticker: string }) {
  const [data, setData]         = useState<SegmentsData | null>(null);
  const [loading, setLoading]   = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setLoading(true);
    setSelected(null);
    fetch(`/api/segments/${ticker}`)
      .then((r) => r.json())
      .then((d: SegmentsData) => setData(d.segments?.length > 0 ? d : null))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [ticker]);

  const handleSelect = useCallback((name: string | null) => {
    setSelected((prev) => (prev === name ? null : name));
  }, []);

  if (loading || !data) return null;

  return (
    <div style={{ marginTop: 32 }}>

      {/* Section header */}
      <div style={{
        fontSize: "1.05em", fontWeight: 700, color: "#fff",
        background: NAVY, padding: "6px 15px", borderRadius: 4,
        marginBottom: 14,
      }}>
        Business Segments
      </div>

      {/* Legend strip + clear filter */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mb-3.5">
        {data.segments.map((s, i) => {
          const isSelected = selected === s.name;
          return (
            <div
              key={s.name}
              onClick={() => handleSelect(s.name)}
              className="flex items-center gap-1.5 cursor-pointer"
              style={{ opacity: selected !== null && !isSelected ? 0.35 : 1, transition: "opacity 0.2s" }}
            >
              <div style={{
                width: 9, height: 9, borderRadius: 2,
                background: segColor(i), flexShrink: 0,
                outline: isSelected ? `2px solid ${segColor(i)}` : "none",
                outlineOffset: 2,
              }} />
              <span style={{ fontSize: "0.75em", color: "var(--gv-text-dim)" }}>{s.name}</span>
            </div>
          );
        })}
        {selected !== null && (
          <button
            onClick={() => setSelected(null)}
            className="ml-auto text-xs px-2.5 py-0.5 rounded border border-slate-300 bg-white text-slate-500 hover:bg-slate-50 cursor-pointer"
          >
            Clear filter
          </button>
        )}
      </div>

      {/* ── Top row: Bar chart (left, ~65%) + Donut (right, ~35%) ── */}
      {/*   Mobile: flex-col → Donut (order-1) on top, Bar (order-2) below  */}
      {/*   Desktop: flex-row → Bar (order-1) left, Donut (order-2) right   */}
      <div className="flex flex-col md:flex-row gap-6 md:gap-8 items-center mb-5">

        {/* Stacked bar — left on desktop, bottom on mobile */}
        <div className="order-2 md:order-1 w-full md:w-[65%]">
          <StackedBarChart data={data} selected={selected} />
        </div>

        {/* Donut — right on desktop, top on mobile */}
        <div className="order-1 md:order-2 w-full md:w-[35%] flex justify-center">
          <div style={{ width: "100%", maxWidth: 260 }}>
            <DonutChart data={data} selected={selected} onSelect={handleSelect} />
          </div>
        </div>
      </div>

      {/* ── Bottom: Revenue table (full width) ── */}
      <div style={{ border: "1px solid #e5e7eb", borderRadius: 6, overflow: "hidden" }}>
        <SegmentsTable data={data} selected={selected} onSelect={handleSelect} />
      </div>
    </div>
  );
}
