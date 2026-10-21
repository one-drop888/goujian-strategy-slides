const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const JSZip=require('jszip');
const {resolveSlide}=require('../composition/resolver');
const {close}=require('./calculations');
const {REPORT_PART}=require('./embed');

function sha256(buffer) { return crypto.createHash('sha256').update(buffer).digest('hex'); }
function normalizeText(value) { return String(value??'').replace(/\s+/g,' ').trim(); }
function unescapeXml(value) {
  return value.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&amp;/g,'&');
}
function blocks(xml,tag) {
  return [...xml.matchAll(new RegExp(`<c:${tag}[ >][\\s\\S]*?</c:${tag}>`,'g'))].map(match=>match[0]);
}
function aBlocks(xml,tag) {
  return [...xml.matchAll(new RegExp(`<a:${tag}[ >][\\s\\S]*?</a:${tag}>`,'g'))].map(match=>match[0]);
}
function block(xml,tag) { return blocks(xml,tag)[0]||''; }
function chartTextValues(fragment) {
  return [...fragment.matchAll(/<c:v>([^<]*)<\/c:v>/g)].map(match=>unescapeXml(match[1]));
}
function chartSeriesNames(xml) {
  return blocks(xml,'ser').map(series=>{
    const tx=block(series,'tx');
    return tx?chartTextValues(tx)[0]??null:null;
  });
}
function chartCategoryLabels(xml) {
  return blocks(xml,'ser').map(series=>{
    const cat=block(series,'cat');
    return cat?chartTextValues(cat):[];
  });
}
function chartNumbers(xml) {
  const values=[];
  for(const valueBlock of blocks(xml,'val')) {
    for(const match of valueBlock.matchAll(/<c:v>([^<]*)<\/c:v>/g)) {
      const number=Number(match[1]);
      if(Number.isFinite(number)) values.push(number);
    }
  }
  return values;
}
function tableRows(xml) {
  return aBlocks(xml,'tbl').map(table=>aBlocks(table,'tr').map(row=>aBlocks(row,'tc').map(cell=>
    unescapeXml([...cell.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>match[1]).join('')))));
}
function slideTexts(xml) {
  return [...xml.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>unescapeXml(match[1]));
}

function chartDescriptor(kind,container,series,labels) {
  return {
    slide:kind,
    series:series.map(item=>item.values||[]),
    names:series.map(item=>item.name||null),
    labels:series.map(item=>item.labels||labels||[]),
  };
}
function expectedCharts(spec,repoRoot) {
  const charts=[];
  for(const raw of spec.slides||[]) {
    const {renderer,slide}=resolveSlide(raw,repoRoot);
    if(renderer==='chart') charts.push(chartDescriptor('chart',slide,slide.series||[],slide.labels));
    if(slide.dashboard) charts.push(chartDescriptor('dashboard',slide.dashboard,slide.dashboard.series||[],slide.dashboard.labels));
    if(renderer==='multimodal') for(const panel of slide.panels||[]) {
      if(panel.kind==='chart') charts.push(chartDescriptor('panel-chart',panel,panel.series||[],panel.labels));
    }
  }
  return charts;
}
function expectedTables(spec,repoRoot) {
  const tables=[],zh=String(spec.lang||'zh-CN').startsWith('zh');
  for(const [index,raw] of (spec.slides||[]).entries()) {
    const {renderer,slide}=resolveSlide(raw,repoRoot);
    if(renderer==='table') tables.push({slide:index+1,headers:(slide.headers||[]).map(normalizeText),rows:(slide.rows||[]).map(row=>row.map(normalizeText))});
    if(renderer==='risk') tables.push({slide:index+1,
      headers:(zh?['风险 / 问题','可能性','影响','应对措施','负责人']:['Risk / issue','Likelihood','Impact','Mitigation','Owner']).map(normalizeText),
      rows:(slide.items||[]).map(it=>[it.title||it.label,it.likelihood||'',it.impact||it.severity||'',it.mitigation||it.action||'',it.owner||''].map(normalizeText))});
    if(renderer==='scorecard') {
      if(slide.semanticType==='research-method') tables.push({slide:index+1,
        headers:(zh?['设计维度','范围 / 方法','依据与限制']:['Design','Scope / method','Basis and limitations']).map(normalizeText),
        rows:(slide.items||[]).map(it=>[it.label||it.title,it.value,it.note||''].map(normalizeText))});
      else tables.push({slide:index+1,
        headers:(slide.headers||(zh?['指标','实际','目标','差异','状态']:['Metric','Actual','Target','Variance','Status'])).map(normalizeText),
        rows:(slide.items||[]).map(it=>[it.label||it.title,it.value??it.actual??'',it.target??'',it.variance??it.delta??'',it.status??''].map(normalizeText))});
    }
    if(renderer==='multimodal') for(const panel of slide.panels||[]) {
      if(panel.kind==='table') tables.push({slide:index+1,headers:(panel.headers||[]).map(normalizeText),rows:(panel.rows||[]).map(row=>row.map(normalizeText))});
    }
  }
  return tables;
}
function expectedKpis(spec,repoRoot) {
  const kpis=[];
  for(const [index,raw] of (spec.slides||[]).entries()) {
    const {renderer,slide}=resolveSlide(raw,repoRoot);
    if(renderer!=='kpi') continue;
    for(const item of slide.items||[]) {
      if(!item||typeof item!=='object') continue;
      kpis.push({slide:index+1,label:item.label||item.title||null,value:item.value==null?null:normalizeText(item.value),
        delta:item.delta==null?[]:String(item.delta).split(' · ').map(normalizeText).filter(Boolean)});
    }
  }
  return kpis;
}

