'use strict';
const {test,after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {buildDeck} = require('../core/renderer');
const {analyze} = require('../core/analytics');
const {validateDeck} = require('../core/schema/validate');
const {inspectNarrative} = require('../core/semantics/narrative');
const benchmark = require('../scripts/v13_benchmark');

const ROOT = path.resolve(__dirname, '..');
const FIXTURES = path.join(ROOT, 'skill/examples/v1.3');
const INPUTS = path.join(FIXTURES, 'inputs');
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'goujian-v13-benchmark-'));
const scratch = name => {
  const dir = path.join(tempRoot, name);
  fs.mkdirSync(dir, {recursive: true});
  return dir;
};

test('matrix fixture is reproducible: 96 cells, 6 families, 2 themes, explicit rejects', () => {
  const declared = readJson(path.join(FIXTURES, 'matrix-cases.json'));
  assert.deepEqual(benchmark.generateMatrixFixture(), declared);
  assert.equal(declared.counts.cells, 96);
  assert.equal(declared.counts.accepted, 72);
  assert.equal(declared.counts.rejected, 24);
  assert.deepEqual(declared.native_chart_families, benchmark.MATRIX_FAMILIES);
  assert.equal(declared.native_chart_families.length, 6);
  assert.deepEqual(declared.cases, benchmark.MATRIX_CASES);
  assert.deepEqual(Object.keys(declared.themes), ['light', 'dark']);
  for (const cell of declared.cells) {
    assert.equal(cell.expected === 'ACCEPT', cell.readback !== null);
    if (cell.expected === 'REJECT') {
      assert(cell.rejection && cell.rejection.code && cell.rejection.reason, cell.id);
      assert.equal(cell.series.length > 0, true);
    }
  }
  const acceptedPerTheme = declared.cells.filter(cell => cell.expected === 'ACCEPT' && cell.theme === 'light');
  assert.equal(acceptedPerTheme.length, 36);
  assert.equal(new Set(acceptedPerTheme.map(cell => cell.family)).size, 6);
  assert.equal(new Set(declared.cells.filter(cell => cell.expected === 'REJECT').map(cell => cell.rejection.code)).size, 6);
  for (const theme of ['light', 'dark']) {
    const single = declared.cells.find(cell => cell.id === `${theme === 'light' ? 'L' : 'D'}-area-single`);
    assert.equal(single.expected, 'REJECT');
    assert.equal(single.rejection.code, 'AREA_SINGLE_POINT');
  }
});

test('declared source inputs are byte-identical, uniquely hashed and ledger-consistent', () => {
  const ledger = readJson(path.join(INPUTS, 'source-ledger.json'));
  const documents = [];
  for (const item of benchmark.SCENARIOS) {
    const canonical = path.join(ROOT, 'skill/analytics', item.input);
    const copied = path.join(INPUTS, item.input);
    assert.deepEqual(fs.readFileSync(canonical), fs.readFileSync(copied), `${item.input} differs from its canonical source`);
    const declared = ledger.documents.find(document => document.id === item.id);
    assert(declared, `${item.id} missing from ledger`);
    assert.equal(declared.sha256, require('crypto').createHash('sha256').update(fs.readFileSync(copied)).digest('hex'));
    assert.equal(declared.bytes, fs.statSync(copied).size);
    const raw = readJson(copied);
    assert.deepEqual(declared.period, raw.period, `${item.id} period must be the raw current-snapshot period`);
    documents.push(declared);
  }
  const business = documents.find(document => document.id === 'synthetic-business-performance');
  assert.deepEqual(business.trend_period, {start: '2026-04', end: '2026-09', basis: 'trend'});
  assert.match(business.period_note, /raw declared reporting window[\s\S]*trend[\s\S]*previous_month/);
  const matrixFile = path.join(FIXTURES, 'matrix-cases.json');
  const derivative = ledger.derivatives.find(item => item.id === 'v13-matrix-cases');
  assert.equal(derivative.sha256, require('crypto').createHash('sha256').update(fs.readFileSync(matrixFile)).digest('hex'));
  assert.equal(derivative.bytes, fs.statSync(matrixFile).size);
  assert.equal(new Set(documents.map(document => document.sha256)).size, documents.length);
  const checked = benchmark.checkSourceLedger(scratch('ledger'));
  assert.equal(checked.status, 'PASS');
  assert.deepEqual(checked.issues, []);
});

