#!/usr/bin/env python3
"""Tests for the final-ZIP security preflight.

Dangerous fixtures are assembled at runtime from fragments so the repository
archive itself never carries a raw executable trigger. Inert fixtures cover
strings, comments and escaped regex literals; the scanner must classify them
as inert rather than executable.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
FILE_MODE = 0o644


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load('goujian_security_preflight', 'scripts/security_preflight.py')
packager = load('goujian_package_runtime', 'scripts/package_runtime.py')


def info_for(name, mode=FILE_MODE):
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def read_members(path):
    with zipfile.ZipFile(path) as archive:
        return [(info, archive.read(info.filename)) for info in archive.infolist()]


def write_members(path, members):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for info, data in members:
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)


def codes(report):
    return {item['code'] for item in report['violations']}


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='goujian-preflight-')
        cls.actual = Path(cls.temp.name) / 'installer.zip'
        packager.build(cls.actual)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def variant(self, name, members):
        path = Path(self.temp.name) / name
        write_members(path, members)
        return path

    def members(self):
        return read_members(self.actual)

    def add_member(self, name, data, mode=FILE_MODE):
        members = self.members()
        members.append((info_for(name, mode), data.encode('utf-8') if isinstance(data, str) else data))
        return members

    def replace_member(self, relative, transform):
        members = self.members()
        target = PREFIX + relative
        replaced = False
        for index, (info, data) in enumerate(members):
            if info.filename == target:
                members[index] = (info, transform(data))
                replaced = True
                break
        self.assertTrue(replaced, relative)
        return members

    def test_actual_installer_passes_all_direct_checks(self):
        report = preflight.preflight(self.actual)
        self.assertEqual(report['status'], 'PASS', report['violations'])
        self.assertEqual(report['violations'], [])
        self.assertGreater(report['entries'], 50)
        self.assertGreater(report['uncompressed_bytes'], 0)
        self.assertEqual(report['code_execution']['status'], 'PASS')
        self.assertEqual(report['code_execution']['python_parser'], 'ast')
        self.assertEqual(report['code_execution']['javascript_parser'], 'lexical-string-comment-stripped')
        self.assertGreater(report['code_execution']['files_scanned'], 20)
        for check in ('structure', 'paths', 'permissions', 'symlinks', 'skill', 'frontmatter',
                      'datetime', 'decompression', 'dependencies', 'code_execution'):
            self.assertEqual(report['checks'][check]['status'], 'PASS', check)

    def test_dangerous_python_shell_call_is_rejected(self):
        source = 'import os\n' + 'os.' + 'sys' + "tem('echo danger')\n"
        path = self.variant('danger-python.zip', self.add_member(PREFIX + 'tests/runtime_fixture.py', source))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('CODE_EXECUTION', codes(report))
        self.assertTrue(any(item['kind'] == 'PYTHON_SHELL_EXECUTION' for item in report['code_execution']['findings']))

    def test_dangerous_javascript_call_is_rejected(self):
        source = 'const cp = require("child_process");\ncp.' + 'ex' + 'ec("echo danger");\n'
        path = self.variant('danger-js.zip', self.add_member(PREFIX + 'tests/runtime_fixture.js', source))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('CODE_EXECUTION', codes(report))
        self.assertTrue(any(item['kind'] == 'CHILD_PROCESS_EXEC' for item in report['code_execution']['findings']))

    def test_shell_true_and_string_commands_are_rejected(self):
        source = ('import ' + 'sub' + 'process\n'
                  + 'sub' + 'process.run("echo danger", she' + 'll=True)\n')
        path = self.variant('danger-shell.zip', self.add_member(PREFIX + 'tests/runtime_shell.py', source))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        kinds = {item['kind'] for item in report['code_execution']['findings']}
        self.assertIn('SHELL_TRUE', kinds)
        self.assertIn('STRING_COMMAND', kinds)

    def test_inert_strings_comments_and_escaped_regexes_pass(self):
        inert_python = ('# inert comment only\n'
                        + 'text = "' + 'os.' + 'sys' + 'tem' + '"\n'
                        + 'pattern = "' + 'sub' + 'process' + '"\n'
                        + 'doc = """' + 'child_' + 'process.' + 'ex' + 'ec' + '"""\n')
        inert_js = ('const text = "child_" + "pro" + "cess." + "ex" + "ec";\n'
                    + 'const commentLike = "she" + "ll: true";\n'
                    + 'const escaped = /child_process\\.ex\\s*ec\\(/;\n')
        members = self.add_member(PREFIX + 'tests/inert_fixture.py', inert_python)
        members.append((info_for(PREFIX + 'tests/inert_fixture.js'), inert_js.encode('utf-8')))
        path = self.variant('inert.zip', members)
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'PASS', report['violations'])
        self.assertEqual(report['code_execution']['findings'], [])

    def test_static_datetime_regression_is_rejected(self):
        members = self.members()
        members[0][0].date_time = (2026, 1, 2, 0, 0, 0)
        path = self.variant('datetime.zip', members)
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('STATIC_DATETIME_REGRESSION', codes(report))

    def test_symlink_and_permission_regressions_are_rejected(self):
        symlink = self.members()
        symlink.append((info_for(PREFIX + 'tests/link.py', 0o120777), b'package.json'))
        report = preflight.preflight(self.variant('symlink.zip', symlink))
        self.assertIn('SYMLINK', codes(report))

        permissions = self.members()
        permissions[0][0].external_attr = 0o100755 << 16
        report = preflight.preflight(self.variant('permissions.zip', permissions))
        self.assertIn('PERMISSIONS', codes(report))

    def test_unsafe_paths_duplicates_and_multiple_skill_entries_are_rejected(self):
        traversal = self.add_member(PREFIX + '../evil.py', 'x = 1\n')
        report = preflight.preflight(self.variant('traversal.zip', traversal))
        self.assertIn('UNSAFE_PATH', codes(report))

        duplicate_skill = self.add_member(PREFIX + 'skill/SKILL.md', '---\nname: other\n---\n')
        report = preflight.preflight(self.variant('skills.zip', duplicate_skill))
        self.assertIn('MULTIPLE_SKILL', codes(report))

        duplicate = self.members()
        duplicate.append(duplicate[0])
        report = preflight.preflight(self.variant('duplicate.zip', duplicate))
        self.assertIn('DUPLICATE_ENTRY', codes(report))

        generated = self.add_member(PREFIX + 'out/generated.json', '{}\n')
        report = preflight.preflight(self.variant('generated.zip', generated))
        self.assertIn('FORBIDDEN_MEMBER', codes(report))

    def test_showcase_allowlist_accepts_only_the_fixed_v13_subtree(self):
        allowed = self.members()
        allowed.append((info_for(PREFIX + 'out/v1.3-showcase/decks/example.pptx'), b'pptx'))
        allowed.append((info_for(PREFIX + 'out/v1.3-showcase/render/slide-1.png'), b'png'))
        report = preflight.preflight(self.variant('showcase-allowed.zip', allowed), allow_showcase=True)
        self.assertEqual(report['status'], 'PASS', report['violations'])

        for member in ('out/v1.2-showcase/decks/example.pptx', 'out/v1.3-showcase-other/deck.pptx', 'out/other/deck.pptx'):
            rejected = self.members()
            rejected.append((info_for(PREFIX + member), b'pptx'))
            report = preflight.preflight(self.variant('showcase-rejected.zip', rejected), allow_showcase=True)
            self.assertEqual(report['status'], 'FAIL')
            self.assertIn('FORBIDDEN_MEMBER', codes(report), member)

        installer = self.members()
        installer.append((info_for(PREFIX + 'out/v1.3-showcase/decks/example.pptx'), b'pptx'))
        report = preflight.preflight(self.variant('showcase-installer.zip', installer))
        self.assertIn('FORBIDDEN_MEMBER', codes(report))

    def test_frontmatter_version_mismatch_is_rejected(self):
        def change(data):
            changed = data.replace(b'version: "1.3.0"', b'version: "9.9.9"')
            self.assertNotEqual(changed, data)
            return changed
        path = self.variant('frontmatter.zip', self.replace_member('SKILL.md', change))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('FRONTMATTER', codes(report))

    def test_dependency_and_requirements_drift_is_rejected(self):
        def drift_dependency(data):
            package = json.loads(data)
            package['dependencies']['ajv'] = '9.9.9'
            return json.dumps(package).encode('utf-8')
        report = preflight.preflight(self.variant('dependency.zip', self.replace_member('package.json', drift_dependency)))
        self.assertIn('DEPENDENCY', codes(report))

        fallback = self.replace_member('requirements-render.txt', lambda data: b'Pillow==12.1.1\n')
        report = preflight.preflight(self.variant('requirements.zip', fallback))
        self.assertIn('REQUIREMENTS', codes(report))

    def test_cli_writes_report_and_uses_exit_status(self):
        report_path = Path(self.temp.name) / 'cli-report.json'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/security_preflight.py'),
                                 str(self.actual), '--json', str(report_path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'PASS')
        bad = self.variant('cli-bad.zip', self.add_member(PREFIX + 'tests/runtime_fixture.js',
                                                          'cp.' + 'ex' + 'ec("echo danger");\n'))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/security_preflight.py'), str(bad)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('CODE_EXECUTION', result.stderr)


if __name__ == '__main__':
    unittest.main()
