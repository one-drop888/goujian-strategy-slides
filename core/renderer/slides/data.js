const { createPrimitives } = require('../primitives/base');
function createDataRenderers(pptx, style, spec) {
  const {base, finish, text, line, C, F, left, width} = createPrimitives(pptx, style);
  const zh = (spec.lang || 'zh-CN').startsWith('zh');
  function drawTable(slide, headers, rows, s, widths) {
    const headerFill = style.style.table_header === 'solid' ? C.text : C.accentSoft;
    const headerColor = style.style.table_header === 'solid' ? style.background : C.text;
    const numeric = (v) => typeof v === 'number' || /^[+−-]?[\d,.]+\s*(%|pp|万元|万)?$/.test(String(v));
    const cells = [headers.map(t => ({text:String(t),options:{bold:true,fill:headerFill,color:headerColor}})),
      ...rows.map((row,i) => row.map((v,j) => ({text:String(v ?? ''),options:{
        align: numeric(v) && j>0 ? 'right' : 'left',
        bold: s.highlightRows?.includes(i) || false,
        fill: s.highlightRows?.includes(i) ? C.accentSoft :
          style.style.table_banding && i%2===1 ? C.panel : style.background,
      }})))];
    const rowH = Math.min(.87, 4.5/(rows.length+1));
    slide.addTable(cells, {
      x:left,y:1.85,w:width,colW:widths?.map(v=>v*width),
      rowH, fontFace:F.cjk,fontSize:headers.length>6?Math.max(12,F.tableSize-2):F.tableSize, color:C.text,
      margin:[5,8,5,8], valign:'mid', autoPage:false,
      border:[{type:'solid',pt:.5,color:C.line},{type:'solid',pt:0,color:style.background},
        {type:'solid',pt:.5,color:C.line},{type:'solid',pt:0,color:style.background}],
    });
  }
  function table(s) {
    const slide=pptx.addSlide(); base(slide,s);
    drawTable(slide,s.headers,s.rows,s,s.columnWidths); finish(slide,s);
  }
  function scorecard(s) {
    const slide=pptx.addSlide(); base(slide,s);
    if(s.semanticType==='research-method') {
      drawTable(slide, zh?['设计维度','范围 / 方法','依据与限制']:['Design','Scope / method','Basis and limitations'],
        s.items.map(it=>[it.label||it.title,it.value,it.note||'']),s,[.23,.24,.53]);
    } else {
      drawTable(slide,s.headers || (zh?['指标','实际','目标','差异','状态']:['Metric','Actual','Target','Variance','Status']),
        s.items.map(it=>[it.label||it.title,it.value??it.actual??'',it.target??'',it.variance??it.delta??'',it.status??'']),
        s,[.30,.19,.19,.16,.16]);
    }
    finish(slide,s);
  }
  function risk(s) {
    const slide=pptx.addSlide(); base(slide,s);
    drawTable(slide,zh?['风险 / 问题','可能性','影响','应对措施','负责人']:['Risk / issue','Likelihood','Impact','Mitigation','Owner'],
      s.items.map(it=>[it.title||it.label,it.likelihood||'',it.impact||it.severity||'',it.mitigation||it.action||'',it.owner||'']),
      s,[.24,.12,.11,.38,.15]);
    finish(slide,s);
  }
  function chart(s) {
    const slide=pptx.addSlide(); base(slide,s);
    const kind=s.chartType || 'bar';
    const map={bar:pptx.ChartType.bar,column:pptx.ChartType.bar,line:pptx.ChartType.line,area:pptx.ChartType.area,
      pie:pptx.ChartType.pie,doughnut:pptx.ChartType.doughnut};
    const series=s.series.map(x=>({name:x.name||'',labels:x.labels||s.labels,values:x.values}));
    const colors=series.length===1 && ['bar','column'].includes(kind)
      ? series[0].values.map((_,i)=>i===(s.highlightIndex??0)?C.accent:'A9B6BF')
      : [C.accent,'899AA8','B3BDC6','526373'];
    const options={fontFace:F.cjk,dataLabelFontFace:F.latin,x:left,y:2.12,w:s.insight?8.25:width,h:4.32,
      showLegend:series.length>1,legendPos:'b',legendColor:C.muted,legendFontFace:F.cjk,legendFontSize:F.chartSize,
      showTitle:false,showBorder:false,showValue:['bar','column'].includes(kind),
      dataLabelPosition:'outEnd',dataLabelColor:C.text,dataLabelFormatCode:s.numberFormat||'0.##',
      dataLabelFontSize:F.chartSize,
      chartColors:colors,catAxisLabelFontFace:F.cjk,catAxisLabelFontSize:F.chartSize,catAxisLabelColor:C.muted,
      valAxisLabelFontFace:F.latin,valAxisLabelFontSize:F.chartSize,valAxisLabelColor:C.muted,
      catAxisLineShow:false,valAxisLineShow:false,catAxisLabelRotate:0,
      catGridLine:{style:'none'},valGridLine:{color:C.line,size:.5,style:style.style.chart_grid==='none'?'none':'solid'},
      showMarker:true,lineSize:2.5,lineDataSymbol:'circle',lineDataSymbolSize:5,
      showCatName:false,showShadow:false,showSerName:false,
      chartArea:{fill:{color:style.background},border:{color:style.background,pt:0}},
      plotArea:{fill:{color:style.background},border:{color:style.background,pt:0}},
      barGapWidthPct:s.semanticType==='histogram'?0:(series[0].labels.length<3?220:65),barDir:kind==='bar'?'bar':'col',
    };
    if (['bar','column','area'].includes(kind)) options.valAxisMinVal=Math.min(0,...series.flatMap(x=>x.values));
    if (s.axisMin != null) options.valAxisMinVal=s.axisMin;
    slide.addChart(map[kind],series,options);
    text(slide,[s.unit,s.period].filter(Boolean).join(' · '),left,1.73,8,.27,{fontSize:11,color:C.muted});
    if(s.insight) {
      const x=left+8.65,w=width-8.65;
      line(slide,x,2.32,.55,C.accent,3);
      text(slide,s.insight,x,2.58,w,2.8,{fontSize:F.bodySize+1,bold:true,valign:'top'});
    }
    finish(slide,s);
  }
  return {chart,table,scorecard,risk};
}
module.exports={createDataRenderers};
