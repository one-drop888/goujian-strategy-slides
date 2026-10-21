#!/usr/bin/env node
// Build the optional v1.2 showcase from the current engine, fixtures and review records.
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const out = path.join(root, 'out/v1.2-showcase');
const compareRoot = path.join(root, 'out/v12-control/dogfood-round3');
const reviewDocs = path.join(root, 'docs/evidence/v1.2/reviews');
const home = os.homedir();
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const rel = file => path.relative(root, file).split(path.sep).join('/');
const text = value => fs.readFileSync(value, 'utf8');
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
};
const artifact = file => ({ path: rel(file), sha256: sha(file), bytes: fs.statSync(file).size });
const walk = (dir, predicate = () => true) => {
  if (!fs.existsSync(dir)) return [];
  const found = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) found.push(...walk(file, predicate));
    else if (entry.isFile() && predicate(file)) found.push(file);
  }
  return found;
};
const sanitize = value => {
  let result = String(value);
  result = result.split(root + '/' ).join('');
  result = result.split(root).join('.');
  result = result.split(home + '/').join('~/');
  result = result.split(home).join('~');
  return result;
};
const sanitizeTextFile = file => {
  const before = text(file);
  const after = sanitize(before);
  if (after !== before) fs.writeFileSync(file, after);
  return after !== before;
};

if (path.dirname(out) !== path.join(root, 'out') || path.basename(out) !== 'v1.2-showcase') {
  throw new Error(`Refusing to replace unexpected showcase path: ${out}`);
}
fs.rmSync(out, { recursive: true, force: true });
execFileSync('node', ['scripts/dogfood_round2.js', '--out-root', 'out/v1.2-showcase'], {
  cwd: root, stdio: 'inherit', timeout: 900000,
});

const sanitized = [];
for (const file of walk(out, file => file.endsWith('.qa.json') || file.endsWith('.render.json'))) {
  if (sanitizeTextFile(file)) sanitized.push(rel(file));
}

const dogfoodFile = path.join(out, 'dogfood.json');
const dogfood = JSON.parse(text(dogfoodFile));
for (const item of dogfood.decks) {
  for (const value of Object.values(item.hashes || {})) {
    if (value && value.path && fs.existsSync(path.join(root, value.path))) value.sha256 = sha(path.join(root, value.path));
  }
}
fs.writeFileSync(dogfoodFile, JSON.stringify(dogfood, null, 2) + '\n');
fs.rmSync(path.join(out, 'dogfood.sha256'), { force: true });

const review = path.join(out, 'review');
fs.mkdirSync(review, { recursive: true });
const reviewNames = fs.readdirSync(reviewDocs).filter(name => name !== 'SOURCE.json').sort();
for (const name of reviewNames) fs.copyFileSync(path.join(reviewDocs, name), path.join(review, name));
writeJson(path.join(review, 'review-status.json'), {
  status: 'PRE_FINAL_REVIEWS_ONLY',
  final_visual_status: 'NOT_RUN',
  final_visual_note: 'Codex performs final actual VQA after the writer stops. Do not cite this folder as publication approval.',
  accepted_engine: {
    head: '2c622db52ff53d2f3f90a6581550f69a978022ef',
    check: '15/15 independent adversarial/native/export checks',
    scope: 'engine acceptance at that commit, not publication approval',
  },
  visual_reviews: [
    'codex-round2-preview-review.md records the actual round-2 preview and the two copy defects fixed before this showcase build.',
    'codex-fullsize-round2-reviewed.json records partial full-size page inspection; it is not a complete deck approval.',
    'codex-source-pptx-acceptance.md records native source PPTX provenance requirements and scope.',
  ],
  copy_fixes: [
    'Q4 summary statement shortened while preserving A1-A6 and the three groups; all Q4 variants rerendered.',
    'Multimodal chart-page subtitle replaced with short business Chinese; detailed denominator/cohort/dedup/cross-period/significance limits remain in claims, notes and appendix.',
  ],
  limitations: [
    'Native PowerPoint on macOS, Windows and ARM64 was not executed: NOT_RUN.',
    'Font measurement is an estimate; structural QA does not prove the absence of rendered text collisions.',
    'Linux x86_64 is the only executed host for this evidence.',
  ],
});

