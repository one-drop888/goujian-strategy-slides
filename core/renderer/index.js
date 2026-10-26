const path=require('path');
const fs=require('fs');
const pptxgen=require('pptxgenjs');
const {loadProfile,profileChain}=require('../style/profile-loader');
const {resolveStyle}=require('../style/resolve-style');
const {createSlideRenderers}=require('./slides/basic');
const {normalizeChartXml}=require('./charts');
const {assertDeck,schemaErrors}=require('../schema/validate');
const {resolveSlide}=require('../composition/resolver');
const {resolveFonts}=require('../style/font-resolver');
const {attachScene}=require('./scene-adapter');
const {createAssetPipeline}=require('./assets');
const {deduplicateSection}=require('../composition/scene');
const {prepareDeckSemantics}=require('../semantics/deck');
const {inspectNarrative}=require('../semantics/narrative');
const {createEncoding,validateChartPlan}=require('./encoding');
const {publicThemeDecision}=require('../reasoning/theme-decision');
const {embedReasoningReport,serializeReasoningReport}=require('../reasoning/embed');
const {assertNotInput,assertDistinctOutputs}=require('../safety/paths');
const os=require('os'),crypto=require('crypto');
function sha256(buffer){return crypto.createHash('sha256').update(buffer).digest('hex');}
function planNotes(ordered) {
  return ordered.map(slide=>[
    `[reasoning:${slide.id}] ${slide.question}`,
    `claims: ${slide.claim_ids.join(', ')}`,
    `sources: ${slide.source_ids.join(', ')}`,
    `mode: ${slide.title_mode}${slide.appendix?' | appendix':''}`,
    `transition: ${slide.transition}`,
  ].join(' | '));
}
function resolvedThemeRecord(style,font) {
  const T=style.tokens;
  return {
    mode:T.mode,
    background:T.background,
    primary:T.accent,
    colors:{text:T.text,muted:T.muted,accent:T.accent,accent_soft:T.accentSoft,panel:T.surface,line:T.divider},
    typography:{latin:font.latin,cjk:font.cjk,title_size:style.font.titleSize,body_size:style.font.bodySize},
    contrast:{series_min:'3:1',text_min:'4.5:1'},
  };
}
function validatedReasoning(reasoning,spec,repoRoot) {
  if(!reasoning) return null;
  const {validatePlan,stableStringify,sha256:planHash}=require('../reasoning/validate-plan');
  if(!reasoning.plan||!reasoning.planDir) {
    throw new Error('Reasoning metadata must include the source plan and planDir for independent validation; a validated flag alone is not accepted');
  }
  const validation=validatePlan(reasoning.plan,{planDir:reasoning.planDir,repoRoot});
  if(!validation.valid) {
    const error=new Error(`Reasoning plan failed validation: ${validation.errors.join('; ')}`);
    error.name='PlanValidationError';error.errors=validation.errors;throw error;
  }
  const ordered=[...reasoning.plan.slides].sort((a,b)=>a.order-b.order);
  const expectedSpec={...reasoning.plan.deck,slides:ordered.map(slide=>slide.spec)};
  const expectedHash=planHash(stableStringify(expectedSpec)),actualHash=planHash(stableStringify(spec));
  if(actualHash!==expectedHash) throw new Error('Supplied spec does not match the validated reasoning plan');
  if(reasoning.spec_sha256&&reasoning.spec_sha256!==expectedHash) throw new Error('Supplied spec_sha256 does not match the validated reasoning plan');
  return {plan_sha256:validation.plan_sha256,spec_sha256:expectedHash,notes:planNotes(ordered)};
}

