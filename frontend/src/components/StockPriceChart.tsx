import { useState, useEffect, useMemo } from "react";
import {
  ComposedChart,
  Area,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { PriceHistoryData, PriceRange, PricePoint } from "../types";

// ── Palette ────────────────────────────────────────────────────────────────────
const NAVY  = "var(--gv-navy)";
const BLUE  = "var(--gv-blue)";
const MA50    = "#f59e0b";   // amber
const MA200   = "#10b981";   // emerald
const SPY_CLR = "#a78bfa";   // violet — S&P 500 benchmark

const RANGES: PriceRange[] = ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y", "10Y"];

// Whether to show each MA for a given range
const SHOW_MA50:  Record<PriceRange, boolean> = { "1D": false, "5D": false, "1M": false, "6M": true,  "YTD": true, "1Y": true, "5Y": true, "10Y": true };
const SHOW_MA200: Record<PriceRange, boolean> = { "1D": false, "5D": false, "1M": false, "6M": false, "YTD": false,"1Y": true, "5Y": true, "10Y": true };

// ── MA calculation ─────────────────────────────────────────────────────────────
function computeMA(pts: PricePoint[], period: number): (number | null)[] {
  return pts.map((_, i) => {
    if (i < period - 1) return null;
    const slice = pts.slice(i - period + 1, i + 1);
    return slice.reduce((s, p) => s + p.price, 0) / period;
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function fmtDate(dateStr: string, range: PriceRange): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (range === "1D" || range === "5D") {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  if (range === "1M" || range === "6M") {
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }
  return d.toLocaleDateString([], { year: "numeric", month: "short" });
}

function fmtPrice(v: number): string {
  return v >= 1 ? `$${v.toFixed(2)}` : `$${v.toFixed(4)}`;
}

function fmtVol(v: number | null): string {
  if (v == null) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

// ── Custom Tooltip ─────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, benchmarkOn }: {
  active?: boolean;
  benchmarkOn?: boolean;
  payload?: { name: string; value: number | null; color?: string; payload: { date: string; price: number; volume: number | null; priceNorm?: number; spyNorm?: number } }[];
}) {
  if (!active || !payload?.length) return null;
  const base = payload[0].payload;
  const priceRow  = payload.find(p => p.name === "price");
  const normRow   = payload.find(p => p.name === "priceNorm");
  const spyRow    = payload.find(p => p.name === "spyNorm");
  const ma50Row   = payload.find(p => p.name === "ma50");
  const ma200Row  = payload.find(p => p.name === "ma200");

  return (
    <div style={{
      background: "#fff",
      border: `1px solid ${BLUE}33`,
      borderRadius: 8,
      padding: "8px 12px",
      boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
      fontSize: "0.78em",
      minWidth: 120,
    }}>
      <div style={{ color: "#7b8899", marginBottom: 6, fontWeight: 500 }}>{base.date}</div>
      {!benchmarkOn && priceRow?.value != null && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, fontWeight: 700, color: NAVY }}>
          <span>Price</span><span>{fmtPrice(priceRow.value)}</span>
        </div>
      )}
      {benchmarkOn && normRow?.value != null && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, fontWeight: 700, color: BLUE }}>
          <span>Stock</span><span>{normRow.value.toFixed(1)}</span>
        </div>
      )}
      {benchmarkOn && spyRow?.value != null && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, color: SPY_CLR, marginTop: 3 }}>
          <span>S&amp;P 500</span><span>{spyRow.value.toFixed(1)}</span>
        </div>
      )}
      {ma50Row?.value != null && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, color: MA50, marginTop: 3 }}>
          <span>MA 50</span><span>{fmtPrice(ma50Row.value)}</span>
        </div>
      )}
      {ma200Row?.value != null && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, color: MA200, marginTop: 3 }}>
          <span>MA 200</span><span>{fmtPrice(ma200Row.value)}</span>
        </div>
      )}
      {base.volume != null && (
        <div style={{ color: "var(--gv-text-muted)", marginTop: 5, paddingTop: 5, borderTop: "1px solid #f0f2f5" }}>
          Vol: {fmtVol(base.volume)}
        </div>
      )}
    </div>
  );
}

