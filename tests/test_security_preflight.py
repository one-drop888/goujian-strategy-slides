#!/usr/bin/env python3
"""Tests for the final-ZIP security preflight.

Dangerous fixture payloads are plain strings for transparent inspection. They
are never executed: tests write them into temporary ZIPs and inspect findings.
Inert fixtures verify that rules and examples are not treated as live code.
"""
import ast
import hashlib
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
        cls.source = Path(cls.temp.name) / 'source.zip'
        packager.build(cls.source, source=True)

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
        self.assertEqual(report['profile'], 'runtime')
        self.assertGreater(report['entries'], 50)
        self.assertGreater(report['uncompressed_bytes'], 0)
        self.assertEqual(report['code_execution']['status'], 'PASS')
        self.assertEqual(report['code_execution']['python_parser'], 'ast')
        self.assertEqual(report['code_execution']['javascript_parser'], 'lexical-string-comment-stripped')
        self.assertGreater(report['code_execution']['files_scanned'], 20)
        self.assertGreater(report['inventory']['text_files'], 50)
        self.assertGreater(report['inventory']['hits'], 0)
        for check in ('structure', 'paths', 'permissions', 'symlinks', 'skill', 'frontmatter',
                      'datetime', 'decompression', 'dependencies', 'metadata', 'code_execution'):
            self.assertEqual(report['checks'][check]['status'], 'PASS', check)

    def test_source_archive_reports_development_module_loading_separately(self):
        report = preflight.preflight(self.source)
        self.assertEqual(report['profile'], 'source')
        self.assertEqual(report['status'], 'PASS', report['violations'])
        self.assertEqual(report['code_execution']['findings'], [])
        development = report['code_execution']['development_findings']
        self.assertTrue(development)
        self.assertTrue(all(item['scope'] == 'development' for item in development))
        self.assertTrue(any(item['member'].startswith(PREFIX + 'tests/') for item in development))
        self.assertTrue(any(item['kind'] == 'PYTHON_DYNAMIC_MODULE_LOAD' for item in development))

    def test_legacy_baseline_reports_new_loading_but_enforces_original_deny_rules(self):
        members = self.members()
        members = [item for item in members
                   if not item[0].filename.startswith(PREFIX + 'distribution/')]
        # v1.3.1 kept the release tools inside the installer; restore them for the
        # historical legacy profile now that they are Source-only.
        for tool in ('scripts/security_preflight.py', 'scripts/package_runtime.py'):
            members.append((info_for(PREFIX + tool), (ROOT / tool).read_bytes()))
        members.append((info_for(PREFIX + 'tests/test_security_preflight.py'), b'legacy = True\n'))
        dynamic = ('import importlib.util\nspec = importlib.util.spec_from_file_location("m", "/tmp/x.py")\nmodule = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n')
        legacy_members = members + [
            (info_for(PREFIX + 'tests/legacy_dynamic.py'), dynamic.encode('utf-8'))]
        report = preflight.preflight(self.variant('legacy.zip', legacy_members))
        self.assertEqual(report['profile'], 'legacy')
        self.assertEqual(report['status'], 'PASS', report['violations'])
        self.assertEqual(report['code_execution']['mode'], 'enforced')
        reported = (report['code_execution']['report_only_findings']
                    + report['code_execution']['development_findings'])
        self.assertTrue(any(item['kind'] == 'PYTHON_DYNAMIC_MODULE_LOAD' for item in reported))

        hostile = ("import os\nos.system('echo legacy')\n")
        blocked = legacy_members + [
            (info_for(PREFIX + 'tests/legacy_fixture.py'), hostile.encode('utf-8'))]
        report = preflight.preflight(self.variant('legacy-hostile.zip', blocked))
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('CODE_EXECUTION', codes(report))

        unsafe = members + [(info_for(PREFIX + '../escape.py'), b'x = 1\n')]
        report = preflight.preflight(self.variant('legacy-unsafe.zip', unsafe))
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('UNSAFE_PATH', codes(report))

    def test_runtime_omits_exactly_the_four_source_only_members(self):
        report = preflight.preflight(self.actual)
        self.assertEqual(report['status'], 'PASS', report['violations'])
        with zipfile.ZipFile(self.actual) as package:
            names = set(package.namelist())
            manifest = json.loads(package.read(PREFIX + 'distribution/runtime-manifest.json'))
            runtime_package = json.loads(package.read(PREFIX + 'package.json'))
        self.assertEqual(len(manifest['runtime_files']), 185)
        self.assertEqual(len(names), 186)
        for relative in ('scripts/security_preflight.py', 'scripts/package_runtime.py',
                         'skill/reasoning/fixtures/hostile-source/plan.json',
                         'skill/reasoning/fixtures/hostile-source/sources/hostile.md'):
            self.assertNotIn(relative, manifest['runtime_files'], relative)
            self.assertNotIn(PREFIX + relative, names, relative)
        self.assertEqual(runtime_package['version'], '1.3.2')
        for command in ('package', 'preflight'):
            self.assertNotIn(command, runtime_package['scripts'])
            self.assertIn(command, manifest['omitted_commands'])
        for command in ('validate:all', 'test', 'test:core'):
            self.assertIn(command, runtime_package['scripts'])

    def test_source_keeps_release_commands_and_tools(self):
        report = preflight.preflight(self.source)
        self.assertEqual(report['status'], 'PASS', report['violations'])
        with zipfile.ZipFile(self.source) as package:
            names = set(package.namelist())
            scripts = json.loads(package.read(PREFIX + 'package.json'))['scripts']
        for command in ('package', 'package:source', 'preflight',
                        'security:scan', 'security:verify', 'test:pdf'):
            self.assertIn(command, scripts, command)
        for relative in ('scripts/security_preflight.py', 'scripts/package_runtime.py',
                         'skill/reasoning/fixtures/hostile-source/plan.json',
                         'skill/reasoning/fixtures/hostile-source/sources/hostile.md'):
            self.assertIn(PREFIX + relative, names, relative)

    def test_runtime_cannot_reintroduce_source_only_commands(self):
        def add_script(data):
            package = json.loads(data)
            package['scripts']['package'] = 'python3 scripts/package_runtime.py'
            return json.dumps(package, indent=2).encode('utf-8')
        members = self.replace_member('package.json', add_script)
        members = [item for item in members if item[0].filename != PREFIX + 'distribution/runtime-package.json']
        members.append((info_for(PREFIX + 'distribution/runtime-package.json'),
                        add_script((ROOT / 'distribution/runtime-package.json').read_bytes())))
        report = preflight.preflight(self.variant('runtime-command.zip', members))
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('RUNTIME_METADATA', codes(report))

    def test_runtime_manifest_must_declare_source_only_commands_omitted(self):
        def drop_omitted(data):
            manifest = json.loads(data)
            manifest['omitted_commands'] = [name for name in manifest['omitted_commands']
                                            if name != 'package']
            return json.dumps(manifest, indent=2).encode('utf-8')
        members = self.replace_member('distribution/runtime-manifest.json', drop_omitted)
        report = preflight.preflight(self.variant('runtime-omitted.zip', members))
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('RUNTIME_MANIFEST', codes(report))

    def test_executable_risk_detectors_are_ast_identical_to_v1_3_1(self):
        """Pin the detector AST; equality with tag v1.3.1 (25f269f) was proven in Phase 1."""
        names = (
            'SUBPROCESS_NAMES', 'DANGEROUS_DOTTED', 'SHELL_EXECUTABLES', 'PYTHON_EXECUTABLES',
            'NODE_EXECUTABLES', 'JS_PATTERNS', 'INVENTORY_PATTERNS', 'strip_javascript_noise',
            'static_string_call_argument', 'position_in_spans', 'python_inert_spans', 'scope_of',
            'inventory_scope', 'scan_inventory', 'scan_literal', 'dotted_name', 'keyword_value',
            'collect_python_aliases', 'resolve_dotted', 'literal_prefix', 'executable_name',
            'scan_python_source', 'js_child_process_vars', 'js_alias_patterns',
            'scan_javascript_source', 'finding',
        )
        tree = ast.parse((ROOT / 'scripts/security_preflight.py').read_text(encoding='utf-8'))
        found = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                found[node.name] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found[target.id] = node.value
        payload = '\n'.join(name + '\n' + ast.dump(found[name], include_attributes=False)
                            for name in names)
        self.assertEqual(hashlib.sha256(payload.encode('utf-8')).hexdigest(),
                         'b0756be5aea1511cbf8fd9919abcf1d32a8acd95ecf2aa44b454b2d866f20433')

    def test_dynamic_module_loading_is_rejected_in_runtime(self):
        source = ('import importlib.util\nspec = importlib.util.spec_from_file_location("m", "/tmp/x.py")\nmodule = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n')
        path = self.variant('dynamic-module.zip',
                            self.add_member(PREFIX + 'tests/runtime_dynamic.py', source))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('CODE_EXECUTION', codes(report))
        self.assertTrue(any(item['kind'] == 'PYTHON_DYNAMIC_MODULE_LOAD'
                            for item in report['code_execution']['findings']))

    def test_known_static_name_dynamic_import_cannot_regress_in_production(self):
        for source in ("__import__('datetime')", "import importlib\nimportlib.import_module('datetime')"):
            for profile in ('runtime', 'source'):
                blocking, _ = preflight.scan_python_source('scripts/doctor.py', source,
                                                           'production', profile)
                self.assertTrue(any(item['kind'] == 'PYTHON_DYNAMIC_MODULE_LOAD' for item in blocking),
                                (profile, source))
        blocking, _ = preflight.scan_python_source('scripts/doctor.py', 'import datetime')
        self.assertEqual(blocking, [])

    def test_static_require_is_transparent_but_dynamic_require_is_rejected(self):
        blocking, reported = preflight.scan_javascript_source(
            'tests/runtime_static.js',
            "const cp = require('child_process');\nconst fs = require('fs');\n",
            'production', 'runtime')
        self.assertEqual(blocking, [])
        self.assertEqual(reported, [])

        dynamic = ('const name = process.argv[2];\nconst loaded = require(name);\n')
        path = self.variant('dynamic-require.zip',
                            self.add_member(PREFIX + 'tests/runtime_dynamic.js', dynamic))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertTrue(any(item['kind'] == 'JAVASCRIPT_DYNAMIC_MODULE_LOAD'
                            for item in report['code_execution']['findings']))

    def test_child_process_aliases_and_bypasses_are_rejected(self):
        cases = {
            'destructured': ("const { exec: run } = require('child_process');\n"
                             "run(process.argv[2]);\n"),
            'bracket': ("const cp = require('child_process');\n"
                        "cp['ex' + 'ec'](process.argv[2]);\n"),
            'dotted': ("const cp = require('child_process');\n"
                       "cp['exec'](process.argv[2]);\n"),
        }
        for label, source in cases.items():
            blocking, _ = preflight.scan_javascript_source(
                f'tests/{label}.js', source, 'production', 'runtime')
            self.assertTrue(blocking, label)

    def test_shell_wrappers_and_inline_payloads_are_rejected_in_runtime(self):
        python_wrapper = ('import subprocess\nsubprocess.run(["sh", "-c", command])\n')
        path = self.variant('shell-wrapper.zip',
                            self.add_member(PREFIX + 'tests/runtime_wrapper.py', python_wrapper))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertTrue(any(item['kind'] == 'PYTHON_SHELL_WRAPPER'
                            for item in report['code_execution']['findings']))

        js_wrapper = ("const {execFileSync}=require('child_process');\n"
                      "execFileSync('sh', ['-c', process.argv[2]]);\n")
        blocking, _ = preflight.scan_javascript_source(
            'tests/wrapper.js', js_wrapper, 'production', 'runtime')
        self.assertTrue(any(item['kind'] == 'JAVASCRIPT_SHELL_WRAPPER' for item in blocking))

        for label, executable in (('node-e', 'node'), ('python-c', 'python3')):
            source = ('const {execFileSync}=require(\'child_process\');\n'
                      + f"execFileSync('{executable}', ['-{('e' if executable == 'node' else 'c')}', '1']);\n")
            blocking, _ = preflight.scan_javascript_source(
                f'tests/{label}.js', source, 'production', 'runtime')
            self.assertTrue(any(item['kind'] == 'JAVASCRIPT_FIXED_CODE_FLAG' for item in blocking), label)

    def test_fixed_inline_payloads_are_development_reporting_in_source_tests(self):
        source = ('import subprocess\nsubprocess.run(["python3", "-c", "print(1)"])\n')
        blocking, reported = preflight.scan_python_source(
            'tests/probe_fixture.py', source, 'development', 'source')
        self.assertEqual(blocking, [])
        self.assertTrue(any(item['kind'] == 'PYTHON_FIXED_CODE_FLAG' for item in reported))

        blocking, _ = preflight.scan_python_source(
            'core/qa/runtime_fixture.py', source, 'production', 'source')
        self.assertTrue(any(item['kind'] == 'PYTHON_FIXED_CODE_FLAG' for item in blocking))

    def test_original_deny_rules_apply_to_every_profile(self):
        for profile in preflight.PROFILES:
            for scope in ('production', 'development'):
                for source in ("eval(user_input)", "import subprocess\nsubprocess.run(['tool'], shell=True)"):
                    blocking, _ = preflight.scan_python_source('probe.py', source, scope, profile)
                    self.assertTrue(blocking, (profile, scope, source))
                blocking, _ = preflight.scan_javascript_source(
                    'probe.js', "const cp = require('child_process'); cp.exec(userInput);", scope, profile)
                self.assertTrue(blocking, (profile, scope))

    def test_dangerous_python_shell_call_is_rejected(self):
        source = "import os\nos.system('echo danger')\n"
        path = self.variant('danger-python.zip', self.add_member(PREFIX + 'tests/runtime_fixture.py', source))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('CODE_EXECUTION', codes(report))
        self.assertTrue(any(item['kind'] == 'PYTHON_SHELL_EXECUTION' for item in report['code_execution']['findings']))

    def test_dangerous_javascript_call_is_rejected(self):
        source = 'const cp = require("child_process");\ncp.exec("echo danger");\n'
        path = self.variant('danger-js.zip', self.add_member(PREFIX + 'tests/runtime_fixture.js', source))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('CODE_EXECUTION', codes(report))
        self.assertTrue(any(item['kind'] == 'CHILD_PROCESS_EXEC' for item in report['code_execution']['findings']))

    def test_shell_true_and_string_commands_are_rejected(self):
        source = ('import subprocess\nsubprocess.run("echo danger", shell=True)\n')
        path = self.variant('danger-shell.zip', self.add_member(PREFIX + 'tests/runtime_shell.py', source))
        report = preflight.preflight(path)
        self.assertEqual(report['status'], 'FAIL')
        kinds = {item['kind'] for item in report['code_execution']['findings']}
        self.assertIn('SHELL_TRUE', kinds)
        self.assertIn('STRING_COMMAND', kinds)

    def test_inert_strings_comments_and_escaped_regexes_pass(self):
        inert_python = ('# inert comment only\ntext = "os.system"\npattern = "subprocess"\ndoc = """child_process.exec"""\n')
        inert_js = ('const text = "child_" + "pro" + "cess." + "ex" + "ec";\nconst commentLike = "she" + "ll: true";\nconst escaped = /child_process\\.ex\\s*ec\\(/;\n')
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
            version = json.loads((ROOT / 'package.json').read_text())['version']
            changed = data.replace(f'version: "{version}"'.encode(), b'version: "9.9.9"')
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
                                                          'cp.exec("echo danger");\n'))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/security_preflight.py'), str(bad)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('CODE_EXECUTION', result.stderr)


if __name__ == '__main__':
    unittest.main()
