/**
 * IndustryComparisonCell.tsx
 *
 * Compact cell for financial data tables that benchmarks a single company
 * metric against its industry average via an animated bullet chart.
 *
 * Layout (stacked, ~72 px tall):
 *   ┌─────────────────────────────┐
 *   │ Industry: 24.5x      +18.4% │  ← 10px muted labels
 *   │  ▏──────|━━━━━━━●──────▕   │  ← 5 px track + animated marker
 *   │  [↗ Above Avg]              │  ← colored badge
 *   └─────────────────────────────┘
 *
 * Usage:
 *   <IndustryComparisonCell
 *     companyValue={29.1}
 *     industryAvg={24.5}
 *     metricName="P/E Ratio"
 *     higherIsBetter={false}
 *   />
 */

import { memo, useId } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  TrendingUp, TrendingDown, Minus,
  ArrowUpRight, ArrowDownRight,
  ShieldCheck, ShieldAlert,
} from "lucide-react";
import {
  analyzeBenchmark, formatMetricValue,
  type BenchmarkResult, type IconName,
} from "../utils/financialAnalysis";

// ── Icon registry ─────────────────────────────────────────────────────────────

const ICON_MAP: Record<IconName, React.ComponentType<{ size?: number; color?: string; strokeWidth?: number }>> = {
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  ShieldAlert,
};

// ── Animated bullet bar ───────────────────────────────────────────────────────

interface BulletBarProps {
  result:     BenchmarkResult;
  animKey:    string;   // change this to re-trigger the entrance animation
}

const BulletBar = memo(function BulletBar({ result, animKey }: BulletBarProps) {
  const { companyPos, fillHex, markerHex } = result;
  const reduced = useReducedMotion();

  // Fill region spans from industry avg (50) to the company marker.
  const fillLeft  = Math.min(50, companyPos);
  const fillRight = Math.max(50, companyPos);

  const transition = reduced
    ? { duration: 0 }
    : { duration: 0.52, ease: [0.22, 1, 0.36, 1] as const };

  return (
    /* Outer: sets the hit-target height so the thin bar + protruding marker don't clip */
    <div style={{ position: "relative", height: 18, display: "flex", alignItems: "center" }}>

      {/* ── Track ── */}
      <div
        aria-hidden
        style={{
          position: "absolute", inset: "0 0", margin: "auto",
          height: 5, borderRadius: 9999,
          background: "#e5e7eb",
          overflow: "visible",
        }}
      >
        {/* Colored fill between industry avg and company marker */}
        <motion.div
          key={`fill-${animKey}`}
          initial={{ left: "50%", right: `${100 - 50}%` }}
          animate={{ left: `${fillLeft}%`, right: `${100 - fillRight}%` }}
          transition={transition}
          style={{
            position: "absolute", top: 0, bottom: 0,
            background: fillHex, borderRadius: 9999,
          }}
        />
      </div>

      {/* ── Industry avg tick (always at 50%) ── */}
      <div
        aria-hidden
        title="Industry average"
        style={{
          position: "absolute",
          left: "50%", transform: "translateX(-50%)",
          width: 2, height: 14,
          background: "#1f2937",
          borderRadius: 2,
          zIndex: 2,
        }}
      />

      {/* ── Company marker dot ── */}
      <motion.div
        key={`dot-${animKey}`}
        initial={{ left: "50%", scale: 0.4, opacity: 0 }}
        animate={{ left: `${companyPos}%`, scale: 1, opacity: 1 }}
        transition={{
          ...transition,
          scale:   { ...transition, type: "spring", stiffness: 320, damping: 22, delay: 0.08 },
          opacity: { duration: 0.2 },
        }}
        aria-hidden
        style={{
          position: "absolute",
          /* center the 11 px dot on its left % position */
          marginLeft: -5.5,
          width: 11, height: 11,
          borderRadius: "50%",
          background: markerHex,
          border: "2px solid #ffffff",
          boxShadow: `0 1px 4px rgba(0,0,0,0.22), 0 0 0 1.5px ${markerHex}40`,
          zIndex: 3,
        }}
      />
    </div>
  );
});

// ── Main component ────────────────────────────────────────────────────────────

interface IndustryComparisonCellProps {
  companyValue:   number;
  industryAvg:    number;
  metricName:     string;
  higherIsBetter: boolean;
  /** Optional custom formatter; defaults to financialAnalysis.formatMetricValue */
  formatValue?:   (v: number) => string;
  /** Tailwind class(es) added to the root div for sizing overrides */
  className?:     string;
}

