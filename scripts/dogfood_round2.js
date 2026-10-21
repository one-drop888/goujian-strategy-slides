// Reproducible round-2/3 dogfood: plans, theme variants, legacy long title, dark chart types and native source provenance.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),{execFileSync}=require('child_process');
const PptxGenJS=require('pptxgenjs');
const {compilePlan}=require('../core/reasoning/compile');
const {buildDeck}=require('../core/renderer');
const root=path.resolve(__dirname,'..');
const args=process.argv.slice(2),outRootIndex=args.indexOf('--out-root');
const out=path.resolve(root,outRootIndex>=0?args[outRootIndex+1]:'out/v12-control/dogfood-round2');
const decks=path.join(out,'decks'),variants=path.join(out,'theme-variants');
const longDir=path.join(out,'long-title'),darkDir=path.join(out,'dark-chart-types'),sources=path.join(out,'sources');
const assets=path.join(root,'skill/examples/assets');
for(const dir of [decks,variants,longDir,darkDir,sources])fs.mkdirSync(dir,{recursive:true});
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const rel=file=>path.relative(root,file);
const CHANNEL_HEADERS=['战区','线索','到店','试驾','成交率','库存','跟进','负责人','复核日'];
const CHANNEL_ROWS=[
  ['华南','1,280','34%','61%','14.2%','38天','90%','A','10/20'],
  ['华东','1,160','32%','59%','13.8%','39天','88%','B','10/20'],
  ['华北','980','29%','55%','11.6%','43天','83%','C','10/21'],
  ['西南','860','28%','54%','10.9%','46天','81%','D','10/21'],
];
const CHART_LABELS=['华南','华东','华北','西南'];
const CHART_VALUES=[14.2,13.8,11.6,10.9];
function text(slide,value,x,y,w,h,size=20,bold=false,objectName) {
  slide.addText(value,{x,y,w,h,fontFace:'Noto Sans CJK SC',fontSize:size,bold,margin:0,color:'202124',valign:'top',...(objectName?{objectName}:{})});
}
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
async function sourceDecks() {
  const table=new PptxGenJS();table.layout='LAYOUT_WIDE';
  const s1=table.addSlide();
  // Table first: pptxgenjs assigns table id 2 on slide 1, so a preceding shape would collide with it.
  s1.addTable([CHANNEL_HEADERS,...CHANNEL_ROWS],{x:.4,y:1.1,w:12.4,colW:[1.3,1.3,1.1,1.1,1.4,1.2,1.1,1.95,1.95],rowH:.5,fontFace:'Noto Sans CJK SC',fontSize:12,margin:.06,border:{pt:.6,color:'CBD5DF'},color:'202124',objectName:'Channel table 9 columns'});
  text(s1,'渠道表 · 合成源材料（9列）',.4,.3,8,.5,24,true,'Source title');
  text(s1,'原生9列表格 + 嵌入渠道截图；合成数据。报告期2026-Q3由合成简报定义；成交率分母/cohort/去重/跨期口径NOT_PROVIDED；线索量仅作背景，不构成成交率分母。',.4,4.0,7.7,2.6,12,false,'Channel note');
  s1.addImage({path:path.join(assets,'channel-evidence.png'),x:8.4,y:4.0,w:4.4,h:2.9,objectName:'Channel screenshot',altText:'合成渠道截图：华南/华东/华北/西南区域指标，仅作背景材料；未提供成交率分母口径。'});
  const tableFile=path.join(sources,'channel-source.pptx');
  await table.writeFile({fileName:tableFile});

  const chart=new PptxGenJS();chart.layout='LAYOUT_WIDE';
  const s2=chart.addSlide();
  text(s2,'成交率 · 合成源图表',.4,.3,8,.5,24,true,'Source title');
  s2.addChart('bar',[{name:'成交率',labels:CHART_LABELS,values:CHART_VALUES}],
    {x:.4,y:1.1,w:7.4,h:4.2,barDir:'bar',showValue:true,showLegend:false,chartColors:['176B87'],catAxisLabelFontFace:'Noto Sans CJK SC',catAxisLabelFontSize:16,valAxisLabelFontSize:14,valAxisMinVal:0,dataLabelFormatCode:'0.0"%"',showTitle:false,objectName:'Conversion rate chart',altText:'合成成交率条形图：华南14.2%，华东13.8%，华北11.6%，西南10.9%；分母口径未提供。'});
  s2.addImage({path:path.join(assets,'interview-evidence.png'),x:8.1,y:1.1,w:4.7,h:3.2,objectName:'Interview screenshot',altText:'合成访谈截图：24位试驾客户便利样本，不能代表总体，也未提供成交率分母口径。'});
  text(s2,'原生图表 + 嵌入访谈截图；成交率分母/cohort/去重/跨期口径NOT_PROVIDED；24位访谈为便利样本；报告期2026-Q3由合成简报定义。',.4,5.7,7.4,1.2,12,false,'Chart note');
  const chartFile=path.join(sources,'chart-source.pptx');
  await chart.writeFile({fileName:chartFile});

  const inspections=[];
  for(const name of ['channel-source','chart-source']) {
    const file=path.join(sources,name+'.pptx');
    const report=path.join(sources,name+'.inspect.json');
    const extracted=path.join(sources,name+'.assets');
    execFileSync('python3',[path.join(root,'skill/scripts/inspect_pptx.py'),file,report,extracted],{encoding:'utf8'});
    const data=JSON.parse(fs.readFileSync(report,'utf8'));
    data.source=rel(file);
    for(const asset of data.assets||[]) if(asset.path) asset.path=rel(path.resolve(root,asset.path));
    fs.writeFileSync(report,JSON.stringify(data,null,2)+'\n');
    inspections.push({source:name+'.pptx',path:rel(file),sha256:sha(file),report:rel(report),assets_dir:rel(extracted),
      slides:data.slides.map(slide=>({slide:slide.slide,shapes:slide.shapes.map(shape=>({id:shape.id,kind:shape.kind,rect:shape.rect,asset_id:shape.asset_id||null,
        source_mapping:shape.source_mapping,rows:shape.rows||null,series:shape.series||null,text:shape.text||''}))})),
      assets:(data.assets||[]).map(asset=>({id:asset.id,source_part:asset.source_part,sha256:asset.sha256,path:asset.path,source_mapping:asset.source_mapping})),
      limitations:data.limitations});
  }
  return inspections;
}
function verifyProvenance(inspections) {
  const multi=JSON.parse(fs.readFileSync(path.join(root,'skill/reasoning/fixtures/multimodal-consolidation/plan.json'),'utf8'));
  const byName=Object.fromEntries(inspections.map(item=>[item.source,item]));
  const table=byName['channel-source.pptx'],chart=byName['chart-source.pptx'];
  const tableShape=table.slides[0].shapes.find(shape=>shape.kind==='table');
  const chartShape=chart.slides[0].shapes.find(shape=>shape.kind==='chart');
  const appendix=multi.slides.find(slide=>slide.id==='mm-appendix-table').spec;
  const channel=multi.sources.find(source=>source.id==='s-channel');
  const interview=multi.sources.find(source=>source.id==='s-interview');
  const expectedRows=[appendix.headers,...appendix.rows];
  const ownerIndex=appendix.headers.indexOf('负责人'),reviewIndex=appendix.headers.indexOf('复核日');
  const chartValues=(chartShape?.series?.[0]?.values||[]).map(Number);
  const planValues=['sc-hn-conv','sc-hd-conv','sc-hb-conv','sc-xn-conv'].map(id=>channel.values.find(value=>value.id===id).value);
  const checks=[];const check=(name,ok,details)=>checks.push({name,status:ok?'PASS':'FAIL',details});
  check('native table has 9 columns',tableShape?.rows?.[0]?.length===9,tableShape?.rows?.[0]);
  check('native table preserves 4 data rows',tableShape?.rows?.length===5,tableShape?.rows?.length);
  check('native table matches plan appendix header plus 4 rows',JSON.stringify(tableShape?.rows)===JSON.stringify(expectedRows),{native:tableShape?.rows,plan:expectedRows});
  check('native table carries owner and review date',ownerIndex>=0&&reviewIndex>=0&&tableShape.rows.slice(1).every(row=>row[ownerIndex]&&row[reviewIndex]),{ownerIndex,reviewIndex});
  check('native chart carries 4 regional values',chartShape?.series?.[0]?.values?.length===4,chartShape?.series?.[0]);
  check('native chart values match plan source',JSON.stringify(chartValues)===JSON.stringify(planValues),{native:chartValues,plan:planValues});
  check('native chart labels match appendix rows',JSON.stringify(chartShape?.series?.[0]?.labels)===JSON.stringify(appendix.rows.map(row=>row[0])),chartShape?.series?.[0]?.labels);
  const channelAsset=table.assets.find(asset=>asset.sha256===channel.sha256);
  check('embedded channel screenshot matches plan source SHA',!!channelAsset,channelAsset||channel.sha256);
  const interviewAsset=chart.assets.find(asset=>asset.sha256===interview.sha256);
  check('embedded interview screenshot matches plan source SHA',!!interviewAsset,interviewAsset||interview.sha256);
  const shapeLocators=inspections.flatMap(item=>item.slides.flatMap(slide=>slide.shapes.map(shape=>({source:item,shape}))));
  check('all shape locators bind native file SHA',shapeLocators.every(({source,shape})=>shape.source_mapping?.pptx_sha256===source.sha256),shapeLocators.length);
  return {status:checks.every(item=>item.status==='PASS')?'PASS':'FAIL',checks,provenance:[
    {plan_source_ids:['s-channel'],native_source:table.path,sha256:table.sha256,report:table.report,
      slide_shape_locator:tableShape?.source_mapping,embedded_images:table.assets.map(asset=>({sha256:asset.sha256,source_part:asset.source_part,asset_id:asset.id})),preserved:{columns:9,rows:4,owner:true,review_date:true}},
    {plan_source_ids:['s-chart','s-interview'],native_source:chart.path,sha256:chart.sha256,report:chart.report,
      slide_shape_locator:chartShape?.source_mapping,embedded_images:chart.assets.map(asset=>({sha256:asset.sha256,source_part:asset.source_part,asset_id:asset.id})),preserved:{regions:4,values:chartValues}},
  ]};
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
  const inspections=await sourceDecks();
  const verification=verifyProvenance(inspections);
  fs.writeFileSync(path.join(out,'source-inspection.json'),JSON.stringify({generated_at:new Date().toISOString(),status:verification.status,inspections,checks:verification.checks,provenance:verification.provenance},null,2)+'\n');
  if(verification.status!=='PASS') throw new Error(`native source provenance FAIL: ${verification.checks.filter(item=>item.status==='FAIL').map(item=>item.name).join(', ')}`);
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
  const summary={generated_at:new Date().toISOString(),visual_review:'NOT_RUN',out_root:rel(out),
    source_inspection:rel(path.join(out,'source-inspection.json')),
    native_source_status:verification.status,
    native_source_checks:verification.checks,
    native_source_provenance:verification.provenance,
    source_hashes:inspections.map(item=>({source:item.source,path:item.path,sha256:item.sha256,report:item.report})),
    decks:built};
  const dogfoodFile=path.join(out,'dogfood.json');
  fs.writeFileSync(dogfoodFile,JSON.stringify(summary,null,2)+'\n');
  const manifest=new Map();
  for(const item of built) for(const artifact of Object.values(item.hashes)) manifest.set(artifact.path,artifact.sha256);
  for(const item of inspections) {
    manifest.set(item.path,item.sha256);
    manifest.set(item.report,sha(path.join(root,item.report)));
  }
  manifest.set(rel(path.join(out,'source-inspection.json')),sha(path.join(out,'source-inspection.json')));
  manifest.set(rel(dogfoodFile),sha(dogfoodFile));
  const lines=[...manifest.entries()].sort(([left],[right])=>left.localeCompare(right)).map(([file,digest])=>`${digest}  ${file}`);
  fs.writeFileSync(path.join(out,'dogfood.sha256'),lines.join('\n')+'\n');
  console.log(`PASS: ${built.length} decks built, rendered and QA-checked; source inspections=${inspections.length}; native provenance=${verification.status}; visual review NOT_RUN`);
  for(const item of built)console.log(`- ${item.kind} ${item.name}: ${item.qa.status} / ${item.qa.visual} / ${item.render.montage}`);
}
main().catch(error=>{console.error(error);process.exitCode=2;});
