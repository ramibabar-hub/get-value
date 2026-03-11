import { useState, useEffect } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Users, ShieldCheck, TrendingUp } from "lucide-react";
import type { OwnershipData } from "../types";

// ── Palette ────────────────────────────────────────────────────────────────────
const NAVY   = "#1c2b46";
const BLUE   = "#007bff";
const SLATE  = "#64748b";

const SEGMENTS = [
  { key: "institutional_pct", label: "Institutional",   color: NAVY,    icon: ShieldCheck },
  { key: "insider_pct",       label: "Insider",         color: BLUE,    icon: TrendingUp  },
  { key: "retail_pct",        label: "Retail / Public", color: "#94a3b8", icon: Users     },
];

// ── Custom centre label rendered via SVG foreignObject ────────────────────────
function CenterLabel({ cx, cy, value }: { cx: number; cy: number; value: number }) {
  return (
    <g>
      <text x={cx} y={cy - 10} textAnchor="middle" dominantBaseline="middle"
        style={{ fill: NAVY, fontSize: 22, fontWeight: 800 }}>
        {value.toFixed(1)}%
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" dominantBaseline="middle"
        style={{ fill: SLATE, fontSize: 10, fontWeight: 500 }}>
        Institutional
      </text>
    </g>
  );
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
function OwnerTooltip({ active, payload }: {
  active?: boolean;
  payload?: { name: string; value: number; payload: { color: string } }[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
      padding: "8px 12px", boxShadow: "0 4px 16px rgba(0,0,0,0.1)", fontSize: "0.82em",
    }}>
      <span style={{ fontWeight: 700, color: d.payload.color }}>{d.name}</span>
      <span style={{ marginLeft: 8, color: NAVY, fontWeight: 600 }}>{d.value.toFixed(1)}%</span>
    </div>
  );
}

// ── Shimmer skeleton ──────────────────────────────────────────────────────────
function OwnershipSkeleton() {
  return (
    <>
      <style>{`
        @keyframes shimmer-own { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
        .own-shimmer { background: linear-gradient(90deg,#f0f2f5 25%,#e2e6ea 50%,#f0f2f5 75%); background-size:200% 100%; animation:shimmer-own 1.4s infinite; border-radius:4px; }
      `}</style>
      <div style={{ display: "flex", gap: 24, alignItems: "center", padding: "16px 0" }}>
        <div className="own-shimmer" style={{ width: 180, height: 180, borderRadius: "50%", flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          {[80, 60, 70].map((w, i) => (
            <div key={i} className="own-shimmer" style={{ height: 14, width: `${w}%`, marginBottom: 12 }} />
          ))}
        </div>
      </div>
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
interface Props { ticker: string; }

export default function CompanyOwnershipChart({ ticker }: Props) {
  const [data, setData]       = useState<OwnershipData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setData(null);
    fetch(`/api/ownership/${encodeURIComponent(ticker)}`)
      .then(r => r.json())
      .then((d: OwnershipData) => {
        // Only render if we have meaningful data
        if (d.insider_pct === 0 && d.institutional_pct === 0) { setData(null); return; }
        setData(d);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return (
    <div>
      <SectionHeader />
      <OwnershipSkeleton />
    </div>
  );

  if (!data) return null;

  const pieData = SEGMENTS.map(s => ({
    name:  s.label,
    value: data[s.key as keyof OwnershipData] as number,
    color: s.color,
  })).filter(d => d.value > 0);

  return (
    <div>
      <SectionHeader />

      <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap" }}>
        {/* Donut chart */}
        <div style={{ flexShrink: 0, width: 200, height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={62}
                outerRadius={90}
                startAngle={90}
                endAngle={-270}
                dataKey="value"
                strokeWidth={2}
                stroke="#fff"
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<OwnerTooltip />} />
              {/* Centre label — rendered as custom label on the innermost ring */}
              <Pie
                data={[{ value: 1 }]}
                cx="50%"
                cy="50%"
                innerRadius={0}
                outerRadius={0}
                dataKey="value"
                label={({ cx, cy }) => (
                  <CenterLabel cx={cx as number} cy={cy as number} value={data.institutional_pct} />
                )}
                labelLine={false}
                stroke="none"
                fill="none"
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Right side: legend + Power Dynamics */}
        <div style={{ flex: 1, minWidth: 200 }}>
          {/* Legend */}
          <div style={{ marginBottom: 14 }}>
            {SEGMENTS.map(s => {
              const val = data[s.key as keyof OwnershipData] as number;
              const Icon = s.icon;
              return (
                <div key={s.key} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  marginBottom: 8,
                }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: s.color, flexShrink: 0 }} />
                  <Icon size={13} color={s.color} />
                  <span style={{ fontSize: "0.82em", color: "#4b5563", flex: 1 }}>{s.label}</span>
                  <span style={{ fontSize: "0.88em", fontWeight: 700, color: NAVY, fontVariantNumeric: "tabular-nums" }}>
                    {val.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>

          {/* Insider label note */}
          <div style={{ fontSize: "0.68em", color: "#9ca3af", marginBottom: 12, fontStyle: "italic" }}>
            Insider % sourced from SEC filings · Institutional/Retail are AI estimates
          </div>

          {/* Power Dynamics */}
          {data.power_dynamics && (
            <div style={{
              background: "#f8faff",
              border: `1px solid ${BLUE}22`,
              borderLeft: `3px solid ${BLUE}`,
              borderRadius: 8,
              padding: "10px 14px",
            }}>
              <div style={{ fontSize: "0.7em", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: BLUE, marginBottom: 5 }}>
                ⚡ Power Dynamics
              </div>
              <p style={{ margin: 0, fontSize: "0.8em", color: NAVY, lineHeight: 1.6 }}>
                {data.power_dynamics}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionHeader() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "24px 0 14px" }}>
      <div style={{ height: 3, width: 28, background: NAVY, borderRadius: 2 }} />
      <h3 style={{ margin: 0, fontSize: "0.95em", fontWeight: 700, color: NAVY, letterSpacing: "0.02em", textTransform: "uppercase" }}>
        Ownership Structure
      </h3>
      <div style={{ flex: 1, height: 1, background: "#e5e7eb" }} />
    </div>
  );
}
