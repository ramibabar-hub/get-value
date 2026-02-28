class ProfileAgent:
    """
    Transforms raw FMP /profile data into display-ready metrics.
    All fields degrade gracefully to "N/A" when absent or zero.
    """

    # ISO 3166-1 alpha-2 country code → emoji flag
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

    # ── private formatters ────────────────────────────────────────────────────

    def _flag(self) -> str:
        code = str(self.data.get("country", "")).strip().upper()
        return self.COUNTRY_FLAGS.get(code, "🏳️")

    @staticmethod
    def _price(v) -> str:
        try:
            return f"${float(v):,.2f}" if v is not None else "N/A"
        except (TypeError, ValueError):
            return "N/A"

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
    def _employees(v) -> str:
        if not v:
            return "N/A"
        try:
            return f"{int(str(v).replace(',', '')):,}"
        except (TypeError, ValueError):
            return str(v)

    # ── public API ────────────────────────────────────────────────────────────

    def get_metrics(self) -> dict:
        d = self.data

        raw_chg = d.get("changesPercentage", 0) or 0
        try:
            chg = float(str(raw_chg).replace("%", "").strip())
        except (TypeError, ValueError):
            chg = 0.0

        # short float: FMP may expose shortPercent (0–1 scale) or shortRatio
        short_raw = d.get("shortPercent") or d.get("shortRatio")

        return {
            # Identity
            "flag":         self._flag(),
            "company_name": d.get("companyName", ""),
            "ticker":       d.get("symbol", ""),
            "exchange":     d.get("exchangeShortName") or d.get("exchange", ""),
            # Basic Info
            "sector":       d.get("sector") or "N/A",
            "industry":     d.get("industry") or "N/A",
            "next_earnings": d.get("earningsAnnouncement") or "N/A",
            "employees":    self._employees(d.get("fullTimeEmployees")),
            # Valuation
            "price":        self._price(d.get("price")),
            "change_pct":   f"{'+' if chg >= 0 else ''}{chg:.2f}%",
            "change_positive": chg >= 0,
            "mkt_cap":      self._cap(d.get("mktCap")),
            "pe":           self._num(d.get("pe")),
            # Risk / Short
            "beta":         self._num(d.get("beta")),
            "short_float":  self._pct(short_raw),
            # Ownership
            "insider_own":  self._pct(d.get("heldByInsiders")),
            "inst_own":     self._pct(d.get("heldByInstitutions")),
        }
