import { useState, useEffect } from "react";
import StockDashboard from "./components/StockDashboard";
import GlobalSearchBar from "./components/GlobalSearchBar";
import DarkModeToggle, { useDarkMode } from "./components/DarkModeToggle";

// ── Session-storage keys (persist view across browser refresh) ─────────────────
const SK_TICKER  = "gv_ticker";   // e.g. "AAPL"
const SK_VERSION = "gv_ss_ver";
const SS_VERSION = "5";

function migrateSessionStorage() {
  if (sessionStorage.getItem(SK_VERSION) !== SS_VERSION) {
    sessionStorage.removeItem(SK_TICKER);
    sessionStorage.setItem(SK_VERSION, SS_VERSION);
  }
}

export default function App() {
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const { dark } = useDarkMode(); // initialize dark mode from localStorage on mount

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
        background:     "var(--gv-bg)",
        display:        "flex",
        flexDirection:  "column",
        alignItems:     "center",
        justifyContent: "center",
        fontFamily:     "var(--gv-font)",
        position:       "relative",
      }}
    >
      {/* Dark mode toggle — top right */}
      <div style={{ position: "absolute", top: 20, right: 24 }}>
        <DarkModeToggle size="md" />
      </div>

      {/* Subtle background grid lines — premium feel */}
      <div
        aria-hidden
        style={{
          position:   "absolute",
          inset:      0,
          backgroundImage: dark
            ? "linear-gradient(rgba(77,148,232,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(77,148,232,0.04) 1px, transparent 1px)"
            : "linear-gradient(rgba(15,30,53,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(15,30,53,0.04) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          pointerEvents: "none",
        }}
      />

      {/* Content */}
      <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
        {/* Brand */}
        <div style={{ marginBottom: 16 }}>
          <img src="/logo.svg" alt="getValue" style={{ height: 56, display: "block" }} />
        </div>

        {/* Headline */}
        <h1
          style={{
            fontSize:    "clamp(1.5em, 4vw, 2.2em)",
            fontWeight:  700,
            color:       "var(--gv-text)",
            margin:      "0 0 10px",
            textAlign:   "center",
            letterSpacing: "-0.02em",
            fontFamily:  "var(--gv-font)",
          }}
        >
          Hi Rami, Let&apos;s get Value
        </h1>

        {/* Subtitle */}
        <p style={{
          fontSize:    "0.88em",
          color:       "var(--gv-text-muted)",
          margin:      "0 0 36px",
          letterSpacing: "0.01em",
          fontWeight:  500,
        }}>
          Deep fundamental analysis · Global equities
        </p>

        {/* Smart search bar */}
        <div style={{ width: "100%", maxWidth: 540, padding: "0 16px", boxSizing: "border-box" }}>
          <GlobalSearchBar onSelect={(t) => t && handleSearch(t)} />
        </div>

        {/* Hint */}
        <p style={{
          marginTop:   16,
          fontSize:    "0.74em",
          color:       "var(--gv-text-dim)",
          letterSpacing: "0.02em",
          textAlign:   "center",
        }}>
          US stocks · International: NICE.TA · BMW.DE · VOD.L
        </p>
      </div>
    </div>
  );
}
// Force redeploy: Wed, Mar 11, 2026  5:09:31 PM
// Build trigger: Wed, Mar 11, 2026  5:35:52 PM
