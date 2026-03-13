import { useState, useEffect } from "react";
import StockDashboard from "./components/StockDashboard";
import GlobalSearchBar from "./components/GlobalSearchBar";

// ── Color palette ─────────────────────────────────────────────────────────────
const NAVY  = "var(--gv-navy)";
const BG    = "var(--gv-bg)";

// ── Session-storage keys (persist view across browser refresh) ─────────────────
const SK_TICKER  = "gv_ticker";   // e.g. "AAPL"
const SK_VERSION = "gv_ss_ver";
const SS_VERSION = "4";

function migrateSessionStorage() {
  if (sessionStorage.getItem(SK_VERSION) !== SS_VERSION) {
    sessionStorage.removeItem(SK_TICKER);
    sessionStorage.setItem(SK_VERSION, SS_VERSION);
  }
}

export default function App() {
  const [activeTicker, setActiveTicker] = useState<string | null>(null);

  // On first mount: wipe stale sessions, then restore ticker if present
  useEffect(() => {
    migrateSessionStorage();
    const ticker = sessionStorage.getItem(SK_TICKER);
    if (ticker) setActiveTicker(ticker);
  }, []);

  const handleSearch = (ticker: string | null) => {
    if (ticker) sessionStorage.setItem(SK_TICKER, ticker);
    else        sessionStorage.removeItem(SK_TICKER);
    setActiveTicker(ticker);
  };

  // ── Stock dashboard view ─────────────────────────────────────────────────────
  if (activeTicker) {
    return (
      <StockDashboard
        ticker={activeTicker}
        onSearch={handleSearch}
      />
    );
  }

  // ── Landing page ────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight:      "100vh",
        background:     BG,
        display:        "flex",
        flexDirection:  "column",
        alignItems:     "center",
        justifyContent: "center",
        fontFamily:     "'Segoe UI', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Brand */}
      <div style={{ marginBottom: 12 }}>
        <img src="/logo.svg" alt="getValue" style={{ height: 52, display: "block" }} />
      </div>

      {/* Headline */}
      <h1
        style={{
          fontSize:   "clamp(1.6em, 4vw, 2.4em)",
          fontWeight: 700,
          color:      NAVY,
          margin:     "0 0 36px",
          textAlign:  "center",
        }}
      >
        Hi Rami, Let&apos;s get Value
      </h1>

      {/* Smart search bar */}
      <div style={{ width: "100%", maxWidth: 520, padding: "0 16px", boxSizing: "border-box" }}>
        <GlobalSearchBar onSelect={(t) => t && handleSearch(t)} />
      </div>

      {/* Hint */}
      <p style={{ marginTop: 14, fontSize: "0.78em", color: "var(--gv-text-muted)" }}>
        US stocks · International: NICE.TA · BMW.DE · VOD.L
      </p>

    </div>
  );
}
// Force redeploy: Wed, Mar 11, 2026  5:09:31 PM
// Build trigger: Wed, Mar 11, 2026  5:35:52 PM
