/**
 * layoutStore.ts
 *
 * Zustand store for user-customisable Valueground layout.
 * Persisted to localStorage under key "gv_layout_v1".
 *
 * Senior Partner rule: this store controls presentation only.
 * It never touches model logic or financial calculations.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export const DEFAULT_CARD_ORDER = [
  "CF + IRR",
  "CF + IRR Special",
  "Normalized PE",
  "DDM",
  "Industry Multiple",
  "Piotroski",
  "Portfolio Impact",
] as const;

export type ModelCardId = typeof DEFAULT_CARD_ORDER[number];

interface LayoutState {
  cardOrder:      string[];
  collapsedCards: string[];
  setOrder:       (order: string[]) => void;
  toggleCollapse: (id: string)      => void;
  resetOrder:     ()                => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      cardOrder:      [...DEFAULT_CARD_ORDER],
      collapsedCards: [],

      setOrder: (order) => set({ cardOrder: order }),

      toggleCollapse: (id) =>
        set((state) => ({
          collapsedCards: state.collapsedCards.includes(id)
            ? state.collapsedCards.filter((c) => c !== id)
            : [...state.collapsedCards, id],
        })),

      resetOrder: () =>
        set({ cardOrder: [...DEFAULT_CARD_ORDER], collapsedCards: [] }),
    }),
    {
      name: "gv_layout_v2",
    }
  )
);
