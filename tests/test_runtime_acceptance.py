import hashlib
import json
import sys
import tempfile
import unittest
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
        evidence = acceptance.baseline_runtime_evidence(
            self.archive, self.root, self.contract('0' * 64))
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


if __name__ == '__main__':
    unittest.main()
