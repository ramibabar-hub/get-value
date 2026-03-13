// ── Shared ────────────────────────────────────────────────────────────────────

export type Scale  = "K" | "MM" | "B";
export type Period = "annual" | "quarterly";

// ── Cascade data service ───────────────────────────────────────────────────────

/** Which provider supplied the data */
export type CascadeProvider = "fmp" | "eodhd" | "alpha_vantage" | "finnhub" | "none";

/** Normalised company profile returned by GET /api/cascade/profile/{ticker} */
export interface CascadeProfile {
  ticker:          string;
  company_name:    string;
  exchange:        string;
  sector:          string;
  industry:        string;
  currency:        string;
  country:         string;
  description:     string;
  price:           number | null;
  market_cap:      number | null;
  pe_ratio:        number | null;
  logo_url:        string;
  website:         string;
  data_source:     CascadeProvider;
  providers_tried: CascadeProvider[];
  /** Set only when every provider failed */
  error?:          string;
}

/** Lightweight price-only result from GET /api/cascade/quote/{ticker} */
export interface CascadeQuote {
  ticker:      string;
  price:       number | null;
  change_pct:  number | null;
  data_source: CascadeProvider;
}

// ── Gemini qualitative analysis ───────────────────────────────────────────────

export type GeminiAnalysisType = "summary" | "moat" | "risks" | "valuation";

/** Context sent to POST /api/gemini/analyze/{ticker} */
export interface GeminiAnalysisRequest {
  company_name?: string;
  sector?:       string;
  industry?:     string;
  country?:      string;
  market_cap?:   number;
  pe_ratio?:     number;
  description?:  string;
}

/** Response from POST /api/gemini/analyze/{ticker} */
export interface GeminiAnalysis {
  ticker:        string;
  analysis_type: GeminiAnalysisType;
  text:          string;
  model:         string;
  error:         string | null;
}

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

// ── Segments ──────────────────────────────────────────────────────────────────

export interface Segment {
  name: string;
  revenue_by_year: Record<string, number | null>;
  operating_income_by_year?: Record<string, number | null>;
  assets_by_year?: Record<string, number | null>;
}

export interface SegmentsData {
  ticker: string;
  years: string[];      // newest-first, e.g. ["2024","2023","2022","2021","2020"]
  segments: Segment[];  // sorted largest revenue first
}

// ── DDM  ──────────────────────────────────────────────────────────────────────

export interface DdmHistRow {
  year:       string;
  divs_paid:  number | null;  // raw dollars, negative (cash outflow)
  shares:     number | null;  // raw share count
  dps:        number | null;  // dollars per share
  net_income: number | null;  // raw dollars
  payout_pct: number | null;  // decimal fraction (0.35 = 35 %)
}

export interface DdmData {
  ticker:             string;
  currency:           string;
  price_now:          number | null;
  hist:               DdmHistRow[];  // oldest year first, no TTM
  ttm:                DdmHistRow;
  dps_cagr:           number | null; // decimal (0.082 = 8.2 %)
  dps_cagr_years:     number;
  wacc_computed:      number;        // decimal
  wacc:               number;        // decimal (= override or computed)
  default_g_terminal: number;        // decimal
  has_dividend:       boolean;
}

// ── CF + IRR Special (TBV + EPS model) ───────────────────────────────────────

export interface CfIrrSpecialData {
  ticker:      string;
  base_year:   number;
  price_now:   number | null;
  base_tbv_ps: number | null;
  base_eps:    number | null;
  wacc:        number;
  wacc_computed: number;
  exit_ptbv:   number;
  exit_pe:     number;
  tbv_weight:  number;
  mos_pct:     number;
  tbv_growth_rates: number[];
  eps_growth_rates: number[];
  default_tbv_rate: number;
  default_eps_rate: number;
  // Historical table (all values pre-formatted as strings)
  hist:      Record<string, string>[];
  hist_ttm:  Record<string, string>;
  hist_avg:  Record<string, string>;
  hist_cagr: Record<string, string>;
  // Forecasts (numeric values)
  tbv_forecast: { Year: string; "Est. Growth Rate (%)": number; "Est. TBV/s": number }[];
  eps_forecast: { Year: string; "Est. Growth Rate (%)": number; "Est. EPS":   number }[];
  // Results
  tbv_terminal: number | null;
  eps_terminal: number | null;
  avg_target:   number | null;
  fair_value:   number | null;
  buy_price:    number | null;
  on_sale:      boolean | null;
  irr:          number | null;
  checklist:    CfIrrCheckItem[];
  // CAGRs
  assets_cagr:  number | null;
  tbv_ps_cagr:  number | null;
  eps_cagr:     number | null;
  margin_avg:   number | null;
}

// ── Industry Multiple ─────────────────────────────────────────────────────────

