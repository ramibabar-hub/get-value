/**
 * FinancialsTab.tsx
 * Pure presentational component — all data is passed in as props.
 * Shows Income Statement, Balance Sheet, Cash Flow, Debt Schedule,
 * then Market & Valuation, Capital Structure, Profitability, Returns,
 * Liquidity, Dividends, Efficiency.
 */
import { memo, useState, Fragment } from "react";
import type {
  FinancialsData, FinancialRow, FinancialsExtendedData, ExtRow, FmtType, Scale, Period,
} from "../types";

const NAVY    = "#1c2b46";
const PERIODS: Period[] = ["annual", "quarterly"];
const SCALES:  Scale[]  = ["K", "MM", "B"];
const EPS_LABELS = new Set(["eps", "epsdiluted", "noi/sh", "ffo/sh"]);

// ── Formatters ────────────────────────────────────────────────────────────────

function isEps(label: string): boolean {
  return EPS_LABELS.has(label.toLowerCase().replace(/[^a-z]/g, ""));
}

function fCell(
  v: number | string | null | undefined,
  label: string,
  scale: Scale,
): { text: string; negative: boolean } {
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

function fExtCell(
  v: number | string | null | undefined,
  fmt: FmtType,
  scale: Scale,
): { text: string; negative: boolean } {
  if (v == null || v === "") return { text: "—", negative: false };
  if (typeof v === "string") return { text: v,   negative: false };
  if (!isFinite(v))          return { text: "—", negative: false };
  const neg = v < 0;
  const abs = Math.abs(v);
  let text: string;
  switch (fmt) {
    case "money": {
      const div = scale === "K" ? 1e3 : scale === "MM" ? 1e6 : 1e9;
      const scaled = abs / div;
      text = scaled.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
      text = neg ? `(${text})` : text;
      break;
    }
    case "pct":
      text = `${(v * 100).toFixed(1)}%`;
      break;
    case "days":
      text = abs.toFixed(1);
      if (neg) text = `(${text})`;
      break;
    case "int":
      text = Math.round(v).toString();
      break;
    default: // ratio
      text = abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      if (neg) text = `(${text})`;
  }
  return { text, negative: neg };
}

// ── Chart helpers ─────────────────────────────────────────────────────────────

function ChartIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor" style={{ display: "block", flexShrink: 0 }}>
      <rect x="0" y="7" width="3.5" height="6" rx="0.5"/>
      <rect x="4.75" y="3.5" width="3.5" height="9.5" rx="0.5"/>
      <rect x="9.5" y="0.5" width="3.5" height="12.5" rx="0.5"/>
    </svg>
  );
}

