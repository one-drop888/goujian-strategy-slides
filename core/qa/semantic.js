'use strict';
// Executable semantic QA over the serialized PPTX. Expected meaning is re-derived from the
// original source spec; native chart cache, workbook cells, table/KPI text and visual encoding
// are read back independently. Colour checks are heuristics, never aesthetic approval.
const fs=require('fs');
const path=require('path');
const {
  loadNativeDeck,normalizeText,tableRows,slideTexts,sha256,
}=require('./native_readback');
const {prepareDeckSemantics}=require('../semantics/deck');
const {formatMetric,chartNormalizationFactor,getPointer}=require('../semantics/numeric');
const {resolveSlide}=require('../composition/resolver');
const {loadProfile}=require('../style/profile-loader');
const {resolveStyle,contrastRatio}=require('../style/resolve-style');
const {
  createEncoding,deltaE76,grayscaleDelta,MIN_DELTA_E,MIN_GRAY,MIN_CONTRAST,
}=require('../renderer/encoding');
const {inspectNarrative}=require('../semantics/narrative');
const {close}=require('../reasoning/calculations');
const {dataLabelNumberFormat}=require('../renderer/charts');

const CHART_SERIES_POINTER=/^\/(series\/\d+\/values|dashboard\/series\/\d+\/values|panels\/\d+\/series\/\d+\/values)\/\d+$/;
const round=value=>Math.round(value*1000)/1000;
function slideIndexFromReference(reference) {
  const match=String(reference||'').match(/^slides\[(\d+)\]$/);
  return match?Number(match[1]):null;
}
function routeKind(route) {
  if(route.route==='dashboard') return 'line';
  if(route.route==='panel') return String(route.panel?.chartType||'bar').toLowerCase();
  const slide=route.slide||{};
  const explicit=String(slide.chartType||'').toLowerCase();
  if(explicit) return explicit;
  if(['line','trend','cohort'].includes(slide.type)) return 'line';
  if(slide.type==='area') return 'area';
  if(['bar','benchmark','distribution'].includes(slide.type)) return 'bar';
  if(['column','variance','cost-structure','histogram','waterfall','bridge'].includes(slide.type)) return 'column';
  return 'bar';
}
function defaultFormat(route) {
  if(route.route==='panel') return '0.0';
  if(route.route==='dashboard') return '0.##';
  return ['pie','doughnut'].includes(routeKind(route))?'0%':'0.##';
}
function routeTarget(route) {
  if(route.route==='dashboard') return route.slide.dashboard;
  if(route.route==='panel') return route.panel;
  return route.slide;
}
const NATIVE_FAMILY={
  column:{kind:'bar',bar_dir:'col'},
  bar:{kind:'bar',bar_dir:'bar'},
  line:{kind:'line'},
  area:{kind:'area'},
  pie:{kind:'pie'},
  doughnut:{kind:'doughnut'},
};
function chartFamily({native,routes}) {
  const errors=[],notes=[];
  let checked=0;
  for(const [routeIndex,route] of routes.entries()) {
    const chart=native.charts[routeIndex];
    if(!chart) continue;
    const kind=routeKind(route),expected=NATIVE_FAMILY[kind];
    if(!expected) { notes.push(`chart ${routeIndex+1} uses chart kind ${JSON.stringify(kind)} with no native family expectation`); continue; }
    checked++;
    if(chart.kind!==expected.kind) {
      errors.push(`chart ${routeIndex+1} (${route.route}) native chart family ${JSON.stringify(chart.kind)} does not match declared ${kind} (expected ${expected.kind})`);
    }
    if(expected.bar_dir&&chart.kind==='bar'&&chart.bar_dir!==expected.bar_dir) {
      errors.push(`chart ${routeIndex+1} (${route.route}) native bar direction ${JSON.stringify(chart.bar_dir)} does not match declared ${expected.bar_dir==='col'?'column':'bar'}`);
    }
    if(['bar','column'].includes(kind)) {
      const stacked=route.series.some(series=>series?.stack===true);
      const expectedGrouping=stacked?'stacked':'clustered';
      if(chart.kind==='bar'&&chart.grouping!==expectedGrouping) {
        errors.push(`chart ${routeIndex+1} (${route.route}) native grouping ${JSON.stringify(chart.grouping)} does not match declared ${stacked?'stacked':'clustered'} series`);
      }
    }
  }
  if(!checked) return notRun('typed','No chart route had a native family expectation.');
  return check('typed',{errors,notes,charts_checked:checked});
}
function chartAxisIntegrity({native,routes}) {
  const errors=[],notes=[];
  let chartsChecked=0,pointsChecked=0;
  for(const [routeIndex,route] of routes.entries()) {
    const chart=native.charts[routeIndex],target=routeTarget(route)||{};
    if(!chart) continue;
    const kind=routeKind(route);
    if(['pie','doughnut'].includes(kind)||!NATIVE_FAMILY[kind]) continue;
    chartsChecked++;
    const axis=chart.value_axis;
    const values=chart.series.flatMap(series=>Array.isArray(series.values)?series.values:[]).filter(value=>value!==null&&Number.isFinite(value));
    pointsChecked+=values.length;
    const declaredMin=target.axisMin!=null&&Number.isFinite(Number(target.axisMin))?Number(target.axisMin):null;
    if(['bar','column','area'].includes(kind)) {
      const baseline=declaredMin==null?Math.min(0,...values):declaredMin;
      if(!axis?.min_present) errors.push(`chart ${routeIndex+1} (${route.route}, ${kind}) native value axis has no minimum; ${kind} must include the zero baseline ${baseline}`);
      else if(!axis.min_valid) errors.push(`chart ${routeIndex+1} (${route.route}) native axis minimum ${JSON.stringify(axis.min_raw)} is not numeric`);
      else if(declaredMin==null&&baseline<0&&!(axis.min<baseline)) errors.push(`chart ${routeIndex+1} (${route.route}) native axis minimum ${axis.min} does not reserve headroom below negative extreme ${baseline}`);
      else if((declaredMin!=null||baseline>=0)&&!close(axis.min,baseline)) errors.push(`chart ${routeIndex+1} (${route.route}) native axis minimum ${axis.min} does not match required baseline ${baseline}`);
    } else if(kind==='line') {
      if(declaredMin!=null) {
        if(!axis?.min_present) errors.push(`chart ${routeIndex+1} (${route.route}) declares axisMin ${declaredMin} but native value axis has no minimum`);
        else if(!axis.min_valid) errors.push(`chart ${routeIndex+1} (${route.route}) native axis minimum ${JSON.stringify(axis.min_raw)} is not numeric`);
        else if(!close(axis.min,declaredMin)) errors.push(`chart ${routeIndex+1} (${route.route}) native axis minimum ${axis.min} does not match declared axisMin ${declaredMin}`);
      } else if(axis?.min_present&&axis.min_valid&&values.length&&axis.min>Math.min(...values)&&!close(axis.min,Math.min(...values))) {
        const note=String(target.axis_note||'').trim();
        if(!note) errors.push(`chart ${routeIndex+1} (${route.route}, line) native axis minimum ${axis.min} clips values below ${Math.min(...values)} without an explicit axis_note`);
        else notes.push(`chart ${routeIndex+1} (${route.route}, line) truncated axis at ${axis.min} is disclosed by axis_note`);
      }
    }
    if(axis?.min_present) {
      if(!axis.min_valid) { /* reported above for bar/column/area and line; other families only note */ }
      else for(const series of chart.series) for(const value of series.values||[]) {
        if(value!==null&&Number.isFinite(value)&&value<axis.min&&!close(value,axis.min)) {
          errors.push(`chart ${routeIndex+1} (${route.route}) native axis minimum ${axis.min} hides value ${value}`);
        }
      }
    }
    if(axis?.max_present&&!axis.max_valid) errors.push(`chart ${routeIndex+1} (${route.route}) native axis maximum ${JSON.stringify(axis.max_raw)} is not numeric`);
    if(axis?.max_present&&axis.max_valid) for(const series of chart.series) for(const value of series.values||[]) {
      if(value!==null&&Number.isFinite(value)&&value>axis.max&&!close(value,axis.max)) {
        errors.push(`chart ${routeIndex+1} (${route.route}) native axis maximum ${axis.max} hides value ${value}`);
      }
    }
  }
  if(!chartsChecked) return notRun('typed','No chart route had a native value axis to audit.');
  return check('typed',{errors,notes,charts_checked:chartsChecked,points_checked:pointsChecked});
}
function expectedRoutes(effective,repoRoot) {
  const routes=[];
  for(const [slideIndex,raw] of (effective.slides||[]).entries()) {
    const {renderer,slide}=resolveSlide(raw,repoRoot);
    if(renderer==='chart') routes.push({route:'chart',slideIndex,slide,series:slide.series||[],labels:slide.labels||[]});
    if(slide.dashboard) routes.push({route:'dashboard',slideIndex,slide,series:slide.dashboard.series||[],labels:slide.dashboard.labels||[],dashboard:slide.dashboard});
    if(renderer==='multimodal') for(const [panelIndex,panel] of (slide.panels||[]).entries()) {
      if(panel.kind==='chart') routes.push({route:'panel',slideIndex,panelIndex,slide,panel,series:panel.series||[],labels:panel.labels||[]});
    }
  }
  return routes;
}
function chartValuesMatch(actual,expected) {
  if(expected===null) return actual===null;
  return typeof actual==='number'&&Number.isFinite(actual)&&close(actual,expected);
}
function nativeSeriesFor(native,routeIndex,seriesIndex) {
  return native.charts[routeIndex]?.series?.[seriesIndex]||null;
}
function pushUnique(list,message) { if(!list.includes(message)) list.push(message); }
function check(mode,{status='PASS',errors=[],notes=[],...details}={}) {
  return {status:errors.length?'FAIL':status,mode,errors,notes,...details};
}
function notRun(mode,reason,extra={}) { return {status:'NOT_RUN',mode,reason,...extra}; }
function partial(mode,reason,extra={}) { return {status:'PARTIAL',mode,reason,...extra}; }

