const crypto=require('crypto');
const fs=require('fs');
const path=require('path');
const {schemaErrors}=require('../schema/validate');
const {resolveSlide}=require('../composition/resolver');
const {evaluateCalculation,formatNumber,resolvePointer,normalizeUnit,close}=require('./calculations');

const QUALIFIED=/可能|假设|待验证|尚需|不确定|未知|待核实|不能证明|hypothes|may|might|possibly|potential|unknown|not\s+proven|requires?\s+validation/i;
const NUMERIC_CELL=/^[-+]?\d[\d,]*(?:\.\d+)?\s*(?:%|pp|万元|万|元|单|天|人|个|次)?$/;

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

function sourceVerification(plan,planDir,errors) {
  const hashes=new Map();
  for(const source of plan.sources||[]) {
    if(source.path) {
      const file=path.resolve(planDir,source.path);
      if(!fs.existsSync(file)||!fs.statSync(file).isFile()) {
        errors.push(`source ${source.id}: path not found: ${source.path}`);
        continue;
      }
      const actual=sha256(fs.readFileSync(file));
      if(source.sha256&&source.sha256!==actual) errors.push(`source ${source.id}: sha256 mismatch (declared ${source.sha256}, actual ${actual})`);
      hashes.set(source.id,{path:file,sha256:actual,status:source.sha256?'HASH_VERIFIED':'FILE_HASHED'});
    } else {
      hashes.set(source.id,{path:null,sha256:source.sha256||null,status:source.sha256?'DECLARED_HASH_UNVERIFIED':'AGENT_SUMMARY'});
    }
  }
  return hashes;
}

function numericPointerSet(slide,renderer) {
  const spec=slide.spec,pointers=new Set();
  (spec.series||[]).forEach((series,i)=>(series.values||[]).forEach((_,j)=>pointers.add(`/series/${i}/values/${j}`)));
  if(spec.dashboard) (spec.dashboard.series||[]).forEach((series,i)=>(series.values||[]).forEach((_,j)=>pointers.add(`/dashboard/series/${i}/values/${j}`)));
  (spec.panels||[]).forEach((panel,i)=>{
    if(panel.kind==='chart') (panel.series||[]).forEach((series,j)=>(series.values||[]).forEach((_,k)=>pointers.add(`/panels/${i}/series/${j}/values/${k}`)));
    if(panel.kind==='table') (panel.rows||[]).forEach((row,r)=>row.forEach((cell,c)=>{if(NUMERIC_CELL.test(String(cell).trim()))pointers.add(`/panels/${i}/rows/${r}/${c}`);}));
  });
  (spec.rows||[]).forEach((row,r)=>row.forEach((cell,c)=>{if(NUMERIC_CELL.test(String(cell).trim()))pointers.add(`/rows/${r}/${c}`);}));
  (spec.items||[]).forEach((item,i)=>{if(item&&typeof item==='object'&&NUMERIC_CELL.test(String(item.value??'').trim()))pointers.add(`/items/${i}/value`);});
  return pointers;
}

function validateBindings(planSlide,renderer,sources,calculations,errors) {
  const required=numericPointerSet(planSlide,renderer);
  const bound=new Set();
  for(const [index,binding] of (planSlide.bindings||[]).entries()) {
    const label=`slides[${planSlide.id}].bindings[${index}]`;
    if(bound.has(binding.pointer)) { errors.push(`${label}: duplicate binding for ${binding.pointer}`); continue; }
    bound.add(binding.pointer);
    let actual,expected;
    try { actual=resolvePointer(planSlide.spec,binding.pointer); }
    catch(error) { errors.push(`${label}: ${error.message}`); continue; }
    try {
      if(binding.target.kind==='source') {
        const source=sources.get(binding.target.source_id);
        if(!source) throw new Error(`unknown source ${binding.target.source_id}`);
        const value=(source.values||[]).find(item=>item.id===binding.target.value_id);
        if(!value) throw new Error(`unknown numeric value ${binding.target.source_id}.${binding.target.value_id}`);
        expected={value:value.value,unit:value.unit,time_window:value.time_window};
      } else {
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

  const dispositions=new Map();
  for(const decision of plan.content_decisions) {
    if(!sources.has(decision.source_id)) { errors.push(`content decision references unknown source ${decision.source_id}`); continue; }
    if(dispositions.has(decision.source_id)) errors.push(`source ${decision.source_id}: duplicate content disposition`);
    dispositions.set(decision.source_id,decision);
  }
  for(const decision of plan.content_decisions) {
    if(decision.disposition!=='deduplicate')continue;
    if(!decision.dedup_target) errors.push(`source ${decision.source_id}: deduplicate requires dedup_target`);
    else if(decision.dedup_target===decision.source_id) errors.push(`source ${decision.source_id}: dedup_target cannot be itself`);
    else if(!sources.has(decision.dedup_target)) errors.push(`source ${decision.source_id}: unknown dedup_target ${decision.dedup_target}`);
    else {
      const target=dispositions.get(decision.dedup_target);
      if(!target) errors.push(`source ${decision.source_id}: dedup_target ${decision.dedup_target} has no content disposition`);
      else if(target.disposition==='deduplicate') errors.push(`source ${decision.source_id}: dedup_target must be a retained canonical source`);
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

  const slideIds=new Set(),orders=new Set();
  const referencedClaims=new Set(),coveredSources=new Set();
  for(const planSlide of plan.slides) {
    if(slideIds.has(planSlide.id)) errors.push(`duplicate slide id ${planSlide.id}`);
    slideIds.add(planSlide.id);
    if(orders.has(planSlide.order)) errors.push(`duplicate slide order ${planSlide.order}`);
    orders.add(planSlide.order);
    const refs=[];
    for(const claimId of planSlide.claim_ids) {
      if(!claims.has(claimId)) errors.push(`slide ${planSlide.id}: unknown claim ${claimId}`);
      else { referencedClaims.add(claimId);refs.push(claims.get(claimId)); }
    }
    for(const sourceId of planSlide.source_ids) {
      if(!sources.has(sourceId)) errors.push(`slide ${planSlide.id}: unknown source ${sourceId}`);
      else coveredSources.add(canonical(sourceId));
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
    validateBindings(planSlide,renderer,sources,calculations,errors);
  }
  for(const source of plan.sources) {
    if(source.importance!=='critical') continue;
    const target=canonical(source.id);
    if(!coveredSources.has(target)) errors.push(`critical source ${source.id}: not covered by any slide (canonical ${target})`);
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
    canonical,coveredSources,referencedClaims,plan_sha256:sha256(stableStringify(plan))};
}

module.exports={validatePlan,stableStringify,sha256,NUMERIC_CELL};
