const {createPrimitives}=require('../primitives/base');
const {createChartHelper,labelOptions}=require('../charts');
const {resolveTitle,balancedWrap}=require('../../planner/title');
function createMultimodalRenderers(pptx,style,spec,assets) {
  const {base,finish,text,C,F,left,width,W,H}=createPrimitives(pptx,style);
  const charts=createChartHelper(style),table=style.tokens.table;
  const native=(extra)=>({space:'slide',...extra});
  function imagePanel(slide,id,box,nodeId) {
    const asset=assets.map.get(id),caption=asset.caption||asset.attribution||asset.source;
    const result=assets.draw(slide,id,{...box,h:box.h-.48},{id:nodeId});
    if(style.style.image_border==='line')slide.addShape(pptx.ShapeType.rect,{...result.frame,line:{color:C.line,width:.6},fill:{color:style.background,transparency:100},scene:native({role:'decoration'})});
    text(slide,caption,box.x,box.y+box.h-.36,box.w,.32,{fontSize:style.style.image_caption_size||11,color:C.muted,scene:native({id:nodeId+'-caption',role:'source'})});
    slide._scene.relationships.push({from:nodeId+'-caption',to:nodeId,type:'caption_of'});
    return result;
  }
  function panel(slide,p,b,s) {
    const scene=native({id:p.id,role:p.role||'evidence',provenance:p.provenance});
    if(!scene.provenance)delete scene.provenance;
    if(p.kind==='image')return imagePanel(slide,p.asset_id,b,p.id);
    if(p.kind==='text') {
      text(slide,balancedWrap(p.text,F.cjk,F.bodySize+2,b.w).join('\n'),b.x,b.y+.1,b.w,b.h-.2,{fontSize:F.bodySize+2,bold:true,valign:'top',scene});return;
    }
    if(p.kind==='table') {
      const header={fill:table.headerFill,bold:true,color:table.headerText};
      const rows=p.rows.map((row,i)=>row.map(value=>({text:String(value),options:{color:table.bodyText,fill:i%2===1?table.bandFill:table.bodyFill}})));
      slide.addTable([p.headers.map(t=>({text:String(t),options:header})),...rows],{x:b.x,y:b.y,w:b.w,rowH:Math.min(.65,b.h/(p.rows.length+1)),fontFace:F.cjk,fontSize:Math.max(12,F.tableSize-1),color:table.bodyText,margin:[4,4,4,4],border:{pt:.5,color:table.border},autoPage:false,scene});return;
    }
    const kind=p.chartType||'bar';
    const caption=[p.unit,p.period].filter(value=>value!=null&&String(value).trim()!=='').map(value=>String(value).trim()).join(' · ');
    const captionHeight=caption?0.32:0;
    const chartBox={...b,h:b.h-captionHeight};
    const colors=style.encoding?style.encoding.colorsFor(kind,p.series||[],s):charts.tokens.chart.palette;
    const numberFormat=p.numberFormat||'0.0';
    const labelStrategy=style.encoding?style.encoding.encodingPlan(s).label_strategy:null;
    const panelSeries=p.series.map(item=>({name:item.name||'',labels:item.labels||p.labels,values:item.values}));
    const panelMissing=p.series.some(item=>(item.values||[]).some(value=>value==null));
    const panelFinite=(p.series||[]).flatMap(item=>item.values||[]).filter(value=>value!=null);
    const panelAxisMin=['bar','column','area'].includes(kind)?charts.valueAxisMin(panelFinite):kind==='line'?0:undefined;
    slide.addChart(kind==='line'?pptx.ChartType.line:pptx.ChartType.bar,panelSeries,charts.options({...chartBox,barDir:kind==='column'?'col':'bar',showLegend:p.series.length>1,...(panelMissing?{displayBlanksAs:'gap'}:{}),...labelOptions(kind,labelStrategy,{showValue:true,showCatName:false,showSerName:false,showPercent:false,showLabel:false}),showMarker:kind==='line',lineDataSymbol:'circle',lineDataSymbolSize:5,lineSize:2.5,catAxisLabelFontSize:12,valAxisLabelFontSize:11,dataLabelFontSize:12,dataLabelFormatCode:numberFormat,valAxisLabelFormatCode:numberFormat,chartColors:colors,...(panelAxisMin!=null?{valAxisMinVal:panelAxisMin}:{}),valGridLine:{color:charts.tokens.chart.grid,size:.5,style:style.style.chart_grid==='none'?'none':'solid'},showShadow:false,scene}));
    if(caption)text(slide,caption,b.x,b.y+b.h-captionHeight+.02,b.w,captionHeight-.04,
      {fontSize:Math.min(11,F.bodySize-4),color:C.muted,valign:'bottom',scene:native({id:`${p.id}-unit`,role:'unit'})});
  }
  function hero(slide,s) {
    const box={x:0,y:0,w:W,h:H};
    const titleFont={...F,titleSize:Math.min(40,F.titleSize+8)};
    const fullTitle=resolveTitle(s,titleFont,width);
    const tw=fullTitle.lines.length===1?width:width*.68;
    const flow=tw===width?fullTitle:resolveTitle(s,titleFont,tw),ty=4.45,sh=flow.h+(flow.subtitleH?flow.subtitleH+.2:0);
    const overlay={x:(left-.2)/W,y:(ty-.2)/H,w:(tw+.4)/W,h:(sh+.4)/H};
    const r=assets.draw(slide,s.asset_ids[0],box,{id:'hero-image',role:'background',overlay,fit:'cover'});
    const c=r.contrast;slide._scene.title={...flow,titleY:ty};
    if(c.scrim&&!c.embedded_scrim)slide.addShape(pptx.ShapeType.rect,{x:left-.2,y:ty-.2,w:tw+.4,h:sh+.4,line:{color:c.scrim,transparency:100},fill:{color:c.scrim},scene:native({role:'background',id:'local-scrim'})});
    text(slide,flow.lines.join('\n'),left,ty,tw,flow.h,{fontSize:flow.size,bold:true,color:c.color,valign:'top',scene:native({id:'claim',role:'claim',contrast:c})});
    if(flow.subtitleH)text(slide,flow.subtitleLines.join('\n'),left,ty+flow.h+.2,tw,flow.subtitleH,{fontSize:Math.min(F.bodySize,17),color:c.color,valign:'top',scene:native({id:'subtitle',role:'subtitle',contrast:c})});
    slide._scene.relationships.push({from:'hero-image',to:'claim',type:'background_of'});
    slide.addShape(pptx.ShapeType.rect,{x:0,y:7.1,w:W,h:.4,line:{color:style.background},fill:{color:style.background},scene:native({role:'background'})});
    finish(slide,{...s,takeaway:null,source:s.source||r.asset.attribution||r.asset.source});
  }
  function multimodal(s) {
    const slide=pptx.addSlide();slide.background={color:style.background};
    if(s.composition==='multimodal-hero'){hero(slide,s);return;}
    const b=base(slide,s),gap=style.style.image_gap||.4;
    if(s.composition==='multimodal-annotated') {
      const asset=assets.map.get(s.asset_ids[0]),image=imagePanel(slide,asset.id,{x:b.x,y:b.y,w:b.w*.64,h:b.h},'document');
      const annotations=s.annotations||[],rh=Math.min(1.1,(b.h-.7)/Math.max(annotations.length,1));
      annotations.forEach((a,i)=>{
        const r=a.source_region,visible=image.crop;
        if(r.x<visible.x||r.y<visible.y||r.x+r.w>visible.x+visible.w+1e-6||r.y+r.h>visible.y+visible.h+1e-6)throw Error('Annotation source region is outside the visible crop');
        const x=image.frame.x+(r.x-visible.x)/visible.w*image.frame.w,y=image.frame.y+(r.y-visible.y)/visible.h*image.frame.h;
        const id=`annotation-${i}`;
        slide.addShape(pptx.ShapeType.rect,{x,y,w:r.w/visible.w*image.frame.w,h:r.h/visible.h*image.frame.h,line:{color:C.accent,width:1.5},fill:{color:C.accent,transparency:100},scene:native({role:'annotation',id:id+'-region'})});
        text(slide,`${i+1}. ${a.text}`,b.x+b.w*.69,b.y+.15+i*rh,b.w*.31,rh-.15,{fontSize:F.bodySize-1,valign:'top',scene:native({id,role:'annotation',provenance:{kind:'generated_annotation',source_asset:asset.id,source_region:r,confidence:a.confidence??1,render_mode:'editable'}})});
        slide._scene.relationships.push({from:id,to:'document',type:'annotates'},{from:id+'-region',to:'document',type:'annotates'});
      });
      if(s.insight)text(slide,s.insight,b.x+b.w*.69,b.y+b.h-.6,b.w*.31,.6,{fontSize:14,bold:true,scene:native({role:'takeaway'})});
    } else {
      let panels=s.panels;
      if(!panels) {
        panels=s.asset_ids.map((id,i)=>({id:`image-${i}`,kind:'image',asset_id:id}));
        if(s.composition==='multimodal-split')panels.push({id:'interpretation',kind:'text',text:s.insight||s.body,provenance:{kind:'derived_insight',render_mode:'editable'}});
      }
      const cols=panels.length===1?1:2,rows=Math.ceil(panels.length/cols),cw=(b.w-gap*(cols-1))/cols,ch=(b.h-gap*(rows-1))/rows;
      panels.forEach((p,i)=>panel(slide,p,{x:b.x+(i%cols)*(cw+gap),y:b.y+Math.floor(i/cols)*(ch+gap),w:cw,h:ch},s));
    }
    finish(slide,s);
  }
  return {multimodal};
}
module.exports={createMultimodalRenderers};
