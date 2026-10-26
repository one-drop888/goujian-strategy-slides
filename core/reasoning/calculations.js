const TOLERANCE=16*Number.EPSILON;

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
  if(typeof actual!=='number'||typeof expected!=='number'||!Number.isFinite(actual)||!Number.isFinite(expected))return false;
  if(actual===expected)return true;
  if(actual===0||expected===0)return false;
  return Math.abs(actual-expected)<=TOLERANCE*Math.max(Math.abs(actual),Math.abs(expected));
}
// Neumaier summation keeps long decimal runs (for example 1000 contributions of
// 0.1) from drifting outside the strict reconciliation tolerance.
function compensatedSum(values) {
  let sum=0,compensation=0;
  for(const value of values) {
    const next=sum+value;
    if(Math.abs(sum)>=Math.abs(value)) compensation+=(sum-next)+value;
    else compensation+=(value-next)+sum;
    sum=next;
  }
  return sum+compensation;
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
    const unit=normalizeUnit(value.unit),metric=String(value.metric||'').trim(),time_window=String(value.time_window||'').trim();
    if(!unit) throw new Error(`${claim.id}: input ${input.source_id}.${input.value_id} requires an explicit unit`);
    if(!metric) throw new Error(`${claim.id}: input ${input.source_id}.${input.value_id} requires an explicit metric`);
    if(!time_window) throw new Error(`${claim.id}: input ${input.source_id}.${input.value_id} requires an explicit time_window`);
    return {
      source_id:input.source_id,value_id:input.value_id,
      value:finite(value.value,`${claim.id} input ${input.source_id}.${input.value_id}`),
      unit,metric,time_window,denominator:value.denominator,
    };
  });
  const operandKeys=operands.map(op=>`${op.source_id}.${op.value_id}`);
  if(new Set(operandKeys).size!==operandKeys.length) {
    throw new Error(`${claim.id}: duplicate operands ${operandKeys.filter((key,index)=>operandKeys.indexOf(key)!==index).join(', ')}`);
  }
  const resultUnit=normalizeUnit(claim.result.unit);
  const operandMetrics=new Set(operands.map(op=>op.metric));
  if(operandMetrics.size!==1) {
    throw new Error(`${claim.id}: calculation operands use different source metrics: ${operands.map(op=>op.metric).join(' / ')}`);
  }
  const operandUnits=new Set(operands.map(op=>op.unit));
  if(operandUnits.size!==1) {
    throw new Error(`${claim.id}: ${operator} inputs must share one compatible unit, received ${operands.map(op=>op.unit).join(' / ')}`);
  }
  const unit=operands[0].unit,metric=operands[0].metric;
  if(claim.result.metric&&String(claim.result.metric).trim()!==metric) {
    throw new Error(`${claim.id}: result metric ${claim.result.metric} does not match operand metric ${metric}`);
  }
  let expected;
  if(operator==='sum') {
    if(['%','pp'].includes(unit)) throw new Error(`${claim.id}: sum of ${unit} values is not a valid aggregate; use raw counts or weighted totals`);
    if(resultUnit!==unit) throw new Error(`${claim.id}: sum result unit ${resultUnit} must equal input unit ${unit}`);
    expected=compensatedSum(operands.map(op=>op.value));
  }
  if(operator==='difference') {
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
    if(operands[0].value<=0) throw new Error(`${claim.id}: percent_change baseline must be positive, received ${operands[0].value}`);
    if(resultUnit!=='%') throw new Error(`${claim.id}: percent_change result unit must be %`);
    expected=(operands[1].value-operands[0].value)/operands[0].value*100;
  }
  if(operator==='percent_change') {
    if(operands[0].time_window===operands[1].time_window) {
      throw new Error(`${claim.id}: percent_change baseline and current time windows must differ`);
    }
    if(!claim.result.time_window) throw new Error(`${claim.id}: percent_change result requires a time_window covering both periods`);
    if(!claim.result.time_window.includes(operands[0].time_window)||!claim.result.time_window.includes(operands[1].time_window)) {
      throw new Error(`${claim.id}: result time_window must include ${operands[0].time_window} and ${operands[1].time_window}`);
    }
  } else {
    if(operands.some(op=>op.time_window!==operands[0].time_window)) {
      throw new Error(`${claim.id}: calculation operands use different time windows`);
    }
    if(!claim.result.time_window) throw new Error(`${claim.id}: ${operator} result requires an explicit time_window`);
    if(claim.result.time_window!==operands[0].time_window) {
      throw new Error(`${claim.id}: result time_window must be ${operands[0].time_window}`);
    }
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

module.exports={evaluateCalculation,formatNumber,resolvePointer,normalizeUnit,close,compensatedSum,TOLERANCE};
