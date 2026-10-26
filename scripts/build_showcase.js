#!/usr/bin/env node
'use strict';
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const {spawnSync}=require('child_process');
const benchmark=require('./v13_benchmark');

const ROOT=path.resolve(__dirname,'..');
const DEFAULT_OUT=path.join(ROOT,'out/v1.3-showcase');
const DEFAULT_PREVIEW=path.join(ROOT,'docs/visual/v1.3');
const RELATIONSHIPS_FIXTURE=path.join(ROOT,'skill/examples/v1.3/relationships-deck.json');
const SOCIAL_PREVIEW_SOURCES=[
  ['KPI dashboard · executive dense','gallery-executive-dense/slide-04.png',4],
  ['Categorical comparison · corporate','gallery-corporate/slide-06.png',6],
  ['Branch swimlane · light','relationships/branch-swimlane-light/slide-01.png',1],
];
const sha256=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const readJson=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const writeJson=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value,null,2)+'\n');};
const writeText=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,value);};
const rel=file=>path.relative(ROOT,file).split(path.sep).join('/');
const walk=(dir,predicate=()=>true)=>{
  if(!fs.existsSync(dir)) return [];
  const found=[];
  for(const entry of fs.readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){
    const file=path.join(dir,entry.name);
    if(entry.isDirectory()) found.push(...walk(file,predicate));
    else if(entry.isFile()&&predicate(file)) found.push(file);
  }
  return found;
};
const resolveInOut=(outRoot,relative)=>{
  const resolved=path.resolve(outRoot,relative);
  if(!resolved.startsWith(path.resolve(outRoot)+path.sep)) throw new Error(`Artifact escapes showcase root: ${relative}`);
  return resolved;
};

function parseArgs(argv){
  const options={outRoot:DEFAULT_OUT,previewRoot:DEFAULT_PREVIEW,baselineRoot:null,reuse:false,noPreviews:false};
  for(let index=0;index<argv.length;index++){
    const arg=argv[index];
    if(arg==='--out-root') options.outRoot=path.resolve(argv[++index]);
    else if(arg==='--preview-root') options.previewRoot=path.resolve(argv[++index]);
    else if(arg==='--baseline-root') options.baselineRoot=path.resolve(argv[++index]);
    else if(arg==='--reuse') options.reuse=true;
    else if(arg==='--no-previews') options.noPreviews=true;
    else if(arg==='--no-render'||arg==='--no-qa') throw new Error('The public showcase requires actual renders and Quality Gate reports');
    else if(arg==='--help'||arg==='-h') {console.log('usage: node scripts/build_showcase.js [--out-root DIR] [--baseline-root DIR] [--reuse] [--no-previews]');process.exit(0);}
    else throw new Error(`Unknown argument ${arg}`);
  }
  if(options.outRoot!==DEFAULT_OUT) throw new Error(`Refusing unexpected showcase output ${options.outRoot}`);
  if(options.previewRoot!==DEFAULT_PREVIEW) throw new Error(`Refusing unexpected preview output ${options.previewRoot}`);
  return options;
}

function reusableBuild(options){
  const manifestPath=path.join(options.outRoot,'showcase.manifest.json');
  if(!fs.existsSync(manifestPath)) return {valid:false,reason:'no existing showcase manifest'};
  let manifest;
  try { manifest=readJson(manifestPath); } catch { return {valid:false,reason:'existing showcase manifest is unreadable'}; }
  const expected=benchmark.currentFingerprint().aggregate_sha256;
  if(manifest.engine_source_fingerprint?.aggregate_sha256!==expected) return {valid:false,reason:'engine fingerprint changed'};
  if(manifest.version!==readJson(path.join(ROOT,'package.json')).version) return {valid:false,reason:'package version changed'};
  if(manifest.matrix?.status!=='PASS'||manifest.gallery?.status!=='PASS'||manifest.ledger?.status!=='PASS') return {valid:false,reason:'a current suite is not PASS'};
  if(!manifest.scenarios?.length||!manifest.scenarios.every(item=>item.before.status==='PASS'&&item.after.status==='PASS'&&['PASS','PASS_WITH_NOTES'].includes(item.comparison.status))) return {valid:false,reason:'before/after comparison is incomplete'};
  const relationshipManifest=path.join(options.outRoot,'relationships/manifest.json');
  if(!fs.existsSync(relationshipManifest)) return {valid:false,reason:'relationships manifest is missing'};
  let relationships;
  try { relationships=readJson(relationshipManifest); } catch { return {valid:false,reason:'relationships manifest is unreadable'}; }
  if(relationships.status!=='PASS'||relationships.fixture?.sha256!==sha256(RELATIONSHIPS_FIXTURE)) return {valid:false,reason:'relationships evidence is stale or not PASS'};
  if(!fs.existsSync(path.join(options.outRoot,'checksums.sha256'))) return {valid:false,reason:'checksum manifest is missing'};
  return {valid:true,manifest};
}

