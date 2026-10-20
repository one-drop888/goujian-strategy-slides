const JSZip=require('jszip');
const REPORT_PART='docProps/goujian-reasoning.json';

function serializeReasoningReport(report) {
  return JSON.stringify(report,null,2)+'\n';
}
async function embedReasoningReport(buffer,report) {
  const zip=await JSZip.loadAsync(buffer);
  zip.file(REPORT_PART,serializeReasoningReport(report));
  let types=await zip.file('[Content_Types].xml').async('string');
  if(!types.includes(`/${REPORT_PART}`)) {
    types=types.replace('</Types>',`<Override PartName="/${REPORT_PART}" ContentType="application/json"/></Types>`);
    zip.file('[Content_Types].xml',types);
  }
  return zip.generateAsync({type:'nodebuffer',compression:'DEFLATE'});
}

module.exports={embedReasoningReport,serializeReasoningReport,REPORT_PART};
