"""Final Audit PDF for one PO (Protexsa / TBI), same layout as the November 14, 2026 audits.

Usage: python3 -I tools/final_audit_pdf.py spec.json out.pdf

spec.json keys (all text in English, as printed):
  program, division, main_label, fabric_content, ex_factory ("Dec 4, 2026"), po, buyer_po, style, color,
  of, ship_mode ("Bulk · Flat"), extra_buttons, fit_block, units_per_box, cartons, weave, garment_wash (bool),
  non_iron (bool), item_description, carton_dimensions, po_comments,
  order_qty, cut_qty, cut_by_size {"15 1/2 x 32/33": n, ...} (dress sizes "neck x sleeve"),
  swatch (png path), trims_sewing / trims_packing [{trim, code, description, picture (png path or null)}],
  rn, price, color_code, key ("JAB OPP 07P"), fit_name ("Traditional"),
  poms [[description, tol, {size: spec}]], factory_rep (default Karla Alvarado)
AQL 2.5 Level II sample from cut_qty; sample per size = ROUNDUP(sample / cut_qty x size cut).
"""
import json, math, sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FD = '/usr/share/fonts/truetype/crosextra/'
pdfmetrics.registerFont(TTFont('Carlito', FD + 'Carlito-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Bold', FD + 'Carlito-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))

NAVY = colors.HexColor('#1F3864'); BLUE = colors.HexColor('#2F4F8F'); GREY = colors.HexColor('#E7E6EE')
LINE = colors.HexColor('#7F7F9F')
P = ParagraphStyle('p', fontName='Carlito', fontSize=7.5, leading=9)
PB = ParagraphStyle('pb', parent=P, fontName='Carlito-Bold')
PV = ParagraphStyle('pv', parent=P, textColor=BLUE)
H1 = ParagraphStyle('h1', fontName='Carlito-Bold', fontSize=14, leading=17)
H2 = ParagraphStyle('h2', fontName='Carlito-Bold', fontSize=10, leading=13, spaceBefore=6, spaceAfter=3)
BOX = '<font name="DejaVu">☐</font>'; XBOX = '<font name="DejaVu">☒</font>'

AQL = [(90, 13, 1, 2), (150, 20, 1, 2), (280, 32, 2, 3), (500, 50, 3, 4), (1200, 80, 5, 6),
       (3200, 125, 7, 8), (10000, 200, 10, 11), (35000, 315, 14, 15), (10**9, 500, 21, 22)]


def aql(n):
    for lim, s, a, r in AQL:
        if n <= lim:
            return s, a, r


def p(t, st=P):
    return Paragraph(str(t) if t is not None else '', st)


def grid_table(sizes):
    """sizes {"15 1/2 x 32/33": n} -> rows by sleeve, columns by neck."""
    necks, sleeves = [], []
    for k in sizes:
        n, s = k.split(' x ')
        necks.append(n) if n not in necks else None
        sleeves.append(s) if s not in sleeves else None
    nk = lambda x: float(x.replace(' 1/2', '.5'))
    necks.sort(key=nk); sleeves.sort(key=lambda x: int(x.split('/')[0]))
    rows = [['Sleeve'] + necks + ['Total']]
    for s in sleeves:
        vals = [sizes.get(f'{n} x {s}', '') for n in necks]
        rows.append([s] + vals + [sum(v for v in vals if v != '')])
    rows.append(['Total'] + [sum(sizes.get(f'{n} x {s}', 0) for s in sleeves) for n in necks] + [sum(sizes.values())])
    return rows


def style_grid(t, nrows):
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Carlito', 7.5), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('BACKGROUND', (0, 0), (-1, 0), GREY), ('TEXTCOLOR', (1, 1), (-1, -1), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black), ('TEXTCOLOR', (0, 1), (0, -1), colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
    ]))
    return t


