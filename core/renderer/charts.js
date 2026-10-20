function createChartHelper(style) {
  const T = style.tokens;
  const F = style.font;
  const gridStyle = style.style.chart_grid === 'none' ? 'none' : 'solid';
  function options(overrides = {}) {
    const { palette, grid, ...rest } = overrides;
    return {
      fontFace: F.cjk,
      chartColors: palette || T.chart.palette,
      chartArea: { fill: { color: T.chart.background }, border: { color: T.chart.background, pt: 0 } },
      plotArea: { fill: { color: T.chart.background }, border: { color: T.chart.background, pt: 0 } },
      showTitle: false,
      titleColor: T.chart.title,
      titleFontFace: F.cjk,
      titleFontSize: F.chartSize + 2,
      showLegend: false,
      legendPos: 'b',
      legendColor: T.chart.labels,
      legendFontFace: F.cjk,
      legendFontSize: F.chartSize,
      catAxisLabelColor: T.chart.labels,
      catAxisLabelFontFace: F.cjk,
      catAxisLabelFontSize: F.chartSize,
      catAxisLabelRotate: 0,
      catAxisLineColor: T.chart.grid,
      catAxisLineShow: false,
      valAxisLabelColor: T.chart.labels,
      valAxisLabelFontFace: F.latin,
      valAxisLabelFontSize: F.chartSize,
      valAxisLineColor: T.chart.grid,
      valAxisLineShow: false,
      catGridLine: { style: 'none', color: T.chart.grid, size: 0 },
      valGridLine: { color: T.chart.grid, size: .5, style: grid === 'none' ? 'none' : (grid || gridStyle) },
      dataLabelColor: T.chart.dataLabel,
      dataLabelFontFace: F.latin,
      dataLabelFontSize: F.chartSize,
      ...rest,
    };
  }
  function categoryColors(values, highlightIndex) {
    return values.map((_,i)=>i===(highlightIndex??0)?T.chart.highlight:T.chart.neutral);
  }
  return { options, categoryColors, tokens: T };
}
// pptxgenjs 4.0.0 hardcodes a black/Arial global label block for pie/doughnut.
async function normalizeChartXml(buffer, style) {
  const JSZip = require('jszip');
  const zip = await JSZip.loadAsync(buffer);
  const names = Object.keys(zip.files).filter(name => /^ppt\/charts\/chart\d+\.xml$/.test(name));
  let changed = false;
  for (const name of names) {
    const xml = await zip.file(name).async('string');
    const next = xml
      .replace(/<a:srgbClr val="000000"\/>/g, `<a:srgbClr val="${style.tokens.chart.dataLabel}"/>`)
      .replace(/typeface="Arial"/g, `typeface="${style.font.latin}"`);
    if (next !== xml) { zip.file(name, next); changed = true; }
  }
  return changed ? zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }) : buffer;
}
module.exports = { createChartHelper, normalizeChartXml };
