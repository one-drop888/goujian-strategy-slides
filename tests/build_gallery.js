// One valid payload per composition, including those absent from the ten scenarios.
const fs=require('fs');
const {buildDeck}=require('../core/renderer');
const {resolveSlide}=require('../core/composition/resolver');
const path=require('path');
const root=path.resolve(__dirname,'..');
const fixtures=new Map();
const assets=[];
for(const name of fs.readdirSync(path.join(root,'skill/examples')).filter(n=>n.endsWith('.json')&&n!=='manifest.json')) {
 const example=JSON.parse(fs.readFileSync(path.join(root,'skill/examples',name)));
 assets.push(...(example.assets||[]).map(a=>({...a,path:path.resolve(root,'skill/examples',a.path)})));
 for(const s of example.slides) {
  const r=resolveSlide(s,root);if(!fixtures.has(r.slide.composition))fixtures.set(r.slide.composition,s);
 }
}
fixtures.set('section-divider',{type:'section',number:2,title:'Evidence before expansion',subtitle:'Gallery fixture / composition coverage'});
fixtures.set('timeline-horizontal',{type:'timeline',title:'Three milestones gate the pilot before broader deployment',items:[{time:'Week 1',title:'Baseline',note:'Measure quality and cost'},{time:'Week 3',title:'Pilot review',note:'Check evidence and failure cases'},{time:'Week 6',title:'Go / no-go',note:'Assign owner and next review'}]});
fixtures.set('pyramid-stack',{type:'pyramid',title:'Trust depends on a stable foundation of data and controls',items:[{title:'Decisions / 决策'},{title:'Evidence / 证据'},{title:'Controls / 控制'},{title:'Data / 数据'}]});
const comps=JSON.parse(fs.readFileSync(path.join(root,'skill/compositions/registry.json'))).compositions;
const slides=comps.map(c=>{const s=fixtures.get(c.id);if(!s)throw Error('Missing gallery fixture '+c.id);return {...s,composition:c.id,source:'Synthetic composition test'};});
const spec={title:'Composition gallery',lang:'en-US',profile:'executive-clean',slides,assets};
fs.mkdirSync(path.join(root,'out'),{recursive:true});fs.writeFileSync(path.join(root,'out/composition-gallery.json'),JSON.stringify(spec,null,2));
buildDeck(spec,path.join(root,'out/composition-gallery.pptx')).then(()=>console.log(`PASS: ${slides.length} composition fixtures built`)).catch(e=>{console.error(e);process.exitCode=2;});
