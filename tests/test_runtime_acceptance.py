import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import runtime_acceptance as acceptance  # noqa: E402


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def make_candidate(root, version='1.3.2', extra_files=(), scripts=None):
    root = Path(root)
    (root / 'distribution').mkdir(parents=True, exist_ok=True)
    files = [f'asset-{index:03d}.txt' for index in range(185)]
    for relative in files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'{relative}\n', encoding='utf-8')
    for relative in extra_files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('extra\n', encoding='utf-8')
        files.append(relative)
    package = {
        'name': 'goujian-strategy-slides',
        'version': version,
        'scripts': scripts or {'test': 'smoke', 'test:core': 'core', 'validate:all': 'validate'},
    }
    package_bytes = (json.dumps(package, indent=2) + '\n').encode('utf-8')
    (root / 'package.json').write_bytes(package_bytes)
    (root / 'distribution/runtime-package.json').write_bytes(package_bytes)
    (root / 'SKILL.md').write_text(
        f'---\nname: goujian-strategy-slides\nmetadata:\n  version: "{version}"\n---\n', encoding='utf-8')
    manifest = {
        'schema_version': version,
        'distribution': 'runtime',
        'omitted_commands': ['package', 'preflight', 'showcase'],
        'runtime_files': files,
    }
    (root / 'distribution/runtime-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return root


def make_baseline_zip(path, version='1.3.1'):
    archive = Path(path)
    members = {
        'goujian-strategy-slides/package.json': json.dumps({'version': version}).encode('utf-8'),
        'goujian-strategy-slides/SKILL.md': (
            f'---\nmetadata:\n  version: "{version}"\n---\n').encode('utf-8'),
        'goujian-strategy-slides/payload.txt': b'baseline\n',
    }
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        for name, data in members.items():
            package.writestr(name, data)
    digest = sha256(archive.read_bytes())
    root = archive.parent / 'baseline-root'
    root.mkdir()
    for name, data in members.items():
        target = root / name.split('/', 1)[1]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return archive, root, digest, members


class CandidateEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'runtime'
        make_candidate(self.root)

    def test_expected_candidate_identity_passes(self):
        evidence = acceptance.candidate_runtime_evidence(self.root)
        self.assertEqual(evidence['status'], 'PASS', evidence['failures'])
        self.assertEqual(evidence['declared_runtime_files'], 185)
        self.assertTrue(evidence['source_only_members_absent'])

    def test_wrong_candidate_version_is_rejected(self):
        make_candidate(self.root, version='1.3.1')
        evidence = acceptance.candidate_runtime_evidence(self.root)
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertTrue(any('version' in item for item in evidence['failures']))

    def test_source_only_member_is_rejected(self):
        make_candidate(self.root, extra_files=('scripts/package_runtime.py',))
        evidence = acceptance.candidate_runtime_evidence(self.root)
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertTrue(any('package_runtime.py' in item for item in evidence['failures']))

    def test_reintroduced_package_and_preflight_commands_are_rejected(self):
        make_candidate(self.root, scripts={'test': 'smoke', 'test:core': 'core',
                                           'validate:all': 'validate',
                                           'package': 'packager', 'preflight': 'preflight'})
        evidence = acceptance.candidate_runtime_evidence(self.root)
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertTrue(any('still exposes package' in item for item in evidence['failures']))
        self.assertTrue(any('still exposes preflight' in item for item in evidence['failures']))


class BaselineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive, self.root, self.digest, self.members = make_baseline_zip(
            Path(self.temp.name) / 'baseline.zip')

    def contract(self, digest=None):
        rule = dict(acceptance.CONTRACT)
        if digest is not None:
            rule['locked_baseline_zip_sha256'] = digest
        return rule

    def test_matching_locked_baseline_passes_with_its_digest(self):
        evidence = acceptance.baseline_runtime_evidence(
            self.archive, self.root, self.contract(self.digest))
        self.assertEqual(evidence['status'], 'PASS', evidence['failures'])
        self.assertEqual(evidence['archive']['tree_members_compared'], len(self.members))

    def test_wrong_locked_digest_is_rejected(self):
        with mock.patch.object(acceptance.zipfile, 'ZipFile') as opener:
            evidence = acceptance.baseline_runtime_evidence(
                self.archive, self.root, self.contract('0' * 64))
        opener.assert_not_called()
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertFalse(evidence['archive']['locked_zip_verified'])

    def test_changed_baseline_member_is_rejected(self):
        (self.root / 'payload.txt').write_bytes(b'changed\n')
        evidence = acceptance.baseline_runtime_evidence(
            self.archive, self.root, self.contract(self.digest))
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertEqual(evidence['archive']['changed_members'], ['payload.txt'])

    def test_symlinked_baseline_member_is_rejected(self):
        target = self.root / 'payload.txt'
        target.unlink()
        target.symlink_to(self.root / 'SKILL.md')
        evidence = acceptance.baseline_runtime_evidence(
            self.archive, self.root, self.contract(self.digest))
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertEqual(evidence['symlinks'], ['payload.txt'])


class ContractAndSourceTests(unittest.TestCase):
    def test_only_the_frozen_current_contract_is_accepted(self):
        rule = acceptance.contract_rule(acceptance.CONTRACT_NAME)
        self.assertEqual(rule['baseline_version'], '1.3.1')
        self.assertEqual(rule['candidate_version'], '1.3.2')
        with self.assertRaises(ValueError):
            acceptance.contract_rule('CAPABILITY_PARITY_V1_3_0_TO_V1_3_1')

    def test_real_source_tree_keeps_source_only_members(self):
        manifest = json.loads((ROOT / 'distribution/runtime-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['runtime_files']), 185)
        for relative in acceptance.SOURCE_ONLY_MEMBERS:
            self.assertNotIn(relative, manifest['runtime_files'])
            self.assertTrue((ROOT / relative).is_file(), relative)
        self.assertTrue((ROOT / 'scripts/runtime_acceptance.py').is_file())

    def test_docstring_describes_actual_cli_execution(self):
        text = ' '.join((acceptance.__doc__ or '').split())
        self.assertIn('executes each installed runtime', text)
        self.assertIn('fixed argv', text)
        self.assertIn('never imports developer or release tools', text)
        self.assertIn('never injects a developer code overlay', text)
        self.assertIn('fresh artifact directory', text)


def make_lock(root, versions):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    packages = {'': {'version': '1.0.0'}}
    for name, version in versions.items():
        packages[f'node_modules/{name}'] = {'version': version}
    payload = json.dumps({'packages': packages}, indent=2, sort_keys=True) + '\n'
    (root / 'package-lock.json').write_text(payload, encoding='utf-8')
    return root


def make_install(path, versions):
    path = Path(path)
    packages = {'': {'version': '1.0.0'}}
    for name, version in versions.items():
        packages[f'node_modules/{name}'] = {'version': version}
    path.mkdir(parents=True, exist_ok=True)
    (path / '.package-lock.json').write_text(
        json.dumps({'packages': packages}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


class ModuleEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.versions = {'left-pad': '1.3.0'}
        self.root = make_lock(self.base / 'runtime', self.versions)
        self.fallback = make_install(self.base / 'fallback', self.versions)

    def test_candidate_missing_node_modules_never_falls_back_to_source(self):
        evidence = acceptance.module_evidence('candidate', self.root, self.fallback)
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertFalse(evidence['owned'])
        self.assertTrue(any('Source fallback is not allowed' in item
                            for item in evidence['failures']))

    def test_candidate_symlinked_node_modules_is_not_an_install(self):
        (self.root / 'node_modules').symlink_to(self.fallback)
        evidence = acceptance.module_evidence('candidate', self.root, self.fallback)
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertFalse(evidence['owned'])
        self.assertEqual(evidence['source'], 'symlink')
        self.assertTrue(any('symlink is not an install' in item
                            for item in evidence['failures']))

    def test_baseline_missing_node_modules_uses_lock_matched_fallback(self):
        evidence = acceptance.module_evidence('baseline', self.root, self.fallback)
        self.assertEqual(evidence['status'], 'PASS', evidence['failures'])
        self.assertEqual(evidence['source'], 'lock-matched-fallback')
        self.assertFalse(evidence['owned'])
        self.assertTrue(evidence['dependencies_match_lock'])
        self.assertIn('rule', evidence['provenance'])

    def test_baseline_fallback_must_match_the_lock(self):
        mismatched = make_install(self.base / 'other-fallback', {'left-pad': '9.9.9'})
        evidence = acceptance.module_evidence('baseline', self.root, mismatched)
        self.assertEqual(evidence['status'], 'FAIL')
        self.assertFalse(evidence['dependencies_match_lock'])

    def test_root_owned_node_modules_passes(self):
        make_install(self.root / 'node_modules', self.versions)
        evidence = acceptance.module_evidence('candidate', self.root, None)
        self.assertEqual(evidence['status'], 'PASS', evidence['failures'])
        self.assertEqual(evidence['source'], 'root-owned')
        self.assertTrue(evidence['owned'])

    def test_baseline_root_owned_node_modules_passes(self):
        make_install(self.root / 'node_modules', self.versions)
        evidence = acceptance.module_evidence('baseline', self.root, None)
        self.assertEqual(evidence['status'], 'PASS', evidence['failures'])
        self.assertEqual(evidence['source'], 'root-owned')
        self.assertTrue(evidence['owned'])
        self.assertTrue(evidence['dependencies_match_lock'])


class MatrixFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / acceptance.MATRIX_SOURCE).read_text(encoding='utf-8'))

    def test_real_fixture_declares_the_full_matrix(self):
        result = acceptance.validate_matrix_fixture(self.fixture)
        self.assertEqual(result['status'], 'PASS', result['failures'])
        self.assertEqual((result['cells'], result['accepted'], result['rejected']), (96, 72, 24))
        self.assertEqual(result['families'], sorted(acceptance.MATRIX_FAMILIES))
        self.assertEqual(result['accepted_per_theme'],
                         {'light': 36, 'dark': 36})
        self.assertEqual(result['rejected_per_theme'], {'light': 12, 'dark': 12})

    def test_missing_cell_is_rejected(self):
        self.fixture['cells'] = self.fixture['cells'][:-1]
        result = acceptance.validate_matrix_fixture(self.fixture)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('95 cells' in item for item in result['failures']))

    def test_unknown_rejection_code_is_rejected(self):
        for cell in self.fixture['cells']:
            if cell['expected'] == 'REJECT':
                cell['rejection']['code'] = 'SOMETHING_ELSE'
                break
        result = acceptance.validate_matrix_fixture(self.fixture)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('unknown rejection code' in item for item in result['failures']))

    def test_theme_deck_specs_cover_accepted_cells_only(self):
        for theme, profile in acceptance.MATRIX_THEMES.items():
            spec, cells = acceptance.matrix_deck_spec(self.fixture, theme)
            self.assertEqual(len(cells), 36)
            self.assertEqual(len(spec['slides']), 36)
            self.assertEqual(spec['profile'], profile)
            self.assertTrue(all(cell['expected'] == 'ACCEPT' for cell in cells))
            self.assertTrue(all(slide['type'] == 'chart' for slide in spec['slides']))
            percentage = [slide for slide in spec['slides']
                          if '-pie-percentage' in slide['title']]
            self.assertEqual(len(percentage), 1)
            self.assertEqual(percentage[0]['numberFormat'], '0.0%')

    def test_rejection_spec_keeps_theme_and_missing_policy(self):
        cell = next(cell for cell in self.fixture['cells']
                    if cell['expected'] == 'REJECT' and cell.get('missing_policy'))
        spec = acceptance.matrix_rejection_spec(self.fixture, cell)
        self.assertEqual(spec['profile'], acceptance.MATRIX_THEMES[cell['theme']])
        self.assertEqual(len(spec['slides']), 1)
        self.assertEqual(spec['slides'][0]['missing_policy'], cell['missing_policy'])


class ArtifactRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.runtime = self.base / 'runtime'
        self.runtime.mkdir()
        self.baseline = self.base / 'baseline'
        self.baseline.mkdir()

    def prepare(self, path):
        return acceptance.prepare_artifact_root(path, self.source, self.runtime, self.baseline)

    def test_fresh_artifact_directory_gets_the_marker(self):
        root = self.prepare(self.base / 'artifacts')
        self.assertTrue((root / acceptance.ARTIFACT_MARKER).is_file())

    def test_non_empty_directory_is_refused(self):
        target = self.base / 'artifacts'
        target.mkdir()
        (target / 'previous.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(SystemExit):
            self.prepare(target)
        self.assertTrue((target / 'previous.json').is_file())

    def test_artifact_directory_may_not_overlap_a_runtime_root(self):
        with self.assertRaises(SystemExit):
            self.prepare(self.runtime / 'artifacts')
        with self.assertRaises(SystemExit):
            self.prepare(self.base)

    def test_artifact_directory_inside_source_must_be_under_out(self):
        with self.assertRaises(SystemExit):
            self.prepare(self.source / 'artifacts')
        root = self.prepare(self.source / 'out' / 'artifacts')
        self.assertTrue((root / acceptance.ARTIFACT_MARKER).is_file())

    def test_default_directory_is_fresh(self):
        root = acceptance.prepare_artifact_root(None, self.source, self.runtime, self.baseline)
        self.addCleanup(shutil.rmtree, root, True)
        self.assertTrue((root / acceptance.ARTIFACT_MARKER).is_file())


class CompareShortCircuitTests(unittest.TestCase):
    def test_failed_case_skips_comparisons_without_losing_status(self):
        result = acceptance.compare_runs(
            'case', {'status': 'FAIL', 'failures': ['build exited 0']},
            {'status': 'PASS', 'artifacts': {}}, Path('/baseline'), Path('/candidate'),
            (('pptx', 'file'),))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('skipped', result['reason'])
        self.assertTrue(result['failures'])

    def test_missing_outputs_fail_before_comparison(self):
        result = acceptance.compare_runs(
            'case', {'status': 'PASS', 'artifacts': {}},
            {'status': 'PASS', 'artifacts': {}}, Path('/baseline'), Path('/candidate'),
            (('pptx', 'file'),))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('required artifacts are missing', result['reason'])
        self.assertEqual(len(result['failures']), 2)

    def test_coverage_requires_every_status_to_pass(self):
        self.assertEqual(acceptance._coverage_status('PASS', 'PASS'), 'PASS')
        self.assertEqual(acceptance._coverage_status('PASS', 'FAIL'), 'FAIL')
        self.assertEqual(acceptance._coverage_status(), 'PASS')


PNG_BYTES = b'\x89PNG\r\n\x1a\n'

BUILD_JS = """\
const fs = require('fs');
const pptx = process.argv[3];
if (fs.existsSync('write-artifacts')) {
  fs.writeFileSync(pptx, 'not-a-real-pptx');
  fs.writeFileSync(pptx + '.scene.json', JSON.stringify({
    slides: [{ title: { measurement: 'font-size-guess' } }]
  }));
}
process.exit(0);
"""

QUALITY_GATE_PY = """\
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index('--out') + 1])
render = Path(args[args.index('--render-dir') + 1])
if Path('bad-json').exists():
    out.write_text('{not json', encoding='utf-8')
else:
    out.write_text('{"status": "PASS", "VISUAL_QA": "NOT_RUN"}', encoding='utf-8')
render.mkdir(parents=True, exist_ok=True)
(render / 'page.png').write_bytes(PNG_BYTES)
"""

RENDER_DECK_PY = """\
import sys
from pathlib import Path

out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
(out / 'page.png').write_bytes(PNG_BYTES)
"""


class RunSpecCaseFailureTests(unittest.TestCase):
    def setUp(self):
        if shutil.which('node') is None:
            self.skipTest('node is not available')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.runtime = self.base / 'runtime'
        scripts = self.runtime / 'skill/scripts'
        scripts.mkdir(parents=True)
        (scripts / 'build_deck.js').write_text(BUILD_JS, encoding='utf-8')
        (scripts / 'quality_gate.py').write_text(
            QUALITY_GATE_PY.replace('PNG_BYTES', repr(PNG_BYTES)), encoding='utf-8')
        (scripts / 'render_deck.py').write_text(
            RENDER_DECK_PY.replace('PNG_BYTES', repr(PNG_BYTES)), encoding='utf-8')
        self.spec = self.base / 'spec.json'
        self.spec.write_text('{"slides": []}', encoding='utf-8')
        self.work = self.base / 'work'
        self.logs = self.base / 'logs'
        self.case = {'name': 'fake', 'path': self.spec}

    def run_case(self):
        return acceptance.run_spec_case(
            'candidate', self.runtime, None, self.case, self.work,
            [str(self.runtime), str(self.work), str(self.logs)], self.logs)

    def test_zero_exit_build_without_pptx_cannot_pass_and_keeps_logs(self):
        result = self.run_case()
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('PPTX missing' in item for item in result['failures']))
        self.assertTrue(any('QA JSON missing' in item for item in result['failures']))
        self.assertTrue(any('scene missing' in item for item in result['failures']))
        self.assertEqual(result['commands'][0]['exit'], 0)
        self.assertEqual(result['commands'][1].get('skipped'), 'PPTX missing')
        self.assertTrue((self.logs / 'candidate-fake-build.command.json').is_file())
        self.assertTrue((self.logs / 'candidate-fake-build.stdout.txt').is_file())
        self.assertTrue((self.logs / 'candidate-fake-build.stderr.txt').is_file())

    def test_failed_title_measurement_cannot_pass(self):
        (self.runtime / 'write-artifacts').write_text('', encoding='utf-8')
        result = self.run_case()
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('candidate-fake title measurement' in item
                            for item in result['failures']))
        self.assertEqual(result['title_measurement']['status'], 'FAIL')
        self.assertEqual(result['title_measurement']['fallback_measurements'],
                         [{'slide': 0, 'measurement': 'font-size-guess'}])
        for key in ('pptx', 'scene', 'qa_json', 'qa_render', 'render'):
            self.assertTrue(Path(result['artifacts'][key]).exists(), key)

    def test_malformed_generated_json_is_a_structured_failure(self):
        (self.runtime / 'write-artifacts').write_text('', encoding='utf-8')
        (self.runtime / 'bad-json').write_text('', encoding='utf-8')
        result = self.run_case()
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('QA JSON is unreadable' in item for item in result['failures']))
        self.assertTrue(Path(result['artifacts']['qa_json']).is_file())


if __name__ == '__main__':
    unittest.main()

