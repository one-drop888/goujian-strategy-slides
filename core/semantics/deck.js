'use strict';
// Deterministic deck-level semantics: metric catalogue, placeholders, numeric bindings,
// typed series and explicit chart contracts. The input spec is never mutated.
const crypto=require('crypto');
const {close}=require('../reasoning/calculations');
const {
  validateMetricCatalogue,resolveMetricRef,formatMetric,formatCodeForMetric,chartNormalizationFactor,unitLabel,
  substituteSlideMetrics,reconcileMetricBindings,normalizeUnit,normalizeScale,effectiveFromRaw,
} = require('./numeric');

const CHART_KINDS=new Set(['bar','column','line','area','pie','doughnut']);
const PERCENT_FORMAT=/^0(?:\.0+)?\s*"%"$/;

function sha256(value) { return crypto.createHash('sha256').update(value).digest('hex'); }
function clone(value) { return structuredClone(value); }
function isFiniteNumber(value) { return typeof value==='number'&&Number.isFinite(value); }
function valuesEqual(a,b) { return a===null&&b===null || (isFiniteNumber(a)&&isFiniteNumber(b)&&close(a,b)); }

function inferKind(slide) {
  if(slide.chartType) return slide.chartType;
  if(['line','trend','cohort'].includes(slide.type)) return 'line';
  if(slide.type==='area') return 'area';
  if(['bar','benchmark','distribution'].includes(slide.type)) return 'bar';
  if(['column','variance','cost-structure','histogram','waterfall','bridge'].includes(slide.type)) return 'column';
  if(slide.type==='chart') return slide.chartType||'bar';
  return null;
}

function seriesList(slide) {
  const charts=[];
  const kind=inferKind(slide);
  if(Array.isArray(slide.series)&&slide.series.length&&kind) charts.push({kind,series:slide.series,path:'/series',slide});
  if(slide.dashboard?.series) charts.push({kind:'line',series:slide.dashboard.series,path:'/dashboard/series',slide,dashboard:true});
  for(const [index,panel] of (slide.panels||[]).entries()) {
    if(panel.kind==='chart') charts.push({kind:panel.chartType||'bar',series:panel.series||[],path:`/panels/${index}/series`,slide,panel,panelIndex:index});
  }
  return charts;
}

function metricScale(metric) { return metric.storage_scale; }
function scaleRaw(value,scale) {
  if(value===null) return null;
  const normalized=normalizeScale(scale);
  if(normalized==='fraction') return value*100;
  if(normalized==='percent'||normalized==='unit') return value;
  if(normalized==='thousand') return value*1e3;
  if(normalized==='million') return value*1e6;
  if(normalized==='billion') return value*1e9;
  throw new Error(`unsupported storage_scale ${scale}`);
}

