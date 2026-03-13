/**
 * ValuegroundCard.tsx
 *
 * A draggable, collapsible wrapper card for each valuation model.
 * The model component (children) is passed in unchanged — this wrapper
 * is purely presentational and never modifies model logic.
 *
 * Uses @dnd-kit/sortable for drag-and-drop.
 */
import { memo } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS }         from "@dnd-kit/utilities";
import { useLayoutStore } from "../store/layoutStore";

interface ValuegroundCardProps {
  id:       string;
  title:    string;
  children: React.ReactNode;
}

export const ValuegroundCard = memo(function ValuegroundCard({
  id, title, children,
}: ValuegroundCardProps) {
  const { collapsedCards, toggleCollapse } = useLayoutStore();
  const isCollapsed = collapsedCards.includes(id);

  const {
    attributes, listeners, setNodeRef,
    transform, transition, isDragging,
  } = useSortable({ id });

  const style: React.CSSProperties = {
    transform:  CSS.Transform.toString(transform),
    transition,
    opacity:    isDragging ? 0.55 : 1,
    zIndex:     isDragging ? 10 : undefined,
  };

  return (
    <div
      ref={setNodeRef}
      style={{
        ...style,
        background:   "var(--gv-surface)",
        border:       "1px solid var(--gv-border)",
        borderRadius: "var(--gv-radius)",
        marginBottom: 16,
        overflow:     "hidden",
        boxShadow:    isDragging ? "0 8px 24px rgba(0,0,0,0.12)" : "0 1px 4px rgba(0,0,0,0.06)",
      }}
    >
      {/* Card header */}
      <div style={{
        display:        "flex",
        alignItems:     "center",
        justifyContent: "space-between",
        padding:        "10px 16px",
        background:     "var(--gv-navy)",
        color:          "#fff",
        userSelect:     "none",
      }}>
        {/* Drag handle + title */}
        <div
          {...attributes}
          {...listeners}
          style={{ display: "flex", alignItems: "center", gap: 10, cursor: isDragging ? "grabbing" : "grab", flex: 1 }}
        >
          {/* Drag grip icon */}
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={{ opacity: 0.6, flexShrink: 0 }}>
            <circle cx="4" cy="3.5" r="1.2"/><circle cx="10" cy="3.5" r="1.2"/>
            <circle cx="4" cy="7"   r="1.2"/><circle cx="10" cy="7"   r="1.2"/>
            <circle cx="4" cy="10.5" r="1.2"/><circle cx="10" cy="10.5" r="1.2"/>
          </svg>
          <span style={{ fontWeight: 700, fontSize: "0.9em", letterSpacing: "0.02em" }}>
            {title}
          </span>
        </div>

        {/* Collapse button */}
        <button
          onClick={() => toggleCollapse(id)}
          title={isCollapsed ? "Expand" : "Collapse"}
          style={{
            background: "none", border: "none", cursor: "pointer",
            color: "#fff", padding: "2px 6px", borderRadius: 4,
            fontSize: "0.85em", opacity: 0.8, lineHeight: 1,
          }}
        >
          {isCollapsed ? "▼" : "▲"}
        </button>
      </div>

      {/* Card body */}
      {!isCollapsed && (
        <div style={{ padding: "16px 20px" }}>
          {children}
        </div>
      )}
    </div>
  );
});