test('ledger check rejects a stale period and a stale derivative hash instead of passing on bytes alone', () => {
  const actual = benchmark.sourceLedger();
  const stale = JSON.parse(JSON.stringify(actual));
  assert.deepEqual(stale.documents[0].period, {start: '2026-09-01', end: '2026-09-30'});
  stale.documents[0].period = {start: '2026-06-01', end: '2026-09-30'};
  stale.derivatives[0].sha256 = '0'.repeat(64);
  const issues = benchmark.sourceLedgerIssues(stale, actual);
  assert(issues.some(issue => /synthetic-business-performance period differs from checked-in ledger/.test(issue)), issues.join('; '));
  assert(issues.some(issue => /derivative v13-matrix-cases sha256 differs from checked-in ledger/.test(issue)), issues.join('; '));
  assert.deepEqual(benchmark.sourceLedgerIssues(actual, actual), []);
});

test('all declared rejection cells fail with their named contract', async () => {
  const fixture = benchmark.generateMatrixFixture();
  const result = await benchmark.testMatrixRejections(fixture, scratch('rejects'));
  assert.equal(result.status, 'PASS');
  assert.equal(result.unique_rejections, 12);
  assert.equal(result.cells_rejected_in_matrix, 24);
  for (const item of result.results) {
    assert.equal(item.status, 'PASS', `${item.id}: ${item.observed_error}`);
    assert.equal(item.expected, 'REJECT');
  }
});

test('waterfall, scatter and bubble are explicitly NOT_SUPPORTED with a histogram alternative', async () => {
  const result = await benchmark.testUnsupported(scratch('unsupported'));
  assert.equal(result.status, 'PASS');
  assert.deepEqual(result.results.map(item => item.chartType), ['waterfall', 'scatter', 'bubble']);
  for (const item of result.results) {
    assert.equal(item.status, 'NOT_SUPPORTED');
    assert.match(item.honest_alternative, /histogram/);
  }
});

test('stacked bar/column and explicit equal-width histogram survive native readback', async () => {
  const result = await benchmark.buildSupplemental(scratch('supplemental'), {render: false, qa: false});
  assert.equal(result.status, 'PASS', JSON.stringify(result.issues));
  assert.equal(result.checks.native_charts, 3);
  assert.equal(result.checks.stacked_bar_grouping, 'stacked');
  assert.equal(result.checks.stacked_column_grouping, 'stacked');
  const bins = benchmark.supplementalSlides().bins;
  assert.deepEqual(result.checks.histogram_labels, bins.map(bin => `${bin.start}–${bin.end}`));
  for (let index = 1; index < bins.length; index++) {
    assert.equal(bins[index].start, bins[index - 1].end);
    assert.equal(bins[index].end - bins[index].start, bins[0].end - bins[0].start);
  }
  assert.deepEqual(result.checks.histogram_counts, bins.map(bin => bin.count));
});

test('one full theme deck keeps native kinds, values, labels, null/zero and workbooks', async () => {
  const fixture = benchmark.generateMatrixFixture();
  const {cells, spec} = await benchmark.matrixDeckSpec(fixture, 'light');
  const dir = scratch('matrix-light');
  const pptx = path.join(dir, 'deck.pptx');
  await buildDeck(spec, pptx, {profile: benchmark.MATRIX_THEMES.light, specDir: dir});
  const result = await benchmark.verifyMatrixDeck(pptx, spec, cells);
  assert.equal(result.status, 'PASS', JSON.stringify(result.deck_issues));
  assert.equal(result.counts.charts_checked, 36);
  assert.equal(result.counts.native_cache_checked, 36);
  assert.equal(result.counts.xlsx_checked, 36);
  assert.equal(result.counts.nulls_checked, 3);
  assert.equal(result.counts.zeros_checked, 3);
  assert(result.counts.values_checked >= 140);
  for (const cell of result.cells) assert.equal(cell.status, 'PASS', `${cell.id}: ${JSON.stringify(cell.issues)}`);
});

