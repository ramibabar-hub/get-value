# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this project is

**getValue** — a personal stock analysis tool built by Rami for deep-dive fundamental analysis of global equities.

Two parallel UI implementations exist and are both maintained:

1. **Streamlit app** (`app.py`) — original production UI. Runs locally with `streamlit run app.py`.
2. **React + FastAPI** (`frontend/` + `backend/`) — primary active implementation. FastAPI serves financial data via REST; React renders the dashboard.

Both UIs share the same Python agent layer (`agents/`) and data normalisation logic.

---

## Running the project

### FastAPI backend
```bash
uvicorn backend.main:app --reload
```
Runs on `http://localhost:8000`. API docs at `/docs`.

### React frontend
```bash
cd frontend
npm install
npm run dev        # dev server at http://localhost:5173
npm run build      # tsc -b && vite build  (always run to confirm no TS errors)
npm run lint       # ESLint
```

Vite dev server proxies all `/api/*` requests to `http://localhost:8000` — no CORS issues in dev.

### Streamlit (original UI)
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Architecture

### Data flow

```
User enters ticker
      │
      ▼
SmartGateway  (backend/services/gateway.py)
      │
      ├── US tickers (no dot suffix)  → FMPService  (fmp_service.py)
      └── Intl tickers (dot suffix)   → EODHDService (eodhd_service.py)
                                          └── Fallback: FMPService for profile/overview
                                          └── Fallback: EOD historical endpoint for price
      │
      ▼
DataNormalizer  (agents/core_agent.py)
  Wraps raw_data dict — helpers for TTM, column headers, per-period values.
      │
      ▼
ProfileAgent / InsightsAgent  (agents/)
  Build the 15-cell header grid, CAGR tables, WACC, valuation multiples.
      │
      ▼
backend/main.py  (FastAPI endpoints)  /  app.py  (Streamlit tabs)
```

### Key routing rule (SmartGateway)
- Tickers **without** a dot suffix (`AAPL`, `MSFT`) → FMP primary
- Tickers **with** a recognised suffix (`NICE.TA`, `BMW.DE`, `VOD.L`) → EODHD primary, FMP fallback for profile
- Exchange suffix map lives in `backend/services/gateway.py` (`_FMP_SUFFIX_TO_EODHD`)
- Israel: `TA` suffix maps to EODHD exchange code `"TA"` (NOT `"IT"`)

### Skeleton fallback
When both EODHD fundamentals (403) and FMP income statements (402) are blocked for an international ticker, `backend/main.py` returns a zero-filled 10-year skeleton (2016–2025) so the Financials tab renders columns instead of a 404.

### Canonical `raw_data` dict keys
All agents and endpoints expect this shape from `fetch_all()`:
```
annual_income_statement    quarterly_income_statement
annual_balance_sheet       quarterly_balance_sheet
annual_cash_flow           quarterly_cash_flow
annual_ratios              annual_key_metrics    quarterly_key_metrics
historical_prices
```

---

## FastAPI endpoints (all in `backend/main.py`)

| Endpoint | Tags | Description |
|---|---|---|
| `GET /api/overview/{ticker}` | Profile | Company profile + 15-cell metric grid |
| `GET /api/segments/{ticker}` | Profile | Revenue/income by business segment |
| `GET /api/financials/{ticker}` | Financials | IS + BS + CF + Debt Schedule tables |
| `GET /api/financials-extended/{ticker}` | Financials | Market/Valuation, Capital Structure, Profitability, Returns, Liquidity, Dividends, Efficiency |
| `GET /api/insights/{ticker}` | Insights | 7 insight groups (CAGR, Valuation, Profitability, …) |
| `GET /api/wacc/{ticker}` | Insights | WACC components + computed WACC (Damodaran credit spread + CAPM) |
| `GET /api/cf-irr/{ticker}` | Valuation | CF + IRR model (EBITDA + FCF dual forecast) |
| `POST /api/cf-irr/{ticker}/pdf` | Valuation | One-pager PDF download |
| `GET /api/cf-irr-special/{ticker}` | Valuation | TBV + EPS special IRR model |
| `GET /api/normalized-pe/{ticker}` | Valuation | Phil Town Rule #1 normalized PE |
| `GET /api/ddm/{ticker}` | Valuation | Dividend Discount Model (Gordon Growth) |
| `GET /api/sec-filings/{ticker}` | Filings | SEC iXBRL links (US) or EODHD portal links (intl) |
| `GET /api/routing-info/{ticker}` | Meta | Debug: which data source was selected |
| `GET /health` | — | Health check |

