import { useState } from "react";
import StockDashboard from "./components/StockDashboard";

// ── Color palette ─────────────────────────────────────────────────────────────
const BLUE  = "#007bff";
const NAVY  = "#1c2b46";
const BG    = "#f0f2f5";

export default function App() {
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [query, setQuery]               = useState("");

  function handleSearch() {
    const t = query.trim().toUpperCase();
    if (t) {
      setActiveTicker(t);
      setQuery("");
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSearch();
  }

  // ── Dashboard view ──────────────────────────────────────────────────────────
  if (activeTicker) {
    return <StockDashboard ticker={activeTicker} onSearch={setActiveTicker} />;
  }

  // ── Landing page ────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight: "100vh",
        background: BG,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Brand */}
      <div style={{ marginBottom: 12 }}>
        <span style={{ color: BLUE,  fontWeight: 900, fontSize: "1.6em", letterSpacing: "-0.02em" }}>get</span>
        <span style={{ color: NAVY, fontWeight: 900, fontSize: "1.6em", letterSpacing: "-0.02em" }}>Value</span>
      </div>

      {/* Headline */}
      <h1
        style={{
          fontSize: "clamp(1.6em, 4vw, 2.4em)",
          fontWeight: 700,
          color: NAVY,
          margin: "0 0 36px",
          textAlign: "center",
        }}
      >
        Hi Rami, Let&apos;s get Value
      </h1>

      {/* Search bar */}
      <div
        style={{
          display: "flex",
          gap: 8,
          width: "100%",
          maxWidth: 520,
          padding: "0 16px",
          boxSizing: "border-box",
        }}
      >
        <input
          autoFocus
          spellCheck={false}
          autoComplete="off"
          placeholder="Search company or ticker… (e.g. AAPL, NICE.TA)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
          style={{
            flex: 1,
            padding: "14px 18px",
            fontSize: "1em",
            border: "1.5px solid #d1d5db",
            borderRadius: 8,
            outline: "none",
            background: "#fff",
            color: NAVY,
            boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
          }}
        />
        <button
          onClick={handleSearch}
          style={{
            padding: "14px 24px",
            background: BLUE,
            color: "#fff",
            border: "none",
            borderRadius: 8,
            fontWeight: 700,
            fontSize: "0.95em",
            cursor: "pointer",
            whiteSpace: "nowrap",
            boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
          }}
        >
          Analyze →
        </button>
      </div>

      {/* Hint */}
      <p style={{ marginTop: 14, fontSize: "0.78em", color: "#9ca3af" }}>
        US stocks · International: NICE.TA · BMW.DE · VOD.L
      </p>
    </div>
  );
}
