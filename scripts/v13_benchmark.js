#!/usr/bin/env node
'use strict';
const fs=require('fs');
const path=require('path');
const os=require('os');
const crypto=require('crypto');
const {spawnSync}=require('child_process');
const {buildDeck}=require('../core/renderer');
const {analyze}=require('../core/analytics');
const {loadNativeDeck,slideTexts}=require('../core/qa/native_readback');
const {getPointer}=require('../core/semantics/numeric');
const {inspectNarrative}=require('../core/semantics/narrative');
const {validateDeck}=require('../core/schema/validate');
const {canonicalPath}=require('../core/safety/paths');
const {ROLE_STYLES}=require('../core/renderer/encoding');

const ROOT=path.resolve(__dirname,'..');
const FIXTURE_ROOT=path.join(ROOT,'skill/examples/v1.3');
const INPUT_ROOT=path.join(FIXTURE_ROOT,'inputs');
const HOME=os.homedir();
const MATRIX_FAMILIES=['bar','column','line','area','pie','doughnut'];
const MATRIX_THEMES={light:'executive-dense',dark:'dark-executive'};
const MATRIX_CASES=['single','multi','long','percentage','negative','missing','large','dense'];
const DENSE_LABELS=['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
const DENSE_VALUES=[12,18,15,22,19,25,28,24,30,27,33,36];
const SCENARIOS=[
  {slug:'business-performance',id:'synthetic-business-performance',input:'business-performance.json'},
  {slug:'sales-conversion',id:'synthetic-sales-conversion',input:'sales-conversion.json'},
  {slug:'project-analytics',id:'synthetic-project-analytics',input:'project-analytics.json'},
];

const sha256=value=>crypto.createHash('sha256').update(value).digest('hex');
const shaFile=file=>sha256(fs.readFileSync(file));
const readJson=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const writeJson=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value,null,2)+'\n');};
const writeText=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,value);};
const clone=value=>JSON.parse(JSON.stringify(value));
const rel=file=>path.relative(ROOT,file).split(path.sep).join('/');
const exists=file=>fs.existsSync(file);
const walk=(dir,predicate=()=>true)=>{
  if(!exists(dir)) return [];
  const found=[];
  for(const entry of fs.readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){
    const file=path.join(dir,entry.name);
    if(entry.isDirectory()){
      if(['node_modules','__pycache__','.git'].includes(entry.name)) continue;
      found.push(...walk(file,predicate));
    } else if(entry.isFile()&&predicate(file)) found.push(file);
  }
  return found;
};
const safeNumber=(a,b,tolerance=1e-9)=>a===b||(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tolerance);
const sameList=(a,b)=>Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((value,index)=>safeNumber(value,b[index])||value===b[index]);
const statusOf=report=>report?.status||'NOT_RUN';
const publicPath=(file,outRoot)=>{
  const resolved=path.resolve(file);
  if(resolved===path.resolve(outRoot)||resolved.startsWith(path.resolve(outRoot)+path.sep)) return path.relative(outRoot,resolved).split(path.sep).join('/');
  if(resolved===ROOT||resolved.startsWith(ROOT+path.sep)) return rel(resolved);
  return path.basename(resolved);
};
const artifact=(file,outRoot)=>({path:publicPath(file,outRoot),sha256:shaFile(file),bytes:fs.statSync(file).size});
const sheetArtifact=(sheet,outRoot)=>sheet.path?{...artifact(sheet.path,outRoot),pages:sheet.pages||null}:sheet;
const sanitizeText=value=>String(value)
  .split(ROOT+path.sep).join('')
  .split(ROOT).join('.')
  .split(os.tmpdir()+path.sep).join('$TMP/')
  .split(HOME+path.sep).join('~/')
  .split(HOME).join('~');
const sanitizeValue=value=>{
  if(typeof value==='string') return sanitizeText(value);
  if(Array.isArray(value)) return value.map(sanitizeValue);
  if(value&&typeof value==='object') return Object.fromEntries(Object.entries(value).map(([key,item])=>[sanitizeText(key),sanitizeValue(item)]));
  return value;
};
function sanitizeReports(outRoot){
  const changed=[];
  for(const file of walk(outRoot,file=>/(^|\/)qa-[^/]*\.json$/.test(file)||path.basename(file)==='render.json')){
    let data;
    try { data=readJson(file); } catch { continue; }
    const clean=sanitizeValue(data);
    if(JSON.stringify(clean)!==JSON.stringify(data)){
      writeJson(file,clean);
      changed.push(path.relative(outRoot,file).split(path.sep).join('/'));
    }
  }
  return changed;
}

function matrixTemplates(){
  return {
    single:{labels:['本期'],unit:'单',numberFormat:'#,##0',series:[{id:'value',name:'实际',role:'actual',values:[120]}],readback:{values:[120],labels:['本期'],series_names:['实际']}},
    multi:{labels:['华东','华北','华南','西南'],unit:'单',numberFormat:'#,##0',series:[
      {id:'actual',name:'实际',role:'actual',values:[120,90,60,30]},
      {id:'target',name:'目标',role:'target',values:[110,100,70,35]}],readback:{values:[120,90,60,30,110,100,70,35],labels:['华东','华北','华南','西南'],series_names:['实际','目标']}},
    long:{labels:['华东区域重点客户续约收入','华北区域新客户首单收入','华南区域渠道合作收入'],unit:'万元',numberFormat:'#,##0',series:[
      {id:'value',name:'收入',role:'actual',values:[120,90,60]}],readback:{values:[120,90,60],labels:['华东区域重点客户续约收入','华北区域新客户首单收入','华南区域渠道合作收入'],series_names:['收入']}},
    percentage:{labels:['线上','门店','渠道'],unit:'%',numberFormat:'0.0"%"',series:[
      {id:'value',name:'占比',role:'actual',storage_scale:'fraction',values:[0.42,0.33,0.25]}],readback:{values:[42,33,25],labels:['线上','门店','渠道'],series_names:['占比'],numberFormat:'0.0"%"'}},
    negative:{labels:['一季度','二季度','三季度','四季度'],unit:'万元',numberFormat:'#,##0',series:[
      {id:'value',name:'净变化',role:'actual',values:[-20,35,10,-5]}],readback:{values:[-20,35,10,-5],labels:['一季度','二季度','三季度','四季度'],series_names:['净变化']}},
    missing:{labels:['一月','二月','三月','四月'],unit:'单',numberFormat:'#,##0',missing_policy:'gap',series:[
      {id:'value',name:'订单',role:'actual',values:[10,null,0,6]}],readback:{values:[10,null,0,6],labels:['一月','二月','三月','四月'],series_names:['订单'],missing_policy:'gap'}},
    large:{labels:['本月','上月','去年同期'],unit:'元',numberFormat:'#,##0',series:[
      {id:'value',name:'金额',role:'actual',values:[1200000000,980000000,450000000]}],readback:{values:[1200000000,980000000,450000000],labels:['本月','上月','去年同期'],series_names:['金额']}},
    dense:{labels:DENSE_LABELS,unit:'单',numberFormat:'#,##0',series:[
      {id:'value',name:'月度值',role:'actual',values:DENSE_VALUES}],readback:{values:DENSE_VALUES,labels:DENSE_LABELS,series_names:['月度值']}},
  };
}
function matrixRejections(){
  return {
    'bar:dense':{code:'CATEGORY_PALETTE_CAPACITY',reason:'Single-series bar/column category palette supports eight distinguishable colors; twelve categories must be split or faceted.'},
    'column:dense':{code:'CATEGORY_PALETTE_CAPACITY',reason:'Single-series bar/column category palette supports eight distinguishable colors; twelve categories must be split or faceted.'},
    'area:missing':{code:'AREA_MISSING',reason:'Area charts cannot render missing values honestly because the filled band visually bridges the gap in office renderers; choose a line chart for an explicit gap or a table that states the missing value.'},
    'area:single':{code:'AREA_SINGLE_POINT',reason:'Area charts require at least two points per series because a single point is visually empty; use a line chart for one point, a KPI value for one number, or a table for one row.'},
    'pie:multi':{code:'PIE_SINGLE_SERIES',reason:'pie/doughnut accepts exactly one series; a multi-series pie is not a faithful type substitution.'},
    'pie:negative':{code:'PIE_NONNEGATIVE',reason:'pie/doughnut requires nonnegative values; negative values are rejected rather than clipped.'},
    'pie:missing':{code:'PIE_MISSING',reason:'pie/doughnut rejects missing values; an explicit other bucket must be supplied by the author.'},
    'pie:dense':{code:'CATEGORY_PALETTE_CAPACITY',reason:'pie/doughnut category palette supports eight distinguishable colors; twelve slices must be split or faceted.'},
    'doughnut:multi':{code:'PIE_SINGLE_SERIES',reason:'pie/doughnut accepts exactly one series; a multi-series doughnut is not a faithful type substitution.'},
    'doughnut:negative':{code:'PIE_NONNEGATIVE',reason:'pie/doughnut requires nonnegative values; negative values are rejected rather than clipped.'},
    'doughnut:missing':{code:'PIE_MISSING',reason:'pie/doughnut rejects missing values; an explicit other bucket must be supplied by the author.'},
    'doughnut:dense':{code:'CATEGORY_PALETTE_CAPACITY',reason:'pie/doughnut category palette supports eight distinguishable colors; twelve slices must be split or faceted.'},
  };
}
function generateMatrixFixture(){
  const templates=matrixTemplates();
  const rejections=matrixRejections();
  const labels={bar:'条形图',column:'柱状图',line:'折线图',area:'面积图',pie:'饼图',doughnut:'环形图'};
  const caseLabels={single:'单系列',multi:'多系列',long:'长标签',percentage:'百分比',negative:'负值',missing:'缺失',large:'大数',dense:'高密度'};
  const cells=[];
  for(const family of MATRIX_FAMILIES) for(const theme of Object.keys(MATRIX_THEMES)) for(const name of MATRIX_CASES) {
    const template=templates[name];
    const pieLike=['pie','doughnut'].includes(family);
    const rejection=rejections[`${family}:${name}`]||null;
    cells.push({
      id:`${theme==='light'?'L':'D'}-${family}-${name}`,
      family,theme,case:name,
      expected:rejection?'REJECT':'ACCEPT',
      chartType:family,
      title:`${labels[family]} · ${caseLabels[name]}`,
      labels:clone(template.labels),
      unit:template.unit,
      numberFormat:template.numberFormat,
      ...(template.missing_policy?{missing_policy:template.missing_policy}:{}),
      series:clone(template.series),
      visual_encoding:{relation:['line','area'].includes(family)?'trend':'comparison',palette_type:'categorical',
        series:clone(template.series).map(item=>({id:item.id,role:item.role})),
        ...(pieLike?{label_strategy:'percent'}:{})},
      readback:rejection?null:clone(template.readback),
      rejection,
    });
  }
  return {
    schema_version:'1.3',
    description:'Explicit 6 native chart families x 2 themes x 8 cases matrix. ACCEPT cells build real native charts; REJECT cells assert the named deterministic contract.',
    native_chart_families:MATRIX_FAMILIES,
    themes:MATRIX_THEMES,
    cases:MATRIX_CASES,
    counts:{cells:cells.length,accepted:cells.filter(cell=>cell.expected==='ACCEPT').length,rejected:cells.filter(cell=>cell.expected==='REJECT').length},
    case_templates:templates,
    cells,
  };
}

function prepareOutRoot(outRoot){
  const resolved=path.resolve(outRoot);
  if([ROOT,HOME,path.parse(resolved).root].includes(resolved)||ROOT===resolved||ROOT.startsWith(resolved+path.sep)) throw new Error(`Refusing unsafe --out-root ${resolved}`);
  const insideRepo=resolved.startsWith(path.join(ROOT,'out')+path.sep);
  const insideTmp=resolved.startsWith(path.resolve(os.tmpdir())+path.sep);
  if(!insideRepo&&!insideTmp) throw new Error('--out-root must be under the checkout out/ directory or the system temp directory');
  const actual=canonicalPath(resolved),allowed=[canonicalPath(path.join(ROOT,'out')),canonicalPath(os.tmpdir())];
  if(!allowed.some(base=>actual.startsWith(base+path.sep)))throw new Error('Refusing output root that escapes through a symbolic link');
  if(exists(resolved)&&fs.readdirSync(resolved).length) {
    let owned=false;
    try {const m=readJson(path.join(resolved,'showcase.manifest.json'));owned=m.product==='Goujian Strategy Slides'&&m.benchmark==='v13-benchmark';}catch{}
    try {owned ||= fs.readFileSync(path.join(resolved,'.goujian-benchmark-output'),'utf8')==='goujian-v13-benchmark\n';}catch{}
    if(!owned)throw new Error('Refusing to replace a nonempty directory without this benchmark ownership marker');
  }
  if(exists(resolved)) fs.rmSync(resolved,{recursive:true,force:true});
  fs.mkdirSync(resolved,{recursive:true});
  fs.writeFileSync(path.join(resolved,'.goujian-benchmark-output'),'goujian-v13-benchmark\n');
  return resolved;
}

