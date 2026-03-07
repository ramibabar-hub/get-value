# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**getValue** — a personal stock analysis tool with two parallel UI implementations:

1. **Streamlit app** (`app.py`) — the original, production UI. Runs locally with `streamlit run app.py`.
2. **React + FastAPI** (`frontend/` + `backend/`) — a newer implementation. FastAPI serves financial data via REST; React renders the dashboard.

Both UIs share the same Python agent layer (`agents/`) and data normalisation logic.

---

## Running the project

### Streamlit (original UI)
```bash
pip install -r requirements.txt
streamlit run app.py
```

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
npm run build      # production build
npm run lint       # ESLint
```

The React frontend expects the FastAPI backend running on port 8000 (CORS is already configured for ports 5173 and 3000).

---

## Architecture

### Data flow

```
User enters ticker
      │
      ▼
SmartGateway  (backend/services/gateway.py)
      │
      ├── US tickers  → FMPService  (backend/services/fmp_service.py)
      └── Intl tickers → EODHDService (backend/services/eodhd_service.py)
                          └── Fallback: FMPService for profile/overview
                          └── Fallback: EOD historical endpoint for price
      │
      ▼
DataNormalizer  (agents/core_agent.py)
  Wraps raw_data dict with helpers for TTM, column headers, per-period values.
      │
      ▼
ProfileAgent / InsightsAgent  (agents/)
  Build the 15-cell header grid, CAGR tables, WACC, valuation multiples.
      │
      ▼
backend/main.py  (FastAPI endpoints)  /  app.py  (Streamlit tabs)
```

### Key routing rule (SmartGateway)
- Tickers **without** a dot suffix (e.g. `AAPL`) → FMP primary
- Tickers **with** a recognised suffix (e.g. `NICE.TA`, `BMW.DE`) → EODHD primary, FMP fallback for profile
- Exchange suffix map lives in `backend/services/gateway.py` (`_FMP_SUFFIX_TO_EODHD`)
- Israel: `TA` suffix maps to EODHD exchange code `"TA"` (not `"IT"`)

### Skeleton fallback
When both EODHD fundamentals (403) and FMP income statements (402) are blocked for an international ticker, `backend/main.py` returns a zero-filled 10-year skeleton (2016–2025) so the Financials tab renders columns instead of a 404.

### canonical `raw_data` dict keys
All agents and endpoints expect this shape from `fetch_all()`:
```
annual_income_statement, quarterly_income_statement,
annual_balance_sheet,    quarterly_balance_sheet,
annual_cash_flow,        quarterly_cash_flow,
annual_ratios,           annual_key_metrics, quarterly_key_metrics,
historical_prices
```

---

## FastAPI endpoints

| Endpoint | Description |
|---|---|
| `GET /api/overview/{ticker}` | Profile + 15-cell metric grid |
| `GET /api/financials/{ticker}` | IS + BS + CF + Debt tables |
| `GET /api/financials-extended/{ticker}` | Market/Valuation, Capital Structure, Profitability, Returns, Liquidity, Dividends, Efficiency |
| `GET /api/insights/{ticker}` | 7 insight groups (CAGR, Valuation, Profitability, ...) |
| `GET /api/cf-irr/{ticker}` | CF + IRR valuation model |
| `GET /api/normalized-pe/{ticker}` | Phil Town Rule #1 valuation |
| `GET /api/routing-info/{ticker}` | Debug: which data source was selected |

Query params: `period=annual|quarterly`, `scale=K|MM|B`

---

## API keys

Stored in `.env` at workspace root (loaded by `backend/services/_key_loader.py`):
```
FMP_API_KEY=...
EODHD_API_KEY=...
```

The Streamlit app also reads from `.streamlit/secrets.toml` (priority: secrets > env > .env file).

**Subscription limits:** EODHD free/basic plan returns 403 for `/fundamentals/`. FMP returns 402 for financial statements on international tickers. The code handles both gracefully via fallbacks and skeleton data.

---

## Frontend (React)

- **`frontend/src/types.ts`** — single source of truth for all TypeScript interfaces shared across components
- **`frontend/src/components/StockDashboard.tsx`** — main orchestrator: fires `overview + financials + insights` API calls in parallel on ticker change; quarterly financials fetched lazily and cached
- Tab components (`FinancialsTab`, `InsightsTab`, `CfIrrTab`) receive data as props and use `React.memo`
- No data is re-fetched when only a tab, slider, or scale changes
- Inline styles throughout (no CSS modules); colour palette constants defined at file top

## REIT handling

When `industry` contains "REIT" or "Real Estate", `backend/main.py` injects additional rows into the `financials-extended` Market & Valuation section: **P/FFO** and **FFO Payout Ratio**.
