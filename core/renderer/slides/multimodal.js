const {createPrimitives}=require('../primitives/base');
const {resolveTitle,balancedWrap}=require('../../planner/title');
function createMultimodalRenderers(pptx,style,spec,assets) {
  const {base,finish,text,C,F,left,width,W,H}=createPrimitives(pptx,style);
  const native=(extra)=>({space:'slide',...extra});
  function imagePanel(slide,id,box,nodeId) {
    const asset=assets.map.get(id),caption=asset.caption||asset.attribution||asset.source;
    const result=assets.draw(slide,id,{...box,h:box.h-.48},{id:nodeId});
    if(style.style.image_border==='line')slide.addShape(pptx.ShapeType.rect,{...result.frame,line:{color:C.line,width:.6},fill:{color:style.background,transparency:100},scene:native({role:'decoration'})});
    text(slide,caption,box.x,box.y+box.h-.36,box.w,.32,{fontSize:style.style.image_caption_size||11,color:C.muted,scene:native({id:nodeId+'-caption',role:'source'})});
    slide._scene.relationships.push({from:nodeId+'-caption',to:nodeId,type:'caption_of'});
    return result;
  }
  function panel(slide,p,b) {
    const scene=native({id:p.id,role:p.role||'evidence',provenance:p.provenance});
    if(!scene.provenance)delete scene.provenance;
    if(p.kind==='image')return imagePanel(slide,p.asset_id,b,p.id);
    if(p.kind==='text') {
      text(slide,balancedWrap(p.text,F.cjk,F.bodySize+2,b.w).join('\n'),b.x,b.y+.1,b.w,b.h-.2,{fontSize:F.bodySize+2,bold:true,valign:'top',scene});return;
    }
    if(p.kind==='table') {
      const header={fill:C.accentSoft,bold:true};
      slide.addTable([p.headers.map(t=>({text:String(t),options:header})),...p.rows],{x:b.x,y:b.y,w:b.w,rowH:Math.min(.65,b.h/(p.rows.length+1)),fontFace:F.cjk,fontSize:Math.max(12,F.tableSize-1),margin:[4,4,4,4],border:{pt:.5,color:C.line},autoPage:false,scene});return;
    }
    const colors=[C.accent,'A9B6BF','526373'];
    slide.addChart(p.chartType==='line'?pptx.ChartType.line:pptx.ChartType.bar,p.series.map(s=>({name:s.name||'',labels:s.labels||p.labels,values:s.values})),{...b,barDir:p.chartType==='column'?'col':'bar',showLegend:p.series.length>1,showValue:true,showTitle:false,showCatName:false,showBorder:false,fontFace:F.cjk,catAxisLabelFontFace:F.cjk,valAxisLabelFontFace:F.latin,dataLabelFontFace:F.latin,legendFontFace:F.cjk,catAxisLabelFontSize:12,valAxisLabelFontSize:11,dataLabelFontSize:12,dataLabelFormatCode:p.numberFormat||'0.0',chartColors:colors,valAxisMinVal:0,catAxisLineShow:false,valAxisLineShow:false,catGridLine:{style:'none'},valGridLine:{color:C.line,size:.5},showShadow:false,scene});
  }
  function hero(slide,s) {
    const box={x:0,y:0,w:W,h:H};
    const titleFont={...F,titleSize:Math.min(40,F.titleSize+8)},tw=width*.68;
    const flow=resolveTitle(s,titleFont,tw),ty=4.45,sh=flow.h+(flow.subtitleH?flow.subtitleH+.2:0);
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
      panels.forEach((p,i)=>panel(slide,p,{x:b.x+(i%cols)*(cw+gap),y:b.y+Math.floor(i/cols)*(ch+gap),w:cw,h:ch}));
    }
    finish(slide,s);
  }
  return {multimodal};
}
module.exports={createMultimodalRenderers};
