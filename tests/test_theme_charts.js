const assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),JSZip=require('jszip'),{execFileSync}=require('child_process');
const {buildDeck}=require('../core/renderer');
const {resolveStyle,contrastRatio,deriveTokens}=require('../core/style/resolve-style');
const {createChartHelper,normalizeChartXml}=require('../core/renderer/charts');
const {loadProfile}=require('../core/style/profile-loader');
const root=path.resolve(__dirname,'..');
function assertXml(text){
  execFileSync('python3',['-c','import sys,xml.etree.ElementTree as ET;ET.fromstring(sys.stdin.read())'],{input:text});
}

const series=(name,labels,values)=>({name,labels,values});
const specFor=(profile)=>({
  title:'V1.2 theme chart regression',profile,lang:'zh-CN',
  slides:[
    {type:'kpi-dashboard',title:'仪表盘：两条序列保留',items:[
      {label:'线索量',value:'12,480',delta:'+14%'},{label:'到店率',value:'31%',delta:'+3pp'},
      {label:'成交率',value:'12.8%',delta:'目标 14.0%',highlight:true}],
      dashboard:{unit:'指数',labels:['7月','8月','9月'],series:[
        {name:'线索指数',values:[100,117.4,135.7]},{name:'成交指数',values:[100,103.3,105.5]}]},
      source:'Synthetic fixture'},
    {type:'chart',chartType:'bar',title:'独立条形图',labels:['华南','华东','华北','西南'],
      series:[series('成交率',['华南','华东','华北','西南'],[14.2,13.8,11.6,10.9])],highlightIndex:0,unit:'%',source:'Synthetic fixture'},
    {type:'chart',chartType:'column',title:'独立柱状图',labels:['Q1','Q2','Q3'],
      series:[series('收入',['Q1','Q2','Q3'],[32,41,38])],unit:'百万元',source:'Synthetic fixture'},
    {type:'chart',chartType:'line',title:'独立折线图',labels:['7月','8月','9月'],
      series:[series('线索',['7月','8月','9月'],[100,117.4,135.7]),series('成交',['7月','8月','9月'],[100,103.3,105.5])],
      unit:'指数',period:'Q3',source:'Synthetic fixture'},
    {type:'chart',chartType:'area',title:'独立面积图',labels:['7月','8月','9月'],
      series:[series('线索',['7月','8月','9月'],[100,117.4,135.7]),series('成交',['7月','8月','9月'],[100,103.3,105.5])],
      unit:'指数',source:'Synthetic fixture'},
    {type:'chart',chartType:'pie',title:'独立饼图',labels:['华南','华东','华北','西南'],
      series:[series('份额',['华南','华东','华北','西南'],[32,28,22,18])],unit:'%',source:'Synthetic fixture'},
    {type:'chart',chartType:'doughnut',title:'独立环图',labels:['A','B','C'],
      series:[series('份额',['A','B','C'],[40,35,25])],unit:'%',source:'Synthetic fixture'},
    {type:'image-evidence',title:'组合面板图表与表格',panels:[
      {id:'panel-chart',kind:'chart',chartType:'bar',series:[series('成交率',['华南','华东','华北'],[14.2,13.8,11.6])],numberFormat:'0.0"%"'},
      {id:'panel-table',kind:'table',headers:['战区','线索','成交率'],rows:[['华南','1,280','14.2%'],['华东','1,160','13.8%'],['华北','980','11.6%']]},
      {id:'panel-note',kind:'text',text:'面板图表和表格继承主题令牌。'}],
      takeaway:'同一页覆盖图表和表格。',source:'Synthetic fixture'},
  ],
});

function blocks(xml,tag){return [...xml.matchAll(new RegExp(`<c:${tag}[ >][\\s\\S]*?</c:${tag}>`,'g'))].map(match=>match[0]);}
function block(xml,tag){return blocks(xml,tag)[0]||'';}
function numbers(xml,tag){
  const values=[];
  for(const inner of blocks(xml,tag))
    for(const match of inner.matchAll(/<c:v>([^<]*)<\/c:v>/g)){const n=Number(match[1]);if(Number.isFinite(n))values.push(n);}
  return values;
}
function categories(xml){
  const values=[];
  for(const match of block(xml,'cat').matchAll(/<c:v>([^<]*)<\/c:v>/g))values.push(match[1]);
  return values;
}
async function chartFiles(file){
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  const names=Object.keys(zip.files).filter(name=>/^ppt\/charts\/chart\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/(\d+)/)[1])-Number(b.match(/(\d+)/)[1]));
  return Promise.all(names.map(async name=>({name,xml:await zip.file(name).async('string')})));
}
async function slideXml(file,index){
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  return zip.file(`ppt/slides/slide${index}.xml`).async('string');
}

