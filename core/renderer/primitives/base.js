const { W, H, M } = require('../compositions/layout');
function createPrimitives(pptx, style) {
  const C = style.colors, F = style.font, L = style.layout;
  const left = L.marginX, right = left, width = W-left-right;
  function text(slide, value, x, y, w, h, options = {}) {
    slide.addText(String(value ?? ''), { x, y, w, h, fontFace: F.cjk,
      fontSize: F.bodySize, color: C.text, margin: 0, valign: 'mid',
      breakLine: false, ...options });
  }
  function line(slide, x, y, w, color = C.line, size = 1) {
    slide.addShape(pptx.ShapeType.line, { x, y, w, h: 0, line: { color, width: size } });
  }
  function base(slide, title, section) {
    slide.background = { color: style.background };
    if (section) text(slide, section, left, .18, width, .22, { fontSize: 10, color: C.muted });
    if (title) {
      // Bound two-line titles before serialization; PowerPoint autofit is not a layout engine.
      const units = [...title].reduce((n,c) => n + (/[^\x00-\xff]/.test(c) ? 1 : .52), 0);
      const size = Math.min(F.titleSize, Math.max(23, width*72*1.8 / Math.max(units,1)));
      text(slide, title, left, L.titleY, width, .80, { fontSize: size, bold: true });
    }
    if (style.style.title_rule !== 'none') {
      line(slide, left, L.dividerY, width, C.line, .7);
      if (style.style.title_rule === 'accent') line(slide, left, L.dividerY, .8, C.accent, 3);
    }
  }
  function finish(slide, s) {
    if (s.takeaway) {
      line(slide, left, 6.77, .42, C.accent, 3);
      text(slide, s.takeaway, left+.58, 6.67, width-.58, .44, { fontSize: 13, bold: true });
    }
    const src = Array.isArray(s.source) ? s.source.join(' · ') : s.source;
    if (src) text(slide, src, left, 7.18, width-.4, .18, { fontSize: 8, color: C.muted });
    text(slide, String(pptx._slides.length).padStart(2,'0'), W-right-.3, 7.18, .3, .18,
      { fontSize: 8, color: C.muted, align: 'right', fontFace: F.latin });
    if (s.evidence?.length) slide.addNotes(s.evidence.map(e => JSON.stringify(e)).join('\n'));
  }
  return { base, finish, text, line, C, F, W, H, M, left, right, width };
}
module.exports = { createPrimitives };
