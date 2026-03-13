/**
 * MetricsCatalogModal.tsx
 *
 * Allows users to show/hide metric sections in Financials and Value Drivers.
 * Senior Partner Rule: pinned sections cannot be hidden.
 * vs. Industry column is always shown for applicable rows.
 */
import { useCallback } from "react";
import { METRICS_REGISTRY, type MetricTab, type MetricCategory } from "../constants/metricsRegistry";
import { useLayoutStore } from "../store/layoutStore";

const FONT_MONO = "var(--gv-font-mono)";
const NAVY = "var(--gv-navy)";
const BLUE = "var(--gv-blue)";

const IMPACT_DOT: Record<string, string> = {
  high:   "#22c55e",
  medium: "#f59e0b",
  low:    "#94a3b8",
};

const IMPACT_LABEL: Record<string, string> = {
  high:   "Core",
  medium: "Supplemental",
  low:    "Advanced",
};

interface Props {
  tab:     MetricTab;
  onClose: () => void;
}

export default function MetricsCatalogModal({ tab, onClose }: Props) {
  const {
    hiddenFinancialsSections,
    hiddenInsightGroups,
    toggleFinancialsSection,
    toggleInsightGroup,
    resetCustomization,
  } = useLayoutStore();

  const sections = METRICS_REGISTRY.filter((m) => m.tab === tab);

  // Group by category
  const grouped = sections.reduce<Record<MetricCategory, typeof sections[number][]>>(
    (acc, s) => { (acc[s.category] ??= []).push(s); return acc; },
    {} as Record<MetricCategory, typeof sections[number][]>
  );

  const isHidden = useCallback(
    (id: string) =>
      tab === "financials"
        ? hiddenFinancialsSections.includes(id)
        : hiddenInsightGroups.includes(id),
    [tab, hiddenFinancialsSections, hiddenInsightGroups]
  );

  const toggle = useCallback(
    (id: string, label: string) => {
      if (tab === "financials") {
        toggleFinancialsSection(id);
      } else {
        toggleInsightGroup(label);
      }
    },
    [tab, toggleFinancialsSection, toggleInsightGroup]
  );

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", zIndex: 1000 }}
      />

      {/* Modal */}
      <div style={{
        position: "fixed",
        top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        background: "var(--gv-surface)",
        borderRadius: 12,
        boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
        width: "min(540px, 95vw)",
        maxHeight: "80vh",
        display: "flex",
        flexDirection: "column",
        zIndex: 1001,
        overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{ background: NAVY, padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontFamily: FONT_MONO, color: "var(--gv-surface)", fontWeight: 700, fontSize: "0.95em", letterSpacing: "0.04em" }}>
              ⚙ Customize Sections
            </div>
            <div style={{ fontFamily: FONT_MONO, color: "rgba(255,255,255,0.55)", fontSize: "0.72em", marginTop: 2 }}>
              {tab === "financials" ? "Financials" : "Value Drivers"} · toggle sections on/off
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.7)", cursor: "pointer", fontSize: "1.2em", lineHeight: 1, padding: "4px 8px" }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ overflowY: "auto", padding: "16px 20px", flex: 1 }}>
          {/* Legend */}
          <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
            {Object.entries(IMPACT_LABEL).map(([k, v]) => (
              <span key={k} style={{ fontFamily: FONT_MONO, fontSize: "0.7em", color: "var(--gv-text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: IMPACT_DOT[k] }} />
                {v}
              </span>
            ))}
            <span style={{ fontFamily: FONT_MONO, fontSize: "0.7em", color: "var(--gv-text-muted)", marginLeft: "auto" }}>
              🔒 = always shown
            </span>
          </div>

          {/* Grouped sections */}
          {Object.entries(grouped).map(([category, items]) => (
            <div key={category} style={{ marginBottom: 20 }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: "0.7em", fontWeight: 700, color: BLUE, textTransform: "uppercase", letterSpacing: "0.08em", borderBottom: `1px solid var(--gv-border)`, paddingBottom: 4, marginBottom: 10 }}>
                {category}
              </div>
              {items.map((section) => {
                const hidden = isHidden(section.id);
                const disabled = section.pinned;
                return (
                  <div
                    key={section.id}
                    onClick={() => { if (!disabled) toggle(section.id, section.label); }}
                    style={{
                      display: "flex", alignItems: "flex-start", gap: 10,
                      padding: "8px 10px", borderRadius: 6, marginBottom: 4,
                      cursor: disabled ? "not-allowed" : "pointer",
                      background: hidden ? "var(--gv-bg)" : "transparent",
                      opacity: disabled ? 0.6 : 1,
                      border: `1px solid ${hidden ? "var(--gv-border)" : "transparent"}`,
                      transition: "background 0.1s",
                    }}
                  >
                    {/* Checkbox */}
                    <div style={{
                      width: 16, height: 16, borderRadius: 3, flexShrink: 0, marginTop: 2,
                      border: `2px solid ${disabled ? "var(--gv-text-muted)" : hidden ? "var(--gv-border-dark)" : BLUE}`,
                      background: disabled ? "var(--gv-data-bg)" : hidden ? "transparent" : BLUE,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      color: "white", fontSize: "0.65em", fontWeight: 900,
                    }}>
                      {disabled ? "🔒" : !hidden ? "✓" : ""}
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontFamily: FONT_MONO, fontWeight: 600, fontSize: "0.82em", color: hidden ? "var(--gv-text-muted)" : NAVY }}>
                          {section.label}
                        </span>
                        <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: IMPACT_DOT[section.impact], flexShrink: 0 }} />
                      </div>
                      <div style={{ fontFamily: FONT_MONO, fontSize: "0.71em", color: "var(--gv-text-muted)", marginTop: 2, lineHeight: 1.4 }}>
                        {section.description}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ borderTop: "1px solid var(--gv-border)", padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--gv-bg)" }}>
          <button
            onClick={resetCustomization}
            style={{ fontFamily: FONT_MONO, fontSize: "0.75em", color: "var(--gv-text-muted)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
          >
            Reset to defaults
          </button>
          <button
            onClick={onClose}
            style={{ fontFamily: FONT_MONO, fontWeight: 700, fontSize: "0.82em", background: BLUE, color: "white", border: "none", borderRadius: 6, padding: "8px 20px", cursor: "pointer" }}
          >
            Done
          </button>
        </div>
      </div>
    </>
  );
}
