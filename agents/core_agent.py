"""
DataNormalizer — Transforms raw FMP data into structured tables.

Layout:
    Rows    = Financial line items  (Revenue, Net Income, CapEx, ...)
    Columns = Time periods          (TTM, FY2024, FY2023, ... or Q3 2024, Q2 2024, ...)

TTM Rule (consistent across both views):
    FLOW  items (Income Stmt / Cash Flow) → sum of last 4 quarters
    STOCK items (Balance Sheet)           → most recent quarter value
"""

import math
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from report_schema import SCHEMA, ITEMS_BY_KEY, StatementType, ItemType


class DataNormalizer:
    def __init__(self, raw_data: dict, ticker: str):
        self.raw_data = raw_data
        self.ticker = ticker.upper()
        self._ttm_cache: Optional[dict] = None  # computed once, reused

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _safe(self, record: dict, key: str) -> Optional[float]:
        val = record.get(key)
        if val is None:
            return None
        try:
            f = float(val)
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _quarter_label(date_str: str) -> str:
        """'2024-06-30' → 'Q2 2024'"""
        year, month, *_ = date_str.split("-")
        quarter = (int(month) - 1) // 3 + 1
        return f"Q{quarter} {year}"

    def _tag(self, records: list, view: str) -> list:
        """Attach _period_label to each record dict."""
        tagged = []
        for r in records:
            r = dict(r)
            r["_period_label"] = (
                r["date"][:4] if view == "annual" else self._quarter_label(r["date"])
            )
            tagged.append(r)
        return tagged

    def _merge(self, view: str, count: Optional[int] = None) -> list:
        """
        Merge all three statements into one list of period-dicts.
        Each dict contains fields from all statements for that period.
        Sorted newest → oldest.
        """
        by_label: dict[str, dict] = {}
        for stmt in StatementType:
            key = f"{view}_{stmt.name}"
            records = self.raw_data.get(key, [])
            for r in self._tag(records, view):
                label = r["_period_label"]
                if label not in by_label:
                    by_label[label] = {"_period_label": label, "date": r.get("date", "")}
                by_label[label].update(r)

        # Sort by raw date descending (most recent first)
        merged = sorted(by_label.values(), key=lambda x: x.get("date", ""), reverse=True)
        return merged[:count] if count else merged

    # ── TTM ───────────────────────────────────────────────────────────────────

    def _compute_ttm(self) -> dict:
        """
        Compute TTM for every item in SCHEMA.

        Called once; result is cached in self._ttm_cache.
        """
        if self._ttm_cache is not None:
            return self._ttm_cache

        ttm: dict[str, Optional[float]] = {}
        for item in SCHEMA:
            quarters = self.raw_data.get(f"quarterly_{item.statement.name}", [])
            if not quarters:
                ttm[item.fmp_key] = None
                continue

            if item.item_type == ItemType.STOCK:
                # Balance sheet: point-in-time → latest quarter
                ttm[item.fmp_key] = self._safe(quarters[0], item.fmp_key)

            else:
                # Flow: sum last 4 quarters
                values = [
                    v
                    for q in quarters[:4]
                    if (v := self._safe(q, item.fmp_key)) is not None
                ]
                if len(values) == 4:
                    ttm[item.fmp_key] = sum(values)
                elif values:
                    # Partial data: sum what we have (flagged implicitly by < 4 values)
                    ttm[item.fmp_key] = sum(values)
                else:
                    ttm[item.fmp_key] = None

        self._ttm_cache = ttm
        return ttm

    # ── Row builder ───────────────────────────────────────────────────────────

    def _build_row(self, fmp_key: str, period_records: list) -> dict:
        item = ITEMS_BY_KEY.get(fmp_key)
        if not item:
            return {}

        row: dict = {"label": item.label}
        row["TTM"] = self._compute_ttm().get(fmp_key)

        for record in period_records:
            row[record["_period_label"]] = self._safe(record, fmp_key)

        return row

    # ── Public tables ─────────────────────────────────────────────────────────

    def build_annual_table(self) -> list[dict]:
        """
        Annual table: TTM | FY2024 | FY2023 | … (up to 10 years)
        Rows ordered by SCHEMA definition.
        """
        periods = self._merge("annual")
        return [row for item in SCHEMA if (row := self._build_row(item.fmp_key, periods))]

    def build_quarterly_table(self) -> list[dict]:
        """
        Quarterly table: TTM | Q3 2024 | Q2 2024 | … (10 quarters)
        TTM values are identical to those in the annual table.
        """
        periods = self._merge("quarterly", count=10)
        return [row for item in SCHEMA if (row := self._build_row(item.fmp_key, periods))]

    def get_column_headers(self, view: str = "annual") -> list[str]:
        """Return ordered column headers: ['Item', 'TTM', period1, period2, ...]"""
        if view == "annual":
            period_labels = [r["_period_label"] for r in self._merge("annual")]
        else:
            period_labels = [r["_period_label"] for r in self._merge("quarterly", count=10)]
        return ["Item", "TTM"] + period_labels
