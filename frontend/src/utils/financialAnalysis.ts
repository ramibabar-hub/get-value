/**
 * financialAnalysis.ts
 *
 * Logic engine for benchmarking a company metric against its industry average.
 * Returns everything the UI needs: position on a bullet bar, colors, badge label,
 * and the Lucide icon name — all derived from the metric name and sign convention.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

export type MetricCategory = 'valuation' | 'profitability' | 'growth' | 'risk' | 'generic';

export type SentimentLevel = 'outperform_strong' | 'outperform_mild' | 'inline' | 'underperform_mild' | 'underperform_strong';

export type IconName =
  | 'TrendingUp'
  | 'TrendingDown'
  | 'Minus'
  | 'ArrowUpRight'
  | 'ArrowDownRight'
  | 'ShieldCheck'
  | 'ShieldAlert';

export interface BenchmarkResult {
  /** Sentiment bucket */
  level: SentimentLevel;
  /** (company - industry) / |industry| × 100 — raw, can be outside ±100 */
  pctDiff: number;
  /** 0-100 clamped position on the bullet bar; 50 = industry avg */
  companyPos: number;
  /** Always 50: the industry average sits at the midpoint */
  readonly industryPos: 50;
  /** Short badge text, e.g. "Top Decile", "Overvalued" */
  label: string;
  /** Lucide icon component name */
  iconName: IconName;
  /** Hex color for the company marker dot & fill accent */
  markerHex: string;
  /** Lighter hex for the filled region between avg and company */
  fillHex: string;
  /** Badge background hex */
  badgeBg: string;
  /** Badge foreground hex */
  badgeFg: string;
  /** Detected metric category */
  category: MetricCategory;
}

// ── Color palettes ────────────────────────────────────────────────────────────

const PALETTE: Record<SentimentLevel, { markerHex: string; fillHex: string; badgeBg: string; badgeFg: string }> = {
  outperform_strong:   { markerHex: '#16a34a', fillHex: '#bbf7d0', badgeBg: '#dcfce7', badgeFg: '#14532d' },
  outperform_mild:     { markerHex: '#22c55e', fillHex: '#d1fae5', badgeBg: '#f0fdf4', badgeFg: '#166534' },
  inline:              { markerHex: '#6b7280', fillHex: '#e5e7eb', badgeBg: '#f9fafb', badgeFg: '#374151' },
  underperform_mild:   { markerHex: '#f97316', fillHex: '#fed7aa', badgeBg: '#fff7ed', badgeFg: '#9a3412' },
  underperform_strong: { markerHex: '#dc2626', fillHex: '#fecaca', badgeBg: '#fef2f2', badgeFg: '#7f1d1d' },
};

// ── Badge labels by category × sentiment ─────────────────────────────────────

const LABELS: Record<MetricCategory, Record<SentimentLevel, string>> = {
  valuation: {
    outperform_strong:   'Undervalued',
    outperform_mild:     'Fairly Priced',
    inline:              'At Market',
    underperform_mild:   'Slight Premium',
    underperform_strong: 'Overvalued',
  },
  profitability: {
    outperform_strong:   'High Margin',
    outperform_mild:     'Above Avg',
    inline:              'Avg Margin',
    underperform_mild:   'Below Avg',
    underperform_strong: 'Thin Margin',
  },
  growth: {
    outperform_strong:   'High Growth',
    outperform_mild:     'Growing',
    inline:              'Stable',
    underperform_mild:   'Slow Growth',
    underperform_strong: 'Declining',
  },
  risk: {
    outperform_strong:   'Low Risk',
    outperform_mild:     'Low-Mod Risk',
    inline:              'Moderate',
    underperform_mild:   'Elevated Risk',
    underperform_strong: 'High Leverage',
  },
  generic: {
    outperform_strong:   'Top Decile',
    outperform_mild:     'Above Avg',
    inline:              'In Line',
    underperform_mild:   'Below Avg',
    underperform_strong: 'Bottom Decile',
  },
};

