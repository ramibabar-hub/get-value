# getValue — Financial Models Library

Internal reference for Rami and the getValue development team.

---

## What we have

This directory contains 42 institutional-grade financial analysis skill frameworks,
sourced from Anthropic's official Financial Services Plugins repository and reorganized
for the getValue platform. These are **AI instruction frameworks** — structured prompts
and workflows that tell Claude exactly how to reason through each financial model,
following Wall Street professional standards.

Think of each skill as a senior analyst sitting next to you who knows precisely
how Goldman, KKR, or a top equity research desk would approach each task.

---

## Directory structure

```
backend/financial_models/
  skills/
    equity_research/        9 skills   — earnings, sector, initiating coverage, thesis tracking
    financial_analysis/     8 skills   — DCF, LBO, Comps, 3-statements, competitive analysis
    investment_banking/     9 skills   — pitch deck, merger model, CIM, buyer list, deal tracker
    private_equity/         9 skills   — IC memo, DD, deal screening, returns (IRR/MOIC), portfolio
    wealth_management/      6 skills   — client reports, financial plans, portfolio rebalance, TLH
  utils/
    validate_dcf.py         Python — validates Excel DCF models for formula errors + logic checks
    extract_numbers.py      Python — extracts financial numbers from markdown/presentation content
  legacy_tools/
    init_skill.py           Meta-tool for creating new skill packages (not for getValue users)
    package_skill.py        Meta-tool for packaging skills
    quick_validate.py       Meta-tool for skill validation
```

---

## The 42 skills — what they do and how to use them

### Equity Research (9 skills)

| File | What it does | getValue use case |
|---|---|---|
| `earnings_analysis.md` | Full earnings report with consensus comparison, surprise analysis, guidance revision | "Analyze {ticker} Q3 earnings" feature |
| `earnings_preview.md` | Pre-earnings setup: what to watch, consensus, key risks | Pre-earnings briefing card |
| `catalyst_calendar.md` | Maps upcoming value catalysts (product launches, regulatory, macro) | Catalyst timeline in Overview tab |
| `initiating_coverage.md` | Full initiation report with 5-task workflow: research → model → valuation → charts → report | Deep-dive report generation |
| `model_update.md` | Updates financial model post-earnings or guidance change | Post-earnings model refresh |
| `morning_note.md` | Daily market brief for a coverage list | Morning briefing for watchlist |
| `sector_overview.md` | Sector-level thematic analysis with peer ranking | Sector comparison tab |
| `thesis_tracker.md` | Tracks investment thesis milestones and whether the story is intact | Thesis health dashboard |
| `idea_generation.md` | Screens for investment ideas based on criteria | Stock screener integration |

**References included:**
- `references/report_template.md` — professional initiation report structure
- `references/quality_checklist.md` — pre-publish checklist for research notes
- `references/valuation_methodologies.md` — when to use DCF vs. Comps vs. DDM vs. Sum-of-Parts
- `references/earnings_best_practices.md` / `earnings_workflow.md` / `earnings_report_structure.md`

---

### Financial Analysis (8 skills)

| File | What it does | getValue use case |
|---|---|---|
| `dcf_model.md` | Institutional DCF with 5-year FCF projection, WACC, terminal value, sensitivity tables (75 cells), sourced cell comments | "Generate DCF model" button → Excel download |
| `lbo_model.md` | LBO model with Sources & Uses, operating model, debt schedule, returns (IRR/MOIC) | LBO tab for PE-style analysis |
| `comps_analysis.md` | Trading comps with EV/EBITDA, EV/Revenue, P/E, NTM vs. LTM, statistical benchmarking | Industry Comps tab (current Financials Extended enriched) |
| `three_statements.md` | Builds integrated IS + BS + CF model with proper balance sheet plugs | 3-statement model generation |
| `competitive_analysis.md` | Porter's Five Forces + SWOT + peer benchmarking in structured format | Competitive analysis card |
| `check_deck.md` | Audits a pitch deck or research report for number consistency | "Check my analysis" quality tool |
| `check_model.md` | Audits a financial model for logic errors, circular refs, and formula issues | Model validation |
| `dcf_troubleshooting.md` | Common DCF mistakes and fixes | Developer reference |

**References included:**
- `references/three_statement_formulas.md` — exact Excel formulas for IS/BS/CF linkages
- `references/three_statement_formatting.md` — color conventions, number formats
- `references/sec_filings_guide.md` — how to read SEC filings for model inputs
- `references/competitive_frameworks.md` — Porter's 5 Forces, SWOT, BCG matrix templates
- `references/ib_terminology.md` — Wall Street glossary for AI output standardization
- `references/report_format.md` — slide/report formatting standards

---

### Investment Banking (9 skills)

| File | What it does | getValue use case |
|---|---|---|
| `pitch_deck.md` | Full M&A or financing pitch deck in PowerPoint/pptx | "Generate pitch deck" for a stock |
| `merger_model.md` | M&A accretion/dilution analysis with synergies | Merger model tab |
| `cim_builder.md` | Confidential Information Memorandum builder | CIM generation |
| `buyer_list.md` | Strategic + financial buyer identification for M&A | M&A buyer universe tool |
| `deal_tracker.md` | Live deal pipeline tracker with status, valuation, timeline | Deal monitoring dashboard |
| `teaser.md` | Anonymous 2-page company teaser for M&A | Company teaser export |
| `process_letter.md` | M&A process letter (bid instructions, timeline, data room access) | Process management |
| `strip_profile.md` | Anonymized company profile for buyer outreach | Blind profile generator |
| `datapack_builder.md` | Financial data package for due diligence rooms | DD data room builder |

