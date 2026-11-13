import json, datetime as dt, collections, re, sys

TODAY = dt.date(2026, 11, 12)
MON = TODAY - dt.timedelta(days=TODAY.weekday())
MES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']

def d(s):
    return dt.date.fromisoformat(s[:10]) if s else None

def fmt(x):
    return f"{x.day} {MES[x.month-1][:3]}" if x else ''

def fmtl(x):
    return f"{x.day} de {MES[x.month-1]} de {x.year}" if x else ''

def lk(v):
    if isinstance(v, dict) and 'valuesByLinkedRecordId' in v:
        out = []
        for x in v['valuesByLinkedRecordId'].values():
            out.extend(x)
        return out
    return v or []

def first(v):
    v = lk(v)
    return v[0] if isinstance(v, list) and v else (v if not isinstance(v, list) else None)

def sel(v):
    return v.get('name') if isinstance(v, dict) else v

# ---------- WIP ----------
wip = []
for f in ['wip.json', 'wip2.json', 'wip3.json']:
    wip += json.load(open(f))['records']

# ---------- fabric containers ----------
cont = {}
for r in json.load(open('cont.json'))['records']:
    c = r['cellValuesByFieldId']
    cont[c['fldgAZ8LRxYTpWUyM']] = dict(
        contenedor=c['fldgAZ8LRxYTpWUyM'],
        estado=sel(c.get('fldLtDMwTWsRACCSO')) or 'Por embarcar',
        etd=c.get('fld8ZQL5pFN7Hqe2E'), eta_puerto=c.get('fldihonrYIF9Jp6wp'),
        eta_planta=c.get('fld8XEo6tEevCI1L1'), dias_atraso=c.get('fldygQXyV9WgMjFlK') or 0,
        mill=(c.get('fldY1dV3uoTmbuZct') or '').split(' (')[0],
        pos_tela=c.get('fldujBQTGgZ9nr0W0') or '', lines=[x['id'] for x in c.get('fld0yuFQrlc2uzvJN', [])])

EST = {'Delayed': 'Atrasado', 'In transit': 'En camino', 'Delivered': 'En planta', 'Arrived port': 'En puerto',
       'Cleared': 'En planta', 'Por embarcar': 'Por embarcar'}

def eta_plant(c):
    if c.get('eta_planta'):
        return d(c['eta_planta'])
    if c.get('eta_puerto'):
        return d(c['eta_puerto']) + dt.timedelta(days=10)
    return None

active = [c for c in cont.values() if c['estado'] not in ('Delivered',)]
active.sort(key=lambda c: (c['eta_puerto'] or '9999', c['contenedor']))
PALETTE = ['#5B2C6F', '#1F7A8C', '#D9822B', '#3A6FB5', '#8E5572', '#4E6E58', '#B5651D', '#2E4057']
colors = {c['contenedor']: i for i, c in enumerate(active)}

# ---------- fabric buy lines ----------
fb = {}
for r in json.load(open('fbuy.json'))['records']:
    c = r['cellValuesByFieldId']
    fb[r['id']] = c

# ---------- trims ----------
inv = {}
for r in json.load(open('inv.json'))['records']:
    c = r['cellValuesByFieldId']
    inv[c['fldbqYsyWiKCwgjGY']] = c.get('fldadwhQQxl6Aya4i') or 0
styles = {}
for r in json.load(open('styles.json'))['records']:
    c = r['cellValuesByFieldId']
    styles[r['id']] = dict(style=c.get('fldTf9WE3KjoFfWea'), color=(c.get('fldw1OPMLw2Z8JbGi') or '').strip(),
                           start=c.get('fld25oR2o9JRIOziK'), program=c.get('fld5wooWq8pBvWb1k'), lines=[])
lines = {}
for r in json.load(open('lines.json'))['records']:
    c = r['cellValuesByFieldId']
    L = dict(id=r['id'], mode=sel(c.get('fldS440wbns8Yp7HE')), sap=c.get('fldo2p2etwiwwuLpO') or '',
             grid=c.get('fldmm062utp8uUcQQ') or '', desc=(c.get('fldCHKGKkK5VztX7T') or '').strip(),
             uom=c.get('fld0vo0JbGe1Exdok') or '', need=c.get('fldO7sQgCajspA7oQ') or 0,
             short_after=c.get('fld6iauWFNGkzLKHU'), status=sel(c.get('fldTp0ZVBxIfGvIsG')),
             po=(c.get('fldEoIEe9JAgB7Icf') or '').strip(), eta=c.get('fldcrYtQI64nscr06'),
             recv=c.get('fldyGANkhe2AnjFcf'), missing=c.get('fldojp5BtLP3Uql5L') or 0,
             bshort=c.get('fldXdpsRKmfDTJJJt') or 0, real=c.get('fldd4jmkfqYZZENmF'),
             closed=bool(c.get('fldDMztpZJHVc97zm')), compras=sel(c.get('fldJrpd9qY9yrRibW')),
             shipped=c.get('fldtIooJxaDvitRKo'), customs=c.get('fld2BrXOnG0EMJ1ox'), tbi=c.get('fldogDyjom6aPEsiP') or '', name=(c.get('fld7XX9NBPqRiAY6W') or c.get('fldogDyjom6aPEsiP') or '').strip())
    if isinstance(L['eta'], str) and L['eta'][:2] not in ('20',):
        L['eta'] = None
    L['onhand'] = inv.get(f"{L['sap']} | {L['grid']}") if L['grid'] else inv.get(f"{L['sap']} | NO GRID")
    lines[r['id']] = L
    for s in c.get('fldvzHfU5HgxW99jd', []):
        if s['id'] in styles:
            styles[s['id']]['lines'].append(r['id'])