function fingerprintTree(base,{dirs=[],files=[]}={}){
  const entries=[];
  for(const dir of dirs) for(const file of walk(path.join(base,dir),file=>!file.endsWith('.pyc'))) entries.push(file);
  for(const file of files) if(exists(path.join(base,file))) entries.push(path.join(base,file));
  const unique=[...new Set(entries)].sort((left,right)=>rel(left).localeCompare(rel(right)));
  const rows=unique.map(file=>({path:path.relative(base,file).split(path.sep).join('/'),sha256:shaFile(file)}));
  const aggregate=sha256(rows.map(row=>`${row.sha256}  ${row.path}`).join('\n')+'\n');
  return {algorithm:'sha256 over sorted "sha256  path" lines',aggregate_sha256:aggregate,file_count:rows.length,files:rows};
}
function currentFingerprint(){
  return fingerprintTree(ROOT,{dirs:['core','skill','scripts'],
    files:['package.json','package-lock.json','requirements-render.txt','skill/archetypes/registry.json','skill/compositions/registry.json','skill/storylines/registry.json','skill/templates/registry.json','skill/analytics/registry.json']});
}
function baselineFingerprint(base){
  return fingerprintTree(base,{dirs:['core','skill/profiles','scripts'],files:['package.json','package-lock.json']});
}

function runProcess(command,args,{cwd=ROOT,env={},timeout=600000,log=null}={}){
  const result=spawnSync(command,args,{cwd,env:{...process.env,...env},encoding:'utf8',timeout,maxBuffer:64*1024*1024});
  if(log) writeText(log,[`$ ${command} ${args.join(' ')}`,result.stdout||'',result.stderr||'',`exit=${result.status}`].join('\n')+'\n');
  return {status:result.status,signal:result.signal,stdout:result.stdout||'',stderr:result.stderr||''};
}
function python(args,options={}){return runProcess('python3',args,options);}

function renderDeck(pptx,dir,log){
  const reportPath=path.join(dir,'render.json');
  const result=python([path.join(ROOT,'skill/scripts/render_deck.py'),pptx,dir,'--json',reportPath],{log});
  if(!exists(reportPath)) return {status:'FAIL',reason:'render report was not produced',command_exit:result.status,pages:[],montage:null,pdf:null,report:null};
  const report=readJson(reportPath);
  return {...report,report:reportPath,command_exit:result.status};
}
function qualityGate(pptx,{spec,scene,profile,out,renderDir,analyticsInput,log,qaScript}){
  const script=qaScript||path.join(ROOT,'skill/scripts/quality_gate.py');
  const args=[script,pptx,'--spec',spec,'--out',out];
  if(scene&&!qaScript) args.push('--scene',scene);
  if(profile&&!qaScript) args.push('--profile',profile);
  if(renderDir) args.push('--render-dir',renderDir);
  if(analyticsInput) args.push('--analytics-input',analyticsInput);
  const result=python(args,{log,timeout:900000,env:{NODE_PATH:path.join(ROOT,'node_modules')}});
  if(!exists(out)) return {status:'FAIL',reason:'Quality Gate report was not produced',command_exit:result.status,report:null};
  const report=readJson(out);
  return {status:report.status||'FAIL',report,report_path:out,command_exit:result.status,
    render:report.checks?.render||{status:'NOT_RUN'},checks:Object.fromEntries(Object.entries(report.checks||{}).map(([key,value])=>[key,statusOf(value)])),
    visual_qa:report.VISUAL_QA||'NOT_RUN',engine:qaScript?'v1.2.1 baseline gate':'current gate'};
}
function contactSheets(pages,dir,prefix,log,perSheet=12){
  if(!pages.length) return [];
  const sheets=[];
  for(let index=0;index<pages.length;index+=perSheet){
    const chunk=pages.slice(index,index+perSheet);
    const out=path.join(dir,`${prefix}-${Math.floor(index/perSheet)+1}.png`);
    const result=runProcess('montage',['-background','#EEEEEE','-fill','#333333','-pointsize','14','-label','%t',...chunk,'-tile','3x4','-geometry','480x270+8+16',out],{log,timeout:180000});
    if(result.status!==0||!exists(out)) {
      sheets.push({status:'UNAVAILABLE',reason:(result.stderr||result.stdout||'montage failed').trim().split('\n').slice(0,2).join(' '),pages:chunk.length});
      continue;
    }
    sheets.push({status:'PASS',path:out,pages:chunk.length,sha256:shaFile(out)});
  }
  return sheets;
}
function renderArtifacts(render,outRoot){
  if(!render||!Array.isArray(render.pages)) return {status:statusOf(render),pages:[],montage:null,pdf:null};
  const pages=render.pages.map(file=>({...artifact(file,outRoot),page:Number((file.match(/slide-(\d+)\.png$/)||[])[1]||0)}));
  return {
    status:render.status,
    pages,
    montage:render.montage&&exists(render.montage)?artifact(render.montage,outRoot):null,
    pdf:render.pdf&&exists(render.pdf)?artifact(render.pdf,outRoot):null,
  };
}

async function matrixDeckSpec(fixture,theme){
  const cells=fixture.cells.filter(cell=>cell.theme===theme&&cell.expected==='ACCEPT');
  const slides=cells.map(cell=>{
    const pieLike=['pie','doughnut'].includes(cell.family);
    return {
      type:'chart',chartType:cell.chartType,title:`${cell.title}（${cell.id}）`,
      labels:cell.labels,unit:cell.unit,
      numberFormat:pieLike?(cell.case==='percentage'?'0.0%':'0%'):cell.numberFormat,
      ...(cell.missing_policy?{missing_policy:cell.missing_policy}:{}),
      series:cell.series,visual_encoding:cell.visual_encoding,source:'V1.3 matrix fixture（合成）',
    };
  });
  return {cells,spec:{schema_version:'1.3',title:`V1.3 native chart matrix · ${theme}`,profile:MATRIX_THEMES[theme],lang:'zh-CN',slides}};
}
function expectedNativeKind(cell){
  if(cell.family==='column') return {kind:'bar',bar_dir:'col'};
  if(cell.family==='bar') return {kind:'bar',bar_dir:'bar'};
  return {kind:cell.family,bar_dir:null};
}
async function verifyMatrixDeck(pptx,spec,cells){
  const scene=readJson(pptx+'.scene.json');
  const native=await loadNativeDeck(pptx,{workbooks:true});
  const plans=[...scene.visual_encoding.plans].sort((a,b)=>a.slide_index-b.slide_index);
  const issues=[];
  if(plans.length!==cells.length) issues.push(`plan count ${plans.length} != accepted cell count ${cells.length}`);
  if(native.charts.length!==cells.length) issues.push(`native chart count ${native.charts.length} != accepted cell count ${cells.length}`);
  if(native.charts.length!==native.slideParts.length) issues.push(`native chart count ${native.charts.length} != slide count ${native.slideParts.length}`);
  const validation=scene.visual_encoding.validation.map(result=>result.status);
  if(validation.some(status=>status!=='PASS')) issues.push(`visual encoding validation statuses: ${validation.join(',')}`);
  const results=[];
  const counts={charts_checked:0,series_checked:0,values_checked:0,nulls_checked:0,zeros_checked:0,categories_checked:0,units_checked:0,native_cache_checked:0,xlsx_checked:0,grouping_checked:0,dash_checked:0,marker_checked:0};
  for(const [index,cell] of cells.entries()){
    const plan=plans[index],chart=native.charts[index],slideXml=await native.zip.file(native.slideParts[index]).async('string');
    const cellIssues=[];
    if(!chart||!plan) { results.push({id:cell.id,status:'FAIL',issues:['missing native chart or plan']}); continue; }
    if(plan.slide_index!==index) cellIssues.push(`plan slide_index ${plan.slide_index} != ${index}`);
    const expectedKind=expectedNativeKind(cell);
    if(chart.kind!==expectedKind.kind) cellIssues.push(`native kind ${chart.kind} != ${expectedKind.kind}`);
    if(expectedKind.bar_dir&&chart.bar_dir!==expectedKind.bar_dir) cellIssues.push(`bar_dir ${chart.bar_dir} != ${expectedKind.bar_dir}`);
    if(['bar','column'].includes(cell.family)&&cell.series.length>1){
      if(chart.grouping!=='clustered') cellIssues.push(`native grouping ${chart.grouping||'null'} != clustered`);
      else counts.grouping_checked++;
    }
    if(chart.kind==='line'){
      for(const [seriesIndex,series] of chart.series.entries()){
        const role=cell.series[seriesIndex]?.role;
        const expected=role?ROLE_STYLES[role]:null;
        if(!expected) continue;
        if(series.dash!==expected.dash) cellIssues.push(`native series ${seriesIndex+1} dash ${series.dash||'null'} != ${expected.dash} for role ${role}`);
        else counts.dash_checked++;
        if(series.marker?.symbol!==expected.symbol) cellIssues.push(`native series ${seriesIndex+1} marker ${series.marker?.symbol||'null'} != ${expected.symbol} for role ${role}`);
        else counts.marker_checked++;
      }
    }
    if(chart.series.length!==cell.series.length) cellIssues.push(`series count ${chart.series.length} != ${cell.series.length}`);
    const readback=cell.readback;
    const nativeValues=chart.series.flatMap(series=>series.values);
    if(!sameList(nativeValues,readback.values)) cellIssues.push(`native cache values ${JSON.stringify(nativeValues)} != expected ${JSON.stringify(readback.values)}`);
    counts.native_cache_checked++;
    const names=chart.series.map(series=>series.name);
    if(!sameList(names,readback.series_names)) cellIssues.push(`native series names ${JSON.stringify(names)} != expected ${JSON.stringify(readback.series_names)}`);
    counts.series_checked+=chart.series.length;
    counts.values_checked+=readback.values.length;
    counts.nulls_checked+=readback.values.filter(value=>value===null).length;
    counts.zeros_checked+=readback.values.filter(value=>value===0).length;
    for(const [seriesIndex,series] of chart.series.entries()){
      if(!sameList(series.category_labels,readback.labels)) cellIssues.push(`series ${seriesIndex+1} category labels ${JSON.stringify(series.category_labels)} != expected ${JSON.stringify(readback.labels)}`);
      if(cell.case==='missing'&&series.raw_values){
        series.raw_values.forEach((raw,valueIndex)=>{if(series.values[valueIndex]===null&&raw==='0')cellIssues.push(`null value ${valueIndex+1} serialized as zero`);});
      }
    }
    counts.categories_checked+=readback.labels.length;
    if(cell.case==='missing'&&chart.disp_blanks_as!=='gap') cellIssues.push(`missing chart disp_blanks_as ${chart.disp_blanks_as} != gap`);
    const texts=slideTexts(slideXml);
    if(!texts.includes(cell.unit)) cellIssues.push(`native slide text is missing unit ${JSON.stringify(cell.unit)}`);
    else counts.units_checked++;
    if(cell.readback.numberFormat){
      const formats=[chart.value_axis_format,chart.global_label_format,...chart.series.map(series=>series.label_format||series.cache_format_code)].filter(Boolean);
      if(cell.case==='percentage'&&!formats.some(format=>String(format).includes('%'))) cellIssues.push(`native formats omit %: ${JSON.stringify(formats)}`);
    }
    if(chart.workbook?.status==='PASS'){
      counts.xlsx_checked++;
      const workbookValues=chart.workbook.series.flatMap(series=>series.values);
      if(!sameList(workbookValues,readback.values)) cellIssues.push(`XLSX values ${JSON.stringify(workbookValues)} != expected ${JSON.stringify(readback.values)}`);
      for(const [seriesIndex,series] of chart.workbook.series.entries()){
        if(!sameList(series.categories,readback.labels)) cellIssues.push(`XLSX series ${seriesIndex+1} categories ${JSON.stringify(series.categories)} != expected ${JSON.stringify(readback.labels)}`);
        if(String(series.name??'')!==String(readback.series_names[seriesIndex]??'')) cellIssues.push(`XLSX series ${seriesIndex+1} name ${JSON.stringify(series.name)} != expected ${JSON.stringify(readback.series_names[seriesIndex])}`);
      }
    } else cellIssues.push(`embedded workbook ${chart.workbook?.status||'NOT_RUN'}: ${chart.workbook?.reason||'no workbook'}`);
    counts.charts_checked++;
    results.push({id:cell.id,family:cell.family,theme:cell.theme,case:cell.case,status:cellIssues.length?'FAIL':'PASS',issues:cellIssues,
      native:{kind:chart.kind,bar_dir:chart.bar_dir,grouping:chart.grouping,values:nativeValues,series_names:names,
        series_styles:chart.series.map(series=>series.dash||series.marker?{dash:series.dash||null,marker:series.marker?.symbol||null}:null),
        format:chart.value_axis_format||chart.series[0]?.label_format||null,disp_blanks_as:chart.disp_blanks_as},
      xlsx:chart.workbook?.status||'NOT_RUN'});
  }
  return {status:issues.length||results.some(result=>result.status==='FAIL')?'FAIL':'PASS',deck_issues:issues,counts,cells:results};
}
function rejectionRegex(code){
  if(code==='CATEGORY_PALETTE_CAPACITY') return /category palette exceeds 8 distinguishable colors/;
  if(code==='PIE_SINGLE_SERIES') return /pie\/doughnut requires exactly one series/;
  if(code==='PIE_NONNEGATIVE') return /pie\/doughnut requires nonnegative values/;
  if(code==='PIE_MISSING') return /pie\/doughnut does not support missing values/;
  if(code==='AREA_MISSING') return /area charts cannot render missing values honestly[\s\S]*line chart[\s\S]*table/;
  if(code==='AREA_SINGLE_POINT') return /area charts require at least two points[\s\S]*line chart[\s\S]*KPI[\s\S]*table/;
  return /./;
}
async function testMatrixRejections(fixture,outRoot,log){
  const dir=path.join(outRoot,'matrix','rejects'); fs.mkdirSync(dir,{recursive:true});
  const seen=new Set(),results=[];
  for(const cell of fixture.cells.filter(item=>item.expected==='REJECT')){
    const key=`${cell.family}:${cell.case}`;
    if(seen.has(key)) continue; seen.add(key);
    const spec={schema_version:'1.3',title:`Reject ${cell.id}`,profile:MATRIX_THEMES[cell.theme],lang:'zh-CN',slides:[{
      type:'chart',chartType:cell.chartType,title:cell.title,labels:cell.labels,unit:cell.unit,numberFormat:cell.numberFormat,
      ...(cell.missing_policy?{missing_policy:cell.missing_policy}:{}),series:cell.series,visual_encoding:cell.visual_encoding,
    }]};
    let error=null;
    try { await buildDeck(spec,path.join(dir,`${cell.id}.pptx`)); }
    catch(caught){ error=caught.message; }
    const matched=Boolean(error&&rejectionRegex(cell.rejection.code).test(error));
    results.push({id:cell.id,theme:cell.theme,family:cell.family,case:cell.case,expected:cell.expected,code:cell.rejection.code,
      reason:cell.rejection.reason,input_case:cell.case,matched,observed_error:error,status:matched&&error?'PASS':'FAIL'});
    if(log) writeText(path.join(dir,'rejections.log'),results.map(item=>`${item.id}\t${item.status}\t${item.code}\t${item.observed_error||'UNEXPECTED_BUILD'}`).join('\n')+'\n');
  }
  return {status:results.every(item=>item.status==='PASS')?'PASS':'FAIL',unique_rejections:results.length,cells_rejected_in_matrix:fixture.cells.filter(cell=>cell.expected==='REJECT').length,results};
}