function expectedSeriesLabels(route,series) {
  if(route.route==='dashboard'&&Array.isArray(route.labels)&&route.labels.length) return route.labels;
  return Array.isArray(series?.labels)&&series.labels.length?series.labels:route.labels||[];
}
function alignPlans(routes,plans) {
  const aligned=[],used=new Set();
  let cursor=0;
  for(const route of routes) {
    const container=route.route==='chart'?'slide':route.route;
    let found=null;
    for(let index=cursor;index<plans.length;index++) {
      if(used.has(index)) continue;
      const plan=plans[index];
      if(plan.container===container&&plan.slideIndex===route.slideIndex
        &&String(plan.kind).toLowerCase()===routeKind(route)) { found=index; break; }
    }
    if(found==null) for(let index=0;index<plans.length;index++) {
      if(used.has(index)) continue;
      const plan=plans[index];
      if(plan.container===container&&plan.slideIndex===route.slideIndex) { found=index; break; }
    }
    if(found==null) aligned.push(null);
    else { used.add(found); aligned.push(plans[found]); cursor=found+1; }
  }
  return aligned;
}
function metricPositionsFor(routes,catalogue) {
  const positions=[];
  for(const [routeIndex,route] of routes.entries()) {
    for(const [seriesIndex,series] of route.series.entries()) {
      const values=Array.isArray(series?.values)?series.values:[];
      const ids=Array.isArray(series?.metric_ids)?series.metric_ids:(series?.metric_id!=null?[series.metric_id]:[]);
      for(const [valueIndex,value] of values.entries()) {
        let id=null;
        if(ids.length===values.length) id=ids[valueIndex];
        else if(ids.length===1&&values.length===1) id=ids[0];
        if(id==null) continue;
        const metric=catalogue.get(String(id));
        if(metric) positions.push({metric,route,routeIndex,seriesIndex,valueIndex,expected:value});
      }
    }
  }
  return positions;
}
function textUsagesFor(semantics) {
  const usages=[];
  for(const record of semantics.bindings||[]) {
    const slideIndex=slideIndexFromReference(record.slide);
    if(slideIndex==null||record.ok!==true||CHART_SERIES_POINTER.test(String(record.pointer||''))) continue;
    usages.push({kind:record.mode,metric_id:record.metric_id,slideIndex,pointer:record.pointer,
      expected:record.mode==='numeric'?String(record.effective_value):record.formatted,
      formatted:record.formatted,record});
  }
  for(const transformation of semantics.transformations||[]) {
    if(transformation.kind!=='replace-placeholder') continue;
    const slideIndex=slideIndexFromReference(transformation.slide);
    if(slideIndex==null) continue;
    for(const match of String(transformation.from||'').matchAll(/\{\{metric:([A-Za-z0-9][A-Za-z0-9._-]{0,80})\}\}/g)) {
      usages.push({kind:'placeholder',metric_id:match[1],slideIndex,pointer:transformation.pointer,
        expected:transformation.to,placeholder:true});
    }
  }
  return usages;
}
function formattedForUsage(usage,metric,effective) {
  if(usage.formatted) return usage.formatted;
  const slide=effective.slides?.[usage.slideIndex];
  const precision=slide?.metric_precision?.[metric.id];
  try { return formatMetric(metric,precision==null?{}:{precision}).text; }
  catch { return null; }
}
function isTablePointer(pointer) { return /^\/(rows\/\d+\/\d+|panels\/\d+\/rows\/\d+\/\d+|items\/\d+\/(value|target|actual|variance|delta))$/.test(String(pointer||'')); }
function tableCellAt(tables,pointer) {
  const match=String(pointer||'').match(/^\/rows\/(\d+)\/(\d+)$/);
  if(!match||!tables.length) return null;
  return tables[0]?.[Number(match[1])+1]?.[Number(match[2])]??null;
}
function normalizedTexts(xml) { return slideTexts(xml||'').map(normalizeText); }
function joinedNormalizedTexts(xml) { return normalizedTexts(xml).join('\n'); }
function formatDiagnostics(chart) {
  return {
    value_axis:chart?.value_axis_format??null,
    global_label:chart?.global_label_format??null,
    series:Array.isArray(chart?.series)?chart.series.map(item=>item.label_format??null):[],
  };
}
function formatObserved(chart,expected,labelExpected=expected) {
  const formats=formatDiagnostics(chart);
  const candidates=[formats.value_axis,formats.global_label,...formats.series].filter(value=>value!=null);
  const labels=[formats.global_label,...formats.series].filter(value=>value!=null);
  const axisMatches=formats.value_axis==null||formats.value_axis===expected;
  return {matches:axisMatches&&labels.length>0&&labels.every(value=>value===labelExpected),observed:candidates,expected,label_expected:labelExpected};
}
function nativeChartPayload(native,routeIndex) {
  const chart=native.charts[routeIndex];
  if(!chart) return null;
  return {series_count:chart.series.length,series_names:chart.series.map(item=>item.name),
    values:chart.series.map(item=>item.values),labels:chart.series.map(item=>item.category_labels),
    colors:chart.series.map(item=>item.color),point_colors:chart.series.map(item=>item.point_colors||[]),
    dash:chart.series.map(item=>item.dash),marker:chart.series.map(item=>item.marker),
    formats:formatDiagnostics(chart),legend:chart.legend,disp_blanks_as:chart.disp_blanks_as};
}
async function slideXmlMap(native,slides) {
  const map=new Map();
  for(let index=1;index<=slides;index++) {
    const file=native.zip.file(`ppt/slides/slide${index}.xml`);
    map.set(index,file?await file.async('string'):'');
  }
  return map;
}

