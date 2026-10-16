#!/usr/bin/env node
const fs=require('fs'),path=require('path');
const {analyze}=require('../core/analytics');
const {buildDeck}=require('../core/renderer');
async function main(){
 const [input,out]=process.argv.slice(2);if(!input||!out)throw Error('Usage: node scripts/analyze.js input.json output.pptx');
 if(!out.toLowerCase().endsWith('.pptx')||['','.spec.json','.data.json','.scene.json'].some(suffix=>path.resolve(input)===path.resolve(out+suffix)))throw Error('Use separate PPTX and sidecar outputs; never overwrite the input');
 const result=analyze(JSON.parse(fs.readFileSync(input,'utf8')));
 fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out+'.spec.json',JSON.stringify(result.spec,null,2)+'\n');
 await buildDeck(result.spec,out,{specDir:path.dirname(path.resolve(input))});result.audit.pptx_sha256=require('crypto').createHash('sha256').update(fs.readFileSync(out)).digest('hex');fs.writeFileSync(out+'.data.json',JSON.stringify(result.audit,null,2)+'\n');console.log(`PASS ${result.audit.recipe}: ${result.spec.slides.length} slides; ${result.audit.warnings.length} data notes`);
}
if(require.main===module)main().catch(e=>{console.error(e.message);process.exitCode=2;});