def build(spec, out):
    sp = spec
    foot = f"{sp['program']} · {sp['style']} {sp['color']} · PO {sp['po']} · OF {sp['of']}"

    def onpage(c, d):
        c.saveState(); c.setFont('Carlito', 6.5); c.setFillColor(colors.HexColor('#808080'))
        c.drawString(0.5 * inch, 0.45 * inch, foot)
        c.drawRightString(letter[0] - 0.5 * inch, 0.45 * inch, f'Page {d.page}'); c.restoreState()

    doc = SimpleDocTemplate(out, pagesize=letter, leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.45 * inch, bottomMargin=0.7 * inch)
    W = letter[0] - inch
    st = []
    # ---------- Page 1
    st.append(p('FINAL AUDIT REPORT', H1)); st.append(Spacer(1, 6))
    yn = lambda b: f"Yes {XBOX if b else BOX}   No {BOX if b else XBOX}"
    s, ac, rj = aql(sp['cut_qty'])
    head = [
        ['Division', sp['division'], 'Main Label', sp['main_label'], 'Fabric Content', sp['fabric_content'], 'Ex-Factory Date', sp['ex_factory']],
        ['Factory', 'Monzini', 'PLM PO #', sp['po'], 'Country of Origin', 'Honduras', 'AQL STD', '2.5 Level II'],
        ['Supplier', 'Threadmark', 'Buyer PO #', sp['buyer_po'], 'Extra Buttons', sp['extra_buttons'], 'Order Qty', f"{sp['order_qty']:,}"],
        ['Style No', sp['style'], 'OF', sp['of'], 'Labels / Tags', 'See check list', 'Cut Qty', f"{sp['cut_qty']:,}"],
        ['Color', sp['color'], 'Ship Mode', sp['ship_mode'], 'Garment Wash', yn(sp['garment_wash']), 'Inspected Qty', str(s)],
        ['Fit Block', sp['fit_block'], 'Units per Box', sp['units_per_box'], 'Non Iron', yn(sp['non_iron']), 'Measured Qty', ''],
        ['Fabric Weave', sp['weave'], 'Total # Cartons', str(sp['cartons']), 'Cartons Inspected', '', 'Defects Obs.', ''],
        ['Auditor', '', '', '', 'Audit Date', '', 'Pass / Fail', ''],
    ]
    rows = [[p(c, PB if i % 2 == 0 else PV) for i, c in enumerate(r)] for r in head]
    for r in rows[4:6]:
        r[5] = p(r[5].text, ParagraphStyle('c', parent=P, alignment=1))
    for r in rows:
        r[7] = p(r[7].text, ParagraphStyle('r', parent=PV, alignment=1))
    cw = [0.75, 0.95, 0.85, 0.95, 0.95, 1.15, 0.9, 0.8]
    t = Table(rows, colWidths=[x * inch for x in cw], rowHeights=None)
    ts = [('GRID', (0, 0), (-1, -1), 0.4, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('SPAN', (1, 7), (3, 7))]
    for c in (0, 2, 4, 6):
        ts.append(('BACKGROUND', (c, 0), (c, -1), GREY))
    t.setStyle(TableStyle(ts)); st.append(t); st.append(Spacer(1, 6))
    t = Table([[p('Item Description', PB), p(sp['item_description'], PV)],
               [p('Carton Dimensions', PB), p(sp['carton_dimensions'], PV)],
               [p('PO Comments', PB), p(sp['po_comments'], PV)]], colWidths=[1.1 * inch, W - 1.1 * inch])
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, LINE), ('BACKGROUND', (0, 0), (0, -1), GREY),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    st.append(t)
    st.append(p('Cut by size (from the PO Distribution)', H2))
    g = grid_table(sp['cut_by_size']); st.append(style_grid(Table(g, colWidths=[W / len(g[0])] * len(g[0])), len(g)))
    st.append(Spacer(1, 4))
    t = Table([['AQL 2.5 Level II', 'Sample', str(s), 'Accept', str(ac), 'Reject', str(rj)]],
              colWidths=[0.95 * inch, 0.55 * inch, 0.45 * inch, 0.55 * inch, 0.45 * inch, 0.55 * inch, 0.45 * inch], hAlign='LEFT')
    t.setStyle(TableStyle([('FONT', (0, 0), (-1, -1), 'Carlito', 7.5), ('GRID', (0, 0), (-1, -1), 0.4, LINE),
                           ('TEXTCOLOR', (2, 0), (2, 0), BLUE), ('TEXTCOLOR', (4, 0), (4, 0), BLUE), ('TEXTCOLOR', (6, 0), (6, 0), BLUE)]))
    st.append(t)
    samp = {k: math.ceil(s / sp['cut_qty'] * v) for k, v in sp['cut_by_size'].items() if v}
    st.append(p('Sample to inspect by size', H2))
    g = grid_table(samp); st.append(style_grid(Table(g, colWidths=[W / len(g[0])] * len(g[0])), len(g)))
    st.append(PageBreak())
    # ---------- Page 2: defects
    st.append(p('Defect Check List (please refer to the Defect Classification List)', H2))
    sw = Image(sp['swatch'], width=1.55 * inch, height=1.55 * inch * 299 / 444) if sp.get('swatch') else ''
    rows = [['Code', 'Qty', 'Description of Defects', 'Code', 'Qty', 'Description of Defects', 'Swatch']] + [[''] * 6 + [sw if i == 0 else ''] for i in range(4)]
    t = Table(rows, colWidths=[x * inch for x in (0.4, 0.38, 1.6, 0.4, 0.38, 1.6, 1.9)], rowHeights=[12] + [26] * 4)
    t.setStyle(TableStyle([('FONT', (0, 0), (-1, -1), 'Carlito', 7), ('GRID', (0, 0), (-1, -1), 0.4, LINE),
                           ('BACKGROUND', (0, 0), (-1, 0), GREY), ('SPAN', (6, 1), (6, 4)),
                           ('ALIGN', (6, 0), (6, -1), 'CENTER'), ('VALIGN', (6, 1), (6, 4), 'MIDDLE')]))
    st.append(t); st.append(Spacer(1, 14))
    t = Table([[f"Factory Rep: {sp.get('factory_rep', 'Karla Alvarado')}", 'Auditor signature:', '', 'Date:', '']],
              colWidths=[1.9 * inch, 1.0 * inch, 2.4 * inch, 0.5 * inch, 1.2 * inch])
    t.setStyle(TableStyle([('FONT', (0, 0), (-1, -1), 'Carlito', 7.5), ('LINEBELOW', (2, 0), (2, 0), 0.5, colors.black),
                           ('LINEBELOW', (4, 0), (4, 0), 0.5, colors.black)]))
    st.append(t); st.append(PageBreak())
    # ---------- Page 3: check list
    t = Table([[p('Check List', H1), p(f"{sp['style']} {sp['color']}"), p(f"PO: {sp['po']}"), p(f"OF: {sp['of']}")]],
              colWidths=[2.9 * inch, 1.8 * inch, 1.3 * inch, 1.5 * inch])
    st.append(t)
    def trims(title, items):
        st.append(p(title, H2))
        rows = [[p('Trim'), p('Code'), p('Description'), p('Picture', ParagraphStyle('c', parent=P, alignment=1)), p('OK', ParagraphStyle('c', parent=P, alignment=1))]]
        for it in items:
            pic = ''
            if it.get('picture'):
                from PIL import Image as PI
                w, h = PI.open(it['picture']).size; mw, mh = 1.4 * inch, 0.55 * inch
                k = min(mw / w, mh / h); pic = Image(it['picture'], width=w * k, height=h * k)
            rows.append([p(it['trim']), p(it['code'], PV), p(it['description']), pic,
                         p(f'<font name="DejaVu" size="12">☐</font>', ParagraphStyle('c', parent=P, alignment=1))])
        t = Table(rows, colWidths=[x * inch for x in (1.3, 1.25, 2.3, 1.95, 0.7)])
        t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, LINE), ('BACKGROUND', (0, 0), (-1, 0), GREY),
                               ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (3, 1), (4, -1), 'CENTER'),
                               ('TOPPADDING', (0, 1), (-1, -1), 5), ('BOTTOMPADDING', (0, 1), (-1, -1), 5)]))
        st.append(t)
    trims('Sewing audit · Sewn into the shirt', sp['trims_sewing'])
    trims('Packing audit · Added at packing', sp['trims_packing'])
    st.append(Spacer(1, 8))
    t = Table([[p('RN / CA #', PB), p(sp['rn'], PV), p('Price', PB), p(sp['price'], PV), p('Color Code / Class', PB), p(sp['color_code'], PV)]],
              colWidths=[x * inch for x in (0.75, 0.9, 0.5, 0.9, 1.15, 1.1)], hAlign='LEFT')
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('BACKGROUND', (0, 0), (0, 0), GREY), ('BACKGROUND', (2, 0), (2, 0), GREY), ('BACKGROUND', (4, 0), (4, 0), GREY)]))
    st.append(t)
    # ---------- Measurement pages: 3 PO sizes (necks) per page
    necks = sorted({k.split(' x ')[0] for k in sp['cut_by_size']}, key=lambda x: float(x.replace(' 1/2', '.5')))
    for i in range(0, len(necks), 3):
        grp = necks[i:i + 3]
        st.append(PageBreak())
        t = Table([[p(f"Measurements · {sp['fit_name']} ({sp['key']})", H2),
                    p(f"Style: {sp['style']} · Color: {sp['color']} · PO: {sp['po']} · Buyer PO: {sp['buyer_po']}")]],
                  colWidths=[3.3 * inch, W - 3.3 * inch]); st.append(t)
        top = ['POM Description', 'Tol']; sub = ['', '']
        for n in grp:
            top += [n, '', '', '']; sub += ['Spec', '1', '2', '3']
        rows = [top, sub]
        for d, tol, specs in sp['poms']:
            r = [p(d), p(tol, ParagraphStyle('c', parent=P, alignment=1))]
            for n in grp:
                r += [specs.get(n, '-'), '', '', '']
            rows.append(r)
        cw = [1.85 * inch, 0.45 * inch] + [((W - 2.3 * inch) / (4 * len(grp)))] * (4 * len(grp))
        t = Table(rows, colWidths=cw, repeatRows=2)
        ts = [('FONT', (0, 0), (-1, -1), 'Carlito', 7), ('GRID', (0, 0), (-1, -1), 0.4, LINE),
              ('BACKGROUND', (0, 0), (-1, 1), GREY), ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
              ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)),
              ('TOPPADDING', (0, 2), (-1, -1), 4), ('BOTTOMPADDING', (0, 2), (-1, -1), 4)]
        for j in range(len(grp)):
            ts.append(('SPAN', (2 + 4 * j, 0), (5 + 4 * j, 0)))
        t.setStyle(TableStyle(ts)); st.append(t)
    doc.build(st, onFirstPage=onpage, onLaterPages=onpage)


if __name__ == '__main__':
    build(json.load(open(sys.argv[1])), sys.argv[2])