// ── Shimmer Skeleton ───────────────────────────────────────────────────────────
function ChartSkeleton() {
  return (
    <div style={{ position: "relative", width: "100%", height: 300, borderRadius: 8, overflow: "hidden", background: "#f0f2f5" }}>
      <style>{`
        @keyframes shimmer-chart {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
        .chart-shimmer {
          background: linear-gradient(90deg, #f0f2f5 25%, #e2e6ea 50%, #f0f2f5 75%);
          background-size: 200% 100%;
          animation: shimmer-chart 1.4s infinite;
          width: 100%; height: 100%; border-radius: 8px;
        }
      `}</style>
      <div className="chart-shimmer" />
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────
interface Props {
  ticker: string;
}

export default function StockPriceChart({ ticker }: Props) {
  const [range, setRange]           = useState<PriceRange>("1Y");
  const [data, setData]             = useState<PriceHistoryData | null>(null);
  const [loading, setLoading]       = useState(true);
  const [, setError]                = useState<string | null>(null);
  const [showBenchmark, setShowBenchmark] = useState(false);
  const [spyPoints, setSpyPoints]   = useState<PricePoint[]>([]);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    setData(null);

    fetch(`/api/price-history/${encodeURIComponent(ticker)}?range=${range}`)
      .then(r => { if (!r.ok) throw new Error("fetch failed"); return r.json(); })
      .then((d: PriceHistoryData) => setData(d))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [ticker, range]);

  // Fetch SPY whenever benchmark is toggled on or range changes
  useEffect(() => {
    if (!showBenchmark) { setSpyPoints([]); return; }
    const ctrl = new AbortController();
    fetch(`/api/price-history/SPY?range=${range}`, { signal: ctrl.signal })
      .then(r => r.json())
      .then((d: PriceHistoryData) => setSpyPoints(d.points ?? []))
      .catch(() => setSpyPoints([]));
    return () => ctrl.abort();
  }, [showBenchmark, range]);

  const points = data?.points ?? [];
  const showMA50  = SHOW_MA50[range];
  const showMA200 = SHOW_MA200[range];

  // Compute MAs and merge into chart data; add normalized + SPY fields when benchmark is on
  const chartData = useMemo(() => {
    const ma50s  = showMA50  ? computeMA(points, 50)  : [];
    const ma200s = showMA200 ? computeMA(points, 200) : [];

    // Build SPY lookup by date
    const spyMap = new Map<string, number>();
    spyPoints.forEach(p => spyMap.set(p.date, p.price));

    const priceBase = points[0]?.price || 1;
    // Find first SPY price that aligns with stock dates
    let spyBase: number | null = null;
    for (const p of points) {
      const sp = spyMap.get(p.date);
      if (sp != null) { spyBase = sp; break; }
    }

    return points.map((p, i) => {
      const spyPrice = spyMap.get(p.date) ?? null;
      return {
        ...p,
        ma50:      showMA50  ? ma50s[i]  : undefined,
        ma200:     showMA200 ? ma200s[i] : undefined,
        priceNorm: showBenchmark ? (p.price / priceBase) * 100 : undefined,
        spyNorm:   showBenchmark && spyBase != null && spyPrice != null
          ? (spyPrice / spyBase) * 100
          : undefined,
      };
    });
  }, [points, showMA50, showMA200, showBenchmark, spyPoints]);

  // Y-axis domain — switch to normalized values when benchmark is on
  const allValues = chartData.flatMap(d => showBenchmark
    ? [d.priceNorm ?? null, d.spyNorm ?? null]
    : [d.price, d.ma50 ?? null, d.ma200 ?? null]
  ).filter((v): v is number => v != null && v > 0);

  const minP = allValues.length ? Math.min(...allValues) : 0;
  const maxP = allValues.length ? Math.max(...allValues) : 100;
  const pad  = (maxP - minP) * 0.05 || 1;

  // X-axis ticks: at most 6 labels
  const tickStep = Math.max(1, Math.floor(points.length / 6));
  const xTicks = points
    .filter((_, i) => i % tickStep === 0 || i === points.length - 1)
    .map(p => p.date);

  return (
    <div>
      {/* Range buttons + benchmark toggle */}
      <div style={{ display: "flex", gap: 4, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
        {RANGES.map(r => (
          <button
            key={r}
            onClick={() => setRange(r)}
            style={{
              padding: "4px 10px",
              fontSize: "0.75em",
              fontWeight: r === range ? 700 : 500,
              borderRadius: 6,
              border: `1px solid ${r === range ? BLUE : "#d1d5db"}`,
              background: r === range ? BLUE : "#fff",
              color: r === range ? "#fff" : "var(--gv-text-muted)",
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            {r}
          </button>
        ))}
        {/* S&P 500 benchmark toggle */}
        <button
          onClick={() => setShowBenchmark(b => !b)}
          style={{
            marginLeft: 8,
            padding: "4px 10px",
            fontSize: "0.75em",
            fontWeight: showBenchmark ? 700 : 500,
            borderRadius: 6,
            border: `1px solid ${showBenchmark ? SPY_CLR : "#d1d5db"}`,
            background: showBenchmark ? SPY_CLR : "#fff",
            color: showBenchmark ? "#fff" : "var(--gv-text-muted)",
            cursor: "pointer",
            transition: "all 0.15s",
          }}
        >
          vs S&amp;P 500
        </button>
      </div>

      {/* Legend: MA lines + benchmark */}
      {(showMA50 || showMA200 || showBenchmark) && !loading && points.length > 0 && (
        <div style={{ display: "flex", gap: 16, marginBottom: 8, fontSize: "0.72em", flexWrap: "wrap" }}>
          {showMA50 && (
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke={MA50} strokeWidth="2" strokeDasharray="4 2" /></svg>
              <span style={{ color: MA50, fontWeight: 600 }}>MA 50</span>
            </div>
          )}
          {showMA200 && (
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke={MA200} strokeWidth="2" strokeDasharray="4 2" /></svg>
              <span style={{ color: MA200, fontWeight: 600 }}>MA 200</span>
            </div>
          )}
          {showBenchmark && (
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke={SPY_CLR} strokeWidth="2" /></svg>
              <span style={{ color: SPY_CLR, fontWeight: 600 }}>S&amp;P 500 (indexed)</span>
            </div>
          )}
        </div>
      )}

      {/* Chart area */}
      {loading ? (
        <ChartSkeleton />
      ) : !points.length ? (
        <div style={{ height: 60, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--gv-text-muted)", fontSize: "0.8em", border: "1px dashed #e5e7eb", borderRadius: 8 }}>
          No price data available for {range}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart
            data={chartData}
            margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={BLUE} stopOpacity={0.18} />
                <stop offset="95%" stopColor={BLUE} stopOpacity={0.01} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="var(--gv-border)" vertical={false} />

            <XAxis
              dataKey="date"
              ticks={xTicks}
              tickFormatter={d => fmtDate(d, range)}
              tick={{ fontSize: 10, fill: "var(--gv-text-muted)" }}
              axisLine={false}
              tickLine={false}
            />

            {/* Left Y: price (raw) or indexed (benchmark mode) */}
            <YAxis
              yAxisId="price"
              domain={[minP - pad, maxP + pad]}
              tickFormatter={v => showBenchmark ? `${(v as number).toFixed(0)}` : `$${(v as number).toFixed(0)}`}
              tick={{ fontSize: 10, fill: "var(--gv-text-muted)" }}
              axisLine={false}
              tickLine={false}
              width={showBenchmark ? 36 : 52}
              label={showBenchmark ? { value: "base 100", angle: -90, position: "insideLeft", fontSize: 9, fill: "var(--gv-text-muted)", offset: 12 } : undefined}
            />

            {/* Right Y: volume */}
            <YAxis
              yAxisId="vol"
              orientation="right"
              tickFormatter={v => fmtVol(v as number)}
              tick={{ fontSize: 10, fill: "#d1d5db" }}
              axisLine={false}
              tickLine={false}
              width={42}
            />

            <Tooltip content={<ChartTooltip benchmarkOn={showBenchmark} />} />

            {/* Volume bars — hidden in benchmark mode */}
            {!showBenchmark && (
              <Bar
                yAxisId="vol"
                dataKey="volume"
                fill="#94a3b8"
                opacity={0.35}
                radius={[2, 2, 0, 0]}
                maxBarSize={8}
              />
            )}

            {/* Price area — raw price OR indexed (benchmark mode) */}
            <Area
              yAxisId="price"
              type="monotone"
              dataKey={showBenchmark ? "priceNorm" : "price"}
              stroke={BLUE}
              strokeWidth={2}
              fill={showBenchmark ? "none" : "url(#priceGrad)"}
              dot={false}
              activeDot={{ r: 4, fill: BLUE, stroke: "#fff", strokeWidth: 2 }}
            />

            {/* S&P 500 benchmark line */}
            {showBenchmark && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="spyNorm"
                stroke={SPY_CLR}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: SPY_CLR }}
                connectNulls
              />
            )}

            {/* MA 50 */}
            {showMA50 && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="ma50"
                stroke={MA50}
                strokeWidth={1.5}
                strokeDasharray="5 3"
                dot={false}
                activeDot={false}
                connectNulls
              />
            )}

            {/* MA 200 */}
            {showMA200 && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="ma200"
                stroke={MA200}
                strokeWidth={1.5}
                strokeDasharray="5 3"
                dot={false}
                activeDot={false}
                connectNulls
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
