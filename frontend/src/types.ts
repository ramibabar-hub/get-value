// ── Shared ────────────────────────────────────────────────────────────────────

export type Scale  = "K" | "MM" | "B";
export type Period = "annual" | "quarterly";

// ── Normalized PE ─────────────────────────────────────────────────────────────

export interface NormalizedPEResult {
  ticker: string;
  data_source: string;

  eps_ttm: number | null;
  eps_3yr: number | string | null;
  eps_5yr: number | string | null;
  eps_10yr: number | string | null;
  hist_pe_10yr: number | null;
  price_now: number | null;
  wacc: number;
  growth_default: number;

  growth_pct: number;
  years: number;
  disc_pct: number;
  mos_pct: number;
  use_wacc: boolean;

  future_eps: number | null;
  discounted_eps: number | null;
  pe_a: number;
  pe_b: number | null;
  pe_c: number | null;
  fair_value: number | null;
  buy_price: number | null;
  on_sale: boolean | null;
  upside_to_fv: number | null;
  upside_to_buy: number | null;
}

// ── Overview ──────────────────────────────────────────────────────────────────

export interface MetricCell {
  label: string;
  value: string;
  color: string | null;
}

export interface OverviewData {
  ticker: string;
  company_name: string;
  logo_url: string;
  exchange: string;
  sector: string;
  industry: string;
  currency: string;
  country: string;
  flag: string;           // emoji e.g. "🇺🇸"
  description: string;
  price: number;
  price_change_pct: number;
  data_source: string;
  metrics: MetricCell[];  // 15 cells for the 5-col x 3-row grid
}

// ── Financials ────────────────────────────────────────────────────────────────

export interface FinancialRow {
  label: string;
  [col: string]: number | null | string;
}

export interface FinancialsData {
  ticker: string;
  period: Period;
  currency: string;
  columns: string[];          // e.g. ["TTM", "2024", "2023", ...]
  income_statement: FinancialRow[];
  balance_sheet: FinancialRow[];
  cash_flow: FinancialRow[];
  debt: FinancialRow[];
}

// ── WACC ──────────────────────────────────────────────────────────────────────

export interface WaccData {
  ticker: string;
  wacc: number | null;
  rf: number;
  beta: number | null;
  equity_weight: number | null;
  debt_weight: number | null;
  cost_of_equity: number | null;
  cost_of_debt_pre_tax: number | null;
  cost_of_debt_after_tax: number | null;
  tax_rate: number | null;
  int_coverage: number | null;
  spread: number | null;
}

// ── Insights ──────────────────────────────────────────────────────────────────

export interface InsightsRow {
  label: string;
  [col: string]: number | string | null;   // "TTM", "Avg. 5yr", "3yr", etc.
}

export interface InsightsGroup {
  title: string;
  cols: string[];     // e.g. ["TTM","Avg. 5yr","Avg. 10yr"] or ["3yr","5yr","10yr"]
  is_pct: boolean;    // true  → multiply by 100, show as "%"
  rows: InsightsRow[];
}

export interface InsightsData {
  ticker: string;
  groups: InsightsGroup[];
}
