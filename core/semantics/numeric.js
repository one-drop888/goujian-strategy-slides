'use strict';
// One deterministic numeric contract for metrics, formatting, bindings and native reconciliation.
// This module never guesses a unit or scale from a display suffix.
const {close,TOLERANCE}=require('../reasoning/calculations');

const TYPES=new Set(['absolute','count','currency','ratio','percent','pp','yoy','mom','growth','achievement','mean','median','rank','index','duration','difference']);
const PERCENT_TYPES=new Set(['percent','pp','yoy','mom','growth','achievement']);
const STORAGE_SCALES=new Set(['fraction','percent','unit','thousand','million','billion']);
const SCALE_FACTORS={thousand:1e3,million:1e6,billion:1e9};
const MISSING_POLICIES=new Set(['gap','null','reject']);
const AGGREGATIONS=new Set(['sum','mean','median','min','max','count','last','none']);
const NOTATIONS=new Set(['auto','plain','scientific']);
const BASIS_PART_OF_WHOLE=new Set(['part_of_whole','part-of-whole','share','proportion','composition']);
const CURRENCY_SYMBOLS={CNY:'¥',USD:'$',EUR:'€',GBP:'£',JPY:'¥',KRW:'₩',HKD:'HK$',SGD:'S$',INR:'₹',AUD:'A$',CAD:'C$',CHF:'CHF '};
const DURATION_UNITS=new Set(['ms','s','sec','second','seconds','min','minute','minutes','h','hr','hour','hours','d','day','days','week','weeks','month','months','year','years','毫秒','秒','分钟','小时','天','日','周','月','年']);
const ALLOWED_FIELDS=new Set(['id','name','raw_value','type','storage_scale','display_unit','precision','currency','time_window','denominator','aggregation','comparison_basis','missing_policy','provenance','display_scale','display_notation','notes','description']);
const FORBIDDEN_KEYS=new Set(['__proto__','prototype','constructor','__defineGetter__','__defineSetter__']);
const MAX_ABS=1e15,MIN_TINY=1e-6,MAX_PRECISION=6;
const COMMA_SCALES=new Map([[1,0],[1e3,1],[1e6,2],[1e9,3]]);
const METRIC_ID=/^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$/;
// Validation provenance is tracked by object identity, never by a caller-supplied flag.
const VALIDATED_METRICS=new WeakSet();
function validatedMetric(input) { return Boolean(input&&typeof input==='object'&&VALIDATED_METRICS.has(input)); }

function safeKeys(value,label,depth=0,seen=new Set()) {
  if(depth>24) throw new Error(`${label}: metric definition nesting is too deep`);
  if(value==null||typeof value!=='object') return;
  if(seen.has(value)) throw new Error(`${label}: metric definition contains a cycle`);
  seen.add(value);
  if(!Array.isArray(value)) for(const key of Object.keys(value)) {
    if(FORBIDDEN_KEYS.has(key)) throw new Error(`${label}: unsafe object key ${JSON.stringify(key)}`);
  }
  if(Array.isArray(value)) value.forEach((item,index)=>safeKeys(item,`${label}[${index}]`,depth+1,seen));
  else for(const [key,item] of Object.entries(value)) safeKeys(item,`${label}.${key}`,depth+1,seen);
  seen.delete(value);
}

function normalizeUnit(unit) {
  const value=String(unit||'').trim(),lower=value.toLowerCase();
  if(['%','percent','percentage','pct'].includes(lower)) return '%';
  if(['pp','percentage_point','percentage-point','percentage point','百分点'].includes(lower)) return 'pp';
  return value;
}
function normalizeBasis(value) { return String(value||'').trim().toLowerCase().replace(/\s+/g,'_'); }
function normalizeScale(value) {
  const scale=String(value||'').trim().toLowerCase();
  const aliases={fractions:'fraction',pct:'percent',ones:'unit',units:'unit',thousands:'thousand',millions:'million',billions:'billion'};
  return aliases[scale]||scale;
}
function finite(value,label) {
  if(typeof value!=='number'||!Number.isFinite(value)) throw new Error(`${label} must be a finite number`);
  return value;
}
function zeroNormalize(value) { return value===0?0:value; }

