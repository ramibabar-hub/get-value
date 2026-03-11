# Company Overview Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a live Recharts price chart and a Claude-powered News & Insights feed to the getValue Overview tab.

**Architecture:** Split-component Option B — `StockPriceChart.tsx` and `CompanyInsightsFeed.tsx` are self-contained components (own fetch + state), mounted inside the existing Overview section of `StockDashboard.tsx`. Backend adds two new FastAPI endpoints: `GET /api/price-history/{ticker}` (slices historical_prices) and `POST /api/news-insights/{ticker}` (FMP news → Claude Haiku → structured JSON).

**Tech Stack:** React 19, TypeScript 5.9, Recharts ^2.12, Anthropic Python SDK, FastAPI, FMP API, lucide-react

---

## Task 1: Install dependencies

**Files:**
- Modify: `frontend/package.json` (via npm)
- Modify: `requirements.txt`

**Step 1: Install recharts**

```bash
cd frontend
npm install recharts
```
Expected: `added N packages` with recharts in `node_modules`.

**Step 2: Verify recharts types are bundled**

```bash
ls node_modules/recharts/types
```
Expected: directory exists (recharts ships its own types, no `@types/recharts` needed).

**Step 3: Install Anthropic Python SDK**

```bash
cd ..
pip install anthropic
```
Expected: `Successfully installed anthropic-X.X.X`.

**Step 4: Add to requirements.txt**

Open `requirements.txt`, add at the end:
```
anthropic>=0.25.0
```

**Step 5: Verify backend still imports cleanly**

```bash
python -c "import anthropic; print('OK')"
```
Expected: `OK`

**Step 6: Commit**

```bash
git add requirements.txt frontend/package.json frontend/package-lock.json
git commit -m "feat(deps): add recharts and anthropic SDK"
```

---

## Task 2: Add TypeScript types

**Files:**
- Modify: `frontend/src/types.ts` (after the `SegmentsData` block, before `// ── DDM`)

**Step 1: Open types.ts and locate insertion point**

Find the line: `// ── DDM  ──────────────────...`
Insert the following block immediately before it:

```typescript
// ── Price History ─────────────────────────────────────────────────────────────

export type PriceRange = "1D" | "5D" | "1M" | "6M" | "YTD" | "1Y" | "5Y" | "10Y";

export interface PricePoint {
  date:   string;        // "2024-03-08" or "2024-03-08 14:30:00"
  price:  number;
  volume: number | null;
}

export interface PriceHistoryData {
  ticker: string;
  range:  PriceRange;
  points: PricePoint[];  // oldest → newest
}

// ── News Insights ─────────────────────────────────────────────────────────────

export interface NewsInsight {
  headline:     string;
  date:         string;   // "2024-03-08"
  summary:      string;   // one-sentence investor summary
  model_impact: string;   // 2-3 sentence valuation impact explanation
  url?:         string;
}

export interface NewsInsightsData {
  ticker:   string;
  insights: NewsInsight[];
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat(types): add PriceHistoryData and NewsInsightsData interfaces"
```

---

## Task 3: Backend — price-history endpoint

**Files:**
- Modify: `backend/main.py` (add before the `@app.get("/api/search"...)` line)

**Context:** `historical_prices` is already fetched by `SmartGateway.fetch_all()`. Each record has keys: `date` (string "YYYY-MM-DD"), `close` (or `adjClose`), `volume`. Records come newest-first from FMP.

**Step 1: Add the endpoint**

Find the line `@app.get("/api/search", tags=["Meta"])` in `backend/main.py`.
Insert the following block immediately before it:

