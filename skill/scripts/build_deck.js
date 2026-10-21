#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { buildDeck } = require('../../core/renderer');
const {execFileSync}=require('child_process');

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('usage: build_deck.js deck.json out.pptx [--profile profile-id-or-json-path]');
  process.exit(2);
}
const [specPath, outPath] = args;
if(path.resolve(specPath)===path.resolve(outPath)){console.error('FAIL: output must differ from the source spec');process.exit(2);}
const profileIndex = args.indexOf('--profile');
const profile = profileIndex >= 0 ? args[profileIndex + 1] : undefined;
if(profileIndex>=0&&!profile){console.error('FAIL: --profile requires an id or path');process.exit(2);}
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
let visual='UNAVAILABLE';
try {visual=JSON.parse(execFileSync('python3',[path.resolve(__dirname,'../../core/qa/capabilities.py')],{encoding:'utf8',timeout:5000})).VISUAL_QA;}catch {}
console.log('VISUAL_QA='+visual);

buildDeck(spec, outPath, { profile, repoRoot: path.resolve(__dirname, '../..'),specDir:path.dirname(path.resolve(specPath)),specPath })
  .then(r => console.log(`PASS: built ${r.outPath} · profile=${r.profile} · slides=${r.slides}`))
  .catch(err => { console.error(`FAIL: ${err.message}`); process.exit(2); });
