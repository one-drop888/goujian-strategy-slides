const fs = require('fs');
const path = require('path');
const Ajv = require('ajv/dist/2020');
const {resolveSlide} = require('../composition/resolver');
const ROOT = path.resolve(__dirname,'../..');
const ajv = new Ajv({allErrors:true,strict:false});
for(const name of ['asset','evidence','slide','deck','profile','composition','reasoning-plan']) ajv.addSchema(JSON.parse(fs.readFileSync(path.join(__dirname,`${name}.schema.json`),'utf8')));
function schemaErrors(name,data) {
  const valid=ajv.getSchema(`${name}.schema.json`);
  return valid(data)?[]:valid.errors.map(e=>`${e.instancePath || '/'} ${e.message}`);
}
function validateDeck(spec) {
  const errors=schemaErrors('deck',spec);
  if(errors.length) return errors;
  const assets=new Map((spec.assets||[]).map(a=>[a.id,a]));
  if(assets.size!==(spec.assets||[]).length)errors.push('Asset IDs must be unique');
  function checkRegion(r,label) {if(r&&(r.x+r.w>1.00001||r.y+r.h>1.00001))errors.push(label+': region exceeds source bounds');}
  for(const a of spec.assets||[]) {
    checkRegion(a.crop,a.id+'.crop');checkRegion(a.safe_area,a.id+'.safe_area');
    for(const p of a.provenance||[]){if(p.source_asset&&!assets.has(p.source_asset))errors.push('Unknown provenance source_asset '+p.source_asset);checkRegion(p.source_region,a.id+'.provenance');}
  }
  spec.slides.forEach((raw,i)=>{
    const fail=m=>errors.push(`slides[${i}]: ${m}`);
    try {
      const {renderer,slide:s}=resolveSlide(raw,ROOT);
      if(!['cover','section'].includes(renderer)&&!s.title?.trim()) fail('title is required');
      const limits={summary:5,kpi:6,scorecard:7,process:6,funnel:6,timeline:7,matrix:14,hierarchy:5,action:6,risk:6,portfolio:4,pyramid:5};
      const items=s.items||s.branches||s.levels;
      if(limits[renderer]) {
        if(!Array.isArray(items)||!items.length) fail('nonempty items are required');
        else if(items.length>limits[renderer]) fail(`items exceed layout capacity ${limits[renderer]}; split the slide`);
        if(items?.some(x=>x==null || !['object','string'].includes(typeof x))) fail('items must be strings or objects');
      }
      if(renderer==='statement' && !(s.statement||s.body)?.trim()) fail('statement/body is required');
      if(s.decision_points && (!Array.isArray(s.decision_points)||s.decision_points.length<1||s.decision_points.length>3||s.decision_points.some(p=>!p.title?.trim()||!p.note?.trim())))fail('decision_points requires 1–3 titled explanations');
      if(s.dashboard && (renderer!=='kpi'||s.items?.length<3||s.items?.length>6||!s.dashboard.unit?.trim()||!s.dashboard.labels?.length||s.dashboard.labels.length>12||!s.dashboard.series?.length||s.dashboard.series.some(x=>x.values?.length!==s.dashboard.labels.length||x.values.some(v=>typeof v!=='number'||!Number.isFinite(v)))))fail('dashboard requires 3–6 KPIs, unit, at most 12 labels and matching finite series');
      if(renderer==='evidence' && !(s.quote||s.evidenceText||s.body)) fail('quote/evidenceText/body is required');
      if(renderer==='comparison') {
        if(!s.columns?.length || s.columns.length>4) fail('comparison requires 1–4 columns');
        else s.columns.forEach(c=>{if(!Array.isArray(c.points)||c.points.length>6) fail('each column requires points (at most 6)');});
        if(s.composition==='compare-2'&&s.columns?.length!==2) fail('compare-2 requires exactly two columns');
      }
      if(renderer==='hierarchy') {
        if(!(s.root||s.center||s.statement)) fail('root/center/statement is required');
        if(items?.some(it=>(it.children||[]).length>3)) fail('at most 3 children per branch');
      }
      if(renderer==='chart') {
        if(!s.series?.length) fail('nonempty series are required');
        for(const series of s.series||[]) {
          const labels=series.labels||s.labels;
          if(!labels?.length||labels.length!==series.values.length) fail('labels and values must have matching lengths');
          if(series.values.some(v=>typeof v!=='number'||!Number.isFinite(v))) fail('values must be finite numbers');
          if(s.series[0]!==series && JSON.stringify(labels)!==JSON.stringify(s.series[0].labels||s.labels)) fail('all series must use identical category labels');
        }
        if(s.highlightIndex!=null && s.highlightIndex>=s.series?.[0]?.values.length) fail('highlightIndex is outside the data');
        if(s.axisMin!=null && !['line','trend','cohort'].includes(s.semanticType) && s.axisMin>0) fail('bar/area axes must include zero');
        if(s.axisMin!=null && s.series?.some(x=>x.values.some(v=>v<s.axisMin))) fail('axisMin would hide data');
        if(['pie','doughnut'].includes(s.chartType) && (s.series?.length!==1 || s.series[0].values.some(v=>v<0))) fail('pie/doughnut requires one nonnegative series');
      }
      if(renderer==='table') {
        if(!s.headers?.length||!s.rows?.length) fail('headers and rows are required');
        else if(s.headers.length>9||s.rows.length>8||s.rows.some(r=>!Array.isArray(r)||r.length!==s.headers.length)) fail('table requires rectangular rows; capacity is 9 columns × 8 rows (split larger tables explicitly)');
        if(s.columnWidths && (s.columnWidths.length!==s.headers.length || s.columnWidths.some(v=>!Number.isFinite(v)||v<=0) || Math.abs(s.columnWidths.reduce((a,b)=>a+b,0)-1)>.001)) fail('columnWidths must be positive fractions summing to 1');
      }
      if(renderer==='matrix' && items?.some(it=>![it.x,it.y].every(v=>typeof v==='number'&&v>=0&&v<=1))) fail('matrix items require explicit x and y values between 0 and 1');
      if(renderer==='funnel') {
        const vals=(items||[]).map(it=>Number(String(it.value).replaceAll(',','').replace(/%$/, '')));
        if(vals.some(v=>!Number.isFinite(v)||v<=0)) fail('funnel values must be positive numeric counts');
        if(vals.some((v,j)=>j&&v>vals[j-1])) fail('funnel counts must not increase between stages');
      }
      if(renderer==='roadmap') {
        const lanes=s.lanes||s.items;
        if(!lanes?.length||lanes.length>5||lanes.some(l=>!(l.phases||l.items)?.length || (l.phases||l.items).length>5)) fail('roadmap requires 1–5 lanes with 1–5 phases each');
      }
      if(renderer==='architecture') {
        const layers=s.layers||[{items:s.items||s.nodes}];
        if(!layers.length||layers.length>5||layers.some(l=>!l.items?.length||l.items.length>5)) fail('architecture requires 1–5 layers with 1–5 items each');
      }
      if(renderer==='multimodal') {
        const ids=s.asset_ids||[];
        for(const id of [...ids,...(s.panels||[]).filter(p=>p.kind==='image').map(p=>p.asset_id)])if(!assets.has(id))fail('Unknown asset '+id);
        if(!ids.length&&!s.panels?.length)fail('Multimodal slide requires asset_ids or panels');
        if(s.composition==='multimodal-hero'&&ids.length!==1)fail('Hero requires exactly one asset');
        if(s.composition==='multimodal-annotated'&&(ids.length!==1||!s.annotations?.length))fail('Document evidence requires one asset and annotations');
        if(s.composition==='multimodal-split'&&!s.panels&&(!s.insight&&!s.body||ids.length>3))fail('Split requires insight/body and at most three assets');
        if(s.type==='image-comparison'&&ids.length!==2)fail('Image comparison requires two assets');
        if(s.panels&&new Set(s.panels.map(p=>p.id)).size!==s.panels.length)fail('Panel IDs must be unique');
        for(const a of s.annotations||[])checkRegion(a.source_region,`slides[${i}].annotation`);
        for(const p of s.panels||[]) {
          if(p.kind==='text'&&!p.text?.trim())fail('Text panel requires text');
          if(p.kind==='text'&&p.provenance&&p.provenance.render_mode!=='editable')fail('Noneditable image/OCR text belongs in asset provenance, not a native text panel');
          if(p.provenance?.source_asset&&!assets.has(p.provenance.source_asset))fail('Unknown source_asset');
          checkRegion(p.provenance?.source_region,`slides[${i}].panel`);
          if(p.kind==='table'&&(!p.headers?.length||p.headers.length>6||!p.rows?.length||p.rows.length>6||p.rows.some(r=>!Array.isArray(r)||r.length!==p.headers.length)))fail('Half-page table requires rectangular data within 6 × 6; split larger evidence');
          if(p.kind==='chart'&&(!p.series?.length||p.series.some(x=>!(x.labels||p.labels)?.length||x.values?.length!==(x.labels||p.labels).length||x.values.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0))))fail('Panel chart requires matching labels and nonnegative finite values');
          if(p.kind==='chart'&&p.chartType&&!['bar','column','line'].includes(p.chartType))fail('Panel chart supports bar, column and line only');
        }
      }
    } catch(e) {fail(e.message);}
  });
  return errors;
}
function assertDeck(spec) {const errors=validateDeck(spec);if(errors.length) throw new Error(errors.join('\n'));}
module.exports={validateDeck,assertDeck,schemaErrors};
if(require.main===module) {
  try {const spec=JSON.parse(fs.readFileSync(process.argv[2]||0,'utf8'));const errors=validateDeck(spec);console.log(JSON.stringify({errors}));process.exitCode=errors.length?2:0;}
  catch(e) {console.log(JSON.stringify({errors:[e.message]}));process.exitCode=2;}
}
