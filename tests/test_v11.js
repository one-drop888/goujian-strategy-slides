const assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),os=require('os'),{execFileSync}=require('child_process');
const {buildDeck}=require('../core/renderer'),{validateDeck}=require('../core/schema/validate');
const {resolveTitle,balancedWrap}=require('../core/planner/title'),{deduplicateSection}=require('../core/composition/scene');
const {loadProfile}=require('../core/style/profile-loader'),{resolveFonts}=require('../core/style/font-resolver');
const PptxGenJS=require('pptxgenjs'),{attachScene}=require('../core/renderer/scene-adapter'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),example=JSON.parse(fs.readFileSync(path.join(root,'skill/examples/multimodal-integration.json')));
const font={cjk:'Noto Sans CJK SC',titleSize:28,bodySize:18};
async function main(){
  // A: identity + role + common page context; a different number is retained.
  const a=deduplicateSection({type:'section',number:1,section:'01',title:'01 总体经营达成'});
  assert.equal(a.title,'总体经营达成');assert.equal(a.section,'');assert.equal(a.deduplication.length,2);
  assert.equal(deduplicateSection({type:'section',number:1,title:'02 另一个来源'}).title,'02 另一个来源');
  const embedded=[{id:'document',fit:'contain',provenance:[{kind:'image_text',text:'01',semantic_role:'section_number',source_region:{x:.02,y:.03,w:.05,h:.05},confidence:1,render_mode:'embedded'}]}];
  assert.equal(deduplicateSection({type:'image-insight',asset_ids:['document'],title:'01 总体经营达成'},embedded).title,'总体经营达成');
  embedded[0].provenance[0].confidence=.5;
  assert.equal(deduplicateSection({type:'image-insight',asset_ids:['document'],title:'01 总体经营达成'},embedded).title,'01 总体经营达成');
  // E: six KPI items and all nine table columns are accepted, seven KPI items rejected explicitly.
  assert.deepEqual(validateDeck(example),[]);
  const over=structuredClone(example);over.slides[1].items.push({label:'Seventh',value:7});assert.match(validateDeck(over).join('\n'),/capacity 6/);
  const missing=structuredClone(example);missing.assets[0].id='different';assert.match(validateDeck(missing).join('\n'),/Unknown asset|source_asset/);
  const pixelText=structuredClone(example);pixelText.assets[0].provenance[0].confidence=undefined;assert.match(validateDeck(pixelText).join('\n'),/confidence/);
  // G/H: no semantic rewrite; every original title character is retained.
  const title='Q4重点攻坚行动：九城收单、保客增换、库存去化、新车蓄势全面推进';
  const subtitle='六项重点行动分战区推进，覆盖收单窗口、专人专岗、库存清理与新品战役';
  const resolved=resolveTitle({title,subtitle},font,11.77);
  assert.equal(resolved.original,title);
  assert.equal(resolved.title,title);
  assert.equal(resolved.subtitle,subtitle);
  assert.equal(resolved.lines.join(''),title);
  assert(!resolved.strategy.includes('remove-redundant')&&!resolved.strategy.includes('title-subtitle'));
  assert(resolved.size>=font.titleSize*.92);
  assert(resolved.dividerY>=resolved.subtitleY+resolved.subtitleH+resolved.gap-1e-5);
  assert(resolved.bodyTop>resolveTitle({title:'经营复盘'},font,11.77).bodyTop);
  const explicit=resolveTitle({title,title_short:'Q4 六项行动先定顺序与责任人',subtitle},font,11.77);
  assert.equal(explicit.original,title);assert.equal(explicit.title,'Q4 六项行动先定顺序与责任人');
  assert.equal(explicit.subtitle,subtitle);assert.equal(explicit.strategy,'author-rewrite');
  const shortWithOriginal=resolveTitle({title,title_short:'Q4 六项行动'},font,11.77);
  assert.equal(shortWithOriginal.subtitle,title,'author rewrite keeps the original title as auditable subtitle');
  assert.throws(()=>resolveTitle({title:'W'.repeat(90)},font,11.77),/unbreakable|title_short/);
  const quote='“功能很多，但我没听明白跟我每天通勤、带家人有什么关系。”';
  const quoteLines=balancedWrap(quote,font.cjk,24,4.97);assert.equal(quoteLines.join(''),quote);assert(quoteLines.every(l=>l.length>5));
  assert(quoteLines.every(l=>!/^\s*[，。；：！？、）】》”’]/.test(l)));
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'构见 空格（Q4）&★-'));
  try {
    fs.mkdirSync(path.join(directory,'profiles'));fs.writeFileSync(path.join(directory,'profiles/yangwang.json'),JSON.stringify({extends:'executive-clean',id:'yangwang',font:{title_size:29}}));
    assert.equal(loadProfile('yangwang',root,new Set(),directory).font.title_size,29);
    const fonts=resolveFonts({latin:'Missing Goujian Font',cjk:'Missing Goujian CJK Font'});
    if(fonts.report.every(r=>r.status==='PROVEN'))assert(fonts.report.every(r=>r.substituted));
    // Unicode CLI input and output paths with assets relative to the spec, never the process CWD.
    fs.cpSync(path.join(root,'skill/examples/assets'),path.join(directory,'assets'),{recursive:true});
    const spec=path.join(directory,'中文 空格（Q4）&★.json'),output=path.join(directory,'中文 空格（Q4）&★.pptx');
    fs.writeFileSync(spec,JSON.stringify(example));
    const original=fs.readFileSync(spec);
    assert.throws(()=>execFileSync('node',[path.join(root,'skill/scripts/build_deck.js'),spec,spec],{stdio:'pipe'}));assert.deepEqual(fs.readFileSync(spec),original);
    const assetBytes=fs.readFileSync(path.join(directory,example.assets[0].path));
    await assert.rejects(buildDeck(example,path.join(directory,example.assets[0].path),{specDir:directory}),/must not overwrite input/);
    assert.deepEqual(fs.readFileSync(path.join(directory,example.assets[0].path)),assetBytes);
    const cli=execFileSync('node',[path.join(root,'skill/scripts/build_deck.js'),spec,output],{cwd:os.tmpdir(),timeout:120000,encoding:'utf8'});assert.match(cli,/VISUAL_QA=(NOT_RUN|UNAVAILABLE)/);
    const graph=JSON.parse(fs.readFileSync(output+'.scene.json'));
    const values=graph.slides[1].nodes.filter(n=>n.kind==='text').map(n=>n.text);
    assert(values.includes('12.8%'));assert.equal(graph.slides[2].nodes.filter(n=>n.kind==='table').length,1);
    // D: screenshot pixels remain embedded, explanation is a separately editable object.
    assert(graph.assets.some(a=>a.provenance.some(p=>p.kind==='image_text'&&p.render_mode==='embedded')));
    assert(graph.slides[5].nodes.some(n=>n.provenance.kind==='derived_insight'&&n.provenance.render_mode==='editable'));
    assert(graph.slides[0].nodes.find(n=>n.role==='claim').contrast.ratio>=4.5);
    fs.mkdirSync(path.join(root,'out/regression'),{recursive:true});
    fs.copyFileSync(output,path.join(root,'out/regression/multimodal.pptx'));fs.copyFileSync(output+'.scene.json',path.join(root,'out/regression/multimodal.pptx.scene.json'));
    // All image semantic routes build through four shared compositions, with no PPTX postprocessor.
    const types=['image-hero','image-insight','image-evidence','image-grid','image-gallery','image-comparison','image-background','image-text-split','document-evidence'];
    const slides=types.map(type=>({type,title:'证据与解释保持关联',asset_ids:type==='image-comparison'?['channel','interview']:type==='image-hero'||type==='image-background'?['source-background']:['interview'],insight:'证据提出假设，尚需验证。',annotations:[{text:'访谈原文',source_region:{x:.05,y:.28,w:.9,h:.26}}]}));
    await buildDeck({...example,slides},path.join(root,'out/regression/image-routes.pptx'),{specDir:path.join(root,'skill/examples')});
    // B: serialize the contained screenshot/table collision that old geometry QA deliberately ignores.
    const bad=new PptxGenJS();bad.layout='LAYOUT_WIDE';const page=bad.addSlide();
    const scene=attachScene(page,{type:'image-evidence'},1,{font:{bodySize:18,cjk:font.cjk}});
    page.addTable([['Metric','Value'],['Rate','14%']],{x:1,y:2,w:8,rowH:1,fontSize:18,fontFace:font.cjk,scene:{id:'table',role:'evidence'}});
    page.addImage({path:path.join(root,'skill/examples/assets/channel-evidence.png'),x:2,y:2.5,w:2,h:1,scene:{id:'screenshot',role:'evidence',provenance:{kind:'image_text',source_asset:'channel',source_region:{x:0,y:0,w:1,h:1},confidence:1,render_mode:'embedded'}}});
    const broken=path.join(root,'out/regression/occlusion.pptx');await bad.writeFile({fileName:broken});
    fs.writeFileSync(broken+'.scene.json',JSON.stringify({pptx_sha256:crypto.createHash('sha256').update(fs.readFileSync(broken)).digest('hex'),assets:[{id:'channel'}],slides:[scene]}));
  } finally {fs.rmSync(directory,{recursive:true,force:true});}
  console.log('PASS: V1.1 native asset routes, provenance, six KPI, long title, divider flow, font/profile and Unicode regressions');
}
main().catch(e=>{console.error(e);process.exitCode=2;});
