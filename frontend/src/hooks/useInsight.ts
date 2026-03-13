/**
 * useInsight.ts
 *
 * Lazy hook for AI-powered metric explanations.
 * - Does NOT auto-fetch on mount; waits for trigger() call.
 * - Caches results per "{ticker}:{metric}" key (module-level Map, session-only).
 * - Cleared automatically on ticker change via the returned clearCache().
 */
import { useState, useCallback, useRef } from "react";

// Module-level cache — shared across all useInsight instances
const _cache = new Map<string, string>();

export function clearInsightCache() {
  _cache.clear();
}

interface UseInsightOptions {
  metric:  string;
  value:   number | string | null;
  ticker:  string;
  context: Record<string, unknown>;
}

interface UseInsightResult {
  insight:   string | null;
  isLoading: boolean;
  hasResult: boolean;
  trigger:   () => void;
}

export function useInsight({
  metric, value, ticker, context,
}: UseInsightOptions): UseInsightResult {
  const [insight,   setInsight]   = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const cacheKey = `${ticker}:${metric}`;

  const trigger = useCallback(() => {
    // Cache hit
    const cached = _cache.get(cacheKey);
    if (cached) { setInsight(cached); return; }

    // Already loading
    if (isLoading) return;

    // Abort any previous in-flight request
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setIsLoading(true);

    fetch(`/api/gemini/analyze/${ticker}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      signal:  ctrl.signal,
      body: JSON.stringify({
        analysis_type: "summary",
        company_name:  context.company_name ?? ticker,
        sector:        context.sector       ?? "",
        industry:      context.industry     ?? "",
        description:   `Focus on the metric "${metric}" with value "${value}". Explain in 2-3 concise sentences what this means for an investor.`,
      }),
    })
      .then(r => r.json())
      .then(d => {
        const text = d.text ?? d.error ?? "No insight available.";
        _cache.set(cacheKey, text);
        setInsight(text);
      })
      .catch(err => {
        if (err.name !== "AbortError") {
          setInsight("Insight unavailable at this time.");
        }
      })
      .finally(() => setIsLoading(false));
  }, [cacheKey, ticker, metric, value, context, isLoading]);

  return {
    insight,
    isLoading,
    hasResult: insight !== null,
    trigger,
  };
}
