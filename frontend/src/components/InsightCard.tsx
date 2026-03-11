import { useState } from "react";
import { Zap, BookOpen, ChevronDown, ChevronUp } from "lucide-react";
import type { NewsInsight } from "../types";

// ── Palette ────────────────────────────────────────────────────────────────────
const NAVY = "#1c2b46";
const BLUE = "#007bff";

interface Props {
  item: NewsInsight;
}

export default function InsightCard({ item }: Props) {
  const [showImpact,      setShowImpact]      = useState(false);
  const [showEducational, setShowEducational] = useState(false);

  return (
    <div style={{
      background: "#fff",
      border: "1px solid #e5e7eb",
      borderRadius: 10,
      padding: "14px 16px",
      marginBottom: 10,
      boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
      transition: "box-shadow 0.15s",
    }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 4px 16px rgba(0,123,255,0.09)")}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 1px 4px rgba(0,0,0,0.05)")}
    >
      {/* Main row */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        {/* Blue dot + date */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, paddingTop: 3, flexShrink: 0 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: BLUE }} />
          <span style={{ fontSize: "0.65em", color: "#9ca3af", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
            {item.date}
          </span>
        </div>

        {/* Headline + summary */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {item.url ? (
            <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
              <div style={{ fontWeight: 700, color: NAVY, fontSize: "0.88em", lineHeight: 1.4, marginBottom: 4, transition: "color 0.12s" }}
                onMouseEnter={e => (e.currentTarget.style.color = BLUE)}
                onMouseLeave={e => (e.currentTarget.style.color = NAVY)}
              >
                {item.headline}
              </div>
            </a>
          ) : (
            <div style={{ fontWeight: 700, color: NAVY, fontSize: "0.88em", lineHeight: 1.4, marginBottom: 4 }}>
              {item.headline}
            </div>
          )}
          <div style={{ color: "#6b7280", fontSize: "0.82em", lineHeight: 1.5 }}>
            {item.summary}
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, flexShrink: 0 }}>
          {/* Model Impact button */}
          <button
            onClick={() => setShowImpact(o => !o)}
            title="How does this affect the valuation model?"
            style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "5px 10px", fontSize: "0.73em", fontWeight: 600,
              border: `1px solid ${showImpact ? BLUE : "#d1d5db"}`,
              borderRadius: 6,
              background: showImpact ? BLUE : "#fff",
              color: showImpact ? "#fff" : BLUE,
              cursor: "pointer", whiteSpace: "nowrap",
              transition: "all 0.15s",
            }}
          >
            <Zap size={12} fill={showImpact ? "#fff" : BLUE} strokeWidth={0} />
            Model Impact
            {showImpact ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </button>

          {/* Educational insight button */}
          {item.educational_insight && (
            <button
              onClick={() => setShowEducational(o => !o)}
              title="Educational insight"
              style={{
                display: "flex", alignItems: "center", gap: 5,
                padding: "5px 10px", fontSize: "0.73em", fontWeight: 600,
                border: `1px solid ${showEducational ? "#10b981" : "#d1d5db"}`,
                borderRadius: 6,
                background: showEducational ? "#10b981" : "#fff",
                color: showEducational ? "#fff" : "#10b981",
                cursor: "pointer", whiteSpace: "nowrap",
                transition: "all 0.15s",
              }}
            >
              <BookOpen size={12} />
              Did You Know?
              {showEducational ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            </button>
          )}
        </div>
      </div>

      {/* Model Impact panel */}
      {showImpact && (
        <div style={{
          marginTop: 10,
          padding: "10px 14px",
          background: "#eff6ff",
          border: `1px solid ${BLUE}33`,
          borderRadius: 8,
          fontSize: "0.82em",
          color: NAVY,
          lineHeight: 1.65,
        }}>
          <div style={{ fontWeight: 700, color: BLUE, marginBottom: 5, fontSize: "0.85em", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            ⚡ Valuation Model Impact
          </div>
          {item.model_impact}
        </div>
      )}

      {/* Educational Insight panel */}
      {showEducational && item.educational_insight && (
        <div style={{
          marginTop: 8,
          padding: "10px 14px",
          background: "#f0fdf4",
          border: "1px solid #bbf7d0",
          borderRadius: 8,
          fontSize: "0.82em",
          color: "#166534",
          lineHeight: 1.65,
        }}>
          <div style={{ fontWeight: 700, marginBottom: 5, fontSize: "0.85em", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            📚 Analyst Insight
          </div>
          {item.educational_insight}
        </div>
      )}
    </div>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────────
export function InsightCardSkeleton() {
  return (
    <>
      <style>{`
        @keyframes shimmer-insight {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
        .insight-shimmer {
          background: linear-gradient(90deg, #f0f2f5 25%, #e2e6ea 50%, #f0f2f5 75%);
          background-size: 200% 100%;
          animation: shimmer-insight 1.4s infinite;
          border-radius: 4px;
        }
      `}</style>
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, padding: "14px 16px", marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <div className="insight-shimmer" style={{ width: 8, height: 8, borderRadius: "50%", marginTop: 4, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div className="insight-shimmer" style={{ height: 14, width: "75%", marginBottom: 8 }} />
            <div className="insight-shimmer" style={{ height: 11, width: "90%", marginBottom: 4 }} />
            <div className="insight-shimmer" style={{ height: 11, width: "60%" }} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div className="insight-shimmer" style={{ width: 100, height: 28, borderRadius: 6 }} />
            <div className="insight-shimmer" style={{ width: 100, height: 28, borderRadius: 6 }} />
          </div>
        </div>
      </div>
    </>
  );
}