function supplementalSlides(){
  const stacked={labels:['华东','华北','华南'],unit:'单',numberFormat:'#,##0',stack_group:'layers',
    series:[{id:'retained',name:'存量',role:'actual',values:[120,90,60],stack:true},{id:'new',name:'新增',role:'comparison',values:[40,30,20],stack:true}],
    visual_encoding:{relation:'composition',palette_type:'categorical',series:[{id:'retained',role:'actual'},{id:'new',role:'comparison'}],label_strategy:'category_value'}};
  const bins=[{start:0,end:10,count:3},{start:10,end:20,count:7},{start:20,end:30,count:9},{start:30,end:40,count:5},{start:40,end:50,count:2}];
  return {stacked,bins};
}
async function buildSupplemental(outRoot,opts){
  const dir=path.join(outRoot,'matrix','supplemental'); fs.mkdirSync(dir,{recursive:true});
  const {stacked,bins}=supplementalSlides();
  const spec={schema_version:'1.3',title:'V1.3 stacked and histogram supplement',profile:MATRIX_THEMES.light,lang:'zh-CN',slides:[
    {type:'chart',chartType:'bar',title:'堆叠条形图：存量与新增分层保留',source:'V1.3 matrix fixture（合成）',...stacked},
    {type:'chart',chartType:'column',title:'堆叠柱状图：存量与新增分层保留',source:'V1.3 matrix fixture（合成）',...stacked},
    {type:'histogram',chartType:'column',title:'线索获取 10 天等宽分箱：40 个去重线索',source:'V1.3 matrix fixture（合成）',unit:'条',period:'2026-08-01 至 2026-09-20',
      bins,series:[{id:'lead_count',name:'线索数',labels:bins.map(bin=>`${bin.start}–${bin.end}`),values:bins.map(bin=>bin.count)}],
      visual_encoding:{relation:'distribution',label_strategy:'value'},insight:'显式等宽分箱；不使用自动分箱，也不把普通分类柱状图重命名为直方图。'},
  ]};
  const specPath=path.join(dir,'supplemental.spec.json'); writeJson(specPath,spec);
  const pptx=path.join(dir,'supplemental.pptx');
  const built=await buildDeck(spec,pptx,{profile:MATRIX_THEMES.light,specDir:dir});
  const native=await loadNativeDeck(pptx,{workbooks:true});
  const scene=readJson(built.scene);
  const charts=native.charts;
  const issues=[];
  const chart0=charts[0],chart1=charts[1],chart2=charts[2];
  if(chart0?.grouping!=='stacked') issues.push(`bar grouping ${chart0?.grouping} != stacked`);
  if(chart1?.grouping!=='stacked') issues.push(`column grouping ${chart1?.grouping} != stacked`);
  if(chart0&&!sameList(chart0.series.flatMap(series=>series.values),[120,90,60,40,30,20])) issues.push('stacked bar values changed');
  if(chart1&&!sameList(chart1.series.flatMap(series=>series.values),[120,90,60,40,30,20])) issues.push('stacked column values changed');
  const counts=bins.map(bin=>bin.count);
  if(chart2&&!sameList(chart2.series.flatMap(series=>series.values),counts)) issues.push('histogram counts changed');
  const histogramLabels=chart2?.series[0]?.category_labels||[];
  if(!sameList(histogramLabels,bins.map(bin=>`${bin.start}–${bin.end}`))) issues.push(`histogram labels ${JSON.stringify(histogramLabels)} != explicit bins`);
  const plans=scene.visual_encoding.plans;
  if(plans.length!==3) issues.push(`supplemental plan count ${plans.length} != 3`);
  const render=await renderCase(pptx,specPath,built.scene,MATRIX_THEMES.light,path.join(dir,'render'),'supplemental',opts);
  return {
    status:issues.length||render.qa.status==='FAIL'?'FAIL':'PASS',spec:artifact(specPath,outRoot),pptx:artifact(pptx,outRoot),scene:artifact(built.scene,outRoot),
    checks:{stacked_bar_grouping:chart0?.grouping,stacked_column_grouping:chart1?.grouping,histogram_labels:histogramLabels,histogram_counts:chart2?.series.flatMap(series=>series.values),
      native_charts:charts.length,visual_encoding:scene.visual_encoding.validation.map(item=>item.status)},
    issues,render:renderArtifacts(render.render,outRoot),qa:{status:render.qa.status,checks:render.qa.checks,visual_qa:render.qa.visual_qa},contact_sheets:render.contact_sheets.map(sheet=>sheetArtifact(sheet,outRoot)),
  };
}
async function testUnsupported(outRoot){
  const dir=path.join(outRoot,'matrix','unsupported'); fs.mkdirSync(dir,{recursive:true});
  const results=[];
  for(const chartType of ['waterfall','scatter','bubble']){
    const spec={schema_version:'1.3',title:`Unsupported ${chartType}`,profile:MATRIX_THEMES.light,lang:'zh-CN',slides:[{
      type:'chart',chartType,title:`${chartType} is not a native family`,labels:['A','B'],unit:'单',
      series:[{id:'value',name:'值',role:'actual',values:[1,2]}],visual_encoding:{relation:'comparison',palette_type:'categorical',series:[{id:'value',role:'actual'}]},
    }]};
    let error=null;
    try { await buildDeck(spec,path.join(dir,`${chartType}.pptx`)); }
    catch(caught){ error=caught.message; }
    const rejected=Boolean(error&&/unsupported native chart type|chartType must be equal to one of the allowed values/.test(error));
    results.push({chartType,status:rejected?'NOT_SUPPORTED':'FAIL',observed_error:error,
      rejected_by:/chartType must be equal to one of the allowed values/.test(error||'')?'schema':'semantic',
      honest_alternative:'Explicit equal-width histogram for distribution; bar/column/line for the underlying values.'});
  }
  return {status:results.every(item=>item.status==='NOT_SUPPORTED')?'PASS':'FAIL',results};
}

async function renderCase(pptx,spec,scene,profile,renderDir,name,opts){
  const qaOut=path.join(path.dirname(renderDir),`qa-${name}.json`);
  if(opts.qa){
    const qa=qualityGate(pptx,{spec,scene,profile,out:qaOut,renderDir:opts.render?renderDir:null,
      analyticsInput:opts.analyticsInput||null,qaScript:opts.qaScript||null,log:opts.logDir?path.join(opts.logDir,`qa-${name}.log`):null});
    const render=qa.render||{status:'NOT_RUN'};
    const contact=opts.render&&render.status==='PASS'&&Array.isArray(render.pages)?contactSheets(render.pages,path.dirname(renderDir),`contact-${name}`,opts.logDir?path.join(opts.logDir,`montage-${name}.log`):null):[];
    return {qa,render,contact_sheets:contact};
  }
  if(!opts.render) return {qa:{status:'NOT_RUN'},render:{status:'NOT_RUN',pages:[]},contact_sheets:[]};
  const render=renderDeck(pptx,renderDir,opts.logDir?path.join(opts.logDir,`render-${name}.log`):null);
  const contact=render.status==='PASS'?contactSheets(render.pages,path.dirname(renderDir),`contact-${name}`,opts.logDir?path.join(opts.logDir,`montage-${name}.log`):null):[];
  return {qa:{status:'NOT_RUN'},render,contact_sheets:contact};
}

