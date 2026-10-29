#!/usr/bin/env python3
"""Fail-closed tests for the shared skill-package security gate.

The scanner is mocked by a small local script that writes scanner-shaped JSON
and SARIF. No vendor SDK is imported and no fixture is executed as target code.
The tests exercise the orchestration contract: safe extraction, bounded
execution, analyzer evidence, exact review binding, input stability and receipt
verification. A separate real-CLI negative control is run outside this suite.
"""
import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import unittest
import warnings
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
VERSION = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load('goujian_scan_gate', 'scripts/scan_skill_package.py')
packager = load('goujian_package_runtime', 'scripts/package_runtime.py')

FAKE_SCANNER = '''#!/usr/bin/env python3
import hashlib, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
if '--version' in sys.argv:
    mode = {}
    try:
        mode = json.loads((HERE / 'mode.json').read_text(encoding='utf-8'))
    except Exception:
        mode = {}
    print('skill-scanner ' + mode.get('version', '2.3.1'))
    sys.exit(0)
mode = json.loads((HERE / 'mode.json').read_text(encoding='utf-8'))
if mode.get('sleep'):
    time.sleep(mode['sleep'])
args = sys.argv
def value(flag):
    return args[args.index(flag) + 1] if flag in args else None
target = Path(args[args.index('scan') + 1])
if mode.get('modify_target'):
    path = target / mode.get('modify_path', 'SKILL.md')
    with path.open('ab') as handle:
        handle.write(b'\\nMUTATED-DURING-SCAN\\n')
findings = mode.get('findings', [])
analyzers = mode.get('analyzers', ['static_analyzer', 'bytecode', 'pipeline', 'correlation', 'behavioral_analyzer'])
report = {
    'skill_name': 'goujian-strategy-slides',
    'is_safe': not any(item.get('severity') in ('CRITICAL', 'HIGH') for item in findings),
    'max_severity': 'CRITICAL' if findings else None,
    'findings_count': len(findings),
    'findings': findings,
    'analyzers_used': analyzers,
    'analyzers_failed': mode.get('analyzers_failed', []),
    'scan_metadata': {
        'policy_name': mode.get('policy_name', 'low-noise'),
        'policy_preset_base': 'balanced',
        'policy_fingerprint_sha256': mode.get('policy_fingerprint_sha256', 'f' * 64),
        'cel': {'mode': 'shadow', 'errors': mode.get('cel_errors', []),
                'suppressed': mode.get('cel_suppressed', 0),
                'would_suppress': mode.get('cel_would_suppress', 0), 'fallbacks': 0,
                'projection_incomplete': 0},
        'rule_contract': {'status': mode.get('rule_contract', 'passed'),
                          'invalid_findings': 0, 'errors': []},
    },
}
out_json = value('--output-json')
out_sarif = value('--output-sarif')
if out_json and not mode.get('no_reports'):
    text = '{not json' if mode.get('malformed_json') else json.dumps(report)
    Path(out_json).write_text(text, encoding='utf-8')
if out_sarif and not mode.get('no_reports'):
    sarif = {'version': '2.1.0', 'runs': [{
        'results': [{} for _ in findings][:mode.get('sarif_results', len(findings))],
        'invocations': [{'executionSuccessful': mode.get('sarif_execution_successful', True),
                         'toolExecutionNotifications': []}],
    }]}
    Path(out_sarif).write_text(json.dumps(sarif), encoding='utf-8')
print('mock scan complete')
sys.exit(int(mode.get('exit_code', 1 if findings else 0)))
'''