async function buildDeck(spec,outPath,options={}){
  assertDeck(spec);
  const repoRoot=options.repoRoot||path.resolve(__dirname,'../..');
  const specDir=options.specDir||repoRoot;
  const profileRef=options.themeDecision?.profile_path||options.profile||spec.profile||'executive-clean';
  const profileFiles=profileChain(profileRef,repoRoot,specDir);
  const inputPaths=[...(options.inputPaths||[]),...(options.specPath?[options.specPath]:[]),
    ...(spec.assets||[]).map(asset=>path.resolve(specDir,asset.path)),...profileFiles];
  const scenePath=outPath+'.scene.json';
  assertNotInput(outPath,'PPTX output',inputPaths);
  assertNotInput(scenePath,'Scene output',inputPaths);
  assertDistinctOutputs([{path:outPath,label:'PPTX output'},{path:scenePath,label:'Scene output'}]);
  const reasoning=validatedReasoning(options.reasoning,spec,repoRoot);
  const profile=loadProfile(profileRef,repoRoot,new Set(),specDir);
  const errors=schemaErrors('profile',profile);
  if(errors.length) throw new Error('Invalid profile: '+errors.join('; '));
  const style=resolveStyle(profile,spec);
  const fontResolution=resolveFonts({...style.font,preferred:spec.font?.preferred||profile.font.preferred,fallback_latin:spec.font?.fallback_latin||profile.font.fallback_latin,fallback_cjk:spec.font?.fallback_cjk||profile.font.fallback_cjk});
  style.font=fontResolution.font;
  const semantics=prepareDeckSemantics(spec,{style,repoRoot});
  const effectiveSpec=semantics.spec;
  const narrative=inspectNarrative(effectiveSpec,{plan:options.reasoning?.plan});
  if(narrative.errors.length)throw new Error('Narrative contract failed: '+narrative.errors.join('; '));
  const effectiveErrors=schemaErrors('deck',effectiveSpec);
  if(effectiveErrors.length) throw new Error('Effective semantic spec is invalid: '+effectiveErrors.join('; '));
  const effectiveInputs=[...(options.inputPaths||[]),...(options.specPath?[options.specPath]:[]),
    ...(effectiveSpec.assets||[]).map(asset=>path.resolve(specDir,asset.path)),...profileFiles];
  assertNotInput(outPath,'PPTX output',effectiveInputs);
  assertNotInput(scenePath,'Scene output',effectiveInputs);
  const encoding=createEncoding(effectiveSpec,style);
  style.encoding=encoding;
  const chartPlans=encoding.chartPlansForSpec();
  const encodingValidation=chartPlans.map(plan=>validateChartPlan(plan,{background:style.tokens.chart.background}));
  for(const [index,result] of encodingValidation.entries()) {
    if(result.status!=='PASS') throw new Error(`chart ${index+1} visual encoding failed: ${result.errors.join('; ')}`);
  }
  const themeDecision={
    ...(options.themeDecision?publicThemeDecision(options.themeDecision):{
      selected_profile:profile.id,
      source:options.profile?'explicit-user':(spec.profile?'spec-profile':'default'),
      mode:style.tokens.mode,requested_mode:'auto',
      rationale:'Legacy spec build without an Agent reasoning plan; theme selection is not plan-validated.',
      conflicts:[],
    }),
    selected_profile:profile.id,
    ...resolvedThemeRecord(style,fontResolution.font),
  };
  const tempDir=fs.mkdtempSync(path.join(os.tmpdir(),'goujian-assets-'));
  const assets=createAssetPipeline(spec.assets,options.specDir||repoRoot,tempDir,style.background);
  const pptx=new pptxgen();
  pptx.layout=style.canvas==='wide'?'LAYOUT_WIDE':'LAYOUT_4X3';
  pptx.author=spec.author||'Goujian Strategy Slides'; pptx.subject=spec.title||''; pptx.title=spec.title||''; pptx.company=spec.company||''; pptx.lang=spec.lang||'zh-CN';
  pptx.theme={headFontFace:style.font.latin,bodyFontFace:style.font.latin,lang:spec.lang||'zh-CN'};
  const scenes=[];let current;
  const nativeAddSlide=pptx.addSlide.bind(pptx);
  pptx.addSlide=(...args)=>{const slide=nativeAddSlide(...args);scenes.push(attachScene(slide,current,scenes.length+1,style));return slide;};
  const renderers={...createSlideRenderers(pptx,style,effectiveSpec),...require('./slides/multimodal').createMultimodalRenderers(pptx,style,effectiveSpec,assets)};
  const resolved=[];
  try {
  for(const raw of effectiveSpec.slides||[]){
    const {renderer,slide}=resolveSlide(deduplicateSection(raw,effectiveSpec.assets),repoRoot);current=slide;
    if(reasoning?.notes?.[resolved.length]) slide.__reasoning_notes=reasoning.notes[resolved.length];
    const narrativeNode=effectiveSpec.narrative?.nodes?.find(node=>node.slide===resolved.length+1);
    if(narrativeNode)slide.__reasoning_notes=[slide.__reasoning_notes,
      `[narrative] ${narrativeNode.question} | claims: ${(narrativeNode.claim_ids||[]).join(', ')} | evidence: ${(narrativeNode.evidence_ids||[]).join(', ')} | transition: ${narrativeNode.transition||''}`].filter(Boolean).join('\n');
    const fn=renderers[renderer]; if(!fn) throw new Error(`renderer not implemented: ${renderer} (semantic type ${raw.type})`);
    fn(slide);
    const scene=scenes.at(-1),ids=new Set(scene.nodes.map(n=>n.id));
    for(const n of scene.nodes) {
      if(n.role==='evidence'&&ids.has('claim'))scene.relationships.push({from:n.id,to:'claim',type:'supports'});
      if(n.role==='evidence'&&ids.has('source'))scene.relationships.push({from:'source',to:n.id,type:'source_of'});
    }
    scene.relationships.push(...(slide.relationships||[]));
    resolved.push({semantic:raw.type,composition:slide.composition,renderer});
  }
  fs.mkdirSync(path.dirname(outPath),{recursive:true});
  let buffer=await normalizeChartXml(await pptx.write({outputType:'nodebuffer'}),style,chartPlans,{strict:true});
  const content_sha256=sha256(buffer);
  let reasoningReport=null,report_sha256=null;
  if(options.reasoning?.reportFactory){
    if(!reasoning) throw new Error('Reasoning report embedding requires a validated source plan');
    reasoningReport=options.reasoning.reportFactory({content_sha256,scene:{slides:scenes},theme_decision:themeDecision,metric_semantics:semantics.report});
    buffer=await embedReasoningReport(buffer,reasoningReport);
    report_sha256=sha256(Buffer.from(serializeReasoningReport(reasoningReport)));
  }
  fs.writeFileSync(outPath,buffer);
  const pptx_sha256=sha256(fs.readFileSync(outPath));
  const reasoningState=reasoning?{
    status:'VALIDATED',plan_sha256:reasoning.plan_sha256,spec_sha256:reasoning.spec_sha256,
    report_sha256,embedded_part:reasoningReport?'docProps/goujian-reasoning.json':null,
  }:{status:'NOT_RUN',reason:'legacy spec build without an Agent-authored reasoning plan'};
  const graph={version:'1.3',pptx_sha256,content_sha256,
    content_sha256_scope:'pre_embed_zip_diagnostic_not_recomputable_from_final_pptx',
    theme_decision:themeDecision,reasoning:reasoningState,
    metric_semantics:semantics.report,narrative,
    visual_encoding:{series_palette:encoding.palette,plans:chartPlans.map(plan=>({kind:plan.kind,container:plan.container,
      slide_index:plan.slideIndex,palette_type:plan.palette_type,
      relation:plan.relation,category_colors:plan.category_colors,legacy_overflow:plan.legacy_overflow,
      series:plan.series,colors:plan.colors})),
      validation:encodingValidation.map((result,index)=>({chart:index+1,status:result.status,
        thresholds:{delta_e76:12,grayscale:8,contrast:3},warnings:result.warnings,contrast:result.contrast}))},
    fonts:fontResolution.report,declared_assets:(effectiveSpec.assets||[]).map(a=>a.id),assets:assets.used,slides:scenes};
  fs.writeFileSync(scenePath,JSON.stringify(graph,null,2)+'\n');
  return {outPath,profile:profile.id,slides:(effectiveSpec.slides||[]).length,resolved,scene:scenePath,
    theme_decision:themeDecision,reasoning:reasoningState,reasoning_report:reasoningReport,pptx_sha256,content_sha256,
    semantics:semantics.report,narrative,effective_spec:effectiveSpec};
  } finally {fs.rmSync(tempDir,{recursive:true,force:true});}
}
module.exports={buildDeck};