async function notesForSlide(zip,index) {
  const relName=`ppt/slides/_rels/slide${index}.xml.rels`;
  const relFile=zip.file(relName);
  if(!relFile) return '';
  const rels=await relFile.async('string');
  const match=rels.match(/Target="([^"]*notesSlide[^"]*\.xml)"/);
  if(!match) return '';
  const target=path.posix.normalize(path.posix.join('ppt/slides',match[1]));
  const notesFile=zip.file(target);
  if(!notesFile) return '';
  const xml=await notesFile.async('string');
  return unescapeXml([...xml.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(item=>item[1]).join('\n'));
}

async function verifyBuiltDeck(pptxPath,spec,reasoning,repoRoot) {
  if(!reasoning.expected_pptx_sha256) throw new Error('native verification requires expected_pptx_sha256 from a trusted sidecar or scene');
  const actualPptxSha=sha256(fs.readFileSync(pptxPath));
  if(actualPptxSha!==reasoning.expected_pptx_sha256) {
    throw new Error(`final PPTX sha256 ${actualPptxSha} does not match expected ${reasoning.expected_pptx_sha256}`);
  }
  const zip=await JSZip.loadAsync(fs.readFileSync(pptxPath));
  const chartNames=Object.keys(zip.files).filter(name=>/^ppt\/charts\/chart\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/(\d+)/)[1])-Number(b.match(/(\d+)/)[1]));
  const expected=expectedCharts(spec,repoRoot);
  if(chartNames.length!==expected.length) throw new Error(`chart cache count ${chartNames.length} does not match spec ${expected.length}`);
  const charts=[];
  let chartSeries=0,chartLabels=0;
  for(const [index,name] of chartNames.entries()) {
    const xml=await zip.file(name).async('string');
    const actual=chartNumbers(xml),wanted=expected[index].series.flat();
    if(actual.length!==wanted.length) throw new Error(`chart ${index+1} value count ${actual.length} does not match spec ${wanted.length}`);
    for(let i=0;i<wanted.length;i++) if(!close(actual[i],wanted[i])) throw new Error(`chart ${index+1} value ${actual[i]} does not match spec ${wanted[i]}`);
    const names=chartSeriesNames(xml),wantedNames=expected[index].names;
    if(names.length!==wantedNames.length) throw new Error(`chart ${index+1} series count ${names.length} does not match spec ${wantedNames.length}`);
    for(const [i,wantedName] of wantedNames.entries()) {
      if(wantedName!=null&&normalizeText(names[i])!==normalizeText(wantedName)) {
        throw new Error(`chart ${index+1} series ${i+1} name "${names[i]}" does not match spec "${wantedName}"`);
      }
      chartSeries++;
    }
    const categories=chartCategoryLabels(xml),wantedLabels=expected[index].labels;
    for(const [i,wantedSet] of wantedLabels.entries()) {
      const actualSet=categories[i]||[];
      if(actualSet.length!==wantedSet.length) {
        throw new Error(`chart ${index+1} series ${i+1} label count ${actualSet.length} does not match spec ${wantedSet.length}`);
      }
      for(const [j,wantedLabel] of wantedSet.entries()) {
        if(normalizeText(actualSet[j])!==normalizeText(wantedLabel)) {
          throw new Error(`chart ${index+1} series ${i+1} label ${j+1} "${actualSet[j]}" does not match spec "${wantedLabel}"`);
        }
        chartLabels++;
      }
    }
    charts.push({part:name,values:actual,series:names.length,labels:categories.reduce((total,set)=>total+set.length,0)});
  }

  const expectedTablesBySlide=new Map();
  for(const table of expectedTables(spec,repoRoot)) {
    expectedTablesBySlide.set(table.slide,[...(expectedTablesBySlide.get(table.slide)||[]),table]);
  }
  const expectedKpisBySlide=new Map();
  for(const item of expectedKpis(spec,repoRoot)) {
    expectedKpisBySlide.set(item.slide,[...(expectedKpisBySlide.get(item.slide)||[]),item]);
  }
  let tableCount=0,tableCellCount=0,kpiCount=0;
  const slideIds=[];
  for(const [index,slide] of (reasoning.slides||[]).entries()) {
    const slideNumber=index+1;
    const xml=await zip.file(`ppt/slides/slide${slideNumber}.xml`).async('string');
    const actualTables=tableRows(xml),wantedTables=expectedTablesBySlide.get(slideNumber)||[];
    if(actualTables.length!==wantedTables.length) {
      throw new Error(`slide ${slideNumber} native table count ${actualTables.length} does not match spec ${wantedTables.length}`);
    }
    for(const [tableIndex,table] of wantedTables.entries()) {
      const actual=actualTables[tableIndex],normalizeRow=row=>row.map(normalizeText);
      if(actual.length<1) throw new Error(`slide ${slideNumber} table ${tableIndex+1} has no content`);
      const actualHeaders=normalizeRow(actual[0]),actualRows=actual.slice(1).map(normalizeRow);
      if(JSON.stringify(actualHeaders)!==JSON.stringify(table.headers)) {
        throw new Error(`slide ${slideNumber} table ${tableIndex+1} headers do not match spec`);
      }
      if(actualRows.length!==table.rows.length) {
        throw new Error(`slide ${slideNumber} table ${tableIndex+1} row count ${actualRows.length} does not match spec ${table.rows.length}`);
      }
      for(let row=0;row<table.rows.length;row++) {
        if(JSON.stringify(actualRows[row])!==JSON.stringify(table.rows[row])) {
          throw new Error(`slide ${slideNumber} table ${tableIndex+1} row ${row+1} cells do not match spec (${actualRows[row].join(' | ')} != ${table.rows[row].join(' | ')})`);
        }
        tableCellCount+=table.rows[row].length;
      }
      tableCellCount+=table.headers.length;
      tableCount++;
    }
    const texts=slideTexts(xml).map(normalizeText);
    for(const item of expectedKpisBySlide.get(slideNumber)||[]) {
      if(item.label!=null&&!texts.includes(item.label)) throw new Error(`slide ${slideNumber} KPI label "${item.label}" is missing from native text`);
      if(item.value!=null&&!texts.includes(item.value)) throw new Error(`slide ${slideNumber} KPI value "${item.value}" is missing from native text`);
      for(const segment of item.delta) if(!texts.includes(segment)) throw new Error(`slide ${slideNumber} KPI supporting text "${segment}" is missing from native text`);
      kpiCount++;
    }
    const text=await notesForSlide(zip,slideNumber);
    if(!text.includes(`[reasoning:${slide.id}]`)) throw new Error(`slide ${slideNumber} notes are missing reasoning id ${slide.id}`);
    for(const claimId of slide.claim_ids||[]) if(!text.includes(claimId)) throw new Error(`slide ${slideNumber} notes are missing claim ${claimId}`);
    slideIds.push(slide.id);
  }
  const reportFile=zip.file(REPORT_PART);
  if(!reportFile) throw new Error(`embedded reasoning report ${REPORT_PART} is missing`);
  const embeddedText=await reportFile.async('string');
  const embedded=JSON.parse(embeddedText);
  if(embedded.plan_sha256!==reasoning.plan_sha256) throw new Error('embedded report plan hash does not match');
  if(embedded.spec_sha256!==reasoning.spec_sha256) throw new Error('embedded report spec hash does not match');
  if(reasoning.report_sha256) {
    const actual=sha256(Buffer.from(embeddedText));
    if(actual!==reasoning.report_sha256) throw new Error('embedded report bytes do not match report_sha256');
  }
  return {status:'PASS',pptx_sha256:actualPptxSha,charts:charts.length,chart_series:chartSeries,chart_labels:chartLabels,
    tables:tableCount,table_cells:tableCellCount,kpis:kpiCount,notes:slideIds.length,embedded_report:REPORT_PART};
}

module.exports={verifyBuiltDeck,expectedCharts,expectedTables,expectedKpis,chartNumbers,tableRows};