function runBenchmark(options){
  if(options.reuse){
    const existing=reusableBuild(options);
    if(existing.valid){
      console.log('Reusing the existing fingerprint-matched build; no render was regenerated.');
      return {manifest:existing.manifest,mode:'reused-current-build'};
    }
    console.log(`Existing build is not reusable: ${existing.reason}. Rebuilding.`);
  }
  const args=[path.join(ROOT,'scripts/v13_benchmark.js'),'--out-root',options.outRoot];
  if(options.baselineRoot) args.push('--baseline-root',options.baselineRoot);
  const result=spawnSync(process.execPath,args,{cwd:ROOT,stdio:'inherit',timeout:3600000});
  if(result.status!==0) throw new Error(`V1.3 benchmark exited ${result.status}`);
  return {manifest:readJson(path.join(options.outRoot,'showcase.manifest.json')),mode:'fresh-benchmark'};
}

function buildRelationships(options){
  const outRoot=path.join(options.outRoot,'relationships');
  const result=spawnSync(process.execPath,[path.join(ROOT,'tests/build_relationships.js'),'--out-root',outRoot],
    {cwd:ROOT,stdio:'inherit',timeout:1800000});
  if(result.status!==0) throw new Error(`Relationship evidence build exited ${result.status}`);
  const manifest=readJson(path.join(outRoot,'manifest.json'));
  if(manifest.status!=='PASS') throw new Error('Relationship evidence build is not PASS');
  if(manifest.fixture?.sha256!==sha256(RELATIONSHIPS_FIXTURE)) throw new Error('Relationship evidence was not built from the canonical fixture');
  return manifest;
}

function copyPage(outRoot,previewRoot,artifact,pptx,kind,targetRelative){
  const source=resolveInOut(outRoot,artifact.path);
  if(!fs.existsSync(source)) throw new Error(`Rendered page is missing: ${artifact.path}`);
  if(artifact.sha256&&sha256(source)!==artifact.sha256) throw new Error(`Rendered page hash changed after build: ${artifact.path}`);
  const target=path.join(previewRoot,targetRelative);
  fs.mkdirSync(path.dirname(target),{recursive:true});
  fs.copyFileSync(source,target);
  const copied=sha256(target);
  if(artifact.sha256&&copied!==artifact.sha256) throw new Error(`Copied preview hash mismatch: ${targetRelative}`);
  return {path:targetRelative,sha256:copied,bytes:fs.statSync(target).size,kind,
    source:{pptx:pptx.path,pptx_sha256:pptx.sha256,page:artifact.page||null,pages:artifact.pages||null}};
}

function scenarioPreviewPair(manifest){
  for(const scenario of manifest.scenarios||[]) {
    const beforePages=scenario.before?.render?.pages||[];
    const afterPages=scenario.after?.render?.pages||[];
    if(!scenario.before?.pptx||!scenario.after?.pptx||!afterPages.length) continue;
    const pairs=afterPages.map(afterPage=>({afterPage,beforePage:beforePages.find(page=>page.page===afterPage.page)}))
      .filter(pair=>pair.beforePage);
    if(pairs.length) return {scenario,...(pairs.find(pair=>pair.beforePage.sha256!==pair.afterPage.sha256)||pairs[0])};
  }
  return null;
}