test('gallery metrics reconcile to raw facts and retain fraction/pp/CNY display semantics', () => {
  const gallery = readJson(path.join(FIXTURES, 'gallery-deck.json'));
  assert.deepEqual(validateDeck(gallery), []);
  const sources = {}, audits = {};
  for (const item of benchmark.SCENARIOS) {
    const raw = readJson(path.join(INPUTS, item.input));
    sources[item.id] = raw;
    audits[item.id] = analyze(raw).audit.metrics;
  }
  const result = benchmark.metricReconciliation(gallery, sources, audits);
  assert.equal(result.status, 'PASS', JSON.stringify(result.issues));
  assert.equal(result.metric_count, 40);
  assert(result.percent_fraction_metrics.length >= 3);
  assert(result.percentage_point_metrics.length >= 2);
  assert(result.currency_display_scale_metrics >= 2);
  for (const metric of gallery.metrics.filter(item => item.type === 'pp')) assert(metric.comparison_basis, metric.id);
  for (const metric of gallery.metrics.filter(item => item.type === 'currency')) assert.match(metric.currency || '', /^[A-Z]{3}$/);
  const narrative = inspectNarrative(gallery);
  assert.deepEqual(narrative.errors, []);
  assert.equal(narrative.coverage.total_slides, gallery.slides.length);
  assert.equal(narrative.coverage.claims, narrative.coverage.total_claims);
  assert.equal(narrative.review_required, true);
});

test('gallery histogram covers the declared window and discloses its unobserved tail', () => {
  const gallery = readJson(path.join(FIXTURES, 'gallery-deck.json'));
  const slide = gallery.slides.find(item => item.type === 'histogram');
  assert(slide, 'gallery histogram is missing');
  assert.equal(slide.period, '2026-08-01 至 2026-09-30 · 获客日期 7 天等宽分箱');
  assert.equal(slide.bins.length, 9);
  assert.equal(slide.bins[0].start, 0);
  assert.equal(slide.bins.at(-1).end, 63);
  slide.bins.forEach((bin, index) => {
    assert.equal(bin.start, index * 7);
    assert.equal(bin.end, (index + 1) * 7);
  });
  assert.equal(slide.bins.reduce((total, bin) => total + bin.count, 0), 40);
  assert(slide.bins.some(bin => bin.count === 0), 'the August zero week must stay visible');
  assert.equal(slide.bins.at(-1).count, 0, 'the bounded tail bin must stay visible');
  assert.deepEqual(slide.series[0].labels, slide.bins.map(bin => `${bin.start}–${bin.end}`));
  assert.deepEqual(slide.series[0].values, slide.bins.map(bin => bin.count));
  assert.match(slide.insight, /仅观察到 09-30/);
  assert.match(slide.insight, /不按 0 推断/);
  assert.match(slide.insight, /共 9 箱至 63 天/);
});

test('ledger fixture keeps all documents and one deliberate redundancy candidate', () => {
  const ledger = readJson(path.join(FIXTURES, 'ledger-deck.json'));
  assert.deepEqual(validateDeck(ledger), []);
  const narrative = inspectNarrative(ledger);
  assert.deepEqual(narrative.errors, []);
  assert.equal(narrative.redundancy.length, 1);
  assert.equal(narrative.redundancy[0].kind, 'same_claims_and_evidence');
  assert.equal(narrative.review_required, true);
  assert(narrative.bindings.length >= 3);
  assert(narrative.bindings.every(binding => binding.disposition === 'retained'));
  const sourceLedger = readJson(path.join(INPUTS, 'source-ledger.json'));
  const rows = ledger.slides[2].rows.concat(ledger.slides[3].rows).flat().map(String);
  for (const document of sourceLedger.documents) {
    assert(rows.some(value => value.includes(document.path)), document.path);
    assert(rows.some(value => value.includes(document.sha256.slice(0, 12))), document.id);
  }
});

test('public sanitization removes checkout and home prefixes only', () => {
  const cleaned = benchmark.sanitizeValue({
    repo: path.join(ROOT, 'out/v1.3-showcase/showcase.manifest.json'),
    home: path.join(os.homedir(), '.cache/tool'),
    system: '/usr/bin/libreoffice',
    nested: [path.join(ROOT, 'core')],
  });
  assert.equal(cleaned.repo, 'out/v1.3-showcase/showcase.manifest.json');
  assert.equal(cleaned.home, '~/.cache/tool');
  assert.equal(cleaned.system, '/usr/bin/libreoffice');
  assert.deepEqual(cleaned.nested, ['core']);
});

