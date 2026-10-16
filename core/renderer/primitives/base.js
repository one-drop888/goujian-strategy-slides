const { W, H, M } = require('../compositions/layout');
const {resolveTitle}=require('../../planner/title');
function createPrimitives(pptx, style) {
  const C = style.colors, F = style.font, L = style.layout;
  const left = L.marginX, right = left, width = W-left-right;
  function text(slide, value, x, y, w, h, options = {}) {
    slide.addText(String(value ?? ''), { x, y, w, h, fontFace: F.cjk,
      fontSize: F.bodySize, color: C.text, margin: 0, valign: 'mid',
      breakLine: false, ...options });
  }
  function line(slide, x, y, w, color = C.line, size = 1) {
    slide.addShape(pptx.ShapeType.line, { x, y, w, h: 0, line: { color, width: size },scene:{role:'rule'} });
  }
  function base(slide, s) {
    slide.background = { color: style.background };
    if(s.section)text(slide,s.section,left,.18,width,.22,{fontSize:10,color:C.muted,scene:{role:'decoration',semantic_role:'section_label',space:'slide'}});
    const flow=resolveTitle(s,F,width);
    if(flow.bodyTop>2.85)throw Error('Title/subtitle leaves less than 3.6 inches for evidence; shorten the header or split the slide');
    if(slide._scene)slide._scene.title=flow;
    if(s.title)text(slide,flow.lines.join('\n'),left,flow.titleY,width,flow.h,{fontSize:flow.size,bold:true,valign:'top',scene:{id:'claim',role:'claim',space:'slide'}});
    if(flow.subtitleH)text(slide,flow.subtitleLines.join('\n'),left,flow.subtitleY,width,flow.subtitleH,{fontSize:Math.min(F.bodySize,17),color:C.muted,valign:'top',scene:{id:'subtitle',role:'subtitle',space:'slide'}});
    if(style.style.title_rule!=='none') {
      slide.addShape(pptx.ShapeType.line,{x:left,y:flow.dividerY,w:width,h:0,line:{color:C.line,width:.7},scene:{role:'divider',space:'slide'}});
      if(style.style.title_rule==='accent')slide.addShape(pptx.ShapeType.line,{x:left,y:flow.dividerY,w:.8,h:0,line:{color:C.accent,width:3},scene:{role:'divider',space:'slide'}});
    }
    slide._bodyTop=flow.bodyTop;
    return {x:left,y:flow.bodyTop,w:width,h:6.45-flow.bodyTop};
  }
  function finish(slide, s) {
    if (s.takeaway) {
      line(slide, left, 6.77, .42, C.accent, 3);
      text(slide, s.takeaway, left+.58, 6.67, width-.58, .44, { fontSize: 13, bold: true,scene:{id:"takeaway",role:"takeaway",space:"slide"} });
    }
    const src = Array.isArray(s.source) ? s.source.join(' · ') : s.source;
    if (src) text(slide, src, left, 7.18, width-.4, .18, { fontSize: 8, color: C.muted,scene:{id:"source",role:"source",space:"slide"} });
    text(slide, String(pptx._slides.length).padStart(2,'0'), W-right-.3, 7.18, .3, .18,
      { fontSize: 8, color: C.muted, align: 'right', fontFace: F.latin,scene:{role:'decoration',semantic_role:'page_number',space:'slide'} });
    if (s.evidence?.length) slide.addNotes(s.evidence.map(e => JSON.stringify(e)).join('\n'));
  }
  return { base, finish, text, line, C, F, W, H, M, left, right, width };
}
module.exports = { createPrimitives };