by_sc = collections.defaultdict(list)
for sid, s in styles.items():
    by_sc[(s['style'], s['color'].lower())].append(s)

IGNORE = {'Customer Service to order', 'Warehouse orders it', 'Ordered per release', 'Small short, not bought',
          'Covered by another buy', 'Bought monthly'}
RANK = {'Falta': 4, 'Tarde': 3, 'Sin fecha': 2, 'En camino': 1, 'En casa': 0}

def trim_status(style, color, start, need_by):
    cands = by_sc.get((style, (color or '').lower()), [])
    if not cands:
        return None
    s = min(cands, key=lambda x: abs((d(x['start']) - start).days) if (x['start'] and start) else 999)
    worst, probs = 'En casa', []
    for lid in s['lines']:
        L = lines[lid]
        if L['closed'] or L['status'] in IGNORE or L['recv']:
            continue
        if L['onhand'] is not None and L['need'] and L['onhand'] >= L['need']:
            continue
        if L['status'] == 'In stock' and not (L['missing'] or L['bshort']):
            continue
        st = None
        if L['missing'] or L['bshort']:
            st = 'Falta'
            if L['real'] is not None and L['real'] < 0:
                short = -L['real']
            elif L['short_after'] and L['short_after'] > 0:
                short = L['short_after']
            else:
                short = (L['need'] or 0) - (L['onhand'] or 0)
            if short <= 0:
                continue
            txt = f"{L['name']} · faltan {int(round(short)):,} {L['uom']}".strip()
        elif L['eta']:
            e = d(L['eta'])
            if need_by and e > need_by:
                st = 'Tarde'; txt = f"{L['name']} · llega {fmt(e)}"
            else:
                st = 'En camino'; txt = None
        else:
            st = 'Sin fecha'; txt = f"{L['name']} · sin fecha de llegada"
        if RANK[st] > RANK[worst]:
            worst = st
        if txt and st in ('Falta', 'Tarde', 'Sin fecha'):
            probs.append((RANK[st], txt))
    probs.sort(key=lambda x: -x[0])
    tip = [t for _, t in probs]
    if len(tip) > 6:
        tip = tip[:6] + [f"y {len(tip) - 6} más"]
    return dict(estado=worst, tip=' | '.join(tip), compras=s['lines'] and lines[s['lines'][0]]['compras'])

# ---------- PO rows ----------
plan = []
for r in wip:
    c = r['cellValuesByFieldId']
    status = sel(c.get('fldH8umxRFCfP6Iio'))
    stage = sel(first(c.get('fldyIs7Vjz9OsRN5y')))
    if stage in ('Shipped', 'Packed, waiting to ship'):
        continue
    maru = d(c.get('fldHnMdIBYDEdxBX0'))
    xf = d(c.get('fldODhCKQl5k1d4I8'))
    pdate = maru or xf
    if not pdate:
        continue
    style = c.get('fldOmgxSUkAvWsSjl'); color = sel(c.get('fldS2kAkKZtZwOLfy'))
    start = d(c.get('fldoqvCqeYOq5VTT8'))
    program = first(c.get('fldeIx4hc9RfFfGoM')) or sel(c.get('fldNEwm0LAC6ntnFf')) or ''
    cn = first(c.get('fld800uXuCwDgk7qK'))
    need_by = pdate - dt.timedelta(days=21)
    if cn and cn in colors:
        k = cont[cn]
        e = eta_plant(k)
        tela = 'Tarde' if (e and e > need_by) else ('Sin fecha' if not e else 'A tiempo')
        tela_tip = f"{cn} · {EST.get(k['estado'], k['estado'])} · llega a planta ~{fmt(e)} · se necesita el {fmt(need_by)}" if e else f"{cn} · sin fecha de llegada"
        cidx = colors[cn]
    elif cn:
        tela = 'En planta'; tela_tip = f"{cn} · ya llegó a planta"; cidx = -1
    else:
        tela = 'Sin contenedor'; tela_tip = 'Todavía no tiene contenedor asignado'; cidx = -2
    ts = trim_status(style, color, start, need_by)
    wk = pdate - dt.timedelta(days=pdate.weekday())
    plan.append(dict(
        po=c.get('fldaW3eA1EiCnWzwq'), of=c.get('fld1yOntZ6nlM6Dv8') or '', programa=program, estilo=style, color=color,
        piezas=c.get('fldTh1u7viIjuIP2M') or 0, fecha_plan=pdate.isoformat(), fuente='Maru' if maru else 'Ex-factory',
        ex_factory=xf.isoformat() if xf else '', semana=wk.isoformat() if wk >= MON else 'atrasadas',
        semana_txt=(f"Semana del {fmtl(wk)}" if wk >= MON else 'Antes de esta semana (sin embarcar)'),
        contenedor=cn or '', color_idx=cidx, tela=tela, tela_tip=tela_tip, tela_alerta=tela in ('Tarde', 'Sin fecha'),
        avios=(ts or {}).get('estado', 'Sin datos'), avios_tip=(ts or {}).get('tip', 'No está en un archivo de Compras'),
        avios_alerta=bool(ts and ts['estado'] in ('Falta', 'Tarde', 'Sin fecha')), etapa=stage or ''))

