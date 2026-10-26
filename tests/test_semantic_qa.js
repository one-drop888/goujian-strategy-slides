'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('fs'),path=require('path'),os=require('os'),crypto=require('crypto');
const {spawnSync}=require('child_process');
const JSZip=require('jszip');
const ROOT=path.resolve(__dirname,'..');
const {buildDeck}=require('../core/renderer');
const {runSemanticQa}=require('../core/qa/semantic');
const CLI=path.join(ROOT,'skill','scripts','semantic_qa.js');

function tmpdir() { return fs.mkdtempSync(path.join(os.tmpdir(),'gj-semqa-')); }
function sha256(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
async function build(spec,dir,name='deck.pptx') {
  const out=path.join(dir,name);
  await buildDeck(spec,out);
  return out;
}
async function runQa(dir,file,spec,{scene=true}={}) {
  let scenePath=null;
  if(scene) {
    scenePath=path.join(dir,'scene.json');
    fs.writeFileSync(scenePath,JSON.stringify({version:'1.3',status:'PASS',pptx_sha256:sha256(file),
      theme_decision:{selected_profile:'executive-clean'},visual_encoding:{plans:[{status:'PASS'}]}}));
  }
  return runSemanticQa({pptxPath:file,spec,repoRoot:ROOT,specDir:dir,scenePath});
}
async function mutate(source,target,edit) {
  const zip=await JSZip.loadAsync(fs.readFileSync(source));
  await edit(zip);
  fs.writeFileSync(target,await zip.generateAsync({type:'nodebuffer'}));
}
function chartParts(zip) {
  return Object.keys(zip.files).filter(name=>/^ppt\/charts\/chart\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/(\d+)/)[1])-Number(b.match(/(\d+)/)[1]));
}
async function editChart(zip,index,fn) {
  const name=chartParts(zip)[index];
  assert(name,`chart part ${index+1} is missing`);
  const xml=await zip.file(name).async('string');
  const next=fn(xml);
  assert.notEqual(next,xml,'expected the chart mutation to change native XML');
  zip.file(name,next);
}
async function editSlide(zip,index,fn) {
  const name=`ppt/slides/slide${index}.xml`;
  assert(zip.file(name),`${name} is missing`);
  const xml=await zip.file(name).async('string');
  const next=fn(xml);
  assert.notEqual(next,xml,'expected the slide mutation to change native XML');
  zip.file(name,next);
}
async function editWorkbook(zip,fn) {
  const name=Object.keys(zip.files).find(item=>/\.xlsx$/.test(item));
  assert(name,'embedded workbook is missing');
  const book=await JSZip.loadAsync(await zip.file(name).async('nodebuffer'));
  const sheet=Object.keys(book.files).find(item=>/^xl\/worksheets\/sheet\d+\.xml$/.test(item));
  assert(sheet,'embedded workbook worksheet is missing');
  const xml=await book.file(sheet).async('string');
  const next=fn(xml);
  assert.notEqual(next,xml,'expected the workbook mutation to change native XML');
  book.file(sheet,next);
  zip.file(name,await book.generateAsync({type:'nodebuffer'}));
}
function numCache(xml) {
  const match=xml.match(/<c:numCache>[\s\S]*?<\/c:numCache>/);
  assert(match,'chart value cache is missing');
  return match[0];
}
function replaceCachedValue(xml,from,to) {
  const cache=numCache(xml);
  const next=cache.replace(`<c:v>${from}</c:v>`,`<c:v>${to}</c:v>`);
  assert.notEqual(next,cache,`cached value ${from} was not present in the native value cache`);
  return xml.replace(cache,next);
}
function expectFailed(report,...names) {
  assert.equal(report.status,'FAIL',`expected aggregate FAIL, got ${report.status}: ${JSON.stringify(report.errors)}`);
  for(const name of names) assert.equal(report.checks[name].status,'FAIL',`${name} should fail: ${JSON.stringify(report.checks[name])}`);
}
function messages(report,name) { return (report.checks[name].errors||[]).join('\n'); }

