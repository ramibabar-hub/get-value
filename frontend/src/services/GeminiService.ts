/**
 * GeminiService.ts
 *
 * Frontend client for Gemini-powered qualitative financial analysis.
 *
 * All requests are proxied through the FastAPI backend (/api/gemini/analyze).
 * The Gemini API key stays server-side and never reaches the browser.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * Usage
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   // One-shot analysis
 *   const result = await GeminiService.analyze("AAPL", profile, "summary");
 *
 *   // React hook with loading state
 *   const { data, loading, error } = useGeminiAnalysis("AAPL", profile, "moat");
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * Analysis types
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   "summary"   — 3–5 sentence investment overview (default)
 *   "moat"      — economic moat: Wide / Narrow / None + explanation
 *   "risks"     — top 3 material investor risks
 *   "valuation" — valuation commentary (cheap / fair / expensive)
 */

import { useState, useEffect } from "react";
import type {
  GeminiAnalysis,
  GeminiAnalysisRequest,
  GeminiAnalysisType,
  CascadeProfile,
} from "../types";

// ─────────────────────────────────────────────────────────────────────────────
//  Internal helpers
// ─────────────────────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  body: unknown,
): Promise<T> {
  const r = await fetch(path, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

/**
 * Extract the GeminiAnalysisRequest context from a CascadeProfile.
 * Passing profile context gives Gemini much richer analytical material.
 */
function profileToContext(profile: Partial<CascadeProfile>): GeminiAnalysisRequest {
  return {
    company_name: profile.company_name  || undefined,
    sector:       profile.sector        || undefined,
    industry:     profile.industry      || undefined,
    country:      profile.country       || undefined,
    market_cap:   profile.market_cap    ?? undefined,
    pe_ratio:     profile.pe_ratio      ?? undefined,
    description:  profile.description   || undefined,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
//  Core service function
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Request a Gemini qualitative analysis for a company.
 *
 * @param ticker        e.g. "AAPL"
 * @param context       Company context — use a CascadeProfile or a plain object
 *                      with {company_name, sector, industry, market_cap, …}
 * @param analysisType  "summary" | "moat" | "risks" | "valuation"
 */
export async function analyze(
  ticker: string,
  context: Partial<CascadeProfile> | GeminiAnalysisRequest,
  analysisType: GeminiAnalysisType = "summary",
): Promise<GeminiAnalysis> {
  const t = ticker.trim().toUpperCase();

  // Accept either a full CascadeProfile or a plain context dict
  const body: GeminiAnalysisRequest =
    "providers_tried" in context
      ? profileToContext(context as CascadeProfile)
      : (context as GeminiAnalysisRequest);

  const url = `/api/gemini/analyze/${encodeURIComponent(t)}?analysis_type=${encodeURIComponent(analysisType)}`;

  console.info(`[GeminiService] requesting ${analysisType} for ${t}…`);
  const result = await apiFetch<GeminiAnalysis>(url, body);

  if (result.error) {
    console.warn(`[GeminiService] ${t} ${analysisType}: ${result.error}`);
  } else {
    console.info(`[GeminiService] ${t} ${analysisType}: ${result.text.length} chars via ${result.model}`);
  }

  return result;
}

// ─────────────────────────────────────────────────────────────────────────────
//  React hook
// ─────────────────────────────────────────────────────────────────────────────

export interface GeminiAnalysisState {
  data:    GeminiAnalysis | null;
  loading: boolean;
  error:   string | null;
}

/**
 * React hook — fetches Gemini analysis; re-fetches when ticker or type changes.
 * Skips the request when context has no useful data (e.g. on initial render).
 *
 *   const { data, loading, error } = useGeminiAnalysis("AAPL", profile, "moat");
 *   if (data) return <p>{data.text}</p>;
 */
export function useGeminiAnalysis(
  ticker: string,
  context: Partial<CascadeProfile> | GeminiAnalysisRequest | null,
  analysisType: GeminiAnalysisType = "summary",
): GeminiAnalysisState {
  const [state, setState] = useState<GeminiAnalysisState>({
    data: null, loading: false, error: null,
  });

  useEffect(() => {
    if (!ticker || !context) return;

    // Don't fire if there's no meaningful context yet
    const hasContext =
      (context as GeminiAnalysisRequest).company_name ||
      (context as CascadeProfile).company_name;
    if (!hasContext) return;

    setState({ data: null, loading: true, error: null });
    analyze(ticker, context, analysisType)
      .then(data  => setState({ data, loading: false, error: data.error ?? null }))
      .catch(err  => setState({ data: null, loading: false, error: String(err) }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, analysisType]);

  return state;
}

// ── Analysis type metadata (for UI labels / tooltips) ─────────────────────────

export const ANALYSIS_TYPES: Record<GeminiAnalysisType, { label: string; description: string }> = {
  summary:   { label: "AI Summary",   description: "3–5 sentence investment overview" },
  moat:      { label: "Moat Rating",  description: "Economic moat: Wide / Narrow / None" },
  risks:     { label: "Key Risks",    description: "Top 3 material investor risks" },
  valuation: { label: "Valuation",    description: "Is the stock cheap, fair, or expensive?" },
};

// ── Default export (namespace style) ─────────────────────────────────────────

const GeminiService = {
  analyze,
  useGeminiAnalysis,
  profileToContext,
  ANALYSIS_TYPES,
} as const;

export default GeminiService;
