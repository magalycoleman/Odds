"""Final garment measurement sheet (Medidas de Prenda Terminada) - one PDF page per sample.
Usage: python3 build_fg.py samples.json pdfdir outdir
Specs come from the TBI PLM Points of Measure PDFs attached to Matrix > Block (Specs - Regular / Tall),
parsed by pom.py. One column per size the sample runs: Spec + blank box to write the measurement.
"""
import json, os, re, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white

F = '/usr/share/fonts/truetype/crosextra'
pdfmetrics.registerFont(TTFont('AD', f'{F}/Carlito-Regular.ttf'))
pdfmetrics.registerFont(TTFont('ADB', f'{F}/Carlito-Bold.ttf'))
NAVY = HexColor('#1F2A44'); AMBER = HexColor('#F2B33D'); INK = HexColor('#1E2430')
MUTED = HexColor('#6B7385'); RULE = HexColor('#D9DDE5'); ZEBRA = HexColor('#F6F7FA')
CHIP = HexColor('#E7ECF5'); SOFT = HexColor('#FDF3DF')

SRC, PDFDIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)

# block name (as in the key string) -> spec files (Regular first, then Tall)
BLOCK_FILES = {
    'Zack': ['Zack_R'], 'Thorne': ['Thorne_R', 'Thorne_T'], 'Clarke SS': ['ClarkeSS_R', 'ClarkeSS_T'],
    'Ed Camp': ['EdCamp_R'], 'Tim': ['Tim_R', 'Tim_T'], 'Stephen': ['Stephen_R', 'Stephen_T'],
    'Warren/Traditional': ['Warren_R'], 'David': ['David_R'], 'Mateo': ['Mateo_R'],
    'Barry': ['Barry_R'], 'Brianna': ['Brianna_R'],
}
# her row names and order (block-measurement-specs skill)
ORDER = [
    ('ASH-01', 'Across Shoulder Natural'), ('ABK-26', 'Across Back at Yoke Seam'),
    ('NEK-35', 'Front Neck Drop from HPS'), ('NEK-31', 'Back Neck Drop from HPS'),
    ('ACH-04', 'Chest'), ('ACH-02', 'Chest'), ('WST-18', 'Waist'), ('WST-16', 'Waist'),
    ('BTM-34', 'Sweep'), ('BTM-33', 'Sweep'), ('AHO-06', 'AH'), ('SLV-01', 'Sleeve Upper Arm (Half)'),
    ('SLV-30', 'Sleeve Elbow Circumference'), ('SLV-37', 'Sleeve Length S/S'),
    ('SLV-35', 'Sleeve Length from CB'), ('SLV-62', 'Sleeve Length from CB'),
    ('SLV-15', 'Sleeve Opening S/S'), ('SLV-41', 'Sleeve Opening L/S'), ('SLV-47', 'Cuff Length'),
    ('SLV-07', 'Sleeve Placket Length'), ('SLV-08', 'Sleeve Placket Width'),
    ('BDL-16', 'Back Length from CB'), ('BDL-17', 'Back Length from CB'),
    ('BDL-03', 'Front Body Length - CF'), ('BDL-28', 'Front Body Length from HPS'),
    ('BDL-04', 'Body Length - Side Seam'),
    ('PKT-19', 'Front Pocket Vertical from HPS'), ('PPKT-36', 'Front Pocket Vertical from HPS'),
    ('PKT-125', 'Front Pocket Vertical from HPS'),
    ('PKT-13', 'Pocket Position Horizontal at CF'), ('PKT-37', 'Front Pocket Horizontal Placket Edge'),
    ('BTN-10', 'Button Spacing Neck Band'), ('BTN-05', 'Button Spacing Neck Band'),
    ('BTN-08', 'Button Spacing Vertical'), ('BTN-26', 'Button Spacing Vertical'),
    ('BTN-04', 'Last Button Position from Bottom Hem'),
    ('CLR-141', 'Collar Height at CB'), ('CLR-04', 'Collar Point'), ('CLR-05', 'Lapel Point'),
    ('NEK-16', 'Neck Opening With Button'),
]
RANK = {c: i for i, (c, _) in enumerate(ORDER)}
NAME = dict(ORDER)

def frac2num(s):
    if not s: return None
    v = 0.0; neg = s.strip().startswith('-')
    for t in s.replace('-', ' ').split():
        if '/' in t: n, d = t.split('/'); v += int(n) / int(d)
        else: v += float(t)
    return -v if neg else v

