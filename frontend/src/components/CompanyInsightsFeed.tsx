import { useState, useEffect } from "react";
import InsightCard, { InsightCardSkeleton } from "./InsightCard";
import type { NewsInsightsData, OverviewData } from "../types";

// ── Palette ────────────────────────────────────────────────────────────────────
const NAVY = "#1c2b46";
const BLUE = "#007bff";

interface Props {
  ticker: string;
  ov: OverviewData | null;
}

export default function CompanyInsightsFeed({ ticker, ov }: Props) {
  const [data, setData]       = useState<NewsInsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [, setError]          = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    setData(null);

    const body = {
      company_name: ov?.company_name ?? ticker,
      sector:       ov?.sector       ?? "",
      industry:     ov?.industry     ?? "",
      description:  ov?.description  ?? "",
    };

    fetch(`/api/news-insights/${encodeURIComponent(ticker)}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    })
      .then(r => { if (!r.ok) throw new Error("fetch failed"); return r.json(); })
      .then((d: NewsInsightsData) => setData(d))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [ticker]); // intentionally omit `ov` — re-fetching on ov change is disruptive

  if (loading) {
    return (
      <div>
        <SectionHeader />
        {/* Executive summary skeleton */}
        <div style={{ background: "#f8faff", border: `1px solid ${BLUE}22`, borderRadius: 10, padding: "14px 18px", marginBottom: 16 }}>
          <style>{`
            @keyframes shimmer-exec { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
            .exec-shimmer { background: linear-gradient(90deg,#eef2ff 25%,#e0e7ff 50%,#eef2ff 75%); background-size: 200% 100%; animation: shimmer-exec 1.4s infinite; border-radius: 4px; }
          `}</style>
          <div className="exec-shimmer" style={{ height: 13, width: "90%", marginBottom: 8 }} />
          <div className="exec-shimmer" style={{ height: 13, width: "70%", marginBottom: 8 }} />
          <div className="exec-shimmer" style={{ height: 13, width: "80%" }} />
        </div>
        <InsightCardSkeleton />
        <InsightCardSkeleton />
        <InsightCardSkeleton />
      </div>
    );
  }

  if (!data?.insights?.length) return null;

  return (
    <div>
      <SectionHeader />

      {/* Executive Summary */}
      {data.executive_summary && (
        <div style={{
          background: "#f8faff",
          border: `1px solid ${BLUE}22`,
          borderLeft: `3px solid ${BLUE}`,
          borderRadius: 10,
          padding: "14px 18px",
          marginBottom: 16,
          fontSize: "0.85em",
          color: NAVY,
          lineHeight: 1.7,
        }}>
          <div style={{ fontWeight: 700, fontSize: "0.78em", textTransform: "uppercase", letterSpacing: "0.07em", color: BLUE, marginBottom: 7 }}>
            Executive Summary
          </div>
          {data.executive_summary}
        </div>
      )}

      {/* Event cards */}
      {data.insights.map((item, i) => (
        <InsightCard key={i} item={item} />
      ))}
    </div>
  );
}

function SectionHeader() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "28px 0 14px" }}>
      <div style={{ height: 3, width: 28, background: BLUE, borderRadius: 2 }} />
      <h3 style={{ margin: 0, fontSize: "0.95em", fontWeight: 700, color: NAVY, letterSpacing: "0.02em", textTransform: "uppercase" }}>
        News &amp; Insights
      </h3>
      <div style={{ flex: 1, height: 1, background: "#e5e7eb" }} />
      <span style={{ fontSize: "0.7em", color: "#9ca3af" }}>Powered by Claude Haiku</span>
    </div>
  );
}