function numericFidelity({native,routes,effective,semantics,slideXml,typedMode,catalogue}) {
  const errors=[],notes=[];
  let gaps=0,zeros=0,nativeValues=0,workbookValues=0,bindingsChecked=0,renderFactors=0;
  if(native.charts.length!==routes.length) {
    errors.push(`native chart count ${native.charts.length} does not match effective spec routes ${routes.length}`);
  }
  const count=Math.min(native.charts.length,routes.length);
  for(let routeIndex=0;routeIndex<count;routeIndex++) {
    const route=routes[routeIndex],chart=native.charts[routeIndex];
    if(!chart) continue;
    if(chart.series.length!==route.series.length) {
      errors.push(`chart ${routeIndex+1} (${route.route}) series count ${chart.series.length} does not match spec ${route.series.length}`);
    }
    for(const [seriesIndex,actual] of chart.series.entries()) {
      for(const issue of actual.structure_errors||[]) errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} native cache structure: ${issue}`);
    }
    const seriesCount=Math.min(chart.series.length,route.series.length);
    let routeGaps=0;
    for(let seriesIndex=0;seriesIndex<seriesCount;seriesIndex++) {
      const actual=chart.series[seriesIndex],series=route.series[seriesIndex];
      const expectedValues=Array.isArray(series?.values)?series.values:[];
      const actualValues=Array.isArray(actual.values)?actual.values:[];
      if(actualValues.length!==expectedValues.length) {
        errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} value count ${actualValues.length} does not match spec ${expectedValues.length}`);
      }
      const valueCount=Math.min(actualValues.length,expectedValues.length);
      for(let valueIndex=0;valueIndex<valueCount;valueIndex++) {
        const wanted=expectedValues[valueIndex],observed=actualValues[valueIndex];
        nativeValues++;
        if(wanted===null) {
          gaps++;
          routeGaps++;
          if(observed!==null) errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} value ${valueIndex+1} ${String(observed)} does not preserve the declared gap`);
        } else {
          if(wanted===0) zeros++;
          if(!chartValuesMatch(observed,wanted)) errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} value ${valueIndex+1} ${String(observed)} does not match effective value ${String(wanted)}`);
        }
      }
      if(actual.invalid_values?.length) errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} contains nonnumeric cache values: ${actual.invalid_values.map(item=>item.text).join(', ')}`);
      const expectedName=series?.name??null;
      if(expectedName!=null&&normalizeText(actual.name)!==normalizeText(expectedName)) {
        errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} name "${actual.name}" does not match spec "${expectedName}"`);
      }
      const expectedLabels=expectedSeriesLabels(route,series).map(normalizeText);
      const actualLabels=(actual.category_labels||[]).map(normalizeText);
      if(actualLabels.length!==expectedLabels.length) {
        errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} label count ${actualLabels.length} does not match spec ${expectedLabels.length}`);
      } else for(const [labelIndex,label] of expectedLabels.entries()) {
        if(actualLabels[labelIndex]!==label) errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} label ${labelIndex+1} "${actualLabels[labelIndex]}" does not match spec "${label}"`);
      }
      const workbook=chart.workbook;
      if(workbook?.status!=='PASS') {
        errors.push(`chart ${routeIndex+1} embedded workbook ${workbook?.status||'MISSING'}: ${workbook?.reason||'not readable'}`);
      } else {
        const workbookSeries=workbook.series?.[seriesIndex];
        if(!workbookSeries) errors.push(`chart ${routeIndex+1} workbook omits series ${seriesIndex+1}`);
        else {
          if(workbookSeries.values.length!==actualValues.length) {
            errors.push(`chart ${routeIndex+1} workbook series ${seriesIndex+1} value count ${workbookSeries.values.length} does not match chart cache ${actualValues.length}`);
          }
          const workbookCount=Math.min(workbookSeries.values.length,actualValues.length);
          for(let valueIndex=0;valueIndex<workbookCount;valueIndex++) {
            workbookValues++;
            const cached=actualValues[valueIndex],cell=workbookSeries.values[valueIndex];
            if(!chartValuesMatch(cell,cached)) errors.push(`chart ${routeIndex+1} workbook series ${seriesIndex+1} cell ${valueIndex+1} ${String(cell)} does not match chart cache ${String(cached)}`);
          }
          if(workbookSeries.name!=null&&actual.name!=null&&normalizeText(workbookSeries.name)!==normalizeText(actual.name)) {
            errors.push(`chart ${routeIndex+1} workbook series ${seriesIndex+1} name "${workbookSeries.name}" does not match chart legend "${actual.name}"`);
          }
          const workbookLabels=(workbookSeries.categories||[]).map(normalizeText);
          if(workbookLabels.length&&workbookLabels.length===actualLabels.length) {
            for(const [labelIndex,label] of actualLabels.entries()) if(workbookLabels[labelIndex]!==label) errors.push(`chart ${routeIndex+1} workbook series ${seriesIndex+1} category ${labelIndex+1} "${workbookLabels[labelIndex]}" does not match chart label "${label}"`);
          }
        }
      }
    }
    if(routeGaps&&chart.disp_blanks_as!=='gap') errors.push(`chart ${routeIndex+1} (${route.route}) declares ${routeGaps} gap(s) but native displayBlanksAs is ${JSON.stringify(chart.disp_blanks_as)}`);
  }
  for(const record of semantics.bindings||[]) {
    if(record.ok!==true) { errors.push(`metric binding ${record.pointer||'?'} was not reconciled: ${record.error||'unknown error'}`); continue; }
    const slideIndex=slideIndexFromReference(record.slide);
    if(slideIndex==null) { errors.push(`metric binding ${record.pointer} references an unknown slide`); continue; }
    const slide=effective.slides?.[slideIndex];
    if(!slide) { errors.push(`metric binding ${record.pointer} references a missing slide`); continue; }
    const actual=getPointer(slide,record.pointer);
    if(record.mode==='numeric') {
      const factor=record.render_factor??1;
      const metric=catalogue.get(record.metric_id);
      const computedFactor=metric?chartNormalizationFactor(metric):factor;
      const expectedEffective=record.render_value??record.effective_value;
      if(!Number.isFinite(factor)||factor<=0) errors.push(`metric binding ${record.pointer} has an invalid render_factor ${factor}`);
      else if(!close(computedFactor,factor)) errors.push(`metric binding ${record.pointer} render_factor ${factor} does not match metric ${record.metric_id} factor ${computedFactor}`);
      if(typeof actual==='number'&&!close(actual,expectedEffective)) errors.push(`metric binding ${record.pointer} effective spec value ${actual} does not match ${expectedEffective}`);
      if(CHART_SERIES_POINTER.test(String(record.pointer))) {
        renderFactors++;
        const chartMatch=String(record.pointer).match(/^\/series\/(\d+)\/values\/(\d+)$/);
        const dashboardMatch=String(record.pointer).match(/^\/dashboard\/series\/(\d+)\/values\/(\d+)$/);
        const panelMatch=String(record.pointer).match(/^\/panels\/(\d+)\/series\/(\d+)\/values\/(\d+)$/);
        let routeIndex=-1,seriesIndex=-1,valueIndex=-1;
        if(chartMatch) { routeIndex=0; seriesIndex=Number(chartMatch[1]); valueIndex=Number(chartMatch[2]);
          routeIndex=routes.findIndex(route=>route.slideIndex===slideIndex&&route.route==='chart'&&!route.dashboard);
        } else if(dashboardMatch) { seriesIndex=Number(dashboardMatch[1]); valueIndex=Number(dashboardMatch[2]);
          routeIndex=routes.findIndex(route=>route.slideIndex===slideIndex&&route.route==='dashboard');
        } else if(panelMatch) { const panelIndex=Number(panelMatch[1]); seriesIndex=Number(panelMatch[2]); valueIndex=Number(panelMatch[3]);
          routeIndex=routes.findIndex(route=>route.slideIndex===slideIndex&&route.route==='panel'&&route.panelIndex===panelIndex);
        }
        if(routeIndex>=0) {
          const nativeSeries=nativeSeriesFor(native,routeIndex,seriesIndex);
          if(!nativeSeries) errors.push(`metric binding ${record.pointer} does not resolve to a native chart series`);
          else if(!chartValuesMatch(nativeSeries.values?.[valueIndex],record.render_value??record.effective_value/factor)) {
            errors.push(`metric binding ${record.pointer} native chart value ${String(nativeSeries.values?.[valueIndex])} does not match rendered value ${String(record.render_value??record.effective_value/factor)}`);
          }
        } else errors.push(`metric binding ${record.pointer} does not resolve to an expected chart route`);
      }
    } else if(record.mode==='text') {
      if(actual!==record.formatted) errors.push(`metric binding ${record.pointer} source text ${JSON.stringify(actual)} does not match formatted ${JSON.stringify(record.formatted)}`);
      const xml=slideXml.get(slideIndex+1)||'';
      const texts=normalizedTexts(xml),joined=joinedNormalizedTexts(xml),wanted=normalizeText(record.formatted);
      const tables=tableRows(xml),cell=tableCellAt(tables,record.pointer);
      if(cell!=null) { if(normalizeText(cell)!==wanted) errors.push(`slide ${slideIndex+1} table cell ${record.pointer} "${normalizeText(cell)}" does not match formatted ${JSON.stringify(wanted)}`); }
      else if(!texts.includes(wanted)&&!joined.includes(wanted)) errors.push(`slide ${slideIndex+1} native text is missing formatted metric ${JSON.stringify(wanted)}`);
    } else if(record.mode==='missing') {
      if(actual!==null) errors.push(`metric binding ${record.pointer} must remain null`);
      const xml=slideXml.get(slideIndex+1)||'';
      const tables=tableRows(xml),cell=tableCellAt(tables,record.pointer);
      if(cell!=null&&cell!==''&&cell!=='—') errors.push(`slide ${slideIndex+1} table cell ${record.pointer} ${JSON.stringify(cell)} does not preserve the missing value`);
    } else errors.push(`metric binding ${record.pointer} has unknown mode ${record.mode}`);
    bindingsChecked++;
  }
  if(!bindingsChecked&&typedMode) notes.push('typed metrics have no metric_bindings; series and placeholder checks still apply');
  if(!errors.length&&nativeValues===0&&!typedMode) return notRun('legacy','No native chart values or typed bindings were available to compare.');
  if(!errors.length&&nativeValues===0&&typedMode) notes.push('no native chart values were present');
  return check(typedMode?'typed':'legacy',{errors,notes,gaps,zeros,native_values:nativeValues,workbook_values:workbookValues,
    bindings_checked:bindingsChecked,render_factors:renderFactors,charts_checked:count,source_spec_immutable:true});
}