test('unsafe output roots are refused and numeric multiset comparison is order-insensitive', () => {
  assert.throws(() => benchmark.prepareOutRoot(ROOT), /unsafe|refusing/i);
  assert.throws(() => benchmark.prepareOutRoot(path.join(ROOT, 'docs')), /under the checkout out/i);
  assert.throws(() => benchmark.prepareOutRoot(os.homedir()), /unsafe|refusing/i);
  assert.equal(benchmark.specDiff({a: [1, 2, 3]}, {a: [3, 2, 1]}).unique_multiset_unchanged, true);
  assert.equal(benchmark.specDiff({a: [1, 2]}, {a: [1, 2, 3]}).unique_multiset_unchanged, false);
});

test('scenario gate requires same raw bytes, both builds PASS and a supplied baseline', () => {
  const scenario = {before: {status: 'PASS'}, after: {status: 'PASS'}, comparison: {status: 'PASS', same_raw_bytes: true}};
  const args = {scenarios: [scenario], sourceLedgerCheck: {status: 'PASS'}, fingerprint: {aggregate_sha256: 'a'.repeat(64)}};
  assert.equal(benchmark.scenarioGate({...args, baseline: {version: '1.2.1'}}), 'PASS');
  assert.equal(benchmark.scenarioGate({...args, baseline: null}), 'NOT_RUN');
  assert.equal(benchmark.scenarioGate({...args, baseline: {version: '1.2.1'},
    scenarios: [{...scenario, comparison: {...scenario.comparison, same_raw_bytes: false}}]}), 'FAIL');
});

function contractInputs() {
  const themeCells = theme => [
    {id: `${theme}-line-multi`, family: 'line', case: 'multi', theme, status: 'PASS',
      native: {series_names: ['实际', '目标'], series_styles: [{dash: 'solid', marker: 'circle'}, {dash: 'dash', marker: 'square'}], format: '#,##0'}},
    {id: `${theme}-bar-multi`, family: 'bar', case: 'multi', theme, status: 'PASS',
      native: {grouping: 'clustered', series_names: ['实际', '目标'], values: [1, 2, 3, 4], format: '#,##0'}},
    {id: `${theme}-column-multi`, family: 'column', case: 'multi', theme, status: 'PASS',
      native: {grouping: 'clustered', series_names: ['实际', '目标'], values: [1, 2, 3, 4], format: '#,##0'}},
    {id: `${theme}-pie-percentage`, family: 'pie', case: 'percentage', theme, status: 'PASS', native: {format: '0.0%'}},
    {id: `${theme}-pie-single`, family: 'pie', case: 'single', theme, status: 'PASS', native: {format: '0%'}},
    {id: `${theme}-bar-percentage`, family: 'bar', case: 'percentage', theme, status: 'PASS', native: {format: '#,##0.0%'}},
    {id: `${theme}-line-dense`, family: 'line', case: 'dense', theme, status: 'PASS', native: {format: '#,##0'}},
    {id: `${theme}-area-dense`, family: 'area', case: 'dense', theme, status: 'PASS', native: {format: '#,##0'}},
  ];
  const theme = name => ({status: 'PASS', checks: {semantic_qa: 'PASS_WITH_NOTES'}, render: {pages: [{page: 1}]},
    readback: {counts: {dash_checked: 2, marker_checked: 2, grouping_checked: 2}, cells: themeCells(name), deck_issues: []}});
  const variant = profile => ({status: 'PASS', spec: {sha256: 'gallery-spec'}, checks: {fonts: 'PASS', spatial: 'PASS'},
    render: {pages: [{page: 1}]}});
  return {
    matrix: {
      status: 'PASS', themes: {light: theme('light'), dark: theme('dark')},
      rejections: {status: 'PASS', results: ['PIE_SINGLE_SERIES', 'PIE_NONNEGATIVE', 'PIE_MISSING'].map(code => ({id: code, code, case: 'multi', status: 'PASS'}))},
      supplemental: {status: 'PASS', checks: {histogram_labels: ['0–10'], histogram_counts: [3]}},
    },
    gallery: {
      status: 'PASS',
      reconciliation: {status: 'PASS', percent_fraction_metrics: ['conv_aug'], percentage_point_metrics: ['conv_delta']},
      dashboards: [{unit: '万元', labels: 6, series: [{name: '实际', metric_ids: 6}]}],
      cohorts: [20, 10, 30, 7, 23].map((denominator, index) => ({id: `cohort-${index}`, denominator})),
      comparison_bases: ['mature_cohort', 'descriptive_branch_not_causal'],
      histogram: {status: 'PASS', bins: 9, width: 7, first: {start: 0}, last: {end: 63}, count_sum: 40, zero_bins: ['21–28', '56–63'], window_note: true},
      title_fit: {max_length: 46, long_titles: [{title_short: true}], title_short_count: 2, subtitle_count: 2},
      variants: {'executive-dense': variant(), corporate: variant(), 'dark-executive': variant()},
      max_title_length: 46,
    },
    ledger: {status: 'PASS', narrative: {redundancy: [{kind: 'same_claims_and_evidence'}], review_required: true,
      bindings: [{evidence_id: 'e', slide: 2, disposition: 'retained'}]}, issues: []},
    scenarios: [{slug: 'sales-conversion', before: {status: 'PASS'}, after: {status: 'PASS'}, comparison: {status: 'PASS', same_raw_bytes: true}}],
    sourceLedgerCheck: {status: 'PASS', documents: [{id: 'a'}, {id: 'b'}, {id: 'c'}]},
    fingerprint: {aggregate_sha256: 'a'.repeat(64)},
  };
}

