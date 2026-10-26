const crypto=require('crypto');
const fs=require('fs');
const path=require('path');
const {schemaErrors}=require('../schema/validate');
const {resolveSlide}=require('../composition/resolver');
const {evaluateCalculation,formatNumber,resolvePointer,normalizeUnit,close}=require('./calculations');
const {validateMetricCatalogue,formatMetric}=require('../semantics/numeric');

const QUALIFIED=/可能|假设|待验证|尚需|不确定|未知|待核实|不能证明|hypothes|may|might|possibly|potential|unknown|not\s+proven|requires?\s+validation/i;
const NUMERIC_CELL=/^(?:[¥$€£]\s*)?[-+−]?\d[\d,]*(?:\.\d+)?\s*(?:%|pp|万元|万|元|单|天|人|个|次)?$/u;

function stableStringify(value) {
  if(Array.isArray(value)) return '['+value.map(stableStringify).join(',')+']';
  if(value&&typeof value==='object') {
    return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+stableStringify(value[key])).join(',')+'}';
  }
  return JSON.stringify(value);
}
function sha256(value) { return crypto.createHash('sha256').update(value).digest('hex'); }

function findCycles(ids,edges) {
  const state=new Map(),cycles=[];
  function visit(id,trail) {
    if(state.get(id)===2)return;
    if(state.get(id)===1) { cycles.push([...trail.slice(trail.indexOf(id)),id].join(' -> ')); return; }
    state.set(id,1);
    for(const next of edges.get(id)||[]) if(ids.has(next)) visit(next,[...trail,id]);
    state.set(id,2);
  }
  for(const id of ids) visit(id,[]);
  return cycles;
}

function isNumericCell(value) {
  if(typeof value==='number') return Number.isFinite(value);
  return NUMERIC_CELL.test(String(value??'').trim());
}

function valueKey(sourceId,valueId) { return `${sourceId}\u0000${valueId}`; }
function valueFacts(value) {
  return {
    value:Number(value.value),
    unit:normalizeUnit(value.unit),
    metric:String(value.metric||'').trim(),
    time_window:String(value.time_window||'').trim(),
    label:String(value.label||'').trim(),
  };
}
function sameValueFacts(a,b) {
  const left=valueFacts(a),right=valueFacts(b);
  return close(left.value,right.value)&&left.unit===right.unit&&left.metric===right.metric
    &&left.time_window===right.time_window&&left.label===right.label;
}