function typedSeries(slide,chart,catalogue,slideName,transformations,usedMetrics) {
  for(const [index,series] of chart.series.entries()) {
    if(!series||typeof series!=='object') throw new Error(`${slideName}: ${chart.path}[${index}] must be an object`);
    if(series.metric_id!=null&&series.metric_ids!=null) throw new Error(`${slideName}: ${chart.path}[${index}] must use metric_id or metric_ids, not both`);
    const pointer=`${chart.path}/${index}`;
    let metrics=null;
    if(series.metric_id!=null) {
      metrics=[resolveMetricRef(catalogue,series.metric_id,{label:`${slideName}: ${pointer}.metric_id`})];
      usedMetrics.add(metrics[0].id);
    } else if(series.metric_ids!=null) {
      if(!Array.isArray(series.metric_ids)||!series.metric_ids.length) throw new Error(`${slideName}: ${pointer}.metric_ids must be a nonempty array`);
      metrics=series.metric_ids.map((id,position)=>resolveMetricRef(catalogue,id,{label:`${slideName}: ${pointer}.metric_ids[${position}]`}));
      for(const metric of metrics) usedMetrics.add(metric.id);
      if(new Set(metrics.map(item=>item.id)).size!==metrics.length) throw new Error(`${slideName}: ${pointer}.metric_ids must not repeat a metric`);
    }
    if(metrics) {
      if(series.storage_scale!=null) {
        const declared=normalizeScale(series.storage_scale);
        const conflict=metrics.find(metric=>metricScale(metric)!==declared);
        if(conflict) throw new Error(`${slideName}: ${pointer}.storage_scale ${declared} conflicts with metric ${conflict.id} storage_scale ${conflict.storage_scale}`);
      }
      if(series.display_unit!=null) {
        const declared=normalizeUnit(series.display_unit);
        const conflict=metrics.find(metric=>normalizeUnit(metric.canonical_unit)!==declared);
        if(conflict) throw new Error(`${slideName}: ${pointer}.display_unit ${series.display_unit} conflicts with metric ${conflict.id} unit ${conflict.canonical_unit}`);
      }
      const effective=metrics.map(metric=>metric.effective_value);
      if(series.values!=null) {
        if(series.values.length!==effective.length) throw new Error(`${slideName}: ${pointer}.values length ${series.values.length} does not match ${effective.length} metrics`);
        for(const [position,value] of series.values.entries()) {
          if(!valuesEqual(value,effective[position])) {
            throw new Error(`${slideName}: ${pointer}.values[${position}] ${value} does not match metric ${metrics[position].id} effective value ${effective[position]}`);
          }
          if(value!==effective[position]) {
            transformations.push({slide:slideName,pointer:`${pointer}/values/${position}`,kind:'normalize-float',from:value,to:effective[position],reason:`metric ${metrics[position].id} exact value`});
            series.values[position]=effective[position];
          }
        }
      } else {
        series.values=effective.slice();
        transformations.push({slide:slideName,pointer,kind:'fill-from-metrics',metrics:metrics.map(metric=>metric.id),to:effective,reason:'typed series values were not duplicated in the spec'});
      }
      if(!Array.isArray(series.labels)||!series.labels.length) {
        const declared=chart.panel?.labels||(chart.dashboard?slide.dashboard.labels:slide.labels);
        series.labels=Array.isArray(declared)&&declared.length?declared.slice():metrics.map((metric,position)=>metric.time_window||metric.name||String(position+1));
        if(series.labels.length!==effective.length)throw new Error(`${slideName}: declared category labels must match metric points`);
        transformations.push({slide:slideName,pointer:`${pointer}/labels`,kind:'derive-labels',from:null,to:series.labels,reason:declared?.length?'preserved author category labels':'labels derived from metric time_window/name'});
      } else if(series.labels.length!==effective.length) {
        throw new Error(`${slideName}: ${pointer}.labels length ${series.labels.length} does not match ${effective.length} metrics`);
      }
      const factors=metrics.map(chartNormalizationFactor);
      if(new Set(factors).size>1)throw new Error(`${slideName}: chart points mix incompatible display scales`);
      if(factors[0]!==1) {
        series.values=effective.map(value=>value===null?null:value/factors[0]);
        transformations.push({slide:slideName,pointer:`${pointer}/values`,kind:'display-scale',from:effective,to:series.values.slice(),factor:factors[0],metric_ids:metrics.map(metric=>metric.id),reason:'Explicit display scale not representable by native Excel comma scaling'});
      }
      if(series.storage_scale==null) series.storage_scale=metrics[0].storage_scale;
      const policies=[...new Set(metrics.filter(metric=>metric.missing_policy).map(metric=>metric.missing_policy))];
      if(policies.length>1) throw new Error(`${slideName}: ${pointer} metrics disagree on missing_policy (${policies.join(', ')})`);
      if(policies.length===1) {
        if(slide.missing_policy&&slide.missing_policy!==policies[0]) throw new Error(`${slideName}: slide missing_policy ${slide.missing_policy} conflicts with metric missing_policy ${policies[0]}`);
        if(!slide.missing_policy) {
          slide.missing_policy=policies[0];
          transformations.push({slide:slideName,pointer:'/missing_policy',kind:'derive-missing-policy',from:null,to:policies[0],reason:'metric null policy'});
        }
      }
    } else if(series.storage_scale!=null) {
      if(!Array.isArray(series.values)) throw new Error(`${slideName}: ${pointer}.storage_scale requires explicit values`);
      const before=series.values.slice();
      series.values=series.values.map(value=>{
        if(value===null) return null;
        if(!isFiniteNumber(value)) throw new Error(`${slideName}: ${pointer}.values must be finite numbers or null`);
        return scaleRaw(value,series.storage_scale);
      });
      if(before.some((value,position)=>value!==series.values[position])) {
        transformations.push({slide:slideName,pointer:`${pointer}/values`,kind:'convert-storage-scale',from:before,to:series.values,reason:`series storage_scale ${normalizeScale(series.storage_scale)}`});
      }
    }
    if(Array.isArray(series.values)) {
      const nulls=series.values.filter(value=>value===null).length;
      if(nulls&&series.values.some(value=>value!==null&&!isFiniteNumber(value))) throw new Error(`${slideName}: ${pointer}.values must be finite numbers or null`);
      if(series.values.length!==(series.labels||chart.panel?.labels||chart.slide.dashboard?.labels||chart.slide.labels||[]).length) {
        throw new Error(`${slideName}: ${pointer} labels and values must have matching lengths`);
      }
    }
  }
}