export interface IMultipleHistRow {
  year:         string;
  price:        number | null;
  price_growth: number | null;
  eps:          number | null;
  eps_growth:   number | null;
  ebitda_mm:    number | null;
  revenue_mm:   number | null;
  fcf_mm:       number | null;
  pe:           number | null;
  ev_ebitda:    number | null;
  ps:           number | null;
  p_fcf:        number | null;
}

export interface IMultipleData {
  ticker:             string;
  sector:             string;
  industry:           string;
  currency:           string;
  hist:               IMultipleHistRow[];
  ttm:                IMultipleHistRow;
  avg_10yr:           IMultipleHistRow;
  avg_eps:            number | null;
  avg_ebitda_mm:      number | null;
  avg_ebitda_raw:     number | null;
  net_debt_mm:        number | null;
  net_debt_raw:       number | null;
  shares_outstanding: number | null;
  price_now:          number | null;
}

// ── Piotroski F-Score ─────────────────────────────────────────────────────────

export interface PiotroskiData {
  ticker:   string;
  currency: string;

  // Raw inputs
  net_income_ttm:           number | null;
  net_income_prev:          number | null;
  total_assets_ttm:         number | null;
  total_assets_prev:        number | null;
  total_assets_2prev:       number | null;
  ocf_ttm:                  number | null;
  ocf_prev:                 number | null;
  ltd_ttm:                  number | null;
  ltd_prev:                 number | null;
  current_assets_ttm:       number | null;
  current_assets_prev:      number | null;
  current_liabilities_ttm:  number | null;
  current_liabilities_prev: number | null;
  shares_ttm:               number | null;
  shares_prev:              number | null;
  gross_profit_ttm:         number | null;
  gross_profit_prev:        number | null;
  revenue_ttm:              number | null;
  revenue_prev:             number | null;

  // Computed ratios
  roa_ttm:             number | null;
  roa_prev:            number | null;
  ocf_ratio_ttm:       number | null;
  ocf_ratio_prev:      number | null;
  leverage_ttm:        number | null;
  leverage_prev:       number | null;
  current_ratio_ttm:   number | null;
  current_ratio_prev:  number | null;
  gross_margin_ttm:    number | null;
  gross_margin_prev:   number | null;
  asset_turnover_ttm:  number | null;
  asset_turnover_prev: number | null;

  // 9-point scores (0 or 1)
  f1_positive_roa:          number;
  f2_positive_ocf:          number;
  f3_higher_roa:            number;
  f4_accruals:              number;
  f5_lower_leverage:        number;
  f6_higher_current_ratio:  number;
  f7_less_shares:           number;
  f8_higher_gross_margin:   number;
  f9_higher_asset_turnover: number;

  total_score: number;
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

// ── Company Overview: Price Chart ──────────────────────────────────────────────
export type PriceRange = "1D" | "5D" | "1M" | "6M" | "YTD" | "1Y" | "5Y" | "10Y";

export interface PricePoint {
  date:   string;
  price:  number;
  volume: number | null;
}

export interface PriceHistoryData {
  ticker: string;
  range:  string;
  points: PricePoint[];
}

// ── Company Overview: News & Insights ─────────────────────────────────────────
export interface NewsInsight {
  headline:             string;
  date:                 string;
  summary:              string;
  model_impact:         string;
  educational_insight?: string;
  url?:                 string;
}

export interface NewsInsightsData {
  ticker:             string;
  executive_summary?: string;
  insights:           NewsInsight[];
}

// ── Ownership Structure ───────────────────────────────────────────────────────
export interface OwnershipData {
  ticker:             string;
  insider_pct:        number;   // real — from SEC via FMP shares-float
  institutional_pct:  number;   // AI estimate
  retail_pct:         number;   // derived
  power_dynamics:     string;   // Claude 2-sentence analysis
}


// ── Condensed Description ─────────────────────────────────────────────────────
export interface DescriptionSummary {
  ticker:  string;
  summary: string;
}

// ── Grok Sentiment ────────────────────────────────────────────────────────────
export interface GrokSentiment {
  ticker:       string;
  score:        number | null;
  label:        "Bullish" | "Neutral" | "Bearish" | "Unavailable";
  reason:       string;
  source:       string;
  cached_until: string | null;
  error:        string | null;
}

// ── Filing Audit (Gemini 10-K Auditor) ────────────────────────────────────────
export interface FilingAudit {
  ticker:       string;
  filing_url:   string | null;
  summary:      string;
  risk_factors: string[];
  red_flags:    string[];
  moat_signals: string[];
  model:        string;
  error:        string | null;
}

// ── Analyst Consensus (FMP) ───────────────────────────────────────────────────
export interface AnalystConsensus {
  ticker:            string;
  num_analysts:      number;
  buy:               number;
  hold:              number;
  sell:              number;
  consensus:         "Buy" | "Hold" | "Sell" | "N/A";
  price_target_avg:  number | null;
  price_target_high: number | null;
  price_target_low:  number | null;
  error?:            string;
}
