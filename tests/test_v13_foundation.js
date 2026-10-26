const {test,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('fs'),path=require('path'),os=require('os');
const JSZip=require('jszip');
const {validateMetric,formatMetric}=require('../core/semantics/numeric');
const {validatePlan}=require('../core/reasoning/validate-plan');
const {compilePlan}=require('../core/reasoning/compile');
const {verifyBuiltDeck}=require('../core/reasoning/verify');
const {buildDeck}=require('../core/renderer');
const {validateDeck}=require('../core/schema/validate');
const {resolveStyle}=require('../core/style/resolve-style');
const {loadProfile}=require('../core/style/profile-loader');
const root=path.resolve(__dirname,'..');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'goujian-v13-foundation-'));
after(()=>fs.rmSync(temp,{recursive:true,force:true}));
let sequence=0;
const output=name=>path.join(temp,`${++sequence}-${name}.pptx`);
const clone=value=>structuredClone(value);

function blocks(xml,tag) {
  return [...xml.matchAll(new RegExp(`<c:${tag}[ >][\\s\\S]*?</c:${tag}>`,'g'))].map(match=>match[0]);
}
function block(xml,tag) { return blocks(xml,tag)[0]||''; }
function numbers(xml,tag) {
  const values=[];
  for(const inner of blocks(xml,tag))
    for(const match of inner.matchAll(/<c:v>([^<]*)<\/c:v>/g)) {
      const text=match[1].trim();
      values.push(text===''?null:Number(text));
    }
  return values;
}
function categories(xml) {
  return [...block(xml,'cat').matchAll(/<c:v>([^<]*)<\/c:v>/g)].map(match=>match[1]);
}
function seriesName(seriesXml) {
  const tx=block(seriesXml,'tx');
  return tx?[...tx.matchAll(/<c:v>([^<]*)<\/c:v>/g)].map(match=>match[1])[0]:null;
}
function seriesPaint(seriesXml) {
  const sp=block(seriesXml,'spPr');
  return (sp.match(/<a:srgbClr val="([0-9A-Fa-f]{6})"\/>/)||[])[1]?.toUpperCase()||null;
}
async function charts(file) {
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  const names=Object.keys(zip.files).filter(name=>/^ppt\/charts\/chart\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/(\d+)/)[1])-Number(b.match(/(\d+)/)[1]));
  return Promise.all(names.map(async name=>({name,xml:await zip.file(name).async('string')})));
}
async function workbookValues(file,chart,seriesIndex=0,count=3) {
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  const rels=await zip.file(`ppt/charts/_rels/${chart.split('/').pop()}.rels`).async('string');
  const target=(rels.match(/Target="\.\.\/embeddings\/([^"]+)"/)||[])[1];
  const book=await JSZip.loadAsync(await zip.file(`ppt/embeddings/${target}`).async('nodebuffer'));
  const sheet=await book.file('xl/worksheets/sheet1.xml').async('string');
  const column=String.fromCharCode(66+seriesIndex),values=[];
  for(let row=2;row<2+count;row++) {
    const cell=(sheet.match(new RegExp(`<c r="${column}${row}"[^>]*>([\\s\\S]*?)<\\/c>`))||[])[1]||'';
    const value=(cell.match(/<v>([^<]*)<\/v>/)||[])[1];
    values.push(value==null||value===''?null:Number(value));
  }
  return values;
}
async function slideXml(file,index) {
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  return zip.file(`ppt/slides/slide${index}.xml`).async('string');
}
function relTargets(xml) {
  const map={};
  for(const tag of xml.matchAll(/<Relationship\b[^>]*>/g)) {
    const attrs=Object.fromEntries([...tag[0].matchAll(/([\w]+)="([^"]*)"/g)].map(match=>[match[1],match[2]]));
    if(attrs.Id&&attrs.Target) map[attrs.Id]=attrs.Target;
  }
  return map;
}
async function chartTargets(file) {
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  const slides=Object.keys(zip.files).filter(name=>/^ppt\/slides\/slide\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/slide(\d+)\.xml$/)[1])-Number(b.match(/slide(\d+)\.xml$/)[1]));
  const found=[];
  for(const name of slides) {
    const slide=Number(name.match(/slide(\d+)\.xml$/)[1]);
    const xml=await zip.file(name).async('string');
    const ids=[...xml.matchAll(/<c:chart[^>]*r:id="([^"]+)"/g)].map(match=>match[1]);
    if(!ids.length) continue;
    const targets=relTargets(await zip.file(`ppt/slides/_rels/slide${slide}.xml.rels`).async('string'));
    for(const id of ids) {
      const target=String(targets[id]||'').replace(/^\//,'');
      found.push({slide,name:target,xml:await zip.file(target).async('string')});
    }
  }
  return found;
}
function tableRows(xml) {
  return [...xml.matchAll(/<a:tr[\s\S]*?<\/a:tr>/g)].map(row=>
    [...row[0].matchAll(/<a:tc>[\s\S]*?<\/a:tc>/g)].map(cell=>
      [...cell[0].matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>match[1]).join('')));
}