function applyFormatAndUnit(slide,chart,catalogue,slideName,transformations) {
  const target=chart.panel||(chart.dashboard?slide.dashboard:slide);
  const formats=new Set(),units=new Set();
  for(const series of chart.series) {
    const ids=series.metric_ids||(series.metric_id?[series.metric_id]:[]);
    for(const id of ids) {
      const metric=resolveMetricRef(catalogue,id,{label:`${slideName}: metric`});
      formats.add(formatCodeForMetric(metric,{normalized:chartNormalizationFactor(metric)!==1}));
      units.add(unitLabel(metric)||'');
    }
    if(!ids.length&&['%','pp'].includes(normalizeUnit(series.display_unit))) {const unit=normalizeUnit(series.display_unit);formats.add(`0.0"${unit}"`);units.add(unit);}
  }
  if(['pie','doughnut'].includes(chart.kind)) {
    const points=chart.series.flatMap(series=>(series.metric_ids||(series.metric_id?[series.metric_id]:[])).map(id=>resolveMetricRef(catalogue,id)));
    if(points.some(metric=>['pp','growth','yoy','mom','achievement','difference'].includes(metric.type)))throw new Error(`${slideName}: pie/doughnut cannot encode changes, percentage points or attainment as parts of a whole; use a comparison chart`);
    if(points.some(metric=>metric.canonical_unit==='%')) {
      const partBases=new Set(['part_of_whole','part-of-whole','share','proportion','composition']);
      if(points.some(metric=>metric.canonical_unit!=='%'||!partBases.has(metric.comparison_basis))||!close(points.reduce((total,metric)=>total+(metric.effective_value??0),0),100))throw new Error(`${slideName}: typed pie percentages require a complete declared part-of-whole total of100; include the remainder or use a comparison chart`);
    }
  }
  if(formats.size>1) throw new Error(`${slideName}: chart series mix incompatible number formats (${[...formats].join(', ')}); split the chart or set an explicit numberFormat`);
  if(units.size>1) throw new Error(`${slideName}: chart series mix incompatible units (${[...units].filter(Boolean).join(', ')}); split the chart or normalize explicitly`);
  const format=[...formats][0],unit=[...units][0];
  if(format&&!target.numberFormat) {
    target.numberFormat=format;
    transformations.push({slide:slideName,pointer:`${chart.path.split('/series')[0]}/numberFormat`,kind:'derive-number-format',from:null,to:format,reason:'metric type/precision'});
  } else if(format&&target.numberFormat!==format) {
    throw new Error(`${slideName}: numberFormat ${target.numberFormat} conflicts with metric format ${format}`);
  }
  if(unit) {
    const declared=target.unit==null?'':String(target.unit).trim();
    const firstId=(chart.series[0].metric_ids||[chart.series[0].metric_id]).find(Boolean);
    const metric=firstId?resolveMetricRef(catalogue,firstId):null;
    if(declared&&normalizeUnit(declared)!==normalizeUnit(unit)&&declared!==metric?.canonical_unit)throw new Error(`${slideName}: unit ${declared} conflicts with metric unit ${unit}`);
    if(declared!==unit) {
      target.unit=unit;
      transformations.push({slide:slideName,pointer:`${chart.path.split('/series')[0]}/unit`,kind:'derive-unit',from:declared||null,to:unit,reason:'Metric base unit and explicit display scale'});
    }
  }
  return format;
}