function sourceImmutability(snapshot,spec) {
  return snapshot===JSON.stringify(spec);
}

function unitConsistency({native,routes,slideXml,catalogue,typedMode}) {
  const errors=[],notes=[];
  let formatsChecked=0,unitsChecked=0,panelUnitsMissing=0;
  for(const [routeIndex,route] of routes.entries()) {
    const chart=native.charts[routeIndex],target=routeTarget(route);
    if(!chart||!target) continue;
    const expectedFormat=target.numberFormat||defaultFormat(route);
    const labelFormat=dataLabelNumberFormat(routeKind(route),route.slide.visual_encoding?.label_strategy??null,expectedFormat);
    const format=formatObserved(chart,expectedFormat,labelFormat);
    formatsChecked++;
    if(!format.matches) errors.push(`chart ${routeIndex+1} (${route.route}) native number format ${JSON.stringify(format.observed)} does not match effective format ${JSON.stringify(expectedFormat)}`);
    const expectedUnit=target.unit==null?'':String(target.unit).trim();
    if(expectedUnit) {
      unitsChecked++;
      const xml=slideXml.get(route.slideIndex+1)||'';
      const texts=normalizedTexts(xml);
      if(route.route==='chart') {
        const axisText=[route.slide.unit,route.slide.period,route.slide.axis_note].filter(Boolean).join(' · ');
        if(axisText&&!texts.includes(normalizeText(axisText))) errors.push(`slide ${route.slideIndex+1} axis unit text ${JSON.stringify(axisText)} is missing from native text`);
      } else if(route.route==='dashboard') {
        if(!texts.includes(normalizeText(expectedUnit))) errors.push(`slide ${route.slideIndex+1} dashboard unit ${JSON.stringify(expectedUnit)} is missing from native text`);
      } else if(route.route==='panel') {
        const period=target.period==null?'':String(target.period).trim();
        const caption=[expectedUnit,period].filter(Boolean).join(' · ');
        if(!texts.some(value=>value.includes(normalizeText(caption)))) errors.push(`slide ${route.slideIndex+1} panel unit caption ${JSON.stringify(caption)} is missing from native text`);
      }
      const routeMetricIds=new Set();
      for(const series of route.series) for(const id of (Array.isArray(series?.metric_ids)?series.metric_ids:(series?.metric_id!=null?[series.metric_id]:[]))) routeMetricIds.add(String(id));
      const routeMetrics=[...routeMetricIds].map(id=>catalogue.get(id)).filter(Boolean);
      const nativeFormats=[chart.value_axis_format,chart.global_label_format,...chart.series.map(item=>item.label_format)].filter(Boolean).join(' ');
      if(routeMetrics.some(metric=>metric.canonical_unit==='%')&&!nativeFormats.includes('%')) errors.push(`chart ${routeIndex+1} declares percent semantics but native format omits %`);
      if(routeMetrics.some(metric=>metric.canonical_unit==='pp')&&!nativeFormats.includes('pp')) errors.push(`chart ${routeIndex+1} declares percentage-point semantics but native format omits pp`);
    } else if(route.route==='panel') {
      panelUnitsMissing++;
      notes.push(`chart ${routeIndex+1} panel route has no declared unit; legacy unit context requires Agent review`);
    }
  }
  if(!formatsChecked&&!unitsChecked) return notRun(typedMode?'typed':'legacy','No declared chart formats or units were available.');
  if(!errors.length&&!unitsChecked&&panelUnitsMissing) return notRun(typedMode?'typed':'legacy',
    'No panel route declares a unit; legacy unit context requires Agent review.',
    {formats_checked:formatsChecked,units_checked:0,panel_units_missing:panelUnitsMissing});
  return check(typedMode?'typed':'legacy',{errors,notes,formats_checked:formatsChecked,units_checked:unitsChecked,panel_units_missing:panelUnitsMissing});
}