const percentMetrics=[
  {id:'rate',name:'转化率',type:'percent',storage_scale:'fraction',raw_value:.08,comparison_basis:'period_over_period',display_unit:'%',precision:1,time_window:'2026 Q3'},
  {id:'target',name:'目标',type:'percent',storage_scale:'fraction',raw_value:.10,comparison_basis:'period_over_period',display_unit:'%',precision:1,time_window:'2026 Q3'},
];
function percentSpec() {
  return {title:'Semantic QA percent',metrics:percentMetrics,slides:[
    {type:'chart',chartType:'column',title:'转化率 {{metric:rate}} → {{metric:target}}',labels:['本期','目标'],
      visual_encoding:{label_strategy:'value'},series:[{id:'rate-series',name:'转化率',metric_ids:['rate','target']}]},
    {type:'kpi',title:'关键指标',items:[{label:'本期',value:'{{metric:rate}}'},{label:'目标',value:'{{metric:target}}'},{label:'样本量',value:'24 例'}],
      dashboard:{unit:'%',labels:['本期','目标'],series:[{name:'转化率',metric_ids:['rate','target']}]}},
    {type:'table',title:'明细',headers:['指标','本期','目标'],rows:[['本期','{{metric:rate}}','{{metric:target}}']]},
  ]};
}

test('typed bindings keep render scale, native cache and immutable source aligned',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Binding scale',metrics:[{id:'revenue',name:'收入',type:'currency',storage_scale:'unit',currency:'CNY',
    raw_value:12500000,precision:1,display_scale:{factor:10000,unit:'万'},time_window:'2026 Q3'}],slides:[
    {type:'chart',chartType:'column',title:'收入 {{metric:revenue}}',labels:['实际'],
      series:[{id:'r',name:'收入',metric_ids:['revenue'],values:[12500000]}],
      metric_bindings:[{metric_id:'revenue',pointer:'/series/0/values/0'}]}]};
  const before=JSON.stringify(spec),file=await build(spec,dir,'binding.pptx');
  const report=await runQa(dir,file,spec);
  assert.notEqual(report.status,'FAIL',JSON.stringify(report.errors));
  assert.equal(report.checks.NUMERIC_SEMANTIC_FIDELITY.status,'PASS');
  assert.equal(report.checks.NUMERIC_SEMANTIC_FIDELITY.bindings_checked,1);
  assert.equal(report.checks.NUMERIC_SEMANTIC_FIDELITY.render_factors,1);
  assert.equal(report.checks.NUMERIC_SEMANTIC_FIDELITY.source_spec_immutable,true);
  assert.deepEqual(report.charts[0].series[0].values,[1250]);
  assert.equal(report.checks.UNIT_CONSISTENCY.status,'PASS');
  assert.equal(JSON.stringify(spec),before,'semantic QA must not mutate the source spec');
});

test('native chart cache tampering fails even when the sidecar claims PASS',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Native tamper',slides:[{type:'chart',chartType:'column',title:'指标',labels:['本期','目标'],
    series:[{name:'转化率',labels:['本期','目标'],values:[8,10]}]}]};
  const file=await build(spec,dir),tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>replaceCachedValue(xml,8,7)));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'NUMERIC_SEMANTIC_FIDELITY');
  assert.match(messages(report,'NUMERIC_SEMANTIC_FIDELITY'),/does not match effective value 8/);
  assert.equal(report.checks.SIDECAR_BINDING.status,'PASS');
  assert.equal(report.pptx_sha256,sha256(tampered));
});

test('embedded workbook tampering is detected independently of the chart cache',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Workbook tamper',slides:[{type:'chart',chartType:'column',title:'指标',labels:['本期','目标'],
    series:[{name:'转化率',labels:['本期','目标'],values:[8,10]}]}]};
  const file=await build(spec,dir),tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editWorkbook(zip,xml=>xml.replace('<c r="B2"><v>8</v></c>','<c r="B2"><v>7</v></c>')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'NUMERIC_SEMANTIC_FIDELITY');
  assert.match(messages(report,'NUMERIC_SEMANTIC_FIDELITY'),/workbook series 1 cell 1/);
});

test('declared number formats are checked against native chart XML',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec=percentSpec(),file=await build(spec,dir),tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml.replace(/0\.0&quot;%&quot;/g,'0.##')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'UNIT_CONSISTENCY');
  assert.match(messages(report,'UNIT_CONSISTENCY'),/number format/);
});

test('dashboard unit text tampering fails unit consistency',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec=percentSpec(),file=await build(spec,dir),tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editSlide(zip,2,xml=>xml.replace('<a:t>%</a:t>','<a:t>share</a:t>')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'UNIT_CONSISTENCY');
  assert.match(messages(report,'UNIT_CONSISTENCY'),/dashboard unit "%" is missing/);
});

test('a percent-scale regression fails both numeric fidelity and percentage validation',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec=percentSpec(),file=await build(spec,dir),tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>replaceCachedValue(xml,8,0.8)));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'NUMERIC_SEMANTIC_FIDELITY','PERCENTAGE_SCALE_VALIDATION');
  assert.match(messages(report,'PERCENTAGE_SCALE_VALIDATION'),/percent-effective 8/);
});