async function buildMatrix(outRoot,fixture,opts){
  const sourcePath=path.join(outRoot,'matrix','matrix-cases.json');
  writeJson(sourcePath,fixture);
  const themes={};
  for(const [theme,profile] of Object.entries(MATRIX_THEMES)){
    const {cells,spec}=await matrixDeckSpec(fixture,theme);
    const specPath=path.join(outRoot,'matrix',`${theme}.spec.json`); writeJson(specPath,spec);
    const pptx=path.join(outRoot,'matrix',`${theme}.pptx`);
    let built=null,error=null;
    try { built=await buildDeck(spec,pptx,{profile,specDir:path.join(outRoot,'matrix')}); }
    catch(caught){ error=caught.message; }
    if(error){ themes[theme]={status:'FAIL',error,accepted_cells:cells.length,spec:artifact(specPath,outRoot)}; continue; }
    const readback=await verifyMatrixDeck(pptx,spec,cells);
    const render=await renderCase(pptx,specPath,built.scene,profile,path.join(outRoot,'matrix',`render-${theme}`),`matrix-${theme}`,opts);
    themes[theme]={status:readback.status==='PASS'&&render.qa.status!=='FAIL'?'PASS':'FAIL',profile,accepted_cells:cells.length,
      spec:artifact(specPath,outRoot),pptx:artifact(pptx,outRoot),scene:artifact(built.scene,outRoot),
      readback:{status:readback.status,deck_issues:readback.deck_issues,counts:readback.counts,cells:readback.cells},
      qa:render.qa.status,checks:render.qa.checks,visual_qa:render.qa.visual_qa,
      render:renderArtifacts(render.render,outRoot),contact_sheets:render.contact_sheets.map(sheet=>sheetArtifact(sheet,outRoot)),
    };
  }
  const rejections=await testMatrixRejections(fixture,outRoot,opts.logDir?path.join(opts.logDir,'matrix-rejects.log'):null);
  const supplemental=await buildSupplemental(outRoot,opts);
  const unsupported=await testUnsupported(outRoot);
  const familyCounts=Object.fromEntries(MATRIX_FAMILIES.map(family=>[family,{
    accepted:fixture.cells.filter(cell=>cell.family===family&&cell.expected==='ACCEPT').length,
    rejected:fixture.cells.filter(cell=>cell.family===family&&cell.expected==='REJECT').length}]));
  const rejectedIds=fixture.cells.filter(cell=>cell.expected==='REJECT').map(cell=>({id:cell.id,family:cell.family,case:cell.case,code:cell.rejection.code,reason:cell.rejection.reason}));
  return {status:Object.values(themes).every(item=>item.status==='PASS')&&rejections.status==='PASS'&&supplemental.status==='PASS'&&unsupported.status==='PASS'?'PASS':'FAIL',
    families:MATRIX_FAMILIES,native_family_count:MATRIX_FAMILIES.length,themes,fixture_counts:fixture.counts,family_counts:familyCounts,
    accepted_cell_ids:fixture.cells.filter(cell=>cell.expected==='ACCEPT').map(cell=>cell.id),rejected_cells:rejectedIds,
    tested_cells:fixture.counts.cells,accepted_cells:fixture.counts.accepted,rejected_cell_count:fixture.counts.rejected,
    rejections,supplemental,unsupported};
}

function declaredTrendPeriod(raw){
  if(!Array.isArray(raw.trend)) return null;
  const dates=raw.trend.map(point=>point?.month||point?.date).filter(Boolean).sort();
  return dates.length?{start:dates[0],end:dates.at(-1),basis:'trend'}:null;
}
function sourceLedger(){
  const docs=SCENARIOS.map(item=>{
    const file=path.join(INPUT_ROOT,item.input);
    const raw=readJson(file);
    return {id:item.id,name:`${raw.title}（合成）`,path:`inputs/${item.input}`,format:'json',bytes:fs.statSync(file).size,sha256:shaFile(file),
      period:raw.period,period_basis:raw.measurement_basis||raw.recipe||null,trend_period:declaredTrendPeriod(raw),
      period_note:'period mirrors the raw declared reporting window; earlier history appears only in explicitly dated trend or previous_month/previous_year fields.',
      measurement_basis:raw.measurement_basis||raw.recipe||null,synthetic:raw.synthetic===true,
      rights:raw.source||'Project-authored synthetic fixture / Apache-2.0',review_status:'NOT_RUN'};
  });
  const matrix=path.join(FIXTURE_ROOT,'matrix-cases.json');
  return {schema_version:'1.3',base_path:'skill/examples/v1.3',generated_by:'scripts/v13_benchmark.js',review_status:'NOT_RUN',
    review_note:'Inventory and hash registry only. Source authenticity, access rights and redistribution rights still require human review.',
    documents:docs,
    derivatives:[{id:'v13-matrix-cases',name:'V1.3 图表矩阵用例（生成）',path:'matrix-cases.json',format:'json',
      bytes:fs.statSync(matrix).size,sha256:shaFile(matrix),
      derived_from:'scripts/v13_benchmark.js matrix generator',synthetic:true,review_status:'NOT_RUN'}],
    controls:{duplicate_documents:'Document IDs and SHA-256 values must be unique; the benchmark rebuilds this ledger from actual input bytes.',
      period:'Declared period mirrors the raw reporting window; trend and previous-period comparisons stay explicitly dated.',
      rights:'No company, customer, personal or third-party asset is included.',
      baseline_reuse:'The V1.2.1 baseline consumes the same raw bytes; the benchmark records both input hashes.'}};
}
function sourceLedgerIssues(expected,actual){
  const issues=[];
  const expectedDocuments=Array.isArray(expected?.documents)?expected.documents:[];
  const actualDocuments=Array.isArray(actual?.documents)?actual.documents:[];
  if(expectedDocuments.length!==actualDocuments.length) issues.push('source ledger document count changed');
  for(const [index,doc] of actualDocuments.entries()){
    const declared=expectedDocuments[index];
    if(!declared) { issues.push(`source ledger missing ${doc.id}`); continue; }
    for(const [field,value] of Object.entries(doc)) {
      if(JSON.stringify(declared[field])!==JSON.stringify(value)) issues.push(`${doc.id} ${field} differs from checked-in ledger`);
    }
    for(const field of Object.keys(declared)) if(!(field in doc)) issues.push(`${doc.id} ${field} is no longer produced by the ledger`);
  }
  if(new Set(expectedDocuments.map(item=>item.sha256)).size!==expectedDocuments.length) issues.push('source ledger contains duplicate hashes');
  const expectedDerivatives=Array.isArray(expected?.derivatives)?expected.derivatives:[];
  const actualDerivatives=Array.isArray(actual?.derivatives)?actual.derivatives:[];
  if(expectedDerivatives.length!==actualDerivatives.length) issues.push('source ledger derivative count changed');
  for(const [index,derivative] of actualDerivatives.entries()){
    const declared=expectedDerivatives[index];
    if(!declared) { issues.push(`source ledger missing derivative ${derivative.id}`); continue; }
    for(const [field,value] of Object.entries(derivative)) {
      if(JSON.stringify(declared[field])!==JSON.stringify(value)) issues.push(`derivative ${derivative.id} ${field} differs from checked-in ledger`);
    }
  }
  return issues;
}
function checkSourceLedger(outRoot){
  const expected=readJson(path.join(INPUT_ROOT,'source-ledger.json'));
  const actual=sourceLedger();
  const issues=sourceLedgerIssues(expected,actual);
  writeJson(path.join(outRoot,'source-ledger.json'),expected);
  return {status:issues.length?'FAIL':'PASS',issues,documents:expected.documents};
}

function flattenNumbers(value,prefix='',out=[]){
  if(typeof value==='number') out.push({path:prefix,value});
  else if(Array.isArray(value)) value.forEach((item,index)=>flattenNumbers(item,`${prefix}/${index}`,out));
  else if(value&&typeof value==='object') for(const [key,item] of Object.entries(value)) flattenNumbers(item,`${prefix}/${key}`,out);
  return out;
}
function specDiff(before,after){
  const a=flattenNumbers(before),b=flattenNumbers(after);
  const add=a.map(item=>item.value).sort((x,y)=>x-y),bd=b.map(item=>item.value).sort((x,y)=>x-y);
  const addedKeys=[];const removedKeys=[];
  const walkKeys=(source,target,prefix)=>{
    if(source&&target&&typeof source==='object'&&typeof target==='object'&&!Array.isArray(source)&&!Array.isArray(target)){
      for(const key of Object.keys(target)) if(!(key in source)) addedKeys.push(`${prefix}/${key}`);
      for(const key of Object.keys(source)) if(!(key in target)) removedKeys.push(`${prefix}/${key}`);
      for(const key of Object.keys(source)) if(key in target) walkKeys(source[key],target[key],`${prefix}/${key}`);
    }
  };
  walkKeys(before,after,'');
  return {before_numbers:a.length,after_numbers:b.length,unique_multiset_unchanged:JSON.stringify(add)===JSON.stringify(bd),
    added_paths:addedKeys.slice(0,40),added_path_count:addedKeys.length,removed_paths:removedKeys.slice(0,40),removed_path_count:removedKeys.length};
}
function compareRenders(before,after){
  if(!before||!after||before.status!=='PASS'||after.status!=='PASS') return {status:'NOT_RUN',pairs:[]};
  const pairs=[];
  for(const page of after.pages||[]){
    const prior=(before.pages||[]).find(candidate=>candidate.page===page.page);
    if(!prior) continue;
    pairs.push({page:page.page,before_sha256:prior.sha256,after_sha256:page.sha256,identical:prior.sha256===page.sha256});
  }
  return {status:pairs.length&&pairs.every(pair=>pair.identical)?'RENDER_IDENTICAL':pairs.length?'RENDER_CHANGED':'NOT_COMPARABLE',pairs};
}
async function buildScenario(item,outRoot,baselineRoot,opts){
  const dir=path.join(outRoot,'scenarios',item.slug); fs.mkdirSync(dir,{recursive:true});
  const source=path.join(INPUT_ROOT,item.input);
  const input=path.join(dir,'input.json'); fs.copyFileSync(source,input);
  const inputSha=shaFile(input);
  const sourceSha=shaFile(source);
  const record={id:item.id,slug:item.slug,input:artifact(input,outRoot),input_sha256:inputSha,source_artifact:artifact(source,outRoot),
    before:{status:'NOT_RUN'},after:{status:'NOT_RUN'},comparison:{status:'NOT_RUN'}};
  if(baselineRoot){
    const analyzeScript=path.join(baselineRoot,'scripts/analyze.js');
    if(!exists(analyzeScript)) record.before={status:'NOT_RUN',reason:`baseline analyze script not found at ${rel(analyzeScript)}`};
    else {
      const beforeDir=path.join(dir,'before'); fs.mkdirSync(beforeDir,{recursive:true});
      const beforePptx=path.join(beforeDir,'deck.pptx');
      const result=runProcess(process.execPath,[analyzeScript,input,beforePptx],{cwd:ROOT,env:{NODE_PATH:path.join(ROOT,'node_modules')},
        timeout:300000,log:opts.logDir?path.join(opts.logDir,`before-${item.slug}.log`):null});
      const specPath=beforePptx+'.spec.json';
      if(result.status!==0||!exists(specPath)||!exists(beforePptx)) record.before={status:'FAIL',reason:(result.stderr||result.stdout||'baseline analyze failed').trim().split('\n').slice(-3).join(' ')};
      else {
        const spec=readJson(specPath),scenePath=beforePptx+'.scene.json';
        const render=await renderCase(beforePptx,specPath,scenePath,spec.profile,beforeDir,'before-'+item.slug,
          {...opts,analyticsInput:null,qaScript:path.join(baselineRoot,'skill/scripts/quality_gate.py')});
        record.before={status:render.qa.status==='FAIL'?'FAIL':'PASS',version:readJson(path.join(baselineRoot,'package.json')).version,
          qa_engine:'v1.2.1 baseline gate',spec:artifact(specPath,outRoot),pptx:artifact(beforePptx,outRoot),data:exists(beforePptx+'.data.json')?artifact(beforePptx+'.data.json',outRoot):null,
          scene:exists(scenePath)?artifact(scenePath,outRoot):null,qa:render.qa.status,checks:render.qa.checks,visual_qa:render.qa.visual_qa,
          render:renderArtifacts(render.render,outRoot),contact_sheets:render.contact_sheets.map(sheet=>sheetArtifact(sheet,outRoot)),spec_json:spec};
      }
    }
  } else record.before={status:'NOT_RUN',reason:'No --baseline-root supplied; before/after comparison is not run.'};
  const afterDir=path.join(dir,'after'); fs.mkdirSync(afterDir,{recursive:true});
  const afterPptx=path.join(afterDir,'deck.pptx');
  const result=runProcess(process.execPath,[path.join(ROOT,'scripts/analyze.js'),input,afterPptx],{cwd:ROOT,timeout:300000,
    log:opts.logDir?path.join(opts.logDir,`after-${item.slug}.log`):null});
  const afterSpecPath=afterPptx+'.spec.json';
  if(result.status!==0||!exists(afterSpecPath)||!exists(afterPptx)) record.after={status:'FAIL',reason:(result.stderr||result.stdout||'current analyze failed').trim().split('\n').slice(-3).join(' ')};
  else {
    const spec=readJson(afterSpecPath),scenePath=afterPptx+'.scene.json';
    const render=await renderCase(afterPptx,afterSpecPath,scenePath,spec.profile,afterDir,'after-'+item.slug,{...opts,analyticsInput:input});
    record.after={status:render.qa.status==='FAIL'?'FAIL':'PASS',version:readJson(path.join(ROOT,'package.json')).version,
      qa_engine:'current gate',spec:artifact(afterSpecPath,outRoot),pptx:artifact(afterPptx,outRoot),data:exists(afterPptx+'.data.json')?artifact(afterPptx+'.data.json',outRoot):null,
      scene:exists(scenePath)?artifact(scenePath,outRoot):null,qa:render.qa.status,checks:render.qa.checks,visual_qa:render.qa.visual_qa,
      render:renderArtifacts(render.render,outRoot),contact_sheets:render.contact_sheets.map(sheet=>sheetArtifact(sheet,outRoot)),spec_json:spec};
    if(record.before.spec_json){
      const diff=specDiff(record.before.spec_json,spec);
      const renders=compareRenders(record.before.render,record.after.render);
      const inputShaAfter=shaFile(input);
      const sameInput=inputSha===sourceSha&&inputSha===inputShaAfter;
      record.comparison={status:sameInput?(diff.unique_multiset_unchanged&&renders.status!=='NOT_RUN'?'PASS':'PASS_WITH_NOTES'):'FAIL',
        same_raw_bytes:sameInput,source_sha256:sourceSha,input_sha256_before:inputSha,input_sha256_after:inputShaAfter,
        before_spec_sha256:record.before.spec.sha256,after_spec_sha256:record.after.spec.sha256,
        before_pptx_sha256:record.before.pptx.sha256,after_pptx_sha256:record.after.pptx.sha256,
        before_slide_count:record.before.spec_json.slides?.length,after_slide_count:spec.slides?.length,
        numeric_values_unchanged:diff.unique_multiset_unchanged,numeric_values_before:diff.before_numbers,numeric_values_after:diff.after_numbers,
        added_paths:diff.added_paths,added_path_count:diff.added_path_count,removed_paths:diff.removed_paths,removed_path_count:diff.removed_path_count,
        render:renders};
    }
  }
  delete record.before.spec_json; delete record.after.spec_json;
  return record;
}