Query params: `period=annual|quarterly`, `scale=K|MM|B`

### REIT handling
When `industry` contains "REIT" or "Real Estate", `backend/main.py` injects additional rows into `financials-extended` Market & Valuation: **P/FFO** and **FFO Payout Ratio**.

---

## API keys

Stored in `.env` at workspace root (loaded by `backend/services/_key_loader.py`):
```
FMP_API_KEY=...
EODHD_API_KEY=...
```

The Streamlit app also reads from `.streamlit/secrets.toml` (priority: secrets > env > .env file).

**Subscription limits:**
- EODHD free/basic plan returns 403 for `/fundamentals/` — handled gracefully via skeleton fallback
- FMP returns 402 for financial statements on international tickers — handled with EODHD primary

---

## Backend logic

### `backend/logic_engine.py`
Pure-Python computation engine — no Streamlit, no HTTP, no side-effects. Framework-agnostic; used by both FastAPI and Streamlit. Contains:
- `compute_wacc(raw_data, overview, rf=0.042)` — CAPM + Damodaran credit spread
- `damodaran_spread(coverage)` — interest-coverage-ratio → credit spread lookup table
- CF+IRR model, DDM model, Phil Town normalized PE model

### `backend/services/sec_service.py`
Filing link resolver with a public entry-point `get_filing_links(ticker)`:
- **US tickers** (no dot): SEC EDGAR CIK lookup → submissions JSON → exact iXBRL viewer URLs per period. CIK map cached in-memory with 1-hour TTL.
- **Intl tickers** (has dot): EODHD fundamentals (Income Statement filter) → extracts `yearly`/`quarterly` date keys → maps to column labels → exchange-specific regulatory portal URLs (20 exchanges covered: TA=Magna, L=LSE, DE=Boerse Frankfurt, PA=Euronext, etc.)
- Period label format: annual `"2024"`, quarterly `"Q2 2024"` (calendar quarter of period-end date)

### WACC formula
```
WACC = E/V × Re + D/V × Rd × (1 − t)
Re   = Rf + β × ERP     (ERP = 5.5%)
Rd   = Rf + Damodaran_spread(EBIT/interest_expense)
Rf   = 0.042 (US 10-year treasury, hardcoded)
```

---

## Frontend (React)

### Technology stack
- **React 19** + **TypeScript 5.9** + **Vite 7**
- **Tailwind CSS v4** (via `@tailwindcss/vite` plugin — imported in `index.css`)
- **framer-motion** for animated components (`IndustryComparisonCell` bullet chart)
- **lucide-react** for all icons
- **xlsx (SheetJS v0.18.5)** — dynamically imported inside `downloadXlsx()` (lazy chunk, ~280 KB, only loads on first Excel export click)
- **file-saver** — installed, available if needed
- No CSS modules — inline styles throughout; colour palette constants at top of each file

### Brand colours (used everywhere)
```
NAVY = "#1c2b46"   (primary dark, headers, text)
BLUE = "#007bff"   (brand blue, active tabs, buttons, links)
```

### File structure
```
frontend/
  public/
    favicon.svg       "g" lettermark, #007bff, Trebuchet MS 900, no border
    logo.svg          "getValue" two-tone wordmark (get=#007bff / Value=#1c2b46)
    favicon.jpg       legacy
    logo.jpg          legacy
  src/
    App.tsx           Landing page + search input → activates StockDashboard
    types.ts          SINGLE SOURCE OF TRUTH for all TypeScript interfaces
    index.css         Global styles + Tailwind v4 import
    components/
      StockDashboard.tsx      Main orchestrator — all data fetching lives here
      FinancialsTab.tsx       IS + BS + CF + Debt + 7 extended metric tables
      InsightsTab.tsx         7 InsightsAgent groups + WACC section
      CfIrrTab.tsx            CF+IRR valuation tab
      CfIrrSpecialTab.tsx     TBV+EPS special IRR model tab
      DDMTab.tsx              Gordon Growth DDM tab
      SegmentsTab.tsx         Self-contained: fetches /api/segments, stacked bar + donut
      TableToolbar.tsx        Reusable toolbar: Search / xlsx Export / Copy TSV / Expand
      IndustryComparisonCell.tsx  Animated bullet chart vs. industry benchmarks
      MiniChart.tsx           Inline bar/line chart (React.lazy loaded)
    utils/
      industryBenchmarks.ts   Static S&P 500 benchmark table for comparison cells
      financialAnalysis.ts    analyzeBenchmark(), formatMetricValue() helpers
```

### `StockDashboard.tsx` — the orchestrator

