import pdfplumber, re, sys, json
CODE=re.compile(r'^[A-Z]{3,4}-\d{2,3}$')
NUM=re.compile(r'^-?\d+(/\d+)?$')
def lines_of(words, tol=3):
    rows=[]
    for w in sorted(words,key=lambda w:(round(w['top']),w['x0'])):
        for r in rows:
            if abs(r[0]-w['top'])<=tol: r[1].append(w); break
        else: rows.append([w['top'],[w]])
    return [(t,sorted(ws,key=lambda w:w['x0'])) for t,ws in sorted(rows,key=lambda r:r[0])]
def join_cells(ws, cols):
    # assign tokens to nearest column center, join
    out={}
    for w in ws:
        cx=(w['x0']+w['x1'])/2
        best=min(cols,key=lambda c:abs(c[1]-cx))
        if abs(best[1]-cx)>25: continue
        out.setdefault(best[0],[]).append(w['text'])
    return {k:' '.join(v) for k,v in out.items()}
def parse(path):
    pages=[]
    with pdfplumber.open(path) as pdf:
        for pi,p in enumerate(pdf.pages):
            txt=p.extract_text() or ''
            if 'Points of Measure' not in txt: continue
            L=lines_of(p.extract_words(keep_blank_chars=False,x_tolerance=1.5))
            name=''; hdr=None; tolx=None
            for i,(t,ws) in enumerate(L):
                s=' '.join(w['text'] for w in ws)
                if s.strip()=='Page Name' and i+1<len(L): name=' '.join(w['text'] for w in L[i+1][1])
                if s.startswith('Page Name') and len(ws)>2: name=' '.join(w['text'] for w in ws[2:])
                if 'Incremental' in s:
                    k=[j for j,w in enumerate(ws) if w['text']=='/'][0]
                    toks=ws[k+1:]
                    # stacked header line above? (e.g. XXXX over L) ignore
                    cols=[]
                    for w in toks:
                        if re.match(r'^\d+/\d+$',w['text']) and cols and w['x0']-cols[-1][2]<12:
                            cols[-1]=(cols[-1][0]+' '+w['text'],cols[-1][1],w['x1'],cols[-1][3])
                        else: cols.append((w['text'],w['x0'],w['x1'],w['x0']))
                    hdr=[(c[0],(c[3]+c[2])/2) for c in cols]; hi=i
                tw=[w for w in ws if w['text'] in('(-)','(+)')]
                if len(tw)==2 and tolx is None:
                    tolx=[('TOL-',(tw[0]['x0']+tw[0]['x1'])/2-12),('TOL+',(tw[1]['x0']+tw[1]['x1'])/2-12)]
            if not hdr: continue
            body=[]
            for t,ws in L:
                if t<=L[hi][0]+5: continue
                s=' '.join(w['text'] for w in ws)
                if s.startswith('CONFIDENTIAL'): break
                body.append((t,ws))
            codes=[(t,ws) for t,ws in body if CODE.match(ws[0]['text'])]
            if not codes: continue
            first_t=codes[0][0]
            valx = (tolx[0][1]-20) if tolx else hdr[0][1]-40
            rows=[dict(code=ws[0]['text'],top=t,words=list(ws[1:])) for t,ws in codes]
            for t,ws in body:
                if CODE.match(ws[0]['text']): continue
                if t<first_t-12: continue
                r=min(rows,key=lambda r:abs(r['top']-t))
                if abs(r['top']-t)>12: continue
                r['words']+= ws
            out=[]
            for r in rows:
                ws=sorted(r['words'],key=lambda w:(round(w['top']),w['x0']))
                desc=' '.join(w['text'] for w in ws if w['x1']<valx)
                vals=sorted([w for w in ws if w['x0']>=valx],key=lambda w:(w['x0']))
                # column join: order tokens inside a column by top then x
                cells={}
                for w in sorted(vals,key=lambda w:(round(w['top']),w['x0'])):
                    cx=(w['x0']+w['x1'])/2
                    best=min(hdr+(tolx or []),key=lambda c:abs(c[1]-cx))
                    if abs(best[1]-cx)>25 or not NUM.match(w['text']): continue
                    cells.setdefault(best[0],[]).append(w['text'])
                cells={k:' '.join(v) for k,v in cells.items()}
                out.append(dict(code=r['code'],desc=desc,cells=cells))
            rows=out
            pages.append(dict(page=pi+1,name=name,sizes=[h[0] for h in hdr],rows=rows))
    return pages
if __name__=='__main__':
    print(json.dumps(parse(sys.argv[1]),indent=1))
