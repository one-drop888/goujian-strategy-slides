'use strict';
// Read-only native PPTX/XLSX evidence. This module never decides whether a deck is
// trustworthy; it exposes what the serialized package actually contains.
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const JSZip=require('jszip');

const CHART_PART=/^ppt\/charts\/chart\d+\.xml$/;
const DEFAULT_REPORT_PART='docProps/goujian-reasoning.json';

function sha256(value) { return crypto.createHash('sha256').update(value).digest('hex'); }
function normalizeText(value) { return String(value??'').replace(/\s+/g,' ').trim(); }
function unescapeXml(value) {
  return String(value??'').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&amp;/g,'&');
}
function escapeXml(value) {
  return String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;');
}
function blocks(xml,tag) {
  return [...String(xml??'').matchAll(new RegExp(`<c:${tag}[ >][\\s\\S]*?</c:${tag}>`,'g'))].map(match=>match[0]);
}
function aBlocks(xml,tag) {
  return [...String(xml??'').matchAll(new RegExp(`<a:${tag}[ >][\\s\\S]*?</a:${tag}>`,'g'))].map(match=>match[0]);
}
function block(xml,tag) { return blocks(xml,tag)[0]||''; }
function attrs(fragment) {
  const result={};
  for(const match of String(fragment??'').matchAll(/([A-Za-z_:][\w:.-]*)\s*=\s*"([^"]*)"/g)) result[match[1]]=unescapeXml(match[2]);
  return result;
}
function attrValue(fragment,name,fallback=null) {
  const match=String(fragment??'').match(new RegExp(`(?:^|\\s)${name.replace(/[:]/g,'\\:')}\\s*=\\s*"([^"]*)"`));
  return match?unescapeXml(match[1]):fallback;
}
function chartTextValues(fragment) {
  return [...String(fragment??'').matchAll(/<c:v>([^<]*)<\/c:v>/g)].map(match=>unescapeXml(match[1]));
}
function chartSeriesNames(xml) {
  return blocks(xml,'ser').map(series=>{
    const tx=block(series,'tx');
    return tx?chartTextValues(tx)[0]??null:null;
  });
}
function chartCategoryLabels(xml) {
  return blocks(xml,'ser').map(series=>{
    const cat=block(series,'cat');
    return cat?chartTextValues(cat):[];
  });
}
const MAX_NATIVE_POINTS=10000;
function numericPoints(fragment,tag='numCache') {
  const cache=block(fragment,tag)||String(fragment??'');
  const structureErrors=[];
  const countMatch=cache.match(/<c:ptCount\b[^>]*\bval\s*=\s*"([^"]*)"/);
  let declaredCount=null;
  if(countMatch) {
    const raw=unescapeXml(countMatch[1]);
    if(!/^(0|[1-9]\d*)$/.test(raw)) structureErrors.push(`ptCount ${JSON.stringify(raw)} is not a nonnegative integer`);
    else {
      const parsed=Number(raw);
      if(!Number.isSafeInteger(parsed)) structureErrors.push(`ptCount ${raw} exceeds the safe integer range`);
      else if(parsed>MAX_NATIVE_POINTS) structureErrors.push(`ptCount ${parsed} exceeds the bounded maximum ${MAX_NATIVE_POINTS}`);
      else declaredCount=parsed;
    }
    if(structureErrors.length&&declaredCount===null) structureErrors.push('native point count is untrusted; the cache cannot certify its own length');
  }
  const points=new Map();
  let capped=false;
  for(const match of cache.matchAll(/<c:pt\b([^>]*)>([\s\S]*?)<\/c:pt>/g)) {
    if(points.size>=MAX_NATIVE_POINTS) { if(!capped) structureErrors.push(`native cache contains more than ${MAX_NATIVE_POINTS} point elements`); capped=true; break; }
    const rawIndex=attrValue(`<c:pt${match[1]}>`,'idx',null);
    if(rawIndex==null||!/^(0|[1-9]\d*)$/.test(rawIndex)) {
      structureErrors.push(`native point index ${JSON.stringify(rawIndex)} is not a nonnegative integer`);
      continue;
    }
    const index=Number(rawIndex);
    if(!Number.isSafeInteger(index)) {
      structureErrors.push(`native point index ${rawIndex} exceeds the safe integer range`);
      continue;
    }
    if(declaredCount!==null&&index>=declaredCount) {
      structureErrors.push(`native point index ${index} is outside declared ptCount ${declaredCount}`);
      continue;
    }
    if(points.has(index)) {
      structureErrors.push(`native point index ${index} is duplicated`);
      continue;
    }
    const valueMatch=match[2].match(/<c:v>([\s\S]*?)<\/c:v>/);
    points.set(index,valueMatch?unescapeXml(valueMatch[1]):'');
  }
  const count=declaredCount==null?points.size:declaredCount;
  const values=[],rawValues=[],invalid=[];
  for(let index=0;index<count;index++) {
    const text=points.get(index);
    rawValues.push(text??null);
    if(text==null||text==='') { values.push(null); continue; }
    const number=Number(text);
    if(Number.isFinite(number)) values.push(number);
    else { values.push(null); invalid.push({index,text}); }
  }
  const formatMatch=cache.match(/<c:formatCode>([^<]*)<\/c:formatCode>/)||cache.match(/<c:numFmt[^>]*\bformatCode="([^"]*)"/);
  return {values,raw_values:rawValues,invalid,format_code:formatMatch?unescapeXml(formatMatch[1]):null,
    pt_count:declaredCount,structure_errors:structureErrors};
}
function chartNumbers(xml) {
  const values=[];
  for(const valueBlock of blocks(xml,'val')) {
    const parsed=numericPoints(valueBlock);
    for(const [index,value] of parsed.values.entries()) {
      if(value!==null) { values.push(value); continue; }
      const raw=parsed.raw_values[index];
      if(raw==null||raw==='') values.push(null);
      else values.push({invalid:raw});
    }
  }
  return values;
}
function tableRows(xml) {
  return aBlocks(xml,'tbl').map(table=>aBlocks(table,'tr').map(row=>aBlocks(row,'tc').map(cell=>
    unescapeXml([...cell.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>match[1]).join('')))));
}
function slideTexts(xml) {
  return [...String(xml??'').matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>unescapeXml(match[1]));
}
function intrinsicColor(fragment) {
  const srgb=String(fragment??'').match(/<a:srgbClr[^>]*\bval="([0-9A-Fa-f]{6})"/);
  if(srgb) return srgb[1].toUpperCase();
  const scheme=String(fragment??'').match(/<a:schemeClr[^>]*\bval="([^"]+)"/);
  return scheme?`scheme:${scheme[1]}`:null;
}
function parseSeries(fragment,index) {
  const withoutPoints=String(fragment).replace(/<c:dPt\b[\s\S]*?<\/c:dPt>/g,'');
  const spPr=block(withoutPoints,'spPr');
  const line=block(spPr,'ln')||aBlocks(spPr,'ln')[0]||'';
  const marker=block(fragment,'marker');
  const labels=block(fragment,'dLbls');
  const tx=block(fragment,'tx');
  const valueBlock=block(fragment,'val');
  const catBlock=block(fragment,'cat');
  const values=numericPoints(valueBlock);
  const categoryLevels=catBlock?blocks(catBlock,'lvl').map(level=>chartTextValues(level)):[];
  const categories=categoryLevels.length?categoryLevels.at(-1):(catBlock?chartTextValues(catBlock):[]);
  const pointColors=[];
  for(const point of blocks(fragment,'dPt')) {
    const idxMatch=point.match(/<c:idx[^>]*\bval="(\d+)"/);
    const color=intrinsicColor(block(point,'spPr'));
    if(idxMatch&&color) pointColors.push({index:Number(idxMatch[1]),color});
  }
  const idxTag=fragment.match(/<c:idx[^>]*>/);
  const orderTag=fragment.match(/<c:order[^>]*>/);
  const symbolTag=marker.match(/<c:symbol[^>]*>/);
  const sizeTag=marker.match(/<c:size[^>]*>/);
  const dashTag=line.match(/<a:prstDash[^>]*>/);
  return {
    index,
    idx:idxTag?Number(attrValue(idxTag[0],'val',index)):index,
    order:orderTag?Number(attrValue(orderTag[0],'val',index)):index,
    name:tx?chartTextValues(tx)[0]??null:null,
    name_formula:refFormula(tx),
    values:values.values,
    raw_values:values.raw_values,
    invalid_values:values.invalid,
    pt_count:values.pt_count,
    structure_errors:values.structure_errors,
    value_formula:refFormula(valueBlock),
    cache_format_code:values.format_code,
    category_labels:categories,
    category_levels:categoryLevels,
    category_formula:refFormula(catBlock),
    color:intrinsicColor(spPr),
    point_colors:pointColors,
    dash:line?(dashTag?attrValue(dashTag[0],'val','solid'):'solid'):null,
    line_width:line?Number(attrValue(line,'w',0))||null:null,
    marker:marker?{
      symbol:symbolTag?attrValue(symbolTag[0],'val',null):null,
      size:sizeTag?Number(attrValue(sizeTag[0],'val',0))||null:null,
    }:null,
    label_format:labels?attrValue(labels.match(/<c:numFmt[^>]*>/)?.[0]||'','formatCode',null):null,
    show_value:labels?attrValue(labels.match(/<c:showVal[^>]*>/)?.[0]||'','val',null):null,
    show_category:labels?attrValue(labels.match(/<c:showCatName[^>]*>/)?.[0]||'','val',null):null,
    show_series_name:labels?attrValue(labels.match(/<c:showSerName[^>]*>/)?.[0]||'','val',null):null,
    show_percent:labels?attrValue(labels.match(/<c:showPercent[^>]*>/)?.[0]||'','val',null):null,
    label_position:labels?attrValue(labels.match(/<c:dLblPos[^>]*>/)?.[0]||'','val',null):null,
  };
}
function refFormula(fragment) {
  const match=String(fragment??'').match(/<c:f>([\s\S]*?)<\/c:f>/);
  return match?unescapeXml(match[1]):null;
}
function parseChartXml(xml) {
  const kinds=[['barChart','bar'],['lineChart','line'],['areaChart','area'],['pieChart','pie'],['doughnutChart','doughnut'],['scatterChart','scatter'],['radarChart','radar']];
  const kind=kinds.find(([tag])=>block(xml,tag))?.[1]||'unknown';
  const kindBlock=block(xml,`${kind}Chart`);
  const valAxis=block(xml,'valAx');
  const catAxis=block(xml,'catAx');
  const scaling=block(valAxis,'scaling');
  const bound=name=>{
    const match=String(scaling||'').match(new RegExp(`<c:${name}\\b[^>]*\\bval\\s*=\\s*"([^"]*)"`));
    if(!match) return {present:false,valid:false,value:null,raw:null};
    const raw=unescapeXml(match[1]);
    const value=Number(raw);
    const valid=raw!==''&&Number.isFinite(value);
    return {present:true,valid,value:valid?value:null,raw};
  };
  const axisMin=bound('min'),axisMax=bound('max');
  const legend=block(xml,'legend');
  const withoutSeries=xml.replace(/<c:ser[\s>][\s\S]*?<\/c:ser>/g,'');
  const globalLabels=block(withoutSeries,'dLbls');
  const deletions=[...legend.matchAll(/<c:legendEntry>([\s\S]*?)<\/c:legendEntry>/g)]
    .filter(([,fragment])=>attrValue(fragment,'delete','0')==='1')
    .map(([,fragment])=>Number(attrValue(fragment,'idx','0')));
  const series=blocks(xml,'ser').map(parseSeries);
  return {
    kind,
    bar_dir:attrValue(kindBlock.match(/<c:barDir[^>]*>/)?.[0]||'','val',null),
    grouping:attrValue(kindBlock.match(/<c:grouping[^>]*>/)?.[0]||'','val',null),
    disp_blanks_as:attrValue(xml.match(/<c:dispBlanksAs[^>]*>/)?.[0]||'','val',null),
    series,
    series_names:chartSeriesNames(xml),
    category_labels:chartCategoryLabels(xml),
    value_axis:valAxis?{
      min:axisMin.value,max:axisMax.value,
      min_present:axisMin.present,min_valid:axisMin.valid,min_raw:axisMin.raw,
      max_present:axisMax.present,max_valid:axisMax.valid,max_raw:axisMax.raw,
      orientation:attrValue(valAxis.match(/<c:orientation[^>]*>/)?.[0]||'','val',null),
    }:null,
    value_axis_format:valAxis?attrValue((valAxis.match(/<c:numFmt[^>]*>/)?.[0])||'','formatCode',null):null,
    category_axis_format:catAxis?attrValue((catAxis.match(/<c:numFmt[^>]*>/)?.[0])||'','formatCode',null):null,
    global_label_format:globalLabels?attrValue((globalLabels.match(/<c:numFmt[^>]*>/)?.[0])||'','formatCode',null):null,
    legend:{present:Boolean(legend),position:attrValue(legend.match(/<c:legendPos[^>]*>/)?.[0]||'','val',null),deletions},
  };
}