function metricReconciliation(gallery,sources,audits){
  const issues=[];let checked=0;
  const close=(a,b)=>a===null&&b===null||safeNumber(a,b,1e-6);
  for(const metric of gallery.metrics||[]){
    const provenance=metric.provenance||{},source=sources[provenance.source_id],pointer=provenance.pointer;
    if(!source){issues.push(`${metric.id}: unknown source ${provenance.source_id}`);continue;}
    let pointed;
    try { pointed=pointer?getPointer(source,pointer):undefined; }
    catch(error){issues.push(`${metric.id}: ${error.message}`);continue;}
    if(pointed===undefined){issues.push(`${metric.id}: pointer ${pointer} not found in raw source`);continue;}
    checked++;
    if(!provenance.calculation){
      if(typeof pointed==='number'){
        const expected=pointed*(provenance.source_factor||1);
        if(!close(metric.raw_value,expected)) issues.push(`${metric.id}: raw ${metric.raw_value} != source ${pointed} × ${provenance.source_factor||1}`);
      } else if(metric.raw_value!==null) issues.push(`${metric.id}: non-scalar source requires an explicit calculation`);
    }
  }
  const byId=Object.fromEntries((gallery.metrics||[]).map(metric=>[metric.id,metric]));
  const source=(id)=>sources[id];
  const business=source('synthetic-business-performance'),sales=source('synthetic-sales-conversion'),project=source('synthetic-project-analytics');
  const audit=(id)=>audits[id]||{};
  const expected=[
    ['revenue_gap',(business.metrics[0].actual-business.metrics[0].target)*10000],
    ['revenue_attainment',business.metrics[0].actual/business.metrics[0].target],
    ['revenue_mom',(business.metrics[0].actual-business.metrics[0].previous_month)/business.metrics[0].previous_month],
    ['revenue_yoy',(business.metrics[0].actual-business.metrics[0].previous_year)/business.metrics[0].previous_year],
    ['margin_gap',business.metrics[2].actual-business.metrics[2].target],
    ['conv_aug',audit('synthetic-sales-conversion').cohorts?.[0]?.rate],
    ['conv_sep',audit('synthetic-sales-conversion').cohorts?.[1]?.rate],
    ['conv_delta',(audit('synthetic-sales-conversion').cohorts?.[1]?.rate-audit('synthetic-sales-conversion').cohorts?.[0]?.rate)*100],
    ['mature_rate',audit('synthetic-sales-conversion').cohort?.rate],
    ['trial_yes_rate',audit('synthetic-sales-conversion').branches?.[1]?.yes_wins/audit('synthetic-sales-conversion').branches?.[1]?.yes],
    ['trial_no_rate',audit('synthetic-sales-conversion').branches?.[1]?.no_wins/audit('synthetic-sales-conversion').branches?.[1]?.no],
    ['cost_p1',project.projects[0].actual_days*project.projects[0].day_rate+project.projects[0].external_cost],
    ['cost_p2',project.projects[1].actual_days*project.projects[1].day_rate+project.projects[1].external_cost],
    ['cost_p3',project.projects[2].actual_days*project.projects[2].day_rate+project.projects[2].external_cost],
    ['cost_variance_p1',project.projects[0].actual_days*project.projects[0].day_rate+project.projects[0].external_cost-project.projects[0].budget],
    ['cost_variance_p2',project.projects[1].actual_days*project.projects[1].day_rate+project.projects[1].external_cost-project.projects[1].budget],
    ['cost_variance_p3',project.projects[2].actual_days*project.projects[2].day_rate+project.projects[2].external_cost-project.projects[2].budget],
    ['cost_total',project.projects.reduce((sum,row)=>sum+row.actual_days*row.day_rate+row.external_cost,0)],
    ['budget_total',project.projects.reduce((sum,row)=>sum+row.budget,0)],
    ['cost_variance_total',project.projects.reduce((sum,row)=>sum+row.actual_days*row.day_rate+row.external_cost-row.budget,0)],
  ];
  for(const [id,value] of expected){
    if(value==null||!Number.isFinite(value)) {issues.push(`${id}: calculation inputs unavailable`);continue;}
    if(!close(byId[id]?.raw_value,value)) issues.push(`${id}: raw ${byId[id]?.raw_value} != recomputed ${value}`);
  }
  const percentages=(gallery.metrics||[]).filter(metric=>metric.storage_scale==='fraction'&&metric.type==='percent');
  const pps=(gallery.metrics||[]).filter(metric=>metric.type==='pp');
  const currencies=(gallery.metrics||[]).filter(metric=>metric.type==='currency'&&metric.display_scale?.factor===10000);
  if(!percentages.some(metric=>metric.raw_value>0&&metric.raw_value<1)) issues.push('no raw-fraction percent metric retained');
  if(!pps.length) issues.push('no percentage-point metric declared');
  if(!currencies.length) issues.push('no CNY 万 display-scale metric declared');
  for(const metric of pps) if(!metric.comparison_basis) issues.push(`${metric.id}: pp metric requires comparison_basis`);
  for(const metric of gallery.metrics||[]) if(metric.type==='currency'&&!/^[A-Z]{3}$/.test(metric.currency||'')) issues.push(`${metric.id}: currency must be ISO 4217`);
  return {status:issues.length?'FAIL':'PASS',issues,checked,
    metric_count:(gallery.metrics||[]).length,percent_fraction_metrics:percentages.map(metric=>metric.id),
    percentage_point_metrics:pps.map(metric=>metric.id),currency_display_scale_metrics:currencies.length,
    denominators_declared:(gallery.metrics||[]).filter(metric=>metric.denominator!=null).length,
    time_windows_declared:(gallery.metrics||[]).filter(metric=>metric.time_window).length};
}
function galleryEvidence(spec){
  const slides=Array.isArray(spec.slides)?spec.slides:[];
  const metrics=Array.isArray(spec.metrics)?spec.metrics:[];
  const histogramSlide=slides.find(slide=>slide.type==='histogram');
  let histogram={status:'NOT_RUN',reason:'no histogram slide'};
  if(histogramSlide){
    const bins=Array.isArray(histogramSlide.bins)?histogramSlide.bins:[];
    const labels=histogramSlide.series?.[0]?.labels||[];
    const values=histogramSlide.series?.[0]?.values||[];
    const width=bins.length?bins[0].end-bins[0].start:null;
    const contiguous=bins.length>1&&bins.every((bin,index)=>index===0||bin.start===bins[index-1].end);
    const equal=bins.length>0&&bins.every(bin=>bin.end-bin.start===width);
    const labelsMatch=bins.length>0&&bins.length===labels.length&&bins.every((bin,index)=>labels[index]===`${bin.start}–${bin.end}`);
    const valuesMatch=bins.length>0&&bins.length===values.length&&bins.every((bin,index)=>values[index]===bin.count);
    const countSum=bins.reduce((sum,bin)=>sum+(Number.isFinite(bin.count)?bin.count:0),0);
    const insight=String(histogramSlide.insight||'');
    histogram={status:contiguous&&equal&&labelsMatch&&valuesMatch?'PASS':'FAIL',bins:bins.length,width,
      first:bins[0]||null,last:bins.at(-1)||null,contiguous,equal_width:equal,labels_match:labelsMatch,values_match:valuesMatch,
      count_sum:countSum,zero_bins:bins.filter((bin,index)=>values[index]===0).map(bin=>`${bin.start}–${bin.end}`),
      period:String(histogramSlide.period||''),window_note:/仅观察到|未观察|不按 0 推断/.test(insight),insight};
  }
  const dashboards=slides.filter(slide=>slide.dashboard).map(slide=>({
    title:slide.title||null,unit:slide.dashboard.unit||null,labels:(slide.dashboard.labels||[]).length,
    series:(slide.dashboard.series||[]).map(series=>({name:series.name||null,metric_ids:(series.metric_ids||[]).length}))}));
  const cohorts=metrics.filter(metric=>/cohort/i.test(String(metric.comparison_basis||''))||/成熟/.test(String(metric.time_window||'')))
    .map(metric=>({id:metric.id,type:metric.type,denominator:metric.denominator??null,time_window:metric.time_window||null,comparison_basis:metric.comparison_basis||null}));
  const comparisonBases=[...new Set(metrics.map(metric=>metric.comparison_basis).filter(Boolean))].sort();
  const longTitles=slides.filter(slide=>String(slide.title||'').length>=40)
    .map(slide=>({title:slide.title,length:slide.title.length,title_short:Boolean(slide.title_short),subtitle:Boolean(slide.subtitle)}));
  return {
    histogram,dashboards,cohorts,comparison_bases:comparisonBases,
    title_fit:{max_length:Math.max(0,...slides.map(slide=>String(slide.title||'').length)),long_titles:longTitles,
      title_short_count:slides.filter(slide=>slide.title_short).length,subtitle_count:slides.filter(slide=>slide.subtitle).length},
  };
}
async function buildGallery(outRoot,opts){
  const specPath=path.join(FIXTURE_ROOT,'gallery-deck.json');
  const spec=readJson(specPath);
  const variants={};
  for(const profile of ['executive-dense','dark-executive','corporate']){
    const dir=path.join(outRoot,'gallery',profile); fs.mkdirSync(dir,{recursive:true});
    const pptx=path.join(dir,`gallery-${profile}.pptx`);
    try {
      const built=await buildDeck(spec,pptx,{profile,specDir:FIXTURE_ROOT});
      const scene=readJson(built.scene);
      const render=await renderCase(pptx,specPath,built.scene,profile,path.join(dir,'render'),`gallery-${profile}`,opts);
      const transformations=built.semantics?.transformations||scene.metric_semantics?.transformations||[];
      variants[profile]={status:render.qa.status==='FAIL'?'FAIL':'PASS',profile,slides:built.slides,
        spec:artifact(specPath,outRoot),pptx:artifact(pptx,outRoot),scene:artifact(built.scene,outRoot),
        narrative:{status:built.narrative.status,errors:built.narrative.errors,redundancy:built.narrative.redundancy,review_required:built.narrative.review_required,coverage:built.narrative.coverage},
        visual_encoding:{charts:scene.visual_encoding.plans.length,validation:scene.visual_encoding.validation.map(item=>item.status)},
        display_scale_transformations:transformations.filter(item=>item.kind==='display-scale').map(item=>({slide:item.slide,factor:item.factor,to:item.to})),
        qa:render.qa.status,checks:render.qa.checks,visual_qa:render.qa.visual_qa,
        render:renderArtifacts(render.render,outRoot),contact_sheets:render.contact_sheets.map(sheet=>sheetArtifact(sheet,outRoot))};
    } catch(error){ variants[profile]={status:'FAIL',profile,error:error.message}; }
  }
  const sources={};for(const item of SCENARIOS) sources[item.id]=readJson(path.join(INPUT_ROOT,item.input));
  const audits={};for(const item of SCENARIOS) audits[item.id]=analyze(sources[item.id]).audit.metrics;
  const reconciliation=metricReconciliation(spec,sources,audits);
  const narrativeCheck=inspectNarrative(spec);
  return {status:Object.values(variants).every(item=>item.status==='PASS')&&reconciliation.status==='PASS'?'PASS':'FAIL',
    spec:artifact(specPath,outRoot),variants,reconciliation,narrative:{status:narrativeCheck.status,errors:narrativeCheck.errors,redundancy:narrativeCheck.redundancy,review_required:narrativeCheck.review_required,coverage:narrativeCheck.coverage},
    ...galleryEvidence(spec),
    title_lengths:spec.slides.map(slide=>(slide.title||'').length),max_title_length:Math.max(...spec.slides.map(slide=>(slide.title||'').length))};
}
async function buildLedger(outRoot,opts){
  const specPath=path.join(FIXTURE_ROOT,'ledger-deck.json');
  const spec=readJson(specPath);
  const dir=path.join(outRoot,'ledger'); fs.mkdirSync(dir,{recursive:true});
  const pptx=path.join(dir,'ledger-executive-dense.pptx');
  const built=await buildDeck(spec,pptx,{profile:'executive-dense',specDir:FIXTURE_ROOT});
  const render=await renderCase(pptx,specPath,built.scene,'executive-dense',path.join(dir,'render'),'ledger',opts);
  const narrative=built.narrative;
  const expectedTables=readJson(path.join(INPUT_ROOT,'source-ledger.json'));
  const issues=[];
  if(narrative.redundancy?.length!==1) issues.push(`expected one deliberate redundancy candidate, got ${narrative.redundancy?.length||0}`);
  if(narrative.redundancy?.[0]?.kind!=='same_claims_and_evidence') issues.push('redundancy candidate kind changed');
  if(!narrative.review_required) issues.push('ledger narrative must still require review');
  if(!Array.isArray(narrative.bindings)||!narrative.bindings.length||narrative.bindings.some(binding=>binding.disposition==='rejected')) issues.push('ledger evidence was not retained');
  const rows=spec.slides[2].rows.concat(spec.slides[3].rows).flat();
  for(const doc of expectedTables.documents){
    if(!rows.some(value=>String(value).includes(doc.path))) issues.push(`ledger deck missing ${doc.path}`);
    if(!rows.some(value=>String(value).includes(doc.sha256.slice(0,12)))) issues.push(`ledger deck missing hash prefix for ${doc.id}`);
  }
  return {status:issues.length||render.qa.status==='FAIL'?'FAIL':'PASS',spec:artifact(specPath,outRoot),pptx:artifact(pptx,outRoot),scene:artifact(built.scene,outRoot),
    narrative:{status:narrative.status,errors:narrative.errors,redundancy:narrative.redundancy,review_required:narrative.review_required,coverage:narrative.coverage,bindings:narrative.bindings},
    qa:render.qa.status,checks:render.qa.checks,visual_qa:render.qa.visual_qa,render:renderArtifacts(render.render,outRoot),
    contact_sheets:render.contact_sheets.map(sheet=>sheetArtifact(sheet,outRoot)),issues};
}