**References included:**
- `references/calculation_standards.md` — IB calculation standards (EV, equity bridge, dilution)
- `references/formatting_standards.md` — Goldman/JPM slide formatting conventions
- `references/slide_templates.md` — XML-level PowerPoint slide templates

---

### Private Equity (9 skills)

| File | What it does | getValue use case |
|---|---|---|
| `returns_analysis.md` | IRR/MOIC sensitivity tables (entry multiple × leverage × exit multiple × hold period) | PE Returns tab — augments our existing CF+IRR |
| `ic_memo.md` | Full Investment Committee memo with deal rationale, risks, returns, structure | IC memo generation |
| `dd_checklist.md` | Due diligence checklist across commercial, financial, legal, HR, IT workstreams | DD tracking tool |
| `dd_meeting_prep.md` | Prepares questions and agenda for management DD sessions | Meeting prep assistant |
| `deal_screening.md` | Quick deal screening against investment criteria (size, sector, geography, returns threshold) | Deal screening filter |
| `deal_sourcing.md` | Proprietary deal sourcing strategy and outreach scripts | Deal sourcing module |
| `portfolio_monitoring.md` | Portfolio company KPI monitoring with variance analysis vs. budget | Portfolio dashboard |
| `unit_economics.md` | LTV, CAC, payback, gross margin, contribution margin per unit | Unit economics breakdown |
| `value_creation_plan.md` | 100-day plan + ongoing value creation initiatives post-acquisition | VCP generator |

---

### Wealth Management (6 skills)

| File | What it does | getValue use case |
|---|---|---|
| `client_report.md` | Quarterly client portfolio performance report | Premium client reporting |
| `client_review.md` | Annual client review prep with portfolio analysis and recommendations | Review meeting prep |
| `financial_plan.md` | Full financial plan: goals, cash flow, retirement, estate, tax | Financial planning tool |
| `investment_proposal.md` | Portfolio proposal with asset allocation, expected returns, risk | Investment proposal generator |
| `portfolio_rebalance.md` | Tax-efficient rebalancing recommendation with drift analysis | Rebalancing calculator |
| `tax_loss_harvesting.md` | TLH opportunity scanner with wash sale rule compliance | TLH scanner |

---

## Python utilities

### `utils/validate_dcf.py`
Validates an Excel DCF model file for:
- Missing required sheets (DCF, WACC, Sensitivity)
- Formula errors (`#REF!`, `#DIV/0!`, etc.)
- Critical logic: terminal growth rate < WACC (math break if violated)
- WACC in reasonable range (5%–20%)
- Terminal value as % of EV (healthy range: 40%–80%)

```bash
python backend/financial_models/utils/validate_dcf.py model.xlsx
python backend/financial_models/utils/validate_dcf.py model.xlsx results.json
```

Returns JSON with `status: PASS/FAIL`, `errors[]`, `warnings[]`, `info[]`.

### `utils/extract_numbers.py`
Extracts all financial numbers from markdown/text content and flags inconsistencies.
Detects units (B/M/K/%), categories (revenue/EBITDA/margin/multiple/valuation),
and groups by slide number (for pitch deck consistency checks).

```bash
python backend/financial_models/utils/extract_numbers.py analysis.md
python backend/financial_models/utils/extract_numbers.py analysis.md --check  # flag inconsistencies
python backend/financial_models/utils/extract_numbers.py analysis.md -o numbers.json
```

---

## How to integrate skills into getValue features

### Option A — AI-powered "Deep Analysis" button (recommended next feature)
Each skill file is a self-contained prompt. To add an AI analysis feature:

1. Read the relevant `.md` skill file at runtime
2. Combine with live financial data from our existing API endpoints
3. Send to Claude API with the skill as the system prompt
4. Stream the response to the frontend

Example for a "Generate Initiation Report" feature:
```python
from pathlib import Path

skill_text = Path("backend/financial_models/skills/equity_research/initiating_coverage.md").read_text()
financial_data = await fetch_all(ticker)  # our existing gateway

response = anthropic.messages.create(
    model="claude-opus-4-6",
    system=skill_text,
    messages=[{"role": "user", "content": f"Initiate coverage on {ticker}. Data: {financial_data}"}]
)
```

### Option B — Educational overlays
Use the reference files to power tooltips and "Learn more" panels explaining
financial concepts (e.g., how WACC is calculated, what EV/EBITDA means).

### Option C — Validation layer
Run `validate_dcf.py` on any Excel model uploaded by users before analysis,
to catch errors before they corrupt downstream AI analysis.

---

## Dependencies added to requirements.txt

```
openpyxl>=3.0.0    # Excel model reading/writing
yfinance>=0.2.0    # Market data for DCF
```

---

## Original source

Anthropic Financial Services Plugins:
`backend/financial-services-plugins-main/` (original, untouched)

All content in `backend/financial_models/` is a clean extraction of the computational
and instructional content — no plugin manifests, hooks configs, or development
meta-tools (those live in `legacy_tools/` if needed).
