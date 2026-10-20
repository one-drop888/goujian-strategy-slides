const path=require('path');
const fs=require('fs');
const pptxgen=require('pptxgenjs');
const {loadProfile}=require('../style/profile-loader');
const {resolveStyle}=require('../style/resolve-style');
const {createSlideRenderers}=require('./slides/basic');
const {normalizeChartXml}=require('./charts');
const {assertDeck,schemaErrors}=require('../schema/validate');
const {resolveSlide}=require('../composition/resolver');
const {resolveFonts}=require('../style/font-resolver');
const {attachScene}=require('./scene-adapter');
const {createAssetPipeline}=require('./assets');
const {deduplicateSection}=require('../composition/scene');
const {publicThemeDecision}=require('../reasoning/theme-decision');
const {embedReasoningReport,serializeReasoningReport}=require('../reasoning/embed');
const os=require('os'),crypto=require('crypto');
function sha256(buffer){return crypto.createHash('sha256').update(buffer).digest('hex');}

async function buildDeck(spec,outPath,options={}){
  assertDeck(spec);
  if(options.reasoning&&(options.reasoning.validated!==true||!options.reasoning.plan_sha256)) {
    throw new Error('Reasoning metadata must come from a validated reasoning-plan compile');
  }
  const repoRoot=options.repoRoot||path.resolve(__dirname,'../..');
  if((spec.assets||[]).some(a=>path.resolve(options.specDir||repoRoot,a.path)===path.resolve(outPath)))throw Error('PPTX output must differ from every source asset');
  const profileRef=options.themeDecision?.profile_path||options.profile||spec.profile||'executive-clean';
  const profile=loadProfile(profileRef,repoRoot,new Set(),options.specDir);
  const errors=schemaErrors('profile',profile);
  if(errors.length) throw new Error('Invalid profile: '+errors.join('; '));
  const style=resolveStyle(profile,spec);
  const themeDecision=options.themeDecision?publicThemeDecision(options.themeDecision):{
    selected_profile:profile.id,
    source:options.profile?'explicit-user':(spec.profile?'spec-profile':'default'),
    mode:style.tokens.mode,requested_mode:'auto',
    rationale:'Legacy spec build without an Agent reasoning plan; theme selection is not plan-validated.',
    conflicts:[],
  };
  const fontResolution=resolveFonts({...style.font,preferred:spec.font?.preferred||profile.font.preferred,fallback_latin:spec.font?.fallback_latin||profile.font.fallback_latin,fallback_cjk:spec.font?.fallback_cjk||profile.font.fallback_cjk});
  style.font=fontResolution.font;
  const tempDir=fs.mkdtempSync(path.join(os.tmpdir(),'goujian-assets-'));
  const assets=createAssetPipeline(spec.assets,options.specDir||repoRoot,tempDir,style.background);
  const pptx=new pptxgen();
  pptx.layout=style.canvas==='wide'?'LAYOUT_WIDE':'LAYOUT_4X3';
  pptx.author=spec.author||'Goujian Strategy Slides'; pptx.subject=spec.title||''; pptx.title=spec.title||''; pptx.company=spec.company||''; pptx.lang=spec.lang||'zh-CN';
  pptx.theme={headFontFace:style.font.latin,bodyFontFace:style.font.latin,lang:spec.lang||'zh-CN'};
  const scenes=[];let current;
  const nativeAddSlide=pptx.addSlide.bind(pptx);
  pptx.addSlide=(...args)=>{const slide=nativeAddSlide(...args);scenes.push(attachScene(slide,current,scenes.length+1,style));return slide;};
  const renderers={...createSlideRenderers(pptx,style,spec),...require('./slides/multimodal').createMultimodalRenderers(pptx,style,spec,assets)};
  const resolved=[];
  try {
  for(const raw of spec.slides||[]){
    const {renderer,slide}=resolveSlide(deduplicateSection(raw,spec.assets),repoRoot);current=slide;
    if(options.reasoning?.notes?.[resolved.length]) slide.__reasoning_notes=options.reasoning.notes[resolved.length];
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
  let buffer=await normalizeChartXml(await pptx.write({outputType:'nodebuffer'}),style);
  const content_sha256=sha256(buffer);
  let reasoningReport=null,report_sha256=null;
  if(options.reasoning?.reportFactory){
    reasoningReport=options.reasoning.reportFactory({content_sha256,scene:{slides:scenes},theme_decision:themeDecision});
    buffer=await embedReasoningReport(buffer,reasoningReport);
    report_sha256=sha256(Buffer.from(serializeReasoningReport(reasoningReport)));
  }
  fs.writeFileSync(outPath,buffer);
  const pptx_sha256=sha256(fs.readFileSync(outPath));
  const reasoning=options.reasoning?{
    status:'VALIDATED',plan_sha256:options.reasoning.plan_sha256,
    report_sha256,embedded_part:reasoningReport?'docProps/goujian-reasoning.json':null,
  }:{status:'NOT_RUN',reason:'legacy spec build without an Agent-authored reasoning plan'};
  const graph={version:'1.2',pptx_sha256,content_sha256,theme_decision:themeDecision,reasoning,
    fonts:fontResolution.report,declared_assets:(spec.assets||[]).map(a=>a.id),assets:assets.used,slides:scenes};
  fs.writeFileSync(outPath+'.scene.json',JSON.stringify(graph,null,2)+'\n');
  return {outPath,profile:profile.id,slides:(spec.slides||[]).length,resolved,scene:outPath+'.scene.json',
    theme_decision:themeDecision,reasoning,reasoning_report:reasoningReport,pptx_sha256,content_sha256};
  } finally {fs.rmSync(tempDir,{recursive:true,force:true});}
}
module.exports={buildDeck};
