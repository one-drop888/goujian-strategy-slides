const {test}=require('node:test'),assert=require('node:assert/strict');
const {close,compensatedSum}=require('../core/reasoning/calculations'),{prepareDeckSemantics}=require('../core/semantics/deck');
test('raw fidelity retains tiny nonzero facts and one-unit differences at large magnitudes',()=>{
 assert(!close(0,1e-20));assert(!close(1e9,1e9+1));assert(!close(1e12,1e12+.01));
 assert(close(.1+.2,.3));assert(close(-0,0));assert(close(1e-20,1e-20*(1+Number.EPSILON)));
 assert(!close(NaN,NaN));assert(!close(Infinity,Infinity));
});
test('compensated summation reconciles long decimal runs without widening tolerance',()=>{
 const values=Array.from({length:1000},()=>0.1);
 assert(close(compensatedSum(values),100));
 assert(!close(values.reduce((total,value)=>total+value,0),100));
 assert.equal(compensatedSum([0.1,0.2,0.3]),compensatedSum([0.3,0.2,0.1]));
});
test('typed numeric bindings reject zero substituted for a scientific nonzero fact',()=>{
 const d={title:'tiny',metrics:[{id:'tiny',type:'absolute',storage_scale:'unit',raw_value:1e-10,display_notation:'scientific',precision:2}],slides:[{type:'kpi',title:'test',items:[{label:'tiny',value:0}],metric_bindings:[{metric_id:'tiny',pointer:'/items/0/value'}]}]};
 assert.throws(()=>prepareDeckSemantics(d),/does not match/);assert.equal(d.slides[0].items[0].value,0);
});

