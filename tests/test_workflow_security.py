#!/usr/bin/env python3
"""Structural guards for the permanent release security pipeline.

These tests read the workflow text so a future edit cannot silently remove the
scanner gate, the live advisory check, the receipt re-verification, the
hash-bound release evidence, or the typed publish approval. They do not run
GitHub Actions.
"""
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
