#!/usr/bin/env python3
"""Structural guards for the permanent release security pipeline.

These tests read the workflow text so a future edit cannot silently remove the
scanner gate, the live advisory check, the receipt re-verification, the
hash-bound release evidence, or the typed publish approval. They do not run
GitHub Actions.
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / '.github/workflows/ci.yml'
SECURITY = ROOT / '.github/workflows/skill-security.yml'
RELEASE = ROOT / '.github/workflows/release.yml'

CAPTURE_ANCHOR = 'npm test 2>&1 | tee "$RUNNER_TEMP/source-archive-test.log"'
PIPESTATUS_CAPTURE = 'npm_test_status=("${PIPESTATUS[@]}")'


def _capture_snippet(text):
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines) if CAPTURE_ANCHOR in line)
    if lines[index - 1].strip() != 'set +e':
        raise AssertionError('the capture snippet must open with set +e')
    return textwrap.dedent('\n'.join(lines[index - 1:index + 5])) + '\n'


def _receipt_snippet(text):
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines)
                 if line.lstrip().startswith('python3 - ')
                 and 'source-archive-test.log' in line
                 and 'source-archive-acceptance.json' in line)
    end = next(i for i in range(index + 1, len(lines)) if lines[i].strip() == 'PY')
    return textwrap.dedent('\n'.join(lines[index + 1:end])) + '\n'


def _runtime_summary_snippet(text):
    lines = text.splitlines()
    marker = next(i for i, line in enumerate(lines)
                  if 'FAIL: installed runtime acceptance exited' in line)
    index = max(i for i in range(marker) if lines[i].lstrip().startswith('python3 - '))
    heredoc = next(i for i in range(index + 1, len(lines)) if "<<'PY'" in lines[i])
    end = next(i for i in range(heredoc + 1, len(lines)) if lines[i].strip() == 'PY')
    return textwrap.dedent('\n'.join(lines[heredoc + 1:end])) + '\n'


def _step_block(text, name):
    marker = f'- name: {name}'
    start = text.index(marker)
    nxt = text.find('\n      - name: ', start + len(marker))
    return text[start:nxt if nxt != -1 else len(text)]


class WorkflowStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = CI.read_text(encoding='utf-8')
        cls.security = SECURITY.read_text(encoding='utf-8')
        cls.release = RELEASE.read_text(encoding='utf-8')

    def test_all_jobs_pin_validated_runner_and_core_leg_survives(self):
        for path in (CI, SECURITY, RELEASE):
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('ubuntu-latest', text, path)
            labels = re.findall(r'^\s+runs-on:\s*(\S+)\s*$', text, re.MULTILINE)
            self.assertTrue(labels, f'{path} declares no runs-on label')
            self.assertEqual(set(labels), {'ubuntu-24.04'}, (path, labels))
        core_job = self.ci.split('\n  core:\n', 1)[1].split('\n  secure:\n', 1)[0]
        self.assertIn('runs-on: ubuntu-24.04', core_job)
        self.assertIn('- node: 18', core_job)
        self.assertRegex(core_job, r"python:\s*'3\.9'")

    def test_pr_workflow_scans_runtime_and_source_with_git_identity(self):
        self.assertIn('scripts/scan_skill_package.py scan', self.security)
        self.assertIn('run_scan runtime runtime', self.security)
        self.assertIn('run_scan source source', self.security)
        self.assertIn('--repo "$GITHUB_WORKSPACE"', self.security)
        self.assertNotIn('build_showcase', self.security)
        self.assertNotIn('security-fixtures', self.security)
        self.assertNotIn('__import__', self.security)

    def test_pr_workflow_runs_live_advisory_and_private_negative_control(self):
        self.assertIn('scripts/advisory_check.py', self.security)
        self.assertIn('npm audit --omit=dev', self.security)
        self.assertIn('scripts/negative_skill_fixture.py', self.security)
        self.assertIn('actions/setup-node@', self.security)
        self.assertIn('if: always()', self.security)
        self.assertIn('retention-days:', self.security)

    def test_publish_is_typed_false_by_default_and_requires_true(self):
        self.assertRegex(self.release, r'publish:\s*\n\s+description:')
        self.assertRegex(self.release, r'type:\s*boolean')
        self.assertRegex(self.release, r'default:\s*false')
        self.assertIn("inputs.publish == true", self.release)
        occurrences = re.findall(r'inputs\.publish\s*==\s*(\S+)', self.release)
        self.assertTrue(occurrences)
        self.assertTrue(all(value == 'true' for value in occurrences), occurrences)

    def test_publish_cannot_bypass_validation_or_read_only_validate(self):
        publisher = self.release.split('\n  publish:\n', 1)[1]
        self.assertRegex(publisher, r'\n    needs:\s*validate\b')
        head = self.release.split('\n  publish:\n', 1)[0]
        self.assertNotIn('contents: write', head)
        self.assertNotIn('gh release create', head)
        self.assertNotIn('git tag -a', head)
        self.assertIn('contents: read', self.security)
        self.assertIn('persist-credentials: false', self.security)

    def test_validate_rehearsal_reverifies_all_three_receipts(self):
        head = self.release.split('\n  publish:\n', 1)[0]
        self.assertIn('scripts/scan_skill_package.py verify', head)
        self.assertEqual(head.count('scripts/scan_skill_package.py verify'), 1)
        for name in ('runtime', 'source', 'showcase'):
            self.assertIn(name, head)
        self.assertIn('--repo "$GITHUB_WORKSPACE"', head)

    def test_publisher_reverifies_receipts_and_requires_evidence(self):
        publisher = self.release.split('\n  publish:\n', 1)[1]
        self.assertIn('scripts/scan_skill_package.py verify', publisher)
        self.assertIn('--repo "$GITHUB_WORKSPACE"', publisher)
        self.assertIn("manifest.get('security')", publisher)
        self.assertIn("security['status'] == 'PASS'", publisher)
        self.assertIn("security['evidence_index']", publisher)
        self.assertIn('security-evidence.json', publisher)

    def test_release_manifest_holds_hash_bound_security_evidence(self):
        self.assertIn('Bind hash-bound security evidence into the external release manifest',
                      self.release)
        self.assertIn("reports['json']['sha256']", self.release)
        self.assertIn("reports['sarif']['sha256']", self.release)
        self.assertIn("receipt['source_identity']", self.release)
        self.assertIn("receipt['review_ledger']['sha256']", self.release)
        self.assertIn("receipt['lock']['sha256']", self.release)
        self.assertIn('retention-days: 90', self.release)

    def test_live_advisory_runs_in_release_and_fails_closed(self):
        head = self.release.split('\n  publish:\n', 1)[0]
        self.assertIn('scripts/advisory_check.py', head)
        self.assertIn('npm audit --omit=dev', head)
        self.assertIn('--npm-audit-exit-code "$npm_status"', head)
        self.assertIn('set +e', head)

    def test_old_release_guards_are_preserved(self):
        for token in (
            'V13_BASELINE_COMMIT', 'V12_BASELINE_COMMIT',
            'V13_BASELINE_TAG_OBJECT', 'V12_BASELINE_TAG_OBJECT',
            'Release v$VERSION already exists; refusing to overwrite',
            'Keep tracked source clean before packaging or tagging',
            'Verify deterministic archives and single Skill entry',
            'Preflight the actual runtime, source and showcase archives',
            'Verify a fresh clone of the published tag and a clean runtime install',
        ):
            self.assertIn(token, self.release)

    def test_pdf_structural_suite_is_wired_before_scans_and_verify(self):
        for text in (self.security, self.release):
            self.assertIn('security/pdf-parser-requirements.txt', text)
            self.assertIn('tests.test_pdf_structural_review', text)
            self.assertIn('"$SCANNER_PYTHON" scripts/scan_skill_package.py scan', text)
        self.assertIn('scripts/pdf_negative_fixture.py', self.security)
        self.assertIn('scripts/pdf_structural_check.py', self.security)
        publisher = self.release.split('\n  publish:\n', 1)[1]
        verifier = publisher.index(
            'name: Install only the hash-locked PDF verifier from the shared lock')
        verify = publisher.index('"$PDF_VERIFIER_PYTHON" scripts/scan_skill_package.py verify')
        secret_write = publisher.index('GH_TOKEN:')
        self.assertLess(verifier, verify)
        self.assertLess(verifier, secret_write)
        self.assertIn("python-version: '3.14'", publisher[:verifier])

    def test_runtime_selection_counts_are_185_declared_and_186_members(self):
        for path, text in ((CI, self.ci), (RELEASE, self.release)):
            self.assertIn('len(files) == 185', text, path)
            self.assertIn('assert len(names) == 186', text, path)
            self.assertNotIn('189', text, path)
            self.assertNotIn('== 190', text, path)
        self.assertIn("'archive_entries': 186", self.release)
        for relative in ('scripts/package_runtime.py', 'scripts/security_preflight.py',
                         'skill/reasoning/fixtures/hostile-source/plan.json',
                         'skill/reasoning/fixtures/hostile-source/sources/hostile.md'):
            self.assertIn(relative, self.release)

    def test_candidate_version_and_release_notes_are_exactly_1_3_2(self):
        self.assertEqual(self.release.count('VERSION: "1.3.2"'), 2)
        self.assertEqual(self.release.count('test "$VERSION" = "1.3.2"'), 2)
        self.assertEqual(self.release.count('version: "1.3.2"'), 2)
        self.assertEqual(self.release.count("manifest.version !== '1.3.2'"), 1)
        self.assertEqual(self.release.count('V1_3_2_RELEASE_NOTES.md'), 1)
        self.assertNotIn('V1_3_1_RELEASE_NOTES.md', self.release)
        self.assertIn("manifest.version !== '1.3.2'", self.ci)

    def test_frozen_v1_3_1_baseline_and_both_parity_contracts_are_wired(self):
        for text in (self.ci, self.release):
            self.assertIn('25f269f8db333e27f23915ecb472eed6cb2709c6', text)
            self.assertIn('72df06c921a80bbe1128a0964f22e187811943c6', text)
            self.assertIn('7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd', text)
            self.assertIn('CAPABILITY_PARITY_V1_3_0_TO_V1_3_1', text)
            self.assertIn('CAPABILITY_PARITY_V1_3_1_TO_V1_3_2', text)
        self.assertIn('releases/download/v1.3.1/goujian-strategy-slides-v1.3.1.zip', self.ci)
        self.assertIn('releases/download/$release/goujian-strategy-slides-$release.zip', self.release)
        self.assertEqual(self.release.count('V131_BASELINE_COMMIT: 25f269f8db333e27f23915ecb472eed6cb2709c6'), 2)
        self.assertEqual(self.release.count('V131_BASELINE_TAG_OBJECT: 72df06c921a80bbe1128a0964f22e187811943c6'), 2)
        self.assertIn('--contract CAPABILITY_PARITY_V1_3_1_TO_V1_3_2', self.release)
        self.assertIn('--contract CAPABILITY_PARITY_V1_3_0_TO_V1_3_1', self.release)
        self.assertIn('V131_BASELINE_ROOT', self.release)
        self.assertIn('distribution/runtime-package.json" "$v131_parent/content/package.json"',
                      self.release)

    def test_installed_runtime_repacks_use_the_source_packager_from_outside(self):
        self.assertIn('"$GITHUB_WORKSPACE/scripts/package_runtime.py"', self.ci)
        self.assertIn('--runtime-root "$PWD"', self.ci)
        self.assertIn('--expect-sha256', self.ci)
        self.assertEqual(self.release.count('"$GITHUB_WORKSPACE/scripts/package_runtime.py"'), 2)
        self.assertEqual(self.release.count('--runtime-root "$PWD"'), 2)
        self.assertEqual(self.release.count('"$GITHUB_WORKSPACE/scripts/security_preflight.py"'), 1)

        in_runtime = self.release.split(
            'cd "$RUNNER_TEMP/runtime-install/goujian-strategy-slides"', 1)[1]
        self.assertNotIn('npm run package', in_runtime)
        self.assertNotIn('npm run preflight', in_runtime)
        self.assertIn('"$GITHUB_WORKSPACE/scripts/package_runtime.py"', in_runtime)

        fresh_clone = self.release.split(
            'git clone --depth 1 --branch "v$VERSION"', 1)[1].split(
            'cd "$RUNNER_TEMP/runtime-install/goujian-strategy-slides"', 1)[0]
        self.assertIn('npm run package', fresh_clone)
        self.assertIn('npm run package:source', fresh_clone)
        self.assertIn('python3 scripts/security_preflight.py', fresh_clone)

    def test_candidate_source_archive_full_suite_and_runtime_acceptance_are_wired(self):
        for path, text, receipt in (
            (CI, self.ci, 'out/runtime-acceptance.json'),
            (RELEASE, self.release, 'out/release-runtime-acceptance.json'),
        ):
            self.assertIn('scripts/runtime_acceptance.py', text, path)
            self.assertIn('--source-root "$GITHUB_WORKSPACE"', text, path)
            self.assertIn('--baseline-zip "$RUNNER_TEMP/goujian-v1.3.1-installer.zip"', text, path)
            self.assertIn('--baseline-root', text, path)
            self.assertIn('--node-modules "$GITHUB_WORKSPACE/node_modules"', text, path)
            self.assertIn(receipt, text, path)
            self.assertIn('goujian-source-acceptance', text, path)
            self.assertIn('source-archive-acceptance', text, path)
            self.assertIn(CAPTURE_ANCHOR, text, path)
            self.assertIn(PIPESTATUS_CAPTURE, text, path)
            self.assertIn('test "${npm_test_status[0]}" -eq 0', text, path)
            self.assertIn('test "${npm_test_status[1]}" -eq 0', text, path)
            self.assertIn('"${npm_test_status[0]}" "${npm_test_status[1]}" <<\'PY\'',
                          text, path)
            self.assertIn("'test_exit_statuses': {'npm': npm_status, 'tee': tee_status}",
                          text, path)
            self.assertNotIn('# fail 0', text, path)
            self.assertIn('installed_runtime_execution', text, path)
        self.assertIn("CAPABILITY_PARITY_V1_3_1_TO_V1_3_2'", self.ci)
        self.assertIn('release-runtime-acceptance.json release-source-archive-acceptance.json',
                      self.release)
        manifest = json.loads(
            (ROOT / 'distribution/runtime-manifest.json').read_text(encoding='utf-8'))
        for relative in ('scripts/runtime_acceptance.py', 'tests/test_runtime_acceptance.py'):
            self.assertNotIn(relative, manifest['runtime_files'], relative)

    def test_source_acceptance_capture_and_receipt_are_shared_and_exit_based(self):
        self.assertIn('out/source-archive-test.log', self.ci)
        self.assertIn('out/release-source-archive-test.log', self.release)
        for text in (self.ci, self.release):
            self.assertEqual(text.count(PIPESTATUS_CAPTURE), 1,
                             'PIPESTATUS must be saved once, immediately after the pipeline')
            self.assertIn('set +e', text)
            self.assertIn('set -e', text)
            self.assertIn('"${npm_test_status[0]}" "${npm_test_status[1]}"', text)
            self.assertNotIn('# fail 0', text)
        self.assertEqual(_capture_snippet(self.ci), _capture_snippet(self.release))
        self.assertEqual(_receipt_snippet(self.ci), _receipt_snippet(self.release))

    def test_installed_runtime_acceptance_failure_evidence_is_retained_and_uploaded(self):
        ci_step = _step_block(
            self.ci,
            'Accept the actual installed candidate runtime against the locked v1.3.1 runtime')
        release_step = _step_block(
            self.release,
            'Accept the installed candidate runtime against the locked v1.3.1 runtime')
        for acceptance in (ci_step, release_step):
            self.assertIn('set +e', acceptance)
            self.assertIn('acceptance_status=$?', acceptance)
            self.assertIn('set -e', acceptance)
            self.assertIn('> "$GITHUB_WORKSPACE/out/', acceptance)
            self.assertIn('-stderr.log"', acceptance)
            self.assertIn("print(f'FAIL: installed runtime acceptance exited", acceptance)
            self.assertIn('exit "$acceptance_status"', acceptance)
            self.assertLess(
                acceptance.index('exit "$acceptance_status"'),
                acceptance.index("assert result['status'] == 'PASS'"),
                'the success assertion must run only after the exact nonzero status is propagated')
            self.assertNotIn('failure-summary.json', acceptance)
        self.assertIn('--json "$GITHUB_WORKSPACE/out/runtime-acceptance.json"', ci_step)
        self.assertIn(
            '--json "$GITHUB_WORKSPACE/out/release-runtime-acceptance.json"', release_step)
        self.assertNotIn('$RUNNER_TEMP/runtime-acceptance-stdout.json', ci_step)

        upload = _step_block(
            self.ci,
            'Upload the real CI showcase, parity and acceptance evidence for independent review')
        self.assertIn('if: always() && matrix.node == 24', upload)
        self.assertIn('if-no-files-found: error', upload)
        for relative in (
            'out/runtime-acceptance.json',
            'out/runtime-acceptance-stdout.json',
            'out/runtime-acceptance-stderr.log',
            'out/runtime-acceptance-artifacts-*',
        ):
            self.assertIn(relative, upload)

        release_upload = _step_block(self.release, 'Upload validated archives and security receipts')
        self.assertIn('if: always()', release_upload)
        for relative in (
            'out/release-*.json',
            'out/release-runtime-acceptance-stderr.log',
            'out/release-runtime-acceptance-artifacts-*',
        ):
            self.assertIn(relative, release_upload)

    def test_actual_workflow_run_blocks_parse_as_bash(self):
        if shutil.which('bash') is None:
            self.skipTest('bash is required to check workflow shell syntax')
        for path, text in ((CI, self.ci), (RELEASE, self.release)):
            lines = text.splitlines()
            checked = 0
            for index, line in enumerate(lines):
                match = re.fullmatch(r'( *)run: \|[+-]?', line)
                if not match:
                    continue
                indent = len(match.group(1))
                end = index + 1
                while end < len(lines):
                    following = lines[end]
                    if following.strip() and len(following) - len(following.lstrip()) <= indent:
                        break
                    end += 1
                script = textwrap.dedent('\n'.join(lines[index + 1:end])) + '\n'
                result = subprocess.run(['bash', '-n'], input=script,
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0,
                                 f'{path}:{index + 1}: {result.stderr}')
                checked += 1
            self.assertGreater(checked, 0, path)

    def test_installed_runtime_installs_baseline_owned_dependencies(self):
        cases = (
            (self.ci,
             'Accept the actual installed candidate runtime against the locked v1.3.1 runtime',
             'cd "$baseline_root"'),
            (self.release,
             'Accept the installed candidate runtime against the locked v1.3.1 runtime',
             'cd "$baseline_root"'),
        )
        for text, name, baseline_cd in cases:
            block = _step_block(text, name)
            self.assertIn(baseline_cd, block)
            self.assertIn('NPM_CONFIG_USERCONFIG="$empty_npmrc"', block)
            self.assertIn('npm ci --ignore-scripts', block)
            self.assertIn("assert baseline_modules['owned'] is True", block)
            self.assertIn("assert baseline_modules['source'] == 'root-owned'", block)
            self.assertLess(
                block.index('npm ci --ignore-scripts'),
                block.index('scripts/runtime_acceptance.py'),
                'the baseline must own its lock-matched install before the harness runs')

    def test_actions_are_pinned_to_commit_shas(self):
        for text in (self.security, self.release):
            for name in ('actions/checkout@', 'actions/setup-python@',
                         'actions/setup-node@', 'actions/upload-artifact@'):
                for match in re.finditer(re.escape(name) + r'([^\s]+)', text):
                    self.assertRegex(match.group(1), r'^[0-9a-f]{40}(?:\s|#|$)',
                                     f'{name} is not pinned: {match.group(0)}')

    def test_release_scanner_uses_3_14_after_unchanged_product_3_11(self):
        head = self.release.split('\n  publish:\n', 1)[0]
        self.assertEqual(head.count("python-version: '3.11'"), 1)
        self.assertEqual(head.count("python-version: '3.14'"), 1)
        self.assertEqual(head.count('uses: actions/setup-python@'), 2)

        product_setup = head.index("python-version: '3.11'")
        product_build = head.index(
            'name: Clean install, test, build, benchmark, doctor and QA')
        scanner_setup = head.index(
            'name: Set up Python 3.14 for the isolated security scanner')
        scanner_install = head.index(
            'name: Install the pinned scanner and PDF parser for the release security gate')
        scanner_venv = head.index('python3 -m venv "$scanner_root"')

        self.assertLess(product_setup, product_build,
                        'the product 3.11 setup must precede the product build')
        self.assertLess(product_build, scanner_setup,
                        'the scanner 3.14 setup must follow product validation')
        self.assertLess(scanner_setup, scanner_install,
                        'the scanner 3.14 setup must precede the scanner install')
        self.assertLess(scanner_install, scanner_venv,
                        'the scanner venv must be created after the scanner install step')
        scanner_step = head[scanner_setup:scanner_install]
        self.assertIn('uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065',
                      scanner_step)
        self.assertIn("python-version: '3.14'", scanner_step)


class SourceAcceptanceReceiptTests(unittest.TestCase):
    REQUIRED_SOURCE_FILES = (
        'scripts/package_runtime.py',
        'scripts/security_preflight.py',
        'scripts/runtime_acceptance.py',
        'tests/test_runtime_acceptance.py',
        'skill/reasoning/fixtures/hostile-source/plan.json',
        'skill/reasoning/fixtures/hostile-source/sources/hostile.md',
    )

    @classmethod
    def setUpClass(cls):
        ci_text = CI.read_text(encoding='utf-8')
        cls.capture = _capture_snippet(ci_text)
        cls.receipt = _receipt_snippet(ci_text)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / 'bin'
        self.bin.mkdir()
        self.runner_temp = self.tmp / 'runner-temp'
        self.runner_temp.mkdir()
        self.path = os.pathsep.join((str(self.bin), '/usr/bin', '/bin'))
        if shutil.which('bash', path=self.path) is None:
            self.skipTest('bash is required to exercise the embedded capture snippet')

    def _install_fake_npm(self, stdout, stderr, code):
        script = self.bin / 'npm'
        script.write_text(
            '#!/bin/bash\n'
            "cat <<'JIAN_STDOUT'\n" + stdout + 'JIAN_STDOUT\n'
            "cat <<'JIAN_STDERR' >&2\n" + stderr + 'JIAN_STDERR\n'
            f'exit {code}\n',
            encoding='utf-8')
        script.chmod(0o755)

    def _run_capture(self, runner_temp=None):
        runner_temp = self.runner_temp if runner_temp is None else runner_temp
        script = self.tmp / 'capture.sh'
        script.write_text(
            'set -euo pipefail\n'
            f'export PATH={shlex.quote(self.path)}\n'
            f'export RUNNER_TEMP={shlex.quote(str(runner_temp))}\n'
            + self.capture,
            encoding='utf-8')
        return subprocess.run(
            ['bash', str(script)],
            capture_output=True, text=True)

    def _read_log(self):
        return (self.runner_temp / 'source-archive-test.log').read_text(encoding='utf-8')

    def test_capture_accepts_tap_and_unicode_spec_success(self):
        self._install_fake_npm(
            'TAP version 13\nok 1 - native case\n1..1\n# fail 0\n\u2139 fail 0\n',
            '\u2139 stderr diagnostic\n', 0)
        result = self._run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        log_text = self._read_log()
        self.assertIn('# fail 0', log_text)
        self.assertIn('\u2139 fail 0', log_text)
        self.assertIn('stderr diagnostic', log_text)

    def test_capture_rejects_nonzero_npm_even_when_output_claims_success(self):
        self._install_fake_npm(
            'TAP version 13\nnot ok 1 - forced case\n1..1\n# fail 0\nPASS\n',
            'forced failure diagnostic\n', 1)
        result = self._run_capture()
        self.assertNotEqual(
            result.returncode, 0,
            'a nonzero npm test must be rejected regardless of the printed text')
        log_text = self._read_log()
        self.assertIn('# fail 0', log_text)
        self.assertIn('PASS', log_text)
        self.assertIn('forced failure diagnostic', log_text)

    def test_capture_rejects_failed_log_capture(self):
        self._install_fake_npm('TAP version 13\n1..0\n', '', 0)
        result = self._run_capture(runner_temp=self.tmp / 'missing' / 'nested')
        self.assertNotEqual(result.returncode, 0, 'a tee failure must reject the receipt')

    def _receipt_fixture(self, version='1.3.2', missing=None):
        source_root = self.tmp / 'source-root'
        for relative in self.REQUIRED_SOURCE_FILES:
            if relative == missing:
                continue
            path = source_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}\n', encoding='utf-8')
        (source_root / 'package.json').write_text(
            json.dumps({'version': version}) + '\n', encoding='utf-8')
        archive = self.tmp / 'source.zip'
        archive.write_bytes(b'archive-bytes')
        log = self.tmp / 'source-archive-test.log'
        log.write_text('\u2139 tests 1\n\u2139 pass 1\n\u2139 fail 0\n', encoding='utf-8')
        receipt_path = self.tmp / 'out' / 'source-archive-acceptance.json'
        return source_root, archive, log, receipt_path

    def _run_receipt(self, source_root, archive, log, receipt_path,
                     version='1.3.2', npm_status='0', tee_status='0'):
        script = self.tmp / 'receipt.py'
        script.write_text(self.receipt, encoding='utf-8')
        return subprocess.run(
            [sys.executable, str(script),
             str(archive), str(source_root), str(log), str(receipt_path),
             version, npm_status, tee_status],
            capture_output=True, text=True)

    def test_receipt_accepts_real_success_and_records_exit_statuses(self):
        fixture = self._receipt_fixture()
        result = self._run_receipt(*fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(fixture[3].read_text(encoding='utf-8'))
        self.assertEqual(receipt['status'], 'PASS')
        self.assertEqual(receipt['test_exit_statuses'], {'npm': 0, 'tee': 0})
        self.assertEqual(receipt['source_version'], '1.3.2')
        self.assertTrue(receipt['required_source_files_present'])
        log_text = fixture[2].read_text(encoding='utf-8')
        self.assertEqual(receipt['test_log_sha256'],
                         hashlib.sha256(log_text.encode('utf-8')).hexdigest())
        self.assertEqual(receipt['archive']['sha256'],
                         hashlib.sha256(fixture[1].read_bytes()).hexdigest())

    def test_receipt_rejects_empty_log(self):
        source_root, archive, log, receipt_path = self._receipt_fixture()
        log.write_text('', encoding='utf-8')
        result = self._run_receipt(source_root, archive, log, receipt_path)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(receipt_path.exists())

    def test_receipt_rejects_nonzero_npm_status_even_with_success_text(self):
        fixture = self._receipt_fixture()
        result = self._run_receipt(*fixture, npm_status='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(fixture[3].exists())

    def test_receipt_rejects_nonzero_tee_status(self):
        fixture = self._receipt_fixture()
        result = self._run_receipt(*fixture, tee_status='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(fixture[3].exists())

    def test_receipt_rejects_version_mismatch(self):
        fixture = self._receipt_fixture(version='1.3.1')
        result = self._run_receipt(*fixture, version='1.3.2')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(fixture[3].exists())

    def test_receipt_rejects_missing_required_source_file(self):
        fixture = self._receipt_fixture(missing='scripts/runtime_acceptance.py')
        result = self._run_receipt(*fixture)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(fixture[3].exists())


class RuntimeAcceptanceFailureCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = _runtime_summary_snippet(CI.read_text(encoding='utf-8'))

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.out = self.tmp / 'out'
        self.out.mkdir()
        if shutil.which('bash') is None:
            self.skipTest('bash is required to exercise the embedded capture snippet')

    def _run(self, code, result_payload=None, stdout='', stderr=''):
        if result_payload is not None:
            (self.out / 'result.json').write_text(result_payload, encoding='utf-8')
        harness = self.tmp / 'fake-acceptance-harness'
        harness.write_text(
            '#!/usr/bin/env bash\n'
            f'printf %s {shlex.quote(stdout)}\n'
            f'printf %s {shlex.quote(stderr)} >&2\n'
            f'exit {code}\n',
            encoding='utf-8')
        harness.chmod(0o755)
        script = self.tmp / 'acceptance-wrapper.sh'
        script.write_text(
            'set -euo pipefail\n'
            f'out_dir={shlex.quote(str(self.out))}\n'
            'set +e\n'
            f'{shlex.quote(str(harness))} > "$out_dir/stdout.json" 2> "$out_dir/stderr.log"\n'
            'acceptance_status=$?\n'
            'set -e\n'
            'if [ "$acceptance_status" -ne 0 ]; then\n'
            '  python3 - "$out_dir/result.json" "$out_dir/stderr.log" '
            '"$acceptance_status" <<\'PY\'\n'
            + self.summary +
            'PY\n'
            '  exit "$acceptance_status"\n'
            'fi\n',
            encoding='utf-8')
        return subprocess.run(['bash', str(script)], capture_output=True, text=True)

    def test_failure_is_bounded_and_the_exact_exit_status_is_propagated(self):
        failures = [f'failure-{index:02d}-' + 'x' * 400 for index in range(25)]
        payload = json.dumps({
            'status': 'FAIL',
            'coverage': {'status': 'FAIL'},
            'failures': failures,
            'comparisons': {
                'failed-case': {'status': 'FAIL',
                                'failures': [f'case-{index}' for index in range(7)]},
                'passing-case': {'status': 'PASS', 'failures': []},
            },
            'artifacts': {'root': '/tmp/artifacts', 'manifest_count': 3,
                          'manifest_sha256': 'a' * 64},
        })
        stderr = ''.join(f'stderr-line-{index:02d}\n' for index in range(50))
        result = self._run(42, result_payload=payload,
                           stdout='stdout-diagnostic\n', stderr=stderr)
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertIn('FAIL: installed runtime acceptance exited 42', result.stdout)
        self.assertEqual(result.stdout.count('  failure: '), 20)
        self.assertNotIn('failure-20-', result.stdout)
        self.assertEqual(result.stdout.count('  comparison failed-case: '), 5)
        self.assertNotIn('comparison passing-case:', result.stdout)
        self.assertIn('stderr-line-49', result.stdout)
        self.assertNotIn('stderr-line-09', result.stdout)
        self.assertNotIn('stdout-diagnostic', result.stdout)
        self.assertEqual(
            json.loads((self.out / 'result.json').read_text(encoding='utf-8')),
            json.loads(payload),
            'the full harness result must remain on disk unchanged')
        self.assertEqual((self.out / 'stderr.log').read_text(encoding='utf-8'), stderr)
        self.assertFalse((self.out / 'summary.json').exists())

    def test_crash_without_result_retains_stderr_and_exit_status(self):
        result = self._run(1, result_payload=None, stderr='boom before result\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('FAIL: installed runtime acceptance exited 1', result.stdout)
        self.assertIn('boom before result', result.stdout)
        self.assertFalse((self.out / 'result.json').exists())

    def test_malformed_result_does_not_mask_the_exit_status(self):
        result = self._run(1, result_payload='{not json', stderr='parser noise\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('FAIL: installed runtime acceptance exited 1', result.stdout)
        self.assertIn('result unreadable', result.stdout)
        self.assertIn('parser noise', result.stdout)

    def test_success_exits_zero_without_failure_output(self):
        payload = json.dumps({'status': 'PASS', 'coverage': {'status': 'PASS'},
                              'failures': [], 'comparisons': {},
                              'artifacts': {'root': '/tmp/artifacts',
                                            'manifest_count': 1,
                                            'manifest_sha256': 'b' * 64}})
        result = self._run(0, result_payload=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('FAIL:', result.stdout)
        self.assertEqual(
            json.loads((self.out / 'result.json').read_text(encoding='utf-8')),
            json.loads(payload))
        self.assertTrue((self.out / 'stdout.json').is_file())
        self.assertTrue((self.out / 'stderr.log').is_file())


if __name__ == '__main__':
    unittest.main()
