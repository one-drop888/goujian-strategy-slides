const JSZip=require('jszip');
// Office renders a filled area band across a blank, so area charts cannot show a true gap.
const NEGATIVE_AXIS_HEADROOM=0.10;
function niceAxisStep(span) {
  const target=span/5;
  const magnitude=Math.pow(10,Math.floor(Math.log10(target)));
  let best=magnitude;
  for(const multiplier of [1,2,2.5,5,10]) {
    const candidate=multiplier*magnitude;
    if(Math.abs(candidate-target)<Math.abs(best-target)) best=candidate;
  }
  return best;
}
function valueAxisMin(values, explicitMin) {
  if (explicitMin != null) {
    const declared=Number(explicitMin);
    if (!Number.isFinite(declared)) throw new Error('explicit value-axis minimum must be finite');
    return declared;
  }
  const finite=(values||[]).filter(value=>typeof value==='number'&&Number.isFinite(value));
  if (!finite.length) return undefined;
  const min=Math.min(...finite);
  if (min>=0) return 0;
  const max=Math.max(...finite);
  const span=Math.max(max,0)-min;
  const step=niceAxisStep(span);
  const padded=min-span*NEGATIVE_AXIS_HEADROOM;
  const snapped=Math.floor(padded/step)*step;
  if (![span,step,padded,snapped].every(Number.isFinite)||!(snapped<min)) {
    throw new Error('chart values are too large to compute a finite value-axis minimum below every real value; split or rescale the values explicitly');
  }
  return Number(snapped.toPrecision(15));
}
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
      catAxisLabelPos: 'low',
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
    return values.map((_,i)=>highlightIndex!=null&&i===highlightIndex?T.chart.highlight:T.chart.neutral);
  }
  return { options, categoryColors, valueAxisMin, tokens: T };
}
function labelOptions(kind, strategy, defaults = {}) {
  const pieLike = ['pie', 'doughnut'].includes(String(kind).toLowerCase());
  const base = { showValue: false, showCatName: false, showSerName: false, showPercent: false, showLabel: false };
  if (strategy == null || strategy === 'auto') return defaults;
  if (strategy === 'none') return base;
  if (strategy === 'value') return { ...base, showValue: true };
  if (strategy === 'category') return { ...base, showCatName: true };
  if (strategy === 'category_value') return { ...base, showValue: true, showCatName: true };
  if (strategy === 'percent') {
    if (!pieLike) throw new Error('label_strategy percent is only supported for pie/doughnut charts');
    return { ...base, showPercent: true, showLabel: true };
  }
  throw new Error(`unsupported label_strategy ${strategy}`);
}
// A pie share is a fraction computed by Office, unlike a canonical percent-point series value.
function dataLabelNumberFormat(kind,strategy,numberFormat) {
  if(['pie','doughnut'].includes(String(kind).toLowerCase())&&(strategy==null||['auto','percent'].includes(strategy))) {
    const decimals=(String(numberFormat).match(/0\.(0+)/)||[])[1]||'';
    return `0${decimals?'.'+decimals:''}%`;
  }
  return numberFormat;
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
function setShowValues(block,enabled) {
  return block.replace(/<c:showVal val="[01]"\/>/g,`<c:showVal val="${enabled?1:0}"/>`);
}
function seriesLabelParts(inner) {
  return {
    numFmt:(inner.match(/<c:numFmt[^>]*\/>/)||[])[0]||'',
    txPr:(inner.match(/<c:txPr>[\s\S]*?<\/c:txPr>/)||[])[0]||'',
  };
}
function applyBlankPolicy(xml,plan) {
  if(!plan?.has_missing) return xml;
  if(/<c:dispBlanksAs\b/.test(xml)) return xml.replace(/<c:dispBlanksAs val="[^"]*"\/>/,'<c:dispBlanksAs val="gap"/>');
  return xml.replace('</c:chart>','<c:dispBlanksAs val="gap"/></c:chart>');
}
function applyLabelLayout(xml,plan) {
  const layout=plan?.label_layout;
  if(!layout||!Array.isArray(layout.series)||!layout.series.length) return xml;
  let seriesIndex=-1;
  const marked=xml.replace(/<c:ser[ >][\s\S]*?<\/c:ser>/g,block=>{
    seriesIndex+=1;
    const spec=layout.series[seriesIndex];
    if(!spec) return block;
    const labels=block.match(/(<c:dLbls>)([\s\S]*?)(<\/c:dLbls>)/);
    if(!labels) return block;
    const inner=layout.mode==='all'?labels[2]:setShowValues(labels[2],false);
    if(layout.mode==='all') {
      const positioned=/<c:dLblPos\b/.test(inner)
        ? inner.replace(/<c:dLblPos val="[^"]+"\/>/,`<c:dLblPos val="${spec.position}"/>`)
        : inner.replace(/<c:showLegendKey\b/,`<c:dLblPos val="${spec.position}"/><c:showLegendKey`);
      return block.replace(labels[0],`${labels[1]}${positioned}${labels[3]}`);
    }
    if(spec.index==null||spec.index<0) return block.replace(labels[0],`${labels[1]}${inner}${labels[3]}`);
    const parts=seriesLabelParts(labels[2]);
    const point=`<c:dLbl><c:idx val="${spec.index}"/>${parts.numFmt}${parts.txPr}<c:dLblPos val="${spec.position}"/><c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/><c:showLeaderLines val="0"/></c:dLbl>`;
    return block.replace(labels[0],`${labels[1]}${point}${inner}${labels[3]}`);
  });
  if(layout.mode!=='end') return marked;
  const last=marked.lastIndexOf('</c:ser>');
  if(last<0) return marked;
  const cut=last+'</c:ser>'.length;
  return marked.slice(0,cut)+marked.slice(cut).replace(/<c:showVal val="1"\/>/g,'<c:showVal val="0"/>');
}
function excelColumn(index) {
  let text='';
  for(let value=index+1;value>0;value=Math.floor((value-1)/26)) text=String.fromCharCode(65+(value-1)%26)+text;
  return text;
}
function chartSeriesValues(xml) {
  return [...xml.matchAll(/<c:ser[ >][\s\S]*?<\/c:ser>/g)].map(match=>{
    const valueBlock=(match[0].match(/<c:val>[\s\S]*?<\/c:val>/)||[])[0]||'';
    return [...valueBlock.matchAll(/<c:v>([^<]*)<\/c:v>/g)]
      .map(item=>item[1].trim()===''?null:Number(item[1]));
  });
}
async function applyWorkbookValues(pptxZip, chartName, chartXml) {
  const seriesValues=chartSeriesValues(chartXml);
  if(!seriesValues.length||seriesValues.every(values=>!values.length)) return false;
  const relName=`ppt/charts/_rels/${chartName.split('/').pop()}.rels`;
  const relFile=pptxZip.file(relName);
  if(!relFile) return false;
  const rels=await relFile.async('string');
  const target=(rels.match(/Target="\.\.\/embeddings\/([^"]+\.xlsx)"/)||[])[1];
  if(!target) return false;
  const embedding=`ppt/embeddings/${target}`;
  const embedFile=pptxZip.file(embedding);
  if(!embedFile) return false;
  const workbook=await JSZip.loadAsync(await embedFile.async('nodebuffer'));
  const sheetFile=workbook.file('xl/worksheets/sheet1.xml');
  if(!sheetFile) return false;
  let sheet=await sheetFile.async('string');
  const header=(sheet.match(/<row r="1"[\s\S]*?<\/row>/)||[])[0]||'';
  const labelColumns=Math.max(1,[...header.matchAll(/<c r="[A-Z]+1"[^>]*>[\s\S]*?<\/c>/g)]
    .filter(match=>/<v>\s*0\s*<\/v>/.test(match[0])).length);
  let changed=false;
  for(const [seriesIndex,values] of seriesValues.entries()) {
    const column=excelColumn(labelColumns+seriesIndex);
    for(const [rowIndex,value] of values.entries()) {
      if(value!=null&&!Number.isFinite(value)) continue;
      const ref=`${column}${rowIndex+2}`;
      const cell=new RegExp(`<c r="${ref}"(?:\\s[^>]*)?(?:\\/>|>[\\s\\S]*?<\\/c>)`);
      if(!cell.test(sheet)) continue;
      const replacement=`<c r="${ref}"><v>${value==null?'':value}</v></c>`;
      const next=sheet.replace(cell,replacement);
      if(next!==sheet){sheet=next;changed=true;}
    }
  }
  if(!changed) return false;
  workbook.file('xl/worksheets/sheet1.xml',sheet);
  pptxZip.file(embedding,await workbook.generateAsync({type:'nodebuffer',compression:'DEFLATE'}));
  return true;
}
function applySeriesStyles(xml, plan) {
  if (!plan || !Array.isArray(plan.series) || !plan.series.length) return xml;
  let index = -1;
  return xml.replace(/<c:ser[ >][\s\S]*?<\/c:ser>/g, block => {
    index += 1;
    const style = plan.series[index];
    if (!style) return block;
    const kind = String(plan.kind || '').toLowerCase();
    const color = /^[0-9A-Fa-f]{6}$/.test(String(style.color || '')) ? style.color.toUpperCase() : null;
    if (!color) return block;
    const spMatch = block.match(/<c:spPr>[\s\S]*?<\/c:spPr>/);
    if (spMatch) {
      let sp = spMatch[0].replace(/<a:srgbClr val="[0-9A-Fa-f]{6}"\/>/g, `<a:srgbClr val="${color}"/>`);
      if (kind === 'line' && style.dash) {
        sp = sp.replace(/<a:prstDash val="[^"]+"\/>/g, `<a:prstDash val="${style.dash}"/>`);
        if (style.dash !== 'solid' && !sp.includes('<a:prstDash')) {
          sp = sp.replace(/(<a:ln\b[^>]*>)([\s\S]*?)(<\/a:ln>)/,
            (all, open, inner, close) => `${open}${inner}<a:prstDash val="${style.dash}"/>${close}`);
        }
      }
      block = block.replace(spMatch[0], sp);
    }
    if (kind === 'line') {
      if (style.symbol) block = block.replace(/<c:symbol val="[^"]+"\/>/, `<c:symbol val="${style.symbol}"/>`);
      if (style.size) block = block.replace(/<c:size val="\d+"\/>/, `<c:size val="${style.size}"/>`);
      block = block.replace(/(<c:marker>[\s\S]*?<\/c:marker>)/, marker => marker.replace(/<a:srgbClr val="[0-9A-Fa-f]{6}"\/>/g, `<a:srgbClr val="${color}"/>`));
    }
    return block;
  });
}
async function normalizeChartXml(buffer, style, chartPlans = [], options = {}) {
  const zip = await JSZip.loadAsync(buffer);
  const names = Object.keys(zip.files).filter(name => /^ppt\/charts\/chart\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/(\d+)/)[1])-Number(b.match(/(\d+)/)[1]));
  if (options.strict && chartPlans.length !== names.length) {
    throw new Error(`chart plan/XML mismatch: ${chartPlans.length} planned native charts but ${names.length} were written`);
  }
  const replacement=`<a:solidFill><a:srgbClr val="${style.tokens.chart.dataLabel}"/></a:solidFill><a:latin typeface="${escapeXmlAttribute(style.font.latin)}"/>`;
  let changed = false;
  for (const [index,name] of names.entries()) {
    let xml = await zip.file(name).async('string');
    let next = xml;
    if (xml.includes(PIE_DEFAULT_LABEL_BLOCK)) {
      const kind=/<c:doughnutChart[ >]/.test(xml)?'doughnut':'pie';
      next = replaceGlobalLabel(xml,replacement,kind,style.tokens.chart.background);
    }
    next = applyBlankPolicy(next, chartPlans[index]);
    next = applySeriesStyles(next, chartPlans[index]);
    next = applyLabelLayout(next, chartPlans[index]);
    const xmlChanged = next !== xml;
    if (xmlChanged) zip.file(name, next);
    if (xmlChanged || await applyWorkbookValues(zip, name, next)) changed = true;
  }
  return changed ? zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }) : buffer;
}
module.exports = {dataLabelNumberFormat, createChartHelper, normalizeChartXml, applySeriesStyles, applyBlankPolicy, applyLabelLayout, labelOptions };