test('formatter preserves declared scales, halfExpand precision, negative zero and native scientific units',()=>{
 const {formatMetric,formatCodeForMetric,validateMetric}=require('../core/semantics/numeric');
 const metric=extra=>({id:'m',type:'absolute',storage_scale:'unit',raw_value:2.675,precision:2,...extra});
 assert.equal(formatMetric(metric()).text,'2.68');
 assert.equal(formatMetric(metric({raw_value:999999999999999.9,precision:1})).text,'999,999,999,999,999.9');
 assert.equal(formatMetric(metric({raw_value:-0})).text,'0.00');
 assert.equal(formatMetric(metric({raw_value:1e-20,display_notation:'scientific'})).text,'1.00e-20');
 assert.equal(formatCodeForMetric(metric({raw_value:1e-20,display_notation:'scientific'})),'0.00E+00');
 const currency=metric({type:'currency',currency:'CNY',raw_value:12500000,precision:1,display_scale:{factor:10000,unit:'万'}});
 assert.equal(formatMetric(currency).text,'¥1,250.0万');
 assert.throws(()=>formatMetric({...currency,display_scale:{factor:1000,unit:'万'}}),/requires factor/);
 assert.throws(()=>formatMetric(metric({raw_value:1e-320,display_notation:'scientific',display_scale:{factor:1e308,unit:'scaled'}})),/erase/);
 const frozen=validateMetric(currency);assert(Object.isFrozen(frozen));assert(Object.isFrozen(frozen.display_scale));
 for(const display_unit of ['x','倍','ratio']) {
  const m=metric({type:'ratio',denominator:1,display_unit});assert(formatMetric(m).text.endsWith(display_unit));assert(formatCodeForMetric(m).endsWith('"'+display_unit+'"'));
 }
});
test('native currency chart and workbook share an explicit 万 scale while KPI and table retain raw facts',async()=>{
 const fs=require('fs'),path=require('path'),os=require('os'),JSZip=require('jszip'),{buildDeck}=require('../core/renderer');
 const {tableRows,chartNumbers}=require('../core/reasoning/verify');
 const metrics=[12500000,10000000].map((raw_value,i)=>({id:'revenue'+i,type:'currency',storage_scale:'unit',currency:'CNY',raw_value,precision:1,display_scale:{factor:10000,unit:'万'},time_window:'2026 Q3'}));
 const spec={title:'收入仍需补齐目标差距',metrics,slides:[
  {type:'chart',chartType:'column',title:'实际{{metric:revenue0}}，目标{{metric:revenue1}}',labels:['实际','目标'],series:[{name:'收入',metric_ids:['revenue0','revenue1']}]},
  {type:'kpi',title:'核对收入',items:[{label:'实际',value:'{{metric:revenue0}}'},{label:'目标',value:'{{metric:revenue1}}'}]},
  {type:'table',title:'收入明细',headers:['指标','金额'],rows:[['实际','{{metric:revenue0}}'],['目标','{{metric:revenue1}}']]}
 ]};
 const before=JSON.stringify(spec),dir=fs.mkdtempSync(path.join(os.tmpdir(),'gj-currency-'));
 try {
  const file=path.join(dir,'万元.pptx'),b=await buildDeck(spec,file),zip=await JSZip.loadAsync(fs.readFileSync(file));
  assert.equal(JSON.stringify(spec),before);assert.deepEqual(b.effective_spec.slides[0].series[0].values,[1250,1000]);
  assert(b.metric_semantics?.transformations?.some(t=>t.kind==='display-scale')||JSON.parse(fs.readFileSync(file+'.scene.json')).metric_semantics?.transformations?.some(t=>t.kind==='display-scale'));
  const chart=Object.keys(zip.files).find(n=>/^ppt\/charts\/chart\d+\.xml$/.test(n)),xml=await zip.file(chart).async('string');assert.deepEqual(chartNumbers(xml),[1250,1000]);assert(xml.includes('万'));assert(xml.includes('¥'));
  const rels=await zip.file('ppt/charts/_rels/'+path.basename(chart)+'.rels').async('string');const target=rels.match(/Target="([^"]*embeddings[^"]*)"/)[1];const book=await JSZip.loadAsync(await zip.file(path.posix.normalize(path.posix.join('ppt/charts',target))).async('nodebuffer'));
  const sheet=await book.file('xl/worksheets/sheet1.xml').async('string');assert.match(sheet,/<c r="B2"[^>]*>[\s\S]*?<v>1250<\/v>/);assert.match(sheet,/<c r="B3"[^>]*>[\s\S]*?<v>1000<\/v>/);
  const text=await zip.file('ppt/slides/slide2.xml').async('string');assert(text.includes('¥1,250.0万'));assert(text.includes('¥1,000.0万'));
  const table=tableRows(await zip.file('ppt/slides/slide3.xml').async('string'));assert.deepEqual(table[0],[['指标','金额'],['实际','¥1,250.0万'],['目标','¥1,000.0万']]);
  const again=await buildDeck(spec,path.join(dir,'again.pptx'));assert.deepEqual(again.effective_spec.slides[0].series[0].values,[1250,1000]);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});

test('explicit series identity is independent of array order and unsupported value encodings fail honestly',async()=>{
 const {createEncoding}=require('../core/renderer/encoding'),{resolveStyle}=require('../core/style/resolve-style'),{loadProfile}=require('../core/style/profile-loader');const style=resolveStyle(loadProfile('executive-clean',require('path').resolve(__dirname,'..')));
 const series=[{id:'north',name:'华北',values:[1,2]},{id:'south',name:'华南',values:[3,4]},{id:'west',name:'西部',values:[2,3]}];
 const make=xs=>({title:'x',slides:[{type:'chart',chartType:'line',title:'比较',labels:['A','B'],series:xs}]});
 const colors=xs=>Object.fromEntries(createEncoding(make(xs),style).chartPlansForSpec()[0].series.map(s=>[s.id,s.color]));assert.deepEqual(colors(series),colors([...series].reverse()));
 const bad=make(series.slice(0,1));bad.slides[0].visual_encoding={palette_type:'sequential',domain:{min:0,max:5}};assert.throws(()=>createEncoding(bad,style).chartPlansForSpec(),/supported on bar\/column/);
 const semantic=make(series.slice(0,1));semantic.slides[0].chartType='column';semantic.slides[0].visual_encoding={palette_type:'semantic'};assert.throws(()=>createEncoding(semantic,style).chartPlansForSpec(),/requires explicit/);
 for(const palette_type of ['sequential','diverging']) {
  const d={title:'x',slides:[{type:'chart',chartType:'column',title:'值编码',labels:['A','B','C','D','E'],series:[{id:'v',name:'量',values:[1,2,3,4,5]}],visual_encoding:{palette_type,domain:{min:0,max:6},...(palette_type==='diverging'?{center:3}:{})}}]};
  const plan=createEncoding(d,style).chartPlansForSpec()[0],{validateChartPlan}=require('../core/renderer/encoding');assert.equal(plan.colors.length,5);assert.equal(validateChartPlan(plan,{background:style.background}).status,'PASS');
 }
});

test('pie share labels use an actual percent format while value labels preserve typed percent points',async()=>{
 const {buildDeck}=require('../core/renderer'),fs=require('fs'),path=require('path'),os=require('os'),JSZip=require('jszip');const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gj-pie-scale-'));
 try {const spec={title:'份额',slides:['percent','value'].map(label_strategy=>({type:'chart',chartType:'doughnut',title:'直营占60%',labels:['直营','渠道'],unit:'%',numberFormat:'0.0"%"',visual_encoding:{label_strategy},series:[{name:'份额',values:[60,40]}]}))};
 const file=path.join(dir,'deck.pptx');await buildDeck(spec,file);const z=await JSZip.loadAsync(fs.readFileSync(file));const names=Object.keys(z.files).filter(n=>/^ppt\/charts\/chart\d+\.xml$/.test(n)).sort((a,b)=>Number(a.match(/chart(\d+)/)[1])-Number(b.match(/chart(\d+)/)[1]));
 const share=await z.file(names[0]).async('string'),value=await z.file(names[1]).async('string');assert(share.includes('formatCode="0.0%"'));assert(value.includes('formatCode="0.0&amp;quot;%&amp;quot;"')||value.includes('formatCode="0.0&quot;%&quot;"'));assert(share.includes('<c:showPercent val="1"/>'));assert(value.includes('<c:showPercent val="0"/>'));
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});

test('standalone schema QA validates typed points and accepts derived pie/panel values',()=>{
 const {validateDeck}=require('../core/schema/validate');const metrics=[{id:'a',type:'count',storage_scale:'unit',raw_value:60},{id:'b',type:'count',storage_scale:'unit',raw_value:40}];const slides=[{type:'chart',chartType:'pie',title:'构成',labels:['A','B'],series:[{name:'量',metric_ids:['a','b']}]},{type:'image-evidence',title:'证据',panels:[{id:'p',kind:'chart',chartType:'bar',labels:['A','B'],series:[{name:'量',metric_ids:['a','b']}]}]}];assert.deepEqual(validateDeck({title:'x',metrics,slides}),[]);
 const bad={title:'x',metrics:[{id:'p',type:'percent',storage_scale:'unit',raw_value:.1,comparison_basis:'part_of_whole'}],slides:slides.slice(0,1)};assert(validateDeck(bad).length);
 const pp={title:'x',slides:[{type:'chart',chartType:'column',title:'差异',series:[{name:'差异',storage_scale:'fraction',display_unit:'pp',labels:['A','B'],values:[.02,.03]}]}]};const prepared=prepareDeckSemantics(pp).spec;assert.equal(prepared.slides[0].numberFormat,'0.0"pp"');assert.equal(prepared.slides[0].unit,'pp');
});

test('independent conversion rates cannot masquerade as a complete pie composition',()=>{
 const {validateDeck}=require('../core/schema/validate');const d={title:'rate',metrics:[{id:'rate',type:'percent',storage_scale:'fraction',raw_value:.092,comparison_basis:'part_of_whole'}],slides:[{type:'chart',chartType:'pie',title:'转化率9.2%',labels:['转化'],series:[{name:'率',metric_ids:['rate']}]}]};assert(validateDeck(d).some(e=>e.includes('complete declared part-of-whole')));
 d.metrics.push({id:'rest',type:'percent',storage_scale:'fraction',raw_value:.908,comparison_basis:'part_of_whole'});d.slides[0].labels.push('未转化');d.slides[0].series[0].metric_ids.push('rest');assert.deepEqual(validateDeck(d),[]);
});

test('metric-derived charts preserve authored categories and histograms use one ordered-frequency paint',()=>{
 const {createEncoding}=require('../core/renderer/encoding'),{resolveStyle}=require('../core/style/resolve-style'),{loadProfile}=require('../core/style/profile-loader');const d={title:'项目比较',metrics:[{id:'p1',type:'count',storage_scale:'unit',raw_value:10,time_window:'2026Q3'},{id:'p2',type:'count',storage_scale:'unit',raw_value:8,time_window:'2026Q3'}],slides:[{type:'chart',chartType:'column',title:'交付',labels:['平台升级','渠道接入'],series:[{name:'交付',metric_ids:['p1','p2']}]}]};const e=prepareDeckSemantics(d).spec;assert.deepEqual(e.slides[0].series[0].labels,['平台升级','渠道接入']);assert.deepEqual(d.slides[0].labels,['平台升级','渠道接入']);
 const hist=prepareDeckSemantics({title:'频数',slides:[{type:'histogram',title:'观察频数',bins:[{start:0,end:7,count:7},{start:7,end:14,count:3}]}]}).spec;const style=resolveStyle(loadProfile('executive-clean',require('path').resolve(__dirname,'..'))),plan=createEncoding(hist,style).chartPlansForSpec()[0];assert.equal(plan.category_colors,false);assert.equal(new Set(plan.colors).size,1);
});
