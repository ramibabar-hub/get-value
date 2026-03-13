/**
 * LanguageSelector.tsx
 *
 * Language preference UI. English is the only active language in v6.5.
 * All other languages show "Soon" and are disabled.
 * Preference persisted to localStorage["gv_lang"].
 */
import { useState, useRef, useEffect } from "react";

const LANGUAGES = [
  { code: "en", label: "English",  flag: "🇺🇸", active: true  },
  { code: "he", label: "Hebrew",   flag: "🇮🇱", active: false },
  { code: "es", label: "Spanish",  flag: "🇪🇸", active: false },
  { code: "ru", label: "Russian",  flag: "🇷🇺", active: false },
  { code: "fr", label: "French",   flag: "🇫🇷", active: false },
  { code: "zh", label: "Mandarin", flag: "🇨🇳", active: false },
  { code: "de", label: "German",   flag: "🇩🇪", active: false },
] as const;

type LangCode = typeof LANGUAGES[number]["code"];

function getStoredLang(): LangCode {
  try { return (localStorage.getItem("gv_lang") as LangCode) ?? "en"; }
  catch { return "en"; }
}

export default function LanguageSelector() {
  const [open, setOpen]   = useState(false);
  const [lang, setLang]   = useState<LangCode>(getStoredLang);
  const ref               = useRef<HTMLDivElement>(null);
  const current           = LANGUAGES.find(l => l.code === lang) ?? LANGUAGES[0];

  useEffect(() => {
    if (!open) return;
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  function select(code: LangCode) {
    try { localStorage.setItem("gv_lang", code); } catch { /* ignore */ }
    setLang(code);
    setOpen(false);
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          background: "none", border: "1px solid var(--gv-border)",
          borderRadius: "var(--gv-radius-sm)", padding: "4px 10px",
          cursor: "pointer", fontSize: "0.8em", color: "var(--gv-text)",
          transition: "border-color 0.15s",
        }}
      >
        <span>{current.flag}</span>
        <span style={{ fontWeight: 600 }}>{current.code.toUpperCase()}</span>
        <span style={{ color: "var(--gv-text-muted)", fontSize: "0.8em" }}>▾</span>
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", right: 0,
          background: "var(--gv-surface)",
          border: "1px solid var(--gv-border)",
          borderRadius: "var(--gv-radius)",
          boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
          minWidth: 160, zIndex: 200, overflow: "hidden",
        }}>
          {LANGUAGES.map(l => (
            <button
              key={l.code}
              onClick={() => l.active ? select(l.code) : undefined}
              disabled={!l.active}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                width: "100%", padding: "8px 14px",
                background: l.code === lang ? "var(--gv-green-bg)" : "none",
                border: "none", cursor: l.active ? "pointer" : "default",
                fontSize: "0.82em", color: l.active ? "var(--gv-text)" : "var(--gv-text-muted)",
                gap: 8, textAlign: "left",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span>{l.flag}</span>
                <span style={{ fontWeight: l.code === lang ? 700 : 400 }}>{l.label}</span>
              </span>
              {!l.active && (
                <span style={{
                  fontSize: "0.72em", fontWeight: 600,
                  background: "var(--gv-data-bg)",
                  color: "var(--gv-text-muted)",
                  padding: "1px 6px", borderRadius: 10,
                }}>
                  Soon
                </span>
              )}
              {l.code === lang && l.active && (
                <span style={{ color: "var(--gv-green)", fontWeight: 700 }}>✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