test('a declared gap rendered as zero fails numeric fidelity',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Gap',slides:[{type:'chart',chartType:'line',title:'缺口',labels:['A','B','C'],missing_policy:'gap',
    series:[{name:'values',labels:['A','B','C'],values:[10,null,0]}]}]};
  const file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.NUMERIC_SEMANTIC_FIDELITY.status,'PASS');
  assert.equal(baseline.checks.NUMERIC_SEMANTIC_FIDELITY.gaps,1);
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml.replace('<c:v></c:v>','<c:v>0</c:v>')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'NUMERIC_SEMANTIC_FIDELITY');
  assert.match(messages(report,'NUMERIC_SEMANTIC_FIDELITY'),/does not preserve the declared gap/);
});

test('legend names are checked against declared series identity',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Legend',slides:[{type:'chart',chartType:'line',title:'两条序列',labels:['A','B'],
    series:[{name:'Series A',labels:['A','B'],values:[1,2]},{name:'Series B',labels:['A','B'],values:[2,3]}]}]};
  const file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.CHART_LEGEND_SERIES_MAPPING.status,'PASS');
  const renamed=path.join(dir,'renamed.pptx');
  await mutate(file,renamed,zip=>editChart(zip,0,xml=>xml.replace('Series B','Series X')));
  const renamedReport=await runQa(dir,renamed,spec);
  expectFailed(renamedReport,'CHART_LEGEND_SERIES_MAPPING');
  assert.match(messages(renamedReport,'CHART_LEGEND_SERIES_MAPPING'),/Series X/);
  const missing=path.join(dir,'missing-legend.pptx');
  await mutate(file,missing,zip=>editChart(zip,0,xml=>xml.replace(/<c:legend>[\s\S]*?<\/c:legend>/,'')));
  const missingReport=await runQa(dir,missing,spec);
  expectFailed(missingReport,'CHART_LEGEND_SERIES_MAPPING');
  assert.match(messages(missingReport,'CHART_LEGEND_SERIES_MAPPING'),/no native legend/);
});

test('percentage-point text cannot be relabelled as percent',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'pp',metrics:[{id:'gap',name:'差额',type:'pp',storage_scale:'percent',raw_value:2,
    comparison_basis:'period_over_period',display_unit:'pp',precision:1}],slides:[
    {type:'kpi',title:'差额',items:[{label:'差额',value:'{{metric:gap}}'}]},
    {type:'chart',chartType:'column',title:'差额 {{metric:gap}}',labels:['本期'],
      series:[{name:'差额',metric_ids:['gap'],values:[2]}]}]};
  const file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.PERCENT_POINT_VALIDATION.status,'PASS');
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editSlide(zip,1,xml=>xml.replace('<a:t>2.0pp</a:t>','<a:t>2.0%</a:t>')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'PERCENT_POINT_VALIDATION');
  assert.match(messages(report,'PERCENT_POINT_VALIDATION'),/is missing for pp metric gap/);
});

test('panel chart routes require their explicit unit caption and typed units PASS',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Panel',metrics:[percentMetrics[0]],slides:[
    {type:'image-evidence',title:'Panel route',panels:[{id:'p',kind:'chart',chartType:'column',
      series:[{name:'转化率',metric_ids:['rate'],labels:['本期'],values:[8]}]}]}]};
  const file=await build(spec,dir);
  const slug=path.join(dir,'subject');
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  const slide=await zip.file('ppt/slides/slide1.xml').async('string');
  assert.match(slide,/<a:t>%<\/a:t>/,'panel unit caption must be native text');
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.routes.length,1);
  assert.equal(baseline.routes[0].route,'panel');
  assert.equal(baseline.checks.NUMERIC_SEMANTIC_FIDELITY.status,'PASS');
  assert.equal(baseline.checks.UNIT_CONSISTENCY.status,'PASS');
  assert.equal(baseline.checks.UNIT_CONSISTENCY.units_checked,1);
  const captionTampered=slug+'-caption.pptx';
  await mutate(file,captionTampered,zip=>editSlide(zip,1,xml=>xml.replace('<a:t>%</a:t>','<a:t>percent</a:t>')));
  const captionReport=await runQa(dir,captionTampered,spec);
  expectFailed(captionReport,'UNIT_CONSISTENCY');
  assert.match(messages(captionReport,'UNIT_CONSISTENCY'),/panel unit caption/);
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>replaceCachedValue(xml,8,0.8)));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'NUMERIC_SEMANTIC_FIDELITY','PERCENTAGE_SCALE_VALIDATION');
});

