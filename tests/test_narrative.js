const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),os=require('os');
const {inspectNarrative}=require('../core/semantics/narrative'),{resolveTitle,wrap,measure}=require('../core/planner/title');
const font={cjk:'Noto Sans CJK SC',titleSize:28,bodySize:16};
const deck=()=>({title:'经营审阅',slides:[{type:'table',title:'收入仍差目标40万元',headers:['实际','目标'],rows:[[960,1000]]},{type:'table',title:'收入仍差目标40万元',headers:['实际','目标'],rows:[[960,1000]]}],narrative:{objective:'决定如何验证收入差距的原因',claims:[{id:'gap',text:'收入仍差目标40万元',kind:'FACT',evidence_ids:['revenue']}],evidence:[{id:'revenue',source_id:'synthetic-revenue',bindings:[{slide:1,pointer:'/rows/0'},{slide:2,pointer:'/rows/0'}]}],decisions:[],nodes:[{slide:1,role:'summary',question:'结果是什么？',claim_ids:['gap'],evidence_ids:['revenue'],decision_ids:[]},{slide:2,role:'detail',question:'具体差异是什么？',claim_ids:['gap'],evidence_ids:['revenue'],decision_ids:[],expansion_note:'展开原始实际与目标数据，保留精确数字',transition:'从摘要展开原始证据'}],edges:[{from:1,to:2,relation:'expands',explanation:'摘要之后展示可核对的明细'}]}});
test('summary and declared detail retain both pages and exact evidence fingerprints',()=>{
 const d=deck(),before=JSON.stringify(d),r=inspectNarrative(d);
 assert.equal(r.errors.length,0);assert.equal(r.redundancy.length,0);assert.equal(r.bindings.length,2);assert.equal(r.bindings[0].content_sha256,r.bindings[1].content_sha256);assert.equal(JSON.stringify(d),before);assert(r.review_required);
});
test('duplicate claims without expansion flag review, without deleting evidence',()=>{
 const d=deck();delete d.narrative.nodes[1].expansion_note;const r=inspectNarrative(d);assert(r.redundancy.length);assert.equal(d.slides.length,2);assert.equal(r.bindings.length,2);
});
test('missing required evidence, dangling claims, omitted pages and backwards edges fail',()=>{
 for(const mutate of [d=>d.narrative.evidence[0].bindings[0].pointer='/rows/9/0',d=>d.narrative.nodes[0].claim_ids=['unknown'],d=>d.narrative.claims[0].evidence_ids=[],d=>d.narrative.nodes.pop(),d=>d.narrative.edges[0]={from:2,to:1,relation:'expands',explanation:'invalid'}]) {
  const d=deck();mutate(d);assert.equal(inspectNarrative(d).status,'FAIL');
 }
});
test('appendix preserves evidence and owner/timing remain unknown',()=>{
 const d=deck();d.narrative.nodes[1].role='appendix';d.narrative.decisions=[{id:'review',question:'是否批准进一步验证？',claim_ids:['gap']}];d.narrative.nodes[0].decision_ids=['review'];const r=inspectNarrative(d);assert.equal(r.errors.length,0);assert(r.bindings.some(b=>b.disposition==='appendix'));assert(r.notes.some(s=>s.includes('owner/timing')));assert.equal(d.narrative.decisions[0].owner,undefined);
});
test('legacy input stays supported without claiming narrative review',()=>{
 const d=deck();delete d.narrative;const r=inspectNarrative(d);assert.equal(r.checks.NARRATIVE_COHERENCE,'NOT_RUN');assert.equal(d.slides.length,2);assert(r.redundancy.length);
});
test('title chooses readable one line beyond former92percent limit and records alternatives',()=>{
 const title='经营差距仍需按区域和渠道进一步核对';const rawWidth=measure(title,font.cjk,28).width;const width=rawWidth*24/28+.01;
 const r=resolveTitle({title},font,width);assert.equal(r.lines.length,1);assert(r.size<=24&&r.size>=22);assert(r.candidates.length>1);assert.equal(r.title,title);assert.equal(r.minimum_size,22);
});
test('balanced wraps keep number/unit atoms and original information',()=>{
 const title='转化率达到96%，仍比目标低1.2pp，下一阶段需要核对样本成熟度';
 const r=resolveTitle({title},font,9);assert.equal(r.lines.join(''),title);assert(r.size>=22);assert(!r.lines.some(l=>/^(%|％|pp)/.test(l)));assert(r.lines.some(l=>l.includes('96%')));assert(r.lines.some(l=>l.includes('1.2pp')));assert(r.dividerY>r.titleY+r.h);
 const narrow=wrap('结果为96%，样本待核对',font.cjk,28,2.2);assert(!narrow.some(l=>/^(%|％|pp)/.test(l)));
 const dated=wrap('统计窗口2026-09-01至2026-09-30',font.cjk,28,4);assert(dated.some(l=>l.includes('2026-09-01')));assert(dated.some(l=>l.includes('2026-09-30')));
});
test('native PPTX build records graph and refuses omitted evidence before writing',async()=>{
 const {buildDeck}=require('../core/renderer'),JSZip=require('jszip');const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gj-narrative-'));
 try {
  const d=deck(),out=path.join(dir,'deck.pptx');const result=await buildDeck(d,out);assert.equal(result.slides,2);const scene=JSON.parse(fs.readFileSync(out+'.scene.json'));assert.equal(scene.narrative.bindings.length,2);const z=await JSZip.loadAsync(fs.readFileSync(out));const notes=await z.file('ppt/notesSlides/notesSlide1.xml').async('string');assert(notes.includes('[narrative]'));
  const bad=deck();bad.narrative.evidence[0].bindings[0].pointer='/rows/9/0';const rejected=path.join(dir,'bad.pptx');await assert.rejects(()=>buildDeck(bad,rejected),/[Nn]arrative/);assert(!fs.existsSync(rejected));assert(!fs.existsSync(rejected+'.scene.json'));
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