test('typed numeric contract keeps scientific, ratio, rounding and provenance explicit',()=>{
  const tiny=validateMetric({id:'tiny',type:'absolute',storage_scale:'unit',raw_value:1e-9,precision:2,display_notation:'scientific'});
  assert.equal(formatMetric(tiny).text,'1.00e-9');
  const ratio=validateMetric({id:'conv',type:'ratio',storage_scale:'fraction',raw_value:.092,denominator:1,display_unit:'%',precision:1});
  assert.equal(formatMetric(ratio).text,'9.2%');
  assert.throws(()=>validateMetric({id:'ambig',type:'ratio',storage_scale:'unit',raw_value:.092,denominator:1,display_unit:'%'}),/ambiguous/);
  const currency=validateMetric({id:'price',type:'currency',storage_scale:'unit',raw_value:2.675,currency:'CNY',precision:2});
  assert.equal(formatMetric(currency).text,'¥2.68');
  const negativeZero=validateMetric({id:'zero',type:'absolute',storage_scale:'unit',raw_value:-0,precision:2});
  assert.equal(formatMetric(negativeZero).text,'0.00');
  const zeroCurrency=validateMetric({id:'zero-cny',type:'currency',storage_scale:'unit',raw_value:-0,currency:'CNY',precision:2});
  assert.equal(formatMetric(zeroCurrency).text,'¥0.00');
  assert.throws(()=>formatMetric({...currency,normalized:true,effective_value:9999}),/unsupported metric fields/);
});

test('native charts keep stable role colors, dashDot, emphasis and honest legacy overflow',async()=>{
  const labels=['Q1','Q2','Q3'];
  const roleSeries=order=>order.map(id=>({id,name:id,labels,values:id==='a'?[1,2,3]:id==='t'?[2,2,2]:[0,1,2]}));
  const encoding={label_strategy:'value',series:[{id:'a',role:'actual'},{id:'t',role:'target'},{id:'h',role:'history'}]};
  const roleSlide=order=>({type:'chart',chartType:'line',title:'Stable roles',labels,visual_encoding:encoding,series:roleSeries(order)});
  const emphasisSlide={type:'chart',chartType:'line',title:'Emphasis',labels,
    visual_encoding:{series:[{id:'a',role:'actual'},{id:'t',role:'target',emphasis:true},{id:'h',role:'history'}]},
    series:roleSeries(['a','t','h'])};
  const categories4=['华南','华东','华北','西南'];
  const modernBar={type:'chart',chartType:'bar',title:'Categories',labels:categories4,
    series:[{id:'region',name:'成交率',labels:categories4,values:[14.2,13.8,11.6,10.9]}]};
  const defaultChart={type:'chart',title:'Default chart',labels,series:[
    {name:'one',labels,values:[1,2,3]},{name:'two',labels,values:[3,2,1]},{name:'three',labels,values:[2,2,2]}]};
  const distribution={type:'distribution',title:'Distribution',labels,series:[
    {name:'low',labels,values:[5,3,1]},{name:'high',labels,values:[1,3,5]}]};
  const legacyLabels=Array.from({length:12},(_,index)=>`C${index+1}`);
  const legacyBar={type:'chart',chartType:'bar',title:'Legacy twelve',labels:legacyLabels,highlightIndex:3,
    series:[{labels:legacyLabels,values:legacyLabels.map((_,index)=>index+1)}]};
  const spec={title:'Encoding',slides:[roleSlide(['a','t','h']),roleSlide(['h','a','t']),emphasisSlide,modernBar,defaultChart,distribution,legacyBar]};
  const built=await buildDeck(spec,output('encoding'));
  const style=resolveStyle(loadProfile('executive-clean',root));
  const files=await charts(built.outPath);
  assert.equal(files.length,7);
  const byName=xml=>Object.fromEntries([...xml.matchAll(/<c:ser[ >][\s\S]*?<\/c:ser>/g)].map(match=>[seriesName(match[0]),seriesPaint(match[0])]));
  const first=byName(files[0].xml),second=byName(files[1].xml);
  assert.deepEqual(first,second,'series colors stay stable when the same series are reordered');
  assert(Object.values(first).every(Boolean));
  assert.equal(new Set(Object.values(first)).size,3);
  assert.equal((files[0].xml.match(/<a:prstDash val="dashDot"\/>/g)||[]).length>=1,true);
  assert(files[0].xml.includes('<c:symbol val="triangle"/>'));
  assert(block(files[0].xml,'dLbls').includes('<c:showVal val="1"/>'));
  const allPointPositions=[...files[0].xml.matchAll(/<c:dLblPos val="([^"]+)"\/>/g)].map(match=>match[1]);
  assert.deepEqual(allPointPositions,['t','r','b'],'three-category role lines keep every value with per-series label positions');
  const emphasisColors=byName(files[2].xml);
  assert.equal(emphasisColors.t,style.tokens.chart.highlight.toUpperCase());
  assert.notEqual(emphasisColors.a,emphasisColors.t);
  assert(!files[3].xml.toUpperCase().includes(style.tokens.chart.highlight.toUpperCase()),'category chart without highlightIndex keeps no implicit protagonist');
  const scene=JSON.parse(fs.readFileSync(built.scene,'utf8'));
  assert.equal(scene.visual_encoding.plans[4].kind,'bar');
  assert.equal(scene.visual_encoding.plans[5].kind,'bar');
  assert.equal(scene.visual_encoding.plans[4].category_colors,false);
  assert.equal(scene.visual_encoding.plans[6].legacy_overflow,true);
  assert.equal(scene.visual_encoding.validation[6].status,'PASS');
  assert(scene.visual_encoding.validation[6].warnings.length>0);
  assert.equal(new Set(scene.visual_encoding.plans[6].colors).size,2);
  assert.equal(scene.visual_encoding.plans[6].colors.filter(color=>color===style.tokens.chart.highlight.toUpperCase()).length,1);
  assert.equal(categories(files[6].xml).length,12);

  const swapped=await buildDeck({...spec,slides:[spec.slides[1],spec.slides[0],...spec.slides.slice(2)]},output('encoding-swapped'));
  const swappedFiles=await charts(swapped.outPath);
  assert.deepEqual(byName(swappedFiles[0].xml),second);
  assert.deepEqual(byName(swappedFiles[1].xml),first);

  const perChart={title:'Per-chart capacity',slides:Array.from({length:3},(_,chart)=>({
    type:'chart',chartType:'line',title:`Chart ${chart+1}`,labels:['A','B'],
    series:[0,1,2].map(offset=>{const id=`s${chart*3+offset+1}`;return {id,name:id,labels:['A','B'],values:[chart+offset,chart+offset+1]};})
  }))};
  const capacity=await buildDeck(perChart,output('capacity'));
  const capacityScene=JSON.parse(fs.readFileSync(capacity.scene,'utf8'));
  assert.equal(capacityScene.visual_encoding.plans.length,3);
  for(const plan of capacityScene.visual_encoding.plans) assert.equal(new Set(plan.series.map(series=>series.color)).size,3);
  assert(capacityScene.visual_encoding.series_palette.length<9);
});

