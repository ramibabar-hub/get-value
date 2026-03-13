"""
run_getValue.py — Entry point for the getValue financial data tool.

Usage:
    python run_getValue.py AAPL
    python run_getValue.py MSFT --view annual
    python run_getValue.py TSLA --view quarterly
    python run_getValue.py AAPL --json
"""

import argparse
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

load_dotenv()


# ── Display helpers ───────────────────────────────────────────────────────────

SECTION_BREAKS = {
    "Revenue":             "── Income Statement ─────────────────────────────────",
    "Cash & Equivalents":  "── Balance Sheet ────────────────────────────────────",
    "Operating Cash Flow": "── Cash Flow ────────────────────────────────────────",
}


def _fmt(val) -> str:
    if val is None:
        return "—"
    if not isinstance(val, float):
        return str(val)
    abs_val = abs(val)
    if abs_val >= 1e12:
        return f"{val/1e12:.2f}T"
    if abs_val >= 1e9:
        return f"{val/1e9:.2f}B"
    if abs_val >= 1e6:
        return f"{val/1e6:.2f}M"
    if abs_val >= 1e3:
        return f"{val/1e3:.1f}K"
    if abs_val < 1 and val != 0:
        return f"{val:.4f}"
    return f"{val:,.0f}"


def print_table(rows: list[dict], headers: list[str], title: str = "") -> None:
    if title:
        print(f"\n{'═' * 90}")
        print(f"  {title}")
        print(f"{'═' * 90}")

    if not rows:
        print("  No data available.")
        return

    # Column widths: label col is wider
    col_w = [28] + [12] * (len(headers) - 1)

    # Header
    header_line = "  ".join(str(h)[:w].ljust(w) for h, w in zip(headers, col_w))
    print(f"\n  {header_line}")
    print(f"  {'─' * len(header_line)}")

    for row in rows:
        label = row.get("label", "")

        # Section separator
        if label in SECTION_BREAKS:
            print(f"\n  {SECTION_BREAKS[label]}")

        cells = [label] + [_fmt(row.get(h)) for h in headers[1:]]
        line = "  ".join(str(c)[:w].ljust(w) for c, w in zip(cells, col_w))
        print(f"  {line}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(ticker: str, view: str = "both", output_json: bool = False) -> None:
    from agents.gateway_agent import GatewayAgent
    from agents.core_agent import DataNormalizer

    print(f"\n  getValue › {ticker.upper()}")
    print("  Fetching data from FMP...\n")

    try:
        gateway = GatewayAgent()
        raw_data = gateway.fetch_all(ticker)
    except (ValueError, RuntimeError) as e:
        print(f"\n  [ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    normalizer = DataNormalizer(raw_data, ticker)

    if output_json:
        result = {}
        if view in ("annual", "both"):
            result["annual"] = normalizer.build_annual_table()
        if view in ("quarterly", "both"):
            result["quarterly"] = normalizer.build_quarterly_table()
        print(json.dumps(result, indent=2, default=str))
        return

    if view in ("annual", "both"):
        headers = normalizer.get_column_headers("annual")
        rows = normalizer.build_annual_table()
        print_table(rows, headers, title=f"{ticker.upper()} — Annual View  (10Y + TTM)")

    if view in ("quarterly", "both"):
        headers = normalizer.get_column_headers("quarterly")
        rows = normalizer.build_quarterly_table()
        print_table(rows, headers, title=f"{ticker.upper()} — Quarterly View  (10Q + TTM)")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="getValue — Financial statement viewer powered by FMP"
    )
    parser.add_argument("ticker", help="Stock ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--view",
        choices=["annual", "quarterly", "both"],
        default="both",
        help="Which view to display (default: both)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON instead of a formatted table",
    )
    args = parser.parse_args()
    run(args.ticker, view=args.view, output_json=args.output_json)


if __name__ == "__main__":
    main()
