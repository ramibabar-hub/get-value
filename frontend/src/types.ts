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

// ── Financials Extended ───────────────────────────────────────────────────────

export type FmtType = "money" | "pct" | "ratio" | "days" | "int";

export interface ExtRow {
  label: string;
  fmt: FmtType;
  [col: string]: number | null | string;
}

export interface FinancialsExtendedData {
  ticker: string;
  period: Period;
  columns: string[];
  market_valuation: ExtRow[];
  capital_structure: ExtRow[];
  profitability: ExtRow[];
  returns: ExtRow[];
  liquidity: ExtRow[];
  dividends: ExtRow[];
  efficiency: ExtRow[];
}

// ── CF + IRR ──────────────────────────────────────────────────────────────────

export interface CfIrrCheckItem {
  label: string;
  threshold: string;
  value: number | null;
  display: string;
  passed: boolean | null;
}

export interface CfIrrData {
  ticker: string;
  base_year: number;
  price_now: number | null;
  wacc: number;
  wacc_computed: number;
  adj_ps_ttm: number | null;
  base_ebitda: number | null;
  net_debt_ttm: number;
  sh_ttm: number | null;
  exit_mult: number;
  exit_yield: number;
  mos_pct: number;
  // Historical tables (rows keyed by column names)
  ebt_hist: Record<string, string>[];
  ebt_ttm: Record<string, string>;
  ebt_avg: Record<string, string>;
  ebt_cagr: Record<string, string>;
  fcf_hist: Record<string, string>[];
  fcf_ttm: Record<string, string>;
  fcf_avg: Record<string, string>;
  fcf_cagr: Record<string, string>;
  // Forecasts
  ebt_forecast: { Year: string; "Est. Growth Rate (%)": number; "Est. EBITDA ($MM)": number }[];
  fcf_forecast: { Year: string; "Est. Growth Rate (%)": number; "Est. Adj. FCF/s": number }[];
  ebt_growth_rates: number[];
  fcf_growth_rates: number[];
  // Results
  ebitda_price: number | null;
  fcf_price: number | null;
  avg_target: number | null;
  fair_value: number | null;
  buy_price: number | null;
  on_sale: boolean | null;
  irr: number | null;
  irr_sensitivity: { row_labels: string[]; col_labels: string[]; matrix: (number | null)[][] };
  checklist: CfIrrCheckItem[];
  ev_ebt_ttm: number | null;
  ebt_avg_mult: number | null;
}
