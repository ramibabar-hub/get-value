import { useState, useRef, useEffect } from "react";
import { Search, X } from "lucide-react";

// ── Color palette ──────────────────────────────────────────────────────────────
const BLUE = "var(--gv-blue)";
const NAVY = "var(--gv-navy)";

// ── Unified result shape (matches /api/search response) ───────────────────────
interface SearchResult {
  ticker:   string;
  name:     string;
  exchange: string;
  country?: string | null;
  type:     "Equity" | "ETF";
}

// ── FMP logo URL (works for most US equities; falls back to letter initial) ────
function fmpLogoUrl(ticker: string) {
  return `https://financialmodelingprep.com/images-symbols/${ticker}.png`;
}

// ── Props ──────────────────────────────────────────────────────────────────────
interface GlobalSearchBarProps {
  onSelect: (ticker: string) => void;
}

// ── Component ──────────────────────────────────────────────────────────────────
export default function GlobalSearchBar({ onSelect }: GlobalSearchBarProps) {
  const [query,     setQuery]     = useState("");
  const [results,   setResults]   = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [noResults, setNoResults] = useState(false);
  const [open,      setOpen]      = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef     = useRef<HTMLInputElement>(null);
  const listRef      = useRef<HTMLDivElement>(null);
  const debounceRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef     = useRef<AbortController | null>(null);

  // ── Debounced live search ─────────────────────────────────────────────────
  useEffect(() => {
    const q = query.trim();

    if (!q) {
      setResults([]); setOpen(false); setNoResults(false); setIsLoading(false);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      return;
    }

    setIsLoading(true);
    setNoResults(false);
    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      const { signal } = abortRef.current;

      try {
        const r = await fetch(
          `/api/search?q=${encodeURIComponent(q)}&limit=8`,
          { signal }
        );
        if (!r.ok) throw new Error("search failed");
        const hits: SearchResult[] = await r.json();
        setResults(hits);
        setNoResults(hits.length === 0);
        setOpen(hits.length > 0);
        setActiveIdx(-1);
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        setResults([]);
        setNoResults(true);
        setOpen(false);
      } finally {
        setIsLoading(false);
      }
    }, 400);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // ── Close on outside click ────────────────────────────────────────────────
  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setNoResults(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  // ── Scroll active row into view ───────────────────────────────────────────
  useEffect(() => {
    if (activeIdx >= 0 && listRef.current) {
      listRef.current.querySelectorAll<HTMLElement>("[data-row]")[activeIdx]
        ?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIdx]);

  // ── Keyboard navigation ───────────────────────────────────────────────────
  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") { setOpen(false); setNoResults(false); setActiveIdx(-1); return; }

    if (!open) {
      if (e.key === "Enter" && query.trim()) commit(query.trim().toUpperCase());
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0) commit(results[activeIdx].ticker);
      else if (query.trim()) commit(query.trim().toUpperCase());
    }
  }

  function commit(ticker: string) {
    abortRef.current?.abort();
    onSelect(ticker);
    setQuery(""); setResults([]); setOpen(false); setNoResults(false); setActiveIdx(-1);
  }

  function clearQuery() {
    abortRef.current?.abort();
    setQuery(""); setResults([]); setOpen(false); setNoResults(false); setIsLoading(false);
    inputRef.current?.focus();
  }

  const showDropdown = open || (noResults && query.trim().length > 0 && !isLoading);
  const borderRadius = showDropdown ? "10px 10px 0 0" : "10px";
  const focused      = showDropdown || isLoading || query.length > 0;

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%", maxWidth: 520 }}>

      {/* ── Input ─────────────────────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center",
        background: "var(--gv-surface)",
        border: `1.5px solid ${focused ? BLUE : "var(--gv-border)"}`,
        borderRadius,
        padding: "0 14px", gap: 10,
        boxShadow: focused
          ? `0 0 0 3px ${BLUE}22, var(--gv-shadow-sm)`
          : "var(--gv-shadow-sm)",
        transition: "border-color 0.15s, box-shadow 0.15s, border-radius 0.1s",
      }}>
        {isLoading
          ? <Spinner />
          : <Search size={17} color={focused ? BLUE : "var(--gv-text-muted)"} style={{ flexShrink: 0, transition: "color 0.15s" }} />
        }
        <input
          ref={inputRef}
          autoFocus spellCheck={false} autoComplete="off"
          placeholder="Search company or ticker…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => (results.length > 0 || noResults) && setOpen(results.length > 0)}
          style={{
            flex: 1, padding: "14px 0", fontSize: "1em",
            border: "none", outline: "none", background: "transparent",
            color: NAVY, fontFamily: "inherit",
          }}
        />
        {query && (
          <button onClick={clearQuery} style={{
            background: "none", border: "none", cursor: "pointer",
            padding: 2, color: "var(--gv-text-muted)", display: "flex", alignItems: "center",
          }}>
            <X size={14} />
          </button>
        )}
      </div>

      {/* ── Dropdown ──────────────────────────────────────────────────────── */}
      {showDropdown && (
        <div ref={listRef} style={{
          position: "absolute", top: "100%", left: 0, right: 0,
          background: "var(--gv-surface)",
          border: `1.5px solid ${BLUE}`, borderTop: "none",
          borderRadius: "0 0 10px 10px",
          maxHeight: 400, overflowY: "auto",
          zIndex: 1000,
          boxShadow: "var(--gv-shadow-lg)",
        }}>

          {/* Results */}
          {results.map((r, i) => (
            <ResultRow
              key={r.ticker + i}
              result={r}
              active={i === activeIdx}
              query={query}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => commit(r.ticker)}
            />
          ))}

          {/* No results */}
          {noResults && (
            <div style={{
              padding: "16px 20px", textAlign: "center",
              color: "var(--gv-text-muted)", fontSize: "0.85em",
            }}>
              No results found for&nbsp;
              <strong style={{ color: "var(--gv-text)" }}>&ldquo;{query.trim()}&rdquo;</strong>
              <br />
              <span style={{ fontSize: "0.88em" }}>
                Try pressing Enter to search directly by ticker
              </span>
            </div>
          )}

          {/* Footer */}
          {results.length > 0 && (
            <div style={{
              padding: "6px 16px", fontSize: "0.71em", color: "var(--gv-text-muted)",
              borderTop: "1px solid var(--gv-border)", display: "flex", alignItems: "center", gap: 6,
            }}>
              <Kbd>↑↓</Kbd> navigate &nbsp;·&nbsp; <Kbd>Enter</Kbd> select
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Result row ─────────────────────────────────────────────────────────────────
function ResultRow({ result, active, query, onMouseEnter, onClick }: {
  result: SearchResult; active: boolean; query: string;
  onMouseEnter: () => void; onClick: () => void;
}) {
  const [logoFailed, setLogoFailed] = useState(false);
  const initial   = result.name.charAt(0).toUpperCase();
  const avatarBg  = active ? BLUE : NAVY;

  return (
    <div
      data-row=""
      onMouseEnter={onMouseEnter}
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "9px 16px", cursor: "pointer",
        background: active ? "color-mix(in srgb, var(--gv-blue) 10%, var(--gv-surface))" : "transparent",
        borderLeft: `3px solid ${active ? BLUE : "transparent"}`,
        transition: "background 0.1s, border-color 0.1s",
      }}
    >
      {/* Logo / avatar */}
      <div style={{
        width: 36, height: 36, borderRadius: "50%",
        background: avatarBg,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0, fontSize: "0.88em", fontWeight: 700, color: "#fff",
        overflow: "hidden", transition: "background 0.15s",
      }}>
        {!logoFailed ? (
          <img
            src={fmpLogoUrl(result.ticker)}
            alt=""
            onError={() => setLogoFailed(true)}
            style={{ width: 36, height: 36, objectFit: "cover" }}
          />
        ) : initial}
      </div>

      {/* Name + ticker */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{
            fontWeight: 600, color: "var(--gv-text)", fontSize: "0.88em",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 220,
          }}>
            <HighlightMatch text={result.name} query={query} />
          </span>
          <span style={{
            background: active ? BLUE : "color-mix(in srgb, var(--gv-blue) 12%, var(--gv-surface))",
            color: active ? "#fff" : BLUE,
            fontSize: "0.67em", fontWeight: 700, letterSpacing: "0.04em",
            padding: "2px 7px", borderRadius: 4, flexShrink: 0,
            fontFamily: "monospace",
            transition: "background 0.15s, color 0.15s",
          }}>
            {result.ticker}
          </span>
        </div>
        <div style={{ fontSize: "0.74em", color: "#7b8899", marginTop: 2 }}>
          {result.exchange}
          {result.country && <>&nbsp;·&nbsp;{result.country}</>}
        </div>
      </div>

      {/* Type badge */}
      <span style={{
        fontSize: "0.64em", fontWeight: 700, letterSpacing: "0.06em",
        padding: "2px 8px", borderRadius: 4, flexShrink: 0,
        background: result.type === "ETF" ? "#fef3c7" : "#e8f8f0",
        color:      result.type === "ETF" ? "#92400e" : "#166534",
      }}>
        {result.type}
      </span>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <div style={{
      width: 17, height: 17, flexShrink: 0,
      border: `2px solid ${BLUE}33`, borderTopColor: BLUE,
      borderRadius: "50%", animation: "gsb-spin 0.7s linear infinite",
    }}>
      <style>{`@keyframes gsb-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd style={{
      background: "#f0f2f5", border: "1px solid #e2e5eb",
      borderRadius: 3, padding: "1px 5px", fontSize: "0.85em", fontFamily: "monospace",
    }}>
      {children}
    </kbd>
  );
}

function HighlightMatch({ text, query }: { text: string; query: string }) {
  const q = query.trim().toLowerCase();
  if (!q) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(q);
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark style={{ background: "#cce5ff", color: NAVY, borderRadius: 2, padding: "0 1px" }}>
        {text.slice(idx, idx + q.length)}
      </mark>
      {text.slice(idx + q.length)}
    </>
  );
}
