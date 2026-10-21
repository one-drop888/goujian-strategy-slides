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
// pptxgenjs 4.0.0 only emits this exact hardcoded text block in the global
// c:dLbls default of pie/doughnut charts (chart XML); per-point labels and all
// series/background paints remain untouched.
const PIE_DEFAULT_LABEL_BLOCK='<a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:latin typeface="Arial"/>';
function escapeXmlAttribute(value) {
  return String(value).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
const PIE_CHART=/<c:(?:pie|doughnut)(?:3D)?Chart[ >]/;
function replaceGlobalLabel(xml, replacement, kind, labelBackground) {
  if (!PIE_CHART.test(xml)) return xml;
  const plot=xml.match(/<c:plotArea[\s\S]*?<\/c:plotArea>/);
  if(!plot) return xml;
  const plotXml=plot[0],base=plot.index;
  let out='',cursor=0;
  for(const match of plotXml.matchAll(/<c:dLbls>[\s\S]*?<\/c:dLbls>/g)) {
    const length=match[0].length;
    let block=match[0];
    if(!block.includes(PIE_DEFAULT_LABEL_BLOCK)) continue;
    if(kind==='doughnut'&&!block.includes('<c:dLblPos'))block=block.replace('<c:dLbls>','<c:dLbls><c:dLblPos val="outEnd"/>');
    if(kind==='doughnut')block=block.replace(/<c:dLbl>([\s\S]*?)<\/c:dLbl>/g,(all,inner)=>
      `<c:dLbl>${inner.replace(/<c:idx val="\d+"\/>(?!<c:dLblPos)/,'$&<c:dLblPos val="outEnd"/>')}</c:dLbl>`);
    if(kind==='doughnut'&&labelBackground)block=block.replace(/<c:spPr\/>/g,
      `<c:spPr><a:solidFill><a:srgbClr val="${escapeXmlAttribute(labelBackground)}"/></a:solidFill></c:spPr>`);
    const split=block.lastIndexOf('</c:dLbl>');
    const head=split>=0?block.slice(0,split+'</c:dLbl>'.length):'';
    const tail=split>=0?block.slice(split+'</c:dLbl>'.length):block;
    out+=xml.slice(base+cursor,base+match.index)+head+tail.split(PIE_DEFAULT_LABEL_BLOCK).join(replacement);
    cursor=match.index+length;
  }
  return out?xml.slice(0,base)+out+xml.slice(base+cursor):xml;
}
async function normalizeChartXml(buffer, style) {
  const JSZip = require('jszip');
  const zip = await JSZip.loadAsync(buffer);
  const names = Object.keys(zip.files).filter(name => /^ppt\/charts\/chart\d+\.xml$/.test(name));
  const replacement=`<a:solidFill><a:srgbClr val="${style.tokens.chart.dataLabel}"/></a:solidFill><a:latin typeface="${escapeXmlAttribute(style.font.latin)}"/>`;
  let changed = false;
  for (const name of names) {
    const xml = await zip.file(name).async('string');
    if (!xml.includes(PIE_DEFAULT_LABEL_BLOCK)) continue;
    const kind=/<c:doughnutChart[ >]/.test(xml)?'doughnut':'pie';
    const next = replaceGlobalLabel(xml,replacement,kind,style.tokens.chart.background);
    if (next===xml) continue;
    zip.file(name, next); changed = true;
  }
  return changed ? zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }) : buffer;
}
module.exports = { createChartHelper, normalizeChartXml };
