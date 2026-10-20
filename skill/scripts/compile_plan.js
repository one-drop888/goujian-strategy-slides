#!/usr/bin/env node
const path=require('path');
const {compilePlan}=require('../../core/reasoning/compile');

const args=process.argv.slice(2),positional=[];
const options={};
for(let i=0;i<args.length;i++) {
  const arg=args[i];
  if(arg==='--out'||arg==='--spec-out'||arg==='--profile') {
    const value=args[++i];
    if(!value) { console.error(`FAIL: ${arg} requires a value`);process.exit(2); }
    if(arg==='--out') options.out=value;
    else if(arg==='--spec-out') options.specOut=value;
    else options.profile=value;
  } else if(arg==='--force') options.force=true;
  else if(arg==='--json') options.json=true;
  else if(arg.startsWith('--')) { console.error(`FAIL: unknown option ${arg}`);process.exit(2); }
  else positional.push(arg);
}
if(positional.length!==1) {
  console.error('usage: compile_plan.js plan.json [--out deck.pptx] [--spec-out deck.spec.json] [--profile id-or-path] [--force] [--json]');
  process.exit(2);
}
compilePlan(positional[0],options).then(result=>{
  if(options.json) console.log(JSON.stringify(result,null,2));
  else {
    console.log(`PASS: ${result.outPath}`);
    console.log(`Reasoning: ${result.reasoning}`);
    console.log(`Theme: ${result.theme_decision.selected_profile} (${result.theme_decision.source}/${result.theme_decision.mode})`);
    console.log(`Verified: ${result.verification.charts} chart caches · ${result.verification.notes} notes · embedded report`);
    if(result.warnings.length) for(const warning of result.warnings) console.log(`WARN: ${warning}`);
    console.log('Visual review: NOT_RUN (independent reviewer required)');
  }
}).catch(error=>{
  if(options.json) console.log(JSON.stringify({status:'FAIL',errors:error.errors||[error.message]},null,2));
  else {
    console.error(`FAIL: ${error.message}`);
    if(error.errors) for(const item of error.errors) console.error(`- ${item}`);
  }
  process.exit(2);
});
