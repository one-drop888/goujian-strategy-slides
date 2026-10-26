const {resolveSlide}=require('../composition/resolver');
const {close}=require('./calculations');
const {getPointer}=require('../semantics/numeric');
const {REPORT_PART}=require('./embed');
const {
  normalizeText,chartNumbers,tableRows,slideTexts,notesForSlide,chartSeriesNames,chartCategoryLabels,loadNativeDeck,
}=require('../qa/native_readback');


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

async function verifyBuiltDeck(pptxPath,spec,reasoning,repoRoot) {
  if(!reasoning.expected_pptx_sha256) throw new Error('native verification requires expected_pptx_sha256 from a trusted sidecar or scene');
  const native=await loadNativeDeck(pptxPath);
  const actualPptxSha=native.pptx_sha256;
  if(actualPptxSha!==reasoning.expected_pptx_sha256) {
    throw new Error(`final PPTX sha256 ${actualPptxSha} does not match expected ${reasoning.expected_pptx_sha256}`);
  }
  const {zip,chartNames}=native;
  const expected=expectedCharts(spec,repoRoot);
  if(chartNames.length!==expected.length) throw new Error(`chart cache count ${chartNames.length} does not match spec ${expected.length}`);
  const charts=[];
  let chartSeries=0,chartLabels=0;
  for(const [index,name] of chartNames.entries()) {
    const xml=native.charts[index].xml;
    const actual=chartNumbers(xml),wanted=expected[index].series.flat();
    if(actual.length!==wanted.length) throw new Error(`chart ${index+1} value count ${actual.length} does not match spec ${wanted.length}`);
    for(let i=0;i<wanted.length;i++) {
      if(wanted[i]===null) {
        if(actual[i]!==null) throw new Error(`chart ${index+1} value ${i+1} ${String(actual[i])} does not preserve the declared gap (null)`);
      } else if(actual[i]===null||typeof actual[i]!=='number'||!close(actual[i],wanted[i])) {
        throw new Error(`chart ${index+1} value ${String(actual[i])} does not match spec ${String(wanted[i])}`);
      }
    }
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
  const embedded=native.embedded_report;
  if(!embedded||embedded.malformed) throw new Error(`embedded reasoning report ${REPORT_PART} is malformed`);
  if(embedded.plan_sha256!==reasoning.plan_sha256) throw new Error('embedded report plan hash does not match');
  if(embedded.spec_sha256!==reasoning.spec_sha256) throw new Error('embedded report spec hash does not match');
  if(reasoning.report_sha256&&native.embedded_report_sha256!==reasoning.report_sha256) throw new Error('embedded report bytes do not match report_sha256');
  let semanticBindings=0;
  const semantics=reasoning.metric_semantics||embedded.metric_semantics;
  if(semantics) {
    if(!Array.isArray(semantics.transformations)||!Array.isArray(semantics.bindings)) throw new Error('metric semantics report is malformed');
    for(const record of semantics.bindings) {
      if(!record||record.ok!==true) throw new Error(`metric binding ${record?.pointer||'?'} was not reconciled`);
      const slideIndex=Number(String(record.slide||'').match(/^slides\[(\d+)\]$/)?.[1]);
      if(!Number.isInteger(slideIndex)||!spec.slides?.[slideIndex]) throw new Error(`metric binding ${record.pointer} references an unknown slide`);
      const actual=getPointer(spec.slides[slideIndex],record.pointer);
      if(record.mode==='numeric') {
        const factor=record.render_factor??1;
        if(typeof factor!=='number'||!Number.isFinite(factor)||factor<=0||typeof actual!=='number'||!close(actual*factor,record.effective_value))throw new Error(`metric binding ${record.pointer} native value ${actual} does not match effective ${record.effective_value}`);
      }
      else if(record.mode==='text') { if(actual!==record.formatted) throw new Error(`metric binding ${record.pointer} text ${JSON.stringify(actual)} does not match formatted ${JSON.stringify(record.formatted)}`); }
      else if(record.mode==='missing') { if(actual!==null) throw new Error(`metric binding ${record.pointer} must remain null`); }
      else throw new Error(`metric binding ${record.pointer} has unknown mode ${record.mode}`);
      semanticBindings++;
    }
    if(embedded.metric_semantics&&JSON.stringify(embedded.metric_semantics)!==JSON.stringify(semantics)) throw new Error('embedded metric semantics do not match the build scene');
  }
  return {status:'PASS',pptx_sha256:actualPptxSha,charts:charts.length,chart_series:chartSeries,chart_labels:chartLabels,
    tables:tableCount,table_cells:tableCellCount,kpis:kpiCount,notes:slideIds.length,embedded_report:REPORT_PART,
    metric_bindings:semanticBindings,metric_transformations:semantics?.transformations?.length||0};
}

module.exports={verifyBuiltDeck,expectedCharts,expectedTables,expectedKpis,chartNumbers,tableRows};