function relationshipOutputs() {
  const timeline = (name, theme) => ({
    case: name, theme, spec: {sha256: `spec-${name}`}, pptx: {path: `out/v1.3-showcase/relationships/${name}-${theme}.pptx`},
    qa: {status: 'PASS_WITH_NOTES', checks: {visual_review: 'NOT_RUN'}}, render: {status: 'PASS', pages: [{page: 1}]},
    evidence: name === 'dated-timeline'
      ? {marker_positions: [1.04, 3.765, 6.49, 9.215, 11.94].map((x, index) => ({id: `m${index}`, x, label_lane: 0})),
        date_labels: ['2026-01-05', '2026-02-02', '2026-03-02', '2026-03-30', '2026-04-27'],
        durations: [{id: 'pilot', days: 18}], leaders: []}
      : {marker_positions: [{id: 'sep1', x: 1.04, label_lane: 0}, {id: 'sep2', x: 1.2216666666666665, label_lane: 1}, {id: 'oct31', x: 11.94, label_lane: 0}],
        date_labels: ['2026-09-01', '2026-09-02', '2026-10-31'], durations: [], leaders: ['sep2']},
  });
  const branch = theme => ({
    case: 'branch-swimlane', theme, spec: {sha256: 'spec-branch'}, pptx: {path: `out/v1.3-showcase/relationships/branch-swimlane-${theme}.pptx`},
    qa: {status: 'PASS_WITH_NOTES', checks: {visual_review: 'NOT_RUN'}}, render: {status: 'PASS', pages: [{page: 1}]},
    evidence: {task_nodes: ['A', 'B', 'C', 'D', 'E'].map(id => ({id, owner: '团队', date: '2026 Q1', status: '进行中'})),
      swimlane_labels: ['业务', '决策', '研究'], decision_edges: ['完成后评估', '达到门槛', '未达门槛', '暂停投入'],
      dependencies: [{from: 'A', to: 'B'}, {from: 'B', to: 'C'}]},
  });
  const roadmap = theme => ({
    case: 'roadmap', theme, spec: {sha256: 'spec-roadmap'}, pptx: {path: `out/v1.3-showcase/relationships/roadmap-${theme}.pptx`},
    qa: {status: 'PASS_WITH_NOTES', checks: {visual_review: 'NOT_RUN'}}, render: {status: 'PASS', pages: [{page: 1}]},
    evidence: {lane_headings: ['产品', '运营', '研究']},
  });
  return {
    status: 'PASS', fixture: {sha256: 'fixture'},
    outputs: ['light', 'dark'].flatMap(theme => [timeline('dated-timeline', theme), timeline('dated-timeline-close', theme), branch(theme), roadmap(theme)]),
  };
}

