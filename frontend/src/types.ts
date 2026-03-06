/** Shape returned by GET /api/normalized-pe/{ticker} */
export interface NormalizedPEResult {
  ticker: string;
  data_source: string;   // "fmp" | "eodhd" | "fmp_fallback" | "eodhd_fallback"

  // source data
  eps_ttm: number | null;
  eps_3yr: number | string | null;
  eps_5yr: number | string | null;
  eps_10yr: number | string | null;
  hist_pe_10yr: number | null;
  price_now: number | null;
  wacc: number;
  growth_default: number;

  // resolved inputs
  growth_pct: number;
  years: number;
  disc_pct: number;
  mos_pct: number;
  use_wacc: boolean;

  // computed
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