def sleeve_set(label):
    """numbers in a sleeve row label: 'FROM CB 34/35' -> {34,35}; 'EXACT 34' -> {34}"""
    m = re.findall(r'(\d{2})(?:/(\d{2}))?', label.split('CB')[-1] if 'CB' in label else label)
    out = set()
    for a, b in m:
        out.add(int(a))
        if b: out.add(int(b))
    return {x for x in out if 30 <= x <= 40}

def parse_size(tok):
    """'155 345' -> dict(label='15 1/2 34/35', neck='15 1/2', sleeves={34,35}); 'M' / '2XLT' -> sport"""
    tok = tok.strip()
    m = re.match(r'^(\d{2})(5)?\s+(\d)(\d)(\d)$', tok)
    if m:
        neck = m.group(1) + (' 1/2' if m.group(2) else '')
        a = int(m.group(3) + m.group(4)); b = int(m.group(3) + m.group(5))
        return dict(label=f'{neck} {a}/{b}', key=neck, sleeves={a, b}, dress=True)
    return dict(label=tok, key=tok, sleeves=set(), dress=False)

def group_of(sz):
    if sz['dress']:
        if max(sz['sleeves']) >= 36: return 'TALL'
        if frac2num(sz['key']) >= 18: return 'BIG'
        return 'REGULAR'
    k = sz['key']
    if k.endswith('LT') or k in ('MT', 'LT'): return 'TALL'
    if re.match(r'^\dX$', k): return 'BIG'
    return 'REGULAR'

def pages_for(block):
    pages = []
    for f in BLOCK_FILES.get(block, []):
        for p in json.load(open(os.path.join(PDFDIR, f + '.json'))):
            n = p['name'].upper()
            g = 'TALL' if 'TALL' in n else 'BIG' if 'BIG' in n else 'REGULAR'
            pages.append(dict(p, group=g, file=f))
    return pages

def pick_page(pages, sz):
    g = group_of(sz)
    for p in pages:
        if p['group'] == g and sz['key'] in p['sizes']: return p
    return None

def tol_txt(r):
    a, b = r['cells'].get('TOL-'), r['cells'].get('TOL+')
    if a is None and b is None: return ''
    if a in (None, '0') and b in (None, '0'): return '0'
    a = a or ''; b = b or ''
    return f"{a} / +{b.lstrip('+')}" if b else a

def build_rows(block, sizes, notes):
    pages = pages_for(block)
    colpage = [pick_page(pages, s) for s in sizes]
    rows = {}   # key -> dict(name, code, rank, tol, spec per col)
    for ci, (sz, p) in enumerate(zip(sizes, colpage)):
        if p is None:
            notes.append(f"Size {sz['label']}: no {group_of(sz).title()} spec page for {block}")
            continue
        for r in p['rows']:
            code = r['code']; cells = r['cells']
            if not any(k not in ('TOL-', 'TOL+') for k in cells): continue
            name = NAME.get(code)
            if code == 'BTN-10' and 'NECK BAND' not in r['desc'] and 'COLLAR' not in r['desc']:
                name = r['desc'].title()
            if not name: name = r['desc'].title()
            sl = None
            if code in ('SLV-35', 'SLV-62') and sleeve_set(r['desc']):
                sl = frozenset(sleeve_set(r['desc']))
                d = r['desc']
                nums = re.findall(r'\d{2}(?:/\d{2})?', d.split('CB')[-1] if 'CB' in d else d)
                lab = ('Sleeve Length from CB ' if 'CB' in d else 'Sleeve Length ') + ('Exact ' if 'EXACT' in d else '') + ' '.join(n for n in nums if 30 <= int(n[:2]) <= 40)
                if '3 POINTS' in d: lab += ' (3 points)'
                name = lab
            key = (name, sl)
            row = rows.setdefault(key, dict(name=name, code=code, rank=RANK.get(code, 900),
                                            tol=tol_txt(r), spec=[None] * len(sizes), sl=sl, tols={}))
            row['tols'].setdefault(p['group'], tol_txt(r))
            if sl is not None and not (sl & sz['sleeves']):
                continue  # other sleeve length: not for this column
            v = cells.get(sz['key'])
            if v in (None, '0'): v = None
            row['spec'][ci] = v
    out = []
    for key, r in rows.items():
        if all(v is None for v in r['spec']):
            continue  # e.g. sleeve lengths the sample does not run
        if len(set(r['tols'].values())) > 1:
            short = {'REGULAR': 'Reg', 'BIG': 'Big', 'TALL': 'Tall'}
            r['tol'] = '  '.join(f"{short[g]} {t}" for g, t in r['tols'].items())
        out.append(r)
    out.sort(key=lambda r: (r['rank'], r['name']))
    return out