function validateBins(bins,slideName) {
  if(!Array.isArray(bins)||bins.length<2) throw new Error(`${slideName}: histogram requires at least two explicit bins`);
  const labels=[],counts=[];
  const width=bins[0]?.end-bins[0]?.start;
  for(const [index,bin] of bins.entries()) {
    if(!bin||typeof bin!=='object') throw new Error(`${slideName}: bins[${index}] must be an object`);
    if(!isFiniteNumber(bin.start)||!isFiniteNumber(bin.end)) throw new Error(`${slideName}: bins[${index}] requires finite start/end`);
    if(!(bin.start<bin.end)) throw new Error(`${slideName}: bins[${index}] start must be less than end`);
    if(!isFiniteNumber(bin.count)||bin.count<0) throw new Error(`${slideName}: bins[${index}].count must be a nonnegative finite number`);
    if(index&&!close(bins[index-1].end,bin.start)) throw new Error(`${slideName}: bins[${index}] is not contiguous with the previous bin`);
    if(index&&!close(bin.end-bin.start,width)) throw new Error(`${slideName}: histogram bins require equal widths; bins[${index}] width ${bin.end-bin.start} differs from ${width}`);
    labels.push(`${bin.start}–${bin.end}`);
    counts.push(bin.count);
  }
  return {labels,counts};
}