function MiniChart({
  cols, vals, isBar,
}: {
  cols: string[];
  vals: (number | null | string)[];
  isBar: boolean;
}) {
  const nums = vals.map(v => (typeof v === "number" && isFinite(v)) ? v : null);
  const nonNull = nums.filter((v): v is number => v !== null);
  if (nonNull.length === 0) {
    return <div style={{ padding: "12px 16px", color: "#9ca3af", fontSize: "0.8em" }}>No chart data</div>;
  }

  const N   = cols.length;
  const VW  = Math.max(N * 55, 280);
  const VH  = 110;
  const PL = 4, PR = 4, PT = 10, PB = 26;
  const cW  = VW - PL - PR;
  const cH  = VH - PT - PB;

  const rawMin = Math.min(...nonNull);
  const rawMax = Math.max(...nonNull);
  const vMin   = Math.min(0, rawMin);
  const vMaxRaw = Math.max(0, rawMax);
  const vMax   = vMaxRaw === vMin ? vMin + 1 : vMaxRaw;
  const range  = vMax - vMin;

  const toY    = (v: number) => PT + cH - ((v - vMin) / range) * cH;
  const zeroY  = toY(0);
  const bW     = cW / N;
  const colX   = (i: number) => PL + i * bW;
  const shortLbl = (c: string) => c === "TTM" ? "TTM" : c.length > 4 ? c.slice(-4) : c;

  if (isBar) {
    return (
      <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
        <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="#e5e7eb" strokeWidth="1"/>
        {nums.map((v, i) => {
          if (v === null) return null;
          const isTtm = cols[i] === "TTM";
          const x  = colX(i) + bW * 0.1;
          const w  = bW * 0.8;
          const top = v >= 0 ? toY(v) : zeroY;
          const h   = Math.max(Math.abs(toY(v) - zeroY), 1);
          const fill = isTtm ? "#3b82f6" : v < 0 ? "#ef4444" : NAVY;
          return (
            <g key={i}>
              <rect x={x} y={top} width={w} height={h} fill={fill} opacity={isTtm ? 1 : 0.72}/>
              <text x={x + w / 2} y={VH - 4} textAnchor="middle" fontSize="8" fill="#9ca3af">{shortLbl(cols[i])}</text>
            </g>
          );
        })}
      </svg>
    );
  }

  // Line chart
  const pts = nums
    .map((v, i) => v !== null ? { x: PL + (i + 0.5) * bW, y: toY(v), col: cols[i] } : null)
    .filter(Boolean) as { x: number; y: number; col: string }[];
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ display: "block" }}>
      <line x1={PL} y1={zeroY} x2={VW - PR} y2={zeroY} stroke="#e5e7eb" strokeWidth="1"/>
      {d && <path d={d} fill="none" stroke={NAVY} strokeWidth="1.5" opacity="0.7"/>}
      {pts.map((p, i) => {
        const isTtm = p.col === "TTM";
        return (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={isTtm ? 4 : 2.5} fill={isTtm ? "#3b82f6" : NAVY}/>
            <text x={p.x} y={VH - 4} textAnchor="middle" fontSize="8" fill="#9ca3af">{shortLbl(p.col)}</text>
          </g>
        );
      })}
    </svg>
  );
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

// ── Core financial table (IS/BS/CF/Debt) ──────────────────────────────────────