const plans = {
  'executive-incomplete-business': 'skill/reasoning/fixtures/executive-incomplete-business',
  'q4-six-actions': 'skill/reasoning/fixtures/q4-six-actions',
  'multimodal-consolidation': 'skill/reasoning/fixtures/multimodal-consolidation',
};
const profiles = {
  light: null,
  'brand-blue': 'skill/reasoning/fixtures/themes/brand-blue.profile.json',
  dark: 'skill/profiles/dark-executive/profile.json',
};
const caseDir = item => item.kind === 'plan' ? 'decks'
  : item.kind === 'theme-variant' ? 'theme-variants'
  : item.kind === 'legacy-long-title' ? 'long-title'
  : item.kind === 'dark-chart-types' ? 'dark-chart-types' : null;

function copyInputs(item) {
  const dir = path.join(out, 'cases', item.kind === 'theme-variant' ? `theme-${item.name}` : item.name, 'inputs');
  fs.mkdirSync(dir, { recursive: true });
  const inputs = [];
  const note = lines => fs.writeFileSync(path.join(dir, 'README.md'), lines.join('\n') + '\n');
  if (item.kind === 'plan') {
    const fixture = plans[item.name];
    const sourceDir = path.join(root, fixture);
    fs.cpSync(path.join(sourceDir, 'plan.json'), path.join(dir, 'plan.json'));
    if (fs.existsSync(path.join(sourceDir, 'sources'))) fs.cpSync(path.join(sourceDir, 'sources'), path.join(dir, 'sources'), { recursive: true });
    const plan = JSON.parse(text(path.join(sourceDir, 'plan.json')));
    const assets = [];
    for (const source of plan.sources || []) {
      if (!source.path) continue;
      const resolved = path.resolve(sourceDir, source.path);
      if (fs.existsSync(resolved) && resolved.startsWith(root + path.sep)) {
        assets.push({ source_id: source.id, canonical_path: rel(resolved), sha256: sha(resolved) });
      }
    }
    writeJson(path.join(dir, 'asset-references.json'), assets);
    inputs.push({ role: 'reference-copy', path: rel(path.join(dir, 'plan.json')), sha256: sha(path.join(dir, 'plan.json')) });
    note([
      'Reference copy of the canonical plan input. The executable copy in this bundle is:',
      `- ${fixture}/plan.json`,
      `Reproduce from the bundle root: node skill/scripts/compile_plan.js ${fixture}/plan.json --out out/reproduced/${item.name}.pptx --spec-out out/reproduced/${item.name}.spec.json --force`,
      'Relative source and asset paths are authored for the canonical fixture directory; use the canonical path above, not this copied file.',
      'See asset-references.json for canonical asset paths and hashes.',
    ]);
  } else if (item.kind === 'theme-variant') {
    fs.cpSync(path.join(root, plans['q4-six-actions'], 'plan.json'), path.join(dir, 'plan.json'));
    inputs.push({ role: 'reference-copy', path: rel(path.join(dir, 'plan.json')), sha256: sha(path.join(dir, 'plan.json')) });
    const profile = profiles[item.name];
    if (profile) {
      fs.copyFileSync(path.join(root, profile), path.join(dir, 'profile.json'));
      inputs.push({ role: 'profile', path: rel(path.join(dir, 'profile.json')), sha256: sha(path.join(dir, 'profile.json')), canonical_path: profile });
    }
    note([
      `Theme variant "${item.name}" of the canonical q4-six-actions plan.`,
      `Canonical plan: ${plans['q4-six-actions']}/plan.json`,
      `Profile: ${profile || 'automatic selection (light executive default)'}`,
      `Reproduce from the bundle root: node skill/scripts/compile_plan.js ${plans['q4-six-actions']}/plan.json --out out/reproduced/theme-${item.name}.pptx --spec-out out/reproduced/theme-${item.name}.spec.json${profile ? ` --profile ${profile}` : ''} --force`,
    ]);
  } else {
    const spec = path.join(root, item.spec);
    fs.copyFileSync(spec, path.join(dir, 'spec.json'));
    inputs.push({ role: 'spec', path: rel(path.join(dir, 'spec.json')), sha256: sha(path.join(dir, 'spec.json')), canonical_path: item.spec });
    if (item.kind === 'legacy-long-title') {
      fs.copyFileSync(path.join(root, 'skill/examples/title-subtitle-layout.json'), path.join(dir, 'source-example.json'));
      inputs.push({ role: 'source-example', path: rel(path.join(dir, 'source-example.json')), sha256: sha(path.join(dir, 'source-example.json')) });
      note([
        'Long-title regression input. Reproduce from the bundle root:',
        'node skill/scripts/build_deck.js skill/examples/title-subtitle-layout.json out/reproduced/long-title.pptx --force',
      ]);
    } else {
      note([
        'Eight-type native dark chart diagnostic. Reproduce from the bundle root:',
        'node scripts/dogfood_round2.js --out-root out/reproduced-dark',
        'The generated spec is kept here as the exact build input.',
      ]);
    }
  }
  return { dir: rel(dir), files: inputs };
}