function sourceVerification(plan,planDir,errors) {
  const hashes=new Map(),documents=new Map();
  function jsonDocument(file) {
    if(documents.has(file)) return documents.get(file);
    let document=null,error=null;
    try { document=JSON.parse(fs.readFileSync(file,'utf8')); }
    catch(caught) { error=caught.message; }
    const parsed={document,error};
    documents.set(file,parsed);
    return parsed;
  }
  for(const source of plan.sources||[]) {
    if(source.path) {
      const file=path.resolve(planDir,source.path);
      if(!fs.existsSync(file)||!fs.statSync(file).isFile()) {
        errors.push(`source ${source.id}: path not found: ${source.path}`);
        continue;
      }
      const actual=sha256(fs.readFileSync(file));
      if(source.sha256&&source.sha256!==actual) errors.push(`source ${source.id}: sha256 mismatch (declared ${source.sha256}, actual ${actual})`);
      const record={declared_path:source.path,sha256:actual,status:source.sha256?'HASH_VERIFIED':'FILE_HASHED'};
      const values=source.values||[];
      if(/\.json$/i.test(source.path)) {
        const parsed=jsonDocument(file);
        if(parsed.error) {
          errors.push(`source ${source.id}: structured JSON ledger cannot be parsed: ${parsed.error}`);
          record.ledger={format:'json',status:'INVALID_JSON',values:[]};
        } else if(!values.length) {
          record.ledger={format:'json',status:'JSON_VERIFIED_NO_VALUES',values:[]};
        } else {
          const entries=[];
          for(const value of values) {
            if(!value.json_pointer) {
              errors.push(`source ${source.id} value ${value.id}: structured JSON source requires json_pointer`);
              entries.push({value_id:value.id,pointer:null,status:'JSON_POINTER_MISSING'});
              continue;
            }
            try {
              const resolved=resolvePointer(parsed.document,value.json_pointer);
              let sourceValue;
              if(typeof resolved==='number') sourceValue=resolved;
              else if(resolved&&typeof resolved==='object'&&typeof resolved.value==='number') sourceValue=resolved.value;
              else throw new Error(`json_pointer must resolve to a finite number or an object with numeric value`);
              if(!Number.isFinite(sourceValue)) throw new Error('json_pointer resolved to a non-finite number');
              if(!close(sourceValue,value.value)) throw new Error(`declared value ${value.value} does not match source bytes ${sourceValue} at ${value.json_pointer}`);
              const slash=value.json_pointer.lastIndexOf('/');
              let parent=null;
              if(slash>0) {
                try { parent=resolvePointer(parsed.document,value.json_pointer.slice(0,slash)); } catch { parent=null; }
              }
              const metadata=[parent,resolved].filter(item=>item&&typeof item==='object');
              for(const item of metadata) {
                if(value.unit!=null&&item.unit!=null&&normalizeUnit(item.unit)!==normalizeUnit(value.unit)) {
                  throw new Error(`declared unit ${value.unit} does not match source bytes unit ${item.unit}`);
                }
                if(value.metric!=null&&item.metric!=null&&String(item.metric).trim()!==String(value.metric).trim()) {
                  throw new Error(`declared metric ${value.metric} does not match source bytes metric ${item.metric}`);
                }
                if(value.time_window!=null&&item.time_window!=null&&String(item.time_window).trim()!==String(value.time_window).trim()) {
                  throw new Error(`declared time_window ${value.time_window} does not match source bytes time_window ${item.time_window}`);
                }
                if(value.time_window!=null&&item.month!=null&&String(item.month).trim()!==String(value.time_window).trim()) {
                  throw new Error(`declared time_window ${value.time_window} does not match source bytes month ${item.month}`);
                }
              }
              entries.push({value_id:value.id,pointer:value.json_pointer,status:'JSON_POINTER_VERIFIED',source_value:sourceValue});
            } catch(error) {
              errors.push(`source ${source.id} value ${value.id}: ${error.message}`);
              entries.push({value_id:value.id,pointer:value.json_pointer,status:'JSON_POINTER_FAILED'});
            }
          }
          record.ledger={format:'json',status:entries.every(entry=>entry.status==='JSON_POINTER_VERIFIED')?'JSON_POINTER_VERIFIED':'JSON_POINTER_FAILED',values:entries};
        }
      } else if(values.length) {
        record.ledger={format:'unstructured',status:'REVIEWER_REQUIRED',values:values.map(value=>({value_id:value.id,status:'REVIEWER_REQUIRED'}))};
      }
      hashes.set(source.id,record);
    } else {
      const record={declared_path:null,sha256:source.sha256||null,status:source.sha256?'DECLARED_HASH_UNVERIFIED':'AGENT_SUMMARY'};
      if((source.values||[]).length) record.ledger={format:'none',status:'REVIEWER_REQUIRED',values:source.values.map(value=>({value_id:value.id,status:'REVIEWER_REQUIRED'}))};
      hashes.set(source.id,record);
    }
  }
  return hashes;
}

function numericPointerSet(slide) {
  const spec=slide.spec,pointers=new Set();
  (spec.series||[]).forEach((series,i)=>(series.values||[]).forEach((_,j)=>pointers.add(`/series/${i}/values/${j}`)));
  if(spec.dashboard) (spec.dashboard.series||[]).forEach((series,i)=>(series.values||[]).forEach((_,j)=>pointers.add(`/dashboard/series/${i}/values/${j}`)));
  (spec.panels||[]).forEach((panel,i)=>{
    if(panel.kind==='chart') (panel.series||[]).forEach((series,j)=>(series.values||[]).forEach((_,k)=>pointers.add(`/panels/${i}/series/${j}/values/${k}`)));
    if(panel.kind==='table') (panel.rows||[]).forEach((row,r)=>row.forEach((cell,c)=>{if(isNumericCell(cell))pointers.add(`/panels/${i}/rows/${r}/${c}`);}));
  });
  (spec.rows||[]).forEach((row,r)=>row.forEach((cell,c)=>{if(isNumericCell(cell))pointers.add(`/rows/${r}/${c}`);}));
  (spec.items||[]).forEach((item,i)=>{
    if(!item||typeof item!=='object')return;
    for(const field of ['value','target','actual','variance','delta']) {
      if(isNumericCell(item[field]))pointers.add(`/items/${i}/${field}`);
    }
  });
  return pointers;
}