function chartContracts(slide,chart,slideName,transformations) {
  const kind=String(chart.kind||'').toLowerCase();
  if(!CHART_KINDS.has(kind)) throw new Error(`${slideName}: unsupported native chart type ${chart.kind}; designed chart types are rejected before rendering`);
  const series=chart.series;
  if(!Array.isArray(series)||!series.length) throw new Error(`${slideName}: chart requires at least one series`);
  if(series.length>4) throw new Error(`${slideName}: chart series exceed the supported four-series contract; split the chart`);
  const ids=series.map((item,index)=>item.id==null?null:String(item.id));
  const present=ids.filter(Boolean);
  if(new Set(present).size!==present.length) throw new Error(`${slideName}: chart series ids must be unique`);
  const missingPolicy=slide.missing_policy||null;
  let hasMissing=false;
  for(const [index,item] of series.entries()) {
    if(item.label_strategy!=null||item.labelStrategy!=null) {
      throw new Error(`${slideName}: per-series label_strategy is unsupported; declare visual_encoding.label_strategy for the whole chart`);
    }
    const values=item.values||[];
    if(item.labels&&item.labels.length!==values.length) throw new Error(`${slideName}: series ${index+1} labels and values must have matching lengths`);
    for(const value of values) {
      if(value===null) hasMissing=true;
      else if(!isFiniteNumber(value)) throw new Error(`${slideName}: series ${index+1} values must be finite numbers or null`);
    }
    if(item.style?.color&&!/^[0-9A-Fa-f]{6}$/.test(String(item.style.color))) throw new Error(`${slideName}: series ${index+1} explicit color must be a six-digit hex value`);
  }
  if(kind==='area'&&hasMissing) {
    throw new Error(`${slideName}: area charts cannot render missing values honestly because the filled band visually bridges the gap in office renderers; choose a line chart for an explicit gap or a table that states the missing value; a missing value is never substituted`);
  }
  if(kind==='area') {
    const short=series.find(item=>(item.values||[]).length<2);
    if(short) {
      throw new Error(`${slideName}: area charts require at least two points per series because a single point is visually empty; use a line chart for one point, a KPI value for one number, or a table for one row; the point is never duplicated to fabricate a band`);
    }
  }
  if(hasMissing&&!['gap','null'].includes(missingPolicy)) {
    throw new Error(`${slideName}: null chart values require an explicit missing_policy (gap or null); a missing value is never rendered as zero`);
  }
  if(['pie','doughnut'].includes(kind)) {
    if(series.length!==1) throw new Error(`${slideName}: pie/doughnut requires exactly one series`);
    const values=series[0].values||[];
    if(values.some(value=>value===null)) throw new Error(`${slideName}: pie/doughnut does not support missing values; provide an explicit 'other' category`);
    if(values.some(value=>value<0)) throw new Error(`${slideName}: pie/doughnut requires nonnegative values`);
    if(!values.some(value=>value>0)) throw new Error(`${slideName}: pie/doughnut requires a positive total`);
  }
  const stacked=series.some(item=>item.stack===true);
  if(slide.stack_group!=null) {
    if(typeof slide.stack_group!=='string'||!slide.stack_group.trim()) throw new Error(`${slideName}: stack_group must be a nonempty string`);
  }
  if(stacked&&series.some(item=>item.stack!==true)) throw new Error(`${slideName}: stacked charts require stack:true on every series; mixed stacking would change the reading of the data`);
  if(stacked&&!['bar','column'].includes(kind)) throw new Error(`${slideName}: native stacking is only supported for bar/column charts; split or use separate slides for ${kind}`);
  if(stacked&&hasMissing) throw new Error(`${slideName}: stacked charts with missing values are unsupported; provide explicit values or split the chart`);
  if(slide.histogram||slide.bins) {
    if(!['column','bar'].includes(kind)) throw new Error(`${slideName}: histogram bins require a column/bar chart`);
    const {labels,counts}=validateBins(slide.bins,slideName);
    if(series.length!==1) throw new Error(`${slideName}: histogram accepts exactly one derived frequency series`);
    if(series[0].values&&series[0].values.length!==counts.length) throw new Error(`${slideName}: histogram series length does not match explicit bins`);
    if(series[0].values) for(const [index,value] of series[0].values.entries()) if(!close(value,counts[index])) throw new Error(`${slideName}: histogram count ${value} for bin ${labels[index]} does not match bins[${index}].count ${counts[index]}`);
    series[0].labels=labels;
    series[0].values=counts;
    slide.labels=labels;
    transformations.push({slide:slideName,pointer:'/bins',kind:'derive-histogram',labels,counts,reason:'explicit numeric bins and counts drive the category axis'});
  }
  if(['line','trend','cohort'].includes(slide.semanticType)&&slide.axisMin!=null&&series[0]?.values) {
    const visible=series[0].values.filter(value=>value!==null);
    if(visible.length&&slide.axisMin>Math.min(...visible)&&!String(slide.axis_note||'').trim()) {
      throw new Error(`${slideName}: a truncated line axis requires an explicit axis_note so the scale is visible`);
    }
  }
  if(slide.axisMin!=null&&series.some(item=>(item.values||[]).some(value=>value!==null&&value<slide.axisMin))) {
    throw new Error(`${slideName}: axisMin ${slide.axisMin} would hide values below the axis`);
  }
  if(['bar','column','area'].includes(kind)&&slide.axisMin!=null&&slide.axisMin>0) {
    throw new Error(`${slideName}: ${kind} axes must include zero`);
  }
  return {kind,series_count:series.length,missing:hasMissing,missing_policy:hasMissing?missingPolicy:null,
    stacked,format:slide.numberFormat||null,axis_note:slide.axis_note||null,container:chart.path.split('/')[1]||'series'};
}