plan.sort(key=lambda p: (p['semana'] != 'atrasadas', p['semana'], p['fecha_plan'], p['programa'], p['estilo'], p['po']))

# ---------- container lines ----------
po_by_sc = collections.defaultdict(list)
for p in plan:
    po_by_sc[(p['estilo'], (p['color'] or '').lower())].append(p)
contenedores, cont_lineas = [], []
for k in active:
    e = eta_plant(k)
    lns = [fb[i] for i in k['lines'] if i in fb]
    tot_u = tot_y = 0
    for c in lns:
        sc = c.get('fldahyaIgGIfORcFZ', '').split(' | ')
        style, color = sc[0], sc[1] if len(sc) > 1 else ''
        units = first(c.get('fldZ36IItLCuoZhS9')) or 0
        yds = c.get('fldoeZ53ksKba5glO') or c.get('fldUuTdljiATMNmle') or c.get('fld3ZXCtA8thDn8z6') or 0
        tot_u += units; tot_y += yds
        pos = sorted(po_by_sc.get((style, color.lower()), []), key=lambda p: p['fecha_plan'])
        cont_lineas.append(dict(
            contenedor=k['contenedor'], programa=first(c.get('fldnUsu5XW5YHi5kf')) or '', estilo=style, color=color,
            piezas=units, yardas=round(yds), entrega=' | '.join(sc[2:]),
            pos=' · '.join(f"{p['po']} ({fmt(d(p['ex_factory']))})" for p in pos) or 'Sin PO todavía',
            avios=max((p['avios'] for p in pos), key=lambda s: RANK.get(s, -1), default='Sin datos'),
            avios_tip=next((p['avios_tip'] for p in pos if p['avios_alerta']), '')))
    contenedores.append(dict(
        contenedor=k['contenedor'], color_idx=colors[k['contenedor']], estado=EST.get(k['estado'], k['estado']),
        etd=k['etd'] or '', eta_puerto=k['eta_puerto'] or '', eta_planta=e.isoformat() if e else '',
        dias_atraso=k['dias_atraso'], mill=k['mill'], pos_tela=k['pos_tela'], piezas=tot_u, yardas=round(tot_y),
        estilos=len(lns), pos_afectados=sum(1 for p in plan if p['contenedor'] == k['contenedor'])))

# ---------- trim POs ----------
tp = collections.defaultdict(list)
for L in lines.values():
    if L['po'] and not L['closed']:
        tp[L['po']].append(L)
avios_po = []
for po, ls in tp.items():
    open_ = [L for L in ls if not L['recv'] and not (L['onhand'] is not None and L['need'] and L['onhand'] >= L['need'])]
    if not open_:
        continue
    etas = [d(L['eta']) for L in open_ if L['eta']]
    eta = max(etas) if etas else None
    if any(L['customs'] for L in open_):
        est = 'En aduana'
    elif any(L['shipped'] for L in open_):
        est = 'Embarcado'
    elif eta:
        est = 'En camino' if eta >= TODAY else 'Debió llegar'
    else:
        est = 'Sin fecha'
    modes = sorted({L['mode'] for L in open_ if L['mode']})
    avios_po.append(dict(po=po, via=' / '.join({'Air': 'Aéreo', 'Sea': 'Marítimo'}.get(m, m) for m in modes),
                         eta=eta.isoformat() if eta else '', estado=est, lineas=len(open_),
                         compras=', '.join(sorted({L['compras'] for L in open_ if L['compras']})),
                         detalle=' | '.join(sorted({L['name'] for L in open_}))[:400],
                         ref=' | '.join(sorted({f"{L['desc']} · {L['sap']}" for L in open_}))[:400]))
avios_po.sort(key=lambda a: (a['eta'] or '9999', a['po']))

for name, data in [('plan_pos', plan), ('plan_contenedores', contenedores), ('plan_lineas', cont_lineas), ('plan_avios', avios_po)]:
    json.dump(data, open(f'out_{name}.json', 'w'), ensure_ascii=False)
    print(name, len(data), len(json.dumps(data, ensure_ascii=False)))
print(collections.Counter(p['semana'] for p in plan).most_common(40))
print(collections.Counter((p['tela'], p['avios']) for p in plan).most_common(30))
