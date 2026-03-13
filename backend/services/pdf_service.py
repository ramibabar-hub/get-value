"""
backend/services/pdf_service.py

Analyst-style one-page PDF export for the CF + IRR valuation model.
Generates a professional investment report matching the analyst one-pager style.

Called from cf_irr_tab.py:
    from backend.services.pdf_service import generate_cfirr_pdf
    pdf_bytes = generate_cfirr_pdf(...)
"""

from __future__ import annotations

import io
import math
import datetime
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")          # non-interactive backend — must precede pyplot import
import matplotlib.pyplot as plt
from fpdf import FPDF, XPos, YPos


# ─────────────────────────────────────────────────────────────────────────────
#  Colour palette  (mirrors app.py / cf_irr_tab.py)
# ─────────────────────────────────────────────────────────────────────────────
_NAVY      = (28,  43,  70)
_WHITE     = (255, 255, 255)
_LT_GREY   = (248, 250, 252)
_MID_GREY  = (226, 232, 240)
_SLATE     = (100, 116, 139)
_BODY_TXT  = (55,  65,  81)
_GRN_BG    = (209, 250, 229)
_GRN_FG    = (6,   95,  70)
_RED_BG    = (254, 226, 226)
_RED_FG    = (153, 27,  27)

# ─────────────────────────────────────────────────────────────────────────────
#  Page geometry  (A4 portrait, mm)
# ─────────────────────────────────────────────────────────────────────────────
_PW   = 210
_PH   = 297
_LM   = 8          # left margin
_RM   = 8          # right margin
_BW   = _PW - _LM - _RM   # 194 mm usable body width

_CL   = round(_BW * 0.48)           # left column  ≈ 93 mm
_GAP  = 2                            # gap between columns
_CR   = _BW - _CL - _GAP            # right column ≈ 99 mm


# ─────────────────────────────────────────────────────────────────────────────
#  Value formatters
# ─────────────────────────────────────────────────────────────────────────────
def _s(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None

def _fp(v)    -> str: f = _s(v); return "N/A" if f is None else f"${f:,.2f}"
def _fmm(v)   -> str: f = _s(v); return "N/A" if f is None else f"{f / 1e6:,.1f}"
def _fmmstr(v)-> str: f = _s(v); return "N/A" if f is None else f"{f:,.1f}"
def _fgr(v)   -> str: f = _s(v); return "-"   if f is None else f"{f:.1f}%"

def _is_summary(year_str: str) -> bool:
    y = str(year_str)
    return y in ("Average", "TTM") or y.startswith("CAGR")

def _col_widths(total: float, ratios: list) -> list:
    """Proportional column widths that sum exactly to total."""
    ws = [round(total * r, 1) for r in ratios]
    ws[-1] = round(total - sum(ws[:-1]), 1)
    return ws


# ─────────────────────────────────────────────────────────────────────────────
#  Price chart builder
# ─────────────────────────────────────────────────────────────────────────────
def _make_chart(hist_prices: list, ticker: str) -> bytes:
    """Return PNG bytes of a 7-year historical price chart, or b'' on failure."""
    try:
        cutoff = datetime.date.today() - datetime.timedelta(days=365 * 7)
        pts: list[tuple] = []
        for p in hist_prices:
            if not isinstance(p, dict):
                continue
            d_str = str(p.get("date") or "")[:10]
            try:
                d = datetime.date.fromisoformat(d_str)
            except ValueError:
                continue
            if d < cutoff:
                continue
            px = _s(p.get("adjClose") or p.get("close"))
            if px is not None:
                pts.append((d, px))

        if len(pts) < 10:
            return b""

        pts.sort()
        dates, prices = zip(*pts)
        xs = list(range(len(prices)))

        fig, ax = plt.subplots(figsize=(7.64, 1.4), dpi=150)
        fig.patch.set_facecolor("#f8fafc")
        ax.set_facecolor("#f8fafc")

        ax.plot(xs, prices, color="#1c2b46", linewidth=1.0, zorder=3)
        ax.fill_between(xs, prices, min(prices) * 0.97,
                        alpha=0.10, color="#1c2b46")

        # Six evenly-spaced date labels on X axis
        n = len(dates)
        idxs = [round(i * (n - 1) / 5) for i in range(6)]
        ax.set_xticks(idxs)
        ax.set_xticklabels(
            [dates[i].strftime("%b '%y") for i in idxs],
            fontsize=5.5, color="#475569",
        )
        ax.tick_params(axis="y", labelsize=5.5, colors="#475569")
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines["left"].set_color("#e2e8f0")
        ax.spines["bottom"].set_color("#e2e8f0")
        ax.grid(axis="y", color="#e2e8f0", linewidth=0.3, linestyle="--")
        ax.set_title(
            f"{ticker}  -  Historical Stock Price  (7-Year)",
            fontsize=6.5, color="#1c2b46", fontweight="bold", pad=2,
        )
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"${v:,.0f}")
        )

        plt.tight_layout(pad=0.3)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception:
        return b""


