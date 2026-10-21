// Reproducible round-2 dogfood: plan decks, theme variants, legacy long title and dark chart types.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),{execFileSync}=require('child_process');
const {compilePlan}=require('../core/reasoning/compile');
const {buildDeck}=require('../core/renderer');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'out/v12-control/dogfood-round2');
const decks=path.join(out,'decks'),variants=path.join(out,'theme-variants');
const longDir=path.join(out,'long-title'),darkDir=path.join(out,'dark-chart-types'),sources=path.join(out,'sources');
for(const dir of [decks,variants,longDir,darkDir,sources])fs.mkdirSync(dir,{recursive:true});
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const rel=file=>path.relative(root,file);
function render(pptx,dir) {
  const report=dir.replace(/\/$/,'')+'.render.json';
  const result=JSON.parse(execFileSync('python3',[path.join(root,'skill/scripts/render_deck.py'),pptx,dir,'--dpi','140','--json',report],{encoding:'utf8',timeout:240000}));
  if(result.status!=='PASS')throw new Error(`render failed for ${pptx}: ${result.status} ${result.reason||''}`);
  return {render_dir:rel(dir),render_report:rel(report),montage:rel(result.montage),pdf:rel(result.pdf),pages:result.pages.length};
}
function quality(pptx,spec,renderDir) {
  const report=pptx+'.qa.json';
  try {execFileSync('python3',[path.join(root,'skill/scripts/quality_gate.py'),pptx,'--spec',spec,'--out',report,'--render-dir',renderDir],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:240000});}
  catch(error) {if(!fs.existsSync(report))throw error;}
  const data=JSON.parse(fs.readFileSync(report,'utf8'));
  if(data.status==='FAIL')throw new Error(`quality gate FAIL for ${pptx}`);
  return {status:data.status,visual:data.VISUAL_QA,report:rel(report),spatial:data.checks.spatial.status,spec_status:data.checks.spec.status};
}
function artifacts(item) {
  const files=Object.entries(item).filter(([key,value])=>typeof value==='string'&&/\.(pptx|json|png|pdf)$/.test(value)&&fs.existsSync(path.join(root,value)));
  return Object.fromEntries(files.map(([key,value])=>[key,{path:value,sha256:sha(path.join(root,value))}]));
}
function inspectSources() {
  const src=path.join(root,'out/v12-control/dogfood-round1/sources');
  for(const name of ['channel-source.pptx','chart-source.pptx'])fs.copyFileSync(path.join(src,name),path.join(sources,name));
  const inspections=[];
  for(const name of ['channel-source','chart-source']) {
    const file=path.join(sources,name+'.pptx');
    const report=path.join(sources,name+'.inspect.json');
    const extracted=path.join(sources,name+'.assets');
    execFileSync('python3',[path.join(root,'skill/scripts/inspect_pptx.py'),file,report,extracted],{encoding:'utf8'});
    const data=JSON.parse(fs.readFileSync(report,'utf8'));
    inspections.push({source:name+'.pptx',sha256:sha(file),report:rel(report),assets:rel(extracted),
      slides:data.slides.map(slide=>({slide:slide.slide,shapes:slide.shapes.map(shape=>({id:shape.id,kind:shape.kind,asset_id:shape.asset_id||null,source_mapping:shape.source_mapping,rows:shape.rows||null,series:shape.series||null,text:shape.text||''}))}))});
  }
  fs.writeFileSync(path.join(out,'source-inspection.json'),JSON.stringify({generated_at:new Date().toISOString(),inspections},null,2)+'\n');
  return inspections;
}
function darkSpec() {
  const series=(name,labels,values)=>({name,labels,values});
  return {title:'V1.2 dark chart types',profile:'dark-executive',lang:'zh-CN',slides:[
    {type:'kpi-dashboard',title:'仪表盘：两条序列保留',items:[
      {label:'线索量',value:'12,480',delta:'+14%'},{label:'到店率',value:'31%',delta:'+3pp'},
      {label:'成交率',value:'12.8%',delta:'目标 14.0%',highlight:true}],
      dashboard:{unit:'指数',labels:['7月','8月','9月'],series:[
        {name:'线索指数',values:[100,117.4,135.7]},{name:'成交指数',values:[100,103.3,105.5]}]},source:'Synthetic fixture'},
    {type:'chart',chartType:'bar',title:'独立条形图',labels:['华南','华东','华北','西南'],
      series:[series('成交率',['华南','华东','华北','西南'],[14.2,13.8,11.6,10.9])],highlightIndex:0,unit:'%',source:'Synthetic fixture'},
    {type:'chart',chartType:'column',title:'独立柱状图',labels:['Q1','Q2','Q3'],
      series:[series('收入',['Q1','Q2','Q3'],[32,41,38])],unit:'百万元',source:'Synthetic fixture'},
    {type:'chart',chartType:'line',title:'独立折线图',labels:['7月','8月','9月'],
      series:[series('线索',['7月','8月','9月'],[100,117.4,135.7]),series('成交',['7月','8月','9月'],[100,103.3,105.5])],unit:'指数',period:'Q3',source:'Synthetic fixture'},
    {type:'chart',chartType:'area',title:'独立面积图',labels:['7月','8月','9月'],
      series:[series('线索',['7月','8月','9月'],[100,117.4,135.7]),series('成交',['7月','8月','9月'],[100,103.3,105.5])],unit:'指数',source:'Synthetic fixture'},
    {type:'chart',chartType:'pie',title:'独立饼图',labels:['华南','华东','华北','西南'],
      series:[series('份额',['华南','华东','华北','西南'],[32,28,22,18])],unit:'%',source:'Synthetic fixture'},
    {type:'chart',chartType:'doughnut',title:'独立环图',labels:['A','B','C'],
      series:[series('份额',['A','B','C'],[40,35,25])],unit:'%',source:'Synthetic fixture'},
    {type:'image-evidence',title:'组合面板图表与表格',panels:[
      {id:'panel-chart',kind:'chart',chartType:'bar',series:[series('成交率',['华南','华东','华北'],[14.2,13.8,11.6])],numberFormat:'0.0"%"'},
      {id:'panel-table',kind:'table',headers:['战区','线索','成交率'],rows:[['华南','1,280','14.2%'],['华东','1,160','13.8%'],['华北','980','11.6%']]},
      {id:'panel-note',kind:'text',text:'面板图表和表格继承主题令牌。'}],takeaway:'同一页覆盖图表和表格。',source:'Synthetic fixture'},
  ]};
}
async function main() {
  const inspections=inspectSources();
  const plans=[
    ['executive-incomplete-business',path.join(root,'skill/reasoning/fixtures/executive-incomplete-business/plan.json')],
    ['q4-six-actions',path.join(root,'skill/reasoning/fixtures/q4-six-actions/plan.json')],
    ['multimodal-consolidation',path.join(root,'skill/reasoning/fixtures/multimodal-consolidation/plan.json')],
  ];
  const built=[];
  for(const [name,plan] of plans) {
    const pptx=path.join(decks,name+'.pptx'),spec=path.join(decks,name+'.spec.json');
    const result=await compilePlan(plan,{out:pptx,specOut:spec,force:true});
    const renderInfo=render(pptx,path.join(decks,name+'-render'));
    const qa=quality(pptx,spec,renderInfo.render_dir);
    built.push({kind:'plan',name,pptx:rel(result.outPath),spec:rel(spec),reasoning:rel(result.reasoning),scene:rel(result.scene),
      theme:result.theme_decision,verification:result.verification.status,render:renderInfo,qa,hashes:artifacts({
        pptx:rel(result.outPath),spec:rel(spec),reasoning:rel(result.reasoning),scene:rel(result.scene),
        montage:renderInfo.montage,qa:qa.report})});
  }
  for(const [name,profile] of [['light',undefined],['brand-blue','../themes/brand-blue.profile.json'],['dark','dark-executive']]) {
    const pptx=path.join(variants,name+'.pptx'),spec=path.join(variants,name+'.spec.json');
    const result=await compilePlan(plans[1][1],{out:pptx,specOut:spec,profile,force:true});
    const renderInfo=render(pptx,path.join(variants,'theme-'+name));
    const qa=quality(pptx,spec,renderInfo.render_dir);
    built.push({kind:'theme-variant',name,pptx:rel(result.outPath),spec:rel(spec),reasoning:rel(result.reasoning),scene:rel(result.scene),
      theme:result.theme_decision,verification:result.verification.status,render:renderInfo,qa,hashes:artifacts({
        pptx:rel(result.outPath),spec:rel(spec),reasoning:rel(result.reasoning),scene:rel(result.scene),
        montage:renderInfo.montage,qa:qa.report})});
  }
  const longTemplate=path.join(root,'skill/examples/title-subtitle-layout.json');
  const longSpec=JSON.parse(fs.readFileSync(longTemplate,'utf8'));
  const longPptx=path.join(longDir,'long-title.pptx'),longSpecOut=path.join(longDir,'long-title.spec.json');
  const longBuilt=await buildDeck(longSpec,longPptx,{repoRoot:root,specDir:path.join(root,'skill/examples')});
  fs.writeFileSync(longSpecOut,JSON.stringify(longSpec,null,2)+'\n');
  const longRender=render(longPptx,path.join(longDir,'render'));
  const longQa=quality(longPptx,longSpecOut,longRender.render_dir);
  built.push({kind:'legacy-long-title',name:'long-title',pptx:rel(longPptx),spec:rel(longSpecOut),scene:rel(longBuilt.scene),
    reasoning_status:longBuilt.reasoning.status,render:longRender,qa:longQa,hashes:artifacts({pptx:rel(longPptx),spec:rel(longSpecOut),scene:rel(longBuilt.scene),montage:longRender.montage,qa:longQa.report})});
  const spec=darkSpec();
  const darkPptx=path.join(darkDir,'dark-chart-types.pptx'),darkSpecOut=path.join(darkDir,'dark-chart-types.spec.json');
  fs.writeFileSync(darkSpecOut,JSON.stringify(spec,null,2)+'\n');
  const darkBuilt=await buildDeck(spec,darkPptx,{repoRoot:root});
  const darkRender=render(darkPptx,path.join(darkDir,'render'));
  const darkQa=quality(darkPptx,darkSpecOut,darkRender.render_dir);
  built.push({kind:'dark-chart-types',name:'dark-chart-types',pptx:rel(darkPptx),spec:rel(darkSpecOut),scene:rel(darkBuilt.scene),
    reasoning_status:darkBuilt.reasoning.status,render:darkRender,qa:darkQa,hashes:artifacts({pptx:rel(darkPptx),spec:rel(darkSpecOut),scene:rel(darkBuilt.scene),montage:darkRender.montage,qa:darkQa.report})});
  const summary={generated_at:new Date().toISOString(),visual_review:'NOT_RUN',
    source_inspection:rel(path.join(out,'source-inspection.json')),
    source_hashes:inspections.map(item=>({source:item.source,sha256:item.sha256,report:item.report})),
    decks:built};
  fs.writeFileSync(path.join(out,'dogfood.json'),JSON.stringify(summary,null,2)+'\n');
  fs.writeFileSync(path.join(out,'dogfood.sha256'),[...built.map(item=>`${item.hashes.pptx.sha256}  ${item.pptx}`),
    ...inspections.map(item=>`${item.sha256}  ${rel(path.join(sources,item.source))}`)].join('\n')+'\n');
  console.log(`PASS: ${built.length} decks built, rendered and QA-checked; visual review NOT_RUN`);
  for(const item of built)console.log(`- ${item.kind} ${item.name}: ${item.qa.status} / ${item.qa.visual} / ${item.render.montage}`);
}
main().catch(error=>{console.error(error);process.exitCode=2;});
