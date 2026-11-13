"""Fabric Payment Schedule weekly report: PDF (looks like the dashboard) + Excel (all payments).

Input: a JSON file with the Airtable records from the Buy Plan base, Fabric Buy table
(list_records_for_table, same field IDs the dashboard reads). Accepts either
{"records": [...]} or a list of such pages.
Usage: python3 fabric_payment_report.py records.json OUT_DIR [YYYY-MM-DD today]
Lines with no due date and no amount (old-season placeholders) are left out.
Needs: pip install reportlab openpyxl
"""
import json, sys, os, datetime as dt
from collections import defaultdict

from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

F = {
    "style": "fldCGBNITK2oeZqo2", "mill": "fldENQ6JhyPDzqFW9", "terms": "fld4qJgLGdARtkqNt",
    "termDays": "fld1JAo7TlKqvbKMm", "shipDate": "fldmwSA8zWqXB2eTv", "dueDate": "fldTQYKTjQlpwmhyb",
    "estimate": "fldj07pMlnOj5RNDB", "amount": "fldmINagLDWBPMOo9", "minAmount": "fldKkKHMyHXk8HnSZ",
    "maxAmount": "fldH60nok6SdCIGoo", "actualXmill": "fld18n9HfBxBYETo1", "intent": "fldBPVIsrT7bEJVUr",
}

# Dashboard look (neutral theme): warm gray page, white cards, amber accent, dashboard series colors
SERIES = ["#D97757", "#6A9BCC", "#788C5D", "#B49A5E", "#9C7FB8", "#C46686", "#5E9C98", "#B0AEA5", "#8A7560", "#4E6E8E"]
BG, PANEL, LINE, MUTED, INK = "#F5F4EE", "#FFFFFF", "#E5E3DA", "#73726C", "#1F1E1D"
GOLD = "#D4A017"      # warn/amber accent on "Due in the next 30 days"
PLUM = INK            # titles in dark text, like the dashboard

# PDF uses the standard Helvetica (not embedded) so the file stays small enough to email as an attachment
BODY_R, BODY_B = "Helvetica", "Helvetica-Bold"


def lk(v):
    if v is None: return None
    if not isinstance(v, (dict, list)): return v
    if isinstance(v, dict) and "valuesByLinkedRecordId" in v:
        vals = [x for arr in v["valuesByLinkedRecordId"].values() for x in (arr if isinstance(arr, list) else [arr])]
    elif isinstance(v, list): vals = v
    else: vals = [v]
    if not vals: return None
    x = vals[0]
    return x.get("name") if isinstance(x, dict) else x


def num(v):
    if v in (None, ""): return None
    try: return float(v)
    except (TypeError, ValueError): return None


def d(s):
    return dt.date.fromisoformat(s[:10]) if s else None


def ln(n):
    return "{} line{}".format(n, "" if n == 1 else "s")


def money(v, cents=False):
    return ("${:,.2f}" if cents else "${:,.0f}").format(v)


def friendly(x):
    return x.strftime("%B %-d, %Y") if x else "—"


def load(path):
    raw = json.load(open(path))
    pages = raw if isinstance(raw, list) else [raw]
    recs = []
    for p in pages:
        if isinstance(p, dict) and "records" in p: recs += p["records"]
        elif isinstance(p, dict) and "id" in p: recs.append(p)
    rows = []
    for r in recs:
        c = r.get("cellValuesByFieldId") or r.get("fields") or {}
        g = lambda k: c.get(F[k], c.get(k))
        rows.append({
            "id": r["id"], "style": g("style"), "mill": lk(g("mill")), "terms": lk(g("terms")),
            "intent": lk(g("intent")), "shipDate": d(g("shipDate")), "actualXmill": g("actualXmill"),
            "dueDate": d(g("dueDate")), "amount": num(g("amount")),
            "minAmount": num(g("minAmount")), "maxAmount": num(g("maxAmount")),
        })
    return rows


