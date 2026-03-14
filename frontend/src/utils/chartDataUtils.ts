import type { FinancialRow, ExtRow, Scale } from "../types";

/**
 * Find a row by exact label. Returns null if not found.
 */
export function findRow(rows: FinancialRow[] | ExtRow[], label: string): FinancialRow | ExtRow | null {
  return rows.find(r => r.label === label) ?? null;
}

/**
 * Build a recharts-compatible data array from columns + multiple row labels.
 * Returns [{col: "2016", Revenue: 1234, "Net Income": 567, …}, …]
 * Missing/null values become null (recharts skips null points on lines).
 *
 * @param columns  - ordered column array (already sorted chronologically, e.g. ["2016","2017","TTM"])
 * @param rows     - array of FinancialRow or ExtRow
 * @param labels   - labels to extract (each becomes a key in the output object)
 * @param divisor  - divide raw values (for scale: K=1e3, MM=1e6, B=1e9)
 */
export function buildChartData(
  columns: string[],
  rows: (FinancialRow | ExtRow)[],
  labels: string[],
  divisor = 1,
): Record<string, string | number | null>[] {
  return columns.map(col => {
    const entry: Record<string, string | number | null> = { col };
    for (const label of labels) {
      const row = rows.find(r => r.label === label);
      const raw = row ? (row[col] as number | null | undefined) : undefined;
      entry[label] = (raw != null && isFinite(raw)) ? raw / divisor : null;
    }
    return entry;
  });
}

/**
 * Build chart data for percentage-format ExtRow (multiply by 100 for display).
 * Use for rows where fmt === "pct".
 */
export function buildPctChartData(
  columns: string[],
  rows: ExtRow[],
  labels: string[],
): Record<string, string | number | null>[] {
  return columns.map(col => {
    const entry: Record<string, string | number | null> = { col };
    for (const label of labels) {
      const row = rows.find(r => r.label === label);
      const raw = row ? (row[col] as number | null | undefined) : undefined;
      // pct rows store as decimal (0.35 = 35%), multiply by 100
      entry[label] = (raw != null && isFinite(raw)) ? +(raw * 100).toFixed(1) : null;
    }
    return entry;
  });
}

/**
 * Scale divisor from Scale type.
 */
export function scaleDivisor(scale: Scale): number {
  return scale === "K" ? 1e3 : scale === "MM" ? 1e6 : 1e9;
}

/**
 * Sorted chart columns: oldest non-TTM columns first, then TTM.
 * Input: ["TTM", "2024", "2023", ...] → ["2016","2017",...,"2024","TTM"]
 */
export function chartColumns(columns: string[]): string[] {
  return [...columns.filter(c => c !== "TTM").reverse(), "TTM"];
}

/**
 * Format a chart axis tick value as a compact number (e.g. 1200 → "1.2K", 1500000 → "1.5M").
 * Values are already divided by scale, so just format the number cleanly.
 */
export function fmtTick(value: number): string {
  if (value == null || !isFinite(value)) return "";
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(1);
}

/**
 * Format a percentage tick (value is already *100).
 */
export function fmtPctTick(value: number): string {
  return `${value.toFixed(1)}%`;
}

/**
 * Format a ratio tick (2 decimal places).
 */
export function fmtRatioTick(value: number): string {
  return value.toFixed(2);
}
