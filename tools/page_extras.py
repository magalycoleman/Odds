"""Extra data for the factory page "¿Qué se movió ayer?" (Maggie, November 16, 2026).

Run from a folder holding these JSON files (Airtable pulls saved as returned, and today's page rows):
  bom.json      Matrix BOM table (SAP Code fldyShwQrchFJQr0L, Section fldv9kcsjw8ImLPa0, Sec flduUntYtnzF1ZkjM)
  trimlib.json  Matrix Trim Library (same pull as plan_build.py)
  fabric.json   Matrix Fabric table (Design Reference flddKwyjWiHufWniQ, Supplier Article fldbvJlzwI7BPXdKA,
                SAP Code fld70JqF9OOnQdsU1, Color Tech Pack fldxzW96s3xSejdjm, Swatch fldRhxhKUacq7SIhw, Style fldDNDDsj67DiqH2S)
  mstyle.json   Matrix Style table (Combo fldOTcuntvL1rBPCe, Style fldKatA8gFlYhs2R6, Label fldkQa7ccVPi6Bkxp)
  avios.json    today's accesorios rows (material, descripcion, color, unidad, antes, ahora, cambio, nota, clave)
  telas.json    today's telas rows (same fields; color holds the supplier)
Writes out_nombres_avios.json, out_avios.json, out_telas.json.
  accesorios: nombre = Trim Library name, seccion/orden = BOM section in BOM order (Spanish), else
              "No está en los BOM de TBI" (other customers or old trims).
  telas: ref | articulo | SAP code, color_tela, programas ("Label: style, style"), muestra (96 px swatch, JPEG data URL).
"""
import json, collections, base64, io, urllib.request
from PIL import Image

SEC_ES = {'Interlining': 'Entretela', 'Interlining Other': 'Entretela (otras)', 'Tape': 'Cinta', 'Button': 'Botones',
          'Thread': 'Hilo', 'Piping': 'Vivo', 'Label Sewing': 'Etiquetas de costura', 'Label Packing': 'Etiquetas de empaque',
          'Packing': 'Empaque'}
NOT_OURS = 'No está en los BOM de TBI'

def sel(v):
    return v.get('name') if isinstance(v, dict) else v

sec = collections.defaultdict(collections.Counter); secmin = {}
for r in json.load(open('bom.json'))['records']:
    c = r['cellValuesByFieldId']; s = sel(c.get('fldv9kcsjw8ImLPa0')); sap = (c.get('fldyShwQrchFJQr0L') or '').strip()
    if not s or not sap:
        continue
    sec[sap][s] += 1
    n = c.get('flduUntYtnzF1ZkjM')
    if n is not None:
        secmin[s] = min(secmin.get(s, 9999), n)

nm = {}
for r in json.load(open('trimlib.json'))['records']:
    c = r['cellValuesByFieldId']
    sap, n = (c.get('fldfVHjTRQfwKJV8x') or '').strip(), (c.get('fldGnHA6z6KykiL9T') or '').strip()
    if not sap.isdigit() or not n:
        continue
    cat = sel(c.get('fldWNAWJRzBKvw0ws')) or ''; cc = (c.get('fldDOEUUCt8FwWOVR') or '').strip()
    if 'Care' in cat and cc and cc not in n:
        n = n.replace(' | Care', f' ({cc}) | Care')
    if sap not in nm or c.get('fldkB0EOMnmYl7lFM'):
        nm[sap] = n

def secof(sap):
    if sap in sec:
        s = sec[sap].most_common(1)[0][0]
        return SEC_ES.get(s, s), secmin.get(s, 900)
    return None, None

nombres = []
for sap in sorted(set(nm) | set(sec)):
    s, o = secof(sap)
    nombres.append(dict(sap=sap, nombre=nm.get(sap, ''), seccion=s or '', orden=o if o is not None else 999))
json.dump(nombres, open('out_nombres_avios.json', 'w'), ensure_ascii=False)

av = json.load(open('avios.json'))
for r in av:
    s, o = secof(str(r['material']))
    r['nombre'] = nm.get(str(r['material']), '')
    r['seccion'] = s or NOT_OURS
    r['orden'] = o if o is not None else 999
json.dump(av, open('out_avios.json', 'w'), ensure_ascii=False)

sty = {}
for r in json.load(open('mstyle.json'))['records']:
    c = r['cellValuesByFieldId']; sty[c.get('fldOTcuntvL1rBPCe')] = (c.get('fldKatA8gFlYhs2R6'), c.get('fldkQa7ccVPi6Bkxp') or '')
bysap = collections.defaultdict(list)
for r in json.load(open('fabric.json'))['records']:
    c = r['cellValuesByFieldId']; bysap[(c.get('fld70JqF9OOnQdsU1') or '').strip()].append(c)

def thumb(c):
    a = (c.get('fldRhxhKUacq7SIhw') or [None])[0]
    if not a:
        return ''
    try:
        u = (a.get('thumbnails') or {}).get('large', {}).get('url') or a['url']
        im = Image.open(io.BytesIO(urllib.request.urlopen(u, timeout=30).read())).convert('RGB')
    except Exception as e:
        print('swatch not loaded:', e); return ''
    w, h = im.size; s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((96, 96))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=80)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()

te = json.load(open('telas.json'))
for r in te:
    m = bysap.get(str(r['material']), [])
    r['proveedor'] = r.get('proveedor') or r.get('color', '')
    if not m:
        r.update(ref='', articulo='', color_tela='', programas='', muestra='', en_matrix=False)
        continue
    c = m[0]
    r['ref'] = (c.get('flddKwyjWiHufWniQ') or '').replace('﻿', '').strip()
    r['articulo'] = (c.get('fldbvJlzwI7BPXdKA') or '').strip()
    r['color_tela'] = ' / '.join(dict.fromkeys((x.get('fldxzW96s3xSejdjm') or '').strip() for x in m if x.get('fldxzW96s3xSejdjm')))
    g = collections.OrderedDict()
    for x in m:
        for s in x.get('fldDNDDsj67DiqH2S', []):
            st, lab = sty.get(s['name'], (s['name'].split(' | ')[0], ''))
            g.setdefault(lab or 'Sin programa', []).append(st)
    r['programas'] = ' · '.join(f"{k}: {', '.join(dict.fromkeys(v))}" for k, v in g.items())
    r['muestra'] = thumb(c); r['en_matrix'] = True
json.dump(te, open('out_telas.json', 'w'), ensure_ascii=False)
print('nombres', len(nombres), '| accesorios', len(av), collections.Counter(r['seccion'] for r in av).most_common(),
      '| telas', len(te), sum(1 for r in te if r['en_matrix']), 'in the Matrix')