**Tabs:** `Overview | Financials | Insights | Valuations`
**Valuation sub-tabs (draggable):** `CF + IRR | CF + IRR Special | Normalized PE | DDM`

**State management pattern:**
- All API data stored as `useState` in StockDashboard, passed as props to tab components
- Annual financials fetched eagerly on ticker change
- Quarterly financials fetched **lazily** (only when period selector switches to Quarterly) and **cached** (switching back to Annual is instant, no re-fetch)
- `NormalizedPETab` is **self-contained**: manages its own fetch + slider debounce (350ms), because slider parameters modify the API call
- `SegmentsTab` is **self-contained**: fetches `/api/segments/{ticker}` internally
- `DDMTab` fetches `/api/ddm/{ticker}` once; all Gordon Growth math computed inline in React (no re-fetch on slider change)
- `filingLinks` state: fetched from `/api/sec-filings/{ticker}` on mount, reset to `{}` on ticker change, passed to `FinancialsTab`

**Data fetch pattern (shared `load` helper):**
```tsx
const load = <T,>(url, set, setErr, setLoading) =>
  fetch(url)
    .then(r => { if (!r.ok) return r.json().then(b => Promise.reject(b.detail)); return r.json(); })
    .then((d: T) => { set(d); })
    .catch(e => setErr(typeof e === "string" ? e : "Failed to load"))
    .finally(() => setLoading(false));
```

**Parallel fetches on ticker change:**
```
overview + annual-financials + financials-extended + insights + WACC + filing-links
```

### `FinancialsTab.tsx` — financial tables

**Props:** `{ ticker, data, loading, extData, extLoading, period, scale, onPeriodChange, onScaleChange, filingLinks? }`

**Sub-components:**
- `FinTable` — renders IS/BS/CF/Debt with `ticker` + `filingLinks` props
- `ExtTable` — renders the 7 extended metric tables; includes "Vs. Industry" column when `industryBenchmarks.ts` has data for any row

**Filing link logic per column header `<th>`:**
```ts
const filingUrl = filingLinks?.[col] ?? generateSECLink(ticker, col);
```
- `filingLinks` = exact iXBRL URLs from SEC EDGAR (backend)
- `generateSECLink` = client-side fallback for US tickers: EDGAR company search filtered by `dateb` and form type (`10-K`/`10-Q`)
- International tickers: `generateSECLink` returns `null` (contains "."); `filingLinks` contains EODHD portal URLs from backend

**Hover CSS for filing link icons:**
```css
.gv-fin-th { position: relative; }
.gv-fil-link { opacity: 0; transition: opacity 0.15s ease; }
.gv-fin-th:hover .gv-fil-link { opacity: 1; }
```
Injected once via `<style>` at the FinancialsTab root.

**TableToolbar** rendered above every table (FinTable and ExtTable):
- Search: row-filter input
- Download: async `downloadXlsx()` with dynamic `import("xlsx")` — auto column widths, frozen header row
- Copy: TSV to clipboard
- Expand: fullscreen `ExpandOverlay` (position: fixed, Escape to close)

**Scale formatter:** `fCell(v, label, scale)` — handles EPS labels differently (always `$X.XX` format regardless of scale)

### `TableToolbar.tsx`

Exported: `TableToolbar` component + `ExpandOverlay` component.

```tsx
// Props
interface TableToolbarProps {
  title: string;
  searchActive: boolean; searchValue: string;
  onToggleSearch: () => void; onSearchChange: (v: string) => void;
  onDownload: () => void;      // caller creates xlsx
  onCopy: () => Promise<void> | void;
  onToggleExpand: () => void; isExpanded: boolean;
}
```

Icons from lucide-react: `Search, Download, Copy, Check, Maximize2, Minimize2, X`

### `IndustryComparisonCell.tsx`

Animated bullet chart comparing company metric vs. industry average.
- Uses `framer-motion` for the fill region and marker dot entrance animation
- Respects `prefers-reduced-motion` via `useReducedMotion()`
- Powered by `analyzeBenchmark()` from `financialAnalysis.ts`
- Appears in `ExtTable` "Vs. Industry" column and `InsightsTab` rows

### `DDMTab.tsx` — Gordon Growth Model

**Formula:**
```
Fair Value = DPS_TTM × (1 + g_forecast) / (r − g_terminal)
Guard: if (r − g_terminal) ≤ 0 → "Rate mismatch" warning
```

**Section order (top to bottom):**
1. About the Model (bold red warning: DDM for dividend-paying companies only)
2. DDM Quality Checklist
3. Historical Dividend Data table (with CAGR row for ALL columns: Divs Paid, Shares, DPS, Net Income, Payout%)
4. Model Inputs (sliders)
5. Gordon Growth Valuation result