function renderArtifacts(item) {
  const renderDir = path.join(root, item.render.render_dir);
  const pages = walk(renderDir, file => /[/\\]slide-\d+\.png$/.test(file)).sort((a, b) => {
    const na = Number(a.match(/slide-(\d+)\.png$/)[1]);
    const nb = Number(b.match(/slide-(\d+)\.png$/)[1]);
    return na - nb;
  });
  return {
    report: artifact(path.join(root, item.render.render_report)),
    montage: artifact(path.join(root, item.render.montage)),
    pdf: artifact(path.join(root, item.render.pdf)),
    pages: pages.map(artifact),
  };
}

function compareCase(item) {
  const name = item.kind === 'theme-variant' ? `theme-${item.name}` : item.name;
  const base = caseDir(item);
  const pairs = [];
  const finalDir = item.render.render_dir ? path.join(root, item.render.render_dir) : null;
  const beforeDir = path.join(compareRoot, base, item.kind === 'theme-variant' ? `theme-${item.name}` : item.kind === 'legacy-long-title' ? 'render' : item.kind === 'dark-chart-types' ? 'render' : `${item.name}-render`);
  if (!finalDir || !fs.existsSync(beforeDir)) return { status: 'NOT_COMPARABLE', pairs: [] };
  for (const file of walk(finalDir, value => /[/\\]slide-\d+\.png$/.test(value))) {
    const leaf = file.match(/slide-\d+\.png$/)[0];
    const before = path.join(beforeDir, leaf);
    if (!fs.existsSync(before)) continue;
    const afterSha = sha(file), beforeSha = sha(before);
    pairs.push({ page: Number(leaf.match(/\d+/)[0]), before_sha256: beforeSha, after_sha256: afterSha, identical: beforeSha === afterSha });
  }
  return { status: pairs.every(pair => pair.identical) ? 'RENDER_IDENTICAL' : 'RENDER_CHANGED', pairs };
}

const cases = [];
for (const item of dogfood.decks) {
  const name = item.kind === 'theme-variant' ? `theme-${item.name}` : item.name;
  const caseRoot = path.join(out, 'cases', name);
  fs.mkdirSync(caseRoot, { recursive: true });
  const inputs = copyInputs(item);
  const comparison = compareCase(item);
  const caseRecord = {
    id: name,
    kind: item.kind,
    name: item.name,
    theme: item.theme || null,
    verification: item.verification || item.reasoning_status || null,
    qa_status: item.qa?.status,
    structural_qa: item.qa?.spatial,
    visual_status: 'FINAL_CODEX_VQA_PENDING',
    visual_note: comparison.status === 'RENDER_IDENTICAL'
      ? 'Page renders are identical to the pre-fix round-3 review set; final Codex VQA still pending.'
      : 'Copy/theme case changed by the bounded fixes; inspect the final actual render.',
    render_comparison: comparison.status,
    changed_pages: comparison.pairs.filter(pair => !pair.identical).map(pair => pair.page),
    inputs,
    exported_spec: artifact(path.join(root, item.spec)),
    pptx: artifact(path.join(root, item.pptx)),
    reasoning: item.reasoning && fs.existsSync(path.join(root, item.reasoning)) ? artifact(path.join(root, item.reasoning)) : null,
    scene: item.scene ? artifact(path.join(root, item.scene)) : null,
    qa: item.qa?.report ? artifact(path.join(root, item.qa.report)) : null,
    render: renderArtifacts(item),
  };
  writeJson(path.join(caseRoot, 'manifest.json'), caseRecord);
  cases.push(caseRecord);
}