function percentageScale({catalogue,positions,usages,native,slideXml,effective}) {
  const metrics=[...catalogue.values()].filter(metric=>['percent','yoy','mom','growth','achievement'].includes(metric.type)
    ||(metric.type==='ratio'&&metric.canonical_unit==='%'));
  if(!metrics.length) return notRun('typed','No percent-typed metrics are declared.');
  const errors=[],notes=[];
  let pointsChecked=0,textsChecked=0,fractionMetrics=0;
  for(const metric of metrics) {
    if(metric.storage_scale==='fraction') fractionMetrics++;
    const metricPositions=positions.filter(item=>item.metric.id===metric.id);
    for(const item of metricPositions) {
      pointsChecked++;
      const factor=chartNormalizationFactor(metric);
      const expected=metric.effective_value===null?null:metric.effective_value/factor;
      const actual=nativeSeriesFor(native,item.routeIndex,item.seriesIndex)?.values?.[item.valueIndex];
      if(!chartValuesMatch(actual,expected)) errors.push(`metric ${metric.id} chart point ${item.valueIndex+1} ${String(actual)} does not match percent-effective ${String(expected)}`);
    }
    for(const usage of usages.filter(item=>item.metric_id===metric.id)) {
      const xml=slideXml.get(usage.slideIndex+1)||'';
      const texts=normalizedTexts(xml),joined=joinedNormalizedTexts(xml);
      const formatted=formattedForUsage(usage,metric,effective);
      if(formatted==null) { errors.push(`metric ${metric.id} usage ${usage.pointer} cannot be formatted from its metric contract`); continue; }
      const wanted=normalizeText(formatted);
      if(!wanted.includes('%')) errors.push(`metric ${metric.id} text usage ${usage.pointer} omits the percent suffix`);
      if(!texts.includes(wanted)&&!joined.includes(wanted)) errors.push(`slide ${usage.slideIndex+1} text ${JSON.stringify(wanted)} is missing for percent metric ${metric.id}`);
      textsChecked++;
    }
  }
  return check('typed',{errors,notes,metrics:metrics.map(metric=>metric.id),points_checked:pointsChecked,
    texts_checked:textsChecked,fraction_storage_metrics:fractionMetrics});
}

function percentagePoints({catalogue,positions,usages,native,slideXml,effective}) {
  const metrics=[...catalogue.values()].filter(metric=>metric.type==='pp'||metric.canonical_unit==='pp');
  if(!metrics.length) return notRun('typed','No percentage-point metrics are declared.');
  const errors=[],notes=[];
  let pointsChecked=0,textsChecked=0;
  for(const metric of metrics) {
    for(const item of positions.filter(candidate=>candidate.metric.id===metric.id)) {
      pointsChecked++;
      const expected=metric.effective_value;
      const actual=nativeSeriesFor(native,item.routeIndex,item.seriesIndex)?.values?.[item.valueIndex];
      if(!chartValuesMatch(actual,expected)) errors.push(`metric ${metric.id} chart point ${item.valueIndex+1} ${String(actual)} does not match pp value ${String(expected)}`);
    }
    for(const usage of usages.filter(item=>item.metric_id===metric.id)) {
      const xml=slideXml.get(usage.slideIndex+1)||'';
      const texts=normalizedTexts(xml),joined=joinedNormalizedTexts(xml);
      const formatted=formattedForUsage(usage,metric,effective);
      if(formatted==null) { errors.push(`metric ${metric.id} usage ${usage.pointer} cannot be formatted from its metric contract`); continue; }
      const wanted=normalizeText(formatted);
      if(!/pp\b/.test(wanted)) errors.push(`metric ${metric.id} text usage ${usage.pointer} omits the pp suffix`);
      if(wanted.includes('%')&&!wanted.includes('pp')) errors.push(`metric ${metric.id} text usage ${usage.pointer} uses % for a percentage-point fact`);
      if(!texts.includes(wanted)&&!joined.includes(wanted)) errors.push(`slide ${usage.slideIndex+1} text ${JSON.stringify(wanted)} is missing for pp metric ${metric.id}`);
      textsChecked++;
    }
  }
  return check('typed',{errors,notes,metrics:metrics.map(metric=>metric.id),points_checked:pointsChecked,texts_checked:textsChecked});
}

