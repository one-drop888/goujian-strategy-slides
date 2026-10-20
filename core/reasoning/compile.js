const fs=require('fs');
const path=require('path');
const {validatePlan,stableStringify,sha256}=require('./validate-plan');
const {selectTheme}=require('./theme-decision');
const {validateDeck,schemaErrors}=require('../schema/validate');
const {buildDeck}=require('../renderer');
const {verifyBuiltDeck}=require('./verify');

function readPlan(planPath) {
  return JSON.parse(fs.readFileSync(planPath,'utf8'));
}

function sourcePaths(plan,planDir) {
  return [
    ...(plan.sources||[]).filter(source=>source.path).map(source=>path.resolve(planDir,source.path)),
    ...((plan.deck||{}).assets||[]).filter(asset=>asset.path).map(asset=>path.resolve(planDir,asset.path)),
  ];
}

function safeOutput(target,label,inputs) {
  const resolved=path.resolve(target);
  for(const input of inputs) if(input&&resolved===path.resolve(input)) throw new Error(`${label} must not overwrite input ${input}`);
  return resolved;
}

function coverageReport(plan,validation) {
  const covered=new Set();
  for(const slide of plan.slides) for(const sourceId of slide.source_ids) covered.add(validation.canonical(sourceId));
  return (plan.sources||[]).map(source=>({
    source_id:source.id,importance:source.importance,
    disposition:validation.dispositions.get(source.id)?.disposition,
    canonical_source:validation.canonical(source.id),
    covered:covered.has(validation.canonical(source.id)),
  }));
}

async function compilePlan(planPath,options={}) {
  const resolvedPlan=path.resolve(planPath);
  const planDir=path.dirname(resolvedPlan);
  const repoRoot=options.repoRoot||path.resolve(__dirname,'../..');
  const plan=readPlan(resolvedPlan);
  const validation=validatePlan(plan,{planDir,repoRoot});
  if(!validation.valid) {
    const error=new Error(validation.errors.join('\n'));
    error.name='PlanValidationError';error.errors=validation.errors;throw error;
  }
  const theme=selectTheme(plan,{planDir,repoRoot,profile:options.profile});
  const ordered=[...plan.slides].sort((a,b)=>a.order-b.order);
  const spec={...plan.deck,slides:ordered.map(slide=>slide.spec)};
  const deckErrors=validateDeck(spec);
  if(deckErrors.length) {
    const error=new Error(deckErrors.join('\n'));
    error.name='PlanValidationError';error.errors=deckErrors;throw error;
  }
  const spec_sha256=sha256(stableStringify(spec));
  const inputs=[resolvedPlan,...sourcePaths(plan,planDir)];
  const outPath=safeOutput(options.out||path.join(planDir,`${plan.plan_id}.pptx`),'PPTX output',inputs);
  const specOut=options.specOut?safeOutput(options.specOut,'Spec output',inputs):null;
  if(specOut&&specOut===outPath) throw new Error('Spec output must differ from the PPTX output');
  for(const target of [outPath,specOut].filter(Boolean)) {
    if(fs.existsSync(target)&&!options.force) throw new Error(`${target} already exists; pass --force to overwrite that output (inputs are never overwritten)`);
  }
  const notes=ordered.map(slide=>[
    `[reasoning:${slide.id}] ${slide.question}`,
    `claims: ${slide.claim_ids.join(', ')}`,
    `sources: ${slide.source_ids.join(', ')}`,
    `mode: ${slide.title_mode}${slide.appendix?' | appendix':''}`,
    `transition: ${slide.transition}`,
  ].join(' | '));
  const reportFactory=({content_sha256,theme_decision})=>{
    const coverage=coverageReport(plan,validation);
    return {
      schema_version:'1.0',
      status:'VALIDATED',
      generated_at:new Date().toISOString(),
      plan_id:plan.plan_id,
      synthetic:plan.synthetic===true,
      plan_sha256:validation.plan_sha256,
      spec_sha256,
      pptx_content_sha256:content_sha256,
      intent:plan.intent,
      theme_decision,
      sources:(plan.sources||[]).map(source=>({
        ...source,
        verification:validation.hashes.get(source.id),
        disposition:validation.dispositions.get(source.id)?.disposition,
        canonical_source:validation.canonical(source.id),
      })),
      claims:(plan.claims||[]).map(claim=>({...claim,calculation:validation.calculations.get(claim.id)||null})),
      content_decisions:plan.content_decisions,
      coverage,
      findings:plan.findings||[],
      evidence_gaps:plan.evidence_gaps||[],
      candidate_conclusions:plan.candidate_conclusions||[],
      uncertainties:plan.uncertainties||[],
      storyline_strategy:plan.storyline_strategy||null,
      slides:ordered.map((slide,index)=>({
        slide_id:slide.id,order:slide.order,spec_index:index,question:slide.question,
        title_mode:slide.title_mode,claim_ids:slide.claim_ids,source_ids:slide.source_ids,
        transition:slide.transition,communication_intent:slide.communication_intent,
        visual_intent:slide.visual_intent||null,appendix:slide.appendix,bindings:slide.bindings.length,
      })),
      boundaries:{
        semantic_faithfulness:'REQUIRES_REVIEWER',
        source_authenticity:'HASH_VERIFIED_WHERE_PATH_PRESENT; summaries are Agent-provided',
        visual_review:'NOT_RUN',
        arithmetic:'DETERMINISTICALLY_VALIDATED',
      },
    };
  };
  const built=await buildDeck(spec,outPath,{
    repoRoot,specDir:planDir,themeDecision:theme,
    reasoning:{validated:true,plan_sha256:validation.plan_sha256,notes,reportFactory},
  });
  const verification=await verifyBuiltDeck(outPath,spec,{plan_sha256:validation.plan_sha256,spec_sha256,slides:ordered,
    report_sha256:built.reasoning.report_sha256},repoRoot);
  const sidecar={
    ...built.reasoning_report,
    pptx_sha256:built.pptx_sha256,
    pptx_content_sha256:built.content_sha256,
    embedded_report_sha256:built.reasoning.report_sha256,
    verification,
  };
  fs.writeFileSync(outPath+'.reasoning.json',JSON.stringify(sidecar,null,2)+'\n');
  if(specOut) fs.writeFileSync(specOut,JSON.stringify(spec,null,2)+'\n');
  return {status:'PASS',outPath,specOut,reasoning:outPath+'.reasoning.json',scene:built.scene,
    theme_decision:built.theme_decision,verification,warnings:validation.warnings,
    pptx_sha256:built.pptx_sha256,content_sha256:built.content_sha256};
}

module.exports={compilePlan,readPlan,sourcePaths};