function scenarioGate({scenarios,sourceLedgerCheck,fingerprint,baseline}){
  if(!baseline) return 'NOT_RUN';
  const compared=Array.isArray(scenarios)&&scenarios.length>0&&scenarios.every(item=>
    item.before?.status==='PASS'&&item.after?.status==='PASS'&&
    ['PASS','PASS_WITH_NOTES'].includes(item.comparison?.status)&&item.comparison?.same_raw_bytes===true);
  return compared&&sourceLedgerCheck?.status==='PASS'&&Boolean(fingerprint?.aggregate_sha256)?'PASS':'FAIL';
}

const list=value=>Array.isArray(value)?value:[];
const passStatus=value=>value==='PASS'||value==='PASS_WITH_NOTES';
function matrixThemeCells(matrix,theme,path){return list(matrix?.themes?.[theme]?.readback?.cells).filter(path);}
function galleryVariant(gallery,profile){return gallery?.variants?.[profile]||null;}

function timelineSpacing(output){
  const evidence=output?.evidence||{};
  const positions=list(evidence.marker_positions);
  const dates=list(evidence.date_labels);
  if(positions.length!==dates.length||positions.length<2) return {status:'FAIL',reason:'marker/date count mismatch'};
  const epoch=dates.map(date=>Date.parse(`${date}T00:00:00Z`));
  if(epoch.some(value=>!Number.isFinite(value))) return {status:'FAIL',reason:'date label is not a real ISO date'};
  const x0=positions[0].x,xN=positions.at(-1).x,d0=epoch[0],dN=epoch.at(-1);
  if(!(xN>x0)||!(dN>d0)) return {status:'FAIL',reason:'axis is not increasing'};
  const pairs=positions.map((position,index)=>{
    const xRatio=(position.x-x0)/(xN-x0),dateRatio=(epoch[index]-d0)/(dN-d0);
    return {id:position.id,date:dates[index],x_ratio:Number(xRatio.toFixed(6)),date_ratio:Number(dateRatio.toFixed(6)),
      delta:Number(Math.abs(xRatio-dateRatio).toFixed(6)),label_lane:position.label_lane??0};
  });
  const ok=pairs.every(pair=>pair.delta<=0.005)&&positions.every((position,index)=>index===0||position.x>positions[index-1].x);
  return {status:ok?'PASS':'FAIL',pairs};
}

function relationshipContractEntries(relationships){
  if(!relationships) {
    const reason='Relationship evidence is produced after the standalone benchmark by tests/build_relationships.js in the showcase pipeline. Run npm run showcase.';
    return [
      ['H','Are actual time distances preserved?'],
      ['I','Are branches/roles preserved?'],
      ['J','Are dependencies inspectable?'],
    ].map(([id,question])=>({id,question,scope:['data','geometry','native','render'],status:'NOT_RUN',
      evidence:['out/v1.3-showcase/relationships/manifest.json','tests/test_relationships.js'],checks:{reason},visual_review:'NOT_RUN'}));
  }
  const outputs=list(relationships.outputs);
  const output=(name,theme)=>outputs.find(item=>item.case===name&&item.theme===theme);
  const ready=relationships.status==='PASS'&&outputs.length===8&&outputs.every(item=>
    item.render?.status==='PASS'&&list(item.render.pages).length>0&&item.qa?.status!=='FAIL');
  const timelines=['dated-timeline','dated-timeline-close'].flatMap(name=>['light','dark'].map(theme=>output(name,theme))).filter(Boolean);
  const spacing=timelines.map(item=>({case:item.case,theme:item.theme,...timelineSpacing(item),
    durations:list(item.evidence?.durations),label_lanes:[...new Set(list(item.evidence?.marker_positions).map(marker=>marker.label_lane??0))].sort(),
    leaders:list(item.evidence?.leaders)}));
  const close=spacing.filter(item=>item.case==='dated-timeline-close');
  const durationTimeline=spacing.filter(item=>item.case==='dated-timeline');
  const hOk=ready&&timelines.length===4&&spacing.every(item=>item.status==='PASS')&&
    durationTimeline.every(item=>item.durations.length>0&&item.durations.every(duration=>Number.isInteger(duration.days)&&duration.days>0))&&
    close.every(item=>item.label_lanes.length>1&&item.leaders.length>0);
  const branches=outputs.filter(item=>item.case==='branch-swimlane');
  const branchChecks=branches.map(item=>{
    const nodes=list(item.evidence?.task_nodes);
    return {theme:item.theme,task_nodes:nodes.length,owners:[...new Set(nodes.map(node=>node.owner).filter(Boolean))],
      statuses:[...new Set(nodes.map(node=>node.status).filter(Boolean))],swimlanes:list(item.evidence?.swimlane_labels),
      decision_edges:list(item.evidence?.decision_edges),dependencies:list(item.evidence?.dependencies).length};
  });
  const iOk=ready&&branches.length===2&&branchChecks.every(item=>
    item.task_nodes===5&&item.owners.length>0&&item.statuses.length>0&&item.swimlanes.length>=3&&
    item.decision_edges.length>=4&&item.dependencies>0);
  const roadmaps=outputs.filter(item=>item.case==='roadmap');
  const jOk=ready&&iOk&&roadmaps.length===2&&roadmaps.every(item=>list(item.evidence?.lane_headings).length>=3);
  const evidencePaths=outputs.map(item=>item.pptx?.path).filter(Boolean)
    .filter((value,index,all)=>all.indexOf(value)===index);
  const shared={visual_review:'NOT_RUN'};
  return [
    {
      id:'H',question:'Are actual time distances preserved?',scope:['data','geometry','native','render'],
      status:hOk?'PASS':'FAIL',
      evidence:[...evidencePaths,'out/v1.3-showcase/relationships/manifest.json','tests/test_relationships.js'],
      checks:{timeline_spacing:spacing,close_date_lanes:close.map(item=>({case:item.case,theme:item.theme,label_lanes:item.label_lanes,leaders:item.leaders})),
        duration_labels:durationTimeline.map(item=>({case:item.case,theme:item.theme,durations:item.durations})),...shared},
      visual_review:'NOT_RUN',
    },
    {
      id:'I',question:'Are branches/roles preserved?',scope:['data','geometry','native','render'],
      status:iOk?'PASS':'FAIL',
      evidence:[...evidencePaths.filter(value=>/branch-swimlane/.test(value)),'out/v1.3-showcase/relationships/manifest.json','tests/test_relationships.js'],
      checks:{branches:branchChecks,cycle_dangling_rejections:'tests/test_relationships.js',...shared},
      visual_review:'NOT_RUN',
    },
    {
      id:'J',question:'Are dependencies inspectable?',scope:['data','geometry','native','render'],
      status:jOk?'PASS':'FAIL',
      evidence:[...evidencePaths.filter(value=>/branch-swimlane|roadmap/.test(value)),'out/v1.3-showcase/relationships/manifest.json','tests/test_relationships.js'],
      checks:{roadmap_lanes:roadmaps.map(item=>({theme:item.theme,headings:list(item.evidence?.lane_headings)})),
        branch_dependencies:branchChecks.map(item=>({theme:item.theme,dependencies:item.dependencies})),
        declared_iso_order:'tests/test_relationships.js',cycle_dangling_rejections:'tests/test_relationships.js',...shared},
      visual_review:'NOT_RUN',
    },
  ];
}

function applyRelationshipEvidence(contract,relationships){
  const replacements=new Map(relationshipContractEntries(relationships).map(item=>[item.id,item]));
  const updated=list(contract).map(item=>replacements.get(item.id)||item);
  if(relationships){
    const outputs=list(relationships.outputs);
    const cases=[...new Set(outputs.map(item=>item.case))].sort();
    const paired=cases.filter(name=>['light','dark'].every(theme=>{
      const item=outputs.find(candidate=>candidate.case===name&&candidate.theme===theme);
      return item?.render?.status==='PASS'&&list(item.render.pages).length>0&&item.qa?.status!=='FAIL';
    }));
    const specParity=cases.every(name=>{
      const shas=['light','dark'].map(theme=>outputs.find(item=>item.case===name&&item.theme===theme)?.spec?.sha256).filter(Boolean);
      return shas.length===2&&new Set(shas).size===1;
    });
    const reuse={status:relationships.status,outputs:outputs.length,cases,paired_themes:paired,
      spec_sha256_parity:specParity,visual_review:'NOT_RUN'};
    const themeEntry=updated.find(item=>item.id==='M');
    if(themeEntry){
      themeEntry.checks={...themeEntry.checks,relationships:reuse};
      if(relationships.status!=='PASS'||paired.length!==cases.length||!specParity) themeEntry.status='FAIL';
    }
    const traceEntry=updated.find(item=>item.id==='N');
    if(traceEntry) traceEntry.checks={...traceEntry.checks,relationships:{status:relationships.status,fixture:relationships.fixture||null,outputs:outputs.length}};
  }
  return updated;
}