test('target defaults to a warm paint and history to neutral unless the user pins a color',async()=>{
  const labels=['1月','2月','3月','4月','5月','6月'];
  const series=[
    {id:'actual',name:'实际',role:'actual',labels,values:[42,45,44,48,51,55]},
    {id:'target',name:'目标',role:'target',labels,values:[45,46,47,49,50,52]},
    {id:'history',name:'去年同期',role:'history',labels,values:[38,40,41,43,45,47]},
  ];
  const encoding={label_strategy:'value',series:[{id:'actual',role:'actual'},{id:'target',role:'target'},{id:'history',role:'history'}]};
  const built=await buildDeck({title:'Role paints',slides:[{type:'chart',chartType:'line',title:'实际、目标与去年同期',
    labels,visual_encoding:encoding,series}]},output('role-paints'));
  const plan=JSON.parse(fs.readFileSync(built.scene,'utf8')).visual_encoding.plans[0];
  const paint=id=>plan.series.find(item=>item.id===id).color;
  const rgb=color=>[0,2,4].map(offset=>parseInt(color.slice(offset,offset+2),16));
  const targetRgb=rgb(paint('target'));
  assert(targetRgb[0]>targetRgb[2]+40,'target uses a warm paint rather than a blue sibling');
  const historyRgb=rgb(paint('history'));
  assert(Math.max(...historyRgb)-Math.min(...historyRgb)<30,'history uses a neutral paint');
  const pinned=structuredClone(series);
  pinned[1].style={color:'009E73'};
  const pinnedDeck=await buildDeck({title:'Pinned target',slides:[{type:'chart',chartType:'line',title:'明确目标色',
    labels,visual_encoding:encoding,series:pinned}]},output('pinned-target'));
  const pinnedPlan=JSON.parse(fs.readFileSync(pinnedDeck.scene,'utf8')).visual_encoding.plans[0];
  assert.equal(pinnedPlan.series.find(item=>item.id==='target').color,'009E73','explicit user color is never overridden');
});

