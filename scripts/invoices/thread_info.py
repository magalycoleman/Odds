"""Read saved Gmail get_message outputs; list invoice zips (with attachment index) and
the dates of Damary's DUCA / shipping documents messages.
Usage: python3 -I thread_info.py <file> [<file> ...]
"""
import json
import re
import sys

MONTHS = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
          "ago": 8, "sept": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


def load(path):
    raw = open(path, encoding="utf-8").read()
    try:
        d = json.loads(raw)
        if isinstance(d, list):
            d = json.loads(d[0]["text"])
        return d
    except Exception:
        i = raw.find("{")
        return json.loads(raw[i:])


out = []
for p in sys.argv[1:]:
    m = load(p)
    body = m.get("plaintextBody", "")
    zips = [(i, a["filename"]) for i, a in enumerate(m.get("attachments", []))
            if re.search(r"INVOICE\s+[A-Z]+\d+-\d+\.zip", a.get("filename", ""), re.I)]
    events = []
    for mm in re.finditer(r"De: ([^\n<]+)<([^>]+)>\nDate: \w+, (\d{1,2}) (\w+)\.? (\d{4})", body):
        sender = mm.group(2)
        nxt = body.find("\nDe: ", mm.end())
        chunk = body[mm.end(): nxt if nxt > 0 else len(body)]
        # strip header lines (To/Cc) up to first blank line
        txt = chunk.split("\n\n", 1)[-1][:600]
        kind = []
        if re.search(r"\bDUCA\b", txt):
            kind.append("DUCA")
        if re.search(r"shipping documents|documentos de embarque", txt, re.I):
            kind.append("DOCS")
        if kind and "jefe.import.export" in sender:
            mon = MONTHS.get(mm.group(4).lower().rstrip("."), 0)
            events.append((f"{mm.group(5)}-{mon:02d}-{int(mm.group(3)):02d}", "+".join(kind)))
    out.append({"id": m.get("id"), "subject": m.get("subject", "")[:120], "zips": zips, "events": events})
print(json.dumps(out, indent=1))
