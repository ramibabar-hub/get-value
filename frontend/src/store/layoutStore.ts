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

  // Per-table row visibility — key = table title, value = hidden row labels
  // undefined key  → never customized (defaults will be seeded by table component)
  // empty array [] → user explicitly chose "Show all"
  hiddenTableRows:  Record<string, string[]>;
  toggleTableRow:   (tableId: string, rowLabel: string) => void;
  resetTableRows:   (tableId?: string)                  => void;
  // Seeds default-hidden rows for a table on first visit (no-op if already set)
  initTableRows:    (tableId: string, defaultHidden: string[]) => void;
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
        set({ hiddenFinancialsSections: [], hiddenInsightGroups: [], hiddenTableRows: {} }),

      // Per-table row visibility
      hiddenTableRows: {},

      toggleTableRow: (tableId, rowLabel) =>
        set((state) => {
          const current = state.hiddenTableRows[tableId] ?? [];
          const updated  = current.includes(rowLabel)
            ? current.filter(r => r !== rowLabel)
            : [...current, rowLabel];
          return { hiddenTableRows: { ...state.hiddenTableRows, [tableId]: updated } };
        }),

      resetTableRows: (tableId?) =>
        set((state) => {
          if (!tableId) return { hiddenTableRows: {} };
          // Set to [] (not delete) so initTableRows won't re-seed after a manual "Show all"
          return { hiddenTableRows: { ...state.hiddenTableRows, [tableId]: [] } };
        }),

      initTableRows: (tableId, defaultHidden) =>
        set((state) => {
          // Only seed if the table has never been customized (key is absent)
          if (state.hiddenTableRows[tableId] !== undefined) return state;
          if (defaultHidden.length === 0) return state;
          return { hiddenTableRows: { ...state.hiddenTableRows, [tableId]: defaultHidden } };
        }),
    }),
    {
      name: "gv_layout_v4",
    }
  )
);