async function main(){
  // P0 regressions: bounded deterministic palettes and best black/white contrast choice.
  const mono=deriveTokens({text:'000000',muted:'000000',accent:'000000'},'FFFFFF',{});
  assert.equal(mono.chart.palette.length,4);
  assert(mono.chart.palette.every(color=>contrastRatio(color,'FFFFFF')>=3));
  const inverse=deriveTokens({text:'FFFFFF',muted:'FFFFFF',accent:'FFFFFF'},'000000',{});
  assert.equal(inverse.chart.palette.length,4);
  assert(inverse.chart.palette.every(color=>contrastRatio(color,'000000')>=3));
  execFileSync(process.execPath,['-e',`const {deriveTokens}=require(${JSON.stringify(path.join(root,'core/style/resolve-style'))});deriveTokens({text:'000000',muted:'000000',accent:'000000'},'FFFFFF',{});deriveTokens({text:'FFFFFF',muted:'FFFFFF',accent:'FFFFFF'},'000000',{});`],{cwd:root,timeout:5000});
  const mid=deriveTokens({text:'888888',accent:'888888'},'808080',{});
  assert(contrastRatio(mid.text,'808080')>=4.5,`midgray text contrast ${contrastRatio(mid.text,'808080')}`);
  assert(contrastRatio(mid.accent,'808080')>=3);

  // The chart postprocessor touches only the pie/doughnut global label block.
  const sampleChart='<?xml version="1.0" encoding="UTF-8"?><c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><c:chart><c:title><a:p><a:r><a:rPr><a:latin typeface="Arial"/></a:rPr></a:r></a:p></c:title><c:plotArea><c:pieChart><c:ser><c:spPr><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:ln><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln></c:spPr><c:cat><c:strRef><c:strCache><c:pt idx="0"><c:v>A</c:v></c:pt></c:strCache></c:strRef></c:cat><c:val><c:numRef><c:numCache><c:pt idx="0"><c:v>40</c:v></c:pt></c:numCache></c:numRef></c:val></c:ser><c:dLbls><c:dLbl><c:idx val="0"/><c:txPr><a:p><a:pPr><a:defRPr><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:latin typeface="Arial"/></a:defRPr></a:pPr></a:p></c:txPr></c:dLbl><c:txPr><a:p><a:pPr><a:defRPr><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:latin typeface="Arial"/></a:defRPr></a:pPr></a:p></c:txPr></c:dLbls></c:pieChart></c:plotArea></c:chart></c:chartSpace>';
  const sampleZip=new JSZip();sampleZip.file('ppt/charts/chart1.xml',sampleChart);
  const normalized=await normalizeChartXml(await sampleZip.generateAsync({type:'nodebuffer'}),{tokens:{chart:{dataLabel:'F9FAFB'}},font:{latin:'A&B Serif'}});
  const normalizedXml=await (await JSZip.loadAsync(normalized)).file('ppt/charts/chart1.xml').async('string');
  assertXml(normalizedXml);
  assert.equal((normalizedXml.match(/srgbClr val="000000"/g)||[]).length,3,'explicit series fill, border and point label stay black');
  assert.equal((normalizedXml.match(/typeface="Arial"/g)||[]).length,2,'per-point label and title keep their explicit font');
  assert(normalizedXml.includes('typeface="A&amp;B Serif"'),'global label font is XML-escaped');
  assert(normalizedXml.includes('<c:v>40</c:v>'),'chart data cache is unchanged');

  const profiles=['executive-clean','dark-executive'];
  const expectedCharts=[
    {cats:['7月','8月','9月'],nums:[100,117.4,135.7,100,103.3,105.5]},
    {cats:['华南','华东','华北','西南'],nums:[14.2,13.8,11.6,10.9]},
    {cats:['Q1','Q2','Q3'],nums:[32,41,38]},
    {cats:['7月','8月','9月'],nums:[100,117.4,135.7,100,103.3,105.5]},
    {cats:['7月','8月','9月'],nums:[100,117.4,135.7,100,103.3,105.5]},
    {cats:['华南','华东','华北','西南'],nums:[32,28,22,18]},
    {cats:['A','B','C'],nums:[40,35,25]},
    {cats:['华南','华东','华北'],nums:[14.2,13.8,11.6]},
  ];
  for(const profile of profiles){
    const style=resolveStyle(loadProfile(profile,root));
    const T=style.tokens;
    assert.equal(T.mode,profile==='dark-executive'?'dark':'light');
    assert.equal(T.chart.palette.length,4);
    assert.equal(new Set(T.chart.palette).size,4);
    for(const color of T.chart.palette)assert(contrastRatio(color,T.chart.background)>=3,`${profile} palette ${color}`);
    assert(contrastRatio(T.chart.labels,T.chart.background)>=4.5);
    assert(contrastRatio(T.chart.dataLabel,T.chart.background)>=4.5);
    assert(contrastRatio(T.table.bodyText,T.table.bodyFill)>=4.5);
    assert(contrastRatio(T.table.headerText,T.table.headerFill)>=4.5);
    for(const status of Object.values(T.status))assert(contrastRatio(status,T.background)>=4.5);
    assert.equal(style.colors.text,loadProfile(profile,root).colors.text);
    assert.equal(style.colors.accent,loadProfile(profile,root).colors.accent);
    const helper=createChartHelper(style);
    assert.equal(helper.options({showTitle:true}).titleColor,T.chart.title);
    assert.equal(helper.options().chartArea.fill.color,T.chart.background);
    assert.equal(helper.options().catAxisLabelColor,T.chart.labels);

    const file=path.join(root,'out/regression',`theme-${profile}.pptx`);
    await buildDeck(specFor(profile),file);
    const charts=await chartFiles(file);
    assert.equal(charts.length,expectedCharts.length);
    for(const [i,chart] of charts.entries()){
      const expected=expectedCharts[i];
      assert.deepEqual(categories(chart.xml),expected.cats,`${profile} chart${i+1} categories`);
      assert.deepEqual(numbers(chart.xml,'val').sort((a,b)=>a-b),expected.nums.slice().sort((a,b)=>a-b),`${profile} chart${i+1} values`);
      const colors=new Set([...chart.xml.matchAll(/srgbClr val="([0-9A-Fa-f]{6})"/g)].map(m=>m[1].toUpperCase()));
      assert(colors.has(T.chart.background),`${profile} chart${i+1} background`);
      assert(colors.has(T.chart.palette[0]),`${profile} chart${i+1} palette`);
      const catAxis=block(chart.xml,'catAx'),valAxis=block(chart.xml,'valAx');
      if(catAxis)assert(catAxis.includes(T.chart.labels),`${profile} chart${i+1} category labels`);
      if(valAxis)assert(valAxis.includes(T.chart.labels),`${profile} chart${i+1} value labels`);
      const dataLabels=block(chart.xml,'dLbls');
      if(dataLabels) {
        assert(dataLabels.includes(T.chart.dataLabel),`${profile} chart${i+1} data labels`);
        const labelColors=[...dataLabels.matchAll(/<a:srgbClr val="([0-9A-Fa-f]{6})"\/>/g)].map(m=>m[1].toUpperCase());
        assert(labelColors.every(color=>color===T.chart.dataLabel),`${profile} chart${i+1} label paint stays tokenized`);
      }
      const seriesBlock=block(chart.xml,'ser');
      if(seriesBlock)assert(seriesBlock.includes(T.chart.palette[0])||seriesBlock.includes(T.chart.highlight),`${profile} chart${i+1} series paint`);
      const legend=block(chart.xml,'legend');
      if(legend)assert(legend.includes(T.chart.labels),`${profile} chart${i+1} legend`);
    }
    const tableSlide=await slideXml(file,8);
    assert(tableSlide.includes(T.table.bodyFill)&&tableSlide.includes(T.table.bodyText),`${profile} table body tokens`);
    assert(tableSlide.includes(T.table.headerFill)&&tableSlide.includes(T.table.headerText),`${profile} table header tokens`);
    const scene=JSON.parse(fs.readFileSync(file+'.scene.json'));
    assert.equal(scene.slides.length,8);
    const chartNodes=scene.slides.flatMap(slide=>slide.nodes.filter(node=>node.kind==='chart'));
    assert.equal(chartNodes.length,expectedCharts.length);
    assert(chartNodes.every(node=>node.role==='evidence'&&node.provenance.kind==='source_data'&&node.provenance.render_mode==='editable'));
    assert(scene.slides.every(slide=>slide.nodes.some(node=>node.role==='source')));
    assert(scene.slides.every(slide=>slide.nodes.every(node=>node.bbox.w>0&&node.bbox.h>=0)));
  }
  console.log('PASS: theme tokens and native chart XML retain labels/values for bar/column/line/area/pie/doughnut, dashboard, panel, table, scene metadata (light/dark)');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