const before = path.join(out, 'before');
fs.mkdirSync(before, { recursive: true });
const beforeFiles = [
  ['out/v12-control/dogfood-round3/decks/q4-six-actions-render/slide-2.png', 'q4-summary-light-before.png'],
  ['out/v12-control/dogfood-round3/theme-variants/theme-light/slide-2.png', 'q4-summary-theme-light-before.png'],
  ['out/v12-control/dogfood-round3/theme-variants/theme-brand-blue/slide-2.png', 'q4-summary-theme-brand-blue-before.png'],
  ['out/v12-control/dogfood-round3/theme-variants/theme-dark/slide-2.png', 'q4-summary-theme-dark-before.png'],
  ['out/v12-control/dogfood-round3/decks/multimodal-consolidation-render/slide-3.png', 'multimodal-chart-page3-before.png'],
];
const beforeRecords = [];
for (const [source, name] of beforeFiles) {
  const sourceFile = path.join(root, source);
  if (!fs.existsSync(sourceFile)) continue;
  const target = path.join(before, name);
  fs.copyFileSync(sourceFile, target);
  beforeRecords.push({ ...artifact(target), source_render: source });
}
writeJson(path.join(before, 'README.json'), {
  note: 'Pre-fix round-3 renders, kept separate from current cases. Not reviewed as final output.',
  files: beforeRecords,
});

const fingerprint = [];
const addFingerprint = file => {
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) return;
  if (file.includes(`${path.sep}__pycache__${path.sep}`) || file.endsWith('.pyc')) return;
  fingerprint.push({ path: rel(file), sha256: sha(file) });
};
for (const file of walk(path.join(root, 'core'))) addFingerprint(file);
for (const file of walk(path.join(root, 'skill/profiles'))) addFingerprint(file);
for (const file of walk(path.join(root, 'skill/reasoning/fixtures'))) addFingerprint(file);
for (const name of ['storylines', 'archetypes', 'compositions', 'templates', 'analytics']) {
  addFingerprint(path.join(root, 'skill', name, 'registry.json'));
}
for (const file of walk(path.join(root, 'skill/scripts'))) addFingerprint(file);
addFingerprint(path.join(root, 'scripts/dogfood_round2.js'));
addFingerprint(path.join(root, 'scripts/build_showcase.js'));
addFingerprint(path.join(root, 'package.json'));
addFingerprint(path.join(root, 'package-lock.json'));
const fingerprintSorted = fingerprint.filter((item, index, list) => list.findIndex(other => other.path === item.path) === index)
  .sort((left, right) => left.path.localeCompare(right.path));
const aggregate = crypto.createHash('sha256')
  .update(fingerprintSorted.map(item => `${item.sha256}  ${item.path}`).join('\n') + '\n')
  .digest('hex');
writeJson(path.join(out, 'engine-source-fingerprint.json'), {
  algorithm: 'sha256 over sorted "sha256  path" lines',
  aggregate_sha256: aggregate,
  scope: 'runtime core, profiles, reasoning fixtures, registries, CLI scripts, dogfood/showcase builders, package metadata',
  files: fingerprintSorted,
});