test('legacy panel routes without a declared unit stay NOT_RUN for Agent context',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Legacy panel',slides:[{type:'image-evidence',title:'Panel route',panels:[
    {id:'p',kind:'chart',chartType:'column',series:[{name:'数量',labels:['本期'],values:[8]}]}]}]};
  const file=await build(spec,dir);
  const report=await runQa(dir,file,spec);
  assert.equal(report.checks.UNIT_CONSISTENCY.status,'NOT_RUN');
  assert.match(report.checks.UNIT_CONSISTENCY.reason,/Agent/);
});

test('line dash and marker must match the chosen encoding roles',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Roles',slides:[{type:'chart',chartType:'line',title:'实际与目标',labels:['Q1','Q2'],
    series:[{id:'a',name:'实际',labels:['Q1','Q2'],values:[1,2]},{id:'b',name:'目标',labels:['Q1','Q2'],values:[2,3]}],
    visual_encoding:{series:[{id:'b',role:'target'}]}}]};
  const file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.CHART_COLOR_SEMANTICS.status,'PASS');
  assert.equal(baseline.checks.CHART_COLOR_SEMANTICS.role_styles_checked,2);
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml
    .replace('<c:symbol val="square"/>','<c:symbol val="circle"/>')
    .replace('<a:prstDash val="dash"/>','<a:prstDash val="solid"/>')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'CHART_COLOR_SEMANTICS');
  assert.match(messages(report,'CHART_COLOR_SEMANTICS'),/marker circle does not match encoded square/);
  assert.match(messages(report,'CHART_COLOR_SEMANTICS'),/dash solid does not match encoded dash/);
});

test('the local semantic CLI rejects undeclared flags',()=>{
  const result=spawnSync(process.execPath,[CLI,'--pptx','x.pptx','--spec','x.json','--out','x.json','--network','evil'],{encoding:'utf8'});
  assert.equal(result.status,2);
  assert.match(result.stderr,/unsupported flag/);
});

test('tampering only axis or only labels cannot hide behind another matching format',async(t)=>{
 const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));const spec=percentSpec(),file=await build(spec,dir);
 for(const tag of ['valAx','dLbls']) {const changed=path.join(dir,tag+'.pptx');await mutate(file,changed,zip=>editChart(zip,0,xml=>xml.replace(new RegExp('<c:'+tag+'[ >][\\s\\S]*?</c:'+tag+'>'),block=>block.replace(/0\.0&quot;%&quot;/g,'0.##'))));const report=await runQa(dir,changed,spec);expectFailed(report,'UNIT_CONSISTENCY');}
});
test('semantic and Quality Gate CLI cannot overwrite inputs, including links and generated sidecars',async(t)=>{
 const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));const spec=percentSpec(),file=await build(spec,dir),input=path.join(dir,'spec.json');fs.writeFileSync(input,JSON.stringify(spec));const before=fs.readFileSync(input),pptxBefore=fs.readFileSync(file);
 const alias=path.join(dir,'alias.json');fs.linkSync(input,alias);
 for(const out of [input,alias,file,file+'.scene.json']) {const r=spawnSync(process.execPath,[CLI,'--pptx',file,'--spec',input,'--out',out],{encoding:'utf8'});assert.notEqual(r.status,0);}
 for(const out of [input,alias,file]) {const r=spawnSync('python3',[path.join(ROOT,'skill/scripts/quality_gate.py'),file,'--spec',input,'--out',out],{encoding:'utf8'});assert.notEqual(r.status,0);}
 // Derived semantic report names must also be guarded before any write.
 const qa=path.join(dir,'report.json'),derived=path.join(dir,'report.semantic-qa.json');fs.linkSync(input,derived);const r=spawnSync('python3',[path.join(ROOT,'skill/scripts/quality_gate.py'),file,'--spec',input,'--out',qa],{encoding:'utf8'});assert.notEqual(r.status,0);assert(!fs.existsSync(qa));assert.deepEqual(fs.readFileSync(input),before);assert.deepEqual(fs.readFileSync(file),pptxBefore);
});

function twoPointSpec() {
  return {title:'Native geometry',slides:[{type:'chart',chartType:'column',title:'本期收入比较',unit:'万元',
    labels:['华南','华北'],series:[{name:'实际',labels:['华南','华北'],values:[10,20]}]}]};
}
function mutateValueCache(xml,change) {
  const cache=numCache(xml);
  const next=change(cache);
  assert.notEqual(next,cache,'mutation did not apply inside the native value cache');
  return xml.replace(cache,next);
}