# ---------------- drawing ----------------
W, H = landscape(letter); L, R = 30, W - 30

def txt(c, x, y, s, f='AD', size=9, col=INK, align='l'):
    c.setFont(f, size); c.setFillColor(col)
    if align == 'c': c.drawCentredString(x, y, s)
    elif align == 'r': c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)

def fit(c, s, f, size, w):
    while size > 6 and pdfmetrics.stringWidth(s, f, size) > w: size -= 0.3
    return size

def draw(c, S, rows, today):
    # header band
    top = H - 28; bh = 58
    c.setFillColor(NAVY); c.roundRect(L, top - bh, R - L, bh, 6, stroke=0, fill=1)
    txt(c, L + 14, top - 20, 'Medidas de Prenda Terminada', 'ADB', 17, white)
    txt(c, L + 14, top - 38, f"{S['type']} · Programa {S['program'] or '—'} · Bloque {S['block']}", 'AD', 10, HexColor('#C9D1E0'))
    # key + style + color chip
    chip = f"{S['key']}   ·   {S['style']}   ·   {S['color']}"
    cw = min(430, pdfmetrics.stringWidth(chip, 'ADB', 14) + 30)
    c.setFillColor(AMBER); c.roundRect(R - cw - 12, top - bh + 12, cw, bh - 24, 5, stroke=0, fill=1)
    txt(c, R - 12 - cw / 2, top - bh / 2 - 5, chip, 'ADB', fit(c, chip, 'ADB', 14, cw - 16), NAVY, 'c')

    # table
    y = top - bh - 16
    n = len(S['sizes'])
    posw, tolw = 200, 80
    colw = (R - L - posw - tolw) / n
    specw = min(62, colw * 0.42); boxw = colw - specw
    th1, th2 = 22, 16
    c.setFillColor(NAVY); c.rect(L, y - th1 - th2, R - L, th1 + th2, stroke=0, fill=1)
    txt(c, L + 8, y - th1 - th2 / 2 - 2, 'Punto de medida', 'ADB', 10, white)
    txt(c, L + posw + tolw / 2, y - th1 - th2 / 2 - 2, 'Tol (−/+)', 'ADB', 9, white, 'c')
    for i, sz in enumerate(S['sizes']):
        x = L + posw + tolw + i * colw
        lab = f"Talla {sz['label']}"
        txt(c, x + colw / 2, y - 15, lab, 'ADB', fit(c, lab, 'ADB', 12, colw - 8), AMBER, 'c')
        txt(c, x + specw / 2, y - th1 - th2 / 2 - 2, 'Spec', 'ADB', 9, white, 'c')
        txt(c, x + specw + boxw / 2, y - th1 - th2 / 2 - 2, f"Medida ({sz['pcs']} pzs)" if sz['pcs'] else 'Medida', 'ADB', 9, white, 'c')
        c.setStrokeColor(HexColor('#3A4A6B')); c.setLineWidth(0.8); c.line(x, y, x, y - th1 - th2)
    y -= th1 + th2
    foot = 118
    rh = max(14, min(24, (y - foot) / max(1, len(rows))))
    tabtop = y
    for i, r in enumerate(rows):
        if i % 2: c.setFillColor(ZEBRA); c.rect(L, y - rh, R - L, rh, stroke=0, fill=1)
        fs = fit(c, r['name'], 'ADB', 9.5, posw - 12)
        txt(c, L + 8, y - rh / 2 - 3, r['name'], 'ADB', fs)
        if '  ' in r['tol']:
            a, b = r['tol'].split('  ', 1)
            txt(c, L + posw + tolw / 2, y - rh / 2 + 1, a, 'AD', fit(c, a, 'AD', 7.5, tolw - 4), MUTED, 'c')
            txt(c, L + posw + tolw / 2, y - rh / 2 - 7, b, 'AD', fit(c, b, 'AD', 7.5, tolw - 4), MUTED, 'c')
        else:
            txt(c, L + posw + tolw / 2, y - rh / 2 - 3, r['tol'], 'AD', fit(c, r['tol'], 'AD', 8.5, tolw - 4), MUTED, 'c')
        for ci in range(n):
            x = L + posw + tolw + ci * colw
            v = r['spec'][ci]
            c.setFillColor(CHIP); c.rect(x, y - rh, specw, rh, stroke=0, fill=1)
            txt(c, x + specw / 2, y - rh / 2 - 3.5, v if v else '—', 'ADB', 10.5, INK if v else MUTED, 'c')
        c.setStrokeColor(RULE); c.setLineWidth(0.5); c.line(L, y - rh, R, y - rh)
        y -= rh
    c.setStrokeColor(RULE); c.setLineWidth(0.8)
    for xx in [L + posw, L + posw + tolw] + [L + posw + tolw + i * colw for i in range(1, n)]:
        c.line(xx, tabtop, xx, y)
    c.setLineWidth(0.5)
    for i in range(n):
        c.line(L + posw + tolw + i * colw + specw, tabtop, L + posw + tolw + i * colw + specw, y)
    c.rect(L, y, R - L, tabtop - y)

    # sign-off + notes
    y -= 12
    bw = 170; bh2 = 40
    for i, lab in enumerate(['Medido por', 'Fecha']):
        bx = L + i * (bw + 10)
        c.setStrokeColor(RULE); c.setLineWidth(0.8); c.roundRect(bx, y - bh2, bw, bh2, 4)
        txt(c, bx + 8, y - 12, lab, 'ADB', 8.5, MUTED)
    ox = L + 2 * (bw + 10)
    c.roundRect(ox, y - bh2, R - ox, bh2, 4)
    txt(c, ox + 8, y - 12, 'Observaciones', 'ADB', 8.5, MUTED)
    # footer
    c.setStrokeColor(RULE); c.setLineWidth(0.6); c.line(L, 34, R, 34)
    txt(c, L, 22, f"Medidas en pulgadas · Spec del bloque {S['block']} (TBI PLM, Points of Measure) · {S['sample']}", 'AD', 7.5, MUTED)
    txt(c, R, 22, f"Impreso {today}", 'AD', 7.5, MUTED, 'r')