test('A–N maps the documented user questions and relationship gates stay NOT_RUN until evidence exists', () => {
  const contract = benchmark.contractMatrix(contractInputs());
  assert.deepEqual(contract.map(item => item.id), 'ABCDEFGHIJKLMN'.split(''));
  assert.deepEqual(contract.map(item => item.question), [
    'Are multiple lines distinguishable?',
    'Are grouped bars/columns comparable?',
    'Are composition values/labels truthful?',
    'Does the dashboard retain units and comparisons?',
    'Are percentages distinct from pp?',
    'Are sales denominators/cohorts correct?',
    'Does a histogram use real numeric bins?',
    'Are actual time distances preserved?',
    'Are branches/roles preserved?',
    'Are dependencies inspectable?',
    'Are long titles and dense evidence readable?',
    'Is multi-document evidence retained?',
    'Is the same content usable across themes?',
    'Can evidence be traced to source/version?',
  ]);
  for (const item of contract) {
    assert(item.scope.length > 0, item.id);
    assert(item.evidence.length > 0, item.id);
    assert(item.checks, item.id);
    assert(!['H', 'I', 'J'].includes(item.id) || item.status === 'NOT_RUN', item.id);
  }
  assert.equal(contract.find(item => item.id === 'K').status, 'PASS');
  assert.equal(contract.find(item => item.id === 'K').visual_review, 'NOT_RUN');
  assert.equal(contract.find(item => item.id === 'N').status, 'NOT_RUN');
  const withBaseline = benchmark.contractMatrix({...contractInputs(),
    baseline: {version: '1.2.1', immutable: true, fingerprint: {aggregate_sha256: 'b'.repeat(64)}}});
  assert.equal(withBaseline.find(item => item.id === 'N').status, 'PASS');
  assert.equal(withBaseline.find(item => item.id === 'A').checks.dash_marker_checked.light, 2);
  assert.equal(withBaseline.find(item => item.id === 'B').checks.grouping_checked, 4);
  assert.equal(withBaseline.find(item => item.id === 'G').checks.gallery_histogram.last.end, 63);
});

test('relationship evidence fills H–J and M, and spatially wrong or incomplete evidence fails', () => {
  const relationships = relationshipOutputs();
  const contract = benchmark.applyRelationshipEvidence(benchmark.contractMatrix(contractInputs()), relationships);
  for (const id of ['H', 'I', 'J']) assert.equal(contract.find(item => item.id === id).status, 'PASS', id);
  assert.equal(contract.find(item => item.id === 'H').checks.timeline_spacing.length, 4);
  assert.equal(contract.find(item => item.id === 'H').checks.close_date_lanes.length, 2);
  const m = contract.find(item => item.id === 'M');
  assert.equal(m.status, 'PASS');
  assert.equal(m.checks.relationships.spec_sha256_parity, true);
  assert.equal(m.checks.relationships.paired_themes.length, 4);

  const wrongSpacing = JSON.parse(JSON.stringify(relationships));
  wrongSpacing.outputs.find(item => item.case === 'dated-timeline-close' && item.theme === 'light').evidence.marker_positions[1].x = 11.9;
  assert.equal(benchmark.relationshipContractEntries(wrongSpacing).find(item => item.id === 'H').status, 'FAIL');

  const incompleteBranch = JSON.parse(JSON.stringify(relationships));
  incompleteBranch.outputs.find(item => item.case === 'branch-swimlane' && item.theme === 'dark').evidence.task_nodes.pop();
  assert.equal(benchmark.relationshipContractEntries(incompleteBranch).find(item => item.id === 'I').status, 'FAIL');

  const divergentTheme = JSON.parse(JSON.stringify(relationships));
  divergentTheme.outputs.find(item => item.case === 'roadmap' && item.theme === 'dark').spec.sha256 = 'different';
  assert.equal(benchmark.applyRelationshipEvidence(benchmark.contractMatrix(contractInputs()), divergentTheme).find(item => item.id === 'M').status, 'FAIL');
});

after(() => fs.rmSync(tempRoot, {recursive: true, force: true}));

