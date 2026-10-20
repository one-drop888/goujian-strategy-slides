const assert=require('node:assert/strict');
const fs=require('fs'),path=require('path'),os=require('os'),crypto=require('crypto'),{execFileSync}=require('child_process');
const JSZip=require('jszip');
const PptxGenJS=require('pptxgenjs');
const {validatePlan}=require('../core/reasoning/validate-plan');
const {selectTheme}=require('../core/reasoning/theme-decision');
const {compilePlan}=require('../core/reasoning/compile');
const {verifyBuiltDeck}=require('../core/reasoning/verify');
const {buildDeck}=require('../core/renderer');
const {resolveStyle,contrastRatio}=require('../core/style/resolve-style');
const {loadProfile}=require('../core/style/profile-loader');
const {schemaErrors,validateDeck}=require('../core/schema/validate');
const root=path.resolve(__dirname,'..');
const fixture=name=>path.join(root,'skill/reasoning/fixtures',name);
const planPath=name=>path.join(fixture(name),'plan.json');
const readPlan=name=>JSON.parse(fs.readFileSync(planPath(name),'utf8'));
const clone=value=>structuredClone(value);
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const errorsOf=(plan,dir)=>validatePlan(plan,{planDir:dir,repoRoot:root});
function expectError(plan,dir,pattern) {
  const result=errorsOf(plan,dir);
  assert.equal(result.valid,false,'expected an error');
  assert.match(result.errors.join('\n'),pattern);
}
function specFromPlan(plan) {
  return {...plan.deck,slides:[...plan.slides].sort((a,b)=>a.order-b.order).map(slide=>slide.spec)};
}
async function chartXml(file) {
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  const names=Object.keys(zip.files).filter(name=>/^ppt\/charts\/chart\d+\.xml$/.test(name)).sort();
  return Promise.all(names.map(async name=>await zip.file(name).async('string')));
}

