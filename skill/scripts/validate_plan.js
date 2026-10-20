#!/usr/bin/env node
const path=require('path');
const {readPlan}=require('../../core/reasoning/compile');
const {validatePlan}=require('../../core/reasoning/validate-plan');
const {selectTheme}=require('../../core/reasoning/theme-decision');

const args=process.argv.slice(2);
const json=args.includes('--json');
const planArg=args.find(arg=>!arg.startsWith('--'));
if(!planArg) {
  console.error('usage: validate_plan.js plan.json [--json]');
  process.exit(2);
}
try {
  const planPath=path.resolve(planArg),planDir=path.dirname(planPath),repoRoot=path.resolve(__dirname,'../..');
  const plan=readPlan(planPath);
  const result=validatePlan(plan,{planDir,repoRoot});
  let theme=null,themeError=null;
  if(result.valid) {
    try { theme=selectTheme(plan,{planDir,repoRoot}); }
    catch(error) { themeError=error.message;result.errors.push(error.message);result.valid=false; }
  }
  const output={status:result.valid?'PASS':'FAIL',plan_id:plan.plan_id,errors:result.errors,warnings:result.warnings||[],
    counts:{sources:(plan.sources||[]).length,claims:(plan.claims||[]).length,slides:(plan.slides||[]).length,
      calculations:result.calculations?.size||0},
    theme_decision:theme?{selected_profile:theme.selected_profile,source:theme.source,mode:theme.mode,conflicts:theme.conflicts}:null};
  if(json) console.log(JSON.stringify(output,null,2));
  else if(result.valid) {
    console.log(`PASS: ${output.plan_id} · ${output.counts.sources} sources · ${output.counts.claims} claims · ${output.counts.slides} slides · theme=${theme.selected_profile} (${theme.source}/${theme.mode})`);
    for(const warning of output.warnings) console.log(`WARN: ${warning}`);
  } else {
    console.error(`FAIL: ${output.plan_id||planPath}`);
    for(const error of result.errors) console.error(`- ${error}`);
  }
  process.exit(result.valid?0:2);
} catch(error) {
  if(json) console.log(JSON.stringify({status:'FAIL',errors:[error.message]},null,2));
  else console.error(`FAIL: ${error.message}`);
  process.exit(2);
}
