/**
 * TableToolbar.tsx
 *
 * Compact right-aligned toolbar for financial data tables.
 * Provides: Search/filter · Export Excel (.xlsx) · Copy TSV · Expand fullscreen
 *
 * Icons:  lucide-react  (already a project dependency)
 * Export: SheetJS xlsx  (npm install xlsx)
 */

import { useState, useEffect } from "react";
import {
  Search, Download, Copy, Check,
  Maximize2, Minimize2, X,
} from "lucide-react";

const NAVY = "var(--gv-navy)";

// ── Tool button ───────────────────────────────────────────────────────────────

interface ToolBtnProps {
  title:    string;
  active?:  boolean;
  onClick:  () => void;
  children: React.ReactNode;
}

function ToolBtn({ title, active = false, onClick, children }: ToolBtnProps) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        border:         `1px solid ${active ? NAVY : "var(--gv-border)"}`,
        borderRadius:   6,
        background:     active ? NAVY : "#fafafa",
        color:          active ? "#fff" : "var(--gv-text-muted)",
        width:          28,
        height:         28,
        display:        "inline-flex",
        alignItems:     "center",
        justifyContent: "center",
        cursor:         "pointer",
        padding:        0,
        flexShrink:     0,
        transition:     "all 0.12s",
      }}
    >
      {children}
    </button>
  );
}

// ── Expand overlay ─────────────────────────────────────────────────────────────

export interface ExpandOverlayProps {
  title:    string;
  onClose:  () => void;
  children: React.ReactNode;
}

export function ExpandOverlay({ title, onClose, children }: ExpandOverlayProps) {
  // Close on Escape
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      style={{
        position:   "fixed",
        inset:      0,
        zIndex:     9999,
        background: "rgba(0,0,0,0.52)",
        display:    "flex",
        alignItems: "flex-start",
        padding:    "24px 20px",
        overflow:   "auto",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background:   "#fff",
          borderRadius: 10,
          width:        "100%",
          maxWidth:     1440,
          boxShadow:    "0 24px 80px rgba(0,0,0,0.32)",
          padding:      "18px 24px",
          margin:       "0 auto",
        }}
      >
        {/* Header */}
        <div style={{
          display:        "flex",
          justifyContent: "space-between",
          alignItems:     "center",
          marginBottom:   14,
          paddingBottom:  12,
          borderBottom:   "1px solid #e5e7eb",
        }}>
          <span style={{ fontWeight: 700, fontSize: "1.0em", color: NAVY }}>{title}</span>
          <button
            onClick={onClose}
            style={{
              border:       "1px solid #e5e7eb",
              borderRadius: 6,
              background:   "#fff",
              color:        "var(--gv-text-muted)",
              padding:      "4px 12px",
              cursor:       "pointer",
              fontWeight:   600,
              fontSize:     "0.83em",
              fontFamily:   "inherit",
              display:      "inline-flex",
              alignItems:   "center",
              gap:          4,
            }}
          >
            <X size={13} strokeWidth={2.5} /> Close
          </button>
        </div>

        {children}
      </div>
    </div>
  );
}

// ── Main toolbar ──────────────────────────────────────────────────────────────

export interface TableToolbarProps {
  title:          string;
  searchActive:   boolean;
  searchValue:    string;
  onToggleSearch: () => void;
  onSearchChange: (v: string) => void;
  /** Caller handles xlsx Blob creation and file download */
  onDownload:     () => void;
  /** Caller handles writing TSV to clipboard; may be async */
  onCopy:         () => Promise<void> | void;
  onToggleExpand: () => void;
  isExpanded:     boolean;
}

export function TableToolbar({
  searchActive,
  searchValue,
  onToggleSearch,
  onSearchChange,
  onDownload,
  onCopy,
  onToggleExpand,
  isExpanded,
}: TableToolbarProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div style={{
      display:        "flex",
      alignItems:     "center",
      justifyContent: "flex-end",
      gap:            4,
      marginBottom:   5,
    }}>
      {searchActive && (
        <input
          autoFocus
          placeholder="Filter rows…"
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          style={{
            border:       "1px solid #d1d5db",
            borderRadius: 5,
            padding:      "3px 10px",
            fontSize:     "0.78em",
            outline:      "none",
            width:        160,
            fontFamily:   "inherit",
            color:        NAVY,
          }}
        />
      )}

      <ToolBtn
        title="Filter rows"
        active={searchActive}
        onClick={onToggleSearch}
      >
        <Search size={13} strokeWidth={2.5} />
      </ToolBtn>

      <ToolBtn title="Export to Excel (.xlsx)" onClick={onDownload}>
        <Download size={13} strokeWidth={2.5} />
      </ToolBtn>

      <ToolBtn
        title={copied ? "Copied!" : "Copy table (Excel-compatible TSV)"}
        onClick={handleCopy}
        active={copied}
      >
        {copied
          ? <Check   size={13} strokeWidth={2.5} />
          : <Copy    size={13} strokeWidth={2.5} />
        }
      </ToolBtn>

      <ToolBtn
        title={isExpanded ? "Exit fullscreen" : "Expand table"}
        onClick={onToggleExpand}
        active={isExpanded}
      >
        {isExpanded
          ? <Minimize2 size={13} strokeWidth={2.5} />
          : <Maximize2 size={13} strokeWidth={2.5} />
        }
      </ToolBtn>
    </div>
  );
}
