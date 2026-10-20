const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const JSZip=require('jszip');
const {resolveSlide}=require('../composition/resolver');
const {close}=require('./calculations');
const {REPORT_PART}=require('./embed');

function expectedCharts(spec,repoRoot) {
  const charts=[];
  for(const raw of spec.slides||[]) {
    const {renderer,slide}=resolveSlide(raw,repoRoot);
    if(renderer==='chart') charts.push({slide:raw.type,series:(slide.series||[]).map(series=>series.values)});
    if(slide.dashboard) charts.push({slide:'dashboard',series:(slide.dashboard.series||[]).map(series=>series.values)});
    if(renderer==='multimodal') for(const panel of slide.panels||[]) {
      if(panel.kind==='chart') charts.push({slide:'panel-chart',series:(panel.series||[]).map(series=>series.values)});
    }
  }
  return charts;
}

function chartNumbers(xml) {
  const values=[];
  for(const block of xml.matchAll(/<c:val[ >][\s\S]*?<\/c:val>/g)) {
    for(const match of block[0].matchAll(/<c:v>([^<]*)<\/c:v>/g)) {
      const number=Number(match[1]);
      if(Number.isFinite(number)) values.push(number);
    }
  }
  return values;
}
function unescapeXml(value) {
  return value.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&amp;/g,'&');
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

async function verifyBuiltDeck(pptxPath,spec,reasoning,repoRoot) {
  const zip=await JSZip.loadAsync(fs.readFileSync(pptxPath));
  const chartNames=Object.keys(zip.files).filter(name=>/^ppt\/charts\/chart\d+\.xml$/.test(name))
    .sort((a,b)=>Number(a.match(/(\d+)/)[1])-Number(b.match(/(\d+)/)[1]));
  const expected=expectedCharts(spec,repoRoot);
  if(chartNames.length!==expected.length) throw new Error(`chart cache count ${chartNames.length} does not match spec ${expected.length}`);
  const charts=[];
  for(const [index,name] of chartNames.entries()) {
    const actual=chartNumbers(await zip.file(name).async('string'));
    const wanted=expected[index].series.flat();
    if(actual.length!==wanted.length) throw new Error(`chart ${index+1} value count ${actual.length} does not match spec ${wanted.length}`);
    for(let i=0;i<wanted.length;i++) if(!close(actual[i],wanted[i])) throw new Error(`chart ${index+1} value ${actual[i]} does not match spec ${wanted[i]}`);
    charts.push({part:name,values:actual});
  }
  const slideIds=[];
  for(const [index,slide] of (reasoning.slides||[]).entries()) {
    const text=await notesForSlide(zip,index+1);
    if(!text.includes(`[reasoning:${slide.id}]`)) throw new Error(`slide ${index+1} notes are missing reasoning id ${slide.id}`);
    for(const claimId of slide.claim_ids||[]) if(!text.includes(claimId)) throw new Error(`slide ${index+1} notes are missing claim ${claimId}`);
    slideIds.push(slide.id);
  }
  const reportFile=zip.file(REPORT_PART);
  if(!reportFile) throw new Error(`embedded reasoning report ${REPORT_PART} is missing`);
  const embeddedText=await reportFile.async('string');
  const embedded=JSON.parse(embeddedText);
  if(embedded.plan_sha256!==reasoning.plan_sha256) throw new Error('embedded report plan hash does not match');
  if(embedded.spec_sha256!==reasoning.spec_sha256) throw new Error('embedded report spec hash does not match');
  if(reasoning.report_sha256) {
    const actual=crypto.createHash('sha256').update(Buffer.from(embeddedText)).digest('hex');
    if(actual!==reasoning.report_sha256) throw new Error('embedded report bytes do not match report_sha256');
  }
  return {status:'PASS',charts:charts.length,notes:slideIds.length,embedded_report:REPORT_PART};
}

module.exports={verifyBuiltDeck,expectedCharts,chartNumbers};
