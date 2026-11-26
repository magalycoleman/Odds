"""Extract the commercial invoice PDF from a TBI invoice zip and parse it.

Usage: python3 -I parse_invoice.py <zip> <outdir>
Prints JSON: invoice, date, container, boxes, total, pdf path, lines[].
"""
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

zpath, outdir = Path(sys.argv[1]), Path(sys.argv[2])
outdir.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zpath) as z:
    names = [n for n in z.namelist() if re.search(r"INVOICE\s+[A-Z]+\d+-\d+\.pdf$", n, re.I)]
    if not names:
        names = [n for n in z.namelist() if n.lower().endswith(".pdf") and "invoice" in n.lower()]
    src = names[0]
    data = z.read(src)
inv_no = re.search(r"([A-Z]{2,4}\d{2}-\d{3})", src).group(1)
pdf = outdir / f"{inv_no}.pdf"
pdf.write_bytes(data)
text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout

def grab(pat):
    m = re.search(pat, text)
    return m.group(1).strip() if m else None

date = grab(r"Invoice Date:\s+(\S+)")
container = grab(r"Container:\s+([A-Z]{3,4}\s?\d{6}\s?\d)")
if container:
    c = container.replace(" ", "")
    k = len(c) - 7
    container = f"{c[:k]} {c[k:k+6]} {c[k+6:]}"
boxes = grab(r"Total Boxes:\s+(\d+)")
total = grab(r"Total Invoice Amount\s+\$([\d,]+\.\d+)")
lines = []
row = re.compile(
    r"^\s*\d+\s+(\d{6})\s+(\S+)\s+(\S+)\s+(.+?)\s{2,}(REG|B&T|BIG|TALL|\S+)\s{2,}.*?\s(\d{4}\.\d{2}\.\d{4})\s+([\d,]+)\s+\$\s*([\d.]+)\s+\$\s*([\d,]+\.\d+)",
    re.M,
)
for m in row.finditer(text):
    lines.append({
        "po": m.group(1), "cust_po": m.group(2), "style": m.group(3),
        "color": m.group(4).strip(), "size": m.group(5),
        "qty": int(m.group(7).replace(",", "")), "price": float(m.group(8)),
        "amount": float(m.group(9).replace(",", "")),
    })
mm, dd, yy = (date or "//").split("/")
if len(yy) == 2:
    yy = "20" + yy
out = {
    "invoice": inv_no, "date": f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}" if date else None,
    "container": container, "boxes": int(boxes) if boxes else None,
    "total": float(total.replace(",", "")) if total else None,
    "pdf": str(pdf), "lines": lines,
    "sum_check": round(sum(l["amount"] for l in lines), 2),
}
print(json.dumps(out, indent=1))