**CAGR computed client-side** for Divs Paid, Shares, Net Income, Payout% (DPS CAGR comes from API `dps_cagr`).
Formula: `(TTM_val / oldest_val)^(1/n) − 1`. Guard: zero/negative oldest → "N/A". Divs Paid uses `Math.abs()` (negative cash outflow).

### `SegmentsTab.tsx` — self-contained

Fetches `/api/segments/{ticker}` internally. Renders:
- Stacked bar chart (65% width) + Donut chart (35% width)
- Interactive: donut slice click → highlights bar + filters table
- Returns `null` silently when no segment data

---

## Coding conventions

### TypeScript / React
- `types.ts` is the single source of truth — always add/update interfaces there first
- Use `React.memo` on all heavy table components
- Inline styles only (no CSS modules, no Tailwind on components except `IndustryComparisonCell` which uses both)
- Colour palette constants (`NAVY`, `BLUE`, etc.) defined at the top of each file
- `async/await` for all API calls; dynamic `import()` for large optional libraries (xlsx)
- Never re-fetch data when only a tab, slider, or scale changes

### Python / backend
- All computation in `logic_engine.py` — pure functions, no framework dependencies
- Service classes: `FMPService`, `EODHDService` — stateless, instantiated per request
- Error handling: swallow non-critical errors (filing links, WACC, segments) and return `{}` / `null` — never let best-effort calls crash the main response
- Use `_s(v)` helper for safe float coercion throughout `logic_engine.py`

### Build verification
Always run `npm run build` (from `frontend/`) after any frontend change to confirm TypeScript compiles clean. The build output should show `✓ built in X.XXs` with no errors.

---

## Component → API endpoint mapping

| Component | Endpoint(s) fetched |
|---|---|
| `StockDashboard` (orchestrator) | `/api/overview`, `/api/financials?period=annual`, `/api/financials-extended?period=annual`, `/api/insights`, `/api/wacc`, `/api/sec-filings` |
| `FinancialsTab` | (data passed as props — no direct fetching) |
| `NormalizedPETab` (inside StockDashboard) | `/api/normalized-pe` (manages own fetch + debounced slider re-fetch) |
| `CfIrrTab` | `/api/cf-irr` (manages own fetch + slider state) |
| `CfIrrSpecialTab` | `/api/cf-irr-special` (manages own fetch + slider state) |
| `DDMTab` | `/api/ddm` (manages own fetch; sliders are purely client-side) |
| `SegmentsTab` | `/api/segments` (self-contained, renders null if no data) |

---

## VS Code development standards

- The active UI is the **React + FastAPI implementation** — all new features go there first
- When modifying `FinancialsTab.tsx`, always pass `ticker` and `filingLinks` props through to `FinTable`/`ExtTable`
- When adding a new API endpoint, add it to the endpoint table in this file
- When adding a new TypeScript type, add it to `types.ts` — never inline interface definitions in component files
- File references in Claude responses should use markdown links: `[filename.tsx](path/filename.tsx)` (clickable in VS Code)
- Prefer `Edit` over `Write` for existing files (smaller diffs, easier review)
- After any frontend change: `npm run build` to verify. After any backend change: `python -c "import ast; ast.parse(open('backend/main.py', encoding='utf-8').read()); print('OK')"` for syntax check

---

## Key design decisions (do not revert)

1. **No state for scale/period changes** — data is already in memory; only the formatter changes
2. **Quarterly financials are lazy** — fetched only when user switches to Quarterly tab; cached in `finQ` state
3. **xlsx is dynamically imported** — keeps the initial JS bundle small; ~280 KB xlsx chunk only loads on first Excel export
4. **MiniChart is React.lazy** — only loaded when first chart is expanded in InsightsTab
5. **IndustryComparisonCell mixes Tailwind + inline styles** — intentional; framer-motion props need inline styles, layout uses Tailwind utility classes
6. **`generateSECLink` client-side fallback** — ensures every US annual/quarterly column gets an EDGAR link even when backend `filingLinks` doesn't cover older periods. International tickers return `null` (ticker contains ".").
7. **Filing link hover uses CSS class** — `.gv-fin-th:hover .gv-fil-link` injected via `<style>` tag because React inline styles can't express `:hover` pseudo-class on descendants
8. **DDM sliders are purely client-side** — the Gordon Growth formula is simple enough to compute in React without a round-trip; only the initial data (`/api/ddm/{ticker}`) is fetched
