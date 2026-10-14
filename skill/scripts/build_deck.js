#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { buildDeck } = require('../../core/renderer');

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('usage: build_deck.js deck.json out.pptx [--profile profile-id-or-json-path]');
  process.exit(2);
}
const [specPath, outPath] = args;
const profileIndex = args.indexOf('--profile');
const profile = profileIndex >= 0 ? args[profileIndex + 1] : undefined;
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));

buildDeck(spec, outPath, { profile, repoRoot: path.resolve(__dirname, '../..') })
  .then(r => console.log(`PASS: built ${r.outPath} · profile=${r.profile} · slides=${r.slides}`))
  .catch(err => { console.error(`FAIL: ${err.message}`); process.exit(2); });
