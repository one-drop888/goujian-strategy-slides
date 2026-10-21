const assert=require('node:assert/strict');
const fs=require('fs'),path=require('path'),os=require('os'),crypto=require('crypto'),{execFileSync}=require('child_process');
const JSZip=require('jszip');
const PptxGenJS=require('pptxgenjs');
const {validatePlan}=require('../core/reasoning/validate-plan');
const {evaluateCalculation}=require('../core/reasoning/calculations');
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
    const q4Roadmap=q4.slides.find(s=>s.id==='q4-roadmap').spec;
    assert.equal(q4Roadmap.tasks.length,6);
    assert.equal(q4Roadmap.dependencies.length,4);
    assert.deepEqual(q4Roadmap.tasks.reduce((rows,task)=>(rows[task.lane].push(task.id),rows),[[],[],[]]),[['A1','A2','A3'],['A6'],['A4','A5']]);
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
    const protectedPlan=clone(q4);protectedPlan.theme={reference_profile:'../themes/brand-blue.profile.json'};
    protectedPlan.deck.background='000000';protectedPlan.deck.colors={accent:'112233'};protectedPlan.deck.font={latin:'Arial'};
    assert.throws(()=>selectTheme(protectedPlan,{planDir:q4Dir,repoRoot:root}),
      /reference profile has highest priority[\s\S]*background 000000[\s\S]*colors\.accent 112233[\s\S]*font\.latin Arial/);
    const matchingPlan=clone(q4);matchingPlan.theme={reference_profile:'../themes/brand-blue.profile.json'};
    matchingPlan.deck.background='FFFFFF';matchingPlan.deck.colors={accent:'1F5EFF'};
    assert.equal(selectTheme(matchingPlan,{planDir:q4Dir,repoRoot:root}).source,'reference');
    const brandPlan=clone(q4);brandPlan.theme={brand_profile:'../themes/brand-blue.profile.json'};brandPlan.deck.colors={accent:'112233'};
    assert.throws(()=>selectTheme(brandPlan,{planDir:q4Dir,repoRoot:root}),/brand profile has highest priority[\s\S]*colors\.accent/);
    assert.match(selectTheme(q4,{planDir:q4Dir,repoRoot:root}).chart_strategy,/3:1 series \/ 4\.5:1 text/);
    assert.doesNotMatch(selectTheme(q4,{planDir:q4Dir,repoRoot:root}).chart_strategy,/WCAG 3\.0/);

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
    assert.match(sidecar.theme_decision.chart_strategy,/3:1 series \/ 4\.5:1 text/);
    assert(sidecar.value_coverage.every(item=>item.basis!=='UNCOVERED'));
    const zip=await JSZip.loadAsync(fs.readFileSync(built.outPath));
    const embedded=JSON.parse(await zip.file('docProps/goujian-reasoning.json').async('string'));
    assert.equal(embedded.plan_sha256,sidecar.plan_sha256);
    const scene=JSON.parse(fs.readFileSync(built.scene,'utf8'));
    assert.equal(scene.reasoning.status,'VALIDATED');assert.equal(scene.theme_decision.mode,'light');
    const notes=await Promise.all(sidecar.slides.map((_,offset)=>offset+1).map(async index=>{
      const rels=await zip.file(`ppt/slides/_rels/slide${index}.xml.rels`).async('string');
      const target=path.posix.normalize(path.posix.join('ppt/slides',rels.match(/Target="([^"]*notesSlide[^"]*\.xml)"/)[1]));
      return await zip.file(target).async('string');
    }));
    assert(notes.every(xml=>xml.includes('[reasoning:')));
    assert.deepEqual(validateDeck(JSON.parse(fs.readFileSync(built.specOut,'utf8'))),[]);

    // Dependency roadmap uses source-defined tasks and orthogonal connector segments outside node text.
    const q4Built=await compilePlan(planPath('q4-six-actions'),{out:path.join(temp,'q4.pptx')});
    assert.equal(q4Built.verification.status,'PASS');
    const q4Scene=JSON.parse(fs.readFileSync(q4Built.scene,'utf8'));
    const q4Nodes=q4Scene.slides[2].nodes;
    assert.equal(q4Nodes.filter(node=>node.semantic_role==='task_node').length,6);
    const dependencies=q4Nodes.filter(node=>node.role==='connector');
    assert.equal(new Set(dependencies.map(node=>`${node.from}->${node.to}`)).size,4);
    assert(dependencies.every(node=>node.from&&node.to));
    for(const connector of dependencies)
      for(const node of q4Nodes.filter(item=>item.semantic_role==='task_node')) {
        const intersects=connector.bbox.x<node.bbox.x+node.bbox.w&&connector.bbox.x+connector.bbox.w>node.bbox.x
          &&connector.bbox.y<node.bbox.y+node.bbox.h&&connector.bbox.y+connector.bbox.h>node.bbox.y;
        assert(!intersects,'connector segment must stay outside task text');
      }

    // Multimodal brief: one embedded interview screenshot, one native chart, full appendix, no repeated source images.
    assert.equal(multi.slides.length,7);
    assert.deepEqual([...new Set(multi.slides.flatMap(slide=>slide.spec.asset_ids||[]))],['showroom','interview']);
    const multiChart=multi.slides.find(slide=>slide.id==='mm-chart');
    assert.deepEqual(multiChart.bindings.map(binding=>binding.target.value_id).sort(),['sc-hn-conv','sc-xn-conv']);
    const gapClaim=multi.claims.find(claim=>claim.id==='c-region-gap');
    assert.equal(gapClaim.result.value,3.3);assert.equal(gapClaim.result.unit,'pp');
    const appendix=multi.slides.find(slide=>slide.id==='mm-appendix-table');
    assert.equal(appendix.spec.headers.length,9);assert.equal(appendix.spec.rows.length,4);assert.equal(appendix.bindings.length,24);
    assert.equal(multi.slides.find(slide=>slide.id==='mm-appendix-sources').spec.rows.length,5);
    const multiScene=JSON.parse(fs.readFileSync(multiResult.scene,'utf8'));
    assert.equal(multiScene.slides.length,7);
    const multiNodes=multiScene.slides.flatMap(slide=>slide.nodes);
    const images=multiNodes.filter(node=>node.kind==='image');
    assert.deepEqual(images.map(node=>node.provenance.source_asset).sort(),['interview','showroom']);
    assert.equal(images.find(node=>node.provenance.source_asset==='interview').provenance.render_mode,'embedded');
    assert.equal(multiNodes.filter(node=>node.role==='annotation'&&node.kind==='shape').length,2);
    assert.equal(multiNodes.filter(node=>node.role==='annotation'&&node.kind==='text').length,2);
    assert.equal(multiNodes.filter(node=>node.kind==='chart').length,1,'one native comparison chart');
    const heroClaim=multiScene.slides[0].nodes.find(node=>node.role==='claim');
    assert(heroClaim.bbox.w>11.7,'hero title uses the full available width');
    assert(heroClaim.bbox.h<=.75,'hero title stays on one line');
    assert(heroClaim.contrast.ratio>=4.5,'hero title contrast is recomputed over the wider overlay');
    const appendixXml=await (await JSZip.loadAsync(fs.readFileSync(multiResult.outPath))).file('ppt/slides/slide6.xml').async('string');
    assert.equal((appendixXml.match(/<a:tr /g)||[]).length,5);
    assert.equal((appendixXml.match(/<a:tc>/g)||[]).length,45);
    assert(appendixXml.includes('1,280')&&appendixXml.includes('10/20'),'appendix keeps full native channel cells');

    // Exported specs rebuild from another cwd/Unicode path with builtin and custom themes.
    const exportedBuiltin=JSON.parse(fs.readFileSync(built.specOut,'utf8'));
    assert.equal(exportedBuiltin.profile,'executive-clean');
    const unicodeDir=path.join(temp,'重建 导出');fs.mkdirSync(unicodeDir);
    fs.copyFileSync(built.specOut,path.join(unicodeDir,'spec.json'));
    execFileSync(process.execPath,[path.join(root,'skill/scripts/build_deck.js'),'spec.json','rebuilt.pptx'],{cwd:unicodeDir,encoding:'utf8'});
    const rebuiltScene=JSON.parse(fs.readFileSync(path.join(unicodeDir,'rebuilt.pptx.scene.json'),'utf8'));
    assert.equal(rebuiltScene.theme_decision.selected_profile,'executive-clean');
    assert.equal(rebuiltScene.reasoning.status,'NOT_RUN');

    const portable=path.join(temp,'portable 源'),portableAssets=path.join(portable,'assets');
    fs.mkdirSync(portableAssets,{recursive:true});
    for(const name of ['channel-evidence.png','chart-evidence.png','interview-evidence.png','showroom-illustration.png']) {
      fs.copyFileSync(path.join(root,'skill/examples/assets',name),path.join(portableAssets,name));
    }
    fs.copyFileSync(path.join(root,'skill/reasoning/fixtures/themes/brand-blue.profile.json'),path.join(portable,'theme.profile.json'));
    const portablePlan=clone(multi);portablePlan.theme={user_profile:'theme.profile.json'};
    for(const source of portablePlan.sources) if(source.path) source.path=source.path.replace('../../../examples/assets/','assets/');
    for(const asset of portablePlan.deck.assets) asset.path=asset.path.replace('../../../examples/assets/','assets/');
    fs.writeFileSync(path.join(portable,'plan.json'),JSON.stringify(portablePlan,null,2));
    await compilePlan(path.join(portable,'plan.json'),{out:path.join(portable,'build','out.pptx'),specOut:path.join(portable,'export','spec.json')});
    const exportedCustom=JSON.parse(fs.readFileSync(path.join(portable,'export','spec.json'),'utf8'));
    assert.equal(exportedCustom.profile,'../theme.profile.json');
    assert.equal(exportedCustom.assets.length,2);
    assert(exportedCustom.assets.every(asset=>!path.isAbsolute(asset.path)&&!asset.path.includes(portable)));
    const unicodePortable=path.join(temp,'可移植 重建');fs.cpSync(portable,unicodePortable,{recursive:true});
    execFileSync(process.execPath,[path.join(root,'skill/scripts/build_deck.js'),'export/spec.json','export/rebuilt.pptx'],{cwd:unicodePortable,encoding:'utf8'});
    const portableScene=JSON.parse(fs.readFileSync(path.join(unicodePortable,'export/rebuilt.pptx.scene.json'),'utf8'));
    assert.equal(portableScene.theme_decision.selected_profile,'brand-blue');
    assert(portableScene.assets.length>=1);

    // Legacy spec overrides stay compatible and the final record reflects resolved values.
    const overrideSpec={title:'Theme override',profile:'dark-executive',background:'FFFFFF',colors:{accent:'112233'},
      font:{latin:'Arial',title_size:31},slides:[{type:'key-message',title:'Override',statement:'No reasoning plan.'}]};
    const overrideFile=path.join(temp,'theme-override.pptx');
    const overrideBuilt=await buildDeck(overrideSpec,overrideFile);
    const expectedStyle=resolveStyle(loadProfile('dark-executive',root),overrideSpec);
    assert.equal(overrideBuilt.theme_decision.mode,'light');
    assert.equal(overrideBuilt.theme_decision.background,expectedStyle.tokens.background);
    assert.equal(overrideBuilt.theme_decision.colors.accent,expectedStyle.tokens.accent);
    assert.equal(overrideBuilt.theme_decision.typography.title_size,31);
    assert.equal(overrideBuilt.theme_decision.contrast.text_min,'4.5:1');
    const overrideScene=JSON.parse(fs.readFileSync(overrideFile+'.scene.json','utf8'));
    assert.equal(overrideScene.theme_decision.background,overrideBuilt.theme_decision.background);
    assert.equal(overrideScene.theme_decision.typography.latin,overrideScene.fonts.find(item=>item.script==='latin').resolved);

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
    await assert.rejects(verifyBuiltDeck(tampered,executiveSpec,{plan_sha256:sidecar.plan_sha256,spec_sha256:sidecar.spec_sha256,slides:executive.slides,expected_pptx_sha256:sidecar.pptx_sha256},root),/sha256/);
    await assert.rejects(verifyBuiltDeck(tampered,executiveSpec,{plan_sha256:sidecar.plan_sha256,spec_sha256:sidecar.spec_sha256,slides:executive.slides,expected_pptx_sha256:sha(tampered)},root),/does not match/);
    await assert.rejects(verifyBuiltDeck(tampered,executiveSpec,{plan_sha256:sidecar.plan_sha256,spec_sha256:sidecar.spec_sha256,slides:executive.slides},root),/requires expected_pptx_sha256/);
    await assert.rejects(buildDeck(executiveSpec,path.join(temp,'guarded.pptx'),{reasoning:{validated:true}}),/source plan/);
    const mismatchedSpec=clone(executiveSpec);mismatchedSpec.title='Tampered';
    await assert.rejects(buildDeck(mismatchedSpec,path.join(temp,'guarded.pptx'),{reasoning:{plan:executive,planDir:executiveDir,validated:true}}),/does not match the validated reasoning plan/);

    // Native table and KPI cells are inspected directly, not just chart caches.
    const tableTampered=path.join(temp,'table-tampered.pptx');
    const tableZip=await JSZip.loadAsync(fs.readFileSync(built.outPath));
    const tableSlideName='ppt/slides/slide5.xml';
    const tableText=(await tableZip.file(tableSlideName).async('string')).replace('<a:t>960</a:t>','<a:t>969</a:t>');
    tableZip.file(tableSlideName,tableText);
    fs.writeFileSync(tableTampered,await tableZip.generateAsync({type:'nodebuffer'}));
    await assert.rejects(verifyBuiltDeck(tableTampered,executiveSpec,{plan_sha256:sidecar.plan_sha256,spec_sha256:sidecar.spec_sha256,slides:executive.slides,expected_pptx_sha256:sha(tableTampered)},root),/table .* cells do not match spec/);
    const kpiTampered=path.join(temp,'kpi-tampered.pptx');
    const kpiZip=await JSZip.loadAsync(fs.readFileSync(built.outPath));
    const kpiSlideName='ppt/slides/slide3.xml';
    const kpiText=(await kpiZip.file(kpiSlideName).async('string')).replace('<a:t>960万元</a:t>','<a:t>969万元</a:t>');
    kpiZip.file(kpiSlideName,kpiText);
    fs.writeFileSync(kpiTampered,await kpiZip.generateAsync({type:'nodebuffer'}));
    await assert.rejects(verifyBuiltDeck(kpiTampered,executiveSpec,{plan_sha256:sidecar.plan_sha256,spec_sha256:sidecar.spec_sha256,slides:executive.slides,expected_pptx_sha256:sha(kpiTampered)},root),/KPI value/);

    // Adversarial calculations, evidence and structure.
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-gap').result.value=-50;return p;})(),executiveDir,/does not match difference arithmetic/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-attain').result.denominator=900;return p;})(),executiveDir,/declared denominator 900/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-margin-gap').result.unit='%';return p;})(),executiveDir,/requires result unit pp/);
    expectError((()=>{const p=clone(executive);p.claims.find(c=>c.id==='c-rev-gap').result.time_window='2026-08';return p;})(),executiveDir,/result time_window must be 2026-09/);
    expectError((()=>{const p=clone(executive);p.sources.find(s=>s.id==='revenue').values.push({id:'rev-zero',metric:'收入',value:0,unit:'万元',time_window:'2026-09'});p.claims.find(c=>c.id==='c-rev-attain').inputs[1].value_id='rev-zero';return p;})(),executiveDir,/denominator cannot be zero/);
    expectError((()=>{const p=clone(executive);p.sources.find(s=>s.id==='revenue').values.push({id:'rev-zero-base',metric:'收入',value:0,unit:'万元',time_window:'2026-08'});p.claims.find(c=>c.id==='c-revenue-mom').inputs[0].value_id='rev-zero-base';return p;})(),executiveDir,/baseline must be positive/);
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
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-actions').title_mode='descriptive';p.slides.find(s=>s.id==='s-actions').spec.title='缺口来自产品结构';return p;})(),executiveDir,/hypothesis presented as fact/);

    // Arithmetic rejects incompatible or missing comparison metadata.
    const calculationSources=new Map([['ledger',{values:[
      {id:'actual',metric:'收入',value:960,unit:'万元',time_window:'2026-09'},
      {id:'target',metric:'收入',value:1000,unit:'万元',time_window:'2026-09'},
      {id:'target-yuan',metric:'收入',value:1000,unit:'元',time_window:'2026-09'},
      {id:'previous',metric:'收入',value:900,unit:'万元',time_window:'2026-08'},
      {id:'negative',metric:'收入',value:-5,unit:'万元',time_window:'2026-08'},
      {id:'no-metric',value:1000,unit:'万元',time_window:'2026-09'},
      {id:'no-unit',metric:'收入',value:1000,time_window:'2026-09'},
      {id:'no-window',metric:'收入',value:1000,unit:'万元'},
      {id:'margin-a',metric:'毛利率',value:22,unit:'%',time_window:'2026-09'},
      {id:'margin-b',metric:'毛利率',value:24,unit:'%',time_window:'2026-09'},
    ]}]]);
    const calculation=(operator,left,right,result,extra={})=>({id:'arithmetic-case',type:'CALCULATION',operator,
      inputs:[{source_id:'ledger',value_id:left},{source_id:'ledger',value_id:right}],result,...extra});
    assert.throws(()=>evaluateCalculation(calculation('ratio','actual','target-yuan',{value:96,unit:'%',time_window:'2026-09'}),calculationSources),/share one compatible unit/);
    assert.throws(()=>evaluateCalculation(calculation('difference','actual','no-metric',{value:-40,unit:'万元',time_window:'2026-09'}),calculationSources),/requires an explicit metric/);
    assert.throws(()=>evaluateCalculation(calculation('difference','actual','no-unit',{value:-40,unit:'万元',time_window:'2026-09'}),calculationSources),/requires an explicit unit/);
    assert.throws(()=>evaluateCalculation(calculation('difference','actual','no-window',{value:-40,unit:'万元',time_window:'2026-09'}),calculationSources),/requires an explicit time_window/);
    assert.throws(()=>evaluateCalculation(calculation('percent_change','negative','actual',{value:19300,unit:'%',time_window:'2026-08->2026-09'}),calculationSources),/baseline must be positive/);
    assert.throws(()=>evaluateCalculation(calculation('percent_change','actual','target',{value:4.1666666667,unit:'%',time_window:'2026-09->2026-09'}),calculationSources),/time windows must differ/);
    assert.throws(()=>evaluateCalculation(calculation('sum','actual','actual',{value:1920,unit:'万元',time_window:'2026-09'}),calculationSources),/duplicate operands/);
    assert.throws(()=>evaluateCalculation(calculation('sum','margin-a','margin-b',{value:46,unit:'%',time_window:'2026-09'}),calculationSources),/sum of % values is not a valid aggregate/);
    assert.throws(()=>evaluateCalculation(calculation('ratio','actual','target',{value:96,unit:'%',metric:'订单',time_window:'2026-09'}),calculationSources),/result metric 订单/);

    // Slide claim/source/binding closures and critical numeric coverage are enforced.
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-table').source_ids=['gap-note'];return p;})(),executiveDir,/source closure missing revenue/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-table').source_ids.push('gap-note');return p;})(),executiveDir,/source gap-note is not referenced/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-actions').source_ids=p.slides.find(s=>s.id==='s-actions').source_ids.filter(id=>id!=='margin');return p;})(),executiveDir,/source closure missing margin/);
    expectError((()=>{const p=clone(executive);p.slides.find(s=>s.id==='s-table').claim_ids=p.slides.find(s=>s.id==='s-table').claim_ids.filter(id=>id!=='c-margin-gap');return p;})(),executiveDir,/binding calculation c-margin-gap is outside the slide claim closure/);
    expectError((()=>{const p=clone(executive);p.sources.find(s=>s.id==='revenue').values.push({id:'rev-uncovered',label:'未使用口径',metric:'收入',value:960,unit:'万元',time_window:'2026-09',json_pointer:'/metrics/0/actual'});return p;})(),executiveDir,/critical numeric value revenue.rev-uncovered/);
    expectError((()=>{const p=clone(executive);delete p.sources.find(s=>s.id==='revenue').values.find(v=>v.id==='rev-actual').json_pointer;return p;})(),executiveDir,/structured JSON source requires json_pointer/);
    expectError((()=>{const p=clone(executive);Object.assign(p.slides.find(s=>s.id==='s-kpi').spec.items[0],{target:1000,actual:960,variance:-40,delta:'+3pp'});return p;})(),executiveDir,/unbound numeric value at \/items\/0\/delta/);
    expectError((()=>{const p=clone(executive);const decision=p.content_decisions.find(d=>d.source_id==='orders');decision.disposition='deduplicate';decision.dedup_target='revenue';return p;})(),executiveDir,/novel numeric evidence/);

    // JSON ledgers are checked against the actual bytes, not the declared summary.
    const copyExecutive=()=>{
      const dir=fs.mkdtempSync(path.join(temp,'fixture-copy-'));
      fs.cpSync(executiveDir,dir,{recursive:true});
      return {dir,plan:JSON.parse(fs.readFileSync(path.join(dir,'plan.json'),'utf8'))};
    };
    const businessFile=dir=>path.join(dir,'sources/business-performance.json');
    const writeBusiness=(dir,data)=>fs.writeFileSync(businessFile(dir),JSON.stringify(data,null,2));
    const refreshHashes=(plan,dir)=>{
      const cache=new Map();
      for(const source of plan.sources) if(source.path) {
        if(!cache.has(source.path))cache.set(source.path,sha(path.join(dir,source.path)));
        source.sha256=cache.get(source.path);
      }
    };
    {
      const {dir,plan}=copyExecutive(),data=JSON.parse(fs.readFileSync(businessFile(dir),'utf8'));
      data.metrics[0].actual=969;writeBusiness(dir,data);refreshHashes(plan,dir);
      expectError(plan,dir,/declared value 960 does not match source bytes 969/);
    }
    {
      const {dir,plan}=copyExecutive(),data=JSON.parse(fs.readFileSync(businessFile(dir),'utf8'));
      data.metrics[0].unit='元';writeBusiness(dir,data);refreshHashes(plan,dir);
      expectError(plan,dir,/declared unit 万元 does not match source bytes unit 元/);
    }
    {
      const {dir,plan}=copyExecutive(),data=JSON.parse(fs.readFileSync(businessFile(dir),'utf8'));
      data.trend[0].month='2026-05';writeBusiness(dir,data);refreshHashes(plan,dir);
      expectError(plan,dir,/declared time_window 2026-04 does not match source bytes month 2026-05/);
    }
    {
      const {dir,plan}=copyExecutive(),data=JSON.parse(fs.readFileSync(businessFile(dir),'utf8'));
      data.metrics[0].new_metric=12345;writeBusiness(dir,data);refreshHashes(plan,dir);
      plan.sources.find(s=>s.id==='revenue').values.push({id:'rev-new',label:'新增字段',metric:'收入',value:12345,unit:'万元',time_window:'2026-09',json_pointer:'/metrics/0/new_metric'});
      expectError(plan,dir,/critical numeric value revenue.rev-new/);
    }

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

    // Guard sidecar/scene/spec collisions, symlink aliases, profiles, and --force.
    const collision=path.join(temp,'collision.pptx');
    await assert.rejects(compilePlan(planPath('q4-six-actions'),{out:collision,specOut:collision+'.scene.json'}),/must be different paths/);
    await assert.rejects(compilePlan(planPath('q4-six-actions'),{out:collision,specOut:collision+'.reasoning.json'}),/must be different paths/);
    await assert.rejects(compilePlan(planPath('executive-incomplete-business'),{out:collision,specOut:path.join(executiveDir,'sources/business-performance.json')}),/must not overwrite input/);
    const alias=path.join(temp,'plan-alias.json');fs.symlinkSync(planPath('q4-six-actions'),alias);
    await assert.rejects(compilePlan(planPath('q4-six-actions'),{out:alias,force:true}),/must not overwrite input/);
    await assert.rejects(compilePlan(planPath('executive-incomplete-business'),{out:sourceFile,force:true}),/must not overwrite input/);
    const customProfileFile=path.join(temp,'custom.profile.json');
    fs.copyFileSync(path.join(root,'skill/profiles/executive-clean/profile.json'),customProfileFile);
    await assert.rejects(compilePlan(planPath('q4-six-actions'),{out:customProfileFile,force:true,profile:customProfileFile}),/must not overwrite input/);
    const profileAlias=path.join(temp,'profile-alias.json');fs.symlinkSync(customProfileFile,profileAlias);
    await assert.rejects(compilePlan(planPath('q4-six-actions'),{out:profileAlias,force:true,profile:customProfileFile}),/must not overwrite input/);

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
