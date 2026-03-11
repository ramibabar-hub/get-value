/**
 * FinancialDataService.ts
 *
 * Frontend service module for the 4-provider cascade data API.
 *
 * All financial data requests flow through the FastAPI backend, which runs
 * the cascade logic (FMP → EODHD → Alpha Vantage → Finnhub) server-side.
 * API keys never touch the browser.
 *
 * Console logging tracks which provider fulfilled each request so you can
 * diagnose fallback behaviour during development.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * Usage
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   // Fetch full profile (4-provider cascade)
 *   const profile = await FinancialDataService.fetchProfile("AAPL");
 *   console.log(profile.company_name, "via", profile.data_source);
 *
 *   // Lightweight live quote (FMP → Finnhub)
 *   const quote = await FinancialDataService.fetchQuote("AAPL");
 *
 *   // React hook — wraps fetchProfile with loading/error state
 *   const { data, loading, error } = useCascadeProfile("AAPL");
 */

import type {
  CascadeProfile,
  CascadeQuote,
  CascadeProvider,
} from "../types";

// ── Provider display labels (for console + UI) ────────────────────────────────

const PROVIDER_LABELS: Record<CascadeProvider, string> = {
  fmp:           "Financial Modeling Prep",
  eodhd:         "EOD Historical Data",
  alpha_vantage: "Alpha Vantage",
  finnhub:       "Finnhub",
  none:          "No provider",
};

// ── Internal fetch helper ─────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

// ── Cascade logging helper ────────────────────────────────────────────────────

function logCascadeResult(
  label: string,
  ticker: string,
  source: CascadeProvider,
  tried: CascadeProvider[],
): void {
  const providerLabel = PROVIDER_LABELS[source] ?? source;
  const chain = tried.map(p => PROVIDER_LABELS[p] ?? p).join(" → ");

  if (source === "none") {
    console.warn(
      `[FinancialDataService] ${label} ${ticker}: all providers failed (tried: ${chain})`,
    );
  } else {
    const fallbacks = tried.length > 1
      ? ` (after ${tried.length - 1} fallback${tried.length > 2 ? "s" : ""})`
      : "";
    console.info(
      `[FinancialDataService] ${label} ${ticker}: fulfilled by ${providerLabel}${fallbacks}`,
      tried.length > 1 ? { providerChain: chain } : "",
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Core service functions
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fetch a full company profile using the 4-provider cascade.
 *
 * Priority: FMP → EODHD → Alpha Vantage → Finnhub
 *
 * @param ticker  e.g. "AAPL", "NICE.TA", "BMW.DE"
 */
export async function fetchProfile(ticker: string): Promise<CascadeProfile> {
  const t = ticker.trim().toUpperCase();
  const data = await apiFetch<CascadeProfile>(
    `/api/cascade/profile/${encodeURIComponent(t)}`,
  );
  logCascadeResult("profile", t, data.data_source, data.providers_tried);
  return data;
}

/**
 * Fetch a lightweight live quote (price + % change).
 *
 * Priority: FMP → Finnhub
 *
 * @param ticker  e.g. "AAPL"
 */
export async function fetchQuote(ticker: string): Promise<CascadeQuote> {
  const t = ticker.trim().toUpperCase();
  const data = await apiFetch<CascadeQuote>(
    `/api/cascade/quote/${encodeURIComponent(t)}`,
  );
  console.info(
    `[FinancialDataService] quote ${t}: $${data.price ?? "N/A"} via ${PROVIDER_LABELS[data.data_source] ?? data.data_source}`,
  );
  return data;
}

// ─────────────────────────────────────────────────────────────────────────────
//  React hooks
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect } from "react";

export interface CascadeState<T> {
  data:    T | null;
  loading: boolean;
  error:   string | null;
}

/**
 * React hook — fetches a full cascade profile; re-fetches when ticker changes.
 *
 *   const { data, loading, error } = useCascadeProfile("AAPL");
 */
export function useCascadeProfile(ticker: string): CascadeState<CascadeProfile> {
  const [state, setState] = useState<CascadeState<CascadeProfile>>({
    data: null, loading: true, error: null,
  });

  useEffect(() => {
    if (!ticker) return;
    setState({ data: null, loading: true, error: null });
    fetchProfile(ticker)
      .then(data  => setState({ data, loading: false, error: null }))
      .catch(err  => setState({ data: null, loading: false, error: String(err) }));
  }, [ticker]);

  return state;
}

/**
 * React hook — fetches a lightweight quote; re-fetches when ticker changes.
 *
 *   const { data, loading, error } = useCascadeQuote("AAPL");
 */
export function useCascadeQuote(ticker: string): CascadeState<CascadeQuote> {
  const [state, setState] = useState<CascadeState<CascadeQuote>>({
    data: null, loading: true, error: null,
  });

  useEffect(() => {
    if (!ticker) return;
    setState({ data: null, loading: true, error: null });
    fetchQuote(ticker)
      .then(data  => setState({ data, loading: false, error: null }))
      .catch(err  => setState({ data: null, loading: false, error: String(err) }));
  }, [ticker]);

  return state;
}

// ── Default export (namespace style) ─────────────────────────────────────────

const FinancialDataService = {
  fetchProfile,
  fetchQuote,
  useCascadeProfile,
  useCascadeQuote,
  PROVIDER_LABELS,
} as const;

export default FinancialDataService;
