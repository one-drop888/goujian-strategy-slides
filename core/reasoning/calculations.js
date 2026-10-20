const TOLERANCE=1e-9;

function normalizeUnit(unit) {
  const value=String(unit||'').trim();
  const lower=value.toLowerCase();
  if(['%','percent','percentage'].includes(lower)) return '%';
  if(['pp','percentage_point','percentage-point','percentage point'].includes(lower)) return 'pp';
  return value;
}

function finite(value,label) {
  if(typeof value!=='number'||!Number.isFinite(value)) throw new Error(`${label} must be a finite number`);
  return value;
}

function close(actual,expected) {
  return Math.abs(actual-expected)<=TOLERANCE*Math.max(1,Math.abs(expected));
}

function lookupSourceValue(sources,sourceId,valueId) {
  const source=sources.get(sourceId);
  if(!source) throw new Error(`Unknown source ${sourceId}`);
  const value=(source.values||[]).find(item=>item.id===valueId);
  if(!value) throw new Error(`Unknown numeric value ${sourceId}.${valueId}`);
  return {source,value};
}

function evaluateCalculation(claim,sources) {
  const operator=claim.operator;
  if(!['sum','difference','ratio','percent_change'].includes(operator)) {
    throw new Error(`${claim.id}: unsupported calculation operator ${operator}`);
  }
  if(!claim.result) throw new Error(`${claim.id}: CALCULATION requires result`);
  if(!Array.isArray(claim.inputs)||claim.inputs.length<2) throw new Error(`${claim.id}: CALCULATION requires at least two numeric inputs`);
  if(['difference','ratio','percent_change'].includes(operator)&&claim.inputs.length!==2) {
    throw new Error(`${claim.id}: ${operator} requires exactly two inputs`);
  }
  const operands=claim.inputs.map(input=>{
    const {source,value}=lookupSourceValue(sources,input.source_id,input.value_id);
    return {
      source_id:input.source_id,value_id:input.value_id,
      value:finite(value.value,`${claim.id} input ${input.source_id}.${input.value_id}`),
      unit:normalizeUnit(value.unit),metric:value.metric||null,time_window:value.time_window||null,
      denominator:value.denominator,
    };
  });
  const resultUnit=normalizeUnit(claim.result.unit);
  let expected;
  if(operator==='sum') {
    const unit=operands[0].unit;
    if(operands.some(op=>op.unit!==unit)) throw new Error(`${claim.id}: sum inputs must share one unit`);
    if(resultUnit!==unit) throw new Error(`${claim.id}: sum result unit ${resultUnit} must equal input unit ${unit}`);
    expected=operands.reduce((total,op)=>total+op.value,0);
  }
  if(operator==='difference') {
    const unit=operands[0].unit;
    if(operands.some(op=>op.unit!==unit)) throw new Error(`${claim.id}: difference inputs must share one unit`);
    const required=unit==='%'?'pp':unit;
    if(resultUnit!==required) throw new Error(`${claim.id}: difference of ${unit} inputs requires result unit ${required}`);
    expected=operands[0].value-operands[1].value;
  }
  if(operator==='ratio') {
    if(operands[1].value===0) throw new Error(`${claim.id}: ratio denominator cannot be zero`);
    if(!['%','ratio'].includes(resultUnit)) throw new Error(`${claim.id}: ratio result unit must be ratio or %`);
    expected=operands[0].value/operands[1].value*(resultUnit==='%'?100:1);
    if(claim.result.denominator!=null) {
      finite(claim.result.denominator,`${claim.id} result denominator`);
      if(!close(claim.result.denominator,operands[1].value)) {
        throw new Error(`${claim.id}: declared denominator ${claim.result.denominator} does not match operand ${operands[1].value}`);
      }
    }
  }
  if(operator==='percent_change') {
    if(operands[0].value===0) throw new Error(`${claim.id}: percent_change baseline cannot be zero`);
    const unit=operands[0].unit;
    if(operands.some(op=>op.unit!==unit)) throw new Error(`${claim.id}: percent_change inputs must share one unit`);
    if(resultUnit!=='%') throw new Error(`${claim.id}: percent_change result unit must be %`);
    expected=(operands[1].value-operands[0].value)/operands[0].value*100;
  }
  const operandMetrics=operands.map(op=>op.metric).filter(Boolean);
  if(operandMetrics.length>1&&new Set(operandMetrics).size>1) {
    throw new Error(`${claim.id}: calculation operands use different source metrics: ${operandMetrics.join(' / ')}`);
  }
  const windows=operands.map(op=>op.time_window).filter(Boolean);
  if(operator==='percent_change') {
    if(operands.some(op=>!op.time_window)) throw new Error(`${claim.id}: percent_change requires explicit baseline and current time windows`);
    if(!claim.result.time_window) throw new Error(`${claim.id}: percent_change result requires a time_window covering both periods`);
    if(!claim.result.time_window.includes(operands[0].time_window)||!claim.result.time_window.includes(operands[1].time_window)) {
      throw new Error(`${claim.id}: result time_window must include ${operands[0].time_window} and ${operands[1].time_window}`);
    }
  } else if(windows.length) {
    if(new Set(windows).size>1) throw new Error(`${claim.id}: calculation operands use different time windows`);
    if(claim.result.time_window!==windows[0]) throw new Error(`${claim.id}: result time_window must be ${windows[0]}`);
  } else if(claim.result.time_window) {
    throw new Error(`${claim.id}: result time_window requires explicit input time windows`);
  }
  finite(expected,`${claim.id} computed result`);
  finite(claim.result.value,`${claim.id} declared result`);
  if(!close(claim.result.value,expected)) {
    throw new Error(`${claim.id}: declared result ${claim.result.value} does not match ${operator} arithmetic ${expected}`);
  }
  return {
    claim_id:claim.id,operator,expected,declared:claim.result.value,unit:claim.result.unit,
    denominator:claim.result.denominator,time_window:claim.result.time_window||null,
    operands:operands.map(op=>({source_id:op.source_id,value_id:op.value_id,value:op.value,unit:op.unit,
      metric:op.metric,time_window:op.time_window})),
  };
}

