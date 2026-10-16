// Synthetic source decks: editable enterprise evidence, rendered into reproducible screenshot fixtures.
const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process'),PptxGenJS=require('pptxgenjs');
const root=path.resolve(__dirname,'..'),out=path.join(root,'out/dogfood/sources'),assets=path.join(root,'skill/examples/assets');
fs.mkdirSync(out,{recursive:true});fs.mkdirSync(assets,{recursive:true});
function text(s,t,x,y,w,h,size=20,bold=false){s.addText(t,{x,y,w,h,fontFace:'Noto Sans CJK SC',fontSize:size,bold,margin:0,color:'202124',valign:'top'});}
async function main(){
  const specs=[
    {file:'经营 分析（Q4）&★',pages:[s=>{
      text(s,'渠道复盘 · 合成数据',.3,.3,6.2,.5,25,true);
      s.addTable([['战区','线索','成交率'],['华南','1,280','14.2%'],['华东','1,160','13.8%'],['华北','980','11.6%'],['西南','860','10.9%']],{x:.3,y:1.15,w:6.2,rowH:.53,fontFace:'Noto Sans CJK SC',fontSize:20,margin:.12,border:{pt:.6,color:'CBD5DF'},color:'202124'});
      text(s,'口径：同一季度；成交 / 有效线索',.3,4.05,6.2,.3,14);
    }]},
    {file:'调研 证据（访谈）&★',pages:[s=>{
      text(s,'客户访谈摘录 · 合成样本',.3,.3,6.2,.55,25,true);
      text(s,'“试驾后没人说明下一步，\n我就先比较了别的品牌。”',.4,1.35,6,1.1,25,true);
      text(s,'样本：24 位近期试驾客户\n方法：半结构化访谈\n限制：定性频次不能证明因果',.4,2.95,6,1.1,19);
    },s=>{
      text(s,'转化差异仍需验证 · 合成数据',.3,.3,6.2,.5,24,true);
      s.addChart('bar',[{name:'成交率',labels:['华南','华东','华北','西南'],values:[14.2,13.8,11.6,10.9]}],{x:.3,y:1.1,w:6.2,h:3.05,barDir:'bar',showValue:true,showLegend:false,chartColors:['176B87'],catAxisLabelFontFace:'Noto Sans CJK SC',catAxisLabelFontSize:16,valAxisLabelFontSize:14,valAxisMinVal:0,dataLabelFormatCode:'0.0"%"',showTitle:false,showBorder:false});
    }]}
  ];
  for(const src of specs){
    const pptx=new PptxGenJS();pptx.defineLayout({name:'SOURCE',width:6.8,height:4.5});pptx.layout='SOURCE';
    src.pages.forEach(fn=>fn(pptx.addSlide()));
    const file=path.join(out,src.file+'.pptx');await pptx.writeFile({fileName:file});
    const dir=path.join(out,src.file);
    const result=JSON.parse(execFileSync('python3',[path.join(root,'skill/scripts/render_deck.py'),file,dir,'--dpi','180'],{encoding:'utf8',timeout:180000}));
    if(result.status!=='PASS')throw Error('Source fixture render unavailable: '+JSON.stringify(result));
    result.pages.forEach((p,i)=>fs.copyFileSync(p,path.join(assets,src===specs[0]?'channel-evidence.png':i===0?'interview-evidence.png':'chart-evidence.png')));
  }
  console.log('PASS: two synthetic source PPTXs and three screenshot assets');
}
main().catch(e=>{console.error(e);process.exitCode=2;});