def zip_info(name, mode=0o644):
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def write_zip(path, members):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for info, data in members:
                archive.writestr(info, data)


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='goujian-gate-tests-')
        cls.base = Path(cls.temp.name)
        cls.archive = cls.base / 'runtime.zip'
        packager.build(cls.archive)
        cls.repo = cls.base / 'repo'
        cls.repo.mkdir()
        with zipfile.ZipFile(cls.archive) as package:
            for info in package.infolist():
                relative = info.filename[len(PREFIX):]
                destination = cls.repo / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(package.read(info))
        cls.git('init', '-q')
        cls.git('config', 'user.email', 'gate@example.invalid')
        cls.git('config', 'user.name', 'Gate Test')
        cls.git('add', '-A')
        cls.git('commit', '-q', '-m', 'fixture')
        cls.commit = cls.git('rev-parse', 'HEAD').strip()
        cls.scanner_dir = cls.base / 'scanner'
        cls.scanner_dir.mkdir()
        cls.scanner = cls.scanner_dir / 'skill-scanner'
        cls.scanner.write_text(FAKE_SCANNER, encoding='utf-8')
        os.chmod(cls.scanner, 0o755)
        cls.config = ROOT / 'security/security-gate.json'
        cls.lock = ROOT / 'security/requirements-lock.txt'
        cls.empty_ledger = cls.base / 'empty-ledger.json'
        cls.write_ledger(cls.empty_ledger, [])
        cls.counter = 0

    @classmethod
    def git(cls, *args):
        return subprocess.run(['git', '-C', str(cls.repo), *args], check=True,
                              capture_output=True, text=True).stdout

    @staticmethod
    def init_repo(path):
        subprocess.run(['git', '-C', str(path), 'init', '-q'], check=True)
        subprocess.run(['git', '-C', str(path), 'config', 'user.email',
                        'gate@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(path), 'config', 'user.name',
                        'Gate Test'], check=True)
        subprocess.run(['git', '-C', str(path), 'add', '-A'], check=True)
        subprocess.run(['git', '-C', str(path), 'commit', '-q', '-m', 'fixture'],
                       check=True)
        return subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                              check=True, capture_output=True, text=True).stdout.strip()

    @classmethod
    def extract_archive(cls, path):
        path = Path(path)
        path.mkdir(parents=True)
        with zipfile.ZipFile(cls.archive) as package:
            for info in package.infolist():
                relative = info.filename[len(PREFIX):]
                destination = path / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(package.read(info))
        return path

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        pin = json.loads(self.config.read_text(encoding='utf-8'))
        self.mode = {
            'policy_fingerprint_sha256':
                pin['scanner']['policy_fingerprint_sha256'],
        }
        self.write_mode()

    @staticmethod
    def write_ledger(path, reviews, status='APPROVED'):
        Path(path).write_text(json.dumps({
            'schema_version': 1, 'status': status, 'reviews': reviews,
        }, indent=2) + '\n', encoding='utf-8')

    def write_mode(self, **values):
        self.mode.update(values)
        (self.scanner_dir / 'mode.json').write_text(
            json.dumps(self.mode), encoding='utf-8')

    def out_dir(self):
        type(self).counter += 1
        path = self.base / f'out-{type(self).counter}'
        path.mkdir()
        return path

    def run_gate(self, *args):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = gate.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def scan(self, ledger=None, extra=()):
        out = self.out_dir()
        code, stdout, stderr = self.run_gate(
            'scan', str(self.archive), '--profile', 'runtime',
            '--version', VERSION, '--commit', self.commit,
            '--repo', str(self.repo),
            '--source-tree-state', 'clean',
            '--config', str(self.config), '--lock', str(self.lock),
            '--review-ledger', str(ledger or self.empty_ledger),
            '--scanner', str(self.scanner), '--out-dir', str(out), *extra)
        receipt = json.loads((out / 'receipt.json').read_text(encoding='utf-8'))
        return code, receipt, out, stdout, stderr

    def verify(self, receipt, out, ledger=None, extra=()):
        return self.run_gate(
            'verify', str(receipt), '--archive', str(self.archive),
            '--version', VERSION, '--commit', self.commit,
            '--repo', str(self.repo),
            '--config', str(self.config), '--lock', str(self.lock),
            '--review-ledger', str(ledger or self.empty_ledger),
            '--artifact-dir', str(out), *extra)

    def high_finding(self, path='SKILL.md', line=3):
        return {
            'id': 'FAKE_HIGH_1',
            'rule_id': 'FAKE_DYNAMIC_CODE',
            'category': 'command_injection',
            'severity': 'CRITICAL',
            'title': 'Mock critical finding',
            'description': 'Mock scanner finding for gate orchestration tests.',
            'file_path': path,
            'line_number': line,
            'snippet': 'fixture',
            'analyzer': 'static',
        }

    # --- extraction / archive safety -------------------------------------

    def test_traversal_is_rejected(self):
        archive = self.base / 'traversal.zip'
        write_zip(archive, [
            (zip_info(PREFIX + 'SKILL.md'), b'---\nname: x\n---\n'),
            (zip_info(PREFIX + '../escape.txt'), b'escape'),
        ])
        with self.assertRaises(gate.GateFailure):
            gate.extract_zip(archive, self.base / 'traversal-out', {
                'max_member_bytes': 1024, 'max_total_bytes': 4096,
                'max_compression_ratio': 1000})

    def test_symlink_is_rejected(self):
        archive = self.base / 'symlink.zip'
        write_zip(archive, [
            (zip_info(PREFIX + 'SKILL.md'), b'---\nname: x\n---\n'),
            (zip_info(PREFIX + 'link', 0o120777), b'/etc/passwd'),
        ])
        with self.assertRaises(gate.GateFailure):
            gate.extract_zip(archive, self.base / 'symlink-out', {
                'max_member_bytes': 1024, 'max_total_bytes': 4096,
                'max_compression_ratio': 1000})

    def test_duplicate_member_is_rejected(self):
        archive = self.base / 'duplicate.zip'
        write_zip(archive, [
            (zip_info(PREFIX + 'SKILL.md'), b'one'),
            (zip_info(PREFIX + 'SKILL.md'), b'two'),
        ])
        with self.assertRaises(gate.GateFailure):
            gate.extract_zip(archive, self.base / 'duplicate-out', {
                'max_member_bytes': 1024, 'max_total_bytes': 4096,
                'max_compression_ratio': 1000})

    def test_unsafe_mode_is_rejected(self):
        archive = self.base / 'mode.zip'
        write_zip(archive, [
            (zip_info(PREFIX + 'SKILL.md'), b'one'),
            (zip_info(PREFIX + 'script.sh', 0o4777), b'echo x'),
        ])
        with self.assertRaises(gate.GateFailure):
            gate.extract_zip(archive, self.base / 'mode-out', {
                'max_member_bytes': 1024, 'max_total_bytes': 4096,
                'max_compression_ratio': 1000})

    # --- scanner orchestration -------------------------------------------

    def test_timeout_is_bounded_and_logs_are_retained(self):
        self.write_mode(sleep=5)
        code, receipt, out, _, _ = self.scan(extra=('--scanner-timeout', '1'))
        self.assertEqual(code, 1)
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'SCANNER_TIMEOUT')
        self.assertTrue((out / 'scanner.stdout.log').is_file())
        self.assertTrue((out / 'scanner.stderr.log').is_file())
        self.assertTrue((out / 'receipt.json').is_file())

    def test_tool_error_without_reports_fails_closed(self):
        self.write_mode(exit_code=2, no_reports=True)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertIn(receipt['failure_reasons'][0]['code'],
                      {'MISSING_REPORT', 'SCANNER_TOOL_ERROR'})

    def test_missing_behavioral_analyzer_is_rejected(self):
        self.write_mode(analyzers=['static_analyzer'])
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'MISSING_ANALYZER')

    def test_unexpected_analyzer_is_rejected(self):
        self.write_mode(analyzers=['static_analyzer', 'behavioral_analyzer', 'llm_analyzer'])
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'UNEXPECTED_ANALYZER')

    def test_rule_contract_error_is_rejected(self):
        self.write_mode(rule_contract='failed')
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'ANALYZER_ERROR')

    def test_cel_error_is_rejected(self):
        self.write_mode(cel_errors=['expression failed'])
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'ANALYZER_ERROR')

    def test_shadow_cel_would_suppress_is_retained_not_an_error(self):
        self.write_mode(cel_would_suppress=78)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 0)
        self.assertEqual(receipt['analyzers']['cel']['would_suppress'], 78)
        self.assertEqual(receipt['analyzers']['cel']['suppressed'], 0)

    def test_actual_cel_suppression_is_rejected(self):
        self.write_mode(cel_suppressed=1)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'ANALYZER_ERROR')

    def test_line_zero_is_a_whole_file_marker(self):
        finding = self.high_finding()
        finding['severity'] = 'MEDIUM'
        finding['line_number'] = 0
        self.write_mode(findings=[finding])
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        self.assertEqual(receipt['findings']['items'][0]['line'], 0)
        code, _, stderr = self.verify(out / 'receipt.json', out)
        self.assertEqual(code, 0, stderr)

    def test_sarif_invocation_failure_is_rejected(self):
        self.write_mode(sarif_execution_successful=False)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'MALFORMED_SARIF')

    def test_malformed_json_is_rejected(self):
        self.write_mode(malformed_json=True)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'MALFORMED_REPORT')

    def test_sarif_count_mismatch_is_rejected(self):
        self.write_mode(findings=[self.high_finding()], sarif_results=0)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'MALFORMED_SARIF')

    def test_wrong_scanner_version_is_rejected(self):
        self.write_mode(version='9.9.9')
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'SCANNER_VERSION_MISMATCH')

    def test_expected_archive_hash_is_bound(self):
        code, receipt, _, _, _ = self.scan(extra=('--expected-sha256', '0' * 64))
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'ARCHIVE_HASH_MISMATCH')

    # --- findings / review binding ---------------------------------------

    def test_unreviewed_high_blocks_and_proposal_is_not_approval(self):
        self.write_mode(findings=[self.high_finding()])
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'UNREVIEWED_BLOCKING')
        self.assertEqual(receipt['findings']['severity_counts'], {'CRITICAL': 1})
        proposal = json.loads((out / 'review-proposal.json').read_text(encoding='utf-8'))
        self.assertEqual(proposal['status'], 'PROPOSAL_NOT_APPROVED')
        self.assertEqual(proposal['review_count'], 1)
        self.assertFalse(proposal['reviews'][0]['approved'])
        self.assertEqual(proposal['reviews'][0]['reviewer'], 'PENDING_INDEPENDENT_REVIEW')
        with self.assertRaises(gate.GateFailure):
            gate.load_ledger(out / 'review-proposal.json', gate.load_config(self.config))

    def test_exact_approved_review_resolves_high_and_verifies(self):
        self.write_mode(findings=[self.high_finding()])
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 1)
        proposal = json.loads((out / 'review-proposal.json').read_text(encoding='utf-8'))
        review = dict(proposal['reviews'][0])
        review['approved'] = True
        review['reviewer'] = 'Codex'
        review['reason'] = 'Exact test review'
        review['evidence'] = 'receipt fixture evidence'
        ledger = self.base / 'approved-ledger.json'
        self.write_ledger(ledger, [review])
        code, receipt, out2, _, _ = self.scan(ledger=ledger)
        self.assertEqual(code, 0, receipt['failure_reasons'])
        self.assertEqual(receipt['status'], 'PASS')
        self.assertEqual(receipt['findings']['blocking_unreviewed'], 0)
        code, _, stderr = self.verify(out2 / 'receipt.json', out2, ledger=ledger)
        self.assertEqual(code, 0, stderr)

    def test_stale_review_cannot_resolve_high(self):
        self.write_mode(findings=[self.high_finding()])
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 1)
        proposal = json.loads((out / 'review-proposal.json').read_text(encoding='utf-8'))
        review = dict(proposal['reviews'][0])
        review['approved'] = True
        review['reviewer'] = 'Codex'
        review['reason'] = 'Changed bytes must not match'
        review['evidence'] = 'test'
        review['file_sha256'] = '0' * 64
        ledger = self.base / 'stale-ledger.json'
        self.write_ledger(ledger, [review])
        code, receipt, _, _, _ = self.scan(ledger=ledger)
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'STALE_REVIEW')

    def test_changed_target_during_scan_is_input_drift(self):
        self.write_mode(modify_target=True)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'INPUT_DRIFT')

    def test_malformed_duplicate_and_wildcard_reviews_are_rejected(self):
        pin = json.loads(self.config.read_text(encoding='utf-8'))
        base_review = {
            'id': 'r1', 'rule_id': 'FAKE_DYNAMIC_CODE', 'path': 'SKILL.md', 'line': 3,
            'file_sha256': '1' * 64, 'root_skill_sha256': '2' * 64,
            'scanner_version': '2.3.1', 'policy': 'low-noise',
            'policy_fingerprint_sha256': pin['scanner']['policy_fingerprint_sha256'],
            'reviewer': 'Codex', 'reason': 'test', 'evidence': 'test', 'approved': True,
        }
        cases = {
            'duplicate': [base_review, dict(base_review, id='r2')],
            'wildcard': [dict(base_review, path='*')],
            'unapproved': [dict(base_review, approved=False)],
        }
        for name, reviews in cases.items():
            path = self.base / f'ledger-{name}.json'
            self.write_ledger(path, reviews)
            with self.assertRaises(gate.GateFailure):
                gate.load_ledger(path, gate.load_config(self.config))

    # --- receipt verification --------------------------------------------

    def test_forged_receipt_is_rejected(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        receipt['archive']['sha256'] = '0' * 64
        forged = out / 'forged-receipt.json'
        forged.write_text(json.dumps(receipt), encoding='utf-8')
        code, _, stderr = self.verify(forged, out)
        self.assertEqual(code, 1)
        self.assertIn('ARCHIVE_HASH_MISMATCH', stderr)

    def test_changed_raw_report_is_rejected(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        with (out / 'scanner.json').open('a', encoding='utf-8') as handle:
            handle.write('\n')
        code, _, stderr = self.verify(out / 'receipt.json', out)
        self.assertEqual(code, 1)
        self.assertIn('FORGED_OR_CHANGED_ARTIFACT', stderr)

    def test_changed_archive_before_verify_is_rejected(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        changed = self.base / 'changed.zip'
        changed.write_bytes(self.archive.read_bytes() + b'x')
        code, _, stderr = self.run_gate(
            'verify', str(out / 'receipt.json'), '--archive', str(changed),
            '--version', VERSION, '--commit', self.commit,
            '--repo', str(self.repo),
            '--config', str(self.config), '--lock', str(self.lock),
            '--review-ledger', str(self.empty_ledger),
            '--artifact-dir', str(out))
        self.assertEqual(code, 1)
        self.assertIn('ARCHIVE_HASH_MISMATCH', stderr)

    def test_stale_receipt_is_rejected(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        receipt['created_at'] = '2000-01-01T00:00:00+00:00'
        (out / 'receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
        code, _, stderr = self.verify(out / 'receipt.json', out)
        self.assertEqual(code, 1)
        self.assertIn('STALE_RECEIPT', stderr)

    def test_commit_and_version_binding_is_enforced(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        code, _, stderr = self.run_gate(
            'verify', str(out / 'receipt.json'), '--archive', str(self.archive),
            '--version', VERSION, '--commit', 'b' * 40,
            '--repo', str(self.repo),
            '--config', str(self.config), '--lock', str(self.lock),
            '--review-ledger', str(self.empty_ledger),
            '--artifact-dir', str(out))
        self.assertEqual(code, 1)
        self.assertIn('COMMIT_MISMATCH', stderr)

    def test_dirty_source_tree_receipt_cannot_verify_for_release(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan(extra=('--source-tree-state', 'dirty'))
        self.assertEqual(code, 0)
        self.assertEqual(receipt['package']['source_tree_state'], 'dirty')
        code, _, stderr = self.verify(out / 'receipt.json', out)
        self.assertEqual(code, 1)
        self.assertIn('SOURCE_TREE_NOT_CLEAN', stderr)

    def test_relative_evidence_dir_survives_private_child_working_directory(self):
        self.write_mode()
        previous = os.getcwd()
        os.chdir(self.base)
        try:
            code, _, stderr = self.run_gate(
                'scan', str(self.archive), '--profile', 'runtime',
                '--version', VERSION, '--commit', self.commit,
                '--repo', str(self.repo),
                '--source-tree-state', 'clean',
                '--config', str(self.config), '--lock', str(self.lock),
                '--review-ledger', str(self.empty_ledger),
                '--scanner', str(self.scanner), '--out-dir', 'relative-evidence')
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0, stderr)
        for name in ('receipt.json', 'scanner.json', 'scanner.sarif'):
            self.assertTrue((self.base / 'relative-evidence' / name).is_file(), name)

    def test_missing_source_tree_state_receipt_is_rejected(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        receipt['package'].pop('source_tree_state')
        (out / 'receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
        code, _, stderr = self.verify(out / 'receipt.json', out)
        self.assertEqual(code, 1)
        self.assertIn('SOURCE_TREE_NOT_CLEAN', stderr)


    # --- gate completeness, review scope, output and source binding ------

    def test_verify_requires_the_complete_named_check_set(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        receipt['checks'].pop('policy_fingerprint')
        (out / 'receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
        code, _, stderr = self.verify(out / 'receipt.json', out)
        self.assertEqual(code, 1)
        self.assertIn('INCOMPLETE_CHECKS', stderr)

    def test_verify_rejects_unrecognized_check_names(self):
        self.write_mode()
        code, receipt, out, _, _ = self.scan()
        self.assertEqual(code, 0)
        receipt['checks']['extra_promises'] = {'status': 'PASS'}
        (out / 'receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
        code, _, stderr = self.verify(out / 'receipt.json', out)
        self.assertEqual(code, 1)
        self.assertIn('INVALID_RECEIPT', stderr)

    def test_review_for_file_absent_from_profile_is_visible_not_applied(self):
        pin = json.loads(self.config.read_text(encoding='utf-8'))
        review = {
            'id': 'absent-1', 'rule_id': 'FAKE_DYNAMIC_CODE',
            'path': 'docs/NOT_PACKAGED.md', 'line': 3,
            'file_sha256': '1' * 64, 'root_skill_sha256': '2' * 64,
            'scanner_version': '2.3.1', 'policy': 'low-noise',
            'policy_fingerprint_sha256': pin['scanner']['policy_fingerprint_sha256'],
            'reviewer': 'Codex', 'reason': 'absent in this profile', 'evidence': 'test',
            'approved': True,
        }
        ledger = self.base / 'absent-ledger.json'
        self.write_ledger(ledger, [review])
        code, receipt, _, _, stderr = self.scan(ledger=ledger)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(receipt['review_ledger']['matched_reviews'], 0)
        self.assertEqual(receipt['review_ledger']['not_applicable_reviews'][0]['path'],
                         'docs/NOT_PACKAGED.md')

    def test_review_for_present_file_with_stale_bytes_is_rejected(self):
        pin = json.loads(self.config.read_text(encoding='utf-8'))
        review = {
            'id': 'stale-1', 'rule_id': 'FAKE_DYNAMIC_CODE', 'path': 'SKILL.md',
            'line': 3, 'file_sha256': '0' * 64, 'root_skill_sha256': '2' * 64,
            'scanner_version': '2.3.1', 'policy': 'low-noise',
            'policy_fingerprint_sha256': pin['scanner']['policy_fingerprint_sha256'],
            'reviewer': 'Codex', 'reason': 'stale bytes', 'evidence': 'test',
            'approved': True,
        }
        ledger = self.base / 'stale-bytes-ledger.json'
        self.write_ledger(ledger, [review])
        code, receipt, _, _, _ = self.scan(ledger=ledger)
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'STALE_REVIEW')

    def test_reused_or_symlinked_output_directory_is_rejected(self):
        stale = self.base / 'stale-evidence'
        stale.mkdir()
        (stale / 'receipt.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(gate.GateFailure) as caught:
            gate.prepare_output_dir(stale)
        self.assertEqual(caught.exception.code, 'OUTPUT_NOT_EMPTY')
        target = self.base / 'real-evidence'
        target.mkdir()
        link = self.base / 'linked-evidence'
        link.symlink_to(target)
        with self.assertRaises(gate.GateFailure) as caught:
            gate.prepare_output_dir(link)
        self.assertEqual(caught.exception.code, 'OUTPUT_UNSAFE')

    def test_snapshot_and_preflight_are_bound_to_the_same_archive(self):
        self.write_mode()
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 0)
        self.assertEqual(receipt['snapshot']['sha256'], receipt['archive']['sha256'])
        self.assertEqual(receipt['preflight']['archive_sha256'],
                         receipt['archive']['sha256'])

    def test_wrong_policy_fingerprint_is_rejected(self):
        self.write_mode(policy_fingerprint_sha256='0' * 64)
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(receipt['failure_reasons'][0]['code'], 'POLICY_MISMATCH')

    def test_binary_finding_keeps_byte_offset(self):
        finding = self.high_finding()
        finding['severity'] = 'LOW'
        finding['line_number'] = 0
        finding['snippet'] = '[binary] byte offset 41'
        self.write_mode(findings=[finding])
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 0)
        item = receipt['findings']['items'][0]
        self.assertEqual(item['location_kind'], 'binary_byte_offset')
        self.assertEqual(item['byte_offset'], 41)

    def test_medium_finding_records_triage_not_a_waiver(self):
        finding = self.high_finding()
        finding['severity'] = 'MEDIUM'
        self.write_mode(findings=[finding])
        code, receipt, _, _, _ = self.scan()
        self.assertEqual(code, 0)
        item = receipt['findings']['items'][0]
        self.assertEqual(item['review_status'], 'TRIAGE_RECORDED_NOT_A_WAIVER')
        self.assertTrue(item['owner'])
        self.assertTrue(item['rationale'])

    def test_source_top_level_matches_packager_include(self):
        self.assertEqual(set(gate.SOURCE_TOP_LEVEL), set(packager.SOURCE_INCLUDE))

    def test_negative_fixture_helper_generates_exactly_one_private_skill(self):
        fixture = load('goujian_negative_fixture', 'scripts/negative_skill_fixture.py')
        destination = self.base / 'negative-fixture'
        result = fixture.materialize(destination)
        skills = sorted(destination.rglob('SKILL.md'))
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0], destination / 'SKILL.md')
        sample = (destination / 'scripts/unsafe_sample.py').read_text(encoding='utf-8')
        self.assertIn('eval(', sample)
        self.assertFalse(result['executed'])

    def test_source_identity_rejects_wrong_bytes_and_wrong_commit(self):
        repo = self.base / 'identity-repo'
        self.extract_archive(repo)
        commit = self.init_repo(repo)
        target = self.extract_archive(self.base / 'identity-target')
        identity = gate.verify_source_identity(target, 'runtime', commit, repo)
        self.assertGreater(identity['compared_members'], 100)
        skill = target / 'SKILL.md'
        skill.write_bytes(skill.read_bytes() + b'\n# drift\n')
        with self.assertRaises(gate.GateFailure) as caught:
            gate.verify_source_identity(target, 'runtime', commit, repo)
        self.assertEqual(caught.exception.code, 'SOURCE_MISMATCH')
        repo_skill = repo / 'SKILL.md'
        repo_skill.write_bytes(repo_skill.read_bytes() + b'\n# drift\n')
        subprocess.run(['git', '-C', str(repo), 'commit', '-q', '-am', 'drift'],
                       check=True)
        commit_two = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'],
                                    check=True, capture_output=True,
                                    text=True).stdout.strip()
        fresh = self.extract_archive(self.base / 'identity-target-two')
        with self.assertRaises(gate.GateFailure) as caught:
            gate.verify_source_identity(fresh, 'runtime', commit_two, repo)
        self.assertEqual(caught.exception.code, 'SOURCE_MISMATCH')


if __name__ == '__main__':
    unittest.main()
