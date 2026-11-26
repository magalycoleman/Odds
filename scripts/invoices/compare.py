"""Match parsed invoices to WIP lines and build the Airtable updates.
Usage: python3 -I compare.py <wip.json> <invoice json dir> <exported dates json> <out.json>
"""
import glob
import json
import re
import sys
from collections import defaultdict

wip_path, inv_dir, exp_path, out_path = sys.argv[1:5]
wip = json.load(open(wip_path))["records"]
exported = json.load(open(exp_path))  # invoice -> YYYY-MM-DD
F = dict(combo="fldz0P5nWX5FkN8so", po="fldaW3eA1EiCnWzwq", style="fldOmgxSUkAvWsSjl",
         color="fldS2kAkKZtZwOLfy", qty="fldTh1u7viIjuIP2M", cut="fldtBonLC7PnNXVNS",
         fobr="fldPUttvlYPMKti55", fobb="fldw6mw2k1SnoHR6P", notes="fldrDSQqjNJaKlan8",
         efl="fldQFYyEfiQLxhvFm", exp="flduTPPgffd883YgF", of="fld1yOntZ6nlM6Dv8",
         ovr="fldVD3B7O5a89y7tL")


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def val(r, k):
    v = r["cellValuesByFieldId"].get(F[k])
    if isinstance(v, dict):
        v = v.get("name")
    return v


index = defaultdict(list)
for r in wip:
    index[(val(r, "po"), val(r, "style"), norm(val(r, "color")))].append(r)

TODAY = "November 26, 2026"
invoices, updates, unmatched, report = [], [], [], []
for f in sorted(glob.glob(f"{inv_dir}/*.json")):
    d = json.load(open(f))
    groups = defaultdict(lambda: {"qty": 0, "reg": None, "bt": None, "parts": []})
    for l in d["lines"]:
        g = groups[(l["po"], l["style"], norm(l["color"]))]
        g["qty"] += l["qty"]
        g["parts"].append(f'{l["qty"]} {"Reg" if l["size"] == "REG" else "B&T"}')
        if l["size"] == "REG":
            g["reg"] = l["price"]
        else:
            g["bt"] = l["price"]
        g["color"] = l["color"]
    rec_ids, inv_issues = [], []
    stated, lines_sum = d["total"], d["sum_check"]
    if stated is not None and abs(stated - lines_sum) > 0.01:
        inv_issues.append(f"Invoice total ${stated:,.2f} does not match its lines (${lines_sum:,.2f}, difference ${lines_sum - stated:,.2f}).")
    for (po, style, colk), g in groups.items():
        recs = index.get((po, style, colk), [])
        if not recs:
            unmatched.append(f'{d["invoice"]}: PO {po} {style} {g["color"]} ({g["qty"]} units) not found among uninvoiced shipped WIP lines')
            continue
        r = recs[0]
        rec_ids.append(r["id"])
        qty, cut = val(r, "qty"), val(r, "cut")
        fobr, fobb = val(r, "fobr"), val(r, "fobb")
        inv = g["qty"]
        mistakes = []
        if qty:
            diff = inv - qty
            pct = diff / qty * 100
            if diff:
                word = "Short" if diff < 0 else "Over"
                mistakes.append(f"{word}: invoiced {inv:,}, ordered {qty:,} ({abs(diff):,} {'short' if diff < 0 else 'over'}, {abs(pct):.1f}%).")
        if cut is not None and inv != cut:
            mistakes.append(f"Invoiced {abs(inv - cut):,} {'more' if inv > cut else 'fewer'} than cut ({cut:,}): check sister POs on OF {val(r, 'of') or '?'}.")
        for lab, ip, wp in (("Reg", g["reg"], fobr), ("B&T", g["bt"], fobb)):
            if ip is None or wp is None or abs(ip - wp) < 0.005:
                continue
            if wp > ip:
                mistakes.append(f"Price: {lab} invoiced at ${ip:.2f}; TBI's WIP FOB is ${wp:.2f} (higher). Leave it, no action.")
            else:
                mistakes.append(f"Price: {lab} invoiced at ${ip:.2f}, higher than TBI's WIP FOB ${wp:.2f}.")
        fields = {"fld5bwhWhVHaMOzoQ": inv}
        if d["invoice"] in exported:
            fields[F["exp"]] = exported[d["invoice"]]
        if mistakes:
            fields["fldQLF4X6fuodEGHJ"] = "\n".join(mistakes)
            old = val(r, "notes") or ""
            line = (f'{TODAY} (Invoice check): invoice {d["invoice"]} ships {inv:,} '
                    f'({" + ".join(g["parts"])}) against PO Qty {qty:,}; Qty Cut {cut if cut is not None else "blank"}. '
                    + " ".join(mistakes))
            fields[F["notes"]] = (line.strip() + ("\n" + old if old else ""))
            report.append({"invoice": d["invoice"], "combo": val(r, "combo"), "mistakes": mistakes,
                           "overage_report": bool(val(r, "ovr"))})
        updates.append({"id": r["id"], "fields": fields})
    invoices.append({"invoice": d["invoice"], "date": d["date"], "container": d["container"],
                     "boxes": d["boxes"], "total": d["total"], "lines_sum": lines_sum,
                     "pdf": d["pdf"], "records": rec_ids, "issues": inv_issues,
                     "efl": None})
json.dump({"invoices": invoices, "updates": updates, "unmatched": unmatched, "report": report},
          open(out_path, "w"), indent=1)
print(f"{len(invoices)} invoices, {len(updates)} WIP lines matched, {len(unmatched)} unmatched, {len(report)} lines with mistakes")
for u in unmatched:
    print("UNMATCHED", u)
for i in invoices:
    if i["issues"]:
        print("ISSUE", i["invoice"], i["issues"])