```python
@app.get("/api/price-history/{ticker}", tags=["Profile"])
def price_history(ticker: str, range: str = Query("1Y")):
    """
    Historical price data for charting.
    Ranges ≤ 5Y: sliced from historical_prices already in fetch_all().
    10Y: extended fetch from FMP.
    1D / 5D: 15-min intraday from FMP.
    Returns points oldest → newest.
    """
    import datetime as _dt

    ticker = ticker.strip().upper()

    # ── Intraday (1D, 5D) ─────────────────────────────────────────────────────
    if range in ("1D", "5D"):
        from backend.services.fmp_service import FMPService as _FMPSvc
        _fmp = _FMPSvc()
        raw = _fmp._get(f"{_fmp._V3}/historical-chart/15min/{ticker}", {})
        if not isinstance(raw, list):
            return {"ticker": ticker, "range": range, "points": []}
        # Filter to last 1 or 5 trading days
        cutoff_days = 1 if range == "1D" else 5
        cutoff = (_dt.datetime.utcnow() - _dt.timedelta(days=cutoff_days * 2)).strftime("%Y-%m-%d")
        points = []
        for rec in reversed(raw):  # oldest → newest
            d = str(rec.get("date") or "")
            if d[:10] < cutoff:
                continue
            p = _sf(rec.get("close"))
            v = _sf(rec.get("volume"))
            if p:
                points.append({"date": d, "price": p, "volume": v})
        return {"ticker": ticker, "range": range, "points": points}

    # ── 10Y: extended daily history ───────────────────────────────────────────
    if range == "10Y":
        from backend.services.fmp_service import FMPService as _FMPSvc
        _fmp = _FMPSvc()
        from_date = (_dt.date.today() - _dt.timedelta(days=3650)).strftime("%Y-%m-%d")
        raw = _fmp._get(
            f"{_fmp._V3}/historical-price-full/{ticker}",
            {"from": from_date}
        )
        hist = raw.get("historical", []) if isinstance(raw, dict) else []
        points = [
            {"date": str(r.get("date", "")), "price": _sf(r.get("adjClose") or r.get("close")), "volume": _sf(r.get("volume"))}
            for r in reversed(hist)
            if _sf(r.get("adjClose") or r.get("close"))
        ]
        return {"ticker": ticker, "range": range, "points": points}

    # ── Daily ranges (1M, 6M, YTD, 1Y, 5Y): slice historical_prices ──────────
    raw_data = _gw.fetch_all(ticker)
    hist_raw = list(reversed(raw_data.get("historical_prices") or []))  # oldest → newest

    today = _dt.date.today()
    _range_days = {"1M": 31, "6M": 183, "YTD": (today - _dt.date(today.year, 1, 1)).days + 1, "1Y": 365, "5Y": 1826}
    days = _range_days.get(range, 365)
    cutoff = (today - _dt.timedelta(days=days)).strftime("%Y-%m-%d")

    points = []
    for rec in hist_raw:
        d = str(rec.get("date") or "")[:10]
        if d < cutoff:
            continue
        p = _sf(rec.get("adjClose") or rec.get("close"))
        v = _sf(rec.get("volume"))
        if p:
            points.append({"date": d, "price": round(p, 4), "volume": v})

    return {"ticker": ticker, "range": range, "points": points}
```

**Step 2: Syntax check**

```bash
python -c "import ast; ast.parse(open('backend/main.py', encoding='utf-8').read()); print('OK')"
```
Expected: `OK`

**Step 3: Quick manual test (backend must be running)**

```bash
curl "http://localhost:8000/api/price-history/AAPL?range=1Y" | python -m json.tool | head -20
```
Expected: JSON with `ticker`, `range`, `points` array where each point has `date`, `price`, `volume`.

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat(api): add GET /api/price-history/{ticker} endpoint"
```

---

## Task 4: Backend — news-insights endpoint

**Files:**
- Modify: `backend/main.py` (add after the price-history endpoint, before `@app.get("/api/search"...)`)
- Modify: `backend/services/_key_loader.py` (verify CLAUDE_API_KEY loads — likely already works)

**Step 1: Verify key loader works for CLAUDE_API_KEY**

```bash
cd c:/Users/RamiB/Desktop/Workspace
python -c "from backend.services._key_loader import load_key; print(bool(load_key('CLAUDE_API_KEY')))"
```
Expected: `True`

**Step 2: Add the endpoint**

In `backend/main.py`, insert immediately after the `price_history` function (before `@app.get("/api/search"...)`):

```python
class _NewsInsightsRequest(BaseModel):
    company_name: str | None = None
    sector:       str | None = None
    industry:     str | None = None
    market_cap:   float | None = None
    description:  str | None = None