function validateBindings(planSlide,sources,calculations,metrics,errors,closure) {
  const required=numericPointerSet(planSlide);
  const bound=new Set();
  for(const [index,binding] of (planSlide.bindings||[]).entries()) {
    const label=`slides[${planSlide.id}].bindings[${index}]`;
    if(bound.has(binding.pointer)) { errors.push(`${label}: duplicate binding for ${binding.pointer}`); continue; }
    bound.add(binding.pointer);
    let actual,expected;
    try { actual=resolvePointer(planSlide.spec,binding.pointer); }
    catch(error) { errors.push(`${label}: ${error.message}`); continue; }
    try {
      if(binding.target.kind==='metric') {
        const metric=metrics.get(binding.target.metric_id);
        if(!metric) throw new Error(`unknown metric ${binding.target.metric_id}`);
        if(typeof actual==='number') {
          if(metric.effective_value===null) throw new Error(`metric ${metric.id} is missing and cannot bind a numeric value`);
          if(binding.format.kind!=='number') throw new Error(`numeric JSON pointer ${binding.pointer} cannot use formatted binding ${binding.format.kind}`);
          if(!close(actual,metric.effective_value)) throw new Error(`bound value ${actual} does not match metric ${metric.id} effective value ${metric.effective_value}`);
        } else if(typeof actual==='string') {
          const formatted=formatMetric(metric).text;
          if(actual!==formatted) throw new Error(`bound text "${actual}" does not match metric ${metric.id} formatted as "${formatted}"`);
        } else if(actual===null) {
          if(metric.effective_value!==null) throw new Error(`null pointer ${binding.pointer} conflicts with metric ${metric.id} value ${metric.effective_value}`);
        } else throw new Error(`JSON pointer ${binding.pointer} must resolve to a number, string or null`);
        continue;
      }
      if(binding.target.kind==='source') {
        if(!closure.sourceIds.has(closure.canonical(binding.target.source_id))) {
          throw new Error(`binding source ${binding.target.source_id} is outside the slide source closure`);
        }
        const source=sources.get(binding.target.source_id);
        if(!source) throw new Error(`unknown source ${binding.target.source_id}`);
        const value=(source.values||[]).find(item=>item.id===binding.target.value_id);
        if(!value) throw new Error(`unknown numeric value ${binding.target.source_id}.${binding.target.value_id}`);
        expected={value:value.value,unit:value.unit,time_window:value.time_window};
      } else {
        if(!closure.claimIds.has(binding.target.claim_id)) {
          throw new Error(`binding calculation ${binding.target.claim_id} is outside the slide claim closure`);
        }
        const calculation=calculations.get(binding.target.claim_id);
        if(!calculation) throw new Error(`unknown calculation ${binding.target.claim_id} (or claim failed validation)`);
        expected={value:calculation.expected,unit:calculation.unit,time_window:calculation.time_window};
      }
      const unit=normalizeUnit(expected.unit),kind=binding.format.kind;
      if(kind==='percent'&&unit!=='%') throw new Error(`percent format requires a % source unit, received ${expected.unit||'none'}`);
      if(kind==='pp'&&unit!=='pp') throw new Error(`pp format requires a pp source unit, received ${expected.unit||'none'}`);
      if(binding.format.suffix&&expected.unit&&binding.format.suffix!==expected.unit) {
        throw new Error(`format suffix ${binding.format.suffix} does not match source unit ${expected.unit}`);
      }
      if(typeof actual==='number') {
        if(kind!=='number') throw new Error(`numeric JSON pointer ${binding.pointer} cannot use formatted binding ${kind}`);
        if(!close(actual,expected.value)) throw new Error(`bound value ${actual} does not match ${binding.target.kind} value ${expected.value}`);
      } else if(typeof actual==='string') {
        const formatted=formatNumber(expected.value,binding.format);
        if(actual!==formatted) throw new Error(`bound text "${actual}" does not match formatted ${expected.value} as "${formatted}"`);
      } else throw new Error(`JSON pointer ${binding.pointer} must resolve to a number or string`);
    } catch(error) { errors.push(`${label}: ${error.message}`); }
  }
  for(const pointer of required) if(!bound.has(pointer)) errors.push(`slides[${planSlide.id}]: unbound numeric value at ${pointer}`);
}