def compute(rows, today):
    for p in rows:
        days = (p["dueDate"] - today).days if p["dueDate"] else None
        p["daysToDue"] = days
        if p["amount"] is None: s = "Amount pending"
        elif days is None: s = "No due date"
        elif days < 0: s = "Due date passed"
        elif days <= 30: s = "Due in 30 days"
        elif days <= 60: s = "Due in 31–60 days"
        else: s = "Later"
        p["status"] = s
    t = dict(scheduled=0, min=0, max=0, lines=0, pending=0, passed=0, passedLines=0, next30=0, next30Lines=0,
             next60=0, next60Lines=0, later=0, laterLines=0)
    on_actual = 0
    for p in rows:
        t["lines"] += 1
        if p["amount"] is None: t["pending"] += 1; continue
        a = p["amount"]
        t["scheduled"] += a
        t["min"] += p["minAmount"] if p["minAmount"] is not None else a
        t["max"] += p["maxAmount"] if p["maxAmount"] is not None else a
        if p["actualXmill"]: on_actual += a
        key = {"Due date passed": "passed", "Due in 30 days": "next30", "Due in 31–60 days": "next60", "Later": "later"}.get(p["status"])
        if key: t[key] += a; t[key + "Lines"] += 1
    t["actualShare"] = on_actual / t["scheduled"] if t["scheduled"] else 0

    by_mill = {}
    for p in rows:
        k = p["mill"] or "No mill"
        m = by_mill.setdefault(k, dict(mill=k, amount=0, lines=0, pending=0, terms=[]))
        m["lines"] += 1
        if p["terms"] and p["terms"] not in m["terms"]: m["terms"].append(p["terms"])
        if p["amount"] is None: m["pending"] += 1
        else: m["amount"] += p["amount"]
    by_mill = sorted(by_mill.values(), key=lambda m: -m["amount"])

    by_month = defaultdict(float)
    for p in rows:
        if p["amount"] is None or not p["dueDate"]: continue
        by_month[(p["dueDate"].strftime("%Y-%m"), p["mill"] or "No mill")] += p["amount"]

    upcoming = sorted([p for p in rows if p["amount"] is not None and p["daysToDue"] is not None and p["daysToDue"] >= 0],
                      key=lambda p: (p["dueDate"], -p["amount"]))[:5]
    return t, by_mill, by_month, upcoming


def short(v):
    if v >= 1e6: return "${:.2f}M".format(v / 1e6).replace(".00M", "M")
    if v >= 1e3: return "${:.0f}K".format(v / 1e3)
    return "${:.0f}".format(v)


def draw_chart(c, x, y, w, h, by_month, by_mill, colors, today):
    months = sorted({m for m, _ in by_month})
    mills = [m["mill"] for m in by_mill if any(k[1] == m["mill"] for k in by_month)]
    if not months: return
    # legend
    lx = x; ly = y + h - 15
    c.setFont(BODY_R, 8)
    for mill in mills:
        c.setFillColor(HexColor(colors[mill])); c.roundRect(lx, ly - 1, 7, 7, 1.5, stroke=0, fill=1)
        c.setFillColor(HexColor(MUTED)); c.drawString(lx + 10, ly, mill)
        lx += 18 + pdfmetrics.stringWidth(mill, BODY_R, 8)
    totals = [sum(by_month.get((mo, m), 0) for m in mills) for mo in months]
    top = max(totals) * 1.15 or 1
    step = 10 ** len(str(int(top / 5))) / 10
    for nice in (1, 2, 2.5, 5, 10):
        if top / (step * nice) <= 6: step *= nice; break
    left = 34; bottom = 24; ph = h - 30 - bottom; pw = w - left
    c.setFont(BODY_R, 7.5)
    v = 0
    while v <= top:
        yy = y + bottom + ph * v / top
        c.setStrokeColor(HexColor(LINE)); c.setLineWidth(0.5); c.line(x + left, yy, x + w, yy)
        c.setFillColor(HexColor(MUTED)); c.drawRightString(x + left - 5, yy - 2.5, short(v))
        v += step
    c.setStrokeColor(HexColor("#BFBDB4")); c.line(x + left, y + bottom, x + w, y + bottom)
    band = pw / len(months); bw = band * 0.62
    this = today.strftime("%Y-%m")
    for i, mo in enumerate(months):
        bx = x + left + i * band + (band - bw) / 2; base = 0
        for mill in mills:
            val = by_month.get((mo, mill), 0)
            if val <= 0: continue
            c.setFillColor(HexColor(colors[mill]))
            c.rect(bx, y + bottom + ph * base / top, bw, ph * val / top, stroke=0, fill=1)
            base += val
        c.setFillColor(HexColor(INK)); c.setFont(BODY_R, 7.5)
        c.drawCentredString(bx + bw / 2, y + bottom + ph * base / top + 3, short(base))
        d0 = dt.date.fromisoformat(mo + "-01")
        c.setFont(BODY_B if mo == this else BODY_R, 8)
        c.setFillColor(HexColor(INK if mo == this else MUTED))
        c.drawCentredString(bx + bw / 2, y + bottom - 11, d0.strftime("%b"))
        if i == 0 or d0.month == 1:
            c.setFont(BODY_R, 7); c.setFillColor(HexColor(MUTED)); c.drawCentredString(bx + bw / 2, y + bottom - 20, d0.strftime("%Y"))


