// Record the final native API calls; body coordinates use the measured header's available frame.
const {provenance:validateProvenance}=require('../composition/scene');
function attachScene(slide,s,index,style) {
  const scene={slide:index,type:s.type,analytical_series:s.analytical_series||null,nodes:[],relationships:[],content_provenance:[],deduplication:s.deduplication||[],title:null};
  slide._scene=scene;
  for(const method of ['addText','addImage','addShape','addChart','addTable']) {
    const native=slide[method].bind(slide);
    slide[method]=(...args)=>{
      const optionIndex=method==='addImage'?0:method==='addChart'?2:1;
      const options={...(args[optionIndex]||{})},meta=options.scene||{};delete options.scene;
      const kind={addText:'text',addImage:'image',addShape:'shape',addChart:'chart',addTable:'table'}[method];
      const role=meta.role||(kind==='shape'?'decoration':'evidence');
      if(slide._bodyTop>1.65 && !meta.space && options.y>=1.65 && options.y<=6.5) {
        const factor=(6.5-slide._bodyTop)/(6.5-1.65);
        options.y=slide._bodyTop+(options.y-1.65)*factor;
        if(options.h)options.h*=factor;
        if(options.rowH)options.rowH*=factor;
      }
      const id=meta.id||`s${index}-n${scene.nodes.length+1}`;
      options.objectName='gj:'+id;
      const text=kind==='text'?String(args[0]??''):null;
      const provenance=meta.provenance||{kind:kind==='text'?'native_text':kind==='chart'||kind==='table'?'source_data':'generated_annotation',render_mode:kind==='image'?'embedded':'editable'};
      validateProvenance({kind,provenance});
      const h=options.h??(kind==='table'?(args[0].length*(options.rowH||.5)):0);
      scene.nodes.push({id,kind,role,bbox:{x:options.x||0,y:options.y||0,w:options.w||0,h},z:scene.nodes.length,text,font_size:options.fontSize||style.font.bodySize,font_family:options.fontFace||style.font.cjk,bold:!!options.bold,valign:options.valign||'top',color:options.color,provenance,...meta});
      delete scene.nodes.at(-1).space;
      args[optionIndex]=options;return native(...args);
    };
  }
  return scene;
}
module.exports={attachScene};