# ─────────────────────────────────────────────────────────────────────────────
#  Custom FPDF subclass
# ─────────────────────────────────────────────────────────────────────────────
class _PDF(FPDF):
    def footer(self):
        self.set_y(-9)
        self.set_font("Helvetica", "I", 5.8)
        self.set_text_color(*_SLATE)
        today = datetime.date.today().strftime("%d %b %Y")
        self.cell(
            0, 5,
            f"getValue -CF+IRR Valuation Model -{today}"
            "  - For informational purposes only. Not investment advice.",
            align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

    def fc(self, rgb): self.set_fill_color(*rgb)
    def tc(self, rgb): self.set_text_color(*rgb)


# ─────────────────────────────────────────────────────────────────────────────
#  Block renderers
# ─────────────────────────────────────────────────────────────────────────────
def _draw_banner(pdf: _PDF, ticker, company, sector, industry, date_str):
    H = 14.0
    pdf.fc(_NAVY)
    pdf.rect(0, 0, _PW, H, "F")

    # Left: TICKER (large) then full company name on the line below
    pdf.set_xy(_LM, 2.0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.tc(_WHITE)
    pdf.cell(0, 6, ticker, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    pdf.set_x(_LM)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.tc((170, 200, 225))
    safe_co = company.encode("latin-1", "replace").decode("latin-1")
    pdf.cell(110, 4.5, safe_co, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # Right-aligned metadata
    pdf.set_xy(_LM, 2.5)
    pdf.set_font("Helvetica", "", 5.5)
    pdf.tc((145, 175, 210))
    meta = "  |  ".join(x for x in [sector, industry, date_str] if x)
    safe_meta = meta.encode("latin-1", "replace").decode("latin-1")
    pdf.cell(_BW, 6, safe_meta, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(H + 1)


def _draw_metric_boxes(pdf: _PDF, boxes: list):
    """boxes = [(label, value, verdict: bool | None), ...]"""
    n   = len(boxes)
    bw  = _BW / n
    bh  = 9.0
    y0  = pdf.get_y()

    for i, (label, value, verdict) in enumerate(boxes):
        x  = _LM + i * bw
        bg = _GRN_BG if verdict is True  else _RED_BG if verdict is False else _LT_GREY
        fg = _GRN_FG if verdict is True  else _RED_FG if verdict is False else _NAVY

        pdf.fc(bg)
        pdf.rect(x, y0, bw - 0.5, bh, "F")

        pdf.set_xy(x + 1.5, y0 + 1.2)
        pdf.set_font("Helvetica", "", 5.0)
        pdf.tc(_SLATE)
        pdf.cell(bw - 3, 3.0, label, new_x=XPos.LEFT, new_y=YPos.NEXT)

        pdf.set_x(x + 1.5)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.tc(fg)
        pdf.cell(bw - 3, 4.5, value, new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_y(y0 + bh + 1)


def _draw_chart(pdf: _PDF, chart_png: bytes, h: float = 22.0):
    if not chart_png:
        return
    y0 = pdf.get_y()
    pdf.image(io.BytesIO(chart_png), x=_LM, y=y0, w=_BW, h=h)
    pdf.set_y(y0 + h + 1)


def _draw_table(
    pdf: _PDF,
    x: float, y: float, w: float,
    title: str,
    headers: list, col_w: list,
    rows: list,
    row_h: float = 3.0,
    hdr_h: float = 3.2,
    title_h: float = 3.5,
) -> float:
    """
    Draw a titled, header-row table inside column at (x, y) with width w.
    Returns the Y position after the last row.
    """
    pdf.set_xy(x, y)

    # Section title bar
    pdf.fc(_NAVY)
    pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.cell(w, title_h, f"  {title}", fill=True, border=0, align="L",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(0.3)
    pdf.set_x(x)

    # Header row
    pdf.fc(_NAVY)
    pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 4.8)
    for hdr, cw in zip(headers, col_w):
        pdf.cell(cw, hdr_h, hdr, fill=True, border=0, align="C",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(hdr_h)

    # Data rows
    for ri, row in enumerate(rows):
        year_str = str(row[0]) if row else ""
        special  = _is_summary(year_str)

        if special:
            pdf.fc(_MID_GREY); pdf.tc(_NAVY)
            pdf.set_font("Helvetica", "B", 4.8)
        elif ri % 2 == 0:
            pdf.fc(_LT_GREY); pdf.tc(_BODY_TXT)
            pdf.set_font("Helvetica", "", 4.8)
        else:
            pdf.fc(_WHITE); pdf.tc(_BODY_TXT)
            pdf.set_font("Helvetica", "", 4.8)

        pdf.set_x(x)
        for ci, (v, cw) in enumerate(zip(row, col_w)):
            align = "L" if ci == 0 else "R"
            pdf.cell(cw, row_h, str(v), fill=True, border=0, align=align,
                     new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(row_h)

    return pdf.get_y()


def _draw_final_output(pdf: _PDF, x, y, w, final_rows) -> float:
    """final_rows = [(metric_label, value_str, verdict: bool | None), ...]"""
    pdf.set_xy(x, y)
    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.cell(w, 3.5, "  5 -Final Output", fill=True, border=0, align="L",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(0.3)

    c_lbl = round(w * 0.61)
    c_val = w - c_lbl

    for metric, value, verdict in final_rows:
        bg = _GRN_BG if verdict is True  else _RED_BG if verdict is False else _LT_GREY
        fg = _GRN_FG if verdict is True  else _RED_FG if verdict is False else _BODY_TXT
        pdf.fc(bg); pdf.tc(fg)

        pdf.set_x(x)
        pdf.set_font("Helvetica", "", 5.0)
        pdf.cell(c_lbl, 3.8, f"  {metric}", fill=True, border=0, align="L",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "B", 5.0)
        pdf.cell(c_val, 3.8, value, fill=True, border=0, align="R",
                 new_x=XPos.LEFT, new_y=YPos.NEXT)

    return pdf.get_y()


def _draw_checklist(pdf: _PDF, x, y, w, checklist) -> float:
    """checklist = [(label, val, passed: bool | None, threshold), ...]"""
    pdf.set_xy(x, y)
    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.cell(w, 3.5, "  Quality Checklist", fill=True, border=0, align="L",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(0.3)
    pdf.set_x(x)

    c1 = round(w * 0.50)
    c2 = round(w * 0.24)
    c3 = w - c1 - c2

    # Sub-header
    pdf.fc(_MID_GREY); pdf.tc(_NAVY)
    pdf.set_font("Helvetica", "B", 4.5)
    pdf.set_x(x)
    pdf.cell(c1, 3.0, "  Metric",    fill=True, border=0, align="L",
             new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(c2, 3.0, "Value",       fill=True, border=0, align="C",
             new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(c3, 3.0, "Status",      fill=True, border=0, align="C",
             new_x=XPos.LEFT,  new_y=YPos.NEXT)

    for item in checklist:
        if isinstance(item, dict):
            label      = item.get("label",     "")
            val        = item.get("display",   "N/A")
            passed     = item.get("passed")
            _threshold = item.get("threshold", "")
        else:
            label, val, passed, _threshold = item
        label = str(label).encode("latin-1", "replace").decode("latin-1")
        val   = str(val).encode("latin-1", "replace").decode("latin-1")
        bg   = _GRN_BG if passed is True  else _RED_BG if passed is False else _LT_GREY
        fg   = _GRN_FG if passed is True  else _RED_FG if passed is False else _BODY_TXT
        icon = "PASS" if passed is True else "FAIL" if passed is False else "N/A"

        pdf.fc(bg); pdf.tc(fg)
        pdf.set_x(x)
        pdf.set_font("Helvetica", "", 4.8)
        pdf.cell(c1, 3.8, f"  {label}", fill=True, border=0, align="L",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(c2, 3.8, val,          fill=True, border=0, align="C",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "B", 4.8)
        pdf.cell(c3, 3.8, icon,         fill=True, border=0, align="C",
                 new_x=XPos.LEFT,  new_y=YPos.NEXT)

    return pdf.get_y()


def _draw_weighting_table(pdf: _PDF, ebitda_price, fcf_price, avg_target) -> float:
    """Weighting — Avg. Target Price table."""
    y0 = pdf.get_y()
    pdf.set_xy(_LM, y0)
    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.cell(_BW, 3.5, "  2 · Weighting  -  Avg. Target Price", fill=True, border=0, align="L",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(0.3)

    c1 = round(_BW * 0.50)
    c2 = round(_BW * 0.25)
    c3 = _BW - c1 - c2

    # Header
    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 4.8)
    pdf.set_x(_LM)
    for txt, w, align in [("Valuation Method", c1, "L"), ("Weighting", c2, "C"), ("Est. Stock Price", c3, "R")]:
        pdf.cell(w, 2.8, txt, fill=True, border=0, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(2.8)

    rows = [
        ("EV/EBITDA Method", "50%", ebitda_price),
        ("FCF Yield Method",  "50%", fcf_price),
    ]
    for i, (method, weight, price) in enumerate(rows):
        pdf.fc(_LT_GREY if i % 2 == 0 else _WHITE)
        pdf.tc(_BODY_TXT)
        pdf.set_x(_LM)
        pdf.set_font("Helvetica", "", 5.0)
        pdf.cell(c1, 3.5, f"  {method}", fill=True, border=0, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(c2, 3.5, weight,       fill=True, border=0, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "B", 5.0)
        price_str = _fp(price) if price is not None else "N/A"
        pdf.cell(c3, 3.5, price_str,    fill=True, border=0, align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)

    # Footer — avg target
    pdf.fc(_MID_GREY); pdf.tc(_NAVY)
    pdf.set_x(_LM)
    pdf.set_font("Helvetica", "B", 5.2)
    avg_str = _fp(avg_target) if avg_target is not None else "N/A"
    pdf.cell(c1, 3.8, "  Avg. Target Price", fill=True, border=0, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(c2, 3.8, "100%",               fill=True, border=0, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(c3, 3.8, avg_str,              fill=True, border=0, align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)

    return pdf.get_y()


def _draw_irr_schedule(pdf: _PDF, x: float, y: float, w: float,
                       rows: list, irr_val) -> float:
    """IRR Cash Flow Schedule — positioned at (x, y) with width w."""
    if not rows:
        return y

    irr_str  = f"IRR: {irr_val * 100:.1f}%" if irr_val is not None else "IRR: N/A"
    irr_pass = irr_val is not None and irr_val >= 0.12
    irr_warn = irr_val is not None and 0.08 <= irr_val < 0.12
    badge_fg = _GRN_FG if irr_pass else ((180, 100, 0) if irr_warn else _RED_FG)

    pdf.set_xy(x, y)

    # Title bar with IRR badge
    pdf.fc(_NAVY)
    pdf.rect(x, y, w, 4.5, "F")
    pdf.set_xy(x + 2, y + 0.5)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.tc(_WHITE)
    pdf.cell(w - 4, 4.0, "4 · IRR Cash Flow Schedule", border=0, align="L",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    # IRR badge right side
    pdf.set_xy(x, y + 0.5)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.tc(tuple(min(c + 80, 255) for c in badge_fg))
    pdf.cell(w - 2, 4.0, irr_str, border=0, align="R",
             new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_y(y + 4.5 + 0.3)

    # Column headers
    hdrs = ["Year", "Price", "Est. Adj. FCF/s", "Total CF"]
    cw   = _col_widths(w, [0.13, 0.22, 0.33, 0.32])

    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 4.8)
    pdf.set_x(x)
    for h, cw_ in zip(hdrs, cw):
        align = "L" if h == "Year" else "R"
        pdf.cell(cw_, 3.0, h, fill=True, border=0, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(3.0)

    for ri, row in enumerate(rows):
        pdf.fc(_LT_GREY if ri % 2 == 0 else _WHITE)
        pdf.tc(_BODY_TXT)
        pdf.set_font("Helvetica", "", 4.8)
        pdf.set_x(x)
        for ci, (v, cw_) in enumerate(zip(row, cw)):
            align = "L" if ci == 0 else "R"
            pdf.cell(cw_, 3.2, str(v), fill=True, border=0, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(3.2)

    # IRR footer
    if irr_val is not None:
        irr_disp = f"{irr_val * 100:.1f}%"
        bg = _GRN_BG if irr_pass else (_LT_GREY if irr_warn else _RED_BG)
        fg = _GRN_FG if irr_pass else (_NAVY    if irr_warn else _RED_FG)
        pdf.fc(bg); pdf.tc(fg)
        pdf.set_font("Helvetica", "B", 5.0)
        pdf.set_x(x)
        total_w = sum(cw[:-1])
        pdf.cell(total_w, 4.0, "  IRR", fill=True, border=0, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(cw[-1],  4.0, irr_disp, fill=True, border=0, align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)

    return pdf.get_y()


def _draw_irr_sensitivity(pdf: _PDF, x: float, y: float, w: float,
                          irr_sensitivity: dict, price_now) -> float:
    """IRR Sensitivity Matrix — positioned at (x, y) with width w."""
    row_labels = irr_sensitivity.get("row_labels") or []
    col_labels = irr_sensitivity.get("col_labels") or []
    matrix     = irr_sensitivity.get("matrix")     or []
    if not row_labels or not col_labels or not matrix:
        return y

    pdf.set_xy(x, y)
    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.cell(w, 4.5,
             "  IRR Sensitivity  |  >=12% green  |  8-12% amber  |  <8% red",
             fill=True, border=0, align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(0.3)

    # Find highlight row
    highlight_row = None
    if price_now is not None and row_labels:
        best_diff = None
        for i, lbl in enumerate(row_labels):
            try:
                p = float(str(lbl).replace("$", "").replace(",", ""))
            except ValueError:
                continue
            diff = abs(p - price_now)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                highlight_row = i

    n_cols   = len(col_labels)
    label_w  = round(w * 0.18)
    data_w   = round((w - label_w) / n_cols, 1)
    row_h    = 3.8

    # Column headers
    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 4.5)
    pdf.set_x(x)
    pdf.cell(label_w, 3.0, "Entry Price", fill=True, border=0, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    for col in col_labels:
        pdf.cell(data_w, 3.0, str(col), fill=True, border=0, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(3.0)

    # Data rows
    for ri, (row_label, row_vals) in enumerate(zip(row_labels, matrix)):
        is_highlight = (ri == highlight_row)
        label_bg = (28, 43, 100) if is_highlight else _NAVY
        pdf.fc(label_bg); pdf.tc(_WHITE)
        pdf.set_font("Helvetica", "B" if is_highlight else "", 4.5)
        pdf.set_x(x)
        pdf.cell(label_w, row_h, str(row_label), fill=True, border=0, align="C",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)

        for irr_cell in (row_vals or []):
            v = irr_cell
            if v is None:
                bg, fg, txt = _LT_GREY, _SLATE, "N/A"
            elif v >= 0.12:
                bg, fg, txt = _GRN_BG, _GRN_FG, f"{v * 100:.1f}%"
            elif v >= 0.08:
                bg, fg, txt = (255, 251, 235), (146, 64, 14), f"{v * 100:.1f}%"
            else:
                bg, fg, txt = _RED_BG, _RED_FG, f"{v * 100:.1f}%"

            pdf.set_font("Helvetica", "B" if is_highlight else "", 4.5)
            pdf.fc(bg); pdf.tc(fg)
            pdf.cell(data_w, row_h, txt, fill=True, border=0, align="C",
                     new_x=XPos.RIGHT, new_y=YPos.TOP)

        pdf.ln(row_h)

    return pdf.get_y()


def _draw_description(pdf: _PDF, text: str, company: str) -> None:
    """Render a compact company description block at the current Y position."""
    if not text or len(text.strip()) < 30:
        return
    pdf.ln(1)
    y0 = pdf.get_y()
    pdf.set_xy(_LM, y0)

    # Title bar
    pdf.fc(_NAVY); pdf.tc(_WHITE)
    pdf.set_font("Helvetica", "B", 5.8)
    title = f"About {company}".encode("latin-1", "replace").decode("latin-1") if company else "Business Description"
    pdf.cell(_BW, 3.5, f"  {title}", fill=True, border=0, align="L",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(0.3)
    pdf.set_x(_LM)

    # Body text — truncate at 600 chars
    safe = text.encode("latin-1", "replace").decode("latin-1")
    if len(safe) > 600:
        safe = safe[:597] + "..."

    pdf.fc(_LT_GREY); pdf.tc(_BODY_TXT)
    pdf.set_font("Helvetica", "", 5.0)
    pdf.multi_cell(_BW, 3.2, f"  {safe}", fill=True, border=0, align="L")


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────────────────────
def generate_cfirr_pdf(
    ticker: str,
    company: str,
    sector: str,
    industry: str,
    historical_prices: list,
    ebt_hist: list,
    ebt_cagr: dict,
    ebt_avg: dict,
    ebt_ttm: dict,
    fcf_hist: list,
    fcf_cagr: dict,
    fcf_avg: dict,
    fcf_ttm: dict,
    ebt_fc_rows: list,
    fcf_fc_rows: list,
    checklist: list,
    final_rows: list,
    price_now,
    avg_target_ss,
    ebitda_price=None,
    fcf_price=None,
    irr_val=None,
    fair_value_now=None,
    buy_price_now=None,
    on_sale_now=None,
    irr_schedule_rows: list = None,
    irr_sensitivity: dict = None,
    description: str = "",
) -> bytes:
    """
    Generate an analyst-style A4 one-page PDF for the CF+IRR model.
    Returns the PDF as bytes (ready for st.download_button or HTTP response).
    """
    date_str   = datetime.date.today().strftime("%d %b %Y")
    irr_str    = f"{irr_val * 100:.1f}%" if irr_val is not None else "N/A"
    irr_pass   = (irr_val >= 0.12) if irr_val is not None else None

    # ── Build price chart ─────────────────────────────────────────────────────
    chart_png = _make_chart(historical_prices, ticker)

    # ── Initialise PDF ────────────────────────────────────────────────────────
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False, margin=10)
    pdf.add_page()
    pdf.set_margins(_LM, 0, _RM)

    # ── BANNER ────────────────────────────────────────────────────────────────
    _draw_banner(pdf, ticker, company, sector, industry, date_str)

    # ── METRIC BOXES (6 KPIs) ─────────────────────────────────────────────────
    sale_str = (
        "YES"  if on_sale_now is True  else
        "NO"   if on_sale_now is False else
        "N/A"
    )
    boxes = [
        ("Current Price",   _fp(price_now),      None),
        ("Avg Target",      _fp(avg_target_ss),  None),
        ("Fair Value",      _fp(fair_value_now), on_sale_now),
        ("Buy Price",       _fp(buy_price_now),  on_sale_now),
        ("IRR",             irr_str,              irr_pass),
        ("On Sale?",        sale_str,             on_sale_now),
    ]
    _draw_metric_boxes(pdf, boxes)

    # ── PRICE CHART ───────────────────────────────────────────────────────────
    _draw_chart(pdf, chart_png, h=22.0)

    # ─────────────────────────────────────────────────────────────────────────
    # HISTORICAL TABLES  (two columns)
    # ─────────────────────────────────────────────────────────────────────────
    y_hist = pdf.get_y()

    ebt_all   = ebt_hist + [ebt_cagr, ebt_avg, ebt_ttm]
    ebt_hdrs  = ["Year", "Rev ($MM)", "EBITDA ($MM)", "EV ($MM)", "EV/EBITDA", "ND/EBITDA"]
    ebt_cw    = _col_widths(_CL, [0.13, 0.17, 0.18, 0.17, 0.18, 0.17])
    ebt_rows  = [
        [
            r.get("Year", ""),
            r.get("Revenues ($MM)", ""),
            r.get("EBITDA ($MM)", ""),
            r.get("EV ($MM)", ""),
            r.get("EV/EBITDA", ""),
            r.get("Net Debt/EBITDA", ""),
        ]
        for r in ebt_all
    ]
    y_l1 = _draw_table(pdf, _LM, y_hist, _CL,
                        "2.1 -EV/EBITDA Historical",
                        ebt_hdrs, ebt_cw, ebt_rows)

    fcf_all   = fcf_hist + [fcf_cagr, fcf_avg, fcf_ttm]
    fcf_hdrs  = ["Year", "FCF ($MM)", "SBC ($MM)", "Adj.FCF/s", "Price", "FCF Yield"]
    fcf_cw    = _col_widths(_CR, [0.13, 0.17, 0.17, 0.17, 0.19, 0.17])
    fcf_rows  = [
        [
            r.get("Year", ""),
            r.get("FCF ($MM)", ""),
            r.get("SBC ($MM)", ""),
            r.get("Adj. FCF/s", ""),
            r.get("Stock Price", ""),
            r.get("Adj. FCF Yield", ""),
        ]
        for r in fcf_all
    ]
    y_r1 = _draw_table(pdf, _LM + _CL + _GAP, y_hist, _CR,
                        "3.1 -Adj. FCF/s Historical",
                        fcf_hdrs, fcf_cw, fcf_rows)

    pdf.set_y(max(y_l1, y_r1) + 1)

    # ─────────────────────────────────────────────────────────────────────────
    # FORECAST TABLES  (two columns)
    # ─────────────────────────────────────────────────────────────────────────
    y_fc = pdf.get_y()

    ebt_fc_avg = None
    if ebt_fc_rows:
        vals = [_s(r.get("Est. EBITDA ($MM)")) for r in ebt_fc_rows]
        vals = [v for v in vals if v is not None]
        ebt_fc_avg = sum(vals) / len(vals) if vals else None

    ebt_fc_display = [
        [r.get("Year", ""), _fgr(r.get("Est. Growth Rate (%)")),
         _fmmstr(r.get("Est. EBITDA ($MM)"))]
        for r in ebt_fc_rows
    ]
    if ebt_fc_avg is not None:
        ebt_fc_display.append(["Average", "-", _fmmstr(ebt_fc_avg)])

    efc_cw = _col_widths(_CL, [0.22, 0.33, 0.45])
    y_l2 = _draw_table(pdf, _LM, y_fc, _CL,
                        "2.2 -EBITDA Forecast",
                        ["Year", "Est. Growth %", "Est. EBITDA ($MM)"],
                        efc_cw, ebt_fc_display)

    fcf_fc_avg = None
    if fcf_fc_rows:
        vals = [_s(r.get("Est. Adj. FCF/s")) for r in fcf_fc_rows]
        vals = [v for v in vals if v is not None]
        fcf_fc_avg = sum(vals) / len(vals) if vals else None

    fcf_fc_display = [
        [r.get("Year", ""), _fgr(r.get("Est. Growth Rate (%)")),
         _fp(r.get("Est. Adj. FCF/s"))]
        for r in fcf_fc_rows
    ]
    if fcf_fc_avg is not None:
        fcf_fc_display.append(["Average", "-", _fp(fcf_fc_avg)])

    ffc_cw = _col_widths(_CR, [0.22, 0.33, 0.45])
    y_r2 = _draw_table(pdf, _LM + _CL + _GAP, y_fc, _CR,
                        "3.2 -Adj. FCF/s Forecast",
                        ["Year", "Est. Growth %", "Est. Adj. FCF/s"],
                        ffc_cw, fcf_fc_display)

    pdf.set_y(max(y_l2, y_r2) + 1)

    # ─────────────────────────────────────────────────────────────────────────
    # WEIGHTING TABLE (full width)
    # ─────────────────────────────────────────────────────────────────────────
    _draw_weighting_table(pdf, ebitda_price, fcf_price, avg_target_ss)
    pdf.ln(1)

    # ─────────────────────────────────────────────────────────────────────────
    # FINAL OUTPUT  +  QUALITY CHECKLIST  (two columns)
    # ─────────────────────────────────────────────────────────────────────────
    y_bot = pdf.get_y()

    y_l3 = _draw_final_output(pdf, _LM, y_bot, _CL, final_rows)
    y_r3 = _draw_checklist(pdf, _LM + _CL + _GAP, y_bot, _CR, checklist)

    pdf.set_y(max(y_l3, y_r3) + 1)

    # ─────────────────────────────────────────────────────────────────────────
    # IRR SCHEDULE (left)  +  IRR SENSITIVITY (right)  — side by side
    # ─────────────────────────────────────────────────────────────────────────
    y_irr = pdf.get_y()

    if irr_schedule_rows:
        y_after_sched = _draw_irr_schedule(
            pdf, _LM, y_irr, _CL, irr_schedule_rows, irr_val
        )
    else:
        y_after_sched = y_irr

    if irr_sensitivity:
        y_after_sens = _draw_irr_sensitivity(
            pdf, _LM + _CL + _GAP, y_irr, _CR, irr_sensitivity, price_now
        )
    else:
        y_after_sens = y_irr

    pdf.set_y(max(y_after_sched, y_after_sens) + 1)

    # ── COMPANY DESCRIPTION ───────────────────────────────────────────────────
    if description:
        _draw_description(pdf, description, company)

    # ── Return bytes ──────────────────────────────────────────────────────────
    return bytes(pdf.output())
