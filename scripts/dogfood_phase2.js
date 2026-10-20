// Reproducible phase-2 dogfood: synthetic sources, reasoning plans, theme variants, renders.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),{execFileSync}=require('child_process');
const PptxGenJS=require('pptxgenjs');
const {compilePlan}=require('../core/reasoning/compile');
const {buildDeck}=require('../core/renderer');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'out/v12-control/dogfood-round1');
const sources=path.join(out,'sources'),decks=path.join(out,'decks'),variants=path.join(out,'theme-variants');
const assets=path.join(root,'skill/examples/assets');
for(const dir of [sources,decks,variants]) fs.mkdirSync(dir,{recursive:true});
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
function text(slide,value,x,y,w,h,size=20,bold=false) {
  slide.addText(value,{x,y,w,h,fontFace:'Noto Sans CJK SC',fontSize:size,bold,margin:0,color:'202124',valign:'top'});
}
async function sourceDecks() {
  const table=new PptxGenJS();table.layout='LAYOUT_WIDE';
  const s1=table.addSlide();
  text(s1,'渠道表 · 合成源材料',.4,.35,8,.5,24,true);
  s1.addTable([['战区','线索','到店','试驾','成交率','库存','跟进'],
    ['华南','1,280','34%','61%','14.2%','38天','90%'],
    ['华东','1,160','32%','59%','13.8%','39天','88%'],
    ['华北','980','29%','55%','11.6%','43天','83%'],
    ['西南','860','28%','54%','10.9%','46天','81%']],{x:.4,y:1.1,w:7.4,rowH:.55,fontFace:'Noto Sans CJK SC',fontSize:16,margin:.08,border:{pt:.6,color:'CBD5DF'},color:'202124'});
  s1.addImage({path:path.join(assets,'channel-evidence.png'),x:8.1,y:1.1,w:4.7,h:3.2});
  text(s1,'原生表格 + 截图 + 原生文字；合成数据。',.4,4.8,11,0.4,14);
  const tableFile=path.join(sources,'channel-source.pptx');
  await table.writeFile({fileName:tableFile});

  const chart=new PptxGenJS();chart.layout='LAYOUT_WIDE';
  const s2=chart.addSlide();
  text(s2,'成交率 · 合成源图表',.4,.35,8,.5,24,true);
  s2.addChart('bar',[{name:'成交率',labels:['华南','华东','华北','西南'],values:[14.2,13.8,11.6,10.9]}],
    {x:.4,y:1.1,w:7.4,h:3.8,barDir:'bar',showValue:true,showLegend:false,chartColors:['176B87'],catAxisLabelFontFace:'Noto Sans CJK SC',catAxisLabelFontSize:16,valAxisLabelFontSize:14,valAxisMinVal:0,dataLabelFormatCode:'0.0"%"',showTitle:false});
  s2.addImage({path:path.join(assets,'interview-evidence.png'),x:8.1,y:1.1,w:4.7,h:3.2});
  text(s2,'原生图表 + 访谈截图 + 原生文字；定性限制随证据保留。',.4,5.2,11,0.4,14);
  const chartFile=path.join(sources,'chart-source.pptx');
  await chart.writeFile({fileName:chartFile});

  const inspections=[];
  for(const file of [tableFile,chartFile]) {
    const report=path.join(sources,path.basename(file,'.pptx')+'.inspect.json');
    const extracted=path.join(sources,path.basename(file,'.pptx')+'.assets');
    execFileSync('python3',[path.join(root,'skill/scripts/inspect_pptx.py'),file,report,extracted],{encoding:'utf8'});
    const data=JSON.parse(fs.readFileSync(report,'utf8'));
    inspections.push({source:path.basename(file),sha256:data.source_sha256,slides:data.slides.map(slide=>({
      slide:slide.slide,
      shapes:slide.shapes.map(shape=>({id:shape.id,kind:shape.kind,asset_id:shape.asset_id||null,
        source_mapping:shape.source_mapping,rows:shape.rows||null,series:shape.series||null,text:shape.text||''})),
    })),report:path.relative(root,report)});
  }
  fs.writeFileSync(path.join(out,'source-inspection.json'),JSON.stringify({generated_at:new Date().toISOString(),inspections},null,2)+'\n');
  return inspections;
}
function render(pptx,name) {
  const dir=path.join(path.dirname(pptx),name);
  const report=path.join(path.dirname(pptx),name+'.render.json');
  const result=JSON.parse(execFileSync('python3',[path.join(root,'skill/scripts/render_deck.py'),pptx,dir,'--dpi','140','--json',report],{encoding:'utf8',timeout:240000}));
  if(result.status!=='PASS') throw new Error(`render failed for ${pptx}: ${result.status} ${result.reason||''}`);
  return {render_dir:path.relative(root,dir),montage:path.relative(root,result.montage),pages:result.pages.length};
}
async function main() {
  const inspections=await sourceDecks();
  const plans=[
    ['executive-incomplete-business',path.join(root,'skill/reasoning/fixtures/executive-incomplete-business/plan.json')],
    ['q4-six-actions',path.join(root,'skill/reasoning/fixtures/q4-six-actions/plan.json')],
    ['multimodal-consolidation',path.join(root,'skill/reasoning/fixtures/multimodal-consolidation/plan.json')],
  ];
  const built=[];
  for(const [name,plan] of plans) {
    const result=await compilePlan(plan,{out:path.join(decks,name+'.pptx'),force:true});
    built.push({kind:'plan',name,pptx:path.relative(root,result.outPath),reasoning:path.relative(root,result.reasoning),
      theme:result.theme_decision,render:render(result.outPath,name)});
  }
  for(const [name,profile] of [['light',undefined],['brand-blue','../themes/brand-blue.profile.json'],['dark','dark-executive']]) {
    const result=await compilePlan(plans[1][1],{out:path.join(variants,name+'.pptx'),profile,force:true});
    built.push({kind:'theme-variant',name,pptx:path.relative(root,result.outPath),reasoning:path.relative(root,result.reasoning),
      theme:result.theme_decision,render:render(result.outPath,'theme-'+name)});
  }
  const longSpec=JSON.parse(fs.readFileSync(path.join(root,'skill/examples/title-subtitle-layout.json'),'utf8'));
  const longPath=path.join(out,'long-title.pptx');
  const longBuilt=await buildDeck(longSpec,longPath,{repoRoot:root,specDir:path.join(root,'skill/examples')});
  built.push({kind:'legacy-long-title',pptx:path.relative(root,longPath),scene:path.relative(root,longBuilt.scene),
    reasoning_status:longBuilt.reasoning.status,render:render(longPath,'long-title')});
  const summary={generated_at:new Date().toISOString(),visual_review:'NOT_RUN',source_inspection:path.relative(root,path.join(out,'source-inspection.json')),
    source_hashes:inspections.map(item=>({source:item.source,sha256:item.sha256})),decks:built};
  fs.writeFileSync(path.join(out,'dogfood.json'),JSON.stringify(summary,null,2)+'\n');
  console.log(`PASS: ${built.length} decks built and rendered; source inspections=${inspections.length}; visual review NOT_RUN`);
  for(const item of built) console.log(`- ${item.kind} ${item.name||''}: ${item.pptx} -> ${item.render.montage}`);
}
main().catch(error=>{console.error(error);process.exitCode=2;});
