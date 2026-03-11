# Company Overview Enhancement — Design Document
_Date: 2026-03-08_

## Summary

Enhance the getValue Overview tab with a live stock price chart (Recharts) and an AI-powered Events & Insights feed (FMP News + Claude Haiku). Uses Option B: split components with thin orchestrator.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Chart library | Recharts | React-native, inline-style compatible, sufficient for daily data |
| AI data source | FMP News + Claude | Existing FMP subscription, structured input → accurate model impact |
| AI model | claude-haiku-4-5-20251001 | Cost-efficient, 2-4s latency, sufficient for structured JSON |
| Architecture | Split components (Option B) | Consistent with existing CfIrrTab/DDMTab pattern |

---

## Layout

```
Overview tab
├── Two-column row (flex, gap 24px, wraps on < 768px)
│   ├── Left col (flex: 1, min-width 300px)
│   │   └── "About" label + company description text (existing)
│   └── Right col (flex: 1.2, min-width 340px)
│       └── StockPriceChart component
├── "AI News & Insights" section header
│   └── CompanyInsightsFeed component (InsightCard × 5-6)
└── SegmentsTab (unchanged, existing)
```

---

## New Files

### `frontend/src/components/StockPriceChart.tsx`
- **Self-contained**: fetches `/api/price-history/{ticker}?range={range}` on ticker/range change
- **State**: `data`, `loading`, `error`, `range` (default `1Y`)
- **Timeframe buttons**: `1D | 5D | 1M | 6M | YTD | 1Y | 5Y | 10Y`
- **Chart**: `ComposedChart` with dual Y-axes
  - Top 75%: `Area` (price, BLUE fill, NAVY stroke)
  - Bottom 25%: `Bar` (volume, grey, opacity 0.5)
  - `Tooltip`: custom — shows date, price, volume on hover
  - `ResponsiveContainer`: width 100%, height 300px
- **Loading state**: shimmer skeleton rectangle (pulse animation)
- **Error state**: silent (returns null)

### `frontend/src/components/CompanyInsightsFeed.tsx`
- **Self-contained**: fetches `POST /api/news-insights/{ticker}` with company context body
- **Props**: `{ ticker: string, ov: OverviewData | null }`
- **State**: `insights`, `loading`, `error`
- **Loading state**: 3× `InsightCardSkeleton` (shimmer gradient sweep)
- **Renders**: list of `InsightCard` components
- **Error state**: returns null (silent, does not break Overview)

### `frontend/src/components/InsightCard.tsx`
- **Props**: `{ item: NewsInsight }`
- **Renders**:
  - Left: blue dot indicator + date badge
  - Center: headline (bold, NAVY), one-sentence summary (grey)
  - Right: `⚡ Model Impact` button (lucide `Zap` icon, BLUE)
- **Popover**: clicking `⚡ Model Impact` toggles an inline expansion panel below the card (no portal needed) showing `model_impact` text in a light-blue bordered box
- **Styling**: inline styles, NAVY/BLUE palette, white card with 1px border, hover shadow

---

## Modified Files

### `frontend/src/types.ts`
Add:
```typescript
export interface PricePoint {
  date:   string;
  price:  number;
  volume: number | null;
}

export interface PriceHistoryData {
  ticker: string;
  range:  string;
  points: PricePoint[];
}

export interface NewsInsight {
  headline:     string;
  date:         string;
  summary:      string;
  model_impact: string;
  url?:         string;
}

export interface NewsInsightsData {
  ticker:   string;
  insights: NewsInsight[];
}
```

### `frontend/src/components/StockDashboard.tsx`
- Import `StockPriceChart` and `CompanyInsightsFeed`
- Replace Overview section content with new two-column layout

### `frontend/package.json`
- Add `recharts` (^2.12)

---

## New Backend Endpoints

### `GET /api/price-history/{ticker}`
**Query param**: `range: str = "1Y"` (1D | 5D | 1M | 6M | YTD | 1Y | 5Y | 10Y)

**Logic**:
- Ranges ≤ 5Y: slice `historical_prices` from `fetch_all()` (already fetched, free)
- 10Y: call FMP `/api/v3/historical-price-full/{ticker}?from={10yr_ago}` directly
- For 1D/5D: use FMP `/api/v3/historical-chart/15min/{ticker}` (intraday)

**Response**: `{ ticker, range, points: [{ date, price, volume }] }` (oldest → newest)

### `POST /api/news-insights/{ticker}`
**Body**: `{ company_name, sector, industry, market_cap, description }` (from OverviewData)

**Logic**:
1. Fetch FMP `/api/v3/stock_news?tickers={ticker}&limit=8`
2. Build Claude prompt (system + user, see below)
3. Call `anthropic.messages.create(model="claude-haiku-4-5-20251001", ...)`
4. Parse JSON from response text
5. Return `{ ticker, insights: [...] }`

**Error handling**: if FMP news returns empty or Claude fails → return `{ ticker, insights: [] }`

---

## Claude System Prompt

```
You are a senior buy-side equity analyst at a top-tier investment fund.

You will receive recent news headlines about a publicly traded company and its financial profile.
For each headline, produce exactly:
1. "summary": One sentence, investor-focused, present tense, ≤ 25 words.
2. "model_impact": 2-3 sentences explaining the accounting and valuation impact.
   - Name the specific financial statement line affected (Revenue, EBITDA, Net Income, FCF, etc.)
   - Distinguish GAAP vs. Adjusted/Non-GAAP if relevant
   - State whether this changes the long-term DCF model or is a one-time item
   - If the event is immaterial to the valuation model, say so explicitly
   - Use precise Wall Street terminology

Return ONLY a valid JSON array. No markdown, no explanation outside the JSON.
Format: [{ "headline": "...", "date": "...", "summary": "...", "model_impact": "...", "url": "..." }]
```

---

## Data Flow

```
User opens Overview tab
  │
  ├─► StockPriceChart mounts
  │     └─► GET /api/price-history/{ticker}?range=1Y
  │           └─► slice historical_prices → return PriceHistoryData
  │
  └─► CompanyInsightsFeed mounts
        └─► POST /api/news-insights/{ticker} (body: ov context)
              ├─► FMP /api/v3/stock_news (8 headlines)
              └─► Claude Haiku: system prompt + headlines → JSON
                    └─► return NewsInsightsData
```

---

## Error Handling

- Both new components fail silently (return `null`) — Overview never crashes
- Chart shows skeleton if no price data available
- Insights feed shows nothing if Claude or FMP news fails
- 30s timeout on the news-insights endpoint (Claude can be slow under load)

---

## Dependencies

- `recharts ^2.12` — to be added via `npm install recharts`
- `anthropic` Python SDK — to be added via `pip install anthropic` + `requirements.txt`
