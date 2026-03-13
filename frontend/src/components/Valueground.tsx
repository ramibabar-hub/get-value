/**
 * Valueground.tsx
 *
 * Horizontal draggable sub-tab layout for all valuation models.
 * User selects which model to view via tabs. Tab order is draggable
 * and persisted in Zustand (localStorage).
 *
 * Senior Partner rule: model components are passed unmodified.
 * This file is layout-only.
 */
import { useState, useCallback } from "react";
import {
  DndContext, closestCenter, PointerSensor,
  useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, horizontalListSortingStrategy, arrayMove, useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { useLayoutStore } from "../store/layoutStore";

import CfIrrTab            from "./CfIrrTab";
import CfIrrSpecialTab     from "./CfIrrSpecialTab";
import DDMTab              from "./DDMTab";
import IndustryMultipleTab from "./IndustryMultipleTab";
import PiotroskiTab        from "./PiotroskiTab";
import PortfolioImpact     from "./PortfolioImpact";

import type { OverviewData } from "../types";

const BLUE = "var(--gv-blue)";

interface ValuegroundProps {
  ticker:           string;
  externalWacc:     number;
  ov?:              OverviewData | null;
  onDdmFairValue?:  (v: number | null) => void;
  NormalizedPENode: React.ReactNode;
}

// ── Sortable tab button ──────────────────────────────────────────────────────

function SortableTab({ id, active, onSelect }: { id: string; active: boolean; onSelect: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition: `color 0.12s${transition ? `, ${transition}` : ""}`,
    padding: "9px 18px",
    border: "none",
    background: "none",
    cursor: isDragging ? "grabbing" : "pointer",
    fontWeight: active ? 700 : 500,
    color: active ? BLUE : "var(--gv-text-muted)",
    borderBottom: active ? `2px solid ${BLUE}` : "2px solid transparent",
    marginBottom: -2,
    fontSize: "0.86em",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
    opacity: isDragging ? 0.7 : 1,
    zIndex: isDragging ? 10 : undefined,
    touchAction: "none",
  };
  return (
    <button ref={setNodeRef} style={style} {...attributes} {...listeners} onClick={() => onSelect(id)}>
      {id}
    </button>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export default function Valueground({
  ticker, externalWacc, ov, onDdmFairValue, NormalizedPENode,
}: ValuegroundProps) {
  const { cardOrder, setOrder, resetOrder } = useLayoutStore();
  const [activeTab, setActiveTab] = useState<string>(cardOrder[0] ?? "CF + IRR");

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = cardOrder.indexOf(String(active.id));
    const newIdx = cardOrder.indexOf(String(over.id));
    if (oldIdx === -1 || newIdx === -1) return;
    setOrder(arrayMove(cardOrder, oldIdx, newIdx));
  }, [cardOrder, setOrder]);

  const handleSelect = useCallback((id: string) => setActiveTab(id), []);

  // Ensure activeTab is valid after order changes
  const effectiveActive = cardOrder.includes(activeTab) ? activeTab : cardOrder[0];

  // Render the active model
  function renderContent() {
    switch (effectiveActive) {
      case "CF + IRR":          return <CfIrrTab ticker={ticker} externalWacc={externalWacc} ov={ov} />;
      case "CF + IRR Special":  return <CfIrrSpecialTab ticker={ticker} externalWacc={externalWacc} ov={ov} />;
      case "Normalized PE":     return NormalizedPENode;
      case "DDM":               return <DDMTab ticker={ticker} externalWacc={externalWacc} onFairValueChange={onDdmFairValue} />;
      case "Industry Multiple": return <IndustryMultipleTab ticker={ticker} />;
      case "Piotroski":         return <PiotroskiTab ticker={ticker} />;
      case "Portfolio Impact":  return <PortfolioImpact ov={ov ?? null} />;
      default:                  return null;
    }
  }

  return (
    <div>
      {/* Draggable tab bar */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div style={{
          display: "flex",
          borderBottom: `2px solid var(--gv-border)`,
          marginBottom: 20,
          overflowX: "auto",
          scrollbarWidth: "none",
        }}>
          <SortableContext items={cardOrder} strategy={horizontalListSortingStrategy}>
            {cardOrder.map((id) => (
              <SortableTab
                key={id}
                id={id}
                active={id === effectiveActive}
                onSelect={handleSelect}
              />
            ))}
          </SortableContext>
        </div>
      </DndContext>

      {/* Reset order button */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <button
          onClick={() => { resetOrder(); setActiveTab("CF + IRR"); }}
          style={{ fontSize: "0.75em", color: "var(--gv-text-muted)", background: "none", border: "none", cursor: "pointer", padding: "2px 6px", textDecoration: "underline" }}
        >
          Reset tab order
        </button>
      </div>

      {/* Active model content */}
      <div>
        {renderContent()}
      </div>
    </div>
  );
}