function effectiveFromRaw(metric) {
  if(metric.raw_value===null) return null;
  const raw=zeroNormalize(metric.raw_value);
  if(metric.storage_scale==='fraction') return raw*100;
  if(metric.storage_scale==='percent') return raw;
  if(metric.storage_scale==='unit') return raw;
  return raw*SCALE_FACTORS[metric.storage_scale];
}

function canonicalUnit(metric) {
  if(metric.type==='percent'||metric.type==='yoy'||metric.type==='mom'||metric.type==='growth'||metric.type==='achievement') return '%';
  if(metric.type==='pp') return 'pp';
  if(metric.type==='currency') return metric.currency;
  if(metric.type==='ratio') return metric.display_unit&&metric.display_unit!=='ratio_x'?normalizeUnit(metric.display_unit):'x';
  return metric.display_unit?String(metric.display_unit).trim():'';
}

function defaultPrecision(type) {
  if(['percent','pp','yoy','mom','growth','achievement','ratio'].includes(type)) return 1;
  if(type==='currency') return 2;
  return 0;
}

function validateMetric(input,{label='metric'}={}) {
  if(!input||typeof input!=='object'||Array.isArray(input)) throw new Error(`${label} must be an object`);
  safeKeys(input,label);
  const unknown=Object.keys(input).filter(key=>!ALLOWED_FIELDS.has(key));
  if(unknown.length) throw new Error(`${label}: unsupported metric fields ${unknown.sort().join(', ')}`);
  const id=String(input.id||'').trim();
  if(!METRIC_ID.test(id)) throw new Error(`${label}: id must match ${METRIC_ID}`);
  if(!TYPES.has(input.type)) throw new Error(`${label} ${id}: unsupported numeric type ${JSON.stringify(input.type)}`);
  const storage_scale=normalizeScale(input.storage_scale);
  if(!STORAGE_SCALES.has(storage_scale)) throw new Error(`${label} ${id}: unknown storage_scale ${JSON.stringify(input.storage_scale)}`);
  if(!Object.prototype.hasOwnProperty.call(input,'raw_value')) throw new Error(`${label} ${id}: raw_value is required`);
  if(input.raw_value!==null) finite(input.raw_value,`${label} ${id} raw_value`);
  const missing_policy=input.missing_policy==null?null:String(input.missing_policy).trim().toLowerCase();
  if(missing_policy!==null&&!MISSING_POLICIES.has(missing_policy)) throw new Error(`${label} ${id}: unsupported missing_policy ${JSON.stringify(input.missing_policy)}`);
  if(input.raw_value===null&&!missing_policy) throw new Error(`${label} ${id}: a null raw_value requires an explicit missing_policy (gap or null)`);
  if(input.raw_value===null&&missing_policy==='reject') throw new Error(`${label} ${id}: null raw_value conflicts with missing_policy reject`);
  let precision=input.precision==null?defaultPrecision(input.type):input.precision;
  if(!Number.isInteger(precision)||precision<0||precision>MAX_PRECISION) throw new Error(`${label} ${id}: precision must be an integer between 0 and ${MAX_PRECISION}`);
  const display_notation=input.display_notation==null?'auto':String(input.display_notation).trim().toLowerCase();
  if(!NOTATIONS.has(display_notation)) throw new Error(`${label} ${id}: unsupported display_notation ${JSON.stringify(input.display_notation)}`);
  let display_scale=null;
  if(input.display_scale!=null) {
    if(typeof input.display_scale!=='object'||Array.isArray(input.display_scale)) throw new Error(`${label} ${id}: display_scale must be an object`);
    safeKeys(input.display_scale,`${label} ${id} display_scale`);
    const scaleUnit=String(input.display_scale.unit||'').trim();
    const factor=input.display_scale.factor;
    if(!scaleUnit) throw new Error(`${label} ${id}: display_scale.unit is required`);
    if(typeof factor!=='number'||!Number.isFinite(factor)||factor<=0) throw new Error(`${label} ${id}: display_scale.factor must be a positive finite number`);
    if(normalizeUnit(scaleUnit)==='%'||normalizeUnit(scaleUnit)==='pp') throw new Error(`${label} ${id}: display_scale cannot be a percentage unit`);
    const conventional={千:1e3,万:1e4,亿:1e8,万元:1e4,亿元:1e8,thousand:1e3,million:1e6,billion:1e9};
    if(conventional[scaleUnit]!=null&&factor!==conventional[scaleUnit])throw new Error(`${label} ${id}: display_scale ${scaleUnit} requires factor ${conventional[scaleUnit]}`);
    if(/[";\r\n]/.test(scaleUnit))throw new Error(`${label} ${id}: display scale unit contains unsupported format delimiters`);
    display_scale={unit:scaleUnit,factor};
  }
  const display_unit=input.display_unit==null?'':String(input.display_unit).trim();
  const currency=input.currency==null?'':String(input.currency).trim().toUpperCase();
  const time_window=input.time_window==null?'':String(input.time_window).trim();
  const comparison_basis=normalizeBasis(input.comparison_basis);
  let denominator=input.denominator;
  if(denominator!=null) {
    finite(denominator,`${label} ${id} denominator`);
    if(denominator===0) throw new Error(`${label} ${id}: denominator cannot be zero`);
  }
  let aggregation=input.aggregation==null?'':String(input.aggregation).trim().toLowerCase();
  if(aggregation&&!AGGREGATIONS.has(aggregation)) throw new Error(`${label} ${id}: unsupported aggregation ${JSON.stringify(input.aggregation)}`);

  if(currency) {
    if(!/^[A-Z]{3}$/.test(currency)) throw new Error(`${label} ${id}: currency must be a three-letter ISO code`);
    if(input.type!=='currency') throw new Error(`${label} ${id}: currency is only valid for type currency`);
  }
  if(input.type==='currency'&&!currency) throw new Error(`${label} ${id}: currency type requires an explicit currency code`);
  if(display_unit) {
    const unit=normalizeUnit(display_unit);
    if(input.type==='percent'&&unit!=='%') throw new Error(`${label} ${id}: percent display_unit must be %`);
    if(input.type==='pp'&&unit!=='pp') throw new Error(`${label} ${id}: pp display_unit must be pp`);
    if(input.type==='currency'&&unit!==currency&&unit!==CURRENCY_SYMBOLS[currency]?.trim()) {
      throw new Error(`${label} ${id}: currency display_unit ${display_unit} conflicts with currency ${currency}`);
    }
    if(input.type==='ratio'&&!['%','x','倍','ratio','ratio_x'].includes(unit.toLowerCase())) {
      throw new Error(`${label} ${id}: ratio display_unit must be %, x or 倍`);
    }
    if(input.type==='duration'&&!DURATION_UNITS.has(unit.toLowerCase())) throw new Error(`${label} ${id}: unsupported duration unit ${display_unit}`);
  }
  if(input.type==='duration'&&!display_unit) throw new Error(`${label} ${id}: duration requires an explicit display_unit`);
  const ratioPercent=input.type==='ratio'&&normalizeUnit(display_unit)==='%';
  if(ratioPercent&&!['fraction','percent'].includes(storage_scale)) {
    throw new Error(`${label} ${id}: ratio displayed as % requires explicit fraction or percent storage_scale; unit storage is ambiguous`);
  }
  if(PERCENT_TYPES.has(input.type)&&!['fraction','percent'].includes(storage_scale)) {
    throw new Error(`${label} ${id}: ${input.type} requires explicit fraction or percent storage_scale`);
  }
  if(!PERCENT_TYPES.has(input.type)&&!ratioPercent&&['fraction','percent'].includes(storage_scale)) {
    throw new Error(`${label} ${id}: ${input.type} cannot use ${storage_scale} storage_scale`);
  }
  if((PERCENT_TYPES.has(input.type)||ratioPercent)&&display_scale) {
    throw new Error(`${label} ${id}: percentage semantics cannot use display_scale; express the scale in storage_scale or omit it`);
  }
  if(['percent','pp','yoy','mom','growth','achievement','difference'].includes(input.type)&&!comparison_basis) {
    throw new Error(`${label} ${id}: ${input.type} requires comparison_basis`);
  }
  if(['yoy','mom','growth','achievement','index'].includes(input.type)&&!time_window) {
    throw new Error(`${label} ${id}: ${input.type} requires an explicit time_window`);
  }
  if(input.type==='achievement'&&denominator==null) throw new Error(`${label} ${id}: achievement requires an explicit denominator (target)`);
  if(input.type==='ratio'&&denominator==null) throw new Error(`${label} ${id}: ratio requires an explicit denominator`);
  if(input.type==='mean'&&aggregation&&aggregation!=='mean') throw new Error(`${label} ${id}: mean type conflicts with aggregation ${aggregation}`);
  if(input.type==='median'&&aggregation&&aggregation!=='median') throw new Error(`${label} ${id}: median type conflicts with aggregation ${aggregation}`);
  if(input.type==='mean') aggregation=aggregation||'mean';
  if(input.type==='median') aggregation=aggregation||'median';
  if(input.type==='rank'&&input.raw_value!==null&&(!Number.isInteger(input.raw_value)||input.raw_value<1)) {
    throw new Error(`${label} ${id}: rank must be a positive integer or null`);
  }
  if(display_scale&&display_unit&&normalizeUnit(display_unit)===normalizeUnit(display_scale.unit)) {
    throw new Error(`${label} ${id}: display_unit and display_scale.unit must not duplicate each other`);
  }

  const metric={id,name:input.name==null?id:String(input.name),type:input.type,raw_value:input.raw_value===null?null:zeroNormalize(input.raw_value),
    storage_scale,display_unit,precision,currency,time_window,comparison_basis,denominator:denominator==null?null:denominator,
    aggregation:aggregation||null,missing_policy,provenance:input.provenance??null,display_scale,display_notation,
    notes:input.notes??null,description:input.description??null};
  if(display_scale&&(PERCENT_TYPES.has(input.type)||input.type==='ratio'))throw new Error(`${label} ${id}: percent, pp and ratios cannot use a second display scale`);
  const effective=effectiveFromRaw(metric);
  if(effective!==null&&!Number.isFinite(effective))throw new Error(`${label} ${id}: storage scaling overflows a finite number`);
  if(['count','rank'].includes(input.type)&&effective!==null&&!Number.isSafeInteger(effective))throw new Error(`${label} ${id}: count/rank requires a safe integer`);
  if(effective!==null) {
    if(input.type==='percent'&&BASIS_PART_OF_WHOLE.has(comparison_basis)&&(effective<0||effective>100)) {
      throw new Error(`${label} ${id}: part-of-whole percent must stay within 0..100, received ${effective}`);
    }
    if(input.type==='ratio'&&canonicalUnit(metric)==='%'&&(effective<0||effective>100)) {
      throw new Error(`${label} ${id}: part-of-whole ratio percent must stay within 0..100, received ${effective}`);
    }
    if(display_notation==='auto'&&!display_scale&&(Math.abs(effective)>=MAX_ABS||(effective!==0&&Math.abs(effective)<MIN_TINY))) {
      throw new Error(`${label} ${id}: ${effective} requires an explicit display_scale or scientific display_notation`);
    }
  }
  metric.effective_value=effective;
  metric.canonical_unit=canonicalUnit(metric);
  if(metric.display_scale)Object.freeze(metric.display_scale);
  Object.freeze(metric);
  VALIDATED_METRICS.add(metric);
  return metric;
}

function validateMetricCatalogue(metrics,{label='deck.metrics'}={}) {
  if(metrics==null) return new Map();
  if(!Array.isArray(metrics)) throw new Error(`${label} must be an array`);
  const catalogue=new Map();
  for(const [index,item] of metrics.entries()) {
    const metric=validateMetric(item,{label:`${label}[${index}]`});
    if(catalogue.has(metric.id)) throw new Error(`${label}: duplicate metric id ${metric.id}`);
    catalogue.set(metric.id,metric);
  }
  return catalogue;
}

function groupFixed(value,precision) {
  return new Intl.NumberFormat('en-US',{useGrouping:true,minimumFractionDigits:precision,maximumFractionDigits:precision}).format(value===0?0:value);
}
function signedText(value,text) {return value>0?`+${text}`:text;}
function scientificFixed(value,precision) {
  return new Intl.NumberFormat('en-US',{notation:'scientific',minimumFractionDigits:precision,maximumFractionDigits:precision}).format(value===0?0:value).replace(/E([+-]?)(\d+)/,(_,sign,power)=>`e${sign||'+'}${power}`);
}
function commaScale(metric) {
  if(!metric.display_scale) return {commas:0,unit:''};
  const factor=metric.display_scale.factor;
  if(!COMMA_SCALES.has(factor)) {
    throw new Error(`metric ${metric.id}: chart number formats can only scale by 1e3, 1e6 or 1e9; factor ${factor} (${metric.display_scale.unit}) is not natively representable`);
  }
  return {commas:COMMA_SCALES.get(factor),unit:metric.display_scale.unit};
}

function formatMetric(input,options={}) {
  const metric=validatedMetric(input)?input:validateMetric(input);
  const precision=options.precision==null?metric.precision:options.precision;
  if(!Number.isInteger(precision)||precision<0||precision>MAX_PRECISION) throw new Error(`metric ${metric.id}: format precision must be 0..${MAX_PRECISION}`);
  if(metric.effective_value===null) {
    return {id:metric.id,missing:true,text:options.missing_text??'—',raw_value:metric.raw_value,value:null,
      display_value:null,unit:metric.canonical_unit,precision,notation:metric.display_notation,storage_scale:metric.storage_scale};
  }
  const factor=metric.display_scale?metric.display_scale.factor:1;
  let display_value=metric.effective_value/factor;
  if(!Number.isFinite(display_value)||(display_value===0&&metric.effective_value!==0)) throw new Error(`metric ${metric.id}: display scaling would overflow or erase a nonzero value`);
  if(Object.is(display_value,-0)) display_value=0;
  const notation=options.notation||metric.display_notation;
  if(notation==='auto'&&(Math.abs(display_value)>=MAX_ABS||(display_value!==0&&Math.abs(display_value)<MIN_TINY))) {
    throw new Error(`metric ${metric.id}: display value ${display_value} requires explicit scientific display_notation`);
  }
  if(notation!=='scientific'&&display_value!==0&&Math.abs(display_value)<.5*10**(-precision)) {
    throw new Error(`metric ${metric.id}: display rounding at precision ${precision} would show a nonzero value as zero; raise precision or use scientific display_notation`);
  }
  let number=notation==='scientific'?scientificFixed(display_value,precision):groupFixed(display_value,precision);
  if(options.signed) number=signedText(display_value,number);
  const unit=metric.canonical_unit;
  const scaleUnit=metric.display_scale?metric.display_scale.unit:'';
  let text;
  if(metric.type==='currency') text=number.startsWith('-')?`-${CURRENCY_SYMBOLS[metric.currency]||metric.currency+' '}${number.slice(1)}${scaleUnit}`:`${CURRENCY_SYMBOLS[metric.currency]||metric.currency+' '}${number}${scaleUnit}`;
  else if(unit==='%'||unit==='pp') text=`${number}${unit}`;
  else text=`${number}${scaleUnit||unit}`;
  return {id:metric.id,missing:false,text,raw_value:metric.raw_value,value:metric.effective_value,
    display_value,unit,precision,notation,storage_scale:metric.storage_scale,scale_unit:scaleUnit||null};
}

function formatDelta(from,to,options={}) {
  if(from==null||to==null) return {missing:true,text:options.missing_text??'—',mode:options.mode||'pp',from,to};
  finite(from,'delta from'),finite(to,'delta to');
  const mode=options.mode||'pp',precision=options.precision==null?1:options.precision;
  if(!['pp','relative'].includes(mode)) throw new Error(`unsupported delta mode ${mode}`);
  if(!Number.isInteger(precision)||precision<0||precision>MAX_PRECISION) throw new Error(`delta precision must be 0..${MAX_PRECISION}`);
  const fromScale=normalizeScale(options.from_storage||options.fromStorage||'percent');
  const toScale=normalizeScale(options.to_storage||options.toStorage||fromScale);
  if(!['fraction','percent'].includes(fromScale)||!['fraction','percent'].includes(toScale)) throw new Error('delta inputs require fraction or percent storage');
  const fromPercent=(fromScale==='fraction'?from*100:from),toPercent=(toScale==='fraction'?to*100:to);
  let value,unit;
  if(mode==='pp') { value=toPercent-fromPercent;unit='pp'; }
  else {
    if(!(fromPercent>0)) throw new Error('relative delta requires a positive baseline');
    value=(toPercent-fromPercent)/fromPercent*100;unit='%';
  }
  if(Object.is(value,-0)||Math.abs(value)<.5*10**(-precision)) value=0;
  const text=`${value>0?'+':''}${groupFixed(value,precision)}${unit}`;
  return {missing:false,text,mode,value,unit,from,to,from_storage:fromScale,to_storage:toScale,precision};
}

function chartNormalizationFactor(metric) {
  return metric.display_scale&&!COMMA_SCALES.has(metric.display_scale.factor)?metric.display_scale.factor:1;
}
function formatCodeForMetric(input,{axis=false,normalized=false}={}) {
  const metric=validatedMetric(input)?input:validateMetric(input);
  const p=metric.precision,decimals=(p?'0.'+'0'.repeat(p):'0')+(metric.display_notation==='scientific'?'E+00':'');
  const scale=normalized&&chartNormalizationFactor(metric)!==1?{commas:0,unit:metric.display_scale.unit}:commaScale(metric);
  const suffix=scale.unit?`"${scale.unit}"`:'';
  const number=metric.display_notation==='scientific'?decimals:`#,##${decimals}`;
  const commas=','.repeat(scale.commas);
  if(metric.type==='percent'||metric.type==='yoy'||metric.type==='mom'||metric.type==='growth'||metric.type==='achievement') return `${decimals}"%"`;
  if(metric.type==='pp') return `${decimals}"pp"`;
  if(metric.type==='currency') return `"${CURRENCY_SYMBOLS[metric.currency]||metric.currency+' '}"${number}${commas}${suffix}`;
  if(metric.type==='ratio'&&metric.canonical_unit==='%') return `${decimals}"%"`;
  if(metric.type==='ratio') return `${number}${commas}"${metric.canonical_unit}"`;
  return `${number}${commas}${suffix}`;
}

function unitLabel(metric,{axis=false}={}) {
  if(metric.type==='currency') return metric.display_scale?`${metric.currency} (${metric.display_scale.unit})`:metric.currency;
  if(metric.canonical_unit==='%'||metric.canonical_unit==='pp') return metric.canonical_unit;
  if(metric.display_scale) return metric.canonical_unit?`${metric.canonical_unit} (${metric.display_scale.unit})`:metric.display_scale.unit;
  return metric.canonical_unit;
}

function resolveMetricRef(catalogue,id,{label='metric reference'}={}) {
  const key=String(id||'').trim();
  if(!METRIC_ID.test(key)) throw new Error(`${label}: invalid metric id ${JSON.stringify(id)}`);
  if(!catalogue.has(key)) throw new Error(`${label}: unknown metric ${key}`);
  return catalogue.get(key);
}

const PLACEHOLDER=/\{\{metric:([A-Za-z0-9][A-Za-z0-9._-]{0,80})\}\}/g;
const ANY_PLACEHOLDER=/\{\{[\s\S]*?\}\}/g;
const ALLOWED_TEXT_PATHS=[
  /^\/(title|subtitle|statement|body|insight|note|takeaway|unit|period|attribution|footer|kicker)$/,
  /^\/source(\/\d+)?$/,
  /^\/(labels|headers)\/\d+$/,
  /^\/rows\/\d+\/\d+$/,
  /^\/items\/\d+\/(title|label|note|text|value|target|actual|variance|delta|status|owner|time|period|description|implication)$/,
  /^\/columns\/\d+\/(heading|value)$/,
  /^\/columns\/\d+\/points\/\d+(\/(text|title))?$/,
  /^\/series\/\d+\/name$/,
  /^\/panels\/\d+\/(text)$/,
  /^\/panels\/\d+\/(headers|rows)\/\d+(\/\d+)?$/,
  /^\/decision_points\/\d+\/(title|note)$/,
  /^\/annotations\/\d+\/text$/,
];
function allowedTextPath(pointer) { return ALLOWED_TEXT_PATHS.some(pattern=>pattern.test(pointer)); }
function decodePointer(pointer) {
  if(typeof pointer!=='string'||!pointer.startsWith('/')) throw new Error(`JSON pointer must start with /: ${pointer}`);
  return pointer.slice(1).split('/').map(token=>{
    const key=token.replace(/~1/g,'/').replace(/~0/g,'~');
    if(FORBIDDEN_KEYS.has(key)) throw new Error(`unsafe JSON pointer token ${JSON.stringify(key)}`);
    return key;
  });
}
function getPointer(document,pointer) {
  let current=document;
  for(const key of decodePointer(pointer)) {
    if(current==null||typeof current!=='object') throw new Error(`JSON pointer not found: ${pointer}`);
    if(Array.isArray(current)) {
      if(!/^\d+$/.test(key)||Number(key)>=current.length) throw new Error(`JSON pointer out of range: ${pointer}`);
      current=current[Number(key)];
    } else {
      if(!Object.prototype.hasOwnProperty.call(current,key)) throw new Error(`JSON pointer not found: ${pointer}`);
      current=current[key];
    }
  }
  return current;
}
function setPointer(document,pointer,value) {
  const keys=decodePointer(pointer);
  if(!keys.length) throw new Error('metric binding cannot replace the slide root');
  let current=document;
  for(const key of keys.slice(0,-1)) {
    if(current==null||typeof current!=='object') throw new Error(`JSON pointer not found: ${pointer}`);
    if(Array.isArray(current)) {
      if(!/^\d+$/.test(key)||Number(key)>=current.length) throw new Error(`JSON pointer out of range: ${pointer}`);
      current=current[Number(key)];
    } else {
      if(!Object.prototype.hasOwnProperty.call(current,key)) throw new Error(`JSON pointer not found: ${pointer}`);
      current=current[key];
    }
  }
  const last=keys.at(-1);
  if(Array.isArray(current)) {
    if(!/^\d+$/.test(last)||Number(last)>=current.length) throw new Error(`JSON pointer out of range: ${pointer}`);
    current[Number(last)]=value;
  } else {
    if(!Object.prototype.hasOwnProperty.call(current,last)) throw new Error(`JSON pointer not found: ${pointer}`);
    current[last]=value;
  }
}

function substituteText(text,catalogue,{pointer='',precision_overrides={}}={}) {
  if(typeof text!=='string'||!text.includes('{{')) return text;
  const replaced=text.replace(PLACEHOLDER,(all,id)=>{
    const metric=resolveMetricRef(catalogue,id,{label:`placeholder at ${pointer||'text'}`});
    const precision=precision_overrides[id];
    return formatMetric(metric,precision==null?{}:{precision}).text;
  });
  const leftovers=[...replaced.matchAll(ANY_PLACEHOLDER)].map(match=>match[0]);
  if(leftovers.length) throw new Error(`unsupported placeholder syntax ${leftovers[0]} at ${pointer||'text'}; use {{metric:id}}`);
  return replaced;
}

const NUMERIC_BINDING_PATHS=[
  /^\/series\/\d+\/values\/\d+$/,
  /^\/dashboard\/series\/\d+\/values\/\d+$/,
  /^\/panels\/\d+\/series\/\d+\/values\/\d+$/,
  /^\/panels\/\d+\/rows\/\d+\/\d+$/,
  /^\/rows\/\d+\/\d+$/,
  /^\/items\/\d+\/(value|target|actual|variance|delta)$/,
];
function allowedBindingPath(pointer) {
  if(!NUMERIC_BINDING_PATHS.some(pattern=>pattern.test(pointer))) return false;
  try { decodePointer(pointer); } catch { return false; }
  return true;
}

function substituteSlideMetrics(slide,catalogue,{slideId='slide'}={}) {
  const precision_overrides={};
  for(const [id,value] of Object.entries(slide.metric_precision||{})) {
    if(!Number.isInteger(value)||value<0||value>MAX_PRECISION) throw new Error(`${slideId}: metric_precision.${id} must be 0..${MAX_PRECISION}`);
    precision_overrides[id]=value;
  }
  const replacements=[];
  function walk(node,path) {
    if(typeof node==='string') {
      if(!node.includes('{{')) return node;
      if(!allowedTextPath(path)) throw new Error(`${slideId}: metric placeholder is not allowed at ${path}`);
      const text=substituteText(node,catalogue,{pointer:path,precision_overrides});
      if(text!==node) replacements.push({pointer:path,from:node,to:text});
      return text;
    }
    if(Array.isArray(node)) { for(let i=0;i<node.length;i++) node[i]=walk(node[i],`${path}/${i}`); return node; }
    if(node&&typeof node==='object') {
      for(const key of Object.keys(node)) {
        if(FORBIDDEN_KEYS.has(key)) throw new Error(`${slideId}: unsafe object key ${key}`);
        if(['metrics','metric_bindings','metric_precision','type','chartType','visual_encoding'].includes(key)) continue;
        node[key]=walk(node[key],`${path}/${key}`);
      }
      return node;
    }
    return node;
  }
  walk(slide,'');
  return {replacements};
}

function reconcileMetricBindings(slide,catalogue,{slideId='slide',apply=false}={}) {
  const records=[],errors=[];
  const seen=new Set();
  for(const [index,binding] of (slide.metric_bindings||[]).entries()) {
    const label=`${slideId}.metric_bindings[${index}]`;
    try {
      if(!binding||typeof binding!=='object') throw new Error(`${label} must be an object`);
      const metric=resolveMetricRef(catalogue,binding.metric_id,{label});
      const pointer=String(binding.pointer||'');
      if(!allowedBindingPath(pointer)) throw new Error(`${label}: pointer ${JSON.stringify(pointer)} is not an allowed slide numeric field`);
      if(seen.has(pointer)) throw new Error(`${label}: duplicate binding for ${pointer}`);
      seen.add(pointer);
      if(binding.precision!=null&&(!Number.isInteger(binding.precision)||binding.precision<0||binding.precision>MAX_PRECISION)) throw new Error(`${label}: precision must be 0..${MAX_PRECISION}`);
      const precision=binding.precision==null?metric.precision:binding.precision;
      const formatted=formatMetric(metric,{precision});
      const actual=getPointer(slide,pointer);
      let mode;
      if(typeof actual==='number') {
        if(metric.effective_value===null) throw new Error(`${label}: missing metric ${metric.id} cannot bind a numeric value`);
        if(!close(actual,metric.effective_value)) throw new Error(`${label}: slide value ${actual} does not match metric ${metric.id} effective value ${metric.effective_value}`);
        if(apply&&binding.replace!==false&&actual!==metric.effective_value) setPointer(slide,pointer,metric.effective_value);
        mode='numeric';
      } else if(typeof actual==='string') {
        const text=substituteText(actual,catalogue);
        const expected=formatted.text;
        if(text!==expected&&actual!==expected) throw new Error(`${label}: slide text ${JSON.stringify(actual)} does not match formatted metric ${JSON.stringify(expected)}`);
        mode='text';
      } else if(actual===null) {
        if(metric.effective_value!==null) throw new Error(`${label}: null slide value conflicts with metric ${metric.id} value ${metric.effective_value}`);
        mode='missing';
      } else throw new Error(`${label}: pointer must resolve to a number, string or null`);
      records.push({metric_id:metric.id,pointer,type:metric.type,storage_scale:metric.storage_scale,precision,
        raw_value:metric.raw_value,effective_value:metric.effective_value,formatted:formatted.text,mode,ok:true});
    } catch(error) {
      errors.push(error.message);
      records.push({metric_id:binding?.metric_id??null,pointer:binding?.pointer??null,ok:false,error:error.message});
    }
  }
  return {records,errors};
}

module.exports={TYPES,STORAGE_SCALES,MISSING_POLICIES,MAX_PRECISION,METRIC_ID,
  validateMetric,validateMetricCatalogue,effectiveFromRaw,canonicalUnit,formatMetric,formatDelta,
  formatCodeForMetric,chartNormalizationFactor,unitLabel,resolveMetricRef,substituteText,substituteSlideMetrics,
  reconcileMetricBindings,allowedBindingPath,allowedTextPath,getPointer,setPointer,decodePointer,
  normalizeUnit,normalizeBasis,normalizeScale,defaultPrecision};