_NEWS_SYSTEM_PROMPT = """You are a senior buy-side equity analyst at a top-tier investment fund.

You will receive recent news headlines about a publicly traded company and its financial profile.
For each headline, produce exactly:
1. "summary": One sentence, investor-focused, present tense, ≤ 25 words.
2. "model_impact": 2-3 sentences explaining the accounting and valuation impact.
   - Name the specific financial statement line affected (Revenue, EBITDA, Net Income, FCF, etc.)
   - Distinguish GAAP vs. Adjusted/Non-GAAP if relevant
   - State whether this changes the long-term DCF model or is a one-time item
   - If the event is immaterial to the valuation model, say so explicitly
   - Use precise Wall Street terminology

Return ONLY a valid JSON array. No markdown, no preamble, no explanation outside the JSON.
Format: [{ "headline": "...", "date": "...", "summary": "...", "model_impact": "...", "url": "..." }]"""


@app.post("/api/news-insights/{ticker}", tags=["AI"])
def news_insights(ticker: str, body: _NewsInsightsRequest):
    """
    Fetch recent FMP news for ticker, synthesize with Claude Haiku into
    structured insights with valuation model-impact explanations.
    """
    import json as _json
    ticker = ticker.strip().upper()

    # ── 1. Fetch FMP news ─────────────────────────────────────────────────────
    from backend.services.fmp_service import FMPService as _FMPSvc
    _fmp = _FMPSvc()
    news_raw = _fmp._get(f"{_fmp._V3}/stock_news", {"tickers": ticker, "limit": 8})
    if not isinstance(news_raw, list) or not news_raw:
        return {"ticker": ticker, "insights": []}

    headlines = "\n".join(
        f"{i+1}. {r.get('publishedDate','')[:10]} — {r.get('title','')} | URL: {r.get('url','')}"
        for i, r in enumerate(news_raw)
    )

    # ── 2. Build user message ─────────────────────────────────────────────────
    ctx_parts = [f"Company: {body.company_name or ticker} ({ticker})"]
    if body.sector:    ctx_parts.append(f"Sector: {body.sector}")
    if body.industry:  ctx_parts.append(f"Industry: {body.industry}")
    if body.market_cap:ctx_parts.append(f"Market Cap: ${body.market_cap/1e9:.1f}B")
    context_line = " | ".join(ctx_parts)

    user_msg = f"{context_line}\n\nRecent news (last 30 days):\n{headlines}"

    # ── 3. Call Claude Haiku ──────────────────────────────────────────────────
    from backend.services._key_loader import load_key as _lk
    claude_key = _lk("CLAUDE_API_KEY")
    if not claude_key:
        return {"ticker": ticker, "insights": []}

    try:
        import anthropic as _ant
        client = _ant.Anthropic(api_key=claude_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=_NEWS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw_text = msg.content[0].text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        insights = _json.loads(raw_text)
        if not isinstance(insights, list):
            insights = []
    except Exception as exc:
        print(f"[news_insights] Claude error for {ticker}: {exc}", flush=True)
        return {"ticker": ticker, "insights": []}

    return {"ticker": ticker, "insights": insights[:6]}
```

**Step 3: Syntax check**

```bash
python -c "import ast; ast.parse(open('backend/main.py', encoding='utf-8').read()); print('OK')"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat(api): add POST /api/news-insights/{ticker} with Claude Haiku"
```

---

## Task 5: Frontend — StockPriceChart component

**Files:**
- Create: `frontend/src/components/StockPriceChart.tsx`

**Step 1: Create the file**

```tsx
/**
 * StockPriceChart.tsx
 * Recharts-based price chart with timeframe toggle and volume overlay.
 * Self-contained: manages its own fetch and range state.
 */
import { useState, useEffect, useCallback } from "react";
import {
  ComposedChart, Area, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import type { PriceHistoryData, PricePoint, PriceRange } from "../types";

const NAVY = "#1c2b46";
const BLUE = "#007bff";

const RANGES: PriceRange[] = ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y", "10Y"];

// Thin out data so Recharts doesn't render 1800 points for 5Y
function downsample(points: PricePoint[], maxPoints: number): PricePoint[] {
  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  return points.filter((_, i) => i % step === 0 || i === points.length - 1);
}

function formatXAxis(dateStr: string, range: PriceRange): string {
  if (!dateStr) return "";
  if (range === "1D" || range === "5D") {
    return dateStr.slice(11, 16); // "HH:MM"
  }
  const d = new Date(dateStr);
  if (range === "1M" || range === "6M") {
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: { value: number; name: string }[];
  label?: string;
}

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const price  = payload.find(p => p.name === "price");
  const volume = payload.find(p => p.name === "volume");
  return (
    <div style={{
      background: "#fff", border: `1px solid #e5e7eb`, borderRadius: 8,
      padding: "8px 12px", fontSize: "0.8em", color: NAVY,
      boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
    }}>
      <div style={{ color: "#6b7280", marginBottom: 4 }}>{label}</div>
      {price  && <div><strong>${price.value.toFixed(2)}</strong></div>}
      {volume && volume.value > 0 && (
        <div style={{ color: "#9ca3af", marginTop: 2 }}>
          Vol: {(volume.value / 1e6).toFixed(1)}M
        </div>
      )}
    </div>
  );
}

// Shimmer skeleton while loading
function ChartSkeleton() {
  return (
    <div style={{
      height: 300, borderRadius: 8,
      background: "linear-gradient(90deg, #f0f2f5 25%, #e5e7eb 50%, #f0f2f5 75%)",
      backgroundSize: "200% 100%",
      animation: "shimmer 1.4s infinite",
    }}>
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
    </div>
  );
}

interface StockPriceChartProps {
  ticker: string;
}

export default function StockPriceChart({ ticker }: StockPriceChartProps) {
  const [range,   setRange]   = useState<PriceRange>("1Y");
  const [data,    setData]    = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback((t: string, r: PriceRange) => {
    setLoading(true);
    fetch(`/api/price-history/${encodeURIComponent(t)}?range=${r}`)
      .then(res => res.ok ? res.json() : Promise.reject())
      .then((d: PriceHistoryData) => setData(downsample(d.points, 300)))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (ticker) fetchData(ticker, range);
  }, [ticker, range, fetchData]);

  if (loading) return <ChartSkeleton />;
  if (!data.length) return null;

  // Price change for colour
  const first = data[0]?.price ?? 0;
  const last  = data[data.length - 1]?.price ?? 0;
  const up    = last >= first;
  const lineColor = up ? "#22c55e" : "#ef4444";
  const areaColor = up ? "#22c55e22" : "#ef444422";

  return (
    <div>
      {/* Timeframe buttons */}
      <div style={{ display: "flex", gap: 4, marginBottom: 10, flexWrap: "wrap" }}>
        {RANGES.map(r => (
          <button
            key={r}
            onClick={() => setRange(r)}
            style={{
              padding: "3px 10px", fontSize: "0.75em", fontWeight: 600,
              border: `1px solid ${r === range ? BLUE : "#d1d5db"}`,
              borderRadius: 5, cursor: "pointer",
              background: r === range ? BLUE : "#fff",
              color: r === range ? "#fff" : "#6b7280",
              transition: "all 0.1s",
            }}
          >
            {r}
          </button>
        ))}
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={lineColor} stopOpacity={0.25} />
              <stop offset="95%" stopColor={lineColor} stopOpacity={0}    />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f2f5" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={d => formatXAxis(d, range)}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            axisLine={false} tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            yAxisId="price"
            orientation="right"
            domain={["auto", "auto"]}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            axisLine={false} tickLine={false}
            tickFormatter={v => `$${v.toFixed(0)}`}
            width={52}
          />
          <YAxis
            yAxisId="vol"
            orientation="left"
            domain={[0, (max: number) => max * 6]}
            hide
          />
          <Tooltip content={<ChartTooltip />} />
          <Bar
            yAxisId="vol"
            dataKey="volume"
            fill="#9ca3af"
            opacity={0.3}
            radius={[2, 2, 0, 0]}
            isAnimationActive={false}
          />
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="price"
            stroke={lineColor}
            strokeWidth={1.5}
            fill="url(#priceGrad)"
            dot={false}
            activeDot={{ r: 4, fill: lineColor }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 2: Build verify**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: `✓ built in X.XXs` with no TypeScript errors.

**Step 3: Commit**

```bash
git add frontend/src/components/StockPriceChart.tsx
git commit -m "feat(ui): add StockPriceChart with Recharts + timeframe toggles"
```

---

## Task 6: Frontend — InsightCard component

**Files:**
- Create: `frontend/src/components/InsightCard.tsx`

**Step 1: Create the file**

```tsx
/**
 * InsightCard.tsx
 * Single news insight card with collapsible "Model Impact" panel.
 */
import { useState, memo } from "react";
import { Zap } from "lucide-react";
import type { NewsInsight } from "../types";

const NAVY = "#1c2b46";
const BLUE = "#007bff";

interface InsightCardProps {
  item: NewsInsight;
}

const InsightCard = memo(function InsightCard({ item }: InsightCardProps) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{
      background: "#fff",
      border: "1px solid #e5e7eb",
      borderRadius: 10,
      padding: "14px 16px",
      marginBottom: 10,
      boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      transition: "box-shadow 0.15s",
    }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.09)")}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)")}
    >
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        {/* Blue dot */}
        <div style={{
          width: 8, height: 8, borderRadius: "50%",
          background: BLUE, flexShrink: 0, marginTop: 6,
        }} />

        {/* Content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            {/* Headline */}
            <div style={{ fontWeight: 600, color: NAVY, fontSize: "0.88em", flex: 1 }}>
              {item.url
                ? <a href={item.url} target="_blank" rel="noopener noreferrer"
                    style={{ color: NAVY, textDecoration: "none" }}
                    onMouseEnter={e => ((e.target as HTMLElement).style.color = BLUE)}
                    onMouseLeave={e => ((e.target as HTMLElement).style.color = NAVY)}>
                    {item.headline}
                  </a>
                : item.headline
              }
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              {/* Date badge */}
              <span style={{
                fontSize: "0.7em", color: "#9ca3af",
                background: "#f3f4f6", padding: "2px 8px", borderRadius: 12,
              }}>
                {item.date}
              </span>

              {/* Model Impact button */}
              <button
                onClick={() => setOpen(o => !o)}
                style={{
                  display: "flex", alignItems: "center", gap: 4,
                  padding: "4px 10px", borderRadius: 6, border: "none",
                  background: open ? BLUE : "#eaf1ff",
                  color: open ? "#fff" : BLUE,
                  fontSize: "0.72em", fontWeight: 700, cursor: "pointer",
                  transition: "background 0.15s, color 0.15s",
                  whiteSpace: "nowrap",
                }}
              >
                <Zap size={11} />
                Model Impact
              </button>
            </div>
          </div>

          {/* One-line summary */}
          <p style={{
            margin: "5px 0 0", fontSize: "0.82em",
            color: "#6b7280", lineHeight: 1.5,
          }}>
            {item.summary}
          </p>
        </div>
      </div>

      {/* Collapsible model impact panel */}
      {open && (
        <div style={{
          marginTop: 12, marginLeft: 20,
          padding: "10px 14px",
          background: "#f0f6ff",
          border: `1px solid ${BLUE}33`,
          borderLeft: `3px solid ${BLUE}`,
          borderRadius: "0 8px 8px 0",
          fontSize: "0.82em", color: NAVY, lineHeight: 1.65,
        }}>
          <div style={{ fontWeight: 700, color: BLUE, marginBottom: 4, fontSize: "0.8em", letterSpacing: "0.05em", textTransform: "uppercase" }}>
            ⚡ Model Impact
          </div>
          {item.model_impact}
        </div>
      )}
    </div>
  );
});

export default InsightCard;


// ── Skeleton (shimmer loading placeholder) ────────────────────────────────────

export function InsightCardSkeleton() {
  const shimmer: React.CSSProperties = {
    background: "linear-gradient(90deg, #f0f2f5 25%, #e5e7eb 50%, #f0f2f5 75%)",
    backgroundSize: "200% 100%",
    animation: "shimmer 1.4s infinite",
    borderRadius: 6,
  };
  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb",
      borderRadius: 10, padding: "14px 16px", marginBottom: 10,
    }}>
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#e5e7eb", marginTop: 6, flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ ...shimmer, height: 14, width: "70%", marginBottom: 8 }} />
          <div style={{ ...shimmer, height: 11, width: "45%"  }} />
        </div>
        <div style={{ ...shimmer, height: 24, width: 90, borderRadius: 6 }} />
      </div>
    </div>
  );
}
```

**Step 2: Build verify**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: `✓ built in X.XXs` with no errors.

**Step 3: Commit**

```bash
git add frontend/src/components/InsightCard.tsx
git commit -m "feat(ui): add InsightCard with Model Impact popover and skeleton"
```

---

## Task 7: Frontend — CompanyInsightsFeed component

**Files:**
- Create: `frontend/src/components/CompanyInsightsFeed.tsx`

**Step 1: Create the file**

```tsx
/**
 * CompanyInsightsFeed.tsx
 * AI-powered news & insights feed using FMP news + Claude Haiku.
 * Self-contained: manages its own fetch + state.
 */
import { useState, useEffect } from "react";
import InsightCard, { InsightCardSkeleton } from "./InsightCard";
import type { OverviewData, NewsInsightsData } from "../types";

const NAVY = "#1c2b46";

interface CompanyInsightsFeedProps {
  ticker: string;
  ov:     OverviewData | null;
}

export default function CompanyInsightsFeed({ ticker, ov }: CompanyInsightsFeedProps) {
  const [data,    setData]    = useState<NewsInsightsData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setData(null);

    const ctrl = new AbortController();
    fetch(`/api/news-insights/${encodeURIComponent(ticker)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: ov?.company_name  ?? null,
        sector:       ov?.sector        ?? null,
        industry:     ov?.industry      ?? null,
        market_cap:   ov?.metrics?.find?.(m => m.label === "Market Cap")
                        ? null   // use raw ov.price for rough cap if needed
                        : null,
        description:  null,
      }),
      signal: ctrl.signal,
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((d: NewsInsightsData) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [ticker]);

  // Silent if no data and not loading
  if (!loading && (!data || data.insights.length === 0)) return null;

  return (
    <div style={{ marginTop: 28 }}>
      {/* Section header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        marginBottom: 14,
      }}>
        <div style={{
          fontSize: "0.72em", fontWeight: 700, textTransform: "uppercase",
          letterSpacing: "0.09em", color: "#4d6b88",
        }}>
          AI News & Insights
        </div>
        <div style={{
          fontSize: "0.65em", color: "#9ca3af",
          background: "#f3f4f6", padding: "2px 8px", borderRadius: 10,
        }}>
          Powered by Claude
        </div>
      </div>

      {/* Loading skeletons */}
      {loading && (
        <>
          <InsightCardSkeleton />
          <InsightCardSkeleton />
          <InsightCardSkeleton />
        </>
      )}

      {/* Results */}
      {!loading && data?.insights.map((item, i) => (
        <InsightCard key={i} item={item} />
      ))}
    </div>
  );
}
```

**Step 2: Build verify**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: `✓ built in X.XXs` with no errors.

**Step 3: Commit**

```bash
git add frontend/src/components/CompanyInsightsFeed.tsx
git commit -m "feat(ui): add CompanyInsightsFeed with Claude-powered insights"
```

---

## Task 8: Wire into StockDashboard Overview section

**Files:**
- Modify: `frontend/src/components/StockDashboard.tsx`

**Step 1: Add imports (after existing imports, around line 25)**

Find the existing import block with `IndustryMultipleTab`, `PiotroskiTab`, `SegmentsTab`.
Add two new imports:

```tsx
import StockPriceChart      from "./StockPriceChart";
import CompanyInsightsFeed  from "./CompanyInsightsFeed";
```

**Step 2: Replace the Overview section**

Find this block (around line 583):

```tsx
{activeTab === "Overview" && (
  ov
    ? <div style={{ maxWidth: 900, marginTop: 8 }}>
        <h4 style={{
          fontSize: "0.72em", fontWeight: 700,
          textTransform: "uppercase", letterSpacing: "0.09em",
          color: "#4d6b88", margin: "0 0 8px",
        }}>
          About
        </h4>
        {ov.description
          ? <p style={{ color: "#4d6b88", fontSize: "0.92em", lineHeight: 1.75, margin: 0 }}>{ov.description}</p>
          : <p style={{ color: "#9ca3af", fontStyle: "italic", margin: 0 }}>No company description available.</p>
        }
        <SegmentsTab ticker={ticker} />
      </div>
    : null
)}
```

Replace with:

```tsx
{activeTab === "Overview" && (
  ov
    ? <div style={{ maxWidth: 1100, marginTop: 8 }}>
        {/* ── About + Chart (two-column) ──────────────────────────────── */}
        <div style={{
          display: "flex", gap: 28, flexWrap: "wrap", alignItems: "flex-start",
        }}>
          {/* Left: description */}
          <div style={{ flex: 1, minWidth: 280 }}>
            <h4 style={{
              fontSize: "0.72em", fontWeight: 700,
              textTransform: "uppercase", letterSpacing: "0.09em",
              color: "#4d6b88", margin: "0 0 8px",
            }}>
              About
            </h4>
            {ov.description
              ? <p style={{ color: "#4d6b88", fontSize: "0.92em", lineHeight: 1.75, margin: 0 }}>{ov.description}</p>
              : <p style={{ color: "#9ca3af", fontStyle: "italic", margin: 0 }}>No company description available.</p>
            }
          </div>

          {/* Right: price chart */}
          <div style={{ flex: 1.2, minWidth: 320 }}>
            <StockPriceChart ticker={ticker} />
          </div>
        </div>

        {/* ── AI News & Insights feed ──────────────────────────────────── */}
        <CompanyInsightsFeed ticker={ticker} ov={ov} />

        {/* ── Segments (existing, unchanged) ──────────────────────────── */}
        <SegmentsTab ticker={ticker} />
      </div>
    : null
)}
```

**Step 3: Full build verify**

```bash
cd frontend && npm run build 2>&1
```
Expected: `✓ built in X.XXs` with zero TypeScript errors.

**Step 4: Commit**

```bash
git add frontend/src/components/StockDashboard.tsx
git commit -m "feat(overview): integrate StockPriceChart and CompanyInsightsFeed into Overview tab"
```

---

## Task 9: Final integration test

**Step 1: Start backend**

```bash
uvicorn backend.main:app --reload
```

**Step 2: Start frontend dev server**

```bash
cd frontend && npm run dev
```

**Step 3: Manual test checklist**

Open http://localhost:5173, search `AAPL`:
- [ ] Overview tab shows two-column layout (description left, chart right)
- [ ] Chart renders with price line and volume bars
- [ ] Timeframe buttons (1D through 10Y) switch chart data correctly
- [ ] "AI News & Insights" section appears below with shimmer while loading (~3s)
- [ ] InsightCards render with headline, date badge, summary
- [ ] Clicking `⚡ Model Impact` expands the blue-bordered impact panel
- [ ] Clicking again collapses it
- [ ] SegmentsTab still renders below insights (unchanged)

Search a non-US ticker (`BMW.DE`) and verify:
- [ ] Chart loads (may have fewer data points for international)
- [ ] If no FMP news available, insights section is silently absent

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(overview): complete Company Overview enhancement — chart + AI insights"
```

---

## Summary of all files changed

| File | Action |
|---|---|
| `requirements.txt` | Add `anthropic>=0.25.0` |
| `frontend/package.json` | Add `recharts` |
| `frontend/src/types.ts` | Add `PriceRange`, `PricePoint`, `PriceHistoryData`, `NewsInsight`, `NewsInsightsData` |
| `backend/main.py` | Add `GET /api/price-history/{ticker}` and `POST /api/news-insights/{ticker}` |
| `frontend/src/components/StockPriceChart.tsx` | **New** — Recharts chart with timeframes |
| `frontend/src/components/InsightCard.tsx` | **New** — Card + skeleton |
| `frontend/src/components/CompanyInsightsFeed.tsx` | **New** — Feed orchestrator |
| `frontend/src/components/StockDashboard.tsx` | Replace Overview section with two-column layout |