def main():
    D = json.load(open(SRC))['records']
    MES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    t = datetime.date.today(); today = f"{t.day} de {MES[t.month-1]} de {t.year}"
    report = []
    for rec in D:
        f = rec['cellValuesByFieldId']
        style_link = (f.get('fldGIFKuLeYSPihsO') or [{}])[0].get('name', '')
        kc = [v for vs in (f.get('fldJTeae3DJgy3vvy') or {}).get('valuesByLinkedRecordId', {}).values() for v in vs]
        key = [v for vs in (f.get('fld3zBnDfX40lN64T') or {}).get('valuesByLinkedRecordId', {}).values() for v in vs]
        szs = f.get('flde3UQtmKluIDlVp')
        typ = (f.get('fldaMHTDQZWM5vAd6') or {}).get('name', '')
        block = kc[0].split(' | ')[1] if kc else None
        st, _, col = style_link.partition(' | ')
        item = dict(id=rec['id'], sample=f.get('fldruCuDdImeXtpFz', ''), style=st, color=col,
                    key=key[0] if key else '', block=block, type=typ, program=f.get('fldWE14j9RCa8RvS5', ''))
        if typ != 'PPS':
            continue  # PPS only (Magaly, November 17, 2026)
        if not szs or not block or not key:
            report.append(dict(item, status='skipped', why='no sizes' if not szs else 'no key / block')); continue
        if block not in BLOCK_FILES:
            report.append(dict(item, status='skipped', why=f'no spec PDF on Matrix Block {block}')); continue
        sizes = []
        for part in szs.split(','):
            tok, _, pcs = part.rpartition(' - ')
            sz = parse_size(tok); sz['pcs'] = pcs.strip(); sizes.append(sz)
        notes = []
        rows = build_rows(block, sizes, notes)
        item['sizes'] = sizes
        fn = f"Medidas Prenda Terminada - {st} {col} - {typ}.pdf".replace('/', '-')
        c = canvas.Canvas(os.path.join(OUT, fn), pagesize=landscape(letter))
        c.setTitle(f"Medidas de Prenda Terminada - {st} {col}")
        draw(c, item, rows, today); c.showPage(); c.save()
        blanks = [f"{r['name']} @ {sizes[i]['label']}" for r in rows for i, v in enumerate(r['spec']) if v is None]
        report.append(dict(item, sizes=[s['label'] for s in sizes], status='ok', file=fn, rows=len(rows), notes=notes, blanks=blanks))
    json.dump(report, open(os.path.join(OUT, '_report.json'), 'w'), indent=1, ensure_ascii=False)
    ok = sum(1 for r in report if r['status'] == 'ok')
    print('built', ok, 'skipped', len(report) - ok)

main()