function contractMatrix({matrix,gallery,ledger,scenarios,sourceLedgerCheck,fingerprint,baseline,relationships=null}){
  const entry=(id,question,scope,status,evidence,checks,extra={})=>({id,question,scope,status,evidence,checks,...extra});
  const lineMulti=['light','dark'].flatMap(theme=>matrixThemeCells(matrix,theme,cell=>cell.family==='line'&&cell.case==='multi'));
  const lineThemeOk=theme=>{
    const counts=matrix?.themes?.[theme]?.readback?.counts||{};
    return (counts.dash_checked||0)>=2&&(counts.marker_checked||0)>=2;
  };
  const linePaintOk=['light','dark'].every(theme=>passStatus(matrix?.themes?.[theme]?.checks?.semantic_qa));
  const aOk=matrix?.status==='PASS'&&lineMulti.length===2&&lineMulti.every(cell=>cell.status==='PASS')&&
    ['light','dark'].every(lineThemeOk)&&linePaintOk;
  const grouped=['light','dark'].flatMap(theme=>matrixThemeCells(matrix,theme,cell=>['bar','column'].includes(cell.family)&&cell.case==='multi'));
  const groupingChecked=['light','dark'].reduce((sum,theme)=>sum+(matrix?.themes?.[theme]?.readback?.counts?.grouping_checked||0),0);
  const bOk=matrix?.status==='PASS'&&grouped.length===4&&grouped.every(cell=>cell.status==='PASS')&&groupingChecked>=4;
  const pieRejects=list(matrix?.rejections?.results).filter(item=>['PIE_SINGLE_SERIES','PIE_NONNEGATIVE','PIE_MISSING'].includes(item.code)&&item.status==='PASS');
  const pieAccepted=['light','dark'].flatMap(theme=>matrixThemeCells(matrix,theme,cell=>['pie','doughnut'].includes(cell.family)));
  const piePercent=pieAccepted.filter(cell=>cell.case==='percentage');
  const cOk=matrix?.rejections?.status==='PASS'&&new Set(pieRejects.map(item=>item.code)).size===3&&
    pieAccepted.length>0&&pieAccepted.every(cell=>cell.status==='PASS')&&piePercent.length>0&&
    piePercent.every(cell=>String(cell.native?.format||'').includes('%'));
  const dashboards=list(gallery?.dashboards);
  const dOk=gallery?.status==='PASS'&&gallery?.reconciliation?.status==='PASS'&&dashboards.length>0&&
    dashboards.every(item=>item.unit&&item.labels>0&&item.series.length>0&&item.series.every(series=>series.metric_ids>0));
  const percentageCells=['light','dark'].flatMap(theme=>matrixThemeCells(matrix,theme,cell=>cell.case==='percentage'));
  const eOk=gallery?.reconciliation?.status==='PASS'&&list(gallery?.reconciliation?.percent_fraction_metrics).length>0&&
    list(gallery?.reconciliation?.percentage_point_metrics).length>0&&percentageCells.length>0&&
    percentageCells.every(cell=>cell.status==='PASS'&&String(cell.native?.format||'').includes('%'));
  const cohorts=list(gallery?.cohorts);
  const cohortDenominators=new Set(cohorts.map(item=>item.denominator).filter(value=>value!=null));
  const salesScenario=list(scenarios).find(item=>item.slug==='sales-conversion');
  const fOk=gallery?.status==='PASS'&&gallery?.reconciliation?.status==='PASS'&&
    [20,10,30,7,23].every(value=>cohortDenominators.has(value))&&
    list(gallery?.comparison_bases).includes('mature_cohort')&&list(gallery?.comparison_bases).includes('descriptive_branch_not_causal')&&
    salesScenario?.after?.status==='PASS'&&salesScenario?.comparison?.same_raw_bytes===true;
  const histogram=gallery?.histogram||{status:'NOT_RUN'};
  const gOk=matrix?.supplemental?.status==='PASS'&&histogram.status==='PASS'&&histogram.bins===9&&
    histogram.width===7&&histogram.first?.start===0&&histogram.last?.end===63&&histogram.count_sum===40&&
    histogram.zero_bins?.length>=2&&histogram.window_note===true;
  const denseCells=['light','dark'].flatMap(theme=>matrixThemeCells(matrix,theme,cell=>cell.case==='dense'));
  const sampleVariant=galleryVariant(gallery,'dark-executive')||galleryVariant(gallery,'executive-dense');
  const renderedPages=(gallery?.variants?Object.values(gallery.variants):[]).reduce((sum,item)=>sum+list(item?.render?.pages).length,0);
  const kOk=gallery?.status==='PASS'&&gallery?.title_fit?.max_length>=40&&
    list(gallery?.title_fit?.long_titles).every(item=>item.title_short)&&gallery?.title_fit?.title_short_count>0&&
    gallery?.title_fit?.subtitle_count>0&&denseCells.length===4&&denseCells.every(cell=>cell.status==='PASS')&&
    (sampleVariant?.checks?.fonts||'FAIL')!=='FAIL'&&(sampleVariant?.checks?.spatial||'FAIL')!=='FAIL'&&renderedPages>0;
  const ledgerBindings=list(ledger?.narrative?.bindings);
  const lOk=ledger?.status==='PASS'&&list(ledger?.narrative?.redundancy).length===1&&
    ledger?.narrative?.review_required===true&&ledgerBindings.length>0&&ledgerBindings.every(binding=>binding.disposition==='retained')&&
    list(sourceLedgerCheck?.documents).length===3;
  const galleryProfiles=['executive-dense','corporate','dark-executive'];
  const mOk=galleryProfiles.every(profile=>gallery?.variants?.[profile]?.status==='PASS')&&
    Object.keys(matrix?.themes||{}).length===2&&Object.values(matrix?.themes||{}).every(item=>item.status==='PASS');
  const nStatus=scenarioGate({scenarios,sourceLedgerCheck,fingerprint,baseline});
  const contract=[
    entry('A','Are multiple lines distinguishable?',['native','data','render'],aOk?'PASS':'FAIL',
      ['matrix/light.pptx','matrix/dark.pptx','matrix/contact-light-1.png','matrix/contact-dark-1.png','tests/test_semantic_qa.js'],
      {line_multi:lineMulti.map(cell=>({id:cell.id,theme:cell.theme,series_names:cell.native?.series_names,series_styles:cell.native?.series_styles})),
        dash_marker_checked:{light:matrix?.themes?.light?.readback?.counts?.dash_checked||0,dark:matrix?.themes?.dark?.readback?.counts?.dash_checked||0},
        native_paint_qa:{light:matrix?.themes?.light?.checks?.semantic_qa||'NOT_RUN',dark:matrix?.themes?.dark?.checks?.semantic_qa||'NOT_RUN'},
        visual_encoding:{light:list(matrix?.themes?.light?.readback?.deck_issues),dark:list(matrix?.themes?.dark?.readback?.deck_issues)},
        rendered_pages:{light:list(matrix?.themes?.light?.render?.pages).length,dark:list(matrix?.themes?.dark?.render?.pages).length},
        visual_review:'NOT_RUN'}),
    entry('B','Are grouped bars/columns comparable?',['native','data','render'],bOk?'PASS':'FAIL',
      ['matrix/light.pptx','matrix/dark.pptx','matrix/contact-light-1.png','matrix/contact-dark-1.png'],
      {grouped_cells:grouped.map(cell=>({id:cell.id,theme:cell.theme,grouping:cell.native?.grouping,series_names:cell.native?.series_names,values:cell.native?.values})),
        grouping_checked:groupingChecked,visual_review:'NOT_RUN'}),
    entry('C','Are composition values/labels truthful?',['native','data','render'],cOk?'PASS':'FAIL',
      ['matrix/light.pptx','matrix/dark.pptx','matrix/rejects/rejections.log','skill/examples/v1.3/matrix-cases.json'],
      {accepted_pie_like:pieAccepted.map(cell=>({id:cell.id,case:cell.case,status:cell.status,format:cell.native?.format})),
        expected_rejections:pieRejects.map(item=>({id:item.id,code:item.code,observed_error:item.observed_error})),
        dense_category_rejections:list(matrix?.rejections?.results).filter(item=>item.case==='dense'&&item.status==='PASS').length,
        visual_review:'NOT_RUN'}),
    entry('D','Does the dashboard retain units and comparisons?',['native','data','render'],dOk?'PASS':'FAIL',
      ['gallery/executive-dense/gallery-executive-dense.pptx','gallery/executive-dense/gallery-executive-dense.pptx.scene.json','skill/examples/v1.3/gallery-deck.json'],
      {dashboards,comparison_bases:list(gallery?.comparison_bases),display_scale_transformations:list(galleryVariant(gallery,'executive-dense')?.display_scale_transformations).length,
        checks:galleryVariant(gallery,'executive-dense')?.checks||null,visual_review:'NOT_RUN'}),
    entry('E','Are percentages distinct from pp?',['native','data'],eOk?'PASS':'FAIL',
      ['skill/examples/v1.3/gallery-deck.json','matrix/light.pptx','tests/test_numeric_fidelity.js'],
      {percent_fraction_metrics:list(gallery?.reconciliation?.percent_fraction_metrics),
        percentage_point_metrics:list(gallery?.reconciliation?.percentage_point_metrics),
        matrix_percentage_cells:percentageCells.map(cell=>({id:cell.id,theme:cell.theme,format:cell.native?.format})),
        reconciliation:gallery?.reconciliation?.status||'NOT_RUN'}),
    entry('F','Are sales denominators/cohorts correct?',['data','render'],fOk?'PASS':'FAIL',
      ['skill/examples/v1.3/gallery-deck.json','scenarios/sales-conversion/input.json','tests/test_analytics.js'],
      {cohorts,comparison_bases:list(gallery?.comparison_bases),sales_scenario:salesScenario?{after:salesScenario.after?.status,comparison:salesScenario.comparison?.status,same_raw_bytes:salesScenario.comparison?.same_raw_bytes}:null,
        causal_inference:'not claimed'}),
    entry('G','Does a histogram use real numeric bins?',['data','native','render'],gOk?'PASS':'FAIL',
      ['skill/examples/v1.3/gallery-deck.json','matrix/supplemental/supplemental.pptx','matrix/supplemental/qa-supplemental.json','tests/test_v13_foundation.js'],
      {gallery_histogram:histogram,supplemental:{labels:matrix?.supplemental?.checks?.histogram_labels,counts:matrix?.supplemental?.checks?.histogram_counts},
        unequal_bin_negative_tests:'tests/test_v13_foundation.js'}),
    entry('H','Are actual time distances preserved?',['data','geometry','render'],'NOT_RUN',
      ['out/v1.3-showcase/relationships/manifest.json','tests/test_relationships.js'],
      {reason:'Relationship evidence is built after the standalone benchmark in the showcase pipeline.'},{visual_review:'NOT_RUN'}),
    entry('I','Are branches/roles preserved?',['data','geometry','render'],'NOT_RUN',
      ['out/v1.3-showcase/relationships/manifest.json','tests/test_relationships.js'],
      {reason:'Relationship evidence is built after the standalone benchmark in the showcase pipeline.'},{visual_review:'NOT_RUN'}),
    entry('J','Are dependencies inspectable?',['data','geometry','render'],'NOT_RUN',
      ['out/v1.3-showcase/relationships/manifest.json','tests/test_relationships.js'],
      {reason:'Relationship evidence is built after the standalone benchmark in the showcase pipeline.'},{visual_review:'NOT_RUN'}),
    entry('K','Are long titles and dense evidence readable?',['data','geometry','render'],kOk?'PASS':'FAIL',
      ['gallery/executive-dense/gallery-executive-dense.pptx','matrix/light.pptx','matrix/contact-light-1.png','tests/test_v13_foundation.js'],
      {title_fit:gallery?.title_fit||null,max_title_length:gallery?.max_title_length??null,dense_cells:denseCells.map(cell=>({id:cell.id,theme:cell.theme,status:cell.status})),
        rendered_pages:renderedPages,visual_review:'NOT_RUN',
        limit:'Structural fit and actual pages exist; readability still requires independent visual review.'},
      {visual_review:'NOT_RUN'}),
    entry('L','Is multi-document evidence retained?',['data','geometry'],lOk?'PASS':'FAIL',
      ['ledger/ledger-executive-dense.pptx','ledger/ledger-executive-dense.pptx.scene.json','source-ledger.json','tests/test_narrative.js'],
      {documents:list(sourceLedgerCheck?.documents).length,redundancy:ledger?.narrative?.redundancy,review_required:ledger?.narrative?.review_required,
        bindings:ledgerBindings.map(binding=>({evidence_id:binding.evidence_id,slide:binding.slide,disposition:binding.disposition})),issues:ledger?.issues}),
    entry('M','Is the same content usable across themes?',['native','render'],mOk?'PASS':'FAIL',
      ['gallery/executive-dense/gallery-executive-dense.pptx','gallery/corporate/gallery-corporate.pptx','gallery/dark-executive/gallery-dark-executive.pptx',
        'matrix/light.pptx','matrix/dark.pptx'],
      {gallery_profiles:galleryProfiles.map(profile=>({profile,status:gallery?.variants?.[profile]?.status,spec_sha256:gallery?.variants?.[profile]?.spec?.sha256})),
        matrix_themes:Object.entries(matrix?.themes||{}).map(([theme,item])=>({theme,status:item.status})),relationships:null,visual_review:'NOT_RUN'}),
    entry('N','Can evidence be traced to source/version?',['data','source'],nStatus,
      ['scenarios/','engine-source-fingerprint.json','source-ledger.json','showcase.manifest.json','checksums.sha256'],
      {baseline:baseline?{version:baseline.version,fingerprint:baseline.fingerprint?.aggregate_sha256,immutable:baseline.immutable}:null,
        scenarios:list(scenarios).map(item=>({slug:item.slug,before:item.before?.status,after:item.after?.status,comparison:item.comparison?.status,same_raw_bytes:item.comparison?.same_raw_bytes})),
        source_ledger:sourceLedgerCheck?.status||'NOT_RUN',fingerprint:fingerprint?.aggregate_sha256||null,
        artifact_manifests:'roles/specs/PPTX/scenes/renders are hashed in showcase.manifest.json; checksums.sha256 covers the output tree.'}),
  ];
  return applyRelationshipEvidence(contract,relationships);
}