export const IndustryComparisonCell = memo(function IndustryComparisonCell({
  companyValue,
  industryAvg,
  metricName,
  higherIsBetter,
  formatValue,
  className = "",
}: IndustryComparisonCellProps) {
  const uid    = useId();
  const result = analyzeBenchmark(companyValue, industryAvg, metricName, higherIsBetter);
  const Icon   = ICON_MAP[result.iconName];
  const fmt    = formatValue ?? ((v: number) => formatMetricValue(v, metricName));

  const sign      = result.pctDiff > 0 ? "+" : "";
  const diffLabel = `${sign}${result.pctDiff.toFixed(1)}%`;
  // Animate key changes whenever the underlying data changes so the marker re-enters.
  const animKey = `${companyValue}-${industryAvg}`;

  return (
    <div
      className={`flex flex-col gap-0.5 py-1 min-w-[108px] max-w-[200px] select-none ${className}`}
      role="img"
      aria-label={`${metricName}: ${fmt(companyValue)} vs industry ${fmt(industryAvg)} — ${result.label}`}
    >
      {/* ── Line 1: reference values ── */}
      <div className="flex items-baseline justify-between gap-2 px-px">
        <span className="text-[10px] leading-none text-gray-400">
          Ind:&thinsp;
          <span className="font-medium text-gray-500">{fmt(industryAvg)}</span>
        </span>
        <span
          className="text-[9px] font-semibold leading-none tabular-nums shrink-0"
          style={{ color: result.markerHex }}
        >
          {diffLabel}
        </span>
      </div>

      {/* ── Line 2: animated bullet chart ── */}
      <BulletBar result={result} animKey={animKey} key={uid} />

      {/* ── Line 3: badge ── */}
      <div
        className="inline-flex items-center gap-[3px] self-start rounded px-1.5 py-[3px] mt-0.5"
        style={{ background: result.badgeBg }}
      >
        <Icon size={9} color={result.badgeFg} strokeWidth={2.5} />
        <span
          className="text-[10px] font-semibold leading-none"
          style={{ color: result.badgeFg }}
        >
          {result.label}
        </span>
      </div>
    </div>
  );
});

export default IndustryComparisonCell;

// ── Demo / Storybook-style preview (remove in production) ─────────────────────

/**
 * DemoGrid — renders a 3-column grid of sample cells.
 * Import and drop into any page for a quick visual test:
 *   import { IndustryComparisonCellDemo } from "./IndustryComparisonCell";
 */
export function IndustryComparisonCellDemo() {
  const SAMPLES: Array<{
    label: string;
    companyValue: number;
    industryAvg:  number;
    metricName:   string;
    higherIsBetter: boolean;
  }> = [
    { label: "P/E — overvalued",        companyValue: 42.0,  industryAvg: 22.5,  metricName: "P/E Ratio",         higherIsBetter: false },
    { label: "P/E — undervalued",        companyValue: 11.2,  industryAvg: 22.5,  metricName: "P/E Ratio",         higherIsBetter: false },
    { label: "Net Margin — above avg",   companyValue: 28.4,  industryAvg: 18.1,  metricName: "Net Margin",        higherIsBetter: true  },
    { label: "Net Margin — thin",        companyValue: 4.1,   industryAvg: 18.1,  metricName: "Net Margin",        higherIsBetter: true  },
    { label: "Revenue Growth — strong",  companyValue: 34.2,  industryAvg: 12.0,  metricName: "Revenue Growth",   higherIsBetter: true  },
    { label: "Debt/Equity — high risk",  companyValue: 3.8,   industryAvg: 1.2,   metricName: "Debt/Equity",       higherIsBetter: false },
    { label: "Debt/Equity — low risk",   companyValue: 0.3,   industryAvg: 1.2,   metricName: "Debt/Equity",       higherIsBetter: false },
    { label: "ROE — inline",             companyValue: 15.3,  industryAvg: 14.9,  metricName: "ROE",               higherIsBetter: true  },
    { label: "EV/EBITDA — extreme",      companyValue: 980.0, industryAvg: 14.0,  metricName: "EV/EBITDA",         higherIsBetter: false },
  ];

  return (
    <div className="p-6 bg-white">
      <h2 className="text-sm font-bold text-gray-700 mb-4">IndustryComparisonCell — visual test</h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: "12px 24px",
        }}
      >
        {SAMPLES.map((s) => (
          <div key={s.label} className="border border-gray-100 rounded-lg p-3 shadow-sm">
            <p className="text-[10px] text-gray-400 mb-1 font-medium uppercase tracking-wide">
              {s.label}
            </p>
            <IndustryComparisonCell
              companyValue={s.companyValue}
              industryAvg={s.industryAvg}
              metricName={s.metricName}
              higherIsBetter={s.higherIsBetter}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
