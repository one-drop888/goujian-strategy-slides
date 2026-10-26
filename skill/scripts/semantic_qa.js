#!/usr/bin/env node
'use strict';
// Fixed local semantic QA runner. Accepts only declared flags and local file paths;
// it never executes build commands, renders, downloads assets or consults a network.
const fs=require('fs');
const path=require('path');
const {runSemanticQa}=require('../../core/qa/semantic');
const {assertNotInput}=require('../../core/safety/paths');
const REPO_ROOT=path.resolve(__dirname,'../..');
const FLAGS=new Set(['pptx','spec','scene','profile','plan','out','repo-root','spec-dir']);
const REQUIRED=['pptx','spec','out'];
function usage(message) {
  const text=message?`semantic_qa: ${message}`:'semantic_qa: usage error';
  process.stderr.write(`${text}\nusage: node skill/scripts/semantic_qa.js --pptx <file.pptx> --spec <spec.json> --out <report.json> [--scene <scene.json>] [--profile <id>] [--plan <plan.json>] [--repo-root <dir>] [--spec-dir <dir>]\n`);
  process.exit(2);
}
function parseArgs(argv) {
  const args={};
  for(let index=0;index<argv.length;index++) {
    const token=argv[index];
    if(!token.startsWith('--')) usage(`unexpected argument ${JSON.stringify(token)}`);
    const flag=token.slice(2);
    if(!FLAGS.has(flag)) usage(`unsupported flag ${JSON.stringify(token)}`);
    if(Object.prototype.hasOwnProperty.call(args,flag)) usage(`duplicate flag ${JSON.stringify(token)}`);
    const value=argv[++index];
    if(value==null||value.startsWith('--')||!value.trim()) usage(`flag ${JSON.stringify(token)} requires a value`);
    args[flag]=value;
  }
  for(const flag of REQUIRED) if(!args[flag]) usage(`--${flag} is required`);
  return args;
}
function readJson(file,label) {
  try { return JSON.parse(fs.readFileSync(file,'utf8')); }
  catch(error) { throw new Error(`${label} could not be read as JSON: ${error.message}`); }
}
async function main() {
  const args=parseArgs(process.argv.slice(2));
  const pptxPath=path.resolve(args.pptx),outPath=path.resolve(args.out);
  const inputs=['pptx','spec','scene','plan'].filter(k=>args[k]).map(k=>path.resolve(args[k]));
  inputs.push(pptxPath+'.scene.json');
  assertNotInput(outPath,'Semantic QA output',inputs);
  const spec=readJson(path.resolve(args.spec),'--spec');
  const assets=(spec.assets||[]).filter(asset=>asset?.path).map(asset=>path.resolve(args['spec-dir']||path.dirname(path.resolve(args.spec)),asset.path));
  if(args.profile&&fs.existsSync(args.profile))assets.push(path.resolve(args.profile));
  assertNotInput(outPath,'Semantic QA output',assets);
  let report;
  try {
    const plan=args.plan?readJson(path.resolve(args.plan),'--plan'):null;
    report=await runSemanticQa({
      pptxPath,
      spec,
      repoRoot:path.resolve(args['repo-root']||REPO_ROOT),
      profileRef:args.profile||null,
      specDir:path.resolve(args['spec-dir']||path.dirname(path.resolve(args.spec))),
      scenePath:args.scene?path.resolve(args.scene):null,
      plan,
    });
  } catch(error) {
    report={status:'FAIL',pptx_sha256:null,checks:{SEMANTIC_QA_RUN:{status:'FAIL',mode:'typed',errors:[error.message]}},
      errors:[error.message],warnings:[],boundaries:{visual_review:'NOT_RUN',source_truth:'NOT_AUTHENTICATED',aesthetic_judgment:'NOT_RUN'}};
  }
  report.artifacts={...(report.artifacts||{}),semantic_report:outPath};
  fs.mkdirSync(path.dirname(outPath),{recursive:true});
  fs.writeFileSync(outPath,JSON.stringify(report,null,2)+'\n');
  process.stdout.write(`${JSON.stringify({status:report.status,pptx_sha256:report.pptx_sha256,report:outPath,errors:report.errors||[]})}\n`);
  process.exit(report.status==='FAIL'?1:0);
}
main().catch(error=>{
  process.stderr.write(`semantic_qa: ${error.stack||error.message}\n`);
  process.exit(3);
});