function prepareDeckSemantics(spec,options={}) {
  const effective=clone(spec);
  const catalogue=validateMetricCatalogue(effective.metrics);
  const transformations=[],bindings=[],charts=[],usedMetrics=new Set();
  let typed=0;
  for(const [index,slide] of (effective.slides||[]).entries()) {
    const slideName=`slides[${index}]`;
    const substituted=substituteSlideMetrics(slide,catalogue,{slideId:slideName});
    for(const item of substituted.replacements) transformations.push({slide:slideName,pointer:item.pointer,kind:'replace-placeholder',from:item.from,to:item.to,reason:'explicit {{metric:id}} placeholder'});
    if(Array.isArray(slide.metric_bindings)&&slide.metric_bindings.length) {
      const reconciled=reconcileMetricBindings(slide,catalogue,{slideId:slideName,apply:true});
      if(reconciled.errors.length) throw new Error(reconciled.errors.join('; '));
      bindings.push(...reconciled.records.map(record=>({slide:slideName,...record})));
      for(const record of reconciled.records) if(record.metric_id) usedMetrics.add(record.metric_id);
    }
    if(Array.isArray(slide.bins)&&(!Array.isArray(slide.series)||!slide.series.length)) {
      const {labels,counts}=validateBins(slide.bins,slideName);
      slide.series=[{id:'histogram-frequency',name:'频数',labels,values:counts}];
      slide.chartType=slide.chartType||'column';
      transformations.push({slide:slideName,pointer:'/series',kind:'derive-histogram-series',from:null,to:counts,reason:'explicit numeric bins and counts'});
    }
    if(slide.type==='histogram'&&!Array.isArray(slide.bins)) {
      throw new Error(`${slideName}: histogram requires explicit bins with numeric widths and counts; a category axis renamed histogram is not accepted`);
    }
    const chartsForSlide=seriesList(slide);
    for(const chart of chartsForSlide) {
      const before=JSON.stringify(chart.series);
      typedSeries(slide,chart,catalogue,slideName,transformations,usedMetrics);
      if(JSON.stringify(chart.series)!==before) typed++;
      applyFormatAndUnit(slide,chart,catalogue,slideName,transformations);
      charts.push({slide:slideName,container:chart.path,path:chart.path,...chartContracts(slide,chart,slideName,transformations)});
    }
    for(const record of bindings.filter(record=>record.slide===slideName&&record.mode==='numeric')) {
      const scaling=transformations.find(item=>item.slide===slideName&&item.kind==='display-scale'&&record.pointer.startsWith(item.pointer+'/'));
      if(scaling) {record.render_factor=scaling.factor;record.render_value=record.effective_value/scaling.factor;}
    }
    if(slide.bins&&!chartsForSlide.length) throw new Error(`${slideName}: bins require a chart series`);
    delete slide.histogram;
    if(slide.bins) slide.histogram=true;
  }
  const unknownPlaceholders=(effective.slides||[]).flatMap((slide,index)=>{
    const found=[];
    const walk=(node,path)=>{
      if(typeof node==='string'&&node.includes('{{')) found.push(`${index}:${path}=${node}`);
      else if(Array.isArray(node)) node.forEach((item,position)=>walk(item,`${path}/${position}`));
      else if(node&&typeof node==='object') for(const [key,value] of Object.entries(node)) walk(value,`${path}/${key}`);
    };
    walk(slide,'');
    return found;
  });
  if(unknownPlaceholders.length) throw new Error(`unresolved metric placeholder syntax: ${unknownPlaceholders[0]}`);
  const report={
    schema_version:'1.3',
    status:'PREPARED',
    catalogue:{count:catalogue.size,ids:[...catalogue.keys()].sort(),sha256:sha256(JSON.stringify(effective.metrics||[]))},
    typed_series:typed,
    used_metrics:[...usedMetrics].sort(),
    bindings,
    transformations,
    charts,
    numeric_contract:'raw_value+storage_scale -> effective value; formatter is the only display path; null is never coerced to zero',
  };
  return {spec:effective,catalogue,report};
}

module.exports={prepareDeckSemantics,validateBins,seriesList,scaleRaw};
