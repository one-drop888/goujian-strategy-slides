const fs=require('fs');
const path=require('path');
const {validatePlan,stableStringify,sha256}=require('./validate-plan');
const {selectTheme}=require('./theme-decision');
const {validateDeck,schemaErrors}=require('../schema/validate');
const {buildDeck}=require('../renderer');
const {verifyBuiltDeck}=require('./verify');
const {profileChain}=require('../style/profile-loader');
const {assertNotInput,assertDistinctOutputs}=require('../safety/paths');

function readPlan(planPath) {
  return JSON.parse(fs.readFileSync(planPath,'utf8'));
}

function sourcePaths(plan,planDir) {
  return [
    ...(plan.sources||[]).filter(source=>source.path).map(source=>path.resolve(planDir,source.path)),
    ...((plan.deck||{}).assets||[]).filter(asset=>asset.path).map(asset=>path.resolve(planDir,asset.path)),
  ];
}

function portableRef(fromDir,target) {
  const relative=path.relative(fromDir,path.resolve(target));
  return relative||path.basename(target);
}

function exportedSpec(spec,{planDir,specOut,repoRoot,theme}) {
  const clone=structuredClone(spec);
  const specDir=path.dirname(path.resolve(specOut));
  clone.assets=(clone.assets||[]).map(asset=>({...asset,path:portableRef(specDir,path.resolve(planDir,asset.path))}));
  const profilesRoot=path.join(repoRoot,'skill','profiles');
  const relative=path.relative(profilesRoot,path.resolve(theme.profile_path));
  const builtin=!relative.startsWith('..')&&!path.isAbsolute(relative);
  if(builtin) {
    const pieces=relative.split(path.sep);
    clone.profile=pieces.length===2&&pieces[1]==='profile.json'?pieces[0]:path.basename(relative,'.json');
  } else {
    clone.profile=portableRef(specDir,theme.profile_path);
  }
  return clone;
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
  const inputs=[resolvedPlan,...sourcePaths(plan,planDir),...profileChain(theme.profile_path,repoRoot,planDir)];
  const outPath=assertNotInput(options.out||path.join(planDir,`${plan.plan_id}.pptx`),'PPTX output',inputs);
  const scenePath=assertNotInput(outPath+'.scene.json','Scene output',inputs);
  const reasoningPath=assertNotInput(outPath+'.reasoning.json','Reasoning sidecar',inputs);
  const specOut=options.specOut?assertNotInput(options.specOut,'Spec output',inputs):null;
  assertDistinctOutputs([{path:outPath,label:'PPTX output'},{path:scenePath,label:'Scene output'},
    {path:reasoningPath,label:'Reasoning sidecar'},...(specOut?[{path:specOut,label:'Spec output'}]:[])]);
  for(const target of [outPath,scenePath,reasoningPath,specOut].filter(Boolean)) {
    if(fs.existsSync(target)&&!options.force) throw new Error(`${target} already exists; pass --force to overwrite that output (inputs are never overwritten)`);
  }
  const reportFactory=({content_sha256,theme_decision,metric_semantics})=>{
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
      metrics:plan.deck.metrics||[],
      metric_semantics:metric_semantics||null,
      sources:(plan.sources||[]).map(source=>({
        ...source,
        verification:validation.hashes.get(source.id),
        disposition:validation.dispositions.get(source.id)?.disposition,
        canonical_source:validation.canonical(source.id),
      })),
      claims:(plan.claims||[]).map(claim=>({...claim,calculation:validation.calculations.get(claim.id)||null})),
      content_decisions:plan.content_decisions,
      coverage,
      value_coverage:validation.valueCoverage,
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
    repoRoot,specDir:planDir,specPath:resolvedPlan,inputPaths:inputs,themeDecision:theme,
    reasoning:{plan,planDir,spec_sha256,reportFactory},
  });
  const sceneFile=JSON.parse(fs.readFileSync(built.scene,'utf8'));
  if(sceneFile.pptx_sha256!==built.pptx_sha256) throw new Error('Scene pptx_sha256 does not match the built deck');
  const verification=await verifyBuiltDeck(outPath,built.effective_spec,{plan_sha256:validation.plan_sha256,spec_sha256,slides:ordered,
    report_sha256:built.reasoning.report_sha256,expected_pptx_sha256:sceneFile.pptx_sha256,
    metric_semantics:sceneFile.metric_semantics},repoRoot);
  const sidecar={
    ...built.reasoning_report,
    pptx_sha256:built.pptx_sha256,
    pptx_content_sha256:built.content_sha256,
    pptx_content_sha256_scope:'pre_embed_zip_diagnostic_not_recomputable_from_final_pptx',
    embedded_report_sha256:built.reasoning.report_sha256,
    verification,
  };
  fs.writeFileSync(reasoningPath,JSON.stringify(sidecar,null,2)+'\n');
  if(specOut) {
    fs.mkdirSync(path.dirname(specOut),{recursive:true});
    fs.writeFileSync(specOut,JSON.stringify(exportedSpec(spec,{planDir,specOut,repoRoot,theme}),null,2)+'\n');
  }
  return {status:'PASS',outPath,specOut,reasoning:reasoningPath,scene:built.scene,
    theme_decision:built.theme_decision,verification,warnings:validation.warnings,
    pptx_sha256:built.pptx_sha256,content_sha256:built.content_sha256};
}

module.exports={compilePlan,readPlan,sourcePaths};