function collectPreviews(outRoot,previewRoot){
  const manifest=readJson(path.join(outRoot,'showcase.manifest.json'));
  const previews=[];
  for(const profile of ['executive-dense','corporate','dark-executive']){
    const variant=manifest.gallery.variants[profile];
    if(!variant||variant.status!=='PASS') throw new Error(`Gallery variant ${profile} is not PASS`);
    if(variant.render.status!=='PASS'||!variant.render.pages.length) throw new Error(`Gallery variant ${profile} has no actual rendered pages`);
    if(sha256(resolveInOut(outRoot,variant.pptx.path))!==variant.pptx.sha256) throw new Error(`Gallery PPTX hash changed: ${profile}`);
    for(const page of variant.render.pages){
      const name=`gallery-${profile}/slide-${String(page.page).padStart(2,'0')}.png`;
      previews.push(copyPage(outRoot,previewRoot,page,variant.pptx,'gallery-slide',name));
    }
  }
  const ledger=manifest.ledger;
  if(!ledger||ledger.status!=='PASS'||ledger.render.status!=='PASS'||!ledger.render.pages.length) throw new Error('Ledger has no actual rendered pages');
  for(const page of ledger.render.pages){
    const name=`ledger/slide-${String(page.page).padStart(2,'0')}.png`;
    previews.push(copyPage(outRoot,previewRoot,page,ledger.pptx,'ledger-slide',name));
  }
  for(const theme of ['light','dark']){
    const deck=manifest.matrix.themes[theme];
    if(!deck||deck.status!=='PASS'||!deck.contact_sheets.length) throw new Error(`Matrix ${theme} has no actual contact sheets`);
    for(const sheet of deck.contact_sheets){
      const name=`matrix-${theme}/${path.basename(sheet.path)}`;
      previews.push(copyPage(outRoot,previewRoot,sheet,deck.pptx,'matrix-contact-sheet',name));
    }
  }
  const supplemental=manifest.matrix.supplemental;
  if(!supplemental||supplemental.status!=='PASS'||!supplemental.contact_sheets.length) throw new Error('Supplemental charts have no actual contact sheets');
  for(const sheet of supplemental.contact_sheets){
    const name=`matrix-supplemental/${path.basename(sheet.path)}`;
    previews.push(copyPage(outRoot,previewRoot,sheet,supplemental.pptx,'supplemental-contact-sheet',name));
  }
  const relationships=readJson(path.join(outRoot,'relationships/manifest.json'));
  if(relationships.status!=='PASS'||relationships.fixture?.sha256!==sha256(RELATIONSHIPS_FIXTURE)) throw new Error('Relationships evidence is stale or not PASS');
  const inShowcase=artifact=>{
    const resolved=path.resolve(ROOT,artifact.path);
    if(!resolved.startsWith(path.resolve(outRoot)+path.sep)) throw new Error(`Relationship artifact escapes showcase root: ${artifact.path}`);
    return {...artifact,path:path.relative(path.resolve(outRoot),resolved).split(path.sep).join('/')};
  };
  for(const output of relationships.outputs){
    if(output.qa?.status==='FAIL'||output.render?.status!=='PASS'||!output.render.pages.length) throw new Error(`Relationship case ${output.case}-${output.theme} is not rendered and QA-passed`);
    for(const page of output.render.pages){
      const name=`relationships/${output.case}-${output.theme}/slide-${String(page.page).padStart(2,'0')}.png`;
      previews.push(copyPage(outRoot,previewRoot,inShowcase(page),output.pptx,'relationship-slide',name));
    }
    if(output.render.montage) previews.push(copyPage(outRoot,previewRoot,inShowcase(output.render.montage),output.pptx,'relationship-montage',`relationships/${output.case}-${output.theme}/montage.png`));
  }
  const pair=scenarioPreviewPair(manifest);
  if(pair){
    const base=`before-after/${pair.scenario.slug}`;
    previews.push(copyPage(outRoot,previewRoot,pair.beforePage,pair.scenario.before.pptx,'scenario-before-page',`${base}-before.png`));
    previews.push(copyPage(outRoot,previewRoot,pair.afterPage,pair.scenario.after.pptx,'scenario-after-page',`${base}-after.png`));
  }
  return {manifest,relationships,previews};
}