const reviewArtifacts = [...reviewNames, 'review-status.json'].map(name => artifact(path.join(review, name)));
const beforeManifest = path.join(out, 'cases');
const manifest = {
  schema_version: '1.0',
  product: 'Goujian Strategy Slides',
  version: JSON.parse(text(path.join(root, 'package.json'))).version,
  generated_at: new Date().toISOString(),
  source_branch: execFileSync('git', ['branch', '--show-current'], { cwd: root, encoding: 'utf8' }).trim(),
  source_head_at_build: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
  source_dirty_at_build: execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).trim().length > 0,
  engine_source_fingerprint: artifact(path.join(out, 'engine-source-fingerprint.json')),
  engine_source_aggregate_sha256: aggregate,
  cases,
  before_variants: beforeRecords,
  review_records: reviewArtifacts,
  case_manifests_root: rel(beforeManifest),
  sanitization: {
    applied_to: sanitized,
    rule: 'The checkout root prefix was replaced with repo-relative paths; the home prefix was replaced with ~. QA statuses, numeric values and PPTX bytes were not altered.',
    verification: 'No absolute developer path is intentionally retained in public JSON/Markdown copies.',
  },
  review_scope: {
    final_visual_status: 'NOT_RUN',
    note: 'Codex final actual VQA is required after the writer stops; this manifest is not a publication approval.',
    native_powerpoint: 'NOT_RUN',
    macos_windows_arm64: 'NOT_RUN',
    agensi_hosted_runtime: 'NOT_VERIFIED',
  },
  limits: [
    'All content and screenshots are synthetic or project-authored; they are not real business evidence.',
    'Structural QA and font measurement are estimates and do not prove the absence of rendered text collisions.',
    'Exact PPTX bytes may vary across Office/PptxGenJS versions; artifact hashes in this manifest bind these exact bytes.',
  ],
};
writeJson(path.join(out, 'showcase.manifest.json'), manifest);

fs.writeFileSync(path.join(out, 'README.md'), [
  '# Goujian Strategy Slides v1.2.0 · showcase',
  '',
  'This optional showcase accompanies the lightweight installer. It contains eight synthetic cases: three audited reasoning decks, three theme variants of the Q4 decision deck, one eight-type native dark chart diagnostic, and one long-title regression deck.',
  '',
  'Each case has a reference input, exported spec, native PPTX, reasoning sidecar where applicable, hash-bound scene, QA report, actual LibreOffice render, montage, PDF and manifest. `sources/` contains the native source PPTX decks and reviewer-checkable table/chart/image provenance. `review/` contains pre-final Codex review records; final VQA is pending after the writer stops.',
  '',
  '## Reproduce',
  '',
  'From the bundle root:',
  '',
  '```bash',
  'npm ci',
  'npm run showcase',
  'npm run package:showcase',
  '```',
  '',
  '`npm run showcase` regenerates this folder with `scripts/dogfood_round2.js`. Exported specs use paths relative to this folder. Keep `out/v1.2-showcase/` at the same relative location inside the extracted showcase ZIP; the normal installer files provide `skill/examples/assets/`, profiles and fixtures.',
  '',
  '## Copy fixes in this build',
  '',
  '- Q4 summary statement shortened; all six action IDs and the three dependency groups are preserved across light, brand-blue and dark variants.',
  '- Multimodal chart-page subtitle replaced with a short business Chinese line. Detailed denominator, cohort, dedup, cross-period and significance limits remain in claims, speaker notes and the appendix.',
  '',
  '## Data and rights',
  '',
  'All fixtures, screenshots and illustrations are synthetic or project-authored under Apache-2.0. No third-party corporate template, logo, font file or private corpus is included. No font is embedded in the PPTX. The AI-generated showroom illustration is scenery, not business evidence.',
  '',
  '## Review boundary',
  '',
  'The pre-final records include 15/15 independent engine acceptance at `2c622db` and partial visual reviews. They are not publication approval. Actual macOS/Windows/ARM64 PowerPoint execution is `NOT_RUN`; Agensi hosted runtime is `NOT_VERIFIED`. See `showcase.manifest.json`, `review/review-status.json` and `engine-source-fingerprint.json`.',
  '',
].join('\n') + '\n');

const manifestFile = path.join(out, 'showcase.manifest.json');
const checksumFiles = walk(out, file => path.basename(file) !== 'showcase.sha256')
  .sort((left, right) => rel(left).localeCompare(rel(right)));
const lines = checksumFiles.map(file => `${sha(file)}  ${rel(file)}`).join('\n') + '\n';
fs.writeFileSync(path.join(out, 'showcase.sha256'), lines);
console.log(`PASS: showcase built with ${cases.length} cases, ${reviewArtifacts.length} review records, ${beforeRecords.length} before variants`);
console.log(`Fingerprint: ${aggregate}`);
console.log(`Manifest: ${rel(manifestFile)}`);