test('showcase --no-previews is explicit and render/QA bypass stays rejected', () => {
  const showcase = require('../scripts/build_showcase');
  assert.equal(showcase.parseArgs([]).noPreviews, false);
  assert.equal(showcase.parseArgs(['--no-previews']).noPreviews, true);
  assert.throws(() => showcase.parseArgs(['--no-render']), /actual renders/);
  assert.throws(() => showcase.parseArgs(['--no-qa']), /Quality Gate/);

  const previewRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'goujian-no-previews-'));
  try {
    const retained = path.join(previewRoot, 'existing.txt');
    fs.writeFileSync(retained, 'keep');
    assert.equal(showcase.preparePreviewRoot({previewRoot, noPreviews: true}), false);
    assert.equal(fs.readFileSync(retained, 'utf8'), 'keep');
    assert.equal(showcase.preparePreviewRoot({previewRoot, noPreviews: false}), true);
    assert.equal(fs.existsSync(retained), false);
  } finally {
    fs.rmSync(previewRoot, {recursive: true, force: true});
  }
});

test('reuse fingerprint covers runtime fixtures and changes with an isolated input edit', () => {
  const fingerprint = benchmark.currentFingerprint();
  assert(fingerprint.files.some(file => file.path.startsWith('skill/analytics/')), 'analytics inputs must be fingerprinted');
  assert(fingerprint.files.some(file => file.path.startsWith('skill/examples/v1.3/inputs/')), 'benchmark fixtures must be fingerprinted');
  assert(fingerprint.files.some(file => file.path.startsWith('skill/reasoning/fixtures/')), 'reasoning fixtures must be fingerprinted');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'goujian-fingerprint-'));
  try {
    fs.mkdirSync(path.join(dir, 'skill', 'examples'), {recursive: true});
    const input = path.join(dir, 'skill', 'examples', 'raw.json');
    fs.writeFileSync(input, '{"value":1}\n');
    const before = benchmark.fingerprintTree(dir, {dirs: ['skill']});
    fs.writeFileSync(input, '{"value":2}\n');
    const after = benchmark.fingerprintTree(dir, {dirs: ['skill']});
    assert.notEqual(before.aggregate_sha256, after.aggregate_sha256);
    assert.equal(after.files[0].path, 'skill/examples/raw.json');
  } finally {
    fs.rmSync(dir, {recursive: true, force: true});
  }
});

test('before/after preview pair uses the same recorded scenario page on both sides', () => {
  const showcase = require('../scripts/build_showcase');
  const manifest = {scenarios: [
    {slug: 'no-baseline', before: {status: 'NOT_RUN'}, after: {render: {pages: [{page: 1}]}}},
    {slug: 'same-input', before: {pptx: {path: 'before.pptx'},
      render: {pages: [{page: 1, sha256: 'cover'}, {page: 2, sha256: 'same'}, {page: 3, sha256: 'old'}]}},
      after: {pptx: {path: 'after.pptx'},
        render: {pages: [{page: 1, sha256: 'cover'}, {page: 2, sha256: 'same'}, {page: 3, sha256: 'new'}]}}},
  ]};
  const pair = showcase.scenarioPreviewPair(manifest);
  assert.equal(pair.scenario.slug, 'same-input');
  assert.equal(pair.beforePage.page, 3);
  assert.equal(pair.afterPage.page, 3);
  assert.notEqual(pair.beforePage.sha256, pair.afterPage.sha256);
  assert.equal(showcase.scenarioPreviewPair({scenarios: manifest.scenarios.slice(0, 1)}), null);
});

test('social preview uses three distinct product views, not a cover plus repeated bars', () => {
  const showcase = require('../scripts/build_showcase');
  const sources = showcase.SOCIAL_PREVIEW_SOURCES;
  assert.equal(sources.length, 3);
  assert.equal(new Set(sources.map(item => item[1])).size, 3);
  assert(sources.some(item => item[1].startsWith('gallery-executive-dense/') && item[2] === 4), 'dashboard view');
  assert(sources.some(item => item[1].startsWith('gallery-corporate/') && item[2] === 6), 'categorical comparison view');
  assert(sources.some(item => item[1].startsWith('relationships/branch-swimlane-light/')), 'relationship view');
});

test('a new benchmark cannot delete unrelated output data',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gj-output-protect-'));try{const file=path.join(dir,'user.txt');fs.writeFileSync(file,'retain');assert.throws(()=>benchmark.prepareOutRoot(dir),/ownership marker/);assert.equal(fs.readFileSync(file,'utf8'),'retain');}finally{fs.rmSync(dir,{recursive:true,force:true});}
});
