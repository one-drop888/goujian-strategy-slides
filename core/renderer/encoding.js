'use strict';
// Deterministic visual encoding: stable series identity, role styles, perceptual checks and
// bounded sequential/diverging scales. Thresholds are engineering heuristics, not color-vision certification.
const crypto=require('crypto');

const ROLE_STYLES={
  actual:{dash:'solid',symbol:'circle'},
  target:{dash:'dash',symbol:'square'},
  history:{dash:'dashDot',symbol:'triangle'},
  forecast:{dash:'sysDot',symbol:'diamond'},
  comparison:{dash:'solid',symbol:'circle'},
  benchmark:{dash:'dash',symbol:'diamond'},
};
const ROLES=new Set(Object.keys(ROLE_STYLES));
const ROLE_LOOKUP=new Map([...ROLES].map(role=>[role.toLowerCase(),role]));
const PALETTE_TYPES=new Set(['categorical','sequential','diverging','semantic']);
const RELATIONS=new Set(['comparison','trend','composition','distribution','relationship']);
const DASH_VALUES=['solid','dash','dashDot','lgDash','lgDashDot','lgDashDotDot','sysDash','sysDot'];
const DASH_LOOKUP=new Map(DASH_VALUES.map(value=>[value.toLowerCase(),value]));
const DASHES=new Set(DASH_VALUES);
const SYMBOLS=new Set(['circle','dash','diamond','dot','none','square','triangle']);
const LABEL_STRATEGIES=new Set(['auto','none','value','category','category_value','percent']);
const ENCODING_FIELDS=new Set(['relation','palette_type','domain','center','series','semantic','label_strategy']);
const ENCODING_SERIES_FIELDS=new Set(['id','role','emphasis']);
const MIN_DELTA_E=12,MIN_GRAY=8,MIN_CONTRAST=3;
function canonicalDash(value) {
  const text=String(value||'').trim();
  const dash=DASH_LOOKUP.get(text.toLowerCase());
  if(!dash) throw new Error(`unsupported line dash ${text}; use ${DASH_VALUES.join(', ')}`);
  return dash;
}
function canonicalSymbol(value) {
  const symbol=String(value||'').trim().toLowerCase();
  if(!SYMBOLS.has(symbol)) throw new Error(`unsupported marker symbol ${symbol}`);
  return symbol;
}
function chartKind(slide) {
  if(slide.chartType) return slide.chartType;
  if(['line','trend','cohort'].includes(slide.type)) return 'line';
  if(slide.type==='area') return 'area';
  if(['bar','benchmark','distribution'].includes(slide.type)) return 'bar';
  if(['column','variance','cost-structure','histogram','waterfall','bridge'].includes(slide.type)) return 'column';
  if(slide.type==='chart') return 'bar';
  return null;
}