async function main(){
  const args=process.argv.slice(2);
  const opts={};
  for(let index=0;index<args.length;index++){
    const arg=args[index];
    if(arg==='--out-root') opts.outRoot=args[++index];
    else if(arg==='--baseline-root') opts.baselineRoot=args[++index];
    else if(arg==='--no-render') opts.render=false;
    else if(arg==='--no-qa') opts.qa=false;
    else if(arg==='--help'||arg==='-h') {console.log('usage: node scripts/v13_benchmark.js [--out-root DIR] [--baseline-root DIR] [--no-render] [--no-qa]');return;}
    else throw new Error(`Unknown argument ${arg}`);
  }
  opts.render=opts.render!==false; opts.qa=opts.qa!==false;
  const outRoot=prepareOutRoot(opts.outRoot||path.join(ROOT,'out/v1.3-showcase'));
  const logDir=path.join(outRoot,'logs'); fs.mkdirSync(logDir,{recursive:true});
  opts.logDir=logDir;
  const fixture=generateMatrixFixture();
  const declared=readJson(path.join(FIXTURE_ROOT,'matrix-cases.json'));
  if(JSON.stringify(fixture)!==JSON.stringify(declared)) throw new Error('matrix-cases.json differs from the benchmark generator');
  const fingerprint=currentFingerprint();
  writeJson(path.join(outRoot,'engine-source-fingerprint.json'),fingerprint);
  const ledgerCheck=checkSourceLedger(outRoot);
  let baseline=null,scenarios=[];
  if(opts.baselineRoot){
    const base=path.resolve(opts.baselineRoot);
    if(!exists(path.join(base,'scripts/analyze.js'))) throw new Error(`Baseline source not found at ${base}`);
    const fingerprintBefore=baselineFingerprint(base);
    const manifestPath=path.join(path.dirname(base),'baseline-source-manifest.json');
    const sourceManifest=exists(manifestPath)?readJson(manifestPath):null;
    baseline={path:publicPath(base,outRoot),version:readJson(path.join(base,'package.json')).version,fingerprint:fingerprintBefore,
      declared_commit:sourceManifest?.commit||null,declared_archive_sha256:sourceManifest?.archive_sha256||null,immutable:true};
    scenarios=[];
    for(const item of SCENARIOS) scenarios.push(await buildScenario(item,outRoot,base,opts));
    baseline.immutable=baselineFingerprint(base).aggregate_sha256===fingerprintBefore.aggregate_sha256;
  } else {
    for(const item of SCENARIOS) scenarios.push(await buildScenario(item,outRoot,null,opts));
  }
  const matrix=await buildMatrix(outRoot,fixture,opts);
  const gallery=await buildGallery(outRoot,opts);
  const ledger=await buildLedger(outRoot,opts);
  const contract=contractMatrix({matrix,gallery,ledger,scenarios,sourceLedgerCheck:ledgerCheck,fingerprint,baseline});
  const sanitized=sanitizeReports(outRoot);
  const scenarioStatus=baseline&&scenarios.every(item=>item.before.status==='PASS'&&item.after.status==='PASS')?'PASS':baseline?'FAIL':'NOT_RUN';
  for(const item of scenarios) item.status=!baseline?'NOT_RUN':(item.after.status==='PASS'&&item.before.status==='PASS'&&['PASS','PASS_WITH_NOTES'].includes(item.comparison.status)?'PASS':'FAIL');
  const manifest={
    schema_version:'1.3',benchmark:'v13-benchmark',product:'Goujian Strategy Slides',version:readJson(path.join(ROOT,'package.json')).version,
    generated_at:new Date().toISOString(),
    source:{branch:runProcess('git',['branch','--show-current'],{cwd:ROOT}).stdout.trim(),head:runProcess('git',['rev-parse','HEAD'],{cwd:ROOT}).stdout.trim(),
      dirty:runProcess('git',['status','--porcelain'],{cwd:ROOT}).stdout.trim().length>0,
      dirty_note:'The live checkout is dirty by construction during development; the aggregate fingerprint binds the actual generated code.'},
    engine_source_fingerprint:{path:'engine-source-fingerprint.json',aggregate_sha256:fingerprint.aggregate_sha256,file_count:fingerprint.file_count},
    baseline:baseline?{...baseline,fingerprint:{aggregate_sha256:baseline.fingerprint.aggregate_sha256,file_count:baseline.fingerprint.file_count,path:'baseline-source-fingerprint.json'}}:null,
    source_ledger:{path:'source-ledger.json',status:ledgerCheck.status,documents:ledgerCheck.documents},
    sanitization:{applied_to:sanitized,rule:'Repository and home prefixes in QA/render JSON were replaced with repo-relative, ~ or $TMP markers. PPTX bytes, QA statuses and numeric values were not changed.'},
    matrix,gallery,ledger,scenarios,contract_matrix:contract,
    contract_note:'A–N maps the user questions in docs/BENCHMARKS_V1_3.md to actual fixtures and renders. PASS covers automated structural/native/render evidence only; visual and semantic judgment remains NOT_RUN.',
    legacy_benchmark:{script:'scripts/benchmark.py',preserved:true,status:'NOT_RERUN',note:'The existing generic 15-case benchmark remains unchanged; this V1.3 script is a targeted supplement.'},
    qa:{visual_qa:'NOT_RUN',note:'Quality Gate structural and semantic checks only. No VisionPASS is claimed; rendered pages still require independent visual review.'},
    review:{status:'NOT_RUN',note:'Codex remains the sole release acceptor. Source authenticity, rights and visual judgment remain review-required.'},
    limits:[
      'All fixtures are synthetic/project-authored; no company, customer, personal or third-party asset is included.',
      'Matrix rendering batches accepted cells into two theme decks; rejected cells are asserted without producing misleading PPTX output.',
      'Native PowerPoint on Windows/macOS/ARM64 and host Agensi execution are NOT_RUN.',
      'Visual review is NOT_RUN; structural QA and montage inspection are not a VisionPASS.',
      'Before/after uses the supplied immutable V1.2.1 source with NODE_PATH pointing at current installed modules; no download is triggered.',
    ],
  };
  if(baseline) writeJson(path.join(outRoot,'baseline-source-fingerprint.json'),baseline.fingerprint);
  if(baseline) delete manifest.baseline.fingerprint.files;
  writeJson(path.join(outRoot,'showcase.manifest.json'),manifest);
  writeText(path.join(outRoot,'README.md'),[
    '# Goujian Strategy Slides V1.3 benchmark showcase','',
    `Generated from package ${manifest.version}. Source head ${manifest.source.head||'UNKNOWN'} (${manifest.source.dirty?'dirty checkout':'clean checkout'}).`,'',
    `- Matrix: ${matrix.tested_cells} declared cells, ${matrix.accepted_cells} accepted, ${matrix.rejected_cell_count} rejected; native families ${matrix.native_family_count}.`,
    `- Matrix decks: light ${matrix.themes.light?.accepted_cells??0} slides, dark ${matrix.themes.dark?.accepted_cells??0} slides; contact sheets are split into <=12 pages.`,
    `- Scenarios: ${scenarios.map(item=>`${item.slug} (before ${item.before.status}, after ${item.after.status})`).join('; ')}.`,
    `- Gallery: ${Object.values(gallery.variants).filter(item=>item.status==='PASS').length}/3 theme variants; ledger narrative review ${ledger.narrative.status}.`,'',
    'Hard limits: visual review is NOT_RUN; source authenticity and rights are NOT_RUN; native Windows/macOS/ARM64 PowerPoint is NOT_RUN. All content is synthetic/project-authored. Do not cite this showcase as publication approval.','',
    'Reproduce: `node scripts/v13_benchmark.js --out-root out/v1.3-showcase --baseline-root out/v13-control/baseline-source-v1.2.1`','',
  ].join('\n')+'\n');
  const files=walk(outRoot,file=>path.basename(file)!=='checksums.sha256').sort((a,b)=>rel(a).localeCompare(rel(b)));
  writeText(path.join(outRoot,'checksums.sha256'),files.map(file=>`${shaFile(file)}  ${path.relative(outRoot,file).split(path.sep).join('/')}`).join('\n')+'\n');
  const relativeOut=rel(outRoot);
  const outLabel=relativeOut&&!relativeOut.startsWith('..')?relativeOut:path.resolve(outRoot);
  const summary={out_root:outLabel,version:manifest.version,matrix:{tested:matrix.tested_cells,accepted:matrix.accepted_cells,rejected:matrix.rejected_cell_count,status:matrix.status},
    scenarios:scenarios.map(item=>({slug:item.slug,before:item.before.status,after:item.after.status,comparison:item.comparison?.status||'NOT_RUN'})),
    gallery:gallery.status,ledger:ledger.status,contract:contract.map(item=>({id:item.id,status:item.status})),visual_qa:'NOT_RUN',
    fingerprint:fingerprint.aggregate_sha256,manifest:'showcase.manifest.json'};
  console.log(JSON.stringify(summary,null,2));
  if([matrix.status,gallery.status,ledger.status,ledgerCheck.status].includes('FAIL')||scenarios.some(item=>item.after.status==='FAIL')) process.exitCode=2;
}

module.exports={generateMatrixFixture,matrixTemplates,matrixRejections,prepareOutRoot,fingerprintTree,currentFingerprint,baselineFingerprint,
  sourceLedger,checkSourceLedger,sourceLedgerIssues,specDiff,compareRenders,metricReconciliation,matrixDeckSpec,verifyMatrixDeck,testMatrixRejections,
  supplementalSlides,buildSupplemental,testUnsupported,buildScenario,contactSheets,sanitizeText,sanitizeValue,sanitizeReports,scenarioGate,
  galleryEvidence,relationshipContractEntries,applyRelationshipEvidence,contractMatrix,SCENARIOS,MATRIX_FAMILIES,MATRIX_THEMES,MATRIX_CASES};
if(require.main===module) main().catch(error=>{console.error(error.stack||error.message);process.exitCode=2;});