function buildSocialPreview(previewRoot){
  const out=path.join(previewRoot,'social-preview-1280x640.png');
  const meta=path.join(previewRoot,'social-preview-1280x640.json');
  const args=[path.join(ROOT,'scripts/social_preview.py'),'--out',out,'--meta',meta];
  for(const [label,relative,page] of SOCIAL_PREVIEW_SOURCES){
    const sourcePath=path.relative(ROOT,path.join(previewRoot,relative)).split(path.sep).join('/');
    args.push('--source',`${label}|${sourcePath}|${page}`);
  }
  const result=spawnSync('python3',args,{cwd:ROOT,stdio:'inherit',timeout:120000});
  if(result.status!==0) throw new Error(`Social preview composition exited ${result.status}`);
  const recorded=readJson(meta);
  if(recorded.sha256!==sha256(out)) throw new Error('Social preview metadata hash does not match the PNG');
  return {path:path.basename(out),meta:path.basename(meta),sha256:recorded.sha256,size:recorded.size,sources:recorded.sources};
}

function sanitizeShowcaseLogs(outRoot){
  const changed=[];
  for(const file of walk(path.join(outRoot,'logs'),file=>file.endsWith('.log'))){
    const text=fs.readFileSync(file,'utf8'),clean=benchmark.sanitizeText(text);
    if(clean!==text){
      fs.writeFileSync(file,clean);
      changed.push(path.relative(outRoot,file).split(path.sep).join('/'));
    }
  }
  return changed;
}

function writeShowcaseChecksums(outRoot){
  const files=walk(outRoot,file=>path.basename(file)!=='checksums.sha256').sort((a,b)=>rel(a).localeCompare(rel(b)));
  writeText(path.join(outRoot,'checksums.sha256'),files.map(file=>`${sha256(file)}  ${path.relative(outRoot,file).split(path.sep).join('/')}`).join('\n')+'\n');
  return files.length;
}

function preparePreviewRoot(options){
  if(options.noPreviews) return false;
  fs.rmSync(options.previewRoot,{recursive:true,force:true});
  fs.mkdirSync(options.previewRoot,{recursive:true});
  return true;
}

