/**
 * FinancialsTab.tsx
 * Pure presentational component — all data is passed in as props.
 * Shows Income Statement, Balance Sheet, and Cash Flow tables.
 * Period and Scale selectors are rendered here but controlled by the parent.
 */
import { memo } from "react";
import type { FinancialsData, FinancialRow, Scale, Period } from "../types";

const NAVY    = "#1c2b46";
const PERIODS: Period[]  = ["annual", "quarterly"];
const SCALES:  Scale[]   = ["K", "MM", "B"];
const EPS_LABELS = new Set(["eps", "epsdiluted"]);

// ── Formatters ────────────────────────────────────────────────────────────────

function isEps(label: string): boolean {
  return EPS_LABELS.has(label.toLowerCase().replace(/[^a-z]/g, ""));
}

function fCell(v: number | string | null | undefined, label: string, scale: Scale): { text: string; negative: boolean } {
  if (v == null || v === "") return { text: "—", negative: false };
  if (typeof v === "string")  return { text: v,  negative: false };
  if (!isFinite(v))           return { text: "—", negative: false };
  const neg = v < 0;
  if (isEps(label)) {
    return { text: `$${Math.abs(v).toFixed(2)}`, negative: neg };
  }
  const div = scale === "K" ? 1e3 : scale === "MM" ? 1e6 : 1e9;
  const abs  = Math.abs(v) / div;
  const text = abs.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return { text: neg ? `(${text})` : text, negative: neg };
}

// ── Radio strip ───────────────────────────────────────────────────────────────

function RadioGroup<T extends string>({
  label, options, value, onChange, formatter,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  formatter?: (v: T) => string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: "0.78em", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </span>
      <div style={{ display: "flex", gap: 4 }}>
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              onClick={() => onChange(opt)}
              style={{
                padding: "4px 12px",
                border: `1px solid ${active ? NAVY : "#d1d5db"}`,
                borderRadius: 4,
                background: active ? NAVY : "#fff",
                color: active ? "#fff" : "#374151",
                fontWeight: active ? 700 : 500,
                fontSize: "0.82em",
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "all 0.12s",
                textTransform: "capitalize",
              }}
            >
              {formatter ? formatter(opt) : opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Memoized financial table ──────────────────────────────────────────────────

const FinTable = memo(function FinTable({
  title, columns, rows, scale,
}: {
  title: string;
  columns: string[];
  rows: FinancialRow[];
  scale: Scale;
}) {
  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "8px 12px", border: "1px solid #2d3f5a",
    fontSize: "0.82em", whiteSpace: "nowrap",
  };

  return (
    <div style={{ marginBottom: 28 }}>
      {/* Section header */}
      <div style={{
        fontSize: "1.05em", fontWeight: "bold", color: "#fff",
        background: NAVY, padding: "6px 15px", borderRadius: 4,
        marginBottom: 6,
      }}>
        {title}
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
          <thead>
            <tr>
              <th style={{ ...thBase, textAlign: "left", minWidth: 200 }}>Item</th>
              {columns.map((col) => (
                <th key={col} style={{ ...thBase, textAlign: "right", minWidth: 88 }}>
                  {col === "TTM"
                    ? <span style={{ color: "#93c5fd" }}>TTM</span>
                    : col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={row.label} style={{ background: ri % 2 === 1 ? "#f8fafc" : "#fff" }}>
                <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY, whiteSpace: "nowrap" }}>
                  {row.label}
                </td>
                {columns.map((col) => {
                  const { text, negative } = fCell(row[col] as number | null, row.label, scale);
                  return (
                    <td key={col} style={{
                      padding: "7px 12px", border: "1px solid #e5e7eb",
                      textAlign: "right",
                      fontVariantNumeric: "tabular-nums",
                      fontFamily: "'Courier New', monospace",
                      color: negative ? "#dc2626" : NAVY,
                      fontWeight: col === "TTM" ? 700 : 400,
                      background: col === "TTM" ? "#eff6ff" : undefined,
                    }}>
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "40px 0", color: "#6b7280" }}>
      <div style={{
        width: 28, height: 28, borderRadius: "50%",
        border: "3px solid #e5e7eb", borderTop: `3px solid ${NAVY}`,
        animation: "gvFinSpin 0.75s linear infinite", flexShrink: 0,
      }} />
      <span style={{ fontSize: "0.88em" }}>{label}</span>
      <style>{`@keyframes gvFinSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Main component (presentational — no fetching) ─────────────────────────────

export interface FinancialsTabProps {
  data: FinancialsData | null;
  loading: boolean;
  period: Period;
  scale: Scale;
  onPeriodChange: (p: Period) => void;
  onScaleChange:  (s: Scale)  => void;
}

export default function FinancialsTab({
  data, loading, period, scale, onPeriodChange, onScaleChange,
}: FinancialsTabProps) {
  return (
    <div>
      {/* Controls bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap",
        marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid #e5e7eb",
      }}>
        <RadioGroup<Period>
          label="Period"
          options={PERIODS}
          value={period}
          onChange={onPeriodChange}
          formatter={(v) => v === "annual" ? "Annual" : "Quarterly"}
        />
        <RadioGroup<Scale>
          label="Scale"
          options={SCALES}
          value={scale}
          onChange={onScaleChange}
        />
        {data && (
          <span style={{ fontSize: "0.78em", color: "#6b7280", marginLeft: "auto" }}>
            Currency: <strong>{data.currency}</strong>
            &nbsp;·&nbsp;values in <strong>{scale}</strong>
          </span>
        )}
      </div>

      {loading && <Spinner label="Loading financials…" />}

      {data && !loading && (
        <>
          <FinTable title="Income Statement" columns={data.columns} rows={data.income_statement} scale={scale} />
          <FinTable title="Balance Sheet"    columns={data.columns} rows={data.balance_sheet}    scale={scale} />
          <FinTable title="Cash Flow"        columns={data.columns} rows={data.cash_flow}        scale={scale} />
          {data.debt && data.debt.length > 0 && (
            <FinTable title="Debt Schedule" columns={data.columns} rows={data.debt} scale={scale} />
          )}
        </>
      )}
    </div>
  );
}
