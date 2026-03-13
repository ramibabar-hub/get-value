/**
 * layoutStore.ts
 *
 * Zustand store for user-customisable Valueground layout.
 * Persisted to localStorage under key "gv_layout_v3".
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

  // Section visibility customization
  hiddenFinancialsSections: string[];   // IDs of hidden extended sections
  hiddenInsightGroups:      string[];   // titles of hidden insight groups
  toggleFinancialsSection:  (id: string)    => void;
  toggleInsightGroup:       (title: string) => void;
  resetCustomization:       ()              => void;
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

      // Section visibility defaults
      hiddenFinancialsSections: [],
      hiddenInsightGroups:      [],

      toggleFinancialsSection: (id) =>
        set((state) => ({
          hiddenFinancialsSections: state.hiddenFinancialsSections.includes(id)
            ? state.hiddenFinancialsSections.filter((s) => s !== id)
            : [...state.hiddenFinancialsSections, id],
        })),

      toggleInsightGroup: (title) =>
        set((state) => ({
          hiddenInsightGroups: state.hiddenInsightGroups.includes(title)
            ? state.hiddenInsightGroups.filter((g) => g !== title)
            : [...state.hiddenInsightGroups, title],
        })),

      resetCustomization: () =>
        set({ hiddenFinancialsSections: [], hiddenInsightGroups: [] }),
    }),
    {
      name: "gv_layout_v3",
    }
  )
);