function formatNumber(value,format={}) {
  finite(value,'formatted value');
  const kind=format.kind||'number';
  const precision=format.precision;
  let text;
  if(kind==='number') text=String(value);
  else if(kind==='integer') {
    if(!Number.isInteger(value)) throw new Error(`integer format requires an integer, received ${value}`);
    text=String(value);
  } else if(kind==='decimal') text=value.toFixed(precision==null?1:precision);
  else if(kind==='percent') text=value.toFixed(precision==null?0:precision)+'%';
  else if(kind==='pp') text=value.toFixed(precision==null?0:precision)+'pp';
  else if(kind==='thousands') {
    const digits=precision==null?0:precision;
    const fixed=value.toFixed(digits);
    const [integer,fraction]=fixed.split('.');
    const sign=integer.startsWith('-')?'-':'';
    const padded=sign?integer.slice(1):integer;
    const grouped=padded.replace(/\B(?=(\d{3})+(?!\d))/g,',');
    text=sign+grouped+(fraction?'.'+fraction:'');
  } else throw new Error(`Unsupported numeric format: ${kind}`);
  return text+(format.suffix||'');
}

function resolvePointer(document,pointer) {
  if(pointer==='')return document;
  if(!pointer.startsWith('/')) throw new Error(`JSON pointer must start with /: ${pointer}`);
  let current=document;
  for(const token of pointer.slice(1).split('/')) {
    const key=token.replace(/~1/g,'/').replace(/~0/g,'~');
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

module.exports={evaluateCalculation,formatNumber,resolvePointer,normalizeUnit,close,TOLERANCE};
