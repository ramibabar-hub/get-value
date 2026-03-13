/**
 * Valueground.tsx
 *
 * Renders all 6 valuation model cards in a user-defined, draggable order.
 * Uses @dnd-kit DndContext + SortableContext.
 * Order is persisted in Zustand (localStorage).
 *
 * Senior Partner rule: each model component is passed unmodified.
 * This file is layout-only.
 */
import { useMemo } from "react";
import {
  DndContext, closestCenter, PointerSensor,
  useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, verticalListSortingStrategy, arrayMove,
} from "@dnd-kit/sortable";

import { useLayoutStore } from "../store/layoutStore";
import { ValuegroundCard } from "./ValuegroundCard";

import CfIrrTab            from "./CfIrrTab";
import CfIrrSpecialTab     from "./CfIrrSpecialTab";
import DDMTab              from "./DDMTab";
import IndustryMultipleTab from "./IndustryMultipleTab";
import PiotroskiTab        from "./PiotroskiTab";

import type { OverviewData } from "../types";

interface ValuegroundProps {
  ticker:           string;
  externalWacc:     number;
  ov?:              OverviewData | null;
  onDdmFairValue?:  (v: number | null) => void;
  NormalizedPENode: React.ReactNode;
}

export default function Valueground({
  ticker, externalWacc, ov, onDdmFairValue, NormalizedPENode,
}: ValuegroundProps) {
  const { cardOrder, setOrder } = useLayoutStore();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = cardOrder.indexOf(String(active.id));
    const newIdx = cardOrder.indexOf(String(over.id));
    if (oldIdx === -1 || newIdx === -1) return;
    setOrder(arrayMove(cardOrder, oldIdx, newIdx));
  }

  const CARD_CONTENT = useMemo<Record<string, React.ReactNode>>(() => ({
    "CF + IRR":          <CfIrrTab        ticker={ticker} externalWacc={externalWacc} ov={ov} />,
    "CF + IRR Special":  <CfIrrSpecialTab ticker={ticker} externalWacc={externalWacc} ov={ov} />,
    "Normalized PE":     NormalizedPENode,
    "DDM":               <DDMTab          ticker={ticker} externalWacc={externalWacc} onFairValueChange={onDdmFairValue} />,
    "Industry Multiple": <IndustryMultipleTab ticker={ticker} />,
    "Piotroski":         <PiotroskiTab    ticker={ticker} />,
  }), [ticker, externalWacc, ov, NormalizedPENode, onDdmFairValue]);

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={cardOrder} strategy={verticalListSortingStrategy}>
        {cardOrder.map((id) => (
          <ValuegroundCard key={id} id={id} title={id}>
            {CARD_CONTENT[id] ?? null}
          </ValuegroundCard>
        ))}
      </SortableContext>
    </DndContext>
  );
}
