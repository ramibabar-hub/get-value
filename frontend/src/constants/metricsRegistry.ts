/**
 * metricsRegistry.ts
 *
 * Catalog of all metric sections that can be shown/hidden in Financials
 * and Value Drivers tabs.
 *
 * Senior Partner Rule: pinned sections can never be hidden.
 * The vs. Industry column is always shown for applicable rows.
 */

export type MetricImpact   = "high" | "medium" | "low";
export type MetricTab      = "financials" | "value_drivers";
export type MetricCategory =
  | "Core Statements"
  | "Valuation"
  | "Capital Quality"
  | "Profitability & Returns"
  | "Liquidity & Safety"
  | "Income & Dividends"
  | "Operating Efficiency"
  | "Growth"
  | "Equity Research";

export interface MetricSection {
  id:          string;          // unique ID, maps to ExtTable property or group title
  label:       string;          // display name
  tab:         MetricTab;
  category:    MetricCategory;
  pinned:      boolean;         // if true, cannot be hidden
  impact:      MetricImpact;    // High=mission-critical, Medium=supplemental, Low=niche
  description: string;          // tooltip / catalog description
}

// ── Core Financial Statements (always pinned) ────────────────────────────────
const CORE_STATEMENTS: MetricSection[] = [
  {
    id: "income_statement",
    label: "Income Statement",
    tab: "financials",
    category: "Core Statements",
    pinned: true,
    impact: "high",
    description: "Revenue, gross profit, EBITDA, operating income, net income, and EPS across TTM + 10 periods.",
  },
  {
    id: "balance_sheet",
    label: "Balance Sheet",
    tab: "financials",
    category: "Core Statements",
    pinned: true,
    impact: "high",
    description: "Assets, liabilities, equity, cash, and debt — the foundation of financial health assessment.",
  },
  {
    id: "cash_flow",
    label: "Cash Flow Statement",
    tab: "financials",
    category: "Core Statements",
    pinned: true,
    impact: "high",
    description: "Operating, investing, and financing cash flows. Free cash flow and CapEx intensity.",
  },
  {
    id: "debt_schedule",
    label: "Debt Schedule",
    tab: "financials",
    category: "Core Statements",
    pinned: true,
    impact: "high",
    description: "Long-term and short-term debt decomposition, net debt, and interest expense trend.",
  },
];

// ── Extended Metric Sections (toggleable) ────────────────────────────────────
const EXTENDED_SECTIONS: MetricSection[] = [
  {
    id: "market_valuation",
    label: "Market & Valuation",
    tab: "financials",
    category: "Valuation",
    pinned: false,
    impact: "high",
    description: "P/E, EV/EBITDA, P/FCF, P/B, EV/Revenue. The primary lens for relative and intrinsic value assessment.",
  },
  {
    id: "capital_structure",
    label: "Capital Structure",
    tab: "financials",
    category: "Capital Quality",
    pinned: false,
    impact: "high",
    description: "Debt/Equity, Net Debt/EBITDA, Interest Coverage. Measures financial leverage and solvency risk.",
  },
  {
    id: "profitability",
    label: "Profitability",
    tab: "financials",
    category: "Profitability & Returns",
    pinned: false,
    impact: "high",
    description: "Gross Margin, EBITDA Margin, Net Margin, Operating Margin. The quality of earnings.",
  },
  {
    id: "returns",
    label: "Returns",
    tab: "financials",
    category: "Profitability & Returns",
    pinned: false,
    impact: "high",
    description: "ROE, ROA, ROIC — the efficiency of capital deployment. Warren Buffett's preferred quality screen.",
  },
  {
    id: "liquidity",
    label: "Liquidity",
    tab: "financials",
    category: "Liquidity & Safety",
    pinned: false,
    impact: "medium",
    description: "Current Ratio, Quick Ratio, Cash Ratio. Measures ability to meet short-term obligations.",
  },
  {
    id: "dividends",
    label: "Dividends",
    tab: "financials",
    category: "Income & Dividends",
    pinned: false,
    impact: "medium",
    description: "Dividend Yield, Payout Ratio, Dividends Per Share history. Essential for income investors.",
  },
  {
    id: "efficiency",
    label: "Efficiency",
    tab: "financials",
    category: "Operating Efficiency",
    pinned: false,
    impact: "medium",
    description: "Asset Turnover, Inventory Days, Receivables Days. Operational excellence metrics.",
  },
];

// ── Value Drivers / Insights Groups (toggleable) ─────────────────────────────
// These IDs must match the group.title strings returned by /api/insights
const VALUE_DRIVER_SECTIONS: MetricSection[] = [
  {
    id: "growth_cagr",
    label: "Growth (CAGR)",
    tab: "value_drivers",
    category: "Growth",
    pinned: false,
    impact: "high",
    description: "3yr, 5yr, 10yr compound annual growth rates for Revenue, EBITDA, EPS, and FCF.",
  },
  {
    id: "valuation_multiples",
    label: "Valuation Multiples",
    tab: "value_drivers",
    category: "Valuation",
    pinned: false,
    impact: "high",
    description: "Historical average P/E, EV/EBITDA, P/FCF, P/B across TTM, 5yr, and 10yr periods.",
  },
  {
    id: "profitability_vd",
    label: "Profitability",
    tab: "value_drivers",
    category: "Profitability & Returns",
    pinned: false,
    impact: "high",
    description: "Gross, EBITDA, Operating, and Net Margins — trend analysis across periods.",
  },
  {
    id: "returns_vd",
    label: "Returns",
    tab: "value_drivers",
    category: "Profitability & Returns",
    pinned: false,
    impact: "high",
    description: "ROE, ROA, ROIC — efficiency of capital over time. The primary quality screen.",
  },
  {
    id: "liquidity_vd",
    label: "Liquidity",
    tab: "value_drivers",
    category: "Liquidity & Safety",
    pinned: false,
    impact: "medium",
    description: "Current and Quick ratio trends. Short-term financial health.",
  },
  {
    id: "dividends_vd",
    label: "Dividends",
    tab: "value_drivers",
    category: "Income & Dividends",
    pinned: false,
    impact: "medium",
    description: "Dividend yield and payout ratio history. Dividend growth trajectory.",
  },
  {
    id: "efficiency_vd",
    label: "Efficiency",
    tab: "value_drivers",
    category: "Operating Efficiency",
    pinned: false,
    impact: "medium",
    description: "Asset turnover, inventory days, receivables collection. Operational quality.",
  },
];

export const METRICS_REGISTRY: MetricSection[] = [
  ...CORE_STATEMENTS,
  ...EXTENDED_SECTIONS,
  ...VALUE_DRIVER_SECTIONS,
];

export const FINANCIALS_SECTIONS         = METRICS_REGISTRY.filter((m) => m.tab === "financials");
export const VALUE_DRIVER_SECTIONS_LIST  = METRICS_REGISTRY.filter((m) => m.tab === "value_drivers");

// Ordered list of ExtTable section IDs (matches FinancialsExtendedData properties)
export const EXT_SECTION_IDS = [
  "market_valuation",
  "capital_structure",
  "profitability",
  "returns",
  "liquidity",
  "dividends",
  "efficiency",
] as const;

export type ExtSectionId = typeof EXT_SECTION_IDS[number];