test('native chart family must match the declared chart type',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec=twoPointSpec(),file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.CHART_TYPE_FIDELITY.status,'PASS');
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml.replaceAll('c:barChart','c:lineChart')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'CHART_TYPE_FIDELITY');
  assert.match(messages(report,'CHART_TYPE_FIDELITY'),/native chart family "line" does not match declared column/);
});

test('clipped native axis fails axis integrity even when points still match',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec=twoPointSpec(),file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.CHART_AXIS_INTEGRITY.status,'PASS');
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml.replace(/<c:min val="[^"]*"\/>/,'<c:min val="1000"/>')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'CHART_AXIS_INTEGRITY');
  assert.match(messages(report,'CHART_AXIS_INTEGRITY'),/does not match required baseline 0/);
  assert.match(messages(report,'CHART_AXIS_INTEGRITY'),/hides value 10/);
});

test('negative column axes must reserve headroom below the minimum instead of touching it',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Negative axis',slides:[{type:'chart',chartType:'column',title:'净变化',unit:'万元',
    labels:['一季度','二季度','三季度','四季度'],
    series:[{name:'净变化',labels:['一季度','二季度','三季度','四季度'],values:[-20,0,10,-5]}]}]};
  const file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.CHART_AXIS_INTEGRITY.status,'PASS',JSON.stringify(baseline.checks.CHART_AXIS_INTEGRITY));
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml.replace(/<c:min val="[^"]*"\/>/,'<c:min val="-20"/>')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'CHART_AXIS_INTEGRITY');
  assert.match(messages(report,'CHART_AXIS_INTEGRITY'),/does not reserve headroom below negative extreme -20/);
});

test('declared line axis bounds must exist natively',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec={title:'Line axis',slides:[{type:'line',chartType:'line',title:'达成率',unit:'%',
    axisMin:80,axis_note:'纵轴从 80% 起，差异需结合绝对水平解读',labels:['Q1','Q2'],
    series:[{name:'达成率',labels:['Q1','Q2'],values:[82,88]}]}]};
  const file=await build(spec,dir);
  const baseline=await runQa(dir,file,spec);
  assert.equal(baseline.checks.CHART_AXIS_INTEGRITY.status,'PASS');
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml.replace(/<c:min val="[^"]*"\/>/,'')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'CHART_AXIS_INTEGRITY');
  assert.match(messages(report,'CHART_AXIS_INTEGRITY'),/declares axisMin 80 but native value axis has no minimum/);
});

test('every declared series and category requires its native paint',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec=twoPointSpec(),file=await build(spec,dir);
  const tampered=path.join(dir,'tampered.pptx');
  await mutate(file,tampered,zip=>editChart(zip,0,xml=>xml.replace(/<a:solidFill>[\s\S]*?<\/a:solidFill>/g,'')));
  const report=await runQa(dir,tampered,spec);
  expectFailed(report,'CHART_COLOR_SEMANTICS');
  assert.match(messages(report,'CHART_COLOR_SEMANTICS'),/missing its expected native point paint/);
});

test('native point counts and indexes are bounded and validated',async(t)=>{
  const dir=tmpdir();t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const spec=twoPointSpec(),file=await build(spec,dir);
  const cases=[
    ['huge ptCount',cache=>cache.replace(/<c:ptCount[^>]*>/,'<c:ptCount val="999999999"/>'),/exceeds the bounded maximum/],
    ['negative ptCount',cache=>cache.replace(/<c:ptCount[^>]*>/,'<c:ptCount val="-1"/>'),/not a nonnegative integer/],
    ['fractional ptCount',cache=>cache.replace(/<c:ptCount[^>]*>/,'<c:ptCount val="2.5"/>'),/not a nonnegative integer/],
    ['duplicate index',cache=>cache.replace('<c:pt idx="1"','<c:pt idx="0"'),/is duplicated/],
    ['out-of-range index',cache=>cache.replace('<c:pt idx="1"','<c:pt idx="5"'),/outside declared ptCount/],
  ];
  for(const [name,change,pattern] of cases) {
    const tampered=path.join(dir,`${name.replace(/\s+/g,'-')}.pptx`);
    await mutate(file,tampered,zip=>editChart(zip,0,xml=>mutateValueCache(xml,change)));
    const report=await runQa(dir,tampered,spec);
    expectFailed(report,'NUMERIC_SEMANTIC_FIDELITY');
    assert.match(messages(report,'NUMERIC_SEMANTIC_FIDELITY'),pattern,`${name} should be rejected with a bounded structure error`);
  }
});