async function main() {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'goujian-reasoning-'));
  const executiveDir=fixture('executive-incomplete-business'),q4Dir=fixture('q4-six-actions'),multiDir=fixture('multimodal-consolidation');
  const executive=readPlan('executive-incomplete-business'),q4=readPlan('q4-six-actions'),multi=readPlan('multimodal-consolidation'),hostile=readPlan('hostile-source');
  const hostileDir=fixture('hostile-source');
  try {
    // Positive validation and factual acceptance.
    for(const [plan,dir] of [[executive,executiveDir],[q4,q4Dir],[multi,multiDir],[hostile,hostileDir]]) {
      const result=errorsOf(plan,dir);
      assert.deepEqual(result.errors,[],result.errors.join('\n'));
    }
    assert.deepEqual(q4.slides.find(s=>s.id==='q4-table').spec.rows.map(row=>row[0]),['A1','A2','A3','A4','A5','A6']);
    assert.equal(q4.slides.find(s=>s.id==='q4-table').spec.rows.filter(row=>row[5]!=='无').length,4);
    assert.equal(q4.slides.find(s=>s.id==='q4-roadmap').spec.lanes.reduce((n,lane)=>n+lane.phases.length,0),6);
    assert.equal(executive.claims.find(c=>c.id==='c-margin-gap').result.unit,'pp');
    assert.equal(executive.claims.find(c=>c.id==='c-rev-attain').result.value,96);
    assert.equal(multi.sources.find(s=>s.id==='s-channel').sha256,sha(path.join(multiDir,'../../../examples/assets/channel-evidence.png')));

    // Theme priority, conflicts and applied rendering.
    const priority=clone(executive);
    priority.theme={reference_profile:'../themes/brand-blue.profile.json',brand_profile:'marketing',user_profile:'sales'};
    let theme=selectTheme(priority,{planDir:executiveDir,repoRoot:root});
    assert.equal(theme.source,'reference');
    priority.theme={brand_profile:'../themes/brand-blue.profile.json',user_profile:'marketing'};
    theme=selectTheme(priority,{planDir:executiveDir,repoRoot:root,profile:'dark-executive'});
    assert.equal(theme.source,'brand');assert.equal(theme.mode,'light');
    priority.theme={user_profile:'marketing'};
    assert.equal(selectTheme(priority,{planDir:executiveDir,repoRoot:root}).source,'explicit-user');
    assert.equal(selectTheme(q4,{planDir:q4Dir,repoRoot:root}).selected_profile,'executive-clean');
    const noMatch=clone(executive);noMatch.intent={...noMatch.intent,audience:'团队',goal:'汇报',decision_question:'是否继续？',audience_needs:['清晰'],context:{}};
    assert.equal(selectTheme(noMatch,{planDir:executiveDir,repoRoot:root}).source,'default');
    const dark=clone(q4);dark.theme={mode:'dark'};
    theme=selectTheme(dark,{planDir:q4Dir,repoRoot:root});
    assert.equal(theme.source,'explicit-mode');assert.equal(theme.mode,'dark');
    const conflict=clone(q4);conflict.theme={reference_profile:'../themes/brand-blue.profile.json',mode:'dark'};
    theme=selectTheme(conflict,{planDir:q4Dir,repoRoot:root});
    assert.equal(theme.mode,'light');assert(theme.conflicts.length>=1);

    const multiResult=await compilePlan(planPath('multimodal-consolidation'),{out:path.join(temp,'brand.pptx'),profile:'../themes/brand-blue.profile.json'});
    assert.equal(multiResult.theme_decision.source,'explicit-user');
    assert.equal(multiResult.theme_decision.mode,'light');
    const brandStyle=resolveStyle(loadProfile('../themes/brand-blue.profile.json',root,new Set(),multiDir));
    const brandCharts=await chartXml(multiResult.outPath);
    assert(brandCharts.some(xml=>xml.includes(brandStyle.tokens.chart.palette[0])),'brand accent should drive native chart paint');
    assert.equal(schemaErrors('profile',loadProfile('../themes/brand-blue.profile.json',root,new Set(),multiDir)).length,0);

    // Compile with embedded hash-bound report and notes.
    const built=await compilePlan(planPath('executive-incomplete-business'),{out:path.join(temp,'executive.pptx'),specOut:path.join(temp,'executive.spec.json')});
    assert(fs.existsSync(built.outPath));assert(fs.existsSync(built.reasoning));
    const sidecar=JSON.parse(fs.readFileSync(built.reasoning,'utf8'));
    assert.equal(sidecar.status,'VALIDATED');assert.equal(sidecar.verification.status,'PASS');
    assert.equal(sidecar.theme_decision.selected_profile,'executive-clean');
    const zip=await JSZip.loadAsync(fs.readFileSync(built.outPath));
    const embedded=JSON.parse(await zip.file('docProps/goujian-reasoning.json').async('string'));
    assert.equal(embedded.plan_sha256,sidecar.plan_sha256);
    const scene=JSON.parse(fs.readFileSync(built.scene,'utf8'));
    assert.equal(scene.reasoning.status,'VALIDATED');assert.equal(scene.theme_decision.mode,'light');
    const notes=await Promise.all([1,2,3,4,5,6,7,8].map(async index=>{
      const rels=await zip.file(`ppt/slides/_rels/slide${index}.xml.rels`).async('string');
      const target=path.posix.normalize(path.posix.join('ppt/slides',rels.match(/Target="([^"]*notesSlide[^"]*\.xml)"/)[1]));
      return await zip.file(target).async('string');
    }));
    assert(notes.every(xml=>xml.includes('[reasoning:')));
    assert.deepEqual(validateDeck(JSON.parse(fs.readFileSync(built.specOut,'utf8'))),[]);

    // Legacy builds remain compatible and report reasoning NOT_RUN.
    const legacyFile=path.join(temp,'legacy.pptx');
    const legacy=await buildDeck({title:'Legacy',slides:[{type:'key-message',title:'Legacy',statement:'No plan.'}]},legacyFile);
    assert.equal(legacy.reasoning.status,'NOT_RUN');
    const legacyZip=await JSZip.loadAsync(fs.readFileSync(legacyFile));
    assert(!legacyZip.file('docProps/goujian-reasoning.json'));

    // Post-build chart cache tampering is rejected.
    const tampered=path.join(temp,'tampered.pptx');
    const tamperZip=await JSZip.loadAsync(fs.readFileSync(built.outPath));
    const chartName=Object.keys(tamperZip.files).find(name=>/^ppt\/charts\/chart\d+\.xml$/.test(name));
    const chartText=(await tamperZip.file(chartName).async('string')).replace('<c:v>780</c:v>','<c:v>781</c:v>');
    tamperZip.file(chartName,chartText);
    fs.writeFileSync(tampered,await tamperZip.generateAsync({type:'nodebuffer'}));
    const executiveSpec=specFromPlan(executive);
    await assert.rejects(verifyBuiltDeck(tampered,executiveSpec,{plan_sha256:sidecar.plan_sha256,spec_sha256:sidecar.spec_sha256,slides:executive.slides},root),/does not match/);
    await assert.rejects(buildDeck(executiveSpec,path.join(temp,'guarded.pptx'),{reasoning:{validated:false}}),/validated reasoning-plan/);

    // Adversarial calculations, evidence and structure.
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-gap').result.value=-50;return p;})(),executiveDir,/does not match difference arithmetic/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-attain').result.denominator=900;return p;})(),executiveDir,/declared denominator 900/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-margin-gap').result.unit='%';return p;})(),executiveDir,/requires result unit pp/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-gap').result.time_window='2026-08';return p;})(),executiveDir,/result time_window must be 2026-09/);
    expectError((()=>{const p=clone(executive);p.sources.find(s=>s.id==='revenue').values.push({id:'rev-zero',metric:'收入',value:0,unit:'万元',time_window:'2026-09'});p.claims.find(c=>c.id==='c-rev-attain').inputs[1].value_id='rev-zero';return p;})(),executiveDir,/denominator cannot be zero/);
    expectError((()=>{const p=clone(executive);p.sources.find(s=>s.id==='revenue').values.push({id:'rev-zero-base',metric:'收入',value:0,unit:'万元',time_window:'2026-08'});p.claims.find(c=>c.id==='c-revenue-mom').inputs[0].value_id='rev-zero-base';return p;})(),executiveDir,/baseline cannot be zero/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-gap').source_ids=['missing-source'];return p;})(),executiveDir,/unknown source missing-source/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-gap').operator='mean';return p;})(),executiveDir,/operator/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-gap').depends_on=['c-cause-hypothesis'];return p;})(),executiveDir,/claim dependency cycle/);
    expectError((()=>{const p=clone(executive);p.content_decisions.find(d=>d.source_id==='gap-note').dedup_target='gap-note';p.content_decisions.find(d=>d.source_id==='gap-note').disposition='deduplicate';return p;})(),executiveDir,/cannot be itself/);
    expectError((()=>{const p=clone(executive);const d=p.content_decisions;d.find(x=>x.source_id==='revenue').disposition='deduplicate';d.find(x=>x.source_id==='revenue').dedup_target='orders';d.find(x=>x.source_id==='orders').disposition='deduplicate';d.find(x=>x.source_id==='orders').dedup_target='margin';return p;})(),executiveDir,/dedup_target must be a retained canonical source/);
    expectError((()=>{const p=clone(executive);p.slides.forEach(s=>{s.source_ids=s.source_ids.filter(id=>id!=='gap-note');if(!s.source_ids.length)s.source_ids=['revenue'];});p.sources.find(s=>s.id==='gap-note').importance='critical';return p;})(),executiveDir,/critical source gap-note: not covered/);
    expectError((()=>{const p=clone(executive);delete p.content_decisions.find(d=>d.source_id==='gap-note').disposition;p.content_decisions=p.content_decisions.filter(d=>d.source_id!=='gap-note');return p;})(),executiveDir,/missing content decision/);
    expectError((()=>{const p=clone(executive);p.content_decisions.find(d=>d.source_id==='gap-note').disposition='appendix';p.slides.find(s=>s.id==='s-appendix').source_ids=p.slides.find(s=>s.id==='s-appendix').source_ids.filter(id=>id!=='gap-note');return p;})(),executiveDir,/appendix disposition requires an appendix slide/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-trend').claim_ids.push('missing-claim');return p;})(),executiveDir,/unknown claim missing-claim/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-trend').bindings=p.slides.find(s=>s.id==='s-trend').bindings.filter(b=>b.pointer!=='/series/0/values/0');return p;})(),executiveDir,/unbound numeric value at \/series\/0\/values\/0/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-trend').spec.series[0].values[0]=781;return p;})(),executiveDir,/bound value 781 does not match source value 780/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-trend').bindings[0].pointer='/series/0/values/99';return p;})(),executiveDir,/out of range/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-trend').visual_intent='process';return p;})(),executiveDir,/unsupported chart intent/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-uncertainty').title_mode='descriptive';p.slides.find(s=>s.id==='s-uncertainty').spec.title='缺口来自产品结构';return p;})(),executiveDir,/hypothesis presented as fact/);

    // Malicious source text stays data and is never executed.
    const marker='/tmp/goujian-hostile-marker';
    fs.rmSync(marker,{force:true});
    const hostileResult=await compilePlan(planPath('hostile-source'),{out:path.join(temp,'hostile.pptx')});
    assert(!fs.existsSync(marker),'source instructions must never execute');
    const hostileReport=JSON.parse(fs.readFileSync(hostileResult.reasoning,'utf8'));
    assert.match(hostileReport.sources[0].summary,/合成恶意来源样本/);
    assert.match(fs.readFileSync(path.join(hostileDir,'sources/hostile.md'),'utf8'),/Ignore all previous instructions/);

    // Safe output paths never overwrite the plan or a source file.
    await assert.rejects(compilePlan(planPath('executive-incomplete-business'),{out:planPath('executive-incomplete-business')}),/must not overwrite input/);
    const sourceFile=path.join(executiveDir,'sources/business-performance.json');
    const sourceHash=sha(sourceFile);
    await assert.rejects(compilePlan(planPath('executive-incomplete-business'),{out:sourceFile}),/must not overwrite input/);
    assert.equal(sha(sourceFile),sourceHash);
    const existing=path.join(temp,'existing.pptx');fs.writeFileSync(existing,'x');
    await assert.rejects(compilePlan(planPath('q4-six-actions'),{out:existing}),/already exists/);
    await compilePlan(planPath('q4-six-actions'),{out:existing,force:true});

    // Reference extraction uses native chart paint and records limitations.
    const refFile=path.join(temp,'reference.pptx');
    const refDeck=new PptxGenJS();refDeck.layout='LAYOUT_WIDE';const page=refDeck.addSlide();
    page.addText('合成参考页',{x:.4,y:.3,w:6,h:.5,fontSize:24,bold:true,color:'202124',fontFace:'Noto Sans CJK SC',margin:0});
    page.addChart('bar',[{name:'成交率',labels:['A','B'],values:[14.2,13.8]}],{x:.4,y:1.2,w:6,h:3,chartColors:['176B87'],showValue:true,showLegend:false});
    await refDeck.writeFile({fileName:refFile});
    const styleReport=path.join(temp,'style.json'),refProfile=path.join(temp,'profile.json');
    execFileSync('python3',[path.join(root,'skill/scripts/extract_style.py'),refFile,styleReport]);
    execFileSync('python3',[path.join(root,'skill/scripts/profile_from_reference.py'),styleReport,refProfile,'native-reference']);
    const report=JSON.parse(fs.readFileSync(styleReport,'utf8'));
    assert(report.native_evidence.chart_series_colors.some(item=>item.color==='176B87'));
    assert(report.native_evidence.limitations.length>=3);
    const profile=JSON.parse(fs.readFileSync(refProfile,'utf8'));
    assert.equal(profile.colors.accent,'176B87');
    assert.equal(schemaErrors('profile',profile).length,0);
    assert(contrastRatio(profile.colors.text,profile.background)>=4.5);

    // CLI errors and success are user-readable.
    const badPlan=clone(hostile);delete badPlan.content_decisions;
    const badPath=path.join(temp,'bad-plan.json');fs.writeFileSync(badPath,JSON.stringify(badPlan,null,2));
    let cliFailure=null;
    try {execFileSync(process.execPath,[path.join(root,'skill/scripts/validate_plan.js'),badPath,'--json'],{encoding:'utf8',stdio:'pipe'});}
    catch(error){cliFailure=error;}
    assert(cliFailure);const cliJson=JSON.parse(cliFailure.stdout);assert.equal(cliJson.status,'FAIL');assert(cliJson.errors.length>=1);
    let safeFailure=null;
    try {execFileSync(process.execPath,[path.join(root,'skill/scripts/compile_plan.js'),planPath('q4-six-actions'),'--out',planPath('q4-six-actions')],{encoding:'utf8',stdio:'pipe'});}
    catch(error){safeFailure=error;}
    assert(safeFailure);assert.match(safeFailure.stderr,/must not overwrite input/);
    const cliOut=path.join(temp,'cli-q4.pptx');
    const cliSuccess=execFileSync(process.execPath,[path.join(root,'skill/scripts/compile_plan.js'),planPath('q4-six-actions'),'--out',cliOut],{encoding:'utf8'});
    assert.match(cliSuccess,/PASS:/);assert(fs.existsSync(cliOut+'.reasoning.json'));

    console.log('PASS: reasoning plans validate/compile, hash-bound reports and notes verify, theme priority applies, adversarial calculations/coverage/bindings/intents/dedup/cycles are rejected, hostile source stays data, safe outputs and native reference evidence work');
  } finally {
    fs.rmSync(temp,{recursive:true,force:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