const LABEL_POSITION_SETS={1:['t'],2:['t','b'],3:['t','r','b'],4:['t','r','l','b']};
function colorRgb(color) {
  const text=String(color||'').replace(/^#/,'');
  return /^[0-9A-Fa-f]{6}$/.test(text)?[parseInt(text.slice(0,2),16),parseInt(text.slice(2,4),16),parseInt(text.slice(4,6),16)]:null;
}
function isWarmColor(color) {
  const rgb=colorRgb(color);
  return Boolean(rgb&&rgb[0]>rgb[2]+40&&rgb[0]>=rgb[1]-10);
}
function isNeutralColor(color) {
  const rgb=colorRgb(color);
  return Boolean(rgb&&Math.max(...rgb)-Math.min(...rgb)<30);
}
function lastValueIndex(values) {
  for(let index=(values||[]).length-1;index>=0;index--) if(values[index]!=null) return index;
  return -1;
}
function labelLayoutFor(kind,strategy,series,labels) {
  if(!['value','category_value'].includes(strategy)) return null;
  if(!['line','area'].includes(String(kind).toLowerCase())) return null;
  if(!Array.isArray(series)||series.length<2) return null;
  const entries=series.map((item,index)=>{
    const values=item.values||[],at=lastValueIndex(values);
    return {id:item.id||item.name||`series-${index+1}`,index:at,value:at<0?null:values[at]};
  });
  const drawable=entries.filter(item=>item.index>=0);
  if(!drawable.length) return null;
  const positions=LABEL_POSITION_SETS[Math.min(drawable.length,4)];
  const ranked=[...drawable].sort((a,b)=>Number(b.value)-Number(a.value));
  const byId=new Map(ranked.map((item,rank)=>[item.id,{...item,position:positions[Math.min(rank,positions.length-1)]}]));
  const categoryCount=Math.max(...series.map(item=>(item.values||[]).length),(labels||[]).length);
  const mode=strategy==='value'&&categoryCount>3?'end':'all';
  return {mode,series:entries.map(item=>{
    const placed=byId.get(item.id);
    return {id:item.id,index:item.index,position:placed?placed.position:positions[0]};
  })};
}

function hashIndex(id,size) {
  const digest=crypto.createHash('sha256').update(String(id)).digest();
  return digest.readUInt32BE(0)%size;
}
function stableIdOrder(ids) {
  return [...ids].sort((a,b)=>{
    const ha=crypto.createHash('sha256').update(String(a)).digest('hex');
    const hb=crypto.createHash('sha256').update(String(b)).digest('hex');
    return ha<hb?-1:ha>hb?1:String(a).localeCompare(String(b));
  });
}
function seriesIds(series,chartIndex=0) {
  const ids=[];
  for(const [index,item] of (series||[]).entries()) {
    const id=String(item?.id||item?.name||'').trim();
    ids.push({id:id||`series-anon-${chartIndex+1}-${index+1}`,inferred:!id,name:item?.name||null});
  }
  return ids;
}

function chartSlides(spec) {
  const found=[];
  for(const [slideIndex,slide] of (spec.slides||[]).entries()) {
    const kind=chartKind(slide);
    if(kind&&Array.isArray(slide.series)&&slide.series.length) found.push({slideIndex,slide,kind,series:slide.series,container:'slide'});
    if(slide.dashboard?.series) found.push({slideIndex,slide,kind:'line',series:slide.dashboard.series,container:'dashboard'});
    for(const [panelIndex,panel] of (slide.panels||[]).entries()) {
      if(panel.kind==='chart') found.push({slideIndex,slide,kind:panel.chartType||'bar',series:panel.series||[],container:'panel',panelIndex});
    }
  }
  return found.map((chart,index)=>({...chart,ids:seriesIds(chart.series,index)}));
}

function createEncoding(spec,style) {
  const palette=(style?.tokens?.chart?.categorical||style?.tokens?.chart?.palette||['0072B2','E69F00','009E73','CC79A7','D55E00','56B4E9']).map(String);
  if(!palette.length) throw new Error('chart palette must contain at least one color');
  if(new Set(palette.map(color=>color.toUpperCase())).size!==palette.length) throw new Error('chart palette colors must be unique');
  const background=style?.tokens?.chart?.background||style?.background||'FFFFFF';
  const highlight=style?.tokens?.chart?.highlight||palette[0];
  const neutral=style?.tokens?.chart?.neutral||style?.tokens?.chart?.['palette']?.[0]||palette[0];
  const explicitRegistry=spec.series_registry&&typeof spec.series_registry==='object'?spec.series_registry:{};
  const charts=chartSlides(spec);
  const seriesSet=new Set(),adjacency=new Map();
  for(const chart of charts) {
    const chartIds=chart.ids.map(item=>item.id);
    const local=new Set();
    for(const id of chartIds) {
      if(local.has(id)) throw new Error(`chart ${chart.container} has duplicate series identity ${id}; assign unique series ids`);
      local.add(id);
      if(!seriesSet.has(id)) seriesSet.add(id);
      if(!adjacency.has(id)) adjacency.set(id,new Set());
    }
    for(let i=0;i<chartIds.length;i++) for(let j=i+1;j<chartIds.length;j++) {
      adjacency.get(chartIds[i]).add(chartIds[j]);
      adjacency.get(chartIds[j]).add(chartIds[i]);
    }
  }
  const orderedSeries=stableIdOrder([...seriesSet]);
  const inferred=new Set(charts.flatMap(chart=>chart.ids).filter(item=>item.inferred).map(item=>item.id));
  const slideSeriesIds=new Map();
  for(const chart of charts) {
    if(!slideSeriesIds.has(chart.slideIndex)) slideSeriesIds.set(chart.slideIndex,new Set());
    for(const item of chart.ids) slideSeriesIds.get(chart.slideIndex).add(item.id);
  }
  const validatedSlides=new Set();
  for(const chart of charts) {
    if(validatedSlides.has(chart.slideIndex)) continue;
    validatedSlides.add(chart.slideIndex);
    const configured=encodingPlan(chart.slide).series||[];
    for(const entry of configured) {
      if(!slideSeriesIds.get(chart.slideIndex).has(entry.id)) {
        throw new Error(`visual_encoding.series ${entry.id} does not match any series on slide ${chart.slideIndex+1}`);
      }
    }
  }
  const legacyChart=chart=>!spec.series_registry&&!chart.slide.visual_encoding
    &&chart.series.every(item=>!item.id&&!item.metric_id&&!Array.isArray(item.metric_ids)
      &&!item.role&&!item.emphasis&&!item.style);
  for(const chart of charts) {
    if(chart.series.length>1) for(const item of chart.series) {
      if(!item?.id&&!item?.name) throw new Error(`chart ${chart.container} requires a stable id or name for every series so colors remain consistent across slides`);
    }
    const kind=String(chart.kind).toLowerCase();
    const categoryColored=['pie','doughnut'].includes(kind)||(['bar','column'].includes(kind)&&chart.series.length===1&&!chart.slide.bins&&!chart.slide.histogram);
    if(categoryColored) {
      const labels=chart.series[0]?.labels||chart.slide.labels||chart.series[0]?.values||[];
      if(!legacyChart(chart)&&encodingPlan(chart.slide).palette_type==='categorical'&&labels.length>palette.length) {
        throw new Error(`category palette exceeds ${palette.length} distinguishable colors (${labels.length} categories); split or facet the chart instead of reusing colors`);
      }
      const item=chart.series[0]||{};
      const configured=(chart.slide.visual_encoding?.series||[]).find(entry=>entry.id===chart.ids[0]?.id);
      if(item.emphasis===true||configured?.emphasis===true||item.style?.color||item.style?.dash||item.style?.symbol) {
        throw new Error('single-series category charts do not support series emphasis or line/marker styles; use highlightIndex or a multi-series chart');
      }
    } else if(chart.series.length>palette.length) {
      throw new Error(`chart ${chart.container} uses ${chart.series.length} series but the palette has ${palette.length} colors; split the chart into facets`);
    }
  }
  for(const id of Object.keys(explicitRegistry)) {
    if(!seriesSet.has(id)) throw new Error(`series_registry.${id} does not match any series id in this deck`);
  }
  const assignments=new Map();
  for(const id of orderedSeries) {
    if(!Object.prototype.hasOwnProperty.call(explicitRegistry,id)) continue;
    const slot=explicitRegistry[id];
    if(!Number.isInteger(slot)||slot<0||slot>=palette.length) throw new Error(`series_registry.${id} must be an integer between 0 and ${palette.length-1}`);
    if([...assignments.values()].includes(slot)) throw new Error(`series_registry assigns duplicate palette slot ${slot}`);
    assignments.set(id,slot);
  }
  for(const [id,slot] of assignments) for(const neighbor of adjacency.get(id)||[]) {
    if(assignments.get(neighbor)===slot) throw new Error(`series ${id} and ${neighbor} share palette slot ${slot} in the same chart`);
  }
  // Role-aware defaults keep target warm and history neutral unless the user
  // pinned a color via the registry, series style or emphasis.
  const warmSlots=palette.map((color,index)=>isWarmColor(color)?index:null).filter(index=>index!=null);
  const neutralSlots=palette.map((color,index)=>isNeutralColor(color)?index:null).filter(index=>index!=null);
  for(const chart of charts) for(const [index,item] of chart.series.entries()) {
    const id=chart.ids[index].id;
    if(assignments.has(id)||Object.prototype.hasOwnProperty.call(explicitRegistry,id)||item?.style?.color) continue;
    const configured=(chart.slide?.visual_encoding?.series||[]).find(entry=>entry.id===id);
    if(item?.emphasis===true||configured?.emphasis===true) continue;
    const role=roleFor(item,chart.slide,id);
    const slots=role==='target'?warmSlots:role==='history'?neutralSlots:null;
    if(!slots?.length) continue;
    const forbidden=new Set([...assignments.values(),
      ...[...(adjacency.get(id)||[])].map(neighbor=>assignments.get(neighbor)).filter(slot=>slot!=null)]);
    const slot=slots.find(candidate=>!forbidden.has(candidate));
    if(slot!=null)assignments.set(id,slot);
  }
  const hashHex=id=>crypto.createHash('sha256').update(String(id)).digest('hex');
  const degree=id=>adjacency.get(id)?.size||0;
  const hashOrder=(a,b)=>hashHex(a)<hashHex(b)?-1:hashHex(a)>hashHex(b)?1:String(a).localeCompare(String(b));
  const preferred=new Map(orderedSeries.map(id=>[id,hashIndex(id,palette.length)]));
  const chartFirst=new Set();
  // Legacy specs keep their familiar first paint; explicit identities never imply emphasis by array order.
  for(const chart of charts) if(legacyChart(chart)&&chart.ids.length) {preferred.set(chart.ids[0].id,0);chartFirst.add(chart.ids[0].id);}
  const pending=orderedSeries.filter(id=>!assignments.has(id)).sort((a,b)=>
    (chartFirst.has(b)?1:0)-(chartFirst.has(a)?1:0)||degree(b)-degree(a)||hashOrder(a,b));
  let searchSteps=0;
  function assignFrom(position) {
    if(position===pending.length) return true;
    const id=pending[position],forbidden=new Set();
    for(const neighbor of adjacency.get(id)||[]) {
      const slot=assignments.get(neighbor);
      if(slot!=null) forbidden.add(slot);
    }
    const start=preferred.get(id);
    for(let offset=0;offset<palette.length;offset++) {
      const slot=(start+offset)%palette.length;
      if(forbidden.has(slot)) continue;
      assignments.set(id,slot);
      if(assignFrom(position+1)) return true;
      assignments.delete(id);
      if(++searchSteps>50000) throw new Error('palette assignment search exceeded its bounded budget; split charts into smaller series sets');
    }
    return false;
  }
  if(!assignFrom(0)) throw new Error(`no distinguishable palette assignment exists for ${seriesSet.size} series with ${palette.length} colors; split the charts into facets`);

  function colorFor(id) {
    if(!assignments.has(String(id))) throw new Error(`no stable palette assignment for series ${id}`);
    return palette[assignments.get(String(id))];
  }
  function roleFor(series,slide,idOverride) {
    const id=idOverride||series?.id||series?.name;
    const configured=(slide?.visual_encoding?.series||[]).find(item=>item.id===id);
    if(series?.role!=null&&configured?.role!=null&&String(series.role).toLowerCase()!==String(configured.role).toLowerCase()) {
      throw new Error(`series ${id} declares conflicting roles ${series.role} and ${configured.role}`);
    }
    const explicit=series?.role??configured?.role;
    if(explicit) {
      const role=ROLE_LOOKUP.get(String(explicit).toLowerCase());
      if(!role) throw new Error(`unknown series role ${explicit}; use ${[...ROLES].join(', ')}`);
      return role;
    }
    return 'actual';
  }
  function styleFor(series,slide,idOverride) {
    const id=idOverride||series?.id||series?.name;
    const role=roleFor(series,slide,idOverride),base=ROLE_STYLES[role];
    const explicit=typeof series?.style==='object'?series.style:{};
    const dash=canonicalDash(explicit.dash??base.dash),symbol=canonicalSymbol(explicit.symbol??base.symbol);
    const configured=(slide?.visual_encoding?.series||[]).find(item=>item.id===id);
    const emphasis=series?.emphasis===true||configured?.emphasis===true;
    return {role,dash,symbol,size:Number(explicit.marker_size||5),emphasis,
      color:explicit.color?String(explicit.color).toUpperCase():(emphasis?highlight:(id!=null?colorFor(id):palette[0]))};
  }
  function categoryColors(labels,highlightIndex,{legacy=false}={}) {
    const items=Array.isArray(labels)?labels:[];
    if(items.length>palette.length) {
      if(legacy) return items.map((_,index)=>highlightIndex!=null&&index===highlightIndex?highlight:neutral);
      throw new Error(`category palette exceeds ${palette.length} distinguishable colors (${items.length} categories); split or facet the chart instead of reusing colors`);
    }
    return items.map((_,index)=>highlightIndex!=null&&index===highlightIndex?highlight:palette[index]);
  }
  function encodingPlan(slide) {
    if(slide?.label_strategy!=null) throw new Error('label_strategy must be declared under visual_encoding, not at slide root');
    const plan=slide?.visual_encoding;
    if(!plan) return {palette_type:'categorical',relation:null,domain:null,center:null,semantic:null,label_strategy:null,series:[]};
    if(typeof plan!=='object'||Array.isArray(plan)) throw new Error('visual_encoding must be an object');
    const unknown=Object.keys(plan).filter(key=>!ENCODING_FIELDS.has(key));
    if(unknown.length) throw new Error(`unsupported visual_encoding fields ${unknown.sort().join(', ')}`);
    if(plan.relation!=null&&!RELATIONS.has(plan.relation)) throw new Error(`unsupported visual relation ${plan.relation}`);
    const palette_type=plan.palette_type||'categorical';
    if(!PALETTE_TYPES.has(palette_type)) throw new Error(`unsupported palette_type ${palette_type}`);
    const label_strategy=plan.label_strategy==null?null:String(plan.label_strategy).toLowerCase();
    if(label_strategy!=null&&!LABEL_STRATEGIES.has(label_strategy)) throw new Error(`unsupported label_strategy ${plan.label_strategy}; use ${[...LABEL_STRATEGIES].join(', ')}`);
    const configuredIds=new Set();
    if(Array.isArray(plan.series)) for(const item of plan.series) {
      if(!item||typeof item!=='object'||Array.isArray(item)) throw new Error('visual_encoding.series entries must be objects');
      const extra=Object.keys(item).filter(key=>!ENCODING_SERIES_FIELDS.has(key));
      if(extra.length) throw new Error(`unsupported visual_encoding.series fields ${extra.sort().join(', ')}`);
      if(typeof item.id!=='string'||!item.id.trim()) throw new Error('visual_encoding.series entries require an id');
      if(configuredIds.has(item.id)) throw new Error(`duplicate visual_encoding.series id ${item.id}`);
      configuredIds.add(item.id);
      if(item.role!=null&&!ROLE_LOOKUP.has(String(item.role).toLowerCase())) throw new Error(`unknown visual role ${item.role}`);
      if(item.emphasis!=null&&typeof item.emphasis!=='boolean') throw new Error('visual_encoding.series emphasis must be boolean');
    }
    if(['sequential','diverging'].includes(palette_type)) {
      if(plan.domain==null||typeof plan.domain!=='object') throw new Error(`${palette_type} palette requires an explicit numeric domain {min,max}`);
      if(!Number.isFinite(plan.domain.min)||!Number.isFinite(plan.domain.max)||!(plan.domain.min<plan.domain.max)) throw new Error(`${palette_type} domain requires finite min < max`);
      if(palette_type==='diverging') {
        if(!Number.isFinite(plan.center)||plan.center<=plan.domain.min||plan.center>=plan.domain.max) throw new Error('diverging palette requires an explicit center inside the domain');
      }
    }
    if(plan.semantic!=null) {
      if(typeof plan.semantic!=='object') throw new Error('semantic palette requires explicit positive/negative/neutral colors');
      for(const key of ['positive','negative','neutral']) if(!/^[0-9A-Fa-f]{6}$/.test(String(plan.semantic[key]||''))) throw new Error(`semantic palette requires a hex ${key} color`);
      if(typeof plan.semantic.higher_is_better!=='boolean') throw new Error('semantic palette requires an explicit higher_is_better decision; sign alone is not business meaning');
    }
    if(palette_type==='semantic'&&!plan.semantic)throw new Error('semantic palette requires explicit positive/negative/neutral colors and higher_is_better');
    return {palette_type,relation:plan.relation||null,domain:plan.domain||null,center:plan.center??null,semantic:plan.semantic||null,label_strategy,series:plan.series||[]};
  }
  function colorsFor(kind,series,slide,ids) {
    if(!Array.isArray(series)||!series.length) throw new Error('chart requires nonempty series');
    const plan=encodingPlan(slide);
    if(slide.bins||slide.histogram)return [styleFor(series[0],slide,ids?.[0]?.id).color];
    if(plan.palette_type!=='categorical'&&!['bar','column'].includes(String(kind).toLowerCase()))throw new Error(`${plan.palette_type} value encoding is supported on bar/column only; split or choose a faithful category chart`);
    const explicit=Boolean(spec.series_registry)||Boolean(slide?.visual_encoding)
      ||series.some(item=>item.id||item.metric_id||Array.isArray(item.metric_ids)||item.role||item.emphasis||item.style);
    if(plan.palette_type==='semantic') {
      if(series.length!==1) throw new Error('semantic encoding requires one series; facet additional series');
      const values=series[0].values||[];
      if(values.some(value=>value!=null&&!Number.isFinite(value))) throw new Error('numeric series values must be finite or null');
      const higher=plan.semantic.higher_is_better===true;
      return values.map(value=>{
        if(value==null) return style.tokens.chart.background;
        if(value===0) return plan.semantic.neutral;
        return ((value>0)===higher)?plan.semantic.positive:plan.semantic.negative;
      });
    }
    if(['sequential','diverging'].includes(plan.palette_type)) {
      if(series.length!==1) throw new Error(`${plan.palette_type} encoding requires one series; facet additional series`);
      const values=series[0].values||[];
      if(values.some(value=>value!=null&&!Number.isFinite(value))) throw new Error('numeric series values must be finite or null');
      const domain=plan.domain;
      if(values.some(value=>value!=null&&(value<domain.min||value>domain.max))) throw new Error(`${plan.palette_type} domain would clip data; expand min/max explicitly`);
      return values.map(value=>value==null?style.tokens.chart.background:scaleColor(value,plan));
    }
    const pieLike=['pie','doughnut'].includes(String(kind).toLowerCase());
    if(pieLike||(['bar','column'].includes(String(kind).toLowerCase())&&series.length===1)) {
      const labels=series[0].labels||slide?.labels||[];
      return categoryColors(labels,slide?.highlightIndex??null,{legacy:!explicit});
    }
    return series.map((item,index)=>styleFor(item,slide,ids?.[index]?.id).color);
  }
  function scaleColor(value,plan) {
    const {min,max}=plan.domain;
    const t=Math.max(0,Math.min(1,(value-min)/(max-min)));
    if(plan.palette_type==='sequential') {
      const colors=style.tokens.chart.sequential||[style.tokens.chart.background,style.tokens.accent];
      return interpolateLab(colors[0],colors[1],t);
    }
    const colors=style.tokens.chart.diverging||['0072B2','D9E1E7','D55E00'];
    const center=(plan.center-min)/(max-min);
    return t<=center?interpolateLab(colors[0],colors[1],center===0?0:t/center):interpolateLab(colors[1],colors[2],center===1?0:(t-center)/(1-center));
  }
  function chartPlansForSpec() {
    return charts.map(chart=>{
      const kind=String(chart.kind).toLowerCase();
      const plan=encodingPlan(chart.slide);
      const pieLike=['pie','doughnut'].includes(kind);
      if(plan.label_strategy==='percent'&&!pieLike) throw new Error('label_strategy percent is only supported for pie/doughnut charts');
      const categoryColored=pieLike||(['bar','column'].includes(kind)&&chart.series.length===1&&!chart.slide.bins&&!chart.slide.histogram);
      if(categoryColored) {
        const item=chart.series[0]||{};
        if(item.emphasis===true||item.style?.color||item.style?.dash||item.style?.symbol) {
          throw new Error('single-series category charts do not support series emphasis or line/marker styles; use highlightIndex or a multi-series chart');
        }
      }
      const emphasized=chart.series.filter((item,index)=>item.emphasis===true
        ||(chart.slide?.visual_encoding?.series||[]).some(entry=>entry.id===chart.ids[index].id&&entry.emphasis===true));
      if(chart.series.length>1&&emphasized.length===chart.series.length) throw new Error('emphasis must leave at least one series unemphasized');
      const colors=colorsFor(kind,chart.series,chart.slide,chart.ids);
      const labels=chart.series[0]?.labels||chart.slide.labels||[];
      const series=chart.series.map((item,index)=>({...styleFor(item,chart.slide,chart.ids[index].id),
        id:chart.ids[index].id,name:item.name||null,
        color:categoryColored?palette[0]:colors[index]}));
      const has_missing=chart.series.some(item=>(item.values||[]).some(value=>value==null));
      return {kind,container:chart.container,slideIndex:chart.slideIndex,palette_type:plan.palette_type,
        relation:plan.relation,label_strategy:plan.label_strategy,category_colors:categoryColored,
        legacy_overflow:categoryColored&&legacyChart(chart)&&labels.length>palette.length,
        labels,has_missing,missing_policy:chart.slide?.missing_policy||null,
        label_layout:labelLayoutFor(kind,plan.label_strategy,chart.series,labels),
        series,colors};
    });
  }
  return {palette,background,highlight,neutral,styleFor,colorFor,roleFor,colorsFor,categoryColors,encodingPlan,chartPlansForSpec,inferredIds:[...inferred]};
}

function hex(value) {
  const text=String(value||'').replace(/^#/,'');
  if(!/^[0-9A-Fa-f]{6}$/.test(text)) throw new Error(`Invalid hex color ${value}`);
  return text.toUpperCase();
}
function rgb(value) {
  const text=hex(value);
  return {r:parseInt(text.slice(0,2),16),g:parseInt(text.slice(2,4),16),b:parseInt(text.slice(4,6),16)};
}
function linear(channel) { const c=channel/255; return c<=.04045?c/12.92:((c+.055)/1.055)**2.4; }
function luminance(value) { const c=rgb(value); return .2126*linear(c.r)+.7152*linear(c.g)+.0722*linear(c.b); }
function lab(value) {
  const c=rgb(value);
  const x=(linear(c.r)*.4124+linear(c.g)*.3576+linear(c.b)*.1805)/.95047;
  const y=(linear(c.r)*.2126+linear(c.g)*.7152+linear(c.b)*.0722);
  const z=(linear(c.r)*.0193+linear(c.g)*.1192+linear(c.b)*.9505)/1.08883;
  const f=t=>t>.008856?Math.cbrt(t):7.787*t+16/116;
  return {L:116*f(y)-16,a:500*(f(x)-f(y)),b:200*(f(y)-f(z))};
}
function deltaE76(a,b) { const x=lab(a),y=lab(b); return Math.hypot(x.L-y.L,x.a-y.a,x.b-y.b); }
function grayscaleDelta(a,b) { return Math.abs(luminance(a)-luminance(b))*100; }
function mixLab(a,b,t) {
  const x=lab(a),y=lab(b);
  const L=x.L+(y.L-x.L)*t,A=x.a+(y.a-x.a)*t,B=x.b+(y.b-x.b)*t;
  // Lab -> XYZ (D65) -> sRGB
  const fy=(L+16)/116,fx=fy+A/500,fz=fy-B/200;
  const inv=t=>t**3>.008856?t**3:(t-16/116)/7.787;
  const X=inv(fx)*.95047,Y=inv(fy),Z=inv(fz)*1.08883;
  const r= X*3.2406+Y*-1.5372+Z*-0.4986;
  const g= X*-0.9689+Y*1.8758+Z*0.0415;
  const bl=X*0.0557+Y*-0.2040+Z*1.0570;
  const gamma=v=>v<=.0031308?12.92*v:1.055*v**(1/2.4)-.055;
  return [r,g,bl].map(v=>Math.max(0,Math.min(255,Math.round(gamma(v)*255))).toString(16).padStart(2,'0')).join('').toUpperCase();
}
function interpolateLab(a,b,t) { return mixLab(hex(a),hex(b),Math.max(0,Math.min(1,t))); }

function validateSeries(series,{kind='chart',colors=null}={}) {
  const errors=[],notes=[];
  if(!Array.isArray(series)||!series.length) return {errors:['chart requires nonempty series'],notes};
  const names=series.map(item=>String(item?.name||'').trim());
  if(series.length>1) {
    if(names.some(name=>!name)) errors.push('multi-series charts require a non-empty name for every series');
    if(new Set(names.filter(Boolean)).size!==names.filter(Boolean).length) errors.push('series names must be unique for legend mapping');
  }
  if(['pie','doughnut'].includes(String(kind).toLowerCase())&&series.length!==1) errors.push('pie/doughnut requires exactly one series');
  return {errors,notes};
}

function validateDistinguishability(series,encoding,displayColors,{kind='chart'}={}) {
  const errors=[],warnings=[],pairs=[];
  const colors=displayColors||series.map((item,index)=>encoding.styleFor(item)?.color);
  for(let i=0;i<series.length;i++) for(let j=i+1;j<series.length;j++) {
    const a=series[i],b=series[j],ca=colors[i],cb=colors[j];
    if(!ca||!cb) continue;
    const sa=encoding.styleFor(a),sb=encoding.styleFor(b);
    const de=deltaE76(ca,cb),gray=grayscaleDelta(ca,cb);
    const pair={a:a.name||a.id||`series-${i+1}`,b:b.name||b.id||`series-${j+1}`,delta_e:round(de),
      grayscale:round(gray),a_color:ca,b_color:cb,a_dash:sa.dash,b_dash:sb.dash,a_symbol:sa.symbol,b_symbol:sb.symbol};
    pairs.push(pair);
    const secondary=sa.dash!==sb.dash||sa.symbol!==sb.symbol;
    if(de<MIN_DELTA_E&&gray<MIN_GRAY&&!secondary) errors.push(`series ${pair.a} and ${pair.b} are perceptually too similar (ΔE76 ${round(de)}, grayscale ${round(gray)}) without a distinct dash or marker`);
    else if(de<MIN_DELTA_E&&!secondary) warnings.push(`series ${pair.a} and ${pair.b} rely on color alone (ΔE76 ${round(de)})`);
  }
  return {errors,warnings,pairs,palette_size:colors.length,thresholds:{delta_e76:MIN_DELTA_E,grayscale:MIN_GRAY,contrast:MIN_CONTRAST}};
}

function validateContrast(colors,background) {
  const {contrastRatio}=require('../style/resolve-style');
  const results=(colors||[]).filter(Boolean).map(color=>({color,ratio:round(contrastRatio(color,background))}));
  return {status:results.every(item=>item.ratio>=MIN_CONTRAST)?'PASS':'FAIL',minimum:MIN_CONTRAST,colors:results};
}

function validateChartPlan(plan,{background='FFFFFF'}={}) {
  const errors=[],warnings=[],pairs=[];
  const colors=plan.category_colors?plan.colors:plan.series.map(item=>item.color);
  const contrast=validateContrast(colors,background);
  if(contrast.status!=='PASS') errors.push(`series paint fails ${MIN_CONTRAST}:1 contrast against the chart background`);
  if(plan.category_colors&&['sequential','diverging','semantic'].includes(plan.palette_type)) {
    warnings.push('Value-based colors encode a declared numeric domain or semantic sign; pairwise categorical color distance is not applicable. Labels and magnitude remain necessary.');
  } else if(plan.category_colors) {
    for(let i=0;i<colors.length;i++) for(let j=i+1;j<colors.length;j++) {
      const de=deltaE76(colors[i],colors[j]),gray=grayscaleDelta(colors[i],colors[j]);
      pairs.push({a:String(i+1),b:String(j+1),delta_e:round(de),grayscale:round(gray),a_dash:'solid',b_dash:'solid',a_symbol:'none',b_symbol:'none'});
      if(de<MIN_DELTA_E&&gray<MIN_GRAY) {
        if(plan.legacy_overflow) warnings.push(`legacy category chart repeats paint for categories ${i+1} and ${j+1}; split the chart so every category has a distinct nominal color`);
        else errors.push(`categories ${i+1} and ${j+1} are not distinguishable with color or grayscale`);
      } else if(de<MIN_DELTA_E) warnings.push(`categories ${i+1} and ${j+1} rely on grayscale separation only`);
    }
  } else {
    for(let i=0;i<plan.series.length;i++) for(let j=i+1;j<plan.series.length;j++) {
      const a=plan.series[i],b=plan.series[j],de=deltaE76(colors[i],colors[j]),gray=grayscaleDelta(colors[i],colors[j]);
      const secondary=a.dash!==b.dash||a.symbol!==b.symbol;
      pairs.push({a:a.id,b:b.id,delta_e:round(de),grayscale:round(gray),a_dash:a.dash,b_dash:b.dash,a_symbol:a.symbol,b_symbol:b.symbol});
      if(de<MIN_DELTA_E&&gray<MIN_GRAY&&!secondary) errors.push(`series ${a.id} and ${b.id} reuse the same paint without a distinct dash or marker`);
      else if(de<MIN_DELTA_E&&secondary) warnings.push(`series ${a.id} and ${b.id} depend on dash/marker rather than color separation`);
    }
  }
  return {status:errors.length?'FAIL':'PASS',errors,warnings,pairs,contrast};
}

function round(value) { return Math.round(value*1000)/1000; }

module.exports={ROLE_STYLES,ROLES,MIN_DELTA_E,MIN_GRAY,MIN_CONTRAST,createEncoding,
  validateSeries,validateDistinguishability,validateContrast,validateChartPlan,deltaE76,grayscaleDelta,luminance,interpolateLab,round};