function chartTableReconciliation({positions,usages,slideXml,typedMode}) {
  if(!typedMode) return notRun('legacy','No typed metric links connect chart facts to table or KPI facts.');
  const errors=[],notes=[];
  const chartMetrics=new Set(positions.map(item=>item.metric.id));
  const tableUsages=usages.filter(item=>isTablePointer(item.pointer));
  const matched=[];
  let cellsChecked=0;
  for(const metricId of chartMetrics) {
    const candidates=tableUsages.filter(item=>item.metric_id===metricId);
    if(!candidates.length) continue;
    matched.push(metricId);
    for(const usage of candidates) {
      const xml=slideXml.get(usage.slideIndex+1)||'';
      const texts=normalizedTexts(xml),joined=joinedNormalizedTexts(xml),wanted=normalizeText(usage.expected);
      const tables=tableRows(xml),cell=tableCellAt(tables,usage.pointer);
      if(cell!=null) {
        cellsChecked++;
        if(normalizeText(cell)!==wanted) errors.push(`slide ${usage.slideIndex+1} ${usage.pointer} "${normalizeText(cell)}" does not reconcile with metric ${metricId} chart fact ${JSON.stringify(wanted)}`);
      } else if(!texts.includes(wanted)&&!joined.includes(wanted)) errors.push(`slide ${usage.slideIndex+1} native text is missing metric ${metricId} table/KPI fact ${JSON.stringify(wanted)}`);
    }
  }
  if(!matched.length) return partial('typed','Charts and table/KPI facts exist but no metric is used in both within this spec.',{chart_metrics:[...chartMetrics],table_usages:tableUsages.length});
  return check('typed',{errors,notes,reconciled_metrics:matched,cells_checked:cellsChecked,table_usages:tableUsages.length});
}

function distinctness({native,routes,plans}) {
  const pairs=[],errors=[],notes=[];
  let chartsChecked=0;
  for(const [routeIndex,route] of routes.entries()) {
    const chart=native.charts[routeIndex],plan=plans[routeIndex];
    if(!chart||!plan) continue;
    chartsChecked++;
    if(plan.category_colors) {
      if(['sequential','diverging','semantic'].includes(plan.palette_type)) {
        notes.push(`chart ${routeIndex+1} uses a declared ${plan.palette_type} value palette; pairwise categorical distance is not applicable`);
        continue;
      }
      const pointColors=chart.series[0]?.point_colors||[];
      const byIndex=new Map(pointColors.map(item=>[item.index,item.color]));
      const labelCount=Math.max(chart.series[0]?.category_labels?.length||0,plan.labels?.length||0);
      const colors=[];
      for(let index=0;index<labelCount;index++) colors.push(byIndex.get(index)??(index===0?chart.series[0]?.color:null));
      if(colors.filter(Boolean).length<2) { notes.push(`chart ${routeIndex+1} has no emitted category paints to compare`); continue; }
      const repeated=[];
      for(let i=0;i<colors.length;i++) for(let j=i+1;j<colors.length;j++) {
        if(!colors[i]||!colors[j]) continue;
        const de=deltaE76(colors[i],colors[j]),gray=grayscaleDelta(colors[i],colors[j]);
        pairs.push({a:String(i+1),b:String(j+1),delta_e:round(de),grayscale:round(gray)});
        if(de<MIN_DELTA_E&&gray<MIN_GRAY) {
          if(plan.legacy_overflow) repeated.push(`${i+1}/${j+1}`);
          else errors.push(`chart ${routeIndex+1} categories ${i+1} and ${j+1} are not distinguishable (ΔE76 ${round(de)}, grayscale ${round(gray)})`);
        }
      }
      if(repeated.length) notes.push(`chart ${routeIndex+1} legacy palette overflows for category pairs ${repeated.join(', ')}; split the chart so every category has a nominal colour`);
    } else if(chart.series.length>1) {
      for(let i=0;i<chart.series.length;i++) for(let j=i+1;j<chart.series.length;j++) {
        const a=chart.series[i],b=chart.series[j];
        if(!a.color||!b.color) continue;
        const de=deltaE76(a.color,b.color),gray=grayscaleDelta(a.color,b.color);
        const secondary=a.dash!==b.dash||a.marker?.symbol!==b.marker?.symbol;
        pairs.push({a:a.name||a.index,b:b.name||b.index,delta_e:round(de),grayscale:round(gray),a_dash:a.dash,b_dash:b.dash,a_symbol:a.marker?.symbol,b_symbol:b.marker?.symbol});
        if(de<MIN_DELTA_E&&gray<MIN_GRAY&&!secondary) errors.push(`chart ${routeIndex+1} series ${i+1} and ${j+1} reuse paint without a distinct dash or marker`);
        else if(de<MIN_DELTA_E&&secondary) notes.push(`chart ${routeIndex+1} series ${i+1} and ${j+1} depend on dash/marker rather than colour separation`);
      }
    }
  }
  if(!chartsChecked) return notRun('heuristic','No native charts were available.');
  if(!pairs.length) return notRun('heuristic','Every chart has a single mark; pairwise distinguishability does not apply.');
  return check('heuristic',{errors,notes,pairs,charts_checked:chartsChecked,
    thresholds:{delta_e76:MIN_DELTA_E,grayscale:MIN_GRAY}});
}

