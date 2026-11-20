// Daily Factory Report PDFs, printed from the factory page itself (Reporte Diario de Fábrica).
// Maggie, November 20, 2026: the PDF must look like the page (new layout of November 18, 2026),
// so this prints the page's own code with the day's data instead of rebuilding a separate layout.
//
// Usage: node tools/factory_pdf.js <page.html> <app.css> <data_dir> <out_dir> <YYYY-MM-DD>
//   page.html : the page code (ArtifactData collection "files", doc "index.html", field "text")
//   app.css   : the page type's stylesheet (Artifact read path "artifact-type/app.css")
//   data_dir  : one <dataset id>.json per dataset (the rows of each file in collection "datasets")
// Makes: "Que se movio ayer - <D mon YYYY>.pdf" (Piso, Corte, Accesorios, Telas; no Historial)
//        "Plan de embarque - <D mon YYYY>.pdf" (Plan tab only)
const fs = require('fs'), path = require('path'), { execSync } = require('child_process');
const [pagePath, cssPath, dataDir, outDir, day] = process.argv.slice(2);
if (!day) { console.error('usage: node factory_pdf.js page.html app.css data_dir out_dir YYYY-MM-DD'); process.exit(1); }

const toolDir = __dirname;
if (!fs.existsSync(path.join(toolDir, 'node_modules/d3/dist/d3.min.js')))
  execSync('npm i --no-save --silent d3@7.9.0', { cwd: toolDir, stdio: 'inherit' });
const { chromium } = require('playwright');

const MES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const MON = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
const [Y, M, D] = day.split('-').map(Number);
const fechaEs = `${D} de ${MES[M - 1]} de ${Y}`, short = `${D} ${MON[M - 1]} ${Y}`;

const data = {};
for (const f of fs.readdirSync(dataDir)) if (f.endsWith('.json')) data[f.slice(0, -5)] = JSON.parse(fs.readFileSync(path.join(dataDir, f), 'utf8'));

const shim = `<script>
(function(){
const RAW=window.__DATA__, calcs={}, draws={}; let params={};
function data(id){ if(calcs[id]){const c=calcs[id]; try{return {status:'ok',data:c.fn(...c.inputs.map(i=>data(i).data||[]))}}catch(e){console.error(e);return {status:'error',data:[]}} }
  return RAW[id]===undefined ? {status:'missing',data:[]} : {status:'ok',data:RAW[id]}; }
window.dash={data, calc(id,c){calcs[id]=c}, draw(n,fn){(draws[n]=draws[n]||[]).push(fn)},
  params(){return params}, setParams(p){Object.assign(params,p);for(const k in params) if(params[k]==null) delete params[k]; redraw()}, setLink(){}};
function redraw(){ for(const [n,fns] of Object.entries(draws)) document.querySelectorAll('[data-draw="'+n+'"]').forEach(el=>fns.forEach(f=>{try{f(el)}catch(e){console.error(n,e)}})); }
window.__redraw=redraw;
})();
</script>`;

function harness(tabs, title) {
  const show = JSON.stringify(tabs);
  return `<!doctype html><html class="cds-root" data-density="comfortable"><head><meta charset="utf-8">
<style>${fs.readFileSync(cssPath, 'utf8')}</style>
<script>window.__DATA__=${JSON.stringify(data)};</script>
<script>${fs.readFileSync(path.join(toolDir, 'node_modules/d3/dist/d3.min.js'), 'utf8')}</script>${shim}
<style>
html,body{margin:0;background:#fff!important;clip-path:none!important;height:auto!important;overflow:visible!important}
body{width:1240px}
.mv-tabs{display:none!important}
.mv-page.part{display:flex!important}
.mv-page.part + .mv-page.part{break-before:page}
.pl-print-tip{display:block;font-size:11px;font-weight:400;color:#4A5560;margin-top:3px;line-height:1.35;white-space:normal}
.part-title{font-family:Montserrat,sans-serif;font-weight:700;font-size:26px;color:#1D3F7A;margin:0 0 8px}
tr,.mv-card,.fl-st{break-inside:avoid}
</style></head><body>${fs.readFileSync(pagePath, 'utf8')}
<script>
window.addEventListener('load',()=>{
  const want=${show}, names={hoy:'Piso','corte-tab':'Corte','avios-tab':'Accesorios','telas-tab':'Telas',plan:'Plan de embarque'};
  document.querySelectorAll('.mv-page').forEach(p=>{ const on=want.includes(p.id); p.hidden=!on; if(on){p.classList.add('part');
    const h=document.createElement('div'); h.className='part-title'; h.textContent=names[p.id]||p.id; p.prepend(h);} });
  // on paper there is no hover: write each pop-up (missing trims, fabric) right under its chip
  if (window.PL && PL.lines) PL.tip = (box, node, text) => { if (!text) return; const d = document.createElement('span'); d.className = 'pl-print-tip';
    PL.lines(text).forEach((l) => { const r = document.createElement('div'); r.textContent = l; d.append(r); }); node.append(d); };
  window.__redraw();
  // open every collapsed week and purchase PO, so the PDF shows what the page shows when clicked
  document.querySelectorAll('.mv-page.part details').forEach(d=>d.open=true);
  setTimeout(()=>{ window.__ready=true; }, 300);
});
</script></body></html>`;
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const b = await chromium.launch();
  const jobs = [
    { tabs: ['hoy', 'corte-tab', 'avios-tab', 'telas-tab'], title: '¿Qué se movió ayer?', file: `Que se movio ayer - ${short}.pdf` },
    { tabs: ['plan'], title: 'Plan de embarque', file: `Plan de embarque - ${short}.pdf` },
  ];
  const errors = [];
  for (const j of jobs) {
    const p = await b.newPage({ viewport: { width: 1240, height: 1400 } });
    await p.emulateMedia({ media: 'screen' });
    p.on('pageerror', (e) => errors.push(j.title + ': ' + e.message));
    const tmp = path.join(outDir, '_' + j.tabs[0] + '.html');
    fs.writeFileSync(tmp, harness(j.tabs, j.title));
    await p.goto('file://' + path.resolve(tmp), { waitUntil: 'load' });
    await p.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
    await p.waitForTimeout(800);
    await p.pdf({
      path: path.join(outDir, j.file), format: 'Letter', printBackground: true,
      margin: { top: '0.45in', bottom: '0.55in', left: '0.45in', right: '0.45in' },
      scale: Math.min(1, (7.6 * 96) / 1240),
      displayHeaderFooter: true, headerTemplate: '<span></span>',
      footerTemplate: `<div style="width:100%;font-size:8px;color:#5d6577;text-align:center;font-family:Inter,sans-serif">${j.title} · Protexsa · ${fechaEs} · página <span class="pageNumber"></span> de <span class="totalPages"></span></div>`,
    });
    fs.unlinkSync(tmp);
    await p.close();
  }
  await b.close();
  if (errors.length) console.error('Page errors:\n' + errors.join('\n'));
  console.log('Made: ' + jobs.map((j) => j.file).join(', '));
})();