def build_pdf(path, today, t, by_mill, by_month, upcoming, colors, chart_png):
    W, H = landscape(letter)
    c = canvas.Canvas(path, pagesize=(W, H))
    c.setTitle("Fabric Payment Schedule - " + friendly(today))
    c.setFillColor(HexColor(BG)); c.rect(0, 0, W, H, stroke=0, fill=1)
    M = 28
    # Header
    c.setFillColor(HexColor(PLUM)); c.setFont(BODY_B, 20); c.drawString(M, H - M - 14, "Fabric payment schedule")
    c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 10)
    c.drawRightString(W - M, H - M - 10, "Protexsa · Report of " + friendly(today))
    c.setFont(BODY_R, 10.5); c.setFillColor(HexColor(INK))
    c.drawString(M, H - M - 32, "{} falls due in the next 30 days across {} payment {}. The full schedule is {}.".format(
        money(t["next30"]), t["next30Lines"], "line" if t["next30Lines"] == 1 else "lines", money(t["scheduled"])))

    def card(x, y, w, h, accent=False):
        c.setFillColor(HexColor(PANEL)); c.setStrokeColor(HexColor(LINE)); c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
        if accent:
            c.setFillColor(HexColor(GOLD)); c.roundRect(x, y, 4, h, 2, stroke=0, fill=1)

    # Six boxes
    tiles = [
        ("All scheduled payments", money(t["scheduled"]), ln(t["lines"]) + " · {} without amount yet".format(t["pending"]), False, 18),
        ("Due in the next 30 days", money(t["next30"]), ln(t["next30Lines"]), True, 18),
        ("Due in 31 to 60 days", money(t["next60"]), ln(t["next60Lines"]), False, 18),
        ("Due later", money(t["later"]), ln(t["laterLines"]), False, 18),
        ("Due date already passed", money(t["passed"]), ln(t["passedLines"]) + " · check against what was paid", False, 18),
        ("If mills ship 3% under / over", money(t["min"]) + " – " + money(t["max"]), "{:.0%} of the money is on actual ex-mill dates".format(t["actualShare"]), False, 13),
    ]
    gap = 8; tw = (W - 2 * M - 5 * gap) / 6; th = 70; ty = H - M - 50 - th
    for i, (lbl, val, sub, acc, fs) in enumerate(tiles):
        x = M + i * (tw + gap)
        card(x, ty, tw, th, acc)
        lf = 8.5
        while pdfmetrics.stringWidth(lbl, BODY_R, lf) > tw - 16 and lf > 6: lf -= 0.25
        c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, lf); c.drawString(x + 10, ty + th - 15, lbl)
        while pdfmetrics.stringWidth(val, BODY_B, fs) > tw - 18 and fs > 8: fs -= 0.5
        c.setFillColor(HexColor(INK)); c.setFont(BODY_B, fs); c.drawString(x + 10, ty + th - 36, val)
        c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 7.5)
        words, lines, cur = sub.split(" "), [], ""
        for w_ in words:
            trial = (cur + " " + w_).strip()
            if pdfmetrics.stringWidth(trial, BODY_R, 7.5) > tw - 18 and cur: lines.append(cur); cur = w_
            else: cur = trial
        lines.append(cur)
        for j, txt in enumerate(lines[:2]):
            c.drawString(x + 10, ty + 18 - j * 9, txt)

    # Cash out by month
    ch_h = 192; cy = ty - gap - ch_h
    card(M, cy, W - 2 * M, ch_h)
    c.setFillColor(HexColor(PLUM)); c.setFont(BODY_B, 12); c.drawString(M + 12, cy + ch_h - 18, "Cash out by month")
    c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 8.5)
    c.drawString(M + 12, cy + ch_h - 30, "Every payment, by the month it falls due, split by mill.")
    draw_chart(c, M + 12, cy + 8, W - 2 * M - 24, ch_h - 40, by_month, by_mill, colors, today)

    # By mill + Next 5
    bh = cy - gap - M; by = M; bw = (W - 2 * M - gap) / 2
    card(M, by, bw, bh)
    c.setFillColor(HexColor(PLUM)); c.setFont(BODY_B, 12); c.drawString(M + 12, by + bh - 18, "By mill")
    c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 8.5); c.drawString(M + 12, by + bh - 30, "Total scheduled per mill and its payment terms.")
    mx = max([m["amount"] for m in by_mill] or [1]) or 1
    rows_fit = max(1, int((bh - 40) // 34))
    yy = by + bh - 48
    for m in by_mill[:rows_fit]:
        col = HexColor(colors.get(m["mill"], "#999999"))
        c.setFillColor(col); c.roundRect(M + 12, yy + 1, 7, 7, 1.5, stroke=0, fill=1)
        c.setFillColor(HexColor(INK)); c.setFont(BODY_R, 9.5); c.drawString(M + 24, yy, m["mill"])
        c.drawRightString(M + bw - 12, yy, money(m["amount"]))
        c.setFillColor(HexColor("#ECEAE3")); c.roundRect(M + 12, yy - 9, bw - 24, 5, 2.5, stroke=0, fill=1)
        c.setFillColor(col); c.roundRect(M + 12, yy - 9, max(3, (bw - 24) * m["amount"] / mx), 5, 2.5, stroke=0, fill=1)
        meta = ln(m["lines"]) + (" · {} without amount".format(m["pending"]) if m["pending"] else "") + (" · " + " / ".join(m["terms"]) if m["terms"] else "")
        c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 7.5)
        while pdfmetrics.stringWidth(meta, BODY_R, 7.5) > bw - 24 and len(meta) > 4: meta = meta[:-2]
        c.drawString(M + 12, yy - 19, meta)
        yy -= 34
    if len(by_mill) > rows_fit:
        c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 7.5)
        c.drawString(M + 12, by + 6, "+ {} more mills in the Excel file".format(len(by_mill) - rows_fit))

    nx = M + bw + gap
    card(nx, by, bw, bh)
    c.setFillColor(HexColor(PLUM)); c.setFont(BODY_B, 12); c.drawString(nx + 12, by + bh - 18, "Next 5 payments")
    c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 8.5); c.drawString(nx + 12, by + bh - 30, "The soonest payments from today with an amount.")
    yy = by + bh - 48
    if not upcoming:
        c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 9.5); c.drawString(nx + 12, yy, "No upcoming payments with an amount.")
    for p in upcoming:
        c.setFillColor(HexColor(colors.get(p["mill"] or "No mill", "#999999"))); c.roundRect(nx + 12, yy + 1, 7, 7, 1.5, stroke=0, fill=1)
        c.setFillColor(HexColor(INK)); c.setFont(BODY_R, 9.5); c.drawString(nx + 24, yy, p["style"] or "—")
        c.drawRightString(nx + bw - 12, yy, money(p["amount"], True))
        c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 7.5)
        dd = p["daysToDue"]
        c.drawString(nx + 12, yy - 11, "{} · in {} day{} · {}".format(friendly(p["dueDate"]), dd, "" if dd == 1 else "s", p["mill"] or ""))
        yy -= 26
    c.setFillColor(HexColor(MUTED)); c.setFont(BODY_R, 7)
    c.drawString(M, 12, "Amounts in US dollars (Updated Total Amount). Full list of payments in the attached Excel file.")
    c.showPage(); c.save()


