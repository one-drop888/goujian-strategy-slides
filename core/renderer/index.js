const path=require('path');
const fs=require('fs');
const pptxgen=require('pptxgenjs');
const {loadProfile}=require('../style/profile-loader');
const {resolveStyle}=require('../style/resolve-style');
const {createSlideRenderers}=require('./slides/basic');
const {assertDeck,schemaErrors}=require('../schema/validate');
const {resolveSlide}=require('../composition/resolver');

async function buildDeck(spec,outPath,options={}){
  assertDeck(spec);
  const repoRoot=options.repoRoot||path.resolve(__dirname,'../..');
  const profile=loadProfile(options.profile||spec.profile||'executive-clean',repoRoot);
  const errors=schemaErrors('profile',profile);
  if(errors.length) throw new Error('Invalid profile: '+errors.join('; '));
  const style=resolveStyle(profile,spec);
  const pptx=new pptxgen();
  pptx.layout=style.canvas==='wide'?'LAYOUT_WIDE':'LAYOUT_4X3';
  pptx.author=spec.author||'Goujian Strategy Slides'; pptx.subject=spec.title||''; pptx.title=spec.title||''; pptx.company=spec.company||''; pptx.lang=spec.lang||'zh-CN';
  pptx.theme={headFontFace:style.font.latin,bodyFontFace:style.font.latin,lang:spec.lang||'zh-CN'};
  const renderers=createSlideRenderers(pptx,style,spec);
  const resolved=[];
  for(const raw of spec.slides||[]){
    const {renderer,slide}=resolveSlide(raw,repoRoot);
    const fn=renderers[renderer]; if(!fn) throw new Error(`renderer not implemented: ${renderer} (semantic type ${raw.type})`);
    fn(slide); resolved.push({semantic:raw.type,composition:slide.composition,renderer});
  }
  fs.mkdirSync(path.dirname(outPath),{recursive:true}); await pptx.writeFile({fileName:outPath});
  return {outPath,profile:profile.id,slides:(spec.slides||[]).length,resolved};
}
module.exports={buildDeck};