const FinTable = memo(function FinTable({
  title, columns, rows, scale,
}: {
  title: string;
  columns: string[];
  rows: FinancialRow[];
  scale: Scale;
}) {
  const [openRow, setOpenRow] = useState<string | null>(null);

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "8px 12px", border: "1px solid #2d3f5a",
    fontSize: "0.82em", whiteSpace: "nowrap",
  };
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6 }}>
        {title}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
          <thead>
            <tr>
              <th style={{ ...thBase, textAlign: "left", minWidth: 200 }}>Item</th>
              {columns.map((col) => (
                <th key={col} style={{ ...thBase, textAlign: "right", minWidth: 88 }}>
                  {col === "TTM" ? <span style={{ color: "#93c5fd" }}>TTM</span> : col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => {
              const isOpen = openRow === row.label;
              const vals   = columns.map(col => row[col] as number | null);
              return (
                <Fragment key={row.label}>
                  <tr style={{ background: ri % 2 === 1 ? "#f8fafc" : "#fff" }}>
                    <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY, whiteSpace: "nowrap" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          onClick={() => setOpenRow(isOpen ? null : row.label)}
                          title="Toggle chart"
                          style={{
                            background: "none", border: "none", padding: 2, cursor: "pointer",
                            color: isOpen ? "#3b82f6" : "#9ca3af", lineHeight: 0,
                            borderRadius: 3, flexShrink: 0,
                          }}
                        >
                          <ChartIcon />
                        </button>
                        {row.label}
                      </div>
                    </td>
                    {columns.map((col) => {
                      const { text, negative } = fCell(row[col] as number | null, row.label, scale);
                      return (
                        <td key={col} style={{
                          padding: "7px 12px", border: "1px solid #e5e7eb",
                          textAlign: "right", fontVariantNumeric: "tabular-nums",
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
                  {isOpen && (
                    <tr>
                      <td colSpan={columns.length + 1} style={{ padding: "8px 16px", border: "1px solid #e5e7eb", background: "#f8fafc" }}>
                        <MiniChart cols={columns} vals={vals} isBar={true} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
});

// ── Extended metric table (Market & Val, Cap Structure, etc.) ─────────────────

const ExtTable = memo(function ExtTable({
  title, columns, rows, scale,
}: {
  title: string;
  columns: string[];
  rows: ExtRow[];
  scale: Scale;
}) {
  const [openRow, setOpenRow] = useState<number | null>(null);

  const thBase: React.CSSProperties = {
    background: NAVY, color: "#fff", fontWeight: 700,
    padding: "8px 12px", border: "1px solid #2d3f5a",
    fontSize: "0.82em", whiteSpace: "nowrap",
  };
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ fontSize: "1.05em", fontWeight: "bold", color: "#fff", background: NAVY, padding: "6px 15px", borderRadius: 4, marginBottom: 6 }}>
        {title}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83em" }}>
          <thead>
            <tr>
              <th style={{ ...thBase, textAlign: "left", minWidth: 240 }}>Metric</th>
              {columns.map((col) => (
                <th key={col} style={{ ...thBase, textAlign: "right", minWidth: 88 }}>
                  {col === "TTM" ? <span style={{ color: "#93c5fd" }}>TTM</span> : col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => {
              const isOpen = openRow === ri;
              const fmt    = row.fmt as FmtType;
              const isBar  = fmt === "money" || fmt === "int";
              const vals   = columns.map(col => row[col] as number | string | null);
              return (
                <Fragment key={ri}>
                  <tr style={{ background: ri % 2 === 1 ? "#f8fafc" : "#fff" }}>
                    <td style={{ padding: "7px 12px", border: "1px solid #e5e7eb", fontWeight: 600, color: NAVY, whiteSpace: "nowrap" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          onClick={() => setOpenRow(isOpen ? null : ri)}
                          title="Toggle chart"
                          style={{
                            background: "none", border: "none", padding: 2, cursor: "pointer",
                            color: isOpen ? "#3b82f6" : "#9ca3af", lineHeight: 0,
                            borderRadius: 3, flexShrink: 0,
                          }}
                        >
                          <ChartIcon />
                        </button>
                        {row.label}
                      </div>
                    </td>
                    {columns.map((col) => {
                      const { text, negative } = fExtCell(
                        row[col] as number | string | null,
                        fmt,
                        scale,
                      );
                      return (
                        <td key={col} style={{
                          padding: "7px 12px", border: "1px solid #e5e7eb",
                          textAlign: "right", fontVariantNumeric: "tabular-nums",
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
                  {isOpen && (
                    <tr>
                      <td colSpan={columns.length + 1} style={{ padding: "8px 16px", border: "1px solid #e5e7eb", background: "#f8fafc" }}>
                        <MiniChart cols={columns} vals={vals} isBar={isBar} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
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

// ── Main component ────────────────────────────────────────────────────────────

export interface FinancialsTabProps {
  data: FinancialsData | null;
  loading: boolean;
  extData: FinancialsExtendedData | null;
  extLoading: boolean;
  period: Period;
  scale: Scale;
  onPeriodChange: (p: Period) => void;
  onScaleChange:  (s: Scale)  => void;
}

export default function FinancialsTab({
  data, loading, extData, extLoading, period, scale, onPeriodChange, onScaleChange,
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
            <FinTable title="Debt Schedule"  columns={data.columns} rows={data.debt}             scale={scale} />
          )}
        </>
      )}

      {extLoading && !loading && <Spinner label="Loading metric tables…" />}

      {extData && !extLoading && (
        <>
          <ExtTable title="Market & Valuation"  columns={extData.columns} rows={extData.market_valuation}  scale={scale} />
          <ExtTable title="Capital Structure"    columns={extData.columns} rows={extData.capital_structure} scale={scale} />
          <ExtTable title="Profitability"        columns={extData.columns} rows={extData.profitability}     scale={scale} />
          <ExtTable title="Returns"              columns={extData.columns} rows={extData.returns}           scale={scale} />
          <ExtTable title="Liquidity"            columns={extData.columns} rows={extData.liquidity}         scale={scale} />
          <ExtTable title="Dividends"            columns={extData.columns} rows={extData.dividends}         scale={scale} />
          <ExtTable title="Efficiency"           columns={extData.columns} rows={extData.efficiency}        scale={scale} />
        </>
      )}
    </div>
  );
}
