/**
 * industryBenchmarks.ts
 *
 * Static broad-market benchmark averages for all labelled metrics in the
 * getValue ExtTable and InsightsTab. Values are in the SAME storage unit as
 * the corresponding ExtRow / InsightsRow cell value:
 *   - fmt "pct"   → decimal  (0.16 = 16 %)
 *   - fmt "ratio" → raw number  (21.5 = 21.5×)
 *   - fmt "days"  → raw days   (45 = 45 days)
 *   - is_pct true → decimal    (0.42 = 42 %)
 *
 * Source: broad S&P 500 / global equity trailing averages (approximate).
 * Keys match the exact label strings produced by financials_tab.py and
 * agents/core_agent.py so no fuzzy-matching is needed at call time.
 */

export interface Benchmark {
  avg: number;
  higherIsBetter: boolean;
}

// ── Primary lookup table ──────────────────────────────────────────────────────

const TABLE: Record<string, Benchmark> = {
  // ── Market & Valuation (format: ratio unless noted) ───────────────────────
  "P/E":                                   { avg: 21.5,  higherIsBetter: false },
  "P/S":                                   { avg: 2.5,   higherIsBetter: false },
  "P/B":                                   { avg: 3.8,   higherIsBetter: false },
  "P/Adj. FCF":                            { avg: 22.0,  higherIsBetter: false },
  "P/FCF":                                 { avg: 22.0,  higherIsBetter: false },
  "EV / EBITDA":                           { avg: 13.5,  higherIsBetter: false },
  "EV / Adj. FCF":                         { avg: 20.0,  higherIsBetter: false },
  "PEG":                                   { avg: 1.5,   higherIsBetter: false },
  "Earnings Yield":                        { avg: 0.046, higherIsBetter: true  }, // 4.6% (≈ 1/21.5)
  "Buyback Yield":                         { avg: 0.020, higherIsBetter: true  }, // 2.0%  pct
  "Total shareholder yield":               { avg: 0.035, higherIsBetter: true  }, // 3.5%  pct
  "Dilution":                              { avg: 0.010, higherIsBetter: false }, // 1.0%  pct — lower is better
  "5 Yr Beta":                             { avg: 1.0,   higherIsBetter: false }, // market = 1.0; lower = less volatile
  "Div.&Repurch./ Adj. FCF":               { avg: 0.50,  higherIsBetter: true  }, // 50 % of FCF returned
  "Revenue / Employee":                    { avg: 350_000, higherIsBetter: true },
  "Net Income / Employee":                 { avg: 42_000,  higherIsBetter: true },

  // ── Capital Structure (format: ratio) ─────────────────────────────────────
  "Debt / Equity":                         { avg: 1.50,  higherIsBetter: false },
  "Debt / EBITDA":                         { avg: 2.20,  higherIsBetter: false },
  "Net Debt / EBITDA":                     { avg: 1.80,  higherIsBetter: false },
  "Debt / Adj. FCF":                       { avg: 3.00,  higherIsBetter: false },
  "Interest Coverage (EBIT/Interest)":     { avg: 6.50,  higherIsBetter: true  },
  "SBC / FCF":                             { avg: 0.08,  higherIsBetter: false }, // 8 % as decimal ratio

  // ── Returns (format: pct → stored as decimal) ─────────────────────────────
  "ROIC":                                  { avg: 0.10,  higherIsBetter: true  }, // 10 %
  "FCF ROC":                               { avg: 0.08,  higherIsBetter: true  }, // 8 %
  "ROE":                                   { avg: 0.16,  higherIsBetter: true  }, // 16 %
  "ROA":                                   { avg: 0.06,  higherIsBetter: true  }, // 6 %
  "ROCE":                                  { avg: 0.11,  higherIsBetter: true  }, // 11 %

  // ── Liquidity (format: ratio) ─────────────────────────────────────────────
  "Current Ratio":                         { avg: 1.80,  higherIsBetter: true  },
  "Cash to Debt":                          { avg: 0.40,  higherIsBetter: true  },

  // ── Dividends (format: pct → decimal, except DPS which is skipped) ────────
  "Yield":                                 { avg: 0.016, higherIsBetter: true  }, // 1.6 %
  "Payout":                                { avg: 0.35,  higherIsBetter: false }, // 35 % — retaining more is better

  // ── Efficiency (format: ratio or days) ────────────────────────────────────
  "Receivable turnover":                   { avg: 8.0,   higherIsBetter: true  },
  "Average receivables collection day":    { avg: 45.0,  higherIsBetter: false },
  "Inventory turnover":                    { avg: 5.5,   higherIsBetter: true  },
  "Average days inventory in stock":       { avg: 65.0,  higherIsBetter: false },
  "Payables turnover":                     { avg: 6.0,   higherIsBetter: false }, // lower = using supplier credit longer
  "Average days payables outstanding":     { avg: 60.0,  higherIsBetter: true  }, // longer = better working capital
  "Operating cycle":                       { avg: 110.0, higherIsBetter: false },
  "Cash cycle":                            { avg: 50.0,  higherIsBetter: false },
  "Working capital turnover":              { avg: 4.0,   higherIsBetter: true  },
  "Fixed asset turnover":                  { avg: 2.50,  higherIsBetter: true  },
  "Asset turnover":                        { avg: 0.65,  higherIsBetter: true  },
  "SBC/ FCF":                              { avg: 0.08,  higherIsBetter: false }, // alt label from InsightsTab

  // ── InsightsTab — Valuation Multiples (stored as raw ratios) ─────────────
  // same as market valuation above — aliases for InsightsTab label spelling

  // ── InsightsTab — Profitability (is_pct: true → decimal) ─────────────────
  "Gross profit":                          { avg: 0.42,  higherIsBetter: true  }, // 42 %
  "EBIT":                                  { avg: 0.12,  higherIsBetter: true  }, // 12 %  (as margin)
  "EBITDA":                                { avg: 0.17,  higherIsBetter: true  }, // 17 %  (as margin)
  "Net Income":                            { avg: 0.085, higherIsBetter: true  }, // 8.5 % (as margin)
  "FCF":                                   { avg: 0.10,  higherIsBetter: true  }, // 10 %  (as margin)

  // ── InsightsTab — Growth CAGR (is_pct: true → decimal) ───────────────────
  "Revenues":                              { avg: 0.08,  higherIsBetter: true  },
  "Operating income":                      { avg: 0.10,  higherIsBetter: true  },
  // EBITDA / EPS / Adj. FCF share aliases with the profitability entries above
  "EPS":                                   { avg: 0.10,  higherIsBetter: true  },
  "Adj. FCF":                              { avg: 0.10,  higherIsBetter: true  },
  "Shares outs.":                          { avg: -0.01, higherIsBetter: false }, // buybacks (negative = fewer shares)

  // ── REIT-specific ─────────────────────────────────────────────────────────
  "P/FFO":                                 { avg: 17.0,  higherIsBetter: false },
  "FFO Payout Ratio":                      { avg: 0.70,  higherIsBetter: false }, // 70 % pct
  "FFO / Total Revenue (%)":               { avg: 0.35,  higherIsBetter: true  }, // 35 % pct
};

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Look up the industry benchmark for a metric label.
 * Returns null if no benchmark is defined (signals UI to skip the column).
 */
export function lookupBenchmark(label: string): Benchmark | null {
  // Exact match first (covers the vast majority of cases)
  const exact = TABLE[label];
  if (exact !== undefined) return exact;

  // Normalised fallback — strip trailing whitespace / parentheses variations
  const norm = label.trim();
  for (const [key, val] of Object.entries(TABLE)) {
    if (key.toLowerCase() === norm.toLowerCase()) return val;
  }

  return null;
}
