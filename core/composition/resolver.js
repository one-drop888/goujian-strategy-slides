const fs = require('fs');
const path = require('path');

let cache = null;
function loadRegistry(repoRoot) {
  if (cache && cache.root === repoRoot) return cache;
  const archetypes = JSON.parse(fs.readFileSync(path.join(repoRoot,'skill','archetypes','registry.json'),'utf8'));
  const compositions = JSON.parse(fs.readFileSync(path.join(repoRoot,'skill','compositions','registry.json'),'utf8'));
  const amap = new Map(archetypes.archetypes.map(x => [x.id, x]));
  const cmap = new Map(compositions.compositions.map(x => [x.id, x]));
  cache = { root: repoRoot, amap, cmap, archetypes, compositions };
  return cache;
}

const legacy = {
  statement: { id:'statement', composition:'message-focus', renderer:'statement' },
  kpi: { id:'kpi', composition:'metric-strip', renderer:'kpi' },
  chart: { id:'chart', composition:'chart-with-insight', renderer:'chart' },
  action: { id:'action', composition:'action-register', renderer:'action' },
};

function asArray(v) { return Array.isArray(v) ? v : (v == null ? [] : [v]); }

function normalizeSlide(slide, meta) {
  const s = JSON.parse(JSON.stringify(slide || {}));
  const semanticType = s.type;
  const renderer = meta.renderer;
  s.semanticType = semanticType;
  s.composition = s.composition || meta.composition;

  if (['key-message','decision','recommendation','closing'].includes(semanticType)) {
    s.statement = s.statement || s.body || s.message || s.takeaway || s.title || '';
  }
  if (['executive-summary','agenda'].includes(semanticType)) {
    if (!s.items && s.points) s.items = asArray(s.points).map(x => typeof x === 'string' ? {title:x} : x);
  }
  if (semanticType === 'before-after' && !s.columns && (s.before || s.after)) {
    s.columns = [
      { heading: s.before?.heading || 'Before', points: s.before?.points || asArray(s.before) },
      { heading: s.after?.heading || 'After', points: s.after?.points || asArray(s.after) },
    ];
  }
  if (['benchmark','segmentation','regional-performance','scenario-analysis','audience-strategy'].includes(semanticType) && !s.columns && s.items) {
    s.columns = s.items.map(x => typeof x === 'string' ? {heading:x,points:[]} : {heading:x.heading||x.label||x.title||'',points:x.points||x.notes||[]});
  }
  if (['trend','line','cohort'].includes(semanticType)) s.chartType = s.chartType || 'line';
  if (['area'].includes(semanticType)) s.chartType = s.chartType || 'area';
  if (['bar','benchmark'].includes(semanticType)) s.chartType = s.chartType || 'bar';
  if (['column','variance','cost-structure','histogram','waterfall','bridge'].includes(semanticType)) s.chartType = s.chartType || 'column';
  if (['scatter','bubble'].includes(semanticType)) s.chartType = s.chartType || 'scatter';
  if (semanticType === 'product-positioning' && !s.xLabel) { s.xLabel='Low differentiation → High differentiation'; s.yLabel='Low relevance → High relevance'; }
  if (semanticType === 'competitive-landscape' && !s.xLabel) { s.xLabel='Dimension X'; s.yLabel='Dimension Y'; }
  return { renderer, slide:s };
}

function resolveSlide(slide, repoRoot) {
  const reg = loadRegistry(repoRoot);
  const meta = reg.amap.get(slide.type) || legacy[slide.type];
  if (!meta) throw new Error(`unsupported semantic slide type: ${slide.type}`);
  if (slide.renderer) throw new Error('renderer override is not a public spec field');
  if (meta.status === 'DESIGNED') throw new Error(`${slide.type}: ${meta.limitation}`);
  const composition = slide.composition || meta.composition;
  const comp = reg.cmap.get(composition);
  if (!comp) throw new Error(`unknown composition: ${composition}`);
  const effective = Object.assign({}, meta, comp ? {renderer: comp.renderer} : {}, {composition});
  return normalizeSlide(slide, effective);
}

module.exports = { loadRegistry, resolveSlide, normalizeSlide };
