import { useState } from "react";
import { ResponsiveContainer } from "recharts";
import { useLayoutStore } from "../store/layoutStore";

const NAVY = "#1c2b46";
const BLUE = "#007bff";

interface ChartCardProps {
  chartId:  string;        // unique ID used for series customization storage
  title:    string;        // displayed in the header
  series:   string[];      // all possible series labels (for customize popover)
  colors:   string[];      // parallel to series: color for each series
  height?:  number;        // chart height in px (default 280)
  children: (hiddenSeries: Set<string>) => React.ReactNode;  // render prop
}

export default function ChartCard({ chartId, title, series, colors, height = 280, children }: ChartCardProps) {
  const [showCustomize, setShowCustomize] = useState(false);
  const { hiddenGraphSeries, toggleGraphSeries } = useLayoutStore();
  const hiddenArr = hiddenGraphSeries[chartId] ?? [];
  const hiddenSet = new Set(hiddenArr);

  return (
    <div style={{ background: "#fff", borderRadius: 6, border: "1px solid #e5e7eb", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
      {/* Header */}
      <div style={{ background: NAVY, padding: "7px 12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ color: "#fff", fontWeight: 700, fontSize: "0.82em", letterSpacing: "0.02em" }}>{title}</span>
        <div style={{ position: "relative" }}>
          <button
            onClick={() => setShowCustomize(v => !v)}
            style={{ background: "none", border: "1px solid rgba(255,255,255,0.3)", borderRadius: 4, color: "rgba(255,255,255,0.8)", fontSize: "0.7em", padding: "2px 8px", cursor: "pointer", fontFamily: "inherit" }}
          >
            ⚙ Series
          </button>
          {showCustomize && (
            <>
              {/* backdrop */}
              <div onClick={() => setShowCustomize(false)} style={{ position: "fixed", inset: 0, zIndex: 50 }} />
              {/* popover */}
              <div style={{ position: "absolute", right: 0, top: "calc(100% + 4px)", background: "#fff", border: "1px solid #e5e7eb", borderRadius: 6, padding: "10px 14px", minWidth: 180, zIndex: 51, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}>
                <div style={{ fontSize: "0.72em", fontWeight: 700, color: NAVY, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Toggle Series</div>
                {series.map((s, i) => {
                  const hidden = hiddenSet.has(s);
                  return (
                    <div
                      key={s}
                      onClick={() => toggleGraphSeries(chartId, s)}
                      style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 2px", cursor: "pointer", borderRadius: 3 }}
                    >
                      <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: hidden ? "#d1d5db" : (colors[i] ?? BLUE), flexShrink: 0 }} />
                      <span style={{ fontSize: "0.78em", color: hidden ? "#9ca3af" : NAVY, textDecoration: hidden ? "line-through" : "none" }}>{s}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
      {/* Chart body */}
      <div style={{ padding: "8px 4px 4px" }}>
        <ResponsiveContainer width="100%" height={height}>
          {/* children is a render prop receiving the hiddenSet */}
          {children(hiddenSet) as React.ReactElement}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