function columnNumber(name) {
  let value=0;
  for(const character of String(name).toUpperCase()) value=value*26+character.charCodeAt(0)-64;
  return value;
}
function columnName(number) {
  let name='';
  while(number>0) { const remainder=(number-1)%26; name=String.fromCharCode(65+remainder)+name; number=Math.floor((number-1)/26); }
  return name;
}
function parseReference(text) {
  const match=String(text??'').trim().replace(/^'|'$/g,'').match(/^\$?([A-Za-z]+)\$?(\d+)(?::\$?([A-Za-z]+)\$?(\d+))?$/);
  if(!match) return null;
  const start={col:columnNumber(match[1]),row:Number(match[2])};
  const end=match[3]?{col:columnNumber(match[3]),row:Number(match[4])}:{...start};
  return {start:{col:Math.min(start.col,end.col),row:Math.min(start.row,end.row)},end:{col:Math.max(start.col,end.col),row:Math.max(start.row,end.row)}};
}
function parseFormulaRange(formula) {
  if(!formula) return null;
  const bang=String(formula).lastIndexOf('!');
  const sheet=bang>=0?String(formula).slice(0,bang).replace(/^'|'$/g,''):null;
  const reference=bang>=0?String(formula).slice(bang+1):String(formula);
  const range=parseReference(reference);
  return range?{sheet,...range}:null;
}
function rangeCells(cells,range) {
  if(!range) return [];
  const rows=range.end.row-range.start.row+1,columns=range.end.col-range.start.col+1;
  const values=[];
  const read=(col,row)=>cells.get(`${columnName(col)}${row}`)?.value??null;
  if(rows===1&&columns>1) { for(let col=range.start.col;col<=range.end.col;col++) values.push(read(col,range.start.row)); }
  else { for(let col=range.start.col;col<=range.end.col;col++) for(let row=range.start.row;row<=range.end.row;row++) values.push(read(col,row)); }
  return values;
}
function parseSharedStrings(xml) {
  if(!xml) return [];
  return [...String(xml).matchAll(/<si\b[\s\S]*?<\/si>/g)].map(([item])=>
    unescapeXml([...item.matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map(match=>match[1]).join('')));
}
function parseSheetCells(xml,sharedStrings=[]) {
  const cells=new Map();
  for(const match of String(xml??'').matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
    const attributes=attrs(match[1]);
    if(!attributes.r) continue;
    const body=match[2]||'';
    const type=attributes.t||'n';
    const valueMatch=body.match(/<v\b[^>]*>([\s\S]*?)<\/v>/);
    const raw=valueMatch?unescapeXml(valueMatch[1]):null;
    let value=null,kind='number';
    if(type==='s') { value=sharedStrings[Number(raw)]??null; kind='string'; }
    else if(type==='inlineStr') { value=unescapeXml([...body.matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map(item=>item[1]).join('')); kind='string'; }
    else if(type==='str') { value=raw; kind='string'; }
    else if(type==='b') { value=raw==='1'; kind='boolean'; }
    else if(type==='e') { value=null; kind='error'; }
    else if(raw==null||raw==='') { value=null; kind='blank'; }
    else { const number=Number(raw); value=Number.isFinite(number)?number:null; kind=Number.isFinite(number)?'number':(raw===''?'blank':'text'); }
    cells.set(attributes.r,{value,kind,raw,type});
  }
  return cells;
}
function relationshipRows(xml) {
  return [...String(xml??'').matchAll(/<Relationship\b([^>]*?)\/?>/g)].map(match=>attrs(match[1]));
}
async function firstWorksheetPart(book) {
  const workbookFile=book.file('xl/workbook.xml');
  if(workbookFile) {
    const workbook=await workbookFile.async('string');
    const sheetMatch=workbook.match(/<sheet\b[^>]*>/);
    const id=sheetMatch?attrValue(sheetMatch[0],'r:id',null):null;
    const relsFile=book.file('xl/_rels/workbook.xml.rels');
    if(id&&relsFile) {
      const rels=relationshipRows(await relsFile.async('string')).find(row=>row.Id===id);
      if(rels?.Target) {
        const target=rels.Target.startsWith('/')?rels.Target.slice(1):path.posix.normalize(path.posix.join('xl',rels.Target));
        if(book.file(target)) return target;
      }
    }
  }
  if(book.file('xl/worksheets/sheet1.xml')) return 'xl/worksheets/sheet1.xml';
  return Object.keys(book.files).find(name=>/^xl\/worksheets\/sheet\d+\.xml$/.test(name))||null;
}
async function readChartWorkbook(zip,chartPart,chart) {
  const relPath=path.posix.join(path.posix.dirname(chartPart),'_rels',`${path.posix.basename(chartPart)}.rels`);
  const relFile=zip.file(relPath);
  if(!relFile) return {status:'NOT_RUN',reason:`no relationships part for ${chartPart}`};
  const relationships=relationshipRows(await relFile.async('string'));
  const rel=relationships.find(row=>/\/package$/.test(row.Type||'')||/embeddings\//.test(row.Target||''));
  if(!rel?.Target) return {status:'NOT_RUN',reason:'chart has no embedded workbook'};
  const target=rel.Target.startsWith('/')?rel.Target.slice(1):path.posix.normalize(path.posix.join(path.posix.dirname(chartPart),rel.Target));
  const workbookFile=zip.file(target);
  if(!workbookFile) return {status:'FAIL',reason:`embedded workbook ${target} is missing`,part:target};
  const book=await JSZip.loadAsync(await workbookFile.async('nodebuffer'));
  const sheetPart=await firstWorksheetPart(book);
  if(!sheetPart) return {status:'FAIL',reason:'embedded workbook has no worksheet',part:target};
  const [sheetXml,sharedStringsXml]=await Promise.all([
    book.file(sheetPart).async('string'),
    book.file('xl/sharedStrings.xml')?.async('string')??Promise.resolve(''),
  ]);
  const sharedStrings=parseSharedStrings(sharedStringsXml);
  const cells=parseSheetCells(sheetXml,sharedStrings);
  const series=chart.series.map(item=>{
    const valueRange=parseFormulaRange(item.value_formula);
    const categoryRange=parseFormulaRange(item.category_formula);
    const nameRange=parseFormulaRange(item.name_formula);
    return {
      index:item.index,order:item.order,
      name:nameRange?rangeCells(cells,nameRange)[0]??null:null,
      values:valueRange?rangeCells(cells,valueRange):[],
      categories:categoryRange?rangeCells(cells,categoryRange):[],
      value_formula:item.value_formula,category_formula:item.category_formula,name_formula:item.name_formula,
    };
  });
  return {status:'PASS',part:target,sheet_part:sheetPart,cells,series};
}
async function notesForSlide(zip,index) {
  const relName=`ppt/slides/_rels/slide${index}.xml.rels`;
  const relFile=zip.file(relName);
  if(!relFile) return '';
  const rels=await relFile.async('string');
  const match=rels.match(/Target="([^"]*notesSlide[^"]*\.xml)"/);
  if(!match) return '';
  const target=path.posix.normalize(path.posix.join('ppt/slides',match[1]));
  const notesFile=zip.file(target);
  if(!notesFile) return '';
  const xml=await notesFile.async('string');
  return unescapeXml([...xml.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(item=>item[1]).join('\n'));
}
function slideParts(zip) {
  return Object.keys(zip.files).filter(name=>/^ppt\/slides\/slide\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/slide(\d+)\.xml/)[1])-Number(b.match(/slide(\d+)\.xml/)[1]));
}
async function loadNativeDeck(pptxPath,{workbooks=false,reportPart=DEFAULT_REPORT_PART}={}) {
  const bytes=fs.readFileSync(pptxPath);
  const zip=await JSZip.loadAsync(bytes);
  const chartNames=Object.keys(zip.files).filter(name=>CHART_PART.test(name))
    .sort((a,b)=>Number(a.match(/(\d+)/)[1])-Number(b.match(/(\d+)/)[1]));
  const charts=[];
  for(const part of chartNames) {
    const xml=await zip.file(part).async('string');
    const parsed=parseChartXml(xml);
    const workbook=workbooks?await readChartWorkbook(zip,part,parsed):null;
    charts.push({part,xml,...parsed,workbook});
  }
  let embeddedReport=null,embeddedReportText=null,embeddedReportSha256=null;
  if(reportPart&&zip.file(reportPart)) {
    embeddedReportText=await zip.file(reportPart).async('string');
    embeddedReportSha256=sha256(Buffer.from(embeddedReportText));
    try { embeddedReport=JSON.parse(embeddedReportText); } catch { embeddedReport={malformed:true}; }
  }
  return {
    pptx_sha256:sha256(bytes),
    bytes,
    zip,
    chartNames,
    charts,
    slideParts:slideParts(zip),
    embedded_report:embeddedReport,
    embedded_report_text:embeddedReportText,
    embedded_report_sha256:embeddedReportSha256,
  };
}
module.exports={
  CHART_PART,DEFAULT_REPORT_PART,
  sha256,normalizeText,unescapeXml,escapeXml,blocks,aBlocks,block,attrs,attrValue,
  chartTextValues,chartSeriesNames,chartCategoryLabels,numericPoints,chartNumbers,tableRows,slideTexts,
  parseChartXml,parseSeries,parseReference,parseFormulaRange,rangeCells,parseSharedStrings,parseSheetCells,
  readChartWorkbook,notesForSlide,slideParts,loadNativeDeck,
};
