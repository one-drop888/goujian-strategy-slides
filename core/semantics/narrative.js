'use strict';
// Checks declared argument structure and retained evidence; meaning and source truth require review.
const crypto=require('crypto');
const {getPointer,allowedBindingPath,allowedTextPath}=require('./numeric');
const ROLES=new Set(['cover','transition','summary','detail','comparison','decision','appendix']);
const RELATIONS=new Set(['introduces','supports','expands','contrasts','leads_to','recaps']);
const list=value=>Array.isArray(value)?value:[];
const KINDS=new Set(['FACT','CALCULATION','INTERPRETATION','HYPOTHESIS','RECOMMENDATION']);
const norm=value=>String(value??'').replace(/\s+/g,' ').trim();
const fingerprint=value=>crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
function inspectNarrative(spec,{plan}={}) {
  const graph=spec.narrative;
  const titles=new Map(),redundancy=[],errors=[],notes=[];
  const issue=message=>errors.push(message);
  const slides=spec.slides||[];
  const nodes=graph?.nodes||[];
  const bySlide=new Map(Array.isArray(nodes)?nodes.map(node=>[node?.slide,node]):[]);
  for(const [index,slide] of slides.entries()) {
    const title=norm(slide.title_short||slide.title);
    if(!title)continue;
    if(titles.has(title)) {
      const prior=titles.get(title),a=bySlide.get(prior),b=bySlide.get(index+1);
      const expanded=a?.role==='summary'&&b?.role==='detail'&&norm(b.expansion_note);
      if(!expanded)redundancy.push({slides:[prior,index+1],kind:'exact_title',reason:'Exact title repeated; reviewer decides whether it adds information.'});
    } else titles.set(title,index+1);
  }
  if(graph==null)return {status:redundancy.length?'PASS_WITH_NOTES':'NOT_RUN',scope:'exact-title candidates only; no declared narrative graph',errors,notes,redundancy,review_required:true,checks:{NARRATIVE_COHERENCE:'NOT_RUN',CROSS_SLIDE_REDUNDANCY:redundancy.length?'PARTIAL':'NOT_RUN',CLAIM_COVERAGE:'NOT_RUN',EVIDENCE_PRESERVATION:'NOT_RUN',DECISION_RELEVANCE:'NOT_RUN',VISUALIZATION_OPPORTUNITY_REVIEW:'NOT_RUN'}};
  const array=(value,label)=>{
    if(!Array.isArray(value)||value.length>500){issue(`${label} must be an array with at most 500 entries`);return [];}
    return value;
  };
  const text=(value,label)=>{if(typeof value!=='string'||!value.trim())issue(`${label} requires nonempty text`);};
  const id=(value,label)=>{if(typeof value!=='string'||!value.trim()||value.length>100)issue(`${label} requires an ID of 1–100 characters`);};
  const catalogue=(rows,label)=>{
    const map=new Map();
    for(const row of array(rows,label)) {
      if(!row||typeof row!=='object'||Array.isArray(row)){issue(`${label} entries must be objects`);continue;}
      id(row.id,`${label}.id`);if(map.has(row.id))issue(`${label} duplicate ID ${row.id}`);map.set(row.id,row);
    }
    return map;
  };
  if(typeof graph!=='object'||Array.isArray(graph)){issue('narrative must be an object');return {status:'FAIL',errors,review_required:true};}
  text(graph.objective,'narrative.objective');
  const claims=catalogue(graph.claims??[],'narrative.claims');
  const evidence=catalogue(graph.evidence??[],'narrative.evidence');
  const decisions=catalogue(graph.decisions??[],'narrative.decisions');
  const pageNodes=array(graph.nodes,'narrative.nodes'),edges=array(graph.edges??[],'narrative.edges');
  const validNodes=new Map(),usedClaims=new Set(),usedEvidence=new Set(),usedDecisions=new Set(),bindings=[];
  for(const node of pageNodes) {
    if(!node||typeof node!=='object'||Array.isArray(node)){issue('narrative.nodes entries must be objects');continue;}
    if(!Number.isInteger(node.slide)||node.slide<1||node.slide>slides.length){issue(`narrative node references missing slide ${node.slide}`);continue;}
    if(validNodes.has(node.slide))issue(`narrative node repeats slide ${node.slide}`);validNodes.set(node.slide,node);
    if(!ROLES.has(node.role))issue(`slide ${node.slide}: unknown narrative role ${node.role}`);
    text(node.question,`slide ${node.slide}.question`);
    const refs=(field,map,used)=>{
      for(const ref of array(node[field]??[],`slide ${node.slide}.${field}`)) {
        if(!map.has(ref))issue(`slide ${node.slide}: unknown ${field} ${ref}`);else used.add(ref);
      }
    };
    refs('claim_ids',claims,usedClaims);refs('evidence_ids',evidence,usedEvidence);refs('decision_ids',decisions,usedDecisions);
    if(!['cover','transition'].includes(node.role)&&!(node.claim_ids||[]).length)issue(`slide ${node.slide}: content page requires a declared claim`);
    if(node.role==='decision'&&!(node.decision_ids||[]).length)issue(`slide ${node.slide}: decision page requires a declared decision`);
    if(node.slide>1)text(node.transition,`slide ${node.slide}.transition`);
  }
  for(let page=1;page<=slides.length;page++)if(!validNodes.has(page))issue(`narrative omits slide ${page}`);
  const planClaims=plan?new Map((plan.claims||[]).map(claim=>[claim.id,claim])):null;
  const planSourceIds=plan?new Set((plan.sources||[]).map(source=>source.id)):null;
  for(const [eid,item] of evidence) {
    const list=array(item.bindings,`evidence ${eid}.bindings`);
    if(!list.length)issue(`evidence ${eid} requires retained output bindings`);
    if(planSourceIds&&item.source_id&&!planSourceIds.has(item.source_id))issue(`evidence ${eid} references unknown plan source ${item.source_id}`);
    if(!item.source_id)notes.push(`evidence ${eid}: no source_id; output presence does not establish source truth`);
    for(const binding of list) {
      if(!binding||!Number.isInteger(binding.slide)||binding.slide<1||binding.slide>slides.length){issue(`evidence ${eid} has an invalid binding slide`);continue;}
      const pointer=binding.pointer;
      if(typeof pointer!=='string'||!(allowedBindingPath(pointer)||allowedTextPath(pointer)||/^\/(rows\/\d+|series\/\d+\/values|items\/\d+)$/u.test(pointer))){issue(`evidence ${eid}: unsupported evidence pointer ${pointer}`);continue;}
      try {
        const value=getPointer(slides[binding.slide-1],pointer);
        if(value==null||typeof value==='string'&&!value.trim()||Array.isArray(value)&&!value.length)throw Error('binding is missing or empty');
        const node=validNodes.get(binding.slide);
        if(!node?.evidence_ids?.includes(eid))throw Error('bound slide does not reference this evidence ID');
        bindings.push({evidence_id:eid,slide:binding.slide,pointer,content_sha256:fingerprint({value,unit:slides[binding.slide-1].unit??null,period:slides[binding.slide-1].period??spec.period??null}),disposition:node.role==='appendix'?'appendix':'retained'});
      } catch(error){issue(`evidence ${eid}: ${error.message}`);}
    }
    if(item.required!==false&&!usedEvidence.has(eid))issue(`required evidence ${eid} is not covered`);
  }
  for(const [cid,claim] of claims) {
    text(claim.text,`claim ${cid}.text`);
    if(planClaims) {
      const source=planClaims.get(cid);
      if(!source||norm(source.text)!==norm(claim.text)||(claim.kind||claim.type||'FACT')!==source.type)issue(`claim ${cid} does not match the validated reasoning plan`);
    }
    if(!KINDS.has(claim.kind||claim.type||'FACT'))issue(`claim ${cid}: unknown claim kind`);
    const refs=claim.evidence_ids??[...evidence.values()].filter(item=>list(claim.source_ids).includes(item.source_id)).map(item=>item.id);
    if(!Array.isArray(refs))issue(`claim ${cid}.evidence_ids must be an array`);
    else {
      if(!refs.length&&!['HYPOTHESIS','RECOMMENDATION'].includes(claim.kind||claim.type))issue(`claim ${cid}: factual or interpretive claim requires supporting evidence`);
      for(const ref of refs)if(!evidence.has(ref))issue(`claim ${cid}: unknown evidence ${ref}`);
    }
    if(claim.required!==false&&!usedClaims.has(cid))issue(`required claim ${cid} is not covered`);
  }
  for(const node of validNodes.values()) for(const cid of list(node.claim_ids)) {
    const claim=claims.get(cid);
    for(const eid of list(claim?.evidence_ids)) if(!list(node.evidence_ids).includes(eid))issue(`slide ${node.slide}: claim ${cid} is missing evidence reference ${eid}`);
  }
  for(const [did,decision] of decisions) {
    text(decision.question,`decision ${did}.question`);
    if(!usedDecisions.has(did))issue(`decision ${did} is not linked to an output page`);
    for(const ref of array(decision.claim_ids??[],`decision ${did}.claim_ids`))if(!claims.has(ref))issue(`decision ${did}: unknown claim ${ref}`);
    if(!norm(decision.owner)||!norm(decision.timing))notes.push(`decision ${did}: owner/timing not supplied; do not invent them`);
  }
  const uniqueEdges=new Set();
  for(const edge of edges) {
    if(!edge||!validNodes.has(edge.from)||!validNodes.has(edge.to)||edge.from>=edge.to){issue('narrative edges must connect existing pages in presentation order');continue;}
    if(!RELATIONS.has(edge.relation))issue(`unknown narrative relation ${edge.relation}`);
    text(edge.explanation,`edge ${edge.from}->${edge.to}.explanation`);
    const key=`${edge.from}:${edge.to}:${edge.relation}`;if(uniqueEdges.has(key))issue(`duplicate narrative edge ${key}`);uniqueEdges.add(key);
  }
  for(let page=1;page<slides.length;page++)if(!edges.some(edge=>edge?.from===page&&edge?.to===page+1))notes.push(`slides ${page}->${page+1}: no explicit transition edge`);
  const signatures=new Map();
  for(const node of validNodes.values()) {
    const signature=JSON.stringify([[...list(node.claim_ids)].sort(),[...list(node.evidence_ids)].sort()]);
    if(!(node.claim_ids||[]).length)continue;
    const prior=signatures.get(signature);
    if(prior) {
      const expanded=prior.role==='summary'&&node.role==='detail'&&norm(node.expansion_note);
      if(!expanded)redundancy.push({slides:[prior.slide,node.slide],kind:'same_claims_and_evidence',reason:'No declared new evidence; review for useful recap versus redundancy.'});
    }else signatures.set(signature,node);
  }
  return {status:errors.length?'FAIL':'PASS_WITH_NOTES',scope:'declared graph, referenced output presence and exact duplicate candidates; not source authenticity or semantic inference',errors,notes,bindings,redundancy,review_required:true,coverage:{slides:validNodes.size,total_slides:slides.length,claims:usedClaims.size,total_claims:claims.size,evidence:usedEvidence.size,total_evidence:evidence.size,decisions:usedDecisions.size},checks:{NARRATIVE_COHERENCE:errors.length?'FAIL':'PASS_WITH_NOTES',CROSS_SLIDE_REDUNDANCY:redundancy.length?'PARTIAL':'PASS',CLAIM_COVERAGE:errors.some(x=>x.includes('claim'))?'FAIL':'PASS',EVIDENCE_PRESERVATION:errors.some(x=>x.includes('evidence'))?'FAIL':'PASS',DECISION_RELEVANCE:decisions.size?'PASS_WITH_NOTES':'PARTIAL',VISUALIZATION_OPPORTUNITY_REVIEW:'NOT_RUN'}};
}
module.exports={inspectNarrative,ROLES,RELATIONS};
