/**
 * InsightTooltip.tsx
 *
 * Renders a ✨ trigger icon next to a metric value.
 * On click: calls trigger(), shows spinner then AI-generated insight text.
 * Tooltip positioned above metric cell.
 */
import { useState, useRef, useEffect } from "react";
import { useInsight } from "../hooks/useInsight";

interface InsightTooltipProps {
  metric:    string;
  value:     number | string | null;
  ticker:    string;
  context?:  Record<string, unknown>;
}

export function InsightTooltip({
  metric, value, ticker, context = {},
}: InsightTooltipProps) {
  const [open, setOpen] = useState(false);
  const ref             = useRef<HTMLDivElement>(null);
  const { insight, isLoading, trigger } = useInsight({ metric, value, ticker, context });

  function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    setOpen(prev => !prev);
    if (!open) trigger();
  }

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  return (
    <span ref={ref} style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
      {/* ✨ trigger */}
      <button
        onClick={handleClick}
        title="AI Insight"
        style={{
          background: "none", border: "none", cursor: "pointer",
          padding: "0 3px", fontSize: "0.75em", lineHeight: 1,
          color: open ? "#f59e0b" : "var(--gv-text-muted)",
          transition: "color 0.15s",
        }}
      >
        ✨
      </button>

      {/* Tooltip */}
      {open ? (
        <div style={{
          position: "absolute", bottom: "calc(100% + 8px)", left: "50%",
          transform: "translateX(-50%)",
          background: "var(--gv-navy)", color: "#fff",
          padding: "10px 14px", borderRadius: "var(--gv-radius-sm)",
          width: 280, fontSize: "0.78em", lineHeight: 1.6,
          boxShadow: "0 4px 20px rgba(0,0,0,0.25)", zIndex: 100,
          whiteSpace: "normal",
        }}>
          {/* Arrow */}
          <div style={{
            position: "absolute", bottom: -6, left: "50%",
            transform: "translateX(-50%)",
            width: 0, height: 0,
            borderLeft: "6px solid transparent",
            borderRight: "6px solid transparent",
            borderTop: "6px solid var(--gv-navy)",
          }} />

          <div style={{ fontWeight: 700, marginBottom: 6, color: "#93c5fd", fontSize: "0.88em" }}>
            ✨ AI Insight — {metric}
          </div>

          {isLoading ? (
            <div style={{ color: "#9ca3af", fontStyle: "italic" }}>Thinking…</div>
          ) : (
            <div>{insight}</div>
          )}
        </div>
      ) : null}
    </span>
  );
}