function main(){
  const options=parseArgs(process.argv.slice(2));
  preparePreviewRoot(options);
  const {manifest,mode}=runBenchmark(options);
  const relationships=buildRelationships(options);
  manifest.contract_matrix=benchmark.applyRelationshipEvidence(manifest.contract_matrix,relationships);
  manifest.relationships={manifest:'relationships/manifest.json',status:relationships.status,fixture:relationships.fixture,
    outputs:relationships.outputs.length,visual_review:'NOT_RUN'};
  const sanitizedLogs=sanitizeShowcaseLogs(options.outRoot);
  manifest.sanitization={...(manifest.sanitization||{}),post_relationship_logs:sanitizedLogs};
  writeJson(path.join(options.outRoot,'showcase.manifest.json'),manifest);
  const checksumEntries=writeShowcaseChecksums(options.outRoot);
  if(options.noPreviews){
    console.log(JSON.stringify({out_root:rel(options.outRoot),preview_root:null,previews:0,
      relationships:relationships.outputs.length,version:manifest.version,fingerprint:manifest.engine_source_fingerprint.aggregate_sha256,
      social_preview:null,checksum_entries:checksumEntries,sanitized_logs:sanitizedLogs.length,build_mode:mode,visual_qa:'NOT_RUN',
      tracked_previews:'SKIPPED'},null,2));
    return;
  }
  const {previews}=collectPreviews(options.outRoot,options.previewRoot);
  const socialPreview=buildSocialPreview(options.previewRoot);
  const generatedAt=new Date().toISOString();
  const status={matrix:manifest.matrix.status,gallery:manifest.gallery.status,ledger:manifest.ledger.status,relationships:relationships.status,
    scenarios:manifest.scenarios.map(item=>({slug:item.slug,before:item.before.status,after:item.after.status,comparison:item.comparison.status}))};
  const previewManifest={
    schema_version:'1.3',product:'Goujian Strategy Slides',version:manifest.version,generated_at:generatedAt,
    engine_source_fingerprint:{path:'out/v1.3-showcase/engine-source-fingerprint.json',aggregate_sha256:manifest.engine_source_fingerprint.aggregate_sha256,file_count:manifest.engine_source_fingerprint.file_count},
    generated_from:{manifest:'out/v1.3-showcase/showcase.manifest.json',relationships:'out/v1.3-showcase/relationships/manifest.json',checksums:'out/v1.3-showcase/checksums.sha256',status,build_mode:mode},
    previews,
    social_preview:socialPreview,
    review:{status:'NOT_RUN',note:'These are actual LibreOffice renders of the current generated PPTX files. No visual approval, VisionPASS or publication approval is claimed.'},
    limits:[
      'All fixtures are synthetic/project-authored; no company, customer, personal or third-party asset is included.',
      'Previews are generated only from the PPTX files in this build; older V1.2 previews and review records are not reused.',
      'Native PowerPoint on Windows/macOS/ARM64 and Agensi hosted runtime remain NOT_RUN/NOT_VERIFIED.',
    ],
  };
  writeJson(path.join(options.previewRoot,'preview-manifest.json'),previewManifest);
  writeText(path.join(options.previewRoot,'README.md'),[
    '# Goujian Strategy Slides V1.3 · actual render previews','',
    `Package ${manifest.version}; engine fingerprint ${manifest.engine_source_fingerprint.aggregate_sha256}.`,'',
    'Every PNG below is a direct LibreOffice render of a PPTX generated by the current checkout:',
    '',
    '- `gallery-*/` — 12-page V1.3 business gallery in light, corporate and dark profiles.',
    '- `ledger/` — 5-page multi-document ledger and redundancy-review fixture.',
    '- `matrix-*/` — contact sheets for the accepted native chart matrix cells and supplemental stacked/histogram charts.',
    '- `relationships/` — four canonical relationship examples (true-date timeline, close-date label lanes, branch swimlane, legacy roadmap) built from `skill/examples/v1.3/relationships-deck.json` in light and dark profiles, with per-page QA reports.',
    '- `before-after/` — one same-input V1.2.1 vs current business-scenario page pair when a baseline is supplied; both sides come from the recorded scenario artifacts.',
    '- `social-preview-1280x640.png` — GitHub social preview composed only from three of the rendered slides above; source paths and SHA-256 values are in the companion JSON. It is not uploaded automatically.',
    '',
    'Visual review is `NOT_RUN`. Structural QA, montage inspection and these previews are not a visual approval.','',
  ].join('\n')+'\n');
  const files=walk(options.previewRoot,file=>path.basename(file)!=='checksums.sha256').sort((a,b)=>a.localeCompare(b));
  writeText(path.join(options.previewRoot,'checksums.sha256'),files.map(file=>`${sha256(file)}  ${path.relative(options.previewRoot,file).split(path.sep).join('/')}`).join('\n')+'\n');
  console.log(JSON.stringify({out_root:rel(options.outRoot),preview_root:rel(options.previewRoot),previews:previews.length,
    relationships:relationships.outputs.length,version:manifest.version,fingerprint:manifest.engine_source_fingerprint.aggregate_sha256,
    social_preview:socialPreview.sha256,checksum_entries:checksumEntries,sanitized_logs:sanitizedLogs.length,build_mode:mode,visual_qa:'NOT_RUN'},null,2));
}

if(require.main===module) main();

module.exports={parseArgs,preparePreviewRoot,scenarioPreviewPair,SOCIAL_PREVIEW_SOURCES};
