class ProfileAgent:
    """
    Transforms raw FMP /profile + enrichment data (from fetch_overview) into
    an ordered list of display rows for the Cardinal Overview Table.

    Each row: {"label": str, "value": str, "color": str | None}
    color is set only for the Price row (green = up, red = down).
    """

    # ISO 3166-1 alpha-2 → emoji flag (fallback for country-based flag in header)
    COUNTRY_FLAGS = {
        "US": "🇺🇸", "GB": "🇬🇧", "IL": "🇮🇱",
        "DE": "🇩🇪", "FR": "🇫🇷", "CN": "🇨🇳",
        "JP": "🇯🇵", "CA": "🇨🇦", "AU": "🇦🇺",
        "IN": "🇮🇳", "KR": "🇰🇷", "SE": "🇸🇪",
        "CH": "🇨🇭", "NL": "🇳🇱", "SG": "🇸🇬",
        "BR": "🇧🇷", "TW": "🇹🇼", "HK": "🇭🇰",
        "NO": "🇳🇴", "DK": "🇩🇰", "FI": "🇫🇮",
        "IE": "🇮🇪", "IT": "🇮🇹", "ES": "🇪🇸",
        "MX": "🇲🇽", "ZA": "🇿🇦", "RU": "🇷🇺",
        "SA": "🇸🇦", "AR": "🇦🇷", "CL": "🇨🇱",
        "PT": "🇵🇹", "BE": "🇧🇪", "AT": "🇦🇹",
        "NZ": "🇳🇿", "TH": "🇹🇭", "ID": "🇮🇩",
        "MY": "🇲🇾", "PH": "🇵🇭", "PK": "🇵🇰",
    }

    def __init__(self, raw: dict):
        self.data = raw or {}

    # ── flag ──────────────────────────────────────────────────────────────────

    def get_flag(self) -> str:
        code = str(self.data.get("country", "")).strip().upper()
        return self.COUNTRY_FLAGS.get(code, "🏳️")

    # ── formatters ────────────────────────────────────────────────────────────

    @staticmethod
    def _price_str(price, chg_pct) -> tuple[str, str]:
        """Returns (formatted_string, css_color)."""
        try:
            p = float(price)
            c = float(str(chg_pct).replace("%", "").strip())
            sign = "+" if c >= 0 else ""
            color = "#22c55e" if c >= 0 else "#ef4444"
            return f"${p:,.2f} ({sign}{c:.2f}%)", color
        except (TypeError, ValueError):
            return "N/A", None

    @staticmethod
    def _cap(v) -> str:
        try:
            v = float(v)
            if v <= 0:
                return "N/A"
            for thr, sfx in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
                if v >= thr:
                    return f"${v / thr:.2f}{sfx}"
            return f"${v:,.0f}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _vol(v) -> str:
        try:
            v = float(v)
            if v <= 0:
                return "N/A"
            for thr, sfx in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
                if v >= thr:
                    return f"{v / thr:.2f}{sfx}"
            return f"{v:,.0f}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _pct(v) -> str:
        if v is None:
            return "N/A"
        try:
            f = float(str(v).replace("%", "").strip())
            return f"{f:.2f}%" if f != 0 else "N/A"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _num(v, dec: int = 2) -> str:
        try:
            f = float(v)
            return f"{f:,.{dec}f}" if f != 0 else "N/A"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _date(v) -> str:
        if not v:
            return "N/A"
        s = str(v).strip()
        # Trim timestamp if present: "2025-11-05T00:00:00" → "2025-11-05"
        return s[:10] if len(s) >= 10 else s

    @staticmethod
    def _employees(v) -> str:
        if not v:
            return "N/A"
        try:
            return f"{int(str(v).replace(',', '')):,}"
        except (TypeError, ValueError):
            return str(v)

    # ── public API ────────────────────────────────────────────────────────────

    def get_rows(self) -> list[dict]:
        """
        Returns 18 ordered rows: [{"label": str, "value": str, "color": str|None}]
        Exact order specified by the Cardinal Overview Table requirement.
        """
        d = self.data

        price_str, price_color = self._price_str(
            d.get("price"), d.get("changesPercentage", 0)
        )

        # EPS: prefer enriched _eps from income-statement, fall back to profile field
        eps_raw = d.get("_eps") or d.get("eps")
        # Short float: check all known FMP field names
        short_raw = (d.get("shortPercent")
                     or d.get("shortPercentOfFloat")
                     or d.get("shortRatio"))

        def row(label, value, color=None):
            return {"label": label, "value": value or "N/A", "color": color}

        return [
            row("Ticker",                   d.get("symbol", "N/A")),
            row("Company Name",             d.get("companyName", "N/A")),
            row("Price",                    price_str, price_color),
            row("Sector",                   d.get("sector") or "N/A"),
            row("Industry",                 d.get("industry") or "N/A"),
            row("Latest Fiscal Year",       d.get("_latestFiscalYear") or "N/A"),
            row("Next Earnings Date",       self._date(d.get("earningsAnnouncement"))),
            row("Avg. Daily Volume",        self._vol(d.get("volAvg"))),
            row("Market Cap",               self._cap(d.get("mktCap"))),
            row("P/E",                      self._num(d.get("pe"))),
            row("EPS (TTM)",                self._num(eps_raw)),
            row("Beta",                     self._num(d.get("beta"))),
            row("Ex-Dividend Date",         self._date(d.get("exDividendDate") or d.get("lastDiv"))),
            row("% Held by Insiders",       self._pct(d.get("heldByInsiders"))),
            row("% Held by Institutions",   self._pct(d.get("heldByInstitutions")
                                                      or d.get("institutionalHolderProp"))),
            row("Put/Call Interest",        d.get("putCallRatio") or "N/A"),
            row("Short Float",              self._pct(short_raw)),
            row("Num. of Employees",        self._employees(d.get("fullTimeEmployees"))),
        ]

    # keep backwards-compat alias used by nothing externally, but safe to have
    def get_metrics(self) -> list[dict]:
        return self.get_rows()