def build_xlsx(path, today, rows, t):
    wb = Workbook(); ws = wb.active; ws.title = "Fabric payments"
    hdr = ["Style | Color", "Mill", "Intent", "Payment terms", "Ship date", "Ship date basis", "Due date",
           "Amount (Updated Total)", "Amount -3%", "Amount +3%", "Status"]
    ws.append(hdr)
    hf = Font(name="Aptos Display", bold=True); fill = PatternFill("solid", fgColor="EDEDED")
    for cell in ws[1]: cell.font = hf; cell.fill = fill; cell.alignment = Alignment(vertical="center")
    order = sorted(rows, key=lambda p: (p["dueDate"] or dt.date.max, p["style"] or ""))
    body = Font(name="Aptos Display")
    for p in order:
        ws.append([p["style"], p["mill"], p["intent"], p["terms"], p["shipDate"],
                   ("Actual ex-mill" if p["actualXmill"] else "Planned") if p["shipDate"] else None,
                   p["dueDate"], p["amount"] if p["amount"] is not None else "Pending",
                   p["minAmount"], p["maxAmount"], p["status"]])
    last = ws.max_row
    for r in ws.iter_rows(min_row=2, max_row=last):
        for cell in r: cell.font = body
        for i in (4, 6): r[i].number_format = "mmmm d, yyyy"; r[i].alignment = Alignment(horizontal="left")
        for i in (7, 8, 9): r[i].number_format = '"$"#,##0.00'
    tr = last + 1
    ws.cell(tr, 7, "Total").font = Font(name="Aptos Display", bold=True)
    for col in (8, 9, 10):
        L = get_column_letter(col)
        cc = ws.cell(tr, col, "=SUM({0}2:{0}{1})".format(L, last))
        cc.font = Font(name="Aptos Display", bold=True); cc.number_format = '"$"#,##0.00'
    for i, w in enumerate([30, 26, 15, 30, 20, 16, 20, 20, 16, 16, 20], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"; ws.auto_filter.ref = "A1:K{}".format(last)
    ws2 = wb.create_sheet("Summary")
    ws2.append(["Fabric Payment Schedule", "Report of " + friendly(today)])
    ws2["A1"].font = Font(name="Aptos Display", bold=True, size=14, color=PLUM[1:])
    ws2.append([])
    for lbl, v in [("All scheduled payments", t["scheduled"]), ("Due in the next 30 days", t["next30"]),
                   ("Due in 31 to 60 days", t["next60"]), ("Due later", t["later"]),
                   ("Due date already passed", t["passed"]), ("If mills ship 3% under", t["min"]),
                   ("If mills ship 3% over", t["max"])]:
        ws2.append([lbl, v]); ws2.cell(ws2.max_row, 2).number_format = '"$"#,##0.00'
    ws2.append(["Lines without amount yet", t["pending"]])
    for r in ws2.iter_rows(min_row=3):
        for cell in r: cell.font = Font(name="Aptos Display")
    ws2.column_dimensions["A"].width = 30; ws2.column_dimensions["B"].width = 22
    wb.save(path)


def main():
    src, out = sys.argv[1], sys.argv[2]
    today = dt.date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else dt.date.today()
    os.makedirs(out, exist_ok=True)
    rows = [p for p in load(src) if not (p["dueDate"] is None and not p["amount"])]
    t, by_mill, by_month, upcoming = compute(rows, today)
    colors = {m["mill"]: SERIES[i % len(SERIES)] for i, m in enumerate(by_mill)}
    stamp = today.strftime("%B %-d, %Y")
    pdf = os.path.join(out, "Fabric Payment Schedule - {}.pdf".format(stamp))
    xl = os.path.join(out, "Fabric Payment Schedule - {}.xlsx".format(stamp))
    build_pdf(pdf, today, t, by_mill, by_month, upcoming, colors, None)
    build_xlsx(xl, today, rows, t)
    print(json.dumps({"pdf": pdf, "xlsx": xl, "lines": t["lines"], "scheduled": round(t["scheduled"], 2),
                      "next30": round(t["next30"], 2), "pending": t["pending"]}))


if __name__ == "__main__":
    main()