function validatePlan(plan,options={}) {
  const errors=[],warnings=[];
  const planDir=options.planDir||process.cwd();
  const repoRoot=options.repoRoot||path.resolve(__dirname,'../..');
  let schema=[];try{schema=schemaErrors('reasoning-plan',plan);}catch(error){errors.push(error.message);return {errors,valid:false};}
  if(schema.length)return {errors:schema.map(message=>`schema ${message}`),valid:false};
  let metrics=new Map();
  try { metrics=validateMetricCatalogue(plan.deck?.metrics,{label:'plan.deck.metrics'}); }
  catch(error) { errors.push(error.message); }
  const sources=new Map();
  for(const source of plan.sources) {
    if(sources.has(source.id)) errors.push(`duplicate source id ${source.id}`);
    sources.set(source.id,source);
    const valueIds=new Set();
    for(const value of source.values||[]) {
      if(valueIds.has(value.id)) errors.push(`source ${source.id}: duplicate numeric value id ${value.id}`);
      valueIds.add(value.id);
    }
  }
  const hashes=sourceVerification(plan,planDir,errors);
  const claims=new Map();
  for(const claim of plan.claims) {
    if(claims.has(claim.id)) errors.push(`duplicate claim id ${claim.id}`);
    claims.set(claim.id,claim);
  }
  const claimEdges=new Map();
  for(const claim of plan.claims) {
    for(const sourceId of claim.source_ids||[]) if(!sources.has(sourceId)) errors.push(`claim ${claim.id}: unknown source ${sourceId}`);
    for(const dependency of claim.depends_on||[]) {
      if(!claims.has(dependency)) errors.push(`claim ${claim.id}: unknown claim dependency ${dependency}`);
      else claimEdges.set(claim.id,[...(claimEdges.get(claim.id)||[]),dependency]);
    }
    if(claim.type==='FACT'&&!(claim.source_ids||[]).length) errors.push(`claim ${claim.id}: FACT requires source_ids`);
    if(['INTERPRETATION','RECOMMENDATION'].includes(claim.type)&&!(claim.source_ids||[]).length&&!(claim.depends_on||[]).length) {
      errors.push(`claim ${claim.id}: ${claim.type} requires source_ids or depends_on evidence`);
    }
    if(claim.type==='HYPOTHESIS') {
      if(!claim.uncertainty) errors.push(`claim ${claim.id}: HYPOTHESIS requires uncertainty`);
      if(!QUALIFIED.test(claim.text)) errors.push(`claim ${claim.id}: HYPOTHESIS must use visible qualified wording`);
    }
    if(claim.type==='CALCULATION') {
      if(!claim.operator||!claim.inputs||!claim.result) errors.push(`claim ${claim.id}: CALCULATION requires operator, inputs and result`);
    }
  }
  for(const cycle of findCycles(new Set(claims.keys()),claimEdges)) errors.push(`claim dependency cycle: ${cycle}`);

  const calculations=new Map();
  for(const claim of plan.claims.filter(item=>item.type==='CALCULATION')) {
    try { calculations.set(claim.id,evaluateCalculation(claim,sources)); }
    catch(error) { errors.push(error.message); }
  }

  const dispositions=new Map(),valueDispositionIndex=new Map(),dedupValueMaps=new Map();
  for(const decision of plan.content_decisions) {
    if(!sources.has(decision.source_id)) { errors.push(`content decision references unknown source ${decision.source_id}`); continue; }
    if(dispositions.has(decision.source_id)) errors.push(`source ${decision.source_id}: duplicate content disposition`);
    dispositions.set(decision.source_id,decision);
    if(decision.value_dispositions) {
      const source=sources.get(decision.source_id),values=new Map();
      for(const entry of decision.value_dispositions) {
        if(values.has(entry.value_id)) errors.push(`source ${decision.source_id}: duplicate value disposition ${entry.value_id}`);
        else if(!(source.values||[]).some(value=>value.id===entry.value_id)) {
          errors.push(`source ${decision.source_id}: value disposition references unknown value ${entry.value_id}`);
        }
        values.set(entry.value_id,entry);
      }
      valueDispositionIndex.set(decision.source_id,values);
    }
  }
  for(const decision of plan.content_decisions) {
    if(decision.disposition!=='deduplicate') {
      if(decision.value_map) errors.push(`source ${decision.source_id}: value_map is only valid with deduplicate disposition`);
      continue;
    }
    if(!decision.dedup_target) errors.push(`source ${decision.source_id}: deduplicate requires dedup_target`);
    else if(decision.dedup_target===decision.source_id) errors.push(`source ${decision.source_id}: dedup_target cannot be itself`);
    else if(!sources.has(decision.dedup_target)) errors.push(`source ${decision.source_id}: unknown dedup_target ${decision.dedup_target}`);
    else {
      const target=dispositions.get(decision.dedup_target);
      if(!target) errors.push(`source ${decision.source_id}: dedup_target ${decision.dedup_target} has no content disposition`);
      else if(target.disposition==='deduplicate') errors.push(`source ${decision.source_id}: dedup_target must be a retained canonical source`);
      else {
        const source=sources.get(decision.source_id),targetSource=sources.get(decision.dedup_target),mapping=new Map();
        for(const entry of decision.value_map||[]) {
          if(mapping.has(entry.from_value_id)) errors.push(`source ${decision.source_id}: duplicate value_map entry ${entry.from_value_id}`);
          const from=(source.values||[]).find(value=>value.id===entry.from_value_id);
          const to=(targetSource.values||[]).find(value=>value.id===entry.to_value_id);
          if(!from) errors.push(`source ${decision.source_id}: value_map references unknown value ${entry.from_value_id}`);
          else if(!to) errors.push(`source ${decision.source_id}: value_map references unknown target value ${decision.dedup_target}.${entry.to_value_id}`);
          else if(!sameValueFacts(from,to)) {
            errors.push(`source ${decision.source_id} value ${entry.from_value_id}: dedup mapping does not preserve label/metric/unit/time_window/value`);
          } else mapping.set(entry.from_value_id,entry.to_value_id);
        }
        for(const value of source.values||[]) {
          if(mapping.has(value.id)) continue;
          const match=(targetSource.values||[]).find(candidate=>sameValueFacts(value,candidate));
          if(match) mapping.set(value.id,match.id);
          else {
            errors.push(`source ${decision.source_id} value ${value.id}: novel numeric evidence (label/metric/unit/time_window/value) is not preserved by dedup_target ${decision.dedup_target}; add a matching value_map entry or retain this source`);
          }
        }
        dedupValueMaps.set(decision.source_id,mapping);
      }
    }
  }
  for(const source of plan.sources) if(!dispositions.has(source.id)) errors.push(`source ${source.id}: missing content decision`);
  function canonical(id) {
    const seen=new Set();
    while(dispositions.get(id)?.disposition==='deduplicate') {
      if(seen.has(id)) return id;
      seen.add(id);id=dispositions.get(id).dedup_target;
    }
    return id;
  }

  const aliasSets=new Map();
  function aliasSet(key) {
    if(!aliasSets.has(key)) aliasSets.set(key,new Set([key]));
    return aliasSets.get(key);
  }
  for(const [sourceId,mapping] of dedupValueMaps) {
    for(const [fromValue,targetValue] of mapping) {
      const left=aliasSet(valueKey(sourceId,fromValue)),right=aliasSet(valueKey(canonical(sourceId),targetValue));
      const merged=new Set([...left,...right]);
      for(const key of merged) aliasSets.set(key,merged);
    }
  }
  function markValue(set,sourceId,valueId) {
    const key=valueKey(sourceId,valueId);
    set.add(key);
    for(const alias of aliasSets.get(key)||[]) set.add(alias);
  }
  function isMarked(set,sourceId,valueId) {
    const key=valueKey(sourceId,valueId);
    if(set.has(key)) return true;
    for(const alias of aliasSets.get(key)||[]) if(set.has(alias)) return true;
    return false;
  }

  const boundValues=new Set(),calculationValues=new Set();
  const slideIds=new Set(),orders=new Set();
  const referencedClaims=new Set(),coveredSources=new Set();
  for(const planSlide of plan.slides) {
    if(slideIds.has(planSlide.id)) errors.push(`duplicate slide id ${planSlide.id}`);
    slideIds.add(planSlide.id);
    if(orders.has(planSlide.order)) errors.push(`duplicate slide order ${planSlide.order}`);
    orders.add(planSlide.order);
    const refs=[],claimClosure=new Set(),stack=[...planSlide.claim_ids];
    while(stack.length) {
      const claimId=stack.pop();
      if(claimClosure.has(claimId)) continue;
      claimClosure.add(claimId);
      const claim=claims.get(claimId);
      for(const dependency of claim?.depends_on||[]) stack.push(dependency);
    }
    for(const claimId of planSlide.claim_ids) {
      if(!claims.has(claimId)) errors.push(`slide ${planSlide.id}: unknown claim ${claimId}`);
      else { referencedClaims.add(claimId);refs.push(claims.get(claimId)); }
    }
    for(const sourceId of planSlide.source_ids) {
      if(!sources.has(sourceId)) errors.push(`slide ${planSlide.id}: unknown source ${sourceId}`);
      else coveredSources.add(canonical(sourceId));
    }
    const requiredSources=new Set();
    for(const claimId of claimClosure) {
      const claim=claims.get(claimId);
      if(!claim) continue;
      for(const sourceId of claim.source_ids||[]) requiredSources.add(sourceId);
      for(const input of claim.inputs||[]) requiredSources.add(input.source_id);
    }
    for(const binding of planSlide.bindings||[]) {
      if(binding.target.kind==='source') requiredSources.add(binding.target.source_id);
      else if(binding.target.kind==='calculation'&&!claimClosure.has(binding.target.claim_id)) {
        errors.push(`slides[${planSlide.id}].binding calculation ${binding.target.claim_id} is outside the slide claim closure`);
      }
    }
    const listedCanonical=new Set(planSlide.source_ids.filter(id=>sources.has(id)).map(canonical));
    const requiredCanonical=new Set([...requiredSources].filter(id=>sources.has(id)).map(canonical));
    for(const sourceId of requiredCanonical) if(!listedCanonical.has(sourceId)) {
      errors.push(`slide ${planSlide.id}: source closure missing ${sourceId} required by its claims or bindings`);
    }
    for(const sourceId of listedCanonical) if(!requiredCanonical.has(sourceId)) {
      errors.push(`slide ${planSlide.id}: source ${sourceId} is not referenced by its claim or binding closure`);
    }
    let resolved;
    try { resolved=resolveSlide(planSlide.spec,repoRoot); }
    catch(error) { errors.push(`slide ${planSlide.id}: ${error.message}`); continue; }
    const renderer=resolved.renderer,spec=resolved.slide;
    if(renderer==='chart') {
      if(!planSlide.visual_intent) errors.push(`slide ${planSlide.id}: chart slides require visual_intent`);
      const allowed={trend:['line','area'],comparison:['bar','column'],composition:['pie','doughnut'],distribution:['bar','column'],relationship:['scatter','bubble']};
      const chartType=spec.chartType||'bar';
      if(planSlide.visual_intent&&(!allowed[planSlide.visual_intent]||!allowed[planSlide.visual_intent].includes(chartType))) {
        errors.push(`slide ${planSlide.id}: unsupported chart intent ${planSlide.visual_intent} for ${chartType}`);
      }
    }
    if(spec.dashboard&&!planSlide.visual_intent) errors.push(`slide ${planSlide.id}: dashboard slides require visual_intent`);
    const hypotheses=refs.filter(claim=>claim.type==='HYPOTHESIS');
    if(hypotheses.length&&planSlide.title_mode!=='qualified_hypothesis'&&!QUALIFIED.test(spec.title||'')) {
      errors.push(`slide ${planSlide.id}: hypothesis presented as fact; use qualified wording or title_mode qualified_hypothesis`);
    }
    if(planSlide.title_mode==='qualified_hypothesis') {
      if(!hypotheses.length) errors.push(`slide ${planSlide.id}: qualified_hypothesis requires a HYPOTHESIS claim`);
      if(!QUALIFIED.test(spec.title||'')) errors.push(`slide ${planSlide.id}: qualified_hypothesis title must carry explicit qualification`);
    }
    if(planSlide.title_mode==='conclusion'&&!refs.some(claim=>['FACT','CALCULATION'].includes(claim.type))) {
      errors.push(`slide ${planSlide.id}: conclusion title requires a FACT or CALCULATION claim`);
    }
    validateBindings(planSlide,sources,calculations,metrics,errors,{sourceIds:requiredCanonical,claimIds:claimClosure,canonical});
    for(const binding of planSlide.bindings||[]) {
      if(binding.target.kind==='source'&&sources.has(binding.target.source_id)) {
        markValue(boundValues,binding.target.source_id,binding.target.value_id);
      }
    }
    const boundCalculations=new Set((planSlide.bindings||[])
      .filter(binding=>binding.target.kind==='calculation').map(binding=>binding.target.claim_id));
    for(const claimId of claimClosure) {
      const calculation=calculations.get(claimId);
      if(!calculation) continue;
      const visible=planSlide.appendix||Boolean(planSlide.summary_rationale)||boundCalculations.has(claimId);
      if(!visible) continue;
      for(const operand of calculation.operands) markValue(calculationValues,operand.source_id,operand.value_id);
    }
  }
  for(const source of plan.sources) {
    if(source.importance!=='critical') continue;
    const target=canonical(source.id);
    if(!coveredSources.has(target)) errors.push(`critical source ${source.id}: not covered by any slide (canonical ${target})`);
  }
  const appendixSources=new Set();
  for(const slide of plan.slides.filter(item=>item.appendix)) {
    for(const sourceId of slide.source_ids) if(sources.has(sourceId)) appendixSources.add(canonical(sourceId));
  }
  const valueCoverage=[];
  for(const source of plan.sources) {
    if(source.importance!=='critical') continue;
    const classified=valueDispositionIndex.get(source.id)||new Map();
    for(const value of source.values||[]) {
      const entry=classified.get(value.id);
      let basis=null;
      if(isMarked(boundValues,source.id,value.id)) basis='bound';
      else if(isMarked(calculationValues,source.id,value.id)) basis='calculation';
      else if(entry) {
        basis=entry.classification;
        if(entry.classification==='appendix'&&!appendixSources.has(canonical(source.id))) {
          errors.push(`source ${source.id} value ${value.id}: appendix classification requires an appendix slide covering the source`);
        }
      }
      if(!basis) errors.push(`critical numeric value ${source.id}.${value.id} (${value.label||value.metric||'unlabeled'}): not bound, used by a visible validated calculation, or explicitly classified noncritical/background/appendix`);
      valueCoverage.push({source_id:source.id,value_id:value.id,label:value.label||null,value:value.value,unit:value.unit||null,basis:basis||'UNCOVERED',rationale:entry?.rationale||null});
    }
  }
  for(const [sourceId,decision] of dispositions) {
    if(decision.disposition!=='appendix')continue;
    const covered=plan.slides.some(slide=>slide.appendix&&slide.source_ids.some(id=>canonical(id)===canonical(sourceId)));
    if(!covered) errors.push(`source ${sourceId}: appendix disposition requires an appendix slide reference`);
  }
  for(const note of [...(plan.findings||[]),...(plan.evidence_gaps||[]),...(plan.candidate_conclusions||[]),...(plan.uncertainties||[])]) {
    for(const claimId of note.claim_ids||[]) if(!claims.has(claimId)) errors.push(`note references unknown claim ${claimId}`);
    for(const sourceId of note.source_ids||[]) if(!sources.has(sourceId)) errors.push(`note references unknown source ${sourceId}`);
  }
  if(referencedClaims.size!==claims.size) {
    const unreferenced=[...claims.keys()].filter(id=>!referencedClaims.has(id));
    warnings.push(`claims not referenced by any slide: ${unreferenced.join(', ')}`);
  }
  return {valid:errors.length===0,errors,warnings,sources,claims,calculations,dispositions,hashes,
    canonical,coveredSources,referencedClaims,valueCoverage,dedupValueMaps,metrics,
    plan_sha256:sha256(stableStringify(plan))};
}

module.exports={validatePlan,stableStringify,sha256,NUMERIC_CELL};