test('dense role lines use non-overlapping end labels without dropping native values',async()=>{
  const labels=['1月','2月','3月','4月','5月','6月'];
  const series=[
    {id:'actual',name:'实际',labels,values:[42,45,44,48,51,55]},
    {id:'target',name:'目标',labels,values:[45,46,47,49,50,52]},
    {id:'history',name:'去年同期',labels,values:[38,40,41,43,45,47]},
  ];
  const built=await buildDeck({title:'Dense roles',slides:[{type:'chart',chartType:'line',title:'实际、目标与去年同期',
    labels,visual_encoding:{label_strategy:'value',series:[
      {id:'actual',role:'actual'},{id:'target',role:'target'},{id:'history',role:'history'}]},series}]},output('dense-roles'));
  const xml=(await charts(built.outPath))[0].xml;
  const points=[...xml.matchAll(/<c:dLbl>[\s\S]*?<\/c:dLbl>/g)].map(match=>match[0]);
  assert.equal(points.length,3,'one end label per series rather than overlapping labels at every month');
  for(const point of points) {
    assert.match(point,/<c:idx val="5"\/>/);
    assert.match(point,/<c:showVal val="1"\/>/);
    assert.match(point,/<c:numFmt formatCode="0\.##" sourceLinked="0"\/>/);
  }
  assert.deepEqual(points.map(point=>(point.match(/<c:dLblPos val="([^"]+)"\/>/)||[])[1]),['t','r','b']);
  assert.equal((xml.match(/<c:showVal val="1"\/>/g)||[]).length,3,'only the three end labels are enabled');
  assert.equal((xml.match(/<c:showVal val="0"\/>/g)||[]).length,4,'three series defaults plus the chart default stay explicit instead of silently disabling the label policy');
  assert.deepEqual(numbers(xml,'val'),[42,45,44,48,51,55,45,46,47,49,50,52,38,40,41,43,45,47],
    'native caches keep every monthly value for editing');
  assert.equal(new Set(points.map(point=>point.match(/<c:dLblPos val="([^"]+)"/)[1])).size,3);
});

test('missing values on chart, dashboard and panel routes use native gap and retain blank cache',async()=>{
  const spec={title:'Gap routes',slides:[
    {type:'chart',chartType:'line',title:'缺口',labels:['A','B','C'],missing_policy:'gap',
      series:[{name:'值',labels:['A','B','C'],values:[10,null,0]}]},
    {type:'kpi',title:'看板',missing_policy:'gap',items:[{label:'A',value:'1'},{label:'B',value:'2'},{label:'C',value:'3'}],
      dashboard:{unit:'%',labels:['A','B','C'],series:[{name:'趋势',values:[1,null,0]}]}},
    {type:'image-evidence',title:'面板',missing_policy:'gap',panels:[
      {id:'panel-gap',kind:'chart',chartType:'bar',labels:['A','B','C'],
        series:[{name:'值',labels:['A','B','C'],values:[2,null,0]}]}]},
  ]};
  const built=await buildDeck(spec,output('gap-routes'));
  const files=await charts(built.outPath);
  assert.equal(files.length,3);
  for(const [index,file] of files.entries()) {
    assert.match(file.xml,/<c:dispBlanksAs val="gap"\/>/,`route ${index+1} writes native gap`);
    assert.doesNotMatch(file.xml,/<c:dispBlanksAs val="span"\/>/);
    assert.equal((file.xml.match(/<c:v><\/c:v>/g)||[]).length,1,`route ${index+1} keeps the missing cache blank`);
    assert(file.xml.includes('<c:v>0</c:v>'),`route ${index+1} keeps an explicit zero distinct from missing`);
  }
  assert.deepEqual(numbers(files[0].xml,'val'),[10,null,0]);
  assert.deepEqual(numbers(files[1].xml,'val'),[1,null,0]);
  assert.deepEqual(numbers(files[2].xml,'val'),[2,null,0]);
  assert.deepEqual(await workbookValues(built.outPath,files[0].name),[10,null,0],'route 1 workbook keeps blank separate from zero');
  assert.deepEqual(await workbookValues(built.outPath,files[1].name),[1,null,0],'route 2 workbook keeps blank separate from zero');
  assert.deepEqual(await workbookValues(built.outPath,files[2].name),[2,null,0],'route 3 workbook keeps blank separate from zero');
});

test('area charts reject missing values instead of faking a gap, while line gaps and explicit zero remain',async()=>{
  const labels=['A','B','C','D'];
  const areaMissing=/area charts cannot render missing values honestly[\s\S]*line chart[\s\S]*table/;
  const root={type:'chart',chartType:'area',title:'Area gap',labels,missing_policy:'gap',
    series:[{name:'值',labels,values:[10,null,0,6]}]};
  assert(validateDeck({title:'Area gap',slides:[root]}).some(message=>areaMissing.test(message)),
    'legacy validation reports the area limitation before rendering');
  await assert.rejects(buildDeck({title:'Area gap',slides:[root]},output('area-missing-root')),areaMissing);
  await assert.rejects(buildDeck({title:'Area type gap',slides:[{type:'area',title:'Area type gap',labels,missing_policy:'gap',
    series:[{name:'值',labels,values:[10,null,0,6]}]}]},output('area-missing-type')),areaMissing);
  await assert.rejects(buildDeck({title:'Area panel gap',slides:[{type:'image-evidence',title:'Panel gap',missing_policy:'gap',panels:[
    {id:'panel-area',kind:'chart',chartType:'area',labels,series:[{name:'值',labels,values:[10,null,0,6]}]}]}]},
    output('area-missing-panel')),areaMissing);
  await assert.rejects(buildDeck({title:'Typed area gap',metrics:[
    {id:'missing',name:'缺失',type:'absolute',storage_scale:'unit',raw_value:null,missing_policy:'gap'}],
    slides:[{type:'chart',chartType:'area',title:'Typed area gap',labels:['A'],series:[
      {id:'value',name:'值',metric_ids:['missing']}]}]},output('area-missing-typed')),areaMissing);

  const areaZero=await buildDeck({title:'Area zero',slides:[{type:'chart',chartType:'area',title:'Area zero',labels,
    series:[{name:'值',labels,values:[10,0,6,2]}]}]},output('area-zero'));
  const areaZeroXml=(await charts(areaZero.outPath))[0].xml;
  assert.deepEqual(numbers(areaZeroXml,'val'),[10,0,6,2]);
  assert.doesNotMatch(areaZeroXml,/<c:dispBlanksAs val="gap"\/>/);

  const lineGap=await buildDeck({title:'Line gap',slides:[{type:'chart',chartType:'line',title:'Line gap',labels,missing_policy:'gap',
    series:[{name:'值',labels,values:[10,null,0,6]}]}]},output('line-gap-guard'));
  const lineGapXml=(await charts(lineGap.outPath))[0].xml;
  assert.match(lineGapXml,/<c:dispBlanksAs val="gap"\/>/);
  assert.deepEqual(numbers(lineGapXml,'val'),[10,null,0,6]);
});

test('single-point area series are rejected on every chart route with line, KPI and table guidance',async()=>{
  const areaSingle=/area charts require at least two points[\s\S]*line chart[\s\S]*KPI[\s\S]*table/;
  const root={type:'chart',chartType:'area',title:'Area single',labels:['本期'],series:[{name:'值',labels:['本期'],values:[120]}]};
  assert(validateDeck({title:'Area single',slides:[root]}).some(message=>areaSingle.test(message)),
    'legacy validation reports the single-point area limit before rendering');
  await assert.rejects(buildDeck({title:'Area single',slides:[root]},output('area-single-root')),areaSingle);
  await assert.rejects(buildDeck({title:'Area type single',slides:[{type:'area',title:'Area type single',labels:['本期'],
    series:[{name:'值',labels:['本期'],values:[120]}]}]},output('area-single-type')),areaSingle);
  await assert.rejects(buildDeck({title:'Area panel single',slides:[{type:'image-evidence',title:'Panel single',panels:[
    {id:'panel-area-single',kind:'chart',chartType:'area',labels:['本期'],series:[{name:'值',labels:['本期'],values:[120]}]}]}]},
    output('area-single-panel')),areaSingle);
  await assert.rejects(buildDeck({title:'Typed area single',metrics:[
    {id:'one',name:'单点',type:'absolute',storage_scale:'unit',raw_value:120}],
    slides:[{type:'chart',chartType:'area',title:'Typed area single',labels:['本期'],series:[
      {id:'value',name:'值',metric_ids:['one']}]}]},output('area-single-typed')),areaSingle);
  const lineSingle=await buildDeck({title:'Line single',slides:[{type:'chart',chartType:'line',title:'Line single',labels:['本期'],
    series:[{name:'值',labels:['本期'],values:[120]}]}]},output('line-single'));
  const lineSingleXml=(await charts(lineSingle.outPath))[0].xml;
  assert.deepEqual(numbers(lineSingleXml,'val'),[120]);
});

test('negative bar, column, area and panel axes reserve a clean minimum below the data without hiding values',async()=>{
  const labels=['一季度','二季度','三季度','四季度'];
  const values=[-20,0,10,-5];
  const slide=(chartType,extra)=>({type:'chart',chartType,title:`Negative ${chartType}`,labels,unit:'万元',
    series:[{name:'净变化',labels,values}],...extra});
  const spec={title:'Negative axes',slides:[
    slide('column'),slide('bar'),slide('area'),slide('column',{axisMin:-30}),
    {type:'image-evidence',title:'Negative panel',panels:[
      {id:'panel-negative',kind:'chart',chartType:'column',labels,numberFormat:'#,##0',
        series:[{name:'净变化',labels,values}]}]},
  ]};
  const built=await buildDeck(spec,output('negative-axes'));
  const files=await charts(built.outPath);
  assert.equal(files.length,5);
  for(const [index,file] of files.slice(0,3).entries()) {
    const axis=block(file.xml,'valAx');
    const min=Number((axis.match(/<c:min val="([^"]+)"\/>/)||[])[1]);
    assert.equal(min,-25,`caller ${index+1} snaps the 10% headroom to a clean -25 step boundary`);
    assert.deepEqual(numbers(file.xml,'val'),values,`caller ${index+1} keeps every actual value including zero and -20`);
    assert.match(block(file.xml,'catAx'),/<c:tickLblPos val="low"\/>/,'category labels remain outside negative bars');
    if(index<2) assert.match(block(file.xml,'dLbls'),/<c:showVal val="1"\/>/,`caller ${index+1} keeps value labels visible`);
  }
  const explicitMin=Number((block(files[3].xml,'valAx').match(/<c:min val="([^"]+)"\/>/)||[])[1]);
  assert.equal(explicitMin,-30,'a safe explicit axisMin is honored exactly');
  const panelMin=Number((block(files[4].xml,'valAx').match(/<c:min val="([^"]+)"\/>/)||[])[1]);
  assert.equal(panelMin,-25,'panel charts use the same clean native axis headroom');
  assert.deepEqual(numbers(files[4].xml,'val'),values);
});

test('value axis minima preserve tiny negatives, mixed signs and ordinary negatives with clean ticks',async()=>{
  const cases=[
    {id:'tiny',values:[-1e-9,2e-9],expected:-1.5e-9,numberFormat:'0.000000000'},
    {id:'tiny-zero',values:[-1e-12,0],expected:-1.2e-12,numberFormat:'0.000000000000'},
    {id:'mixed',values:[-20,35],expected:-30,numberFormat:'#,##0'},
    {id:'ordinary',values:[-20,0,10,-5],expected:-25,numberFormat:'#,##0'},
  ];
  for(const item of cases) {
    const built=await buildDeck({title:`Axis ${item.id}`,slides:[{type:'chart',chartType:'column',title:`Axis ${item.id}`,
      labels:item.values.map((_,index)=>String(index+1)),numberFormat:item.numberFormat,
      series:[{name:'值',values:item.values}]}]},output(`axis-${item.id}`));
    const xml=(await charts(built.outPath))[0].xml;
    const min=Number((block(xml,'valAx').match(/<c:min val="([^"]+)"\/>/)||[])[1]);
    assert.equal(min,item.expected,`${item.id} minimum is finite, below every value and snapped to a clean step`);
    assert(min<Math.min(...item.values),`${item.id} minimum preserves the smallest real value`);
    assert.deepEqual(numbers(xml,'val'),item.values,`${item.id} values are unchanged`);
  }
  const explicit=await buildDeck({title:'Axis explicit',slides:[{type:'chart',chartType:'column',title:'Explicit',
    labels:['A','B'],axisMin:-1e-9,series:[{name:'值',values:[-1e-9,2e-9]}]}]},output('axis-explicit'));
  const explicitMin=Number((block((await charts(explicit.outPath))[0].xml,'valAx').match(/<c:min val="([^"]+)"\/>/)||[])[1]);
  assert.equal(explicitMin,-1e-9,'a valid explicit axisMin is preserved exactly');

  await assert.rejects(buildDeck({title:'Axis overflow',slides:[{type:'chart',chartType:'column',title:'Overflow',
    labels:['A','B'],series:[{name:'值',values:[-1.7e308,1.7e308]}]}]},output('axis-overflow')),
    /too large to compute a finite value-axis minimum/);
});

test('explicit unsupported encoding fields are rejected instead of ignored',async()=>{
  const labels=['A','B'];
  const rejects=(spec,pattern)=>assert.rejects(buildDeck(spec,output('reject')),pattern);
  await rejects({title:'x',slides:[{type:'chart',chartType:'bar',title:'x',labels,series:[{id:'s',name:'s',labels,values:[1,2],emphasis:true}]}]},
    /category charts do not support series emphasis/);
  await rejects({title:'x',slides:[{type:'chart',chartType:'line',title:'x',labels,visual_encoding:{series:[
    {id:'a',role:'actual',emphasis:true},{id:'b',role:'target',emphasis:true}]},
    series:[{id:'a',name:'a',labels,values:[1,2]},{id:'b',name:'b',labels,values:[2,1]}]}]},/leave at least one series unemphasized/);
  await rejects({title:'x',slides:[{type:'chart',chartType:'bar',title:'x',
    labels:Array.from({length:9},(_,i)=>`C${i}`),series:[{id:'s',name:'s',labels:Array.from({length:9},(_,i)=>`C${i}`),values:Array.from({length:9},(_,i)=>i+1)}]}]},
    /category palette exceeds/);
  await rejects({title:'x',slides:[{type:'chart',chartType:'line',title:'x',labels,
    series:[{id:'a',name:'a',labels,values:[1,2],label_strategy:'value'},{id:'b',name:'b',labels,values:[2,1]}]}]},
    /per-series label_strategy is unsupported/);
  await rejects({title:'x',slides:[{type:'chart',chartType:'bar',title:'x',labels,
    visual_encoding:{label_strategy:'percent'},series:[{id:'s',name:'s',labels,values:[1,2]}]}]},
    /percent is only supported for pie\/doughnut/);
  await rejects({title:'x',slides:[{type:'chart',chartType:'line',title:'x',labels,
    visual_encoding:{series:[{id:'ghost',role:'actual'}]},
    series:[{id:'a',name:'a',labels,values:[1,2]}]}]},/does not match any series/);
  await rejects({title:'x',slides:[{type:'chart',chartType:'line',title:'x',labels,
    visual_encoding:{unknown_field:true},series:[{id:'a',name:'a',labels,values:[1,2]}]}]},
    /additional properties/);
  await rejects({title:'x',slides:[{type:'chart',chartType:'line',title:'x',labels,
    series:[{id:'a',name:'a',labels,values:[1,2],style:{dash:'wavy'}}]}]},/unsupported line dash/);
});

test('histogram aliases require contiguous equal-width bins and never fall back to area',async()=>{
  const equal=await buildDeck({title:'Histogram',slides:[{type:'histogram',title:'Equal bins',
    bins:[{start:0,end:10,count:3},{start:10,end:20,count:5}]}]},output('histogram'));
  const xml=(await charts(equal.outPath))[0].xml;
  assert.deepEqual(categories(xml),['0–10','10–20']);
  assert.deepEqual(numbers(xml,'val'),[3,5]);
  await assert.rejects(buildDeck({title:'Histogram',slides:[{type:'histogram',title:'Unequal',
    bins:[{start:0,end:10,count:3},{start:10,end:25,count:5}]}]},output('histogram-unequal')),/equal widths/);
  await assert.rejects(buildDeck({title:'Histogram',slides:[{type:'histogram',chartType:'area',title:'Area',
    bins:[{start:0,end:10,count:3},{start:10,end:20,count:5}]}]},output('histogram-area')),/histogram bins require a column\/bar chart/);
  await assert.rejects(buildDeck({title:'Histogram',slides:[{type:'histogram',title:'No bins',
    labels:['A','B'],series:[{name:'s',labels:['A','B'],values:[1,2]}]}]},output('histogram-none')),/histogram requires explicit bins with numeric widths and counts/);
});

test('typed 8% to 10% example reconciles final text, cache, formats, kpi and table gap-vs-zero',async()=>{
  const metrics=[
    {id:'rate',name:'转化率',type:'percent',storage_scale:'fraction',raw_value:.08,comparison_basis:'period_over_period',display_unit:'%',precision:1},
    {id:'target',name:'目标',type:'percent',storage_scale:'fraction',raw_value:.10,comparison_basis:'period_over_period',display_unit:'%',precision:1},
    {id:'gap',name:'差额',type:'pp',storage_scale:'percent',raw_value:2,comparison_basis:'period_over_period',display_unit:'pp',precision:1},
  ];
  const spec={title:'Typed',metrics,slides:[
    {type:'chart',chartType:'column',title:'转化率 {{metric:rate}} → {{metric:target}}',labels:['本期','目标'],
      visual_encoding:{label_strategy:'value'},
      series:[{id:'rate',name:'转化率',metric_ids:['rate','target']}]},
    {type:'kpi',title:'关键指标',
      visual_encoding:{label_strategy:'value'},
      items:[{label:'本期',value:'{{metric:rate}}'},{label:'目标',value:'{{metric:target}}'},{label:'差额',value:'{{metric:gap}}'}],
      dashboard:{unit:'%',labels:['本期','目标'],series:[{name:'转化率',metric_ids:['rate','target']}]}},
    {type:'table',title:'明细',headers:['指标','本期','目标'],
      rows:[['本期','{{metric:rate}}','{{metric:target}}'],['缺口',null,0]]},
    {type:'chart',chartType:'line',title:'Gap vs zero',labels:['A','B','C'],missing_policy:'gap',
      series:[{name:'values',labels:['A','B','C'],values:[10,null,0]}]},
  ]};
  const built=await buildDeck(spec,output('typed'));
  const files=await charts(built.outPath);
  assert.equal(files.length,3);
  assert.deepEqual(numbers(files[0].xml,'val'),[8,10]);
  assert(block(files[0].xml,'dLbls').includes('formatCode="0.0&quot;%&quot;"'));
  assert(block(files[0].xml,'valAx').includes('formatCode="0.0&quot;%&quot;"'));
  assert.deepEqual(numbers(files[1].xml,'val'),[8,10]);
  assert(block(files[1].xml,'dLbls').includes('<c:showVal val="1"/>'));
  assert(block(files[1].xml,'dLbls').includes('formatCode="0.0&quot;%&quot;"'));
  assert(block(files[1].xml,'valAx').includes('formatCode="0.0&quot;%&quot;"'));
  assert.deepEqual(numbers(files[2].xml,'val'),[10,null,0]);
  assert.match(files[2].xml,/<c:dispBlanksAs val="gap"\/>/,'missing policy is enforced in native chart XML');
  assert.doesNotMatch(files[2].xml,/<c:dispBlanksAs val="span"\/>/);
  assert((files[2].xml.match(/<c:v><\/c:v>/g)||[]).length>=1,'missing cache stays blank rather than zero');
  const title=await slideXml(built.outPath,1);
  assert([...title.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>match[1]).join(' ').includes('转化率 8.0% → 10.0%'));
  const kpi=await slideXml(built.outPath,2);
  const kpiText=[...kpi.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>match[1]).join(' ');
  assert(kpiText.includes('8.0%'));
  assert(kpiText.includes('10.0%'));
  assert(kpiText.includes('2.0pp'));
  const table=await slideXml(built.outPath,3);
  const rows=tableRows(table);
  assert.deepEqual(rows.find(row=>row[0]==='本期'),['本期','8.0%','10.0%']);
  assert.deepEqual(rows.find(row=>row[0]==='缺口'),['缺口','','0']);
});

test('native dashboard and panel charts map one-to-one through chart10 and chart11',async()=>{
  const slides=Array.from({length:8},(_,index)=>({type:'chart',chartType:'column',title:`Chart ${index+1}`,labels:['A','B'],
    series:[{name:`S${index+1}`,labels:['A','B'],values:[index+1,index+1.5]}]}));
  slides.push({type:'kpi',title:'Dashboard',items:[{label:'A',value:'1'},{label:'B',value:'2'},{label:'C',value:'3'}],
    dashboard:{unit:'指数',labels:['A','B'],series:[{name:'D1',values:[90,91]},{name:'D2',values:[80,82]}]}});
  slides.push({type:'image-evidence',title:'Panels',panels:[
    {id:'panel-bar',kind:'chart',chartType:'bar',labels:['A','B'],series:[{name:'P1',labels:['A','B'],values:[70,71]}]},
    {id:'panel-line',kind:'chart',chartType:'line',labels:['A','B'],series:[{name:'P2',labels:['A','B'],values:[60,61]}]},
  ]});
  await buildDeck({title:'Chart numbering warmup',slides:Array.from({length:9},(_,index)=>({
    type:'chart',chartType:'column',title:`W${index+1}`,labels:['A'],
    series:[{name:`W${index+1}`,labels:['A'],values:[index]}]}))},output('mapping-warmup'));
  const built=await buildDeck({title:'Mapping',slides},output('mapping'));
  const files=await charts(built.outPath);
  assert.equal(files.length,11);
  const chartNumbers=files.map(file=>Number(file.name.match(/chart(\d+)\.xml$/)[1]));
  assert(chartNumbers[0]>=10,'multi-digit chart parts exercise numeric rather than lexical ordering');
  assert.deepEqual(chartNumbers,[...chartNumbers].sort((a,b)=>a-b));
  assert.deepEqual(chartNumbers.slice(1),chartNumbers.slice(0,-1).map(number=>number+1));
  const scene=JSON.parse(fs.readFileSync(built.scene,'utf8'));
  assert.equal(scene.visual_encoding.plans.length,11);
  assert.deepEqual(scene.visual_encoding.plans.map(plan=>plan.container).slice(8),['dashboard','panel','panel']);
  assert.deepEqual(scene.visual_encoding.plans.map(plan=>plan.kind).slice(8),['line','bar','line']);
  const targets=await chartTargets(built.outPath);
  assert.deepEqual(targets.map(target=>target.slide),[1,2,3,4,5,6,7,8,9,10,10]);
  assert.deepEqual(targets.map(target=>target.name),files.map(file=>file.name),
    'slide-embedded chart relationships map one-to-one to native chart parts');
  assert.deepEqual(scene.visual_encoding.plans.map(plan=>plan.slide_index+1),[1,2,3,4,5,6,7,8,9,10,10]);
  const expected=[
    ...[1,2,3,4,5,6,7,8].map(index=>[index,index+.5]),
    [90,91,80,82],[70,71],[60,61],
  ];
  for(const [index,target] of targets.entries()) assert.deepEqual(numbers(target.xml,'val'),expected[index],`slide ${target.slide} ${target.name}`);
});

test('reasoning source hashes stay enforced and tampered output fails native verification',async()=>{
  const planPath=path.join(root,'skill/reasoning/fixtures/executive-incomplete-business/plan.json');
  const planDir=path.dirname(planPath);
  const plan=JSON.parse(fs.readFileSync(planPath,'utf8'));
  assert.equal(validatePlan(plan,{planDir,repoRoot:root}).valid,true);
  const tampered=clone(plan);
  tampered.sources[0]={...tampered.sources[0],sha256:'0'.repeat(64)};
  const result=validatePlan(tampered,{planDir,repoRoot:root});
  assert.equal(result.valid,false);
  assert.match(result.errors.join('\n'),/sha256 mismatch/);
  const built=await compilePlan(planPath,{out:output('reasoning')});
  const tamperedPath=path.join(temp,'tampered-output.pptx');
  fs.copyFileSync(built.outPath,tamperedPath);
  fs.appendFileSync(tamperedPath,Buffer.from('tamper'));
  await assert.rejects(verifyBuiltDeck(tamperedPath,{}, {expected_pptx_sha256:built.pptx_sha256},root),/does not match expected/);
});
