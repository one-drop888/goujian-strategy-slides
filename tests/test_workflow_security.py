#!/usr/bin/env python3
"""Structural guards for the permanent release security pipeline.

These tests read the workflow text so a future edit cannot silently remove the
scanner gate, the live advisory check, the receipt re-verification, the
hash-bound release evidence, or the typed publish approval. They do not run
GitHub Actions.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / '.github/workflows/ci.yml'
SECURITY = ROOT / '.github/workflows/skill-security.yml'
RELEASE = ROOT / '.github/workflows/release.yml'


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
            self.assertIn('npm test | tee', text, path)
            self.assertIn('installed_runtime_execution', text, path)
        self.assertIn("CAPABILITY_PARITY_V1_3_1_TO_V1_3_2'", self.ci)
        self.assertIn('release-runtime-acceptance.json release-source-archive-acceptance.json',
                      self.release)
        manifest = json.loads(
            (ROOT / 'distribution/runtime-manifest.json').read_text(encoding='utf-8'))
        for relative in ('scripts/runtime_acceptance.py', 'tests/test_runtime_acceptance.py'):
            self.assertNotIn(relative, manifest['runtime_files'], relative)

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


if __name__ == '__main__':
    unittest.main()
