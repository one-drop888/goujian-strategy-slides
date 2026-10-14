const { columns } = require('../compositions/layout');

function createSlideRenderers(pptx, style, spec) {
  const { createPrimitives } = require('../primitives/base');
  const { base, finish, text, line, C, F, W, H, left, right, width } = createPrimitives(pptx, style);
  const body = style.layout?.bodySize || F.bodySize || 15;

  const txt=(v)=>v==null?'':String(v);
  const itemTitle=(it)=>typeof it==='string'?it:(it.title||it.label||it.heading||'');
  const itemNote=(it)=>typeof it==='string'?'':(it.note||it.detail||it.description||'');

  function cover(s) {
    const slide=pptx.addSlide(); slide.background={color:style.background};
    const dark=style.style.cover_treatment==='band';
    if(dark) slide.addShape(pptx.ShapeType.rect,{x:0,y:0,w:W,h:.20,line:{color:C.accent},fill:{color:C.accent}});
    text(slide,s.kicker||spec.brand||'构见 · GOUJIAN',left,1.0,width,.32,{fontSize:12,bold:true,color:C.accent});
    text(slide,s.title||spec.title,left,2.03,width,1.7,{fontSize:Math.max(36,F.titleSize+10),bold:true,valign:'top'});
    if(s.subtitle) text(slide,s.subtitle,left,4.03,width*.85,.9,{fontSize:F.bodySize+1,color:C.muted,valign:'top'});
    line(slide,left,5.73,style.style.cover_treatment==='editorial'?width:2.1,C.accent,1.5);
    text(slide,s.footer||spec.footer||'',left,6.66,width,.25,{fontSize:10,color:C.muted});
  }

  function section(s) {
    const slide=pptx.addSlide(); slide.background={color:C.accentSoft};
    text(slide,s.number==null?'':String(s.number).padStart(2,'0'),left,1.2,2,.7,{fontSize:30,bold:true,color:C.accent});
    text(slide,s.title,left,2.5,width,1.25,{fontSize:36,bold:true});
    if(s.subtitle) text(slide,s.subtitle,left,4.0,width*.85,.9,{color:C.muted});
  }

  function statement(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    line(slide,left,2.22,.70,C.accent,4);
    text(slide,s.statement||s.body,left,2.72,width*.92,2.5,{fontSize:F.bodySize+10,bold:true,valign:'top'});
    if(s.note) text(slide,s.note,left,5.52,width,.66,{fontSize:15,color:C.muted});
    finish(slide,s);
  }

  function summary(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const rowH=Math.min(1.14,4.65/s.items.length);
    s.items.forEach((it,i)=>{
      const y=1.94+i*rowH;
      text(slide,String(i+1).padStart(2,'0'),left,y,.42,.34,{fontSize:12,color:C.accent,bold:true});
      text(slide,itemTitle(it),left+.68,y,2.72,rowH-.22,{fontSize:F.bodySize,bold:true,valign:'top'});
      text(slide,itemNote(it)||it.implication||'',left+3.64,y,width-3.64,rowH-.22,{fontSize:F.bodySize,color:C.muted,valign:'top'});
      line(slide,left+.68,y+rowH-.15,width-.68,C.line,.6);
    }); finish(slide,s);
  }

  function kpi(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const cols=columns(s.items.length,.32,left,width);
    s.items.forEach((it,i)=>{
      const {x,w}=cols[i]; const emphasis=it.highlight===true;
      if(style.style.metric_style==='panel') slide.addShape(pptx.ShapeType.rect,{x,y:2.12,w,h:3.0,line:{color:C.panel},fill:{color:C.panel}});
      text(slide,it.label||it.title,x+.08,2.24,w-.16,.5,{fontSize:16,color:C.muted});
      text(slide,it.value,x+.08,3.06,w-.16,.88,{fontFace:F.latin,fontSize:s.items.length>4?30:38,bold:true,color:emphasis?C.accent:C.text});
      line(slide,x+.08,4.24,w-.16,emphasis?C.accent:C.line,emphasis?2:1);
      text(slide,it.note||it.delta||'',x+.08,4.52,w-.16,.68,{fontSize:14,color:emphasis?C.accent:C.muted,valign:'top'});
    }); finish(slide,s);
  }

  function comparison(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const cols=columns(s.columns.length,.55,left,width);
    s.columns.forEach((c,i)=>{
      const {x,w}=cols[i]; const highlight=c.highlight===true;
      line(slide,x,1.99,w,highlight?C.accent:C.line,highlight?3:1);
      text(slide,c.heading,x,2.21,w,.65,{fontSize:F.bodySize+3,bold:true,color:highlight?C.accent:C.text});
      const rh=Math.min(.72,3.4/Math.max(c.points.length,1));
      c.points.forEach((p,j)=>{
        text(slide,String(j+1).padStart(2,'0'),x,3.06+j*rh,.32,.4,{fontSize:10,color:C.muted});
        text(slide,typeof p==='string'?p:(p.text||p.title),x+.44,3.01+j*rh,w-.44,rh-.1,{fontSize:F.bodySize-1,valign:'top'});
      });
      if(c.value) text(slide,c.value,x,6.0,w,.48,{fontSize:22,bold:true,color:C.accent});
    }); finish(slide,s);
  }

  function process(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const cols=columns(s.items.length,.32,left,width);
    line(slide,left,2.56,width,C.line,1.5);
    s.items.forEach((it,i)=>{
      const {x,w}=cols[i];
      text(slide,String(i+1).padStart(2,'0'),x,2.04,.6,.4,{fontSize:18,bold:true,color:C.accent});
      text(slide,itemTitle(it),x,2.98,w,1.0,{fontSize:F.bodySize+1,bold:true,valign:'top'});
      if(itemNote(it)) text(slide,itemNote(it),x,4.25,w,1.3,{fontSize:F.bodySize-2,color:C.muted,valign:'top'});
    }); finish(slide,s);
  }

  function funnel(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const values=s.items.map(it=>Number(String(it.value).replaceAll(',','').replace(/%$/, '')));
    const max=Math.max(...values); const rh=Math.min(.86,4.55/s.items.length);
    s.items.forEach((it,i)=>{
      const y=1.98+i*rh, bw=7.6*values[i]/max;
      text(slide,itemTitle(it),left,y,2.25,.42,{fontSize:15,bold:true});
      slide.addShape(pptx.ShapeType.rect,{x:left+2.55,y:y+.05,w:Math.max(.025,bw),h:.31,line:{color:i===0?C.accent:C.line},fill:{color:i===0?C.accent:C.line}});
      text(slide,it.value,left+10.5,y,width-10.5,.42,{fontSize:16,bold:true,align:'right',fontFace:F.latin});
      if(i>0) text(slide,`${(values[i]/values[i-1]*100).toFixed(1)}%`+(spec.lang?.startsWith('en')?' retained':' 留存'),left+2.55,y+.40,4,.26,{fontSize:10,color:C.muted});
    }); finish(slide,s);
  }

  function timeline(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section); const items=(s.items||[]).slice(0,7);
    slide.addShape(pptx.ShapeType.line,{x:1.15,y:3.62,w:10.9,h:0,line:{color:C.line,width:2}}); const n=Math.max(1,items.length);
    items.forEach((it,i)=>{ const x=1.15+(n===1?5.45:i*(10.9/(n-1)));
      slide.addShape(pptx.ShapeType.ellipse,{x:x-.11,y:3.51,w:.22,h:.22,line:{color:C.accent,width:1},fill:{color:C.accent}});
      slide.addText(it.time||it.period||'',{x:x-.72,y:2.40,w:1.44,h:.3,fontFace:F.latin,fontSize:13,bold:true,color:C.accent,align:'center',margin:0,fit:'shrink'});
      slide.addText(itemTitle(it),{x:x-.82,y:2.86,w:1.64,h:.52,fontFace:F.cjk,fontSize:14,bold:true,color:C.text,align:'center',margin:0,fit:'shrink'});
      if(itemNote(it)) slide.addText(itemNote(it),{x:x-.82,y:3.91,w:1.64,h:.7,fontFace:F.cjk,fontSize:12,color:C.muted,align:'center',margin:0,fit:'shrink'});
    }); finish(slide,s);
  }

  function roadmap(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const lanes=s.lanes||s.items, h=Math.min(1.13,4.6/lanes.length-.1);
    lanes.forEach((lane,i)=>{
      const y=1.98+i*(h+.10);
      text(slide,lane.title||lane.label,left,y,2.0,h,{fontSize:16,bold:true});
      const phases=lane.phases||lane.items, cols=columns(phases.length,.18,left+2.2,width-2.2);
      phases.forEach((p,j)=>{
        const {x,w}=cols[j];
        line(slide,x,y+.12,w,C.accent,2);
        text(slide,itemTitle(p),x,y+.3,w,h-.36,{fontSize:16,bold:true});
      });
    }); finish(slide,s);
  }

  function matrix(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const x=left+.55,y=2.02,w=s.insight?8.7:width-.8,h=4.12;
    slide.addShape(pptx.ShapeType.rect,{x,y,w,h,line:{color:C.line,width:.6},fill:{color:style.background}});
    slide.addShape(pptx.ShapeType.line,{x:x+w/2,y,w:0,h,line:{color:C.line,width:.7,dash:'dash'}});
    line(slide,x,y+h/2,w,C.line,.7);
    text(slide,(s.xLabel||'')+' →',x,6.32,w,.32,{fontSize:12,color:C.muted,align:'center'});
    text(slide,(s.yLabel||'')+' ↑',left,1.68,width,.28,{fontSize:12,color:C.muted});
    (s.quadrants||[]).forEach((q,i)=>text(slide,q,x+(i%2)*w/2+.12,y+Math.floor(i/2)*h/2+.08,w/2-.24,.27,{fontSize:10,color:C.muted}));
    s.items.forEach(it=>{
      const cx=x+.18+it.x*(w-.36),cy=y+.18+(1-it.y)*(h-.36);
      slide.addShape(pptx.ShapeType.ellipse,{x:cx-.065,y:cy-.065,w:.13,h:.13,line:{color:C.accent},fill:{color:C.accent}});
      const labelW=1.75,goLeft=cx+labelW+.16>x+w;
      text(slide,itemTitle(it),goLeft?cx-labelW-.14:cx+.14,cy-.18,labelW,.37,{fontSize:14,bold:true,align:goLeft?'right':'left'});
    });
    if(s.insight)text(slide,s.insight,x+w+.3,2.55,width-w-.85,2.7,{fontSize:16,bold:true,valign:'top'});
    finish(slide,s);
  }

  function hierarchy(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const items=s.items||s.branches, cols=columns(items.length,.42,left,width);
    text(slide,s.root||s.center||s.statement,left,1.93,width,.70,{fontSize:F.bodySize+5,bold:true,align:'center'});
    const centers=cols.map(c=>c.x+c.w/2);
    slide.addShape(pptx.ShapeType.line,{x:W/2,y:2.75,w:0,h:.3,line:{color:C.line,width:1}});
    line(slide,centers[0],3.05,centers.at(-1)-centers[0],C.line,1);
    items.forEach((it,i)=>{
      const {x,w}=cols[i];
      slide.addShape(pptx.ShapeType.line,{x:x+w/2,y:3.05,w:0,h:.27,line:{color:C.line,width:1}});
      text(slide,itemTitle(it),x,3.54,w,.65,{fontSize:F.bodySize+1,bold:true,align:'center',color:C.accent});
      (it.children||[]).forEach((k,j)=>text(slide,itemTitle(k),x+.1,4.5+j*.57,w-.2,.45,{fontSize:F.bodySize-2,align:'center',color:C.muted}));
    }); finish(slide,s);
  }

  function action(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const rh=Math.min(1.2,4.55/s.items.length);
    s.items.forEach((it,i)=>{
      const y=1.99+i*rh;
      text(slide,String(i+1).padStart(2,'0'),left,y,.5,.4,{fontSize:12,bold:true,color:C.accent});
      text(slide,itemTitle(it),left+.7,y,5.6,.56,{fontSize:F.bodySize,bold:true});
      if(itemNote(it)) text(slide,itemNote(it),left+.7,y+.60,5.6,rh-.7,{fontSize:13,color:C.muted});
      text(slide,[it.owner,it.time||it.period].filter(Boolean).join(' · '),left+6.7,y,3.15,.56,{fontSize:14,color:C.muted});
      if(it.status) text(slide,it.status,left+10.0,y,width-10,.56,{fontSize:14,bold:true,color:C.accent,align:'right'});
      line(slide,left+.7,y+rh-.17,width-.7,C.line,.6);
    }); finish(slide,s);
  }

  function evidence(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    slide.addShape(pptx.ShapeType.rect,{x:left,y:1.94,w:width*.47,h:4.35,line:{color:C.panel},fill:{color:C.panel}});
    text(slide,s.quote||s.evidenceText||s.body,left+.32,2.33,width*.47-.64,2.65,{fontSize:F.bodySize+6,bold:true,valign:'top'});
    if(s.attribution) text(slide,s.attribution,left+.32,5.4,width*.47-.64,.57,{fontSize:12,color:C.muted});
    const x=left+width*.53;
    line(slide,x,2.30,.55,C.accent,3);
    text(slide,s.insight||s.interpretation||s.takeaway,x,2.72,width*.47,2.2,{fontSize:F.bodySize+4,bold:true,valign:'top'});
    if(s.note) text(slide,s.note,x,5.3,width*.47,.8,{fontSize:14,color:C.muted});
    finish(slide,{...s,takeaway:null});
  }

  function architecture(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const layers=s.layers||[{title:'',items:s.items||s.nodes}];
    const h=Math.min(1.2,(4.55-.12*(layers.length-1))/layers.length);
    layers.forEach((layer,i)=>{
      const y=1.9+i*(h+.12), labelW=2.0;
      text(slide,layer.title||'',left,y,labelW-.15,h,{fontSize:15,bold:true,color:C.muted});
      const cols=columns(layer.items.length,.12,left+labelW,width-labelW);
      cols.forEach(({x,w},j)=>{
        slide.addShape(pptx.ShapeType.rect,{x,y,w,h,line:{color:C.line,width:.6},fill:{color:layer.highlight?C.accentSoft:C.panel}});
        text(slide,itemTitle(layer.items[j]),x+.12,y+.10,w-.24,h-.20,{fontSize:16,bold:true,align:'center'});
      });
    }); finish(slide,s);
  }

  function portfolio(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section);
    const cols=columns(2,.65,left,width), rows=Math.ceil(s.items.length/2),rh=Math.min(2.0,4.6/rows);
    s.items.forEach((it,i)=>{
      const {x,w}=cols[i%2],y=1.98+Math.floor(i/2)*rh;
      line(slide,x,y,w,it.highlight?C.accent:C.line,it.highlight?3:1);
      text(slide,itemTitle(it),x,y+.23,w,.52,{fontSize:F.bodySize+2,bold:true});
      text(slide,[it.value,it.status].filter(Boolean).join(' · '),x,y+.86,w,.34,{fontSize:14,bold:true,color:C.accent});
      if(itemNote(it))text(slide,itemNote(it),x,y+1.32,w,rh-1.4,{fontSize:14,color:C.muted,valign:'top'});
    }); finish(slide,s);
  }

  function pyramid(s) {
    const slide=pptx.addSlide(); base(slide,s.title,s.section); const levels=(s.levels||s.items||[]).slice(0,5); const n=Math.max(levels.length,1);
    levels.forEach((it,i)=>{const width=4.2+i*1.35, x=(W-width)/2, y=1.80+i*.88; slide.addShape(pptx.ShapeType.trapezoid,{x,y,w:width,h:.68,line:{color:i===0?C.accent:C.line},fill:{color:i===0?C.accentSoft:C.panel}}); slide.addText(itemTitle(it),{x:x+.25,y:y+.19,w:width-.5,h:.28,fontFace:F.cjk,fontSize:14,bold:true,color:C.text,align:'center',margin:0,fit:'shrink'});}); finish(slide,s);
  }

  return { cover, section, statement, summary, kpi, comparison, process, funnel, timeline, roadmap, matrix, hierarchy, action, evidence, architecture, portfolio, pyramid, ...require('./data').createDataRenderers(pptx, style, spec) };
}
module.exports={createSlideRenderers};