// ── Category detection ────────────────────────────────────────────────────────

export function detectCategory(metricName: string): MetricCategory {
  const n = metricName.toLowerCase();
  if (/p\/e|p\/b|p\/s|ev\/|ev\s*\/|price.to|multiple|enterprise|valuat/.test(n)) return 'valuation';
  if (/margin|roa\b|roe\b|roic|roiic|return on|profit|ebitda\s*%|net income %/.test(n))   return 'profitability';
  if (/growth|cagr|yoy|revenue.*growth|eps.*growth|sales.*growth/.test(n))                 return 'growth';
  if (/debt|leverage|coverage|interest|d\/e|risk|beta|volatil|short/.test(n))              return 'risk';
  return 'generic';
}

// ── Bar position math ─────────────────────────────────────────────────────────

/**
 * Maps pctDiff → 0–100 bar position where 50 = industry avg.
 *
 * Uses a dynamic span so common deviations (~20-40%) use most of the bar,
 * while extreme outliers are clamped gracefully to [3, 97].
 */
function pctDiffToBarPos(pctDiff: number): number {
  const abs = Math.abs(pctDiff);
  // Span: at minimum ±30 pp so tiny differences don't look huge;
  // at maximum ±200 pp so extreme outliers don't blow the layout.
  const halfSpan = Math.max(30, Math.min(abs * 1.8, 200));
  const raw = 50 + (pctDiff / halfSpan) * 50;
  return Math.max(3, Math.min(97, raw));
}

// ── Main export ───────────────────────────────────────────────────────────────

export function analyzeBenchmark(
  companyValue: number,
  industryAvg:  number,
  metricName:   string,
  higherIsBetter: boolean,
): BenchmarkResult {
  const category = detectCategory(metricName);

  // Percentage difference — positive means company > industry.
  const pctDiff = industryAvg !== 0
    ? ((companyValue - industryAvg) / Math.abs(industryAvg)) * 100
    : 0;

  // "Better" means outperforming according to the sign convention.
  const companyIsBetter = higherIsBetter ? pctDiff > 0 : pctDiff < 0;
  const abs = Math.abs(pctDiff);

  let level: SentimentLevel;
  if (abs < 5) {
    level = 'inline';
  } else if (companyIsBetter) {
    level = abs >= 20 ? 'outperform_strong' : 'outperform_mild';
  } else {
    level = abs >= 20 ? 'underperform_strong' : 'underperform_mild';
  }

  // Icon choice
  let iconName: IconName;
  if (category === 'risk') {
    iconName = level.startsWith('outperform')   ? 'ShieldCheck'
             : level.startsWith('underperform') ? 'ShieldAlert'
             : 'Minus';
  } else if (level === 'outperform_strong')   { iconName = 'TrendingUp'; }
  else if (level === 'outperform_mild')        { iconName = 'ArrowUpRight'; }
  else if (level === 'underperform_strong')    { iconName = 'TrendingDown'; }
  else if (level === 'underperform_mild')      { iconName = 'ArrowDownRight'; }
  else                                          { iconName = 'Minus'; }

  const companyPos = pctDiffToBarPos(pctDiff);

  return {
    level,
    pctDiff,
    companyPos,
    industryPos: 50,
    label:       LABELS[category][level],
    iconName,
    category,
    ...PALETTE[level],
  };
}

// ── Convenience: format a raw number for display ──────────────────────────────

export function formatMetricValue(value: number, metricName?: string): string {
  const n = (metricName ?? '').toLowerCase();
  if (n.includes('%') || /margin|growth|yield|pct/.test(n)) {
    return `${value.toFixed(1)}%`;
  }
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000)     return `${(value / 1_000).toFixed(1)}K`;
  if (abs >= 100)       return value.toFixed(1);
  return value.toFixed(2);
}
