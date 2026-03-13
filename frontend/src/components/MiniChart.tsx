/**
 * MiniChart.tsx
 *
 * Lazy-loadable SVG chart used by InsightsTab rows.
 * Bar variant  → CAGR / Growth groups (comparing rates across periods).
 * Line variant → Ratio / Return groups (trend over time + median line).
 *
 * Loaded via React.lazy() — only bundled when a row is first expanded.
 */

const CHART_NAVY = "var(--gv-navy)";

// ── Median helper ─────────────────────────────────────────────────────────────

function calcMedian(vals: number[]): number {
  const sorted = [...vals].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

// ── Props ─────────────────────────────────────────────────────────────────────

export interface MiniChartProps {
  cols: string[];
  vals: (number | null | string)[];
  isBar: boolean;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function MiniChart({ cols, vals, isBar }: MiniChartProps) {
  const nums = vals.map(v =>
    typeof v === "number" && isFinite(v) ? v : null,
  );
  const nonNull = nums.filter((v): v is number => v !== null);

  if (nonNull.length === 0) {
    return (
      <div style={{ padding: "12px 16px", color: "var(--gv-text-muted)", fontSize: "0.8em" }}>
        No chart data
      </div>
    );
  }

  const N  = cols.length;
  const VW = Math.max(N * 60, 300);
  const VH = 120;
  const PL = 6, PR = 6, PT = 10, PB = 26;
  const cW = VW - PL - PR;
  const cH = VH - PT - PB;

  const rawMin  = Math.min(...nonNull);
  const rawMax  = Math.max(...nonNull);
  const vMin    = Math.min(0, rawMin);
  const vMaxRaw = Math.max(0, rawMax);
  const vMax    = vMaxRaw === vMin ? vMin + 1 : vMaxRaw;
  const range   = vMax - vMin;

  const toY      = (v: number) => PT + cH - ((v - vMin) / range) * cH;
  const zeroY    = toY(0);
  const bW       = cW / N;
  const shortLbl = (c: string) =>
    c === "TTM" ? "TTM" : c.length > 4 ? c.slice(-4) : c;

  // ── Bar chart (CAGR / Growth) ─────────────────────────────────────────────

  if (isBar) {
    return (
      <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
        {/* baseline */}
        <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="var(--gv-border)" strokeWidth="1" />

        {nums.map((v, i) => {
          if (v === null) return null;
          const isTtm = cols[i] === "TTM";
          const x    = PL + i * bW + bW * 0.1;
          const w    = bW * 0.8;
          const top  = v >= 0 ? toY(v) : zeroY;
          const h    = Math.max(Math.abs(toY(v) - zeroY), 1);
          const fill = isTtm ? "#3b82f6" : v < 0 ? "#ef4444" : CHART_NAVY;
          return (
            <g key={i}>
              <rect x={x} y={top} width={w} height={h} fill={fill} opacity={isTtm ? 1 : 0.72} rx="1" />
              <text x={x + w / 2} y={VH - 4} textAnchor="middle" fontSize="8" fill="var(--gv-text-muted)">
                {shortLbl(cols[i])}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }

  // ── Line chart (Ratios / Returns) + median reference ─────────────────────

  const pts = nums
    .map((v, i) =>
      v !== null ? { x: PL + (i + 0.5) * bW, y: toY(v), col: cols[i], v } : null,
    )
    .filter(Boolean) as { x: number; y: number; col: string; v: number }[];

  const d       = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const median  = calcMedian(nonNull);
  const medianY = toY(median);

  return (
    <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
      {/* baseline */}
      <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="var(--gv-border)" strokeWidth="1" />

      {/* median reference line (only when ≥ 3 data points) */}
      {nonNull.length >= 3 && (
        <>
          <line
            x1={PL} y1={medianY} x2={VW - PR} y2={medianY}
            stroke="#f59e0b" strokeWidth="1" strokeDasharray="4 3" opacity="0.75"
          />
          <text
            x={VW - PR - 2} y={medianY - 3}
            textAnchor="end" fontSize="7" fill="#d97706"
            fontFamily="system-ui, sans-serif"
          >
            med
          </text>
        </>
      )}

      {/* line path */}
      {d && <path d={d} fill="none" stroke={CHART_NAVY} strokeWidth="1.5" opacity="0.7" />}

      {/* data points — TTM highlighted in blue */}
      {pts.map((p, i) => {
        const isTtm = p.col === "TTM";
        return (
          <g key={i}>
            <circle
              cx={p.x} cy={p.y}
              r={isTtm ? 4.5 : 2.5}
              fill={isTtm ? "#3b82f6" : CHART_NAVY}
              opacity={isTtm ? 1 : 0.8}
            />
            <text x={p.x} y={VH - 4} textAnchor="middle" fontSize="8" fill="var(--gv-text-muted)">
              {shortLbl(p.col)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