function colorSemantics({native,routes,plans,style}) {
  if(!style) return notRun('heuristic','Profile/style could not be re-derived, so the chosen build encoding is unknown.');
  const errors=[],notes=[];
  let seriesChecked=0,categoryPointsChecked=0,roleStylesChecked=0;
  const paletteTypes=new Set();
  for(const [routeIndex,route] of routes.entries()) {
    const chart=native.charts[routeIndex],plan=plans[routeIndex];
    if(!chart||!plan) continue;
    paletteTypes.add(plan.palette_type);
    if(plan.category_colors) {
      const pointColors=chart.series[0]?.point_colors||[];
      const byIndex=new Map(pointColors.map(item=>[item.index,item.color]));
      for(const [index,expected] of (plan.colors||[]).entries()) {
        const actual=byIndex.get(index)??(index===0?chart.series[0]?.color:null);
        categoryPointsChecked++;
        if(!actual) errors.push(`chart ${routeIndex+1} category ${index+1} is missing its expected native point paint ${expected}`);
        else if(String(actual).toUpperCase()!==String(expected).toUpperCase()) errors.push(`chart ${routeIndex+1} category ${index+1} paint ${actual} does not match encoded colour ${expected}`);
      }
    } else {
      for(const [seriesIndex,expected] of (plan.series||[]).entries()) {
        const actual=chart.series[seriesIndex];
        if(!actual) continue;
        seriesChecked++;
        if(expected.color&&!actual.color) {
          errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} is missing its expected native paint ${expected.color}`);
        } else if(expected.color&&String(actual.color).toUpperCase()!==String(expected.color).toUpperCase()) {
          errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} paint ${actual.color} does not match encoded colour ${expected.color}`);
        }
        if(routeKind(route)==='line') {
          roleStylesChecked++;
          const actualDash=actual.dash||'solid',actualSymbol=actual.marker?.symbol||'none';
          if(expected.dash&&expected.dash!==actualDash) errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} dash ${actualDash} does not match encoded ${expected.dash}`);
          if(expected.symbol&&expected.symbol!==actualSymbol) errors.push(`chart ${routeIndex+1} series ${seriesIndex+1} marker ${actualSymbol} does not match encoded ${expected.symbol}`);
        }
      }
    }
  }
  if(!seriesChecked&&!categoryPointsChecked) return notRun('heuristic','No comparable native series or category paints were present.');
  return check('heuristic',{errors,notes,series_checked:seriesChecked,category_points_checked:categoryPointsChecked,
    role_styles_checked:roleStylesChecked,palette_types:[...paletteTypes],boundary:'Deterministic paint/role comparison; aesthetic preference is not judged.'});
}

function legendMapping({native,routes}) {
  const errors=[],notes=[];
  let legendsChecked=0,seriesNamesChecked=0,labelsChecked=0;
  if(!native.charts.length) return notRun('typed','No native charts were available.');
  for(const [routeIndex,route] of routes.entries()) {
    const chart=native.charts[routeIndex];
    if(!chart) continue;
    legendsChecked++;
    if(chart.series.length!==route.series.length) errors.push(`chart ${routeIndex+1} native series ${chart.series.length} cannot map to ${route.series.length} declared series`);
    const count=Math.min(chart.series.length,route.series.length);
    const names=[];
    for(let index=0;index<count;index++) {
      const expected=route.series[index]?.name??null;
      const actual=chart.series[index]?.name??null;
      if(expected!=null) {
        seriesNamesChecked++;
        if(normalizeText(actual)!==normalizeText(expected)) errors.push(`chart ${routeIndex+1} native series ${index+1} "${actual}" does not match declared legend name "${expected}"`);
        names.push(normalizeText(expected));
      }
      const expectedLabels=expectedSeriesLabels(route,route.series[index]).map(normalizeText);
      const actualLabels=(chart.series[index]?.category_labels||[]).map(normalizeText);
      if(expectedLabels.length!==actualLabels.length) errors.push(`chart ${routeIndex+1} series ${index+1} legend/category count ${actualLabels.length} does not match declared ${expectedLabels.length}`);
      else for(const [labelIndex,label] of expectedLabels.entries()) {
        labelsChecked++;
        if(actualLabels[labelIndex]!==label) errors.push(`chart ${routeIndex+1} series ${index+1} category ${labelIndex+1} "${actualLabels[labelIndex]}" does not match declared "${label}"`);
      }
    }
    if(new Set(names).size!==names.length) errors.push(`chart ${routeIndex+1} repeats a legend name; series cannot be mapped uniquely`);
    if(route.series.length>1&&!chart.legend.present) errors.push(`chart ${routeIndex+1} has ${route.series.length} series but no native legend`);
    for(const deletion of chart.legend.deletions||[]) if(deletion<route.series.length) errors.push(`chart ${routeIndex+1} legend deletes declared series ${deletion+1}`);
    if(route.series.length===1&&['pie','doughnut'].includes(routeKind(route))&&!chart.legend.present) notes.push(`chart ${routeIndex+1} pie/doughnut has no native legend; category labels must remain visible elsewhere`);
  }
  return check('typed',{errors,notes,legends_checked:legendsChecked,series_names_checked:seriesNamesChecked,labels_checked:labelsChecked});
}

function accessibility({native,routes,plans,style,distinct}) {
  if(!style) return notRun('heuristic','Profile/style could not be re-derived for contrast checks.');
  const errors=[],notes=[];
  const background=style.tokens?.chart?.background||style.background||'FFFFFF';
  const contrast=[];
  let colorsChecked=0;
  for(const [routeIndex,route] of routes.entries()) {
    const chart=native.charts[routeIndex],plan=plans[routeIndex];
    if(!chart) continue;
    const colors=plan?.category_colors
      ?(chart.series[0]?.point_colors||[]).map(item=>item.color)
      :chart.series.map(item=>item.color).filter(Boolean);
    for(const color of colors) {
      if(!/^[0-9A-Fa-f]{6}$/.test(String(color))) continue;
      colorsChecked++;
      const ratio=round(contrastRatio(color,background));
      contrast.push({chart:routeIndex+1,color,ratio});
      if(ratio<MIN_CONTRAST) errors.push(`chart ${routeIndex+1} series paint ${color} has ${ratio}:1 contrast against ${background}; minimum is ${MIN_CONTRAST}:1`);
    }
    if(chart.series.length>1&&!chart.legend.present) errors.push(`chart ${routeIndex+1} multi-series chart has no native legend for non-colour identification`);
  }
  if(distinct.status==='FAIL') errors.push('series/category distinguishability failed; colour accessibility cannot pass');
  if(!colorsChecked) return notRun('heuristic','No native series or category paints were available for contrast checks.');
  const notesAll=[...notes,...(distinct.notes||[])];
  const status=distinct.status==='PARTIAL'?'PARTIAL':undefined;
  return check('heuristic',{status,errors,notes:notesAll,colors_checked:colorsChecked,contrast,background,
    thresholds:{contrast:MIN_CONTRAST,delta_e76:MIN_DELTA_E,grayscale:MIN_GRAY},
    boundary:'Contrast/distinguishability heuristic only; text size, reading order and visual clarity require independent review.'});
}

function narrativeCheck(effective,{plan}={}) {
  let report;
  try { report=inspectNarrative(effective,{plan}); }
  catch(error) { return {status:'FAIL',mode:'declarative',errors:[error.message],report:null}; }
  const mapped=report.status==='FAIL'?'FAIL':report.status==='NOT_RUN'?'NOT_RUN':report.status==='PASS_WITH_NOTES'?'PARTIAL':'PASS';
  return {status:mapped,mode:'declarative',errors:report.errors||[],notes:report.notes||[],report,
    boundary:'Declared graph structure and retained output presence; meaning, source truth and inference require review.'};
}

async function runSemanticQa({pptxPath,spec,repoRoot,profileRef,specDir,scenePath,plan}={}) {
  if(!pptxPath) throw new Error('semantic QA requires a PPTX path');
  if(!spec||typeof spec!=='object') throw new Error('semantic QA requires the original source spec');
  repoRoot=repoRoot||path.resolve(__dirname,'../..');
  specDir=specDir||process.cwd();
  const snapshot=JSON.stringify(spec);
  const native=await loadNativeDeck(pptxPath,{workbooks:true});
  let scene=null,sceneError=null;
  if(scenePath) {
    try { scene=JSON.parse(fs.readFileSync(scenePath,'utf8')); }
    catch(error) { sceneError=error.message; }
  }
  let prepared;
  try { prepared=prepareDeckSemantics(spec); }
  catch(error) {
    return {status:'FAIL',pptx_sha256:native.pptx_sha256,source_spec_sha256:null,
      scope:'Semantic preparation failed; no native semantic checks could be issued.',
      errors:[`semantic preparation failed: ${error.message}`],
      checks:{NUMERIC_SEMANTIC_FIDELITY:{status:'FAIL',mode:'typed',errors:[error.message]},VISUAL_QA:{status:'NOT_RUN',reason:'No automated visual judgment.'}}};
  }
  const effective=prepared.spec,semantics=prepared.report,catalogue=prepared.catalogue;
  const immutable=sourceImmutability(snapshot,spec);
  const typedMode=Boolean((spec.metrics||[]).length)||(spec.slides||[]).some(slide=>
    (Array.isArray(slide.metric_bindings)&&slide.metric_bindings.length)
    ||(slide.series||[]).some(item=>item?.metric_id!=null||Array.isArray(item?.metric_ids))
    ||(slide.dashboard?.series||[]).some(item=>item?.metric_id!=null||Array.isArray(item?.metric_ids))
    ||(slide.panels||[]).some(panel=>(panel.series||[]).some(item=>item?.metric_id!=null||Array.isArray(item?.metric_ids))));
  const routes=expectedRoutes(effective,repoRoot);
  let style=null,profileId=null,profileError=null;
  const candidates=[profileRef||scene?.theme_decision?.selected_profile||spec.profile||'executive-clean'];
  for(const candidate of [...new Set(candidates)]) {
    try { style=resolveStyle(loadProfile(candidate,repoRoot,new Set(),specDir),spec); profileId=candidate; break; }
    catch(error) { profileError=error.message; }
  }
  let plans=[],planError=null;
  if(style) {
    try { plans=alignPlans(routes,createEncoding(effective,style).chartPlansForSpec()); }
    catch(error) { planError=error.message; }
  }
  const slideXml=await slideXmlMap(native,(effective.slides||[]).length);
  const positions=metricPositionsFor(routes,catalogue);
  const usages=textUsagesFor(semantics);
  const numeric=numericFidelity({native,routes,effective,semantics,slideXml,typedMode,catalogue});
  if(!immutable) { numeric.status='FAIL'; numeric.errors.unshift('prepareDeckSemantics mutated the original source spec; it must be immutable'); numeric.source_spec_immutable=false; }
  if(native.charts.length!==routes.length) { numeric.status='FAIL'; }
  const family=chartFamily({native,routes});
  const axes=chartAxisIntegrity({native,routes});
  const units=unitConsistency({native,routes,slideXml,catalogue,typedMode});
  const percent=percentageScale({catalogue,positions,usages,native,slideXml,effective});
  const pp=percentagePoints({catalogue,positions,usages,native,slideXml,effective});
  const reconciliation=chartTableReconciliation({positions,usages,slideXml,typedMode});
  const distinct=distinctness({native,routes,plans});
  const colors=colorSemantics({native,routes,plans,style});
  const legend=legendMapping({native,routes});
  const access=accessibility({native,routes,plans,style,distinct});
  let sidecar=notRun('typed',scenePath?'Scene file was not readable.':'No build scene was supplied.');
  if(scenePath) {
    if(sceneError) sidecar={status:'FAIL',mode:'typed',errors:[`scene file could not be read: ${sceneError}`]};
    else if(scene?.pptx_sha256) {
      if(scene.pptx_sha256!==native.pptx_sha256) sidecar={status:'FAIL',mode:'typed',errors:[`scene pptx_sha256 ${scene.pptx_sha256} does not match final PPTX ${native.pptx_sha256}`]};
      else sidecar={status:'PASS',mode:'typed',note:'Scene is hash-bound to this PPTX; its PASS claims are not used as evidence.'};
    } else sidecar={status:'PARTIAL',mode:'typed',reason:'Scene has no pptx_sha256 binding.'};
  }
  if(planError) { colors.status='FAIL'; colors.errors.push(`visual encoding could not be re-derived: ${planError}`); }
  if(profileError&&!style) {
    for(const checkItem of [colors,access]) { checkItem.status='FAIL'; checkItem.errors=[...(checkItem.errors||[]),`profile/style could not be re-derived: ${profileError}`]; }
  }
  const narrative=narrativeCheck(effective,{plan});
  const checks={
    NUMERIC_SEMANTIC_FIDELITY:numeric,
    CHART_TYPE_FIDELITY:family,
    CHART_AXIS_INTEGRITY:axes,
    UNIT_CONSISTENCY:units,
    PERCENTAGE_SCALE_VALIDATION:percent,
    PERCENT_POINT_VALIDATION:pp,
    CHART_TABLE_NUMERIC_RECONCILIATION:reconciliation,
    CHART_SERIES_DISTINGUISHABILITY:distinct,
    CHART_COLOR_SEMANTICS:colors,
    CHART_LEGEND_SERIES_MAPPING:legend,
    CHART_ACCESSIBILITY:access,
    NARRATIVE_STRUCTURE:narrative,
    SIDECAR_BINDING:sidecar,
    VISUAL_QA:{status:'NOT_RUN',mode:'human',reason:'Requires an independent reviewer inspecting actual rendered pages; semantic QA never grants visual PASS.'},
  };
  const errors=[];const warnings=[];
  for(const [name,item] of Object.entries(checks)) {
    for(const message of item.errors||[]) pushUnique(errors,`${name}: ${message}`);
    for(const message of item.notes||[]) pushUnique(warnings,`${name}: ${message}`);
  }
  for(const checkName of ['NUMERIC_SEMANTIC_FIDELITY','CHART_TYPE_FIDELITY','CHART_AXIS_INTEGRITY','UNIT_CONSISTENCY','CHART_TABLE_NUMERIC_RECONCILIATION','CHART_LEGEND_SERIES_MAPPING']) {
    if(checks[checkName].status==='FAIL') pushUnique(errors,`${checkName} failed`);
  }
  const blocking=Object.values(checks).some(item=>item.status==='FAIL');
  const incomplete=Object.values(checks).some(item=>item.status==='PARTIAL'||item.status==='NOT_RUN');
  const status=blocking?'FAIL':incomplete?'PASS_WITH_NOTES':'PASS';
  const chartPayload=native.charts.map((chart,index)=>({part:chart.part,kind:chart.kind,route:routes[index]?.route||null,
    slide:routes[index]?routes[index].slideIndex+1:null,series:chart.series.map(item=>({name:item.name,values:item.values,
      labels:item.category_labels,color:item.color,dash:item.dash,marker:item.marker,label_format:item.label_format})),
    workbook:chart.workbook?{status:chart.workbook.status,part:chart.workbook.part}:null,
    legend:chart.legend,formats:formatDiagnostics(chart)}));
  return {
    status,
    pptx_sha256:native.pptx_sha256,
    source_spec_sha256:sha256(Buffer.from(snapshot)),
    effective_spec_sha256:sha256(Buffer.from(JSON.stringify(effective))),
    scope:'Re-derives typed semantics from the original spec and compares native chart cache, workbook cells, table/KPI text, formats, legends and encoded paints. Colour/distinguishability checks are engineering heuristics; visual and source-truth judgment remain NOT_RUN.',
    profile:profileId,
    typed:typedMode,
    routes:routes.map((route,index)=>({index,route:route.route,slide:route.slideIndex+1,panel:route.panelIndex??null,
      kind:routeKind(route),series:route.series.length,labels:expectedSeriesLabels(route,route.series[0]).length,plan:Boolean(plans[index])})),
    checks,
    errors,
    warnings,
    narrative,
    charts:chartPayload,
    artifacts:{semantic_report:null},
    boundaries:{visual_review:'NOT_RUN',source_truth:'NOT_AUTHENTICATED',aesthetic_judgment:'NOT_RUN'},
  };
}

module.exports={runSemanticQa,expectedRoutes,routeKind};
