#!/usr/bin/env python3
"""Acceptance for an installed candidate runtime against the locked v1.3.1 runtime.

This is a Source-only harness. The Source tree supplies JSON Spec, plan and
data files as ordinary input. The harness then executes each installed
runtime's own documented production CLIs with fixed argv in that runtime root.
It never imports developer or release tools from an installed root and never
injects a developer code overlay into it; the installed package must remain
self-contained. Native PPTX parts, scene JSON, QA JSON, rendered pixels,
reasoning reports and analytics data are compared with the existing
capability_parity functions.

The baseline must be the locked v1.3.1 Runtime ZIP. Versions and the baseline
SHA256 are fixed by CAPABILITY_PARITY_V1_3_1_TO_V1_3_2; callers cannot supply
alternative versions or hashes.

All Spec/PPTX/scene/QA/log/render/Montage evidence is retained under an
explicit fresh artifact directory, including when a case fails. Commands are
run with their raw stdout/stderr written to that directory.
"""

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import date
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import capability_parity as parity  # noqa: E402

CONTRACT_NAME = parity.CAPABILITY_PARITY_V1_3_1_TO_V1_3_2
CONTRACT = parity.CONTRACTS[CONTRACT_NAME]
SOURCE_ONLY_MEMBERS = (
    'scripts/package_runtime.py',
    'scripts/security_preflight.py',
    'skill/reasoning/fixtures/hostile-source/plan.json',
    'skill/reasoning/fixtures/hostile-source/sources/hostile.md',
)
RUNTIME_PRODUCTION_COMMANDS = ('test', 'test:core', 'validate:all')
SPEC_CASES = (
    {'name': 'q4-generated', 'kind': 'source-generated-spec'},
    {'name': 'executive-review', 'kind': 'source-provided-spec'},
)

MATRIX_SOURCE = 'skill/examples/v1.3/matrix-cases.json'
MATRIX_THEMES = {'light': 'executive-dense', 'dark': 'dark-executive'}
MATRIX_FAMILIES = ('bar', 'column', 'line', 'area', 'pie', 'doughnut')
MATRIX_ACCEPTED_PER_THEME = 36
MATRIX_REJECTED_PER_THEME = 12
MATRIX_REJECTION_PATTERNS = {
    'CATEGORY_PALETTE_CAPACITY': re.compile(r'category palette exceeds 8 distinguishable colors'),
    'PIE_SINGLE_SERIES': re.compile(r'pie/doughnut requires exactly one series'),
    'PIE_NONNEGATIVE': re.compile(r'pie/doughnut requires nonnegative values'),
    'PIE_MISSING': re.compile(r'pie/doughnut does not support missing values'),
    'AREA_MISSING': re.compile(r'area charts cannot render missing values honestly[\s\S]*'
                               r'line chart[\s\S]*table'),
    'AREA_SINGLE_POINT': re.compile(r'area charts require at least two points[\s\S]*'
                                    r'line chart[\s\S]*KPI[\s\S]*table'),
}
EXPECTED_NATIVE_KIND = {
    'bar': ('barChart', 'bar'),
    'column': ('barChart', 'col'),
    'line': ('lineChart', None),
    'area': ('areaChart', None),
    'pie': ('pieChart', None),
    'doughnut': ('doughnutChart', None),
}

MULTIMODAL_SOURCE = 'skill/examples/multimodal-integration.json'
MULTIMODAL_MIN_EMBEDDED_IMAGES = 9

ANALYTICS_RECIPES = ('business-performance', 'project-analytics', 'sales-conversion')
ANALYTICS_SOURCE = 'skill/examples/v1.3/inputs/{recipe}.json'

REASONING_PLANS = ('q4-six-actions', 'multimodal-consolidation',
                   'executive-incomplete-business')
REASONING_SOURCE = 'skill/reasoning/fixtures/{plan}/plan.json'
REASONING_REQUIRED_SLIDES = {
    'q4-six-actions': ('roadmap', 'risk'),
    'multimodal-consolidation': ('image-hero', 'document-evidence'),
    'executive-incomplete-business': ('kpi-dashboard', 'table'),
}

RELATIONSHIP_SOURCE = 'skill/examples/v1.3/relationships-deck.json'
RELATIONSHIP_CASES = (
    ('dated-timeline', 0),
    ('dated-timeline-close', 1),
    ('branch-swimlane', 2),
    ('roadmap', 3),
)
RELATIONSHIP_THEMES = (('light', 'executive-clean'), ('dark', 'dark-executive'))
RELATIONSHIP_REQUIRED = {
    'dated-timeline': {'markers': 5, 'min_dates': 5, 'min_durations': 1},
    'dated-timeline-close': {'markers': 3, 'min_label_lanes': 2},
    'branch-swimlane': {'task_nodes': 5, 'decision_edges': 4, 'dependencies': 4},
    'roadmap': {'lane_headings': ['研究', '产品', '运营']},
}

ARTIFACT_MARKER = '.goujian-runtime-acceptance-artifacts'
ARTIFACT_MARKER_TEXT = 'goujian-runtime-acceptance-artifacts\n'

CHART_TAG_RE = re.compile(r'<c:(barChart|lineChart|areaChart|pieChart|doughnutChart)[ />]')
CHART_POINT_RE = re.compile(r'<c:pt\b[^>]*\bidx="(\d+)"[^>]*>(.*?)</c:pt>', re.S)
CHART_VALUE_RE = re.compile(r'<c:v>(.*?)</c:v>', re.S)
CHART_SERIES_RE = re.compile(r'<c:ser>(.*?)</c:ser>', re.S)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_generated_json(path, failures, label):
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f'{label} is unreadable: {error}')
        return None


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8')


def version_from_skill(path):
    text = Path(path).read_text(encoding='utf-8')
    match = re.search(r'^  version: "([^"]+)"$', text, flags=re.MULTILINE)
    return match.group(1) if match else None


def inside(path, root):
    path = Path(path).resolve()
    root = Path(root).resolve()
    return path == root or root in path.parents


def sanitize(text, roots):
    for root in sorted((str(Path(root)) for root in roots), key=len, reverse=True):
        text = text.replace(root, '<ROOT>')
        resolved = str(Path(root).resolve())
        if resolved != root:
            text = text.replace(resolved, '<ROOT>')
    return text


def sanitize_value(value, roots):
    if isinstance(value, str):
        return sanitize(value, roots)
    if isinstance(value, list):
        return [sanitize_value(item, roots) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_value(item, roots) for key, item in value.items()}
    return value


def contract_rule(name):
    if name != CONTRACT_NAME:
        raise ValueError(f'unsupported contract {name!r}; only {CONTRACT_NAME} is accepted')
    return CONTRACT


def dependency_versions(lock_path):
    lock_path = Path(lock_path)
    if not lock_path.is_file():
        return {}
    data = read_json(lock_path)
    packages = data.get('packages') or {}
    versions = {}
    for name, package in packages.items():
        if not name:
            continue
        version = package.get('version') if isinstance(package, dict) else None
        if version:
            versions[name] = version
    return versions


def module_evidence(role, root, fallback):
    """Prove dependency provenance. A candidate may never fall back to Source."""
    root = Path(root)
    expected = dependency_versions(root / 'package-lock.json')

    def describe(path, source, owned):
        path = Path(path)
        installed = dependency_versions(path / '.package-lock.json')
        matches = bool(installed) and installed == expected
        return {
            'status': 'PASS' if matches else 'FAIL',
            'source': source,
            'owned': owned,
            'dependencies_match_lock': matches,
            'dependency_count': len(expected),
            'installed_lock_sha256':
                sha256_file(path / '.package-lock.json')
                if (path / '.package-lock.json').is_file() else None,
            'expected_lock_sha256':
                sha256_file(root / 'package-lock.json')
                if (root / 'package-lock.json').is_file() else None,
            'failures': [] if matches else [
                'installed dependency versions do not match package-lock.json'],
        }

    local = root / 'node_modules'
    if local.is_symlink():
        evidence = describe(local, 'symlink', False)
        evidence['path'] = '<LINKED-NODE-MODULES>'
        if role == 'candidate':
            evidence['status'] = 'FAIL'
            evidence.setdefault('failures', []).append(
                'candidate must own a real installed node_modules; a symlink is not an install')
        else:
            evidence['provenance'] = {
                'kind': 'symlink',
                'rule': 'linked dependencies must still match the root package-lock versions',
            }
        return evidence
    if local.is_dir():
        evidence = describe(local, 'root-owned', True)
        evidence['path'] = '<ROOT-NODE-MODULES>'
        return evidence
    if role == 'candidate':
        return {
            'status': 'FAIL',
            'source': 'missing',
            'owned': False,
            'dependencies_match_lock': False,
            'path': None,
            'failures': ['candidate must use its own installed node_modules; '
                         'a Source fallback is not allowed'],
        }
    if fallback and Path(fallback).is_dir():
        evidence = describe(fallback, 'lock-matched-fallback', False)
        evidence['path'] = '<FALLBACK-NODE-MODULES>'
        evidence['provenance'] = {
            'fallback': '<FALLBACK-NODE-MODULES>',
            'expected_lock': '<ROOT>/package-lock.json',
            'rule': 'fallback dependency versions must equal the root package-lock versions',
        }
        return evidence
    return {
        'status': 'FAIL',
        'source': 'missing',
        'owned': False,
        'dependencies_match_lock': False,
        'path': None,
        'failures': [f'{role} has no node_modules and no fallback was provided'],
    }


def candidate_runtime_evidence(root):
    root = Path(root)
    failures = []
    package_path = root / 'package.json'
    skill_path = root / 'SKILL.md'
    manifest_path = root / 'distribution/runtime-manifest.json'
    mapping_path = root / 'distribution/runtime-package.json'
    for path in (package_path, skill_path, manifest_path, mapping_path):
        if not path.is_file():
            failures.append(f'missing candidate member {path.relative_to(root).as_posix()}')
    if failures:
        return {'status': 'FAIL', 'failures': failures}
    package = read_json(package_path)
    manifest = read_json(manifest_path)
    files = manifest.get('runtime_files') or []
    omitted = set(manifest.get('omitted_commands') or [])
    scripts = package.get('scripts') or {}
    expected = {
        'package.json version': (package.get('version'), CONTRACT['candidate_version']),
        'SKILL.md version': (version_from_skill(skill_path), CONTRACT['candidate_version']),
        'manifest schema_version': (manifest.get('schema_version'), CONTRACT['candidate_version']),
        'manifest distribution': (manifest.get('distribution'), 'runtime'),
        'manifest declared files': (len(files), 185),
        'manifest unique files': (len(set(files)), 185),
    }
    for label, (actual, wanted) in expected.items():
        if actual != wanted:
            failures.append(f'{label} is {actual!r}, expected {wanted!r}')
    for command in ('package', 'preflight'):
        if command not in omitted:
            failures.append(f'candidate manifest does not omit {command}')
        if command in scripts:
            failures.append(f'candidate package.json still exposes {command}')
    for command in RUNTIME_PRODUCTION_COMMANDS:
        if command not in scripts:
            failures.append(f'candidate package.json is missing {command}')
    for relative in SOURCE_ONLY_MEMBERS:
        if relative in files:
            failures.append(f'candidate manifest still declares {relative}')
        if (root / relative).exists():
            failures.append(f'candidate runtime still contains {relative}')
    for relative in files:
        target = root / relative
        if not target.is_file():
            failures.append(f'candidate member is missing: {relative}')
        elif target.is_symlink():
            failures.append(f'candidate member is a symlink: {relative}')
    if package_path.read_bytes() != mapping_path.read_bytes():
        failures.append('candidate package.json differs from distribution/runtime-package.json')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'version': package.get('version'),
        'declared_runtime_files': len(files),
        'source_only_members_absent': not any(
            relative in files or (root / relative).exists() for relative in SOURCE_ONLY_MEMBERS),
        'omitted_commands': sorted(omitted),
        'production_commands': list(RUNTIME_PRODUCTION_COMMANDS),
    }


def baseline_runtime_evidence(zip_path, root, contract):
    root = Path(root)
    failures = []
    evidence = parity.baseline_archive_evidence(
        zip_path, root, locked_sha256=contract['locked_baseline_zip_sha256'])
    if evidence.get('status') != 'PASS':
        failures.append('locked v1.3.1 baseline archive/tree identity failed')
    if not evidence.get('locked_zip_verified'):
        return {'status': 'FAIL', 'failures': failures, 'version': None,
                'archive': evidence, 'symlinks': []}
    package_path = root / 'package.json'
    skill_path = root / 'SKILL.md'
    for path in (package_path, skill_path):
        if not path.is_file():
            failures.append(f'missing baseline member {path.relative_to(root).as_posix()}')
    version = read_json(package_path).get('version') if package_path.is_file() else None
    skill_version = version_from_skill(skill_path) if skill_path.is_file() else None
    if version != contract['baseline_version']:
        failures.append(f'baseline version is {version!r}, expected {contract["baseline_version"]!r}')
    if skill_version != contract['baseline_version']:
        failures.append(f'baseline SKILL version is {skill_version!r}')
    symlinks = []
    prefix = (evidence.get('package_root_prefix') or '').rstrip('/')
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = [name for name in archive.namelist() if not name.endswith('/')]
    except (OSError, zipfile.BadZipFile):
        names = []
    if not prefix and names:
        prefix = names[0].split('/', 1)[0]
    declared = {name[len(prefix) + 1:] for name in names
                if prefix and name.startswith(prefix + '/')}
    for relative in sorted(declared):
        if (root / relative).is_symlink():
            symlinks.append(relative)
    if symlinks:
        failures.append(f'baseline archive members are symlinks: {symlinks[:3]}')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'version': version,
        'archive': evidence,
        'symlinks': symlinks[:12],
    }


def source_evidence(root, contract):
    root = Path(root)
    failures = []
    package = read_json(root / 'package.json')
    if package.get('version') != contract['candidate_version']:
        failures.append(f'source version is {package.get("version")!r}')
    if version_from_skill(root / 'SKILL.md') != contract['candidate_version']:
        failures.append('source SKILL version differs')
    for relative in SOURCE_ONLY_MEMBERS:
        if not (root / relative).is_file():
            failures.append(f'source is missing {relative}')
    return {'status': 'PASS' if not failures else 'FAIL', 'failures': failures}


def prepare_artifact_root(path, source_root, runtime_root, baseline_root):
    """Return a fresh evidence directory without deleting or overwriting data."""
    if path is None:
        root = Path(tempfile.mkdtemp(prefix='goujian-runtime-acceptance-artifacts-'))
        (root / ARTIFACT_MARKER).write_text(ARTIFACT_MARKER_TEXT, encoding='utf-8')
        return root
    root = Path(path).resolve()
    for protected in (runtime_root, baseline_root):
        if inside(root, protected) or inside(protected, root):
            raise SystemExit(f'refusing artifact directory that overlaps {protected}')
    allowed = Path(source_root).resolve() / 'out'
    if inside(root, source_root) and not inside(root, allowed):
        raise SystemExit('artifact directory inside Source is allowed only under Source/out')
    if root.exists():
        data = [entry for entry in root.iterdir() if entry.name != ARTIFACT_MARKER]
        if data:
            raise SystemExit('artifact directory must be new or empty; '
                             'refusing to overwrite previous evidence')
        marker = root / ARTIFACT_MARKER
        if marker.exists() and marker.read_text(encoding='utf-8') != ARTIFACT_MARKER_TEXT:
            raise SystemExit('artifact directory marker does not match this harness')
    root.mkdir(parents=True, exist_ok=True)
    (root / ARTIFACT_MARKER).write_text(ARTIFACT_MARKER_TEXT, encoding='utf-8')
    return root


def artifact_manifest(root):
    root = Path(root)
    rows = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.name == ARTIFACT_MARKER or path.name == 'result.json':
            continue
        relative = path.relative_to(root).as_posix()
        rows.append({'path': relative, 'bytes': path.stat().st_size,
                     'sha256': sha256_file(path)})
    payload = '\n'.join(f"{row['sha256']}  {row['path']}" for row in rows) + '\n'
    return rows, sha256_bytes(payload.encode('utf-8'))


def _safe_label(label):
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', label)


def run_command(root, argv, node_modules, roots, label, log_dir=None, timeout=900):
    environment = os.environ.copy()
    environment['PATH'] = str(Path(sys.executable).parent) + os.pathsep + environment.get('PATH', '')
    if node_modules:
        environment['NODE_PATH'] = str(node_modules)
    started = time.time()
    record = {
        'label': label,
        'argv': sanitize_value([str(item) for item in argv], roots),
        'cwd': '<ROOT>',
        'exit': None,
        'duration_seconds': None,
        'timed_out': False,
        'stdout_tail': '',
        'stderr_tail': '',
    }
    stdout = ''
    stderr = ''
    try:
        result = subprocess.run(argv, cwd=str(root), env=environment, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout)
        record['exit'] = result.returncode
        stdout = result.stdout or ''
        stderr = result.stderr or ''
    except subprocess.TimeoutExpired as error:
        record['timed_out'] = True
        stdout = error.stdout or ''
        stderr = error.stderr or ''
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', 'replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', 'replace')
        stderr = (stderr + f'\nTIMEOUT after {timeout}s').strip()
    except OSError as error:
        stderr = f'command could not start: {error}'
    record['duration_seconds'] = round(time.time() - started, 3)
    record['stdout_tail'] = sanitize(stdout[-2000:], roots)
    record['stderr_tail'] = sanitize(stderr[-2000:], roots)
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        safe = _safe_label(label)
        names = {'command': f'{safe}.command.json',
                 'stdout': f'{safe}.stdout.txt',
                 'stderr': f'{safe}.stderr.txt'}
        write_json(log_dir / names['command'], record)
        (log_dir / names['stdout']).write_text(sanitize(stdout, roots), encoding='utf-8')
        (log_dir / names['stderr']).write_text(sanitize(stderr, roots), encoding='utf-8')
        record['logs'] = {'directory': 'logs', **names}
    return record


def resolve_node_modules(root, fallback):
    """Kept for compatibility; this only reports a local directory."""
    local = Path(root) / 'node_modules'
    if local.is_dir():
        return local
    if fallback and Path(fallback).is_dir():
        return Path(fallback)
    return None


def node_binary():
    return shutil.which('node') or 'node'


def command_failed(command):
    return command.get('exit') != 0 or command.get('timed_out')


def combined_output(command):
    return (command.get('stdout_tail') or '') + '\n' + (command.get('stderr_tail') or '')


def count_pngs(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.rglob('*.png') if path.is_file())


def generate_source_spec(source_root, work, node_modules, roots, log_dir):
    source_out = Path(work) / 'source-harness'
    source_out.mkdir(parents=True, exist_ok=True)
    plan = Path(source_root) / 'skill/reasoning/fixtures/q4-six-actions/plan.json'
    spec = source_out / 'q4.spec.json'
    pptx = source_out / 'source-q4.pptx'
    argv = [node_binary(), 'skill/scripts/compile_plan.js', str(plan),
            '--out', str(pptx), '--spec-out', str(spec)]
    command = run_command(source_root, argv, node_modules, roots,
                          'source-generate-q4-spec', log_dir)
    ok = command.get('exit') == 0 and spec.is_file()
    return {
        'status': 'PASS' if ok else 'FAIL',
        'kind': 'source-generated-spec',
        'plan': {'path': 'skill/reasoning/fixtures/q4-six-actions/plan.json',
                 'sha256': sha256_file(plan) if plan.is_file() else None},
        'generated_spec': {'sha256': sha256_file(spec) if spec.is_file() else None},
        'command': command,
    }, spec


def spec_cases(source_root, generated_spec, roots):
    cases = []
    for definition in SPEC_CASES:
        if definition['name'] == 'q4-generated':
            path = Path(generated_spec)
            origin = 'skill/reasoning/fixtures/q4-six-actions/plan.json'
        else:
            path = Path(source_root) / 'skill/examples/executive-review.json'
            origin = 'skill/examples/executive-review.json'
        cases.append({
            'name': definition['name'],
            'kind': definition['kind'],
            'path': path,
            'origin': origin,
            'sha256': sha256_file(path) if path.is_file() else None,
        })
    return cases


def run_spec_case(side, root, node_modules, spec_case, work, roots, log_dir):
    label = f'{side}-{spec_case["name"]}'
    out = Path(work) / 'cases' / side / spec_case['name']
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    qa_json = out / 'qa.json'
    qa_render = out / 'qa-render'
    render = out / 'render'
    scene = Path(str(pptx) + '.scene.json')
    commands = []
    failures = []
    build = run_command(
        root, [node_binary(), 'skill/scripts/build_deck.js', str(spec_case['path']), str(pptx)],
        node_modules, roots, f'{label}-build', log_dir)
    commands.append(build)
    if command_failed(build):
        failures.append(f'{label} build exited {build.get("exit")}')
    if not pptx.is_file():
        failures.append(f'{label} PPTX missing')
    quality = None
    if pptx.is_file():
        qa = run_command(
            root, [sys.executable, 'skill/scripts/quality_gate.py', str(pptx),
                   '--spec', str(spec_case['path']), '--out', str(qa_json),
                   '--render-dir', str(qa_render)],
            node_modules, roots, f'{label}-qa', log_dir, timeout=1800)
        commands.append(qa)
        if command_failed(qa):
            failures.append(f'{label} QA exited {qa.get("exit")}')
        rendering = run_command(
            root, [sys.executable, 'skill/scripts/render_deck.py', str(pptx), str(render)],
            node_modules, roots, f'{label}-render', log_dir, timeout=1800)
        commands.append(rendering)
        if command_failed(rendering):
            failures.append(f'{label} render exited {rendering.get("exit")}')
    else:
        commands.append({'label': f'{label}-qa', 'exit': None, 'skipped': 'PPTX missing'})
        commands.append({'label': f'{label}-render', 'exit': None, 'skipped': 'PPTX missing'})
    if not scene.is_file():
        failures.append(f'{label} scene missing')
    if qa_json.is_file():
        quality = read_generated_json(qa_json, failures, f'{label} QA JSON')
        if quality is not None:
            if quality.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
                failures.append(f'{label} QA status is {quality.get("status")!r}')
            if quality.get('VISUAL_QA') != 'NOT_RUN':
                failures.append(f'{label} QA VISUAL_QA is {quality.get("VISUAL_QA")!r}')
    else:
        failures.append(f'{label} QA JSON missing')
    for directory, name in ((qa_render, 'QA render'), (render, 'render')):
        if count_pngs(directory) == 0:
            failures.append(f'{label} {name} produced no PNG')
    measurement = parity.title_measurement_evidence(scene) if scene.is_file() else {
        'status': 'FAIL', 'reason': 'scene missing'}
    if measurement.get('status') != 'PASS':
        failures.append(f'{label} title measurement is not real Pillow evidence')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'commands': commands,
        'artifacts': {
            'pptx': str(pptx),
            'scene': str(scene),
            'qa_json': str(qa_json),
            'qa_semantic_json': str(out / 'qa.semantic-qa.json'),
            'qa_render': str(qa_render),
            'render': str(render),
        },
        'qa_status': quality.get('status') if quality else None,
        'title_measurement': measurement,
    }


def validate_matrix_fixture(fixture):
    failures = []
    cells = fixture.get('cells') if isinstance(fixture, dict) else None
    if not isinstance(cells, list):
        return {'status': 'FAIL', 'failures': ['matrix fixture has no cells list']}
    accepted = [cell for cell in cells if cell.get('expected') == 'ACCEPT']
    rejected = [cell for cell in cells if cell.get('expected') == 'REJECT']
    if len(cells) != 96:
        failures.append(f'matrix has {len(cells)} cells, expected 96')
    if len(accepted) != 72:
        failures.append(f'matrix has {len(accepted)} accepted cells, expected 72')
    if len(rejected) != 24:
        failures.append(f'matrix has {len(rejected)} rejected cells, expected 24')
    families = sorted({cell.get('family') for cell in cells})
    if families != sorted(MATRIX_FAMILIES):
        failures.append(f'matrix families are {families}')
    themes = set(fixture.get('themes') or {})
    if themes != set(MATRIX_THEMES):
        failures.append(f'matrix themes are {sorted(themes)}')
    for theme in MATRIX_THEMES:
        theme_cells = [cell for cell in cells if cell.get('theme') == theme]
        theme_accepted = [cell for cell in theme_cells if cell.get('expected') == 'ACCEPT']
        theme_rejected = [cell for cell in theme_cells if cell.get('expected') == 'REJECT']
        if len(theme_accepted) != MATRIX_ACCEPTED_PER_THEME:
            failures.append(f'{theme} has {len(theme_accepted)} accepted cells')
        if len(theme_rejected) != MATRIX_REJECTED_PER_THEME:
            failures.append(f'{theme} has {len(theme_rejected)} rejected cells')
    for cell in rejected:
        rejection = cell.get('rejection') or {}
        code = rejection.get('code')
        if code not in MATRIX_REJECTION_PATTERNS:
            failures.append(f'{cell.get("id")} has unknown rejection code {code!r}')
        elif not rejection.get('reason'):
            failures.append(f'{cell.get("id")} has no rejection reason')
    required_keys = {'id', 'family', 'theme', 'case', 'expected', 'chartType', 'labels',
                     'unit', 'numberFormat', 'series', 'visual_encoding'}
    for cell in cells:
        missing = sorted(required_keys - set(cell))
        if missing:
            failures.append(f'{cell.get("id")} is missing {missing}')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'cells': len(cells),
        'accepted': len(accepted),
        'rejected': len(rejected),
        'families': families,
        'themes': sorted(themes),
        'accepted_per_theme': {theme: sum(
            1 for cell in accepted if cell.get('theme') == theme) for theme in MATRIX_THEMES},
        'rejected_per_theme': {theme: sum(
            1 for cell in rejected if cell.get('theme') == theme) for theme in MATRIX_THEMES},
        'failures': failures,
    }


def matrix_accepted_cells(fixture, theme):
    return [cell for cell in fixture['cells']
            if cell.get('theme') == theme and cell.get('expected') == 'ACCEPT']


def matrix_deck_spec(fixture, theme):
    cells = matrix_accepted_cells(fixture, theme)
    slides = []
    for cell in cells:
        pie_like = cell['family'] in ('pie', 'doughnut')
        slide = {
            'type': 'chart',
            'chartType': cell['chartType'],
            'title': f"{cell['title']}（{cell['id']}）",
            'labels': cell['labels'],
            'unit': cell['unit'],
            'numberFormat': ('0.0%' if cell['case'] == 'percentage' else '0%')
            if pie_like else cell['numberFormat'],
            'series': cell['series'],
            'visual_encoding': cell['visual_encoding'],
            'source': 'V1.3 matrix fixture（合成）',
        }
        if cell.get('missing_policy'):
            slide['missing_policy'] = cell['missing_policy']
        slides.append(slide)
    spec = {
        'schema_version': '1.3',
        'title': f'V1.3 native chart matrix · {theme}',
        'profile': MATRIX_THEMES[theme],
        'lang': 'zh-CN',
        'slides': slides,
    }
    return spec, cells


def matrix_rejection_spec(fixture, cell):
    spec = {
        'schema_version': '1.3',
        'title': f"Reject {cell['id']}",
        'profile': MATRIX_THEMES[cell['theme']],
        'lang': 'zh-CN',
        'slides': [{
            'type': 'chart',
            'chartType': cell['chartType'],
            'title': cell['title'],
            'labels': cell['labels'],
            'unit': cell['unit'],
            'numberFormat': cell['numberFormat'],
            'series': cell['series'],
            'visual_encoding': cell['visual_encoding'],
        }],
    }
    if cell.get('missing_policy'):
        spec['slides'][0]['missing_policy'] = cell['missing_policy']
    return spec


def _points(block):
    match = re.search(
        r'<c:(?:strCache|numCache|multiLvlStrCache)>(.*?)</c:(?:strCache|numCache|multiLvlStrCache)>',
        block, re.S)
    if not match:
        return []
    points = {}
    for index, body in CHART_POINT_RE.findall(match.group(1)):
        value = CHART_VALUE_RE.search(body)
        points[int(index)] = unescape(value.group(1)) if value else ''
    if not points:
        return []
    return [points.get(index, '') for index in range(max(points) + 1)]


def _chart_series(xml):
    series = []
    for body in CHART_SERIES_RE.findall(xml):
        name_block = re.search(r'<c:tx>(.*?)</c:tx>', body, re.S)
        name = _points(name_block.group(1))[0] if name_block else None
        cat_block = re.search(r'<c:cat>(.*?)</c:cat>', body, re.S)
        labels = _points(cat_block.group(1)) if cat_block else []
        val_block = re.search(r'<c:val>(.*?)</c:val>', body, re.S)
        raw_values = _points(val_block.group(1)) if val_block else []
        values = []
        for item in raw_values:
            if item == '':
                values.append(None)
            else:
                try:
                    values.append(float(item))
                except ValueError:
                    values.append(item)
        series.append({'name': name, 'labels': labels, 'values': values})
    return series


def _chart_part_for_slide(archive, index):
    rels_name = f'ppt/slides/_rels/slide{index}.xml.rels'
    names = set(archive.namelist())
    if rels_name not in names:
        return None
    text = archive.read(rels_name).decode('utf-8', 'replace')
    match = re.search(r'Type="[^"]*/chart"[^>]*Target="([^"]+)"', text)
    if not match:
        match = re.search(r'Target="([^"]+)"[^>]*Type="[^"]*/chart"', text)
    if not match:
        return None
    target = match.group(1)
    if target.startswith('/'):
        return target.lstrip('/')
    return posixpath.normpath(posixpath.join('ppt/slides', target))


def _numeric(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def matrix_expected(cell):
    """Return the flat native expectation for one accepted matrix cell.

    The fixture readback is authoritative where present (it records the
    storage-scale conversion); otherwise the cell series definition is used.
    """
    series = cell.get('series') or []
    readback = cell.get('readback')
    expected_values = [v for item in series for v in (item.get('values') or [])]
    labels = list(cell.get('labels') or [])
    names = [item.get('name') for item in series]
    if isinstance(readback, dict):
        if isinstance(readback.get('values'), list):
            expected_values = list(readback['values'])
        if isinstance(readback.get('labels'), list):
            labels = list(readback['labels'])
        if isinstance(readback.get('series_names'), list):
            names = list(readback['series_names'])
    return [_numeric(item) for item in expected_values], labels, names


def verify_matrix_pptx(pptx, cells):
    failures = []
    families = {}
    charts_checked = 0
    try:
        archive = zipfile.ZipFile(pptx)
    except (OSError, zipfile.BadZipFile) as error:
        return {'status': 'FAIL', 'failures': [f'PPTX is unreadable: {error}'],
                'charts': 0, 'families': {}}
    with archive:
        chart_parts = [name for name in archive.namelist()
                       if re.match(r'ppt/charts/chart\d+\.xml$', name)]
        if len(chart_parts) != len(cells):
            failures.append(f'{len(chart_parts)} native charts for {len(cells)} accepted cells')
        for index, cell in enumerate(cells, start=1):
            part = _chart_part_for_slide(archive, index)
            if not part or part not in archive.namelist():
                failures.append(f'{cell["id"]} has no native chart part')
                continue
            xml = archive.read(part).decode('utf-8', 'replace')
            tag = CHART_TAG_RE.search(xml)
            kind = tag.group(1) if tag else None
            expected_kind, expected_dir = EXPECTED_NATIVE_KIND[cell['family']]
            if kind != expected_kind:
                failures.append(f'{cell["id"]} chart is {kind}, expected {expected_kind}')
            bar_dir = re.search(r'<c:barDir val="([^"]+)"', xml)
            if expected_dir and (not bar_dir or bar_dir.group(1) != expected_dir):
                failures.append(f'{cell["id"]} bar direction is '
                                f'{bar_dir.group(1) if bar_dir else None}, expected {expected_dir}')
            series = _chart_series(xml)
            expected_values, expected_labels, expected_names = matrix_expected(cell)
            if len(series) != len(cell['series']):
                failures.append(f'{cell["id"]} has {len(series)} series')
            native_flat = [_numeric(item) for row in series for item in row['values']]
            if native_flat != expected_values:
                failures.append(f'{cell["id"]} native values {native_flat!r} '
                                f'!= {expected_values!r}')
            offset = 0
            for series_index, item in enumerate(series):
                width = len((cell['series'][series_index].get('values') or [])) \
                    if series_index < len(cell['series']) else 0
                segment = expected_values[offset:offset + width]
                offset += width
                if [_numeric(value) for value in item['values']] != segment:
                    failures.append(f'{cell["id"]} series {series_index + 1} values differ')
                if item['labels'] != expected_labels:
                    failures.append(f'{cell["id"]} series {series_index + 1} labels '
                                    f'{item["labels"]!r} != {expected_labels!r}')
                expected_name = expected_names[series_index] \
                    if series_index < len(expected_names) else None
                if item['name'] != expected_name:
                    failures.append(f'{cell["id"]} series {series_index + 1} name '
                                    f'{item["name"]!r} != {expected_name!r}')
            formats = (re.findall(r'<c:formatCode>(.*?)</c:formatCode>', xml)
                       + re.findall(r'<c:numFmt[^>]*formatCode="([^"]*)"', xml))
            formats = [unescape(item) for item in formats]
            if cell['case'] == 'percentage' and not any('%' in item for item in formats):
                failures.append(f'{cell["id"]} percentage chart has no % number format')
            blanks = re.search(r'<c:dispBlanksAs val="([^"]+)"', xml)
            if cell['case'] == 'missing':
                if not blanks or blanks.group(1) != 'gap':
                    failures.append(f'{cell["id"]} missing values are not plotted as gaps')
                if None not in expected_values:
                    failures.append(f'{cell["id"]} missing case has no null value')
            families[cell['family']] = families.get(cell['family'], 0) + 1
            charts_checked += 1
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'charts': charts_checked,
        'families': families,
        'failures': failures,
    }


def run_matrix_deck(side, root, node_modules, spec_case, cells, work, roots, log_dir):
    label = f'{side}-{spec_case["name"]}'
    out = Path(work) / 'cases' / side / spec_case['name']
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    scene = Path(str(pptx) + '.scene.json')
    qa_json = out / 'qa.json'
    qa_render = out / 'qa-render'
    commands = []
    failures = []
    build = run_command(
        root, [node_binary(), 'skill/scripts/build_deck.js', str(spec_case['path']), str(pptx)],
        node_modules, roots, f'{label}-build', log_dir, timeout=1800)
    commands.append(build)
    if command_failed(build):
        failures.append(f'{label} build exited {build.get("exit")}')
    if not pptx.is_file():
        failures.append(f'{label} PPTX missing')
    quality = None
    if pptx.is_file():
        qa = run_command(
            root, [sys.executable, 'skill/scripts/quality_gate.py', str(pptx),
                   '--spec', str(spec_case['path']), '--out', str(qa_json),
                   '--render-dir', str(qa_render)],
            node_modules, roots, f'{label}-qa', log_dir, timeout=2400)
        commands.append(qa)
        if command_failed(qa):
            failures.append(f'{label} QA exited {qa.get("exit")}')
    else:
        commands.append({'label': f'{label}-qa', 'exit': None, 'skipped': 'PPTX missing'})
    if not scene.is_file():
        failures.append(f'{label} scene missing')
    if qa_json.is_file():
        quality = read_generated_json(qa_json, failures, f'{label} QA JSON')
        if quality is not None:
            if quality.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
                failures.append(f'{label} QA status is {quality.get("status")!r}')
            if quality.get('VISUAL_QA') != 'NOT_RUN':
                failures.append(f'{label} QA VISUAL_QA is {quality.get("VISUAL_QA")!r}')
    else:
        failures.append(f'{label} QA JSON missing')
    expected_pages = len(cells) + 1  # title slide plus one page per accepted cell
    if count_pngs(qa_render) != expected_pages:
        failures.append(f'{label} QA render has {count_pngs(qa_render)} pages for '
                        f'{expected_pages} expected (title plus {len(cells)} cells)')
    measurement = parity.title_measurement_evidence(scene) if scene.is_file() else {
        'status': 'FAIL', 'reason': 'scene missing'}
    if measurement.get('status') != 'PASS':
        failures.append(f'{label} title measurement is not real Pillow evidence')
    native = verify_matrix_pptx(pptx, cells) if pptx.is_file() else {
        'status': 'FAIL', 'failures': ['PPTX missing'], 'charts': 0, 'families': {}}
    if native.get('status') != 'PASS':
        failures.extend(f'{label} {item}' for item in native['failures'])
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'commands': commands,
        'artifacts': {
            'pptx': str(pptx),
            'scene': str(scene),
            'qa_json': str(qa_json),
            'qa_semantic_json': str(out / 'qa.semantic-qa.json'),
            'qa_render': str(qa_render),
        },
        'qa_status': quality.get('status') if quality else None,
        'title_measurement': measurement,
        'native': native,
        'accepted_cells': len(cells),
    }


def run_matrix_rejection(side, root, node_modules, cell, spec_path, work, roots, log_dir):
    label = f'{side}-reject-{cell["id"]}'
    out = Path(work) / 'cases' / side / 'rejections' / cell['id']
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    command = run_command(
        root, [node_binary(), 'skill/scripts/build_deck.js', str(spec_path), str(pptx)],
        node_modules, roots, label, log_dir, timeout=300)
    code = (cell.get('rejection') or {}).get('code')
    pattern = MATRIX_REJECTION_PATTERNS.get(code)
    output = combined_output(command)
    matched = bool(pattern and pattern.search(output))
    unexpected_output = pptx.is_file()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    observed = lines[-1][:500] if lines else None
    failures = []
    if command.get('exit') in (0, None) and not command.get('timed_out'):
        failures.append(f'{label} did not fail the build')
    if not matched:
        failures.append(f'{label} did not report the named {code} rejection')
    if unexpected_output:
        failures.append(f'{label} wrote a PPTX for a rejected cell')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'cell': cell['id'],
        'theme': cell['theme'],
        'family': cell['family'],
        'case': cell['case'],
        'code': code,
        'expected_reason': (cell.get('rejection') or {}).get('reason'),
        'observed_error': sanitize(observed, roots) if observed else None,
        'matched': matched,
        'unexpected_output': unexpected_output,
        'commands': [command],
        'artifacts': {'pptx': str(pptx)},
    }


def run_multimodal_case(side, root, node_modules, spec_path, work, roots, log_dir):
    label = f'{side}-multimodal'
    out = Path(work) / 'cases' / side / 'multimodal'
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    scene = Path(str(pptx) + '.scene.json')
    qa_json = out / 'qa.json'
    qa_render = out / 'qa-render'
    commands = []
    failures = []
    build = run_command(
        root, [node_binary(), 'skill/scripts/build_deck.js', str(spec_path), str(pptx)],
        node_modules, roots, f'{label}-build', log_dir, timeout=1200)
    commands.append(build)
    if command_failed(build):
        failures.append(f'{label} build exited {build.get("exit")}')
    if not pptx.is_file():
        failures.append(f'{label} PPTX missing')
    quality = None
    if pptx.is_file():
        qa = run_command(
            root, [sys.executable, 'skill/scripts/quality_gate.py', str(pptx),
                   '--spec', str(spec_path), '--out', str(qa_json),
                   '--render-dir', str(qa_render)],
            node_modules, roots, f'{label}-qa', log_dir, timeout=1800)
        commands.append(qa)
        if command_failed(qa):
            failures.append(f'{label} QA exited {qa.get("exit")}')
    else:
        commands.append({'label': f'{label}-qa', 'exit': None, 'skipped': 'PPTX missing'})
    if not scene.is_file():
        failures.append(f'{label} scene missing')
    if qa_json.is_file():
        quality = read_generated_json(qa_json, failures, f'{label} QA JSON')
        if quality is not None:
            if quality.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
                failures.append(f'{label} QA status is {quality.get("status")!r}')
            if quality.get('VISUAL_QA') != 'NOT_RUN':
                failures.append(f'{label} QA VISUAL_QA is {quality.get("VISUAL_QA")!r}')
    else:
        failures.append(f'{label} QA JSON missing')
    if count_pngs(qa_render) == 0:
        failures.append(f'{label} QA render produced no PNG')
    media = []
    image_nodes = 0
    embedded = 0
    if pptx.is_file():
        try:
            with zipfile.ZipFile(pptx) as archive:
                media = [name for name in archive.namelist()
                         if name.startswith('ppt/media/') and not name.endswith('/')]
        except (OSError, zipfile.BadZipFile) as error:
            failures.append(f'{label} PPTX is unreadable: {error}')
    if scene.is_file():
        try:
            scene_data = read_json(scene)
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f'{label} scene is unreadable: {error}')
            scene_data = {}
        for slide in scene_data.get('slides') or []:
            for node in slide.get('nodes') or []:
                if node.get('kind') == 'image':
                    image_nodes += 1
                    if (node.get('provenance') or {}).get('render_mode') == 'embedded':
                        embedded += 1
    measurement = parity.title_measurement_evidence(scene) if scene.is_file() else {
        'status': 'FAIL', 'reason': 'scene missing'}
    if measurement.get('status') != 'PASS':
        failures.append(f'{label} title measurement is not real Pillow evidence')
    if len(media) < MULTIMODAL_MIN_EMBEDDED_IMAGES:
        failures.append(f'{label} embeds {len(media)} media files, expected at least '
                        f'{MULTIMODAL_MIN_EMBEDDED_IMAGES}')
    if image_nodes == 0 or embedded != image_nodes:
        failures.append(f'{label} has {image_nodes} image nodes and {embedded} embedded ones')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'commands': commands,
        'artifacts': {
            'pptx': str(pptx),
            'scene': str(scene),
            'qa_json': str(qa_json),
            'qa_semantic_json': str(out / 'qa.semantic-qa.json'),
            'qa_render': str(qa_render),
        },
        'qa_status': quality.get('status') if quality else None,
        'title_measurement': measurement,
        'embedded_images': len(media),
        'image_nodes': image_nodes,
        'embedded_image_nodes': embedded,
    }


def analytic_checks(recipe, data):
    metrics = data.get('metrics') or {}
    percentage_fields = 0
    percentage_point_fields = 0
    branches = 0
    if recipe == 'business-performance':
        kpis = metrics.get('kpis') or []
        percentage_fields = sum(
            1 for kpi in kpis for key in ('attainment', 'mom', 'yoy')
            if isinstance(kpi.get(key), (int, float)))
        percentage_point_fields = sum(
            1 for kpi in kpis if kpi.get('variance_unit') == 'pp')
    elif recipe == 'project-analytics':
        projects = metrics.get('projects') or []
        percentage_fields = sum(
            1 for project in projects for key in ('budget_usage', 'value_cost')
            if isinstance(project.get(key), (int, float)))
    elif recipe == 'sales-conversion':
        branches = len(metrics.get('branches') or [])
        percentage_fields = sum(
            1 for key in ('rate',) if isinstance((metrics.get('cohort') or {}).get(key),
                                                 (int, float)))
        percentage_fields += sum(
            1 for edge in metrics.get('edges') or []
            if isinstance(edge.get('rate'), (int, float)))
    return {
        'recipe': data.get('recipe'),
        'percentage_fields': percentage_fields,
        'percentage_point_fields': percentage_point_fields,
        'branches': branches,
        'has_data': bool(metrics),
    }


def run_analytics_case(side, root, node_modules, recipe, input_path, work, roots, log_dir):
    label = f'{side}-analytic-{recipe}'
    out = Path(work) / 'cases' / side / 'analytics' / recipe
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    data_json = Path(str(pptx) + '.data.json')
    scene = Path(str(pptx) + '.scene.json')
    spec = Path(str(pptx) + '.spec.json')
    commands = []
    failures = []
    command = run_command(
        root, [node_binary(), 'scripts/analyze.js', str(input_path), str(pptx)],
        node_modules, roots, f'{label}-analyze', log_dir, timeout=900)
    commands.append(command)
    if command_failed(command):
        failures.append(f'{label} analyze exited {command.get("exit")}')
    for path, name in ((pptx, 'PPTX'), (data_json, 'data JSON'),
                       (scene, 'scene'), (spec, 'spec')):
        if not path.is_file():
            failures.append(f'{label} {name} missing')
    data = None
    checks = {'recipe': recipe, 'percentage_fields': 0,
              'percentage_point_fields': 0, 'branches': 0, 'has_data': False}
    if data_json.is_file():
        data = read_generated_json(data_json, failures, f'{label} data JSON')
        if data is not None:
            checks = analytic_checks(recipe, data)
            if checks['recipe'] != recipe:
                failures.append(f'{label} data recipe is {checks["recipe"]!r}')
            if not checks['has_data']:
                failures.append(f'{label} analysis produced no metrics')
    if recipe == 'business-performance':
        if checks['percentage_fields'] < 3:
            failures.append(f'{label} lacks percentage attainment/change fields')
        if checks['percentage_point_fields'] < 1:
            failures.append(f'{label} lacks a percentage-point metric')
    if recipe == 'sales-conversion' and checks['branches'] < 1:
        failures.append(f'{label} lacks analytical branch outcomes')
    if recipe == 'project-analytics' and checks['percentage_fields'] < 1:
        failures.append(f'{label} lacks project percentage fields')
    measurement = parity.title_measurement_evidence(scene) if scene.is_file() else {
        'status': 'FAIL', 'reason': 'scene missing'}
    if measurement.get('status') != 'PASS':
        failures.append(f'{label} title measurement is not real Pillow evidence')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'commands': commands,
        'artifacts': {
            'pptx': str(pptx),
            'data_json': str(data_json),
            'scene': str(scene),
            'spec': str(spec),
        },
        'checks': checks,
        'title_measurement': measurement,
    }


def run_reasoning_case(side, root, node_modules, plan, plan_path, work, roots, log_dir):
    label = f'{side}-reasoning-{plan}'
    out = Path(work) / 'cases' / side / 'reasoning' / plan
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    spec = out / 'deck.spec.json'
    scene = Path(str(pptx) + '.scene.json')
    reasoning = Path(str(pptx) + '.reasoning.json')
    commands = []
    failures = []
    command = run_command(
        root, [node_binary(), 'skill/scripts/compile_plan.js', str(plan_path),
               '--out', str(pptx), '--spec-out', str(spec)],
        node_modules, roots, f'{label}-compile', log_dir, timeout=900)
    commands.append(command)
    if command_failed(command):
        failures.append(f'{label} compile exited {command.get("exit")}')
    for path, name in ((pptx, 'PPTX'), (spec, 'spec'), (scene, 'scene'),
                       (reasoning, 'reasoning report')):
        if not path.is_file():
            failures.append(f'{label} {name} missing')
    slide_types = []
    report_status = None
    if reasoning.is_file():
        try:
            report = read_json(reasoning)
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f'{label} reasoning report is unreadable: {error}')
            report = {}
        report_status = report.get('status')
        if report_status not in {'VALIDATED', 'PASS'}:
            failures.append(f'{label} reasoning report status is {report_status!r}')
    if scene.is_file():
        try:
            scene_data = read_json(scene)
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f'{label} scene is unreadable: {error}')
            scene_data = {}
        slide_types = [slide.get('type') for slide in scene_data.get('slides') or []]
    missing_types = [kind for kind in REASONING_REQUIRED_SLIDES[plan]
                     if kind not in slide_types]
    if missing_types:
        failures.append(f'{label} is missing representative slide types {missing_types}')
    measurement = parity.title_measurement_evidence(scene) if scene.is_file() else {
        'status': 'FAIL', 'reason': 'scene missing'}
    if measurement.get('status') != 'PASS':
        failures.append(f'{label} title measurement is not real Pillow evidence')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'commands': commands,
        'artifacts': {
            'pptx': str(pptx),
            'spec': str(spec),
            'scene': str(scene),
            'reasoning': str(reasoning),
        },
        'plan': plan,
        'report_status': report_status,
        'slide_types': slide_types,
        'title_measurement': measurement,
    }


def relationship_evidence(name, scene):
    slide = (scene.get('slides') or [{}])[0]
    nodes = slide.get('nodes') or []

    def role(value):
        return [node for node in nodes if node.get('semantic_role') == value]

    if name.startswith('dated-timeline'):
        markers = role('timeline_marker')
        return {
            'markers': len(markers),
            'marker_positions': [
                {'id': node.get('node_id'), 'x': (node.get('bbox') or {}).get('x'),
                 'label_lane': node.get('label_lane', 0)} for node in markers],
            'date_labels': [node.get('text') for node in role('timeline_date')],
            'durations': [
                {'id': node.get('node_id'), 'days': node.get('duration_days')}
                for node in role('timeline_duration')],
            'leaders': [node.get('node_id') for node in role('timeline_leader')],
        }
    if name == 'branch-swimlane':
        dependencies = []
        seen = set()
        for node in role('dependency'):
            edge = (node.get('from'), node.get('to'))
            if edge not in seen:
                seen.add(edge)
                dependencies.append({'from': edge[0], 'to': edge[1]})
        return {
            'task_nodes': [
                {'id': node.get('task_id'), 'owner': node.get('owner'),
                 'date': node.get('date'), 'status': node.get('status')}
                for node in role('task_node')],
            'swimlane_labels': [node.get('text') for node in role('swimlane_label')],
            'decision_edges': [node.get('text') for node in role('decision_edge')],
            'dependencies': dependencies,
        }
    lane_headings = [node.get('text') for node in nodes
                     if node.get('kind') == 'text' and node.get('text') in ('产品', '运营', '研究')]
    return {'lane_headings': lane_headings}


def timeline_distance_checks(name, evidence):
    """Marker positions must be proportional to real ISO date distances."""
    failures = []
    positions = [item['x'] for item in evidence['marker_positions']]
    labels = evidence['date_labels']
    if len(positions) != len(labels) or len(positions) < 2:
        return [f'{name} has {len(positions)} marker positions for {len(labels)} dates']
    try:
        dates = [date.fromisoformat(str(item)) for item in labels]
    except ValueError:
        return [f'{name} date labels are not ISO dates: {labels}']
    offsets = [(item - dates[0]).days for item in dates]
    if offsets != sorted(offsets) or len(set(offsets)) != len(offsets):
        failures.append(f'{name} date labels are not strictly increasing')
        return failures
    if not all(isinstance(item, (int, float)) for item in positions):
        failures.append(f'{name} marker positions are not numeric')
        return failures
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        failures.append(f'{name} marker positions are not strictly increasing')
        return failures
    day_span = offsets[-1]
    x_span = positions[-1] - positions[0]
    if day_span == 0 or x_span == 0:
        failures.append(f'{name} has no time span to compare')
        return failures
    for label, offset, position in zip(labels, offsets, positions):
        expected = offset / day_span
        actual = (position - positions[0]) / x_span
        if abs(expected - actual) > 0.01:
            failures.append(f'{name} marker {label} is at {actual:.4f} of the axis, '
                            f'expected {expected:.4f} from real dates')
    return failures


def relationship_checks(name, evidence):
    failures = []
    required = RELATIONSHIP_REQUIRED[name]
    if name == 'dated-timeline':
        if evidence['markers'] != required['markers']:
            failures.append(f'{name} has {evidence["markers"]} markers')
        if len(evidence['date_labels']) < required['min_dates']:
            failures.append(f'{name} has {len(evidence["date_labels"])} date labels')
        if len(evidence['durations']) < required['min_durations']:
            failures.append(f'{name} has no duration evidence')
        failures.extend(timeline_distance_checks(name, evidence))
    elif name == 'dated-timeline-close':
        if evidence['markers'] != required['markers']:
            failures.append(f'{name} has {evidence["markers"]} markers')
        lanes = {item['label_lane'] for item in evidence['marker_positions']}
        if len(lanes) < required['min_label_lanes']:
            failures.append(f'{name} does not use two label lanes')
    elif name == 'branch-swimlane':
        if len(evidence['task_nodes']) != required['task_nodes']:
            failures.append(f'{name} has {len(evidence["task_nodes"])} task nodes')
        if len(evidence['decision_edges']) != required['decision_edges']:
            failures.append(f'{name} has {len(evidence["decision_edges"])} decision edges')
        if len(evidence['dependencies']) != required['dependencies']:
            failures.append(f'{name} has {len(evidence["dependencies"])} dependencies')
        outgoing = sum(1 for item in evidence['dependencies'] if item['from'] == 'B')
        if outgoing != 3:
            failures.append(f'{name} branch B has {outgoing} explicit edges')
    elif name == 'roadmap':
        if set(evidence['lane_headings']) != set(required['lane_headings']):
            failures.append(f'{name} lane headings are {evidence["lane_headings"]}')
    return failures


def run_relationship_case(side, root, node_modules, name, spec_path, profile,
                          work, roots, log_dir, render):
    label = f'{side}-relationship-{name}-{profile["theme"]}'
    out = Path(work) / 'cases' / side / 'relationships' / f'{name}-{profile["theme"]}'
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    scene = Path(str(pptx) + '.scene.json')
    qa_json = out / 'qa.json'
    qa_render = out / 'qa-render'
    commands = []
    failures = []
    build = run_command(
        root, [node_binary(), 'skill/scripts/build_deck.js', str(spec_path), str(pptx)],
        node_modules, roots, f'{label}-build', log_dir, timeout=600)
    commands.append(build)
    if command_failed(build):
        failures.append(f'{label} build exited {build.get("exit")}')
    if not pptx.is_file():
        failures.append(f'{label} PPTX missing')
    quality = None
    if render and pptx.is_file():
        qa = run_command(
            root, [sys.executable, 'skill/scripts/quality_gate.py', str(pptx),
                   '--spec', str(spec_path), '--out', str(qa_json),
                   '--render-dir', str(qa_render)],
            node_modules, roots, f'{label}-qa', log_dir, timeout=900)
        commands.append(qa)
        if command_failed(qa):
            failures.append(f'{label} QA exited {qa.get("exit")}')
        if qa_json.is_file():
            quality = read_json(qa_json)
            if quality.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
                failures.append(f'{label} QA status is {quality.get("status")!r}')
            if quality.get('VISUAL_QA') != 'NOT_RUN':
                failures.append(f'{label} QA VISUAL_QA is {quality.get("VISUAL_QA")!r}')
        else:
            failures.append(f'{label} QA JSON missing')
        if count_pngs(qa_render) == 0:
            failures.append(f'{label} QA render produced no PNG')
    if not scene.is_file():
        failures.append(f'{label} scene missing')
    evidence = {}
    if scene.is_file():
        try:
            scene_data = read_json(scene)
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f'{label} scene is unreadable: {error}')
            scene_data = {}
        evidence = relationship_evidence(name, scene_data)
        failures.extend(f'{label} {item}' for item in relationship_checks(name, evidence))
    measurement = parity.title_measurement_evidence(scene) if scene.is_file() else {
        'status': 'FAIL', 'reason': 'scene missing'}
    if measurement.get('status') != 'PASS':
        failures.append(f'{label} title measurement is not real Pillow evidence')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'commands': commands,
        'artifacts': {
            'pptx': str(pptx),
            'scene': str(scene),
            'qa_json': str(qa_json),
            'qa_semantic_json': str(out / 'qa.semantic-qa.json'),
            'qa_render': str(qa_render),
        },
        'qa_status': quality.get('status') if quality else None,
        'evidence': evidence,
        'title_measurement': measurement,
        'profile': profile['profile'],
        'theme': profile['theme'],
    }


def _artifact_state(run, key, kind):
    path = (run.get('artifacts') or {}).get(key)
    if path is None:
        return False, f'missing {key}'
    path = Path(path)
    if kind == 'dir':
        return path.is_dir() and count_pngs(path) > 0, f'{key} is empty or missing'
    return path.is_file(), f'{key} is missing'


def reasoning_comparison(baseline_path, candidate_path, roots, limit=12):
    """Compare reasoning reports after dropping only volatile hash/time fields."""
    for path in (baseline_path, candidate_path):
        if not Path(path).is_file():
            return {'status': 'FAIL', 'reason': 'missing reasoning report',
                    'baseline': str(baseline_path), 'candidate': str(candidate_path)}

    def canonical(path):
        value = read_json(path)
        for key in ('generated_at', 'pptx_sha256', 'pptx_content_sha256',
                    'embedded_report_sha256'):
            value.pop(key, None)
        verification = value.get('verification')
        if isinstance(verification, dict):
            verification.pop('pptx_sha256', None)
        return value

    expected = parity.normalize_value(canonical(baseline_path), roots)
    actual = parity.normalize_value(canonical(candidate_path), roots)
    differences = parity.json_differences(expected, actual)
    return {
        'status': 'PASS' if not differences else 'FAIL',
        'differences': len(differences),
        'examples': [{'path': item[0], 'baseline': item[1], 'candidate': item[2]}
                     for item in differences[:limit]],
        'normalized': ['/generated_at', '/pptx_sha256', '/pptx_content_sha256',
                       '/embedded_report_sha256', '/verification/pptx_sha256'],
    }


def compare_runs(name, baseline_run, candidate_run, baseline_root, candidate_root, keys):
    if baseline_run.get('status') != 'PASS' or candidate_run.get('status') != 'PASS':
        return {
            'status': 'FAIL',
            'reason': 'case did not pass on both runtimes; comparisons were skipped',
            'failures': [
                f'{name} baseline {baseline_run.get("status")}',
                f'{name} candidate {candidate_run.get("status")}',
            ],
        }
    base = baseline_run.get('artifacts') or {}
    cand = candidate_run.get('artifacts') or {}
    missing = []
    for key, kind in keys:
        ok, message = _artifact_state(baseline_run, key, kind)
        if not ok:
            missing.append(f'baseline {message}')
        ok, message = _artifact_state(candidate_run, key, kind)
        if not ok:
            missing.append(f'candidate {message}')
    if missing:
        return {'status': 'FAIL', 'reason': 'required artifacts are missing',
                'failures': missing}
    roots = [str(baseline_root), str(candidate_root), str(Path(base['pptx']).parent),
             str(Path(cand['pptx']).parent)]
    comparisons = {}
    failures = []
    def both(key, kind):
        left = base.get(key)
        right = cand.get(key)
        if not left or not right:
            return False
        if kind == 'dir':
            return Path(left).is_dir() and Path(right).is_dir()
        return Path(left).is_file() and Path(right).is_file()

    if 'pptx' in base and 'pptx' in cand:
        comparisons['pptx'] = parity.compare_pptx_files(base['pptx'], cand['pptx'])
    if both('scene', 'file'):
        comparisons['scene'] = parity.compare_json_files(
            base['scene'], cand['scene'], roots, scene=True,
            paired_pptx=(base['pptx'], cand['pptx']))
    if both('qa_json', 'file'):
        comparisons['qa_json'] = parity.compare_json_files(
            base['qa_json'], cand['qa_json'], roots)
    if both('qa_semantic_json', 'file'):
        comparisons['qa_semantic_json'] = parity.compare_json_files(
            base['qa_semantic_json'], cand['qa_semantic_json'], roots)
    if both('qa_render', 'dir'):
        comparisons['qa_render_pngs'] = parity.compare_png_trees(
            base['qa_render'], cand['qa_render'])
    if both('render', 'dir'):
        comparisons['render_pngs'] = parity.compare_png_trees(base['render'], cand['render'])
    if both('spec', 'file'):
        comparisons['spec'] = parity.compare_json_files(base['spec'], cand['spec'], roots)
    if both('data_json', 'file'):
        comparisons['data_json'] = parity.compare_json_files(
            base['data_json'], cand['data_json'], roots)
    if both('reasoning', 'file'):
        comparisons['reasoning'] = reasoning_comparison(
            base['reasoning'], cand['reasoning'], roots)
    for label, result in comparisons.items():
        if result.get('status') != 'PASS':
            failures.append(f'{name} {label} comparison failed')
    return {'status': 'PASS' if not failures else 'FAIL', 'failures': failures,
            'comparisons': comparisons}


def _matrix_keys(_case):
    return (('pptx', 'file'), ('scene', 'file'), ('qa_json', 'file'), ('qa_render', 'dir'))


def _spec_keys(_case):
    return (('pptx', 'file'), ('scene', 'file'), ('qa_json', 'file'),
            ('qa_render', 'dir'), ('render', 'dir'))


def _analytics_keys(_case):
    return (('pptx', 'file'), ('data_json', 'file'), ('scene', 'file'), ('spec', 'file'))


def _reasoning_keys(_case):
    return (('pptx', 'file'), ('spec', 'file'), ('scene', 'file'), ('reasoning', 'file'))


def _relationship_keys(case):
    if case.get('render'):
        return (('pptx', 'file'), ('scene', 'file'), ('qa_json', 'file'), ('qa_render', 'dir'))
    return (('pptx', 'file'), ('scene', 'file'))


def _coverage_status(*statuses):
    return 'PASS' if all(status == 'PASS' for status in statuses) else 'FAIL'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True,
                        help='candidate Source tree that owns the harness and Spec data')
    parser.add_argument('--runtime-root', required=True,
                        help='installed candidate runtime directory (the skill root)')
    parser.add_argument('--baseline-zip', required=True,
                        help='locked official v1.3.1 Runtime ZIP')
    parser.add_argument('--baseline-root', required=True,
                        help='extracted locked v1.3.1 Runtime root (the skill root)')
    parser.add_argument('--node-modules',
                        help='baseline/source dependency fallback when no local node_modules exists; '
                             'the candidate must always own its installed node_modules')
    parser.add_argument('--artifact-dir',
                        help='fresh evidence directory; stale or caller-owned data is refused')
    parser.add_argument('--contract', default=CONTRACT_NAME, choices=[CONTRACT_NAME])
    parser.add_argument('--json', help='write the result JSON to this path')
    parser.add_argument('--performance', action='store_true', help='accepted for symmetry; not used')
    args = parser.parse_args(argv)

    contract = contract_rule(args.contract)
    source_root = Path(args.source_root).resolve()
    runtime_root = Path(args.runtime_root).resolve()
    baseline_root = Path(args.baseline_root).resolve()
    baseline_zip = Path(args.baseline_zip).resolve()
    artifact_root = prepare_artifact_root(args.artifact_dir, source_root,
                                          runtime_root, baseline_root)
    work = artifact_root / 'work'
    work.mkdir(parents=True, exist_ok=True)
    log_dir = artifact_root / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    roots = [source_root, runtime_root, baseline_root, str(ROOT),
             str(artifact_root), str(work)]
    failures = []

    source = source_evidence(source_root, contract)
    candidate = candidate_runtime_evidence(runtime_root)
    baseline = baseline_runtime_evidence(baseline_zip, baseline_root, contract)
    module_roles = {
        'source': module_evidence('source', source_root, args.node_modules),
        'candidate': module_evidence('candidate', runtime_root, args.node_modules),
        'baseline': module_evidence('baseline', baseline_root, args.node_modules),
    }
    write_json(Path(work) / 'evidence' / 'identity.json', {
        'source': source, 'candidate': candidate, 'baseline': baseline,
        'modules': module_roles,
    })
    for name, evidence in (('source', source), ('candidate runtime', candidate),
                           ('baseline runtime', baseline)):
        if evidence['status'] != 'PASS':
            failures.append(f'{name} identity failed')
    for name, evidence in module_roles.items():
        if evidence['status'] != 'PASS':
            failures.append(f'{name} node_modules evidence failed: '
                            + '; '.join(evidence.get('failures') or []))

    generated = {'status': 'FAIL', 'failures': ['not run']}
    generated_spec = None
    spec_case_list = []
    runs = {'baseline': {}, 'candidate': {}}
    comparisons = {}
    coverage = {
        'status': 'FAIL',
        'matrix': {'status': 'FAIL', 'reason': 'not run'},
        'multimodal': {'status': 'FAIL', 'reason': 'not run'},
        'analytics': {'status': 'FAIL', 'reason': 'not run'},
        'reasoning': {'status': 'FAIL', 'reason': 'not run'},
        'relationships': {'status': 'FAIL', 'reason': 'not run'},
    }
    matrix_fixture = None
    matrix_validation = {'status': 'FAIL', 'failures': ['not run']}
    matrix_runs = {'baseline': {}, 'candidate': {}}
    matrix_specs = {}
    rejection_runs = {'baseline': {}, 'candidate': {}}
    multimodal_runs = {'baseline': {}, 'candidate': {}}
    analytics_runs = {'baseline': {}, 'candidate': {}}
    reasoning_runs = {'baseline': {}, 'candidate': {}}
    relationship_runs = {'baseline': {}, 'candidate': {}}
    rejection_specs = {}

    if not failures:
        generated, generated_spec = generate_source_spec(
            source_root, work, resolve_node_modules(source_root, args.node_modules),
            roots, log_dir)
        if generated['status'] != 'PASS':
            failures.append('Source spec generation failed')
        else:
            spec_case_list = spec_cases(source_root, generated_spec, roots)
            for case in spec_case_list:
                if not case['sha256']:
                    failures.append(f'{case["name"]} spec is missing')
        if not failures:
            try:
                matrix_fixture = read_json(source_root / MATRIX_SOURCE)
            except (OSError, json.JSONDecodeError) as error:
                failures.append(f'matrix fixture is unreadable: {error}')
                matrix_fixture = None
            if matrix_fixture is not None:
                matrix_validation = validate_matrix_fixture(matrix_fixture)
                if matrix_validation['status'] != 'PASS':
                    failures.extend(f'matrix fixture: {item}'
                                    for item in matrix_validation['failures'])
        if not failures:
            for theme in MATRIX_THEMES:
                spec, cells = matrix_deck_spec(matrix_fixture, theme)
                spec_path = Path(work) / 'source-matrix' / f'{theme}.spec.json'
                write_json(spec_path, spec)
                case = {'name': f'matrix-{theme}', 'kind': 'source-matrix-spec',
                        'path': spec_path, 'cells': cells,
                        'origin': MATRIX_SOURCE, 'sha256': sha256_file(spec_path)}
                matrix_specs[theme] = case
            for cell in matrix_fixture['cells']:
                if cell.get('expected') != 'REJECT':
                    continue
                spec_path = Path(work) / 'source-rejections' / f"{cell['id']}.spec.json"
                write_json(spec_path, matrix_rejection_spec(matrix_fixture, cell))
                rejection_specs[cell['id']] = spec_path
            multimodal_spec = source_root / MULTIMODAL_SOURCE
            relationships = read_json(source_root / RELATIONSHIP_SOURCE)
            for name, index in RELATIONSHIP_CASES:
                for theme, profile in RELATIONSHIP_THEMES:
                    spec = {
                        'schema_version': relationships.get('schema_version', '1.3'),
                        'title': relationships.get('title', name),
                        'profile': profile,
                        'slides': [relationships['slides'][index]],
                    }
                    path = Path(work) / 'source-relationships' / f'{name}-{theme}.spec.json'
                    write_json(path, spec)
            for recipe in ANALYTICS_RECIPES:
                if not (source_root / ANALYTICS_SOURCE.format(recipe=recipe)).is_file():
                    failures.append(f'analytics input is missing for {recipe}')
            for plan in REASONING_PLANS:
                if not (source_root / REASONING_SOURCE.format(plan=plan)).is_file():
                    failures.append(f'reasoning plan is missing for {plan}')

        if not failures:
            node_modules = {
                'baseline': resolve_node_modules(baseline_root, args.node_modules),
                'candidate': resolve_node_modules(runtime_root, args.node_modules),
            }
            for case in spec_case_list:
                for side, root, modules in (('baseline', baseline_root, node_modules['baseline']),
                                            ('candidate', runtime_root, node_modules['candidate'])):
                    run = run_spec_case(side, root, modules, case, work, roots, log_dir)
                    runs[side][case['name']] = run
                    if run['status'] != 'PASS':
                        failures.extend(run['failures'])
            for case in spec_case_list:
                comparison = compare_runs(case['name'], runs['baseline'][case['name']],
                                          runs['candidate'][case['name']],
                                          baseline_root, runtime_root, _spec_keys(case))
                comparisons[case['name']] = comparison
                if comparison['status'] != 'PASS':
                    failures.extend(comparison['failures'])

            for theme, case in matrix_specs.items():
                for side, root, modules in (('baseline', baseline_root, node_modules['baseline']),
                                            ('candidate', runtime_root, node_modules['candidate'])):
                    run = run_matrix_deck(side, root, modules, case, case['cells'],
                                          work, roots, log_dir)
                    matrix_runs[side][case['name']] = run
                    if run['status'] != 'PASS':
                        failures.extend(run['failures'])
            for theme, case in matrix_specs.items():
                comparison = compare_runs(case['name'],
                                          matrix_runs['baseline'][case['name']],
                                          matrix_runs['candidate'][case['name']],
                                          baseline_root, runtime_root, _matrix_keys(case))
                comparisons[case['name']] = comparison
                if comparison['status'] != 'PASS':
                    failures.extend(comparison['failures'])

            rejection_cells = {}
            for cell in matrix_fixture['cells']:
                if cell.get('expected') != 'REJECT':
                    continue
                rejection_cells[cell['id']] = cell
                for side, root, modules in (('baseline', baseline_root, node_modules['baseline']),
                                            ('candidate', runtime_root, node_modules['candidate'])):
                    run = run_matrix_rejection(side, root, modules, cell,
                                               rejection_specs[cell['id']],
                                               work, roots, log_dir)
                    rejection_runs[side][cell['id']] = run
                    if run['status'] != 'PASS':
                        failures.extend(run['failures'])
            rejection_comparison = {'status': 'PASS', 'failures': [], 'cells': {}}
            for cell_id in rejection_cells:
                base = rejection_runs['baseline'][cell_id]
                cand = rejection_runs['candidate'][cell_id]
                same_code = base.get('code') == cand.get('code')
                matched = base.get('matched') and cand.get('matched') and same_code
                rejection_comparison['cells'][cell_id] = {
                    'baseline_matched': base.get('matched'),
                    'candidate_matched': cand.get('matched'),
                    'baseline_code': base.get('code'),
                    'candidate_code': cand.get('code'),
                    'status': 'PASS' if matched else 'FAIL',
                }
                if not matched:
                    rejection_comparison['failures'].append(
                        f'{cell_id} rejection was not reproduced by both runtimes')
            if rejection_comparison['failures']:
                rejection_comparison['status'] = 'FAIL'
                failures.extend(rejection_comparison['failures'])
            comparisons['matrix-rejections'] = rejection_comparison

            for side, root, modules in (('baseline', baseline_root, node_modules['baseline']),
                                        ('candidate', runtime_root, node_modules['candidate'])):
                run = run_multimodal_case(side, root, modules, multimodal_spec,
                                          work, roots, log_dir)
                multimodal_runs[side]['multimodal-integration'] = run
                if run['status'] != 'PASS':
                    failures.extend(run['failures'])
            comparison = compare_runs('multimodal-integration',
                                      multimodal_runs['baseline']['multimodal-integration'],
                                      multimodal_runs['candidate']['multimodal-integration'],
                                      baseline_root, runtime_root, _matrix_keys(None))
            comparisons['multimodal-integration'] = comparison
            if comparison['status'] != 'PASS':
                failures.extend(comparison['failures'])

            for recipe in ANALYTICS_RECIPES:
                name = f'analytic-{recipe}'
                input_path = source_root / ANALYTICS_SOURCE.format(recipe=recipe)
                for side, root, modules in (('baseline', baseline_root, node_modules['baseline']),
                                            ('candidate', runtime_root, node_modules['candidate'])):
                    run = run_analytics_case(side, root, modules, recipe, input_path,
                                             work, roots, log_dir)
                    analytics_runs[side][name] = run
                    if run['status'] != 'PASS':
                        failures.extend(run['failures'])
                comparison = compare_runs(name, analytics_runs['baseline'][name],
                                          analytics_runs['candidate'][name],
                                          baseline_root, runtime_root, _analytics_keys(None))
                comparisons[name] = comparison
                if comparison['status'] != 'PASS':
                    failures.extend(comparison['failures'])

            for plan in REASONING_PLANS:
                name = f'reasoning-{plan}'
                plan_path = source_root / REASONING_SOURCE.format(plan=plan)
                for side, root, modules in (('baseline', baseline_root, node_modules['baseline']),
                                            ('candidate', runtime_root, node_modules['candidate'])):
                    run = run_reasoning_case(side, root, modules, plan, plan_path,
                                             work, roots, log_dir)
                    reasoning_runs[side][name] = run
                    if run['status'] != 'PASS':
                        failures.extend(run['failures'])
                comparison = compare_runs(name, reasoning_runs['baseline'][name],
                                          reasoning_runs['candidate'][name],
                                          baseline_root, runtime_root, _reasoning_keys(None))
                comparisons[name] = comparison
                if comparison['status'] != 'PASS':
                    failures.extend(comparison['failures'])

            for name, _index in RELATIONSHIP_CASES:
                for theme, profile in RELATIONSHIP_THEMES:
                    case_name = f'relationship-{name}-{theme}'
                    spec_path = Path(work) / 'source-relationships' / f'{name}-{theme}.spec.json'
                    render = theme == 'light'
                    for side, root, modules in (('baseline', baseline_root, node_modules['baseline']),
                                                ('candidate', runtime_root, node_modules['candidate'])):
                        run = run_relationship_case(
                            side, root, modules, name, spec_path,
                            {'theme': theme, 'profile': profile},
                            work, roots, log_dir, render)
                        relationship_runs[side][case_name] = run
                        if run['status'] != 'PASS':
                            failures.extend(run['failures'])
                    case = {'name': case_name, 'render': render}
                    comparison = compare_runs(
                        case_name, relationship_runs['baseline'][case_name],
                        relationship_runs['candidate'][case_name],
                        baseline_root, runtime_root, _relationship_keys(case))
                    comparisons[case_name] = comparison
                    if comparison['status'] != 'PASS':
                        failures.extend(comparison['failures'])

    # Coverage is computed from actual runs and comparisons, never copied PASS fields.
    matrix_coverage = {
        'status': 'FAIL',
        'source': MATRIX_SOURCE,
        'fixture': matrix_validation,
        'cells': 0, 'accepted': 0, 'rejected': 0,
        'themes': {},
        'accepted_decks': {},
        'rejections': {'status': 'FAIL', 'attempted': 0, 'matched': 0,
                       'by_code': {}, 'by_family': {}},
    }
    if matrix_fixture is not None and matrix_validation.get('status') == 'PASS':
        accepted_total = sum(len(case['cells']) for case in matrix_specs.values())
        rejected_cells = [cell for cell in matrix_fixture['cells']
                          if cell.get('expected') == 'REJECT']
        statuses = []
        for theme, case in matrix_specs.items():
            base = matrix_runs['baseline'].get(case['name'], {})
            cand = matrix_runs['candidate'].get(case['name'], {})
            comparison = comparisons.get(case['name'], {})
            theme_status = _coverage_status(
                base.get('status', 'FAIL'), cand.get('status', 'FAIL'),
                comparison.get('status', 'FAIL'))
            statuses.append(theme_status)
            matrix_coverage['themes'][theme] = {
                'accepted_cells': len(case['cells']),
                'accepted_deck_status': base.get('status'),
                'candidate_deck_status': cand.get('status'),
                'comparison_status': comparison.get('status'),
                'native_charts': (cand.get('native') or {}).get('charts', 0),
                'families': (cand.get('native') or {}).get('families', {}),
                'qa_status': cand.get('qa_status'),
                'status': theme_status,
            }
            matrix_coverage['accepted_decks'][theme] = {
                'accepted_cells': len(case['cells']),
                'native_charts': (cand.get('native') or {}).get('charts', 0),
                'status': theme_status,
            }
        by_code = {}
        by_family = {}
        matched = 0
        attempted = 0
        for cell in rejected_cells:
            attempted += 1
            code = (cell.get('rejection') or {}).get('code')
            base = rejection_runs['baseline'].get(cell['id'], {})
            cand = rejection_runs['candidate'].get(cell['id'], {})
            comparison = (comparisons.get('matrix-rejections') or {}).get('cells', {}).get(
                cell['id'], {})
            if comparison.get('status') == 'PASS':
                matched += 1
                by_code[code] = by_code.get(code, 0) + 1
                by_family[cell['family']] = by_family.get(cell['family'], 0) + 1
        rejection_status = 'PASS' if matched == len(rejected_cells) == 24 else 'FAIL'
        matrix_coverage.update({
            'cells': matrix_validation['cells'],
            'accepted': matrix_validation['accepted'],
            'rejected': matrix_validation['rejected'],
            'families': matrix_validation['families'],
            'status': _coverage_status(*statuses) if statuses and rejection_status == 'PASS'
            else 'FAIL',
        })
        matrix_coverage['rejections'] = {
            'status': rejection_status,
            'attempted': attempted,
            'matched': matched,
            'by_code': by_code,
            'by_family': by_family,
            'commands': sum(len(run.get('commands') or [])
                            for side in rejection_runs.values()
                            for run in side.values()),
        }

    multimodal_coverage = {'status': 'FAIL', 'source': MULTIMODAL_SOURCE}
    base_mm = multimodal_runs['baseline'].get('multimodal-integration', {})
    cand_mm = multimodal_runs['candidate'].get('multimodal-integration', {})
    mm_comparison = comparisons.get('multimodal-integration', {})
    if base_mm and cand_mm:
        multimodal_coverage.update({
            'case': 'multimodal-integration',
            'embedded_images': min(base_mm.get('embedded_images', 0),
                                   cand_mm.get('embedded_images', 0)),
            'image_nodes': min(base_mm.get('image_nodes', 0),
                               cand_mm.get('image_nodes', 0)),
            'embedded_image_nodes': min(base_mm.get('embedded_image_nodes', 0),
                                        cand_mm.get('embedded_image_nodes', 0)),
            'baseline_status': base_mm.get('status'),
            'candidate_status': cand_mm.get('status'),
            'comparison_status': mm_comparison.get('status'),
            'status': _coverage_status(base_mm.get('status', 'FAIL'),
                                       cand_mm.get('status', 'FAIL'),
                                       mm_comparison.get('status', 'FAIL')),
        })

    analytics_coverage = {
        'status': 'FAIL', 'recipes': [], 'percentage_fields': 0,
        'percentage_point_fields': 0, 'branches': 0,
    }
    analytics_statuses = []
    for recipe in ANALYTICS_RECIPES:
        name = f'analytic-{recipe}'
        base = analytics_runs['baseline'].get(name, {})
        cand = analytics_runs['candidate'].get(name, {})
        comparison = comparisons.get(name, {})
        checks = cand.get('checks') or {}
        status = _coverage_status(base.get('status', 'FAIL'), cand.get('status', 'FAIL'),
                                  comparison.get('status', 'FAIL'))
        analytics_statuses.append(status)
        analytics_coverage['recipes'].append({
            'recipe': recipe,
            'percentage_fields': checks.get('percentage_fields', 0),
            'percentage_point_fields': checks.get('percentage_point_fields', 0),
            'branches': checks.get('branches', 0),
            'status': status,
        })
        analytics_coverage['percentage_fields'] += checks.get('percentage_fields', 0)
        analytics_coverage['percentage_point_fields'] += checks.get('percentage_point_fields', 0)
        analytics_coverage['branches'] += checks.get('branches', 0)
    if analytics_statuses:
        analytics_coverage['status'] = _coverage_status(*analytics_statuses)

    reasoning_coverage = {'status': 'FAIL', 'plans': [], 'slide_types': {}}
    reasoning_statuses = []
    for plan in REASONING_PLANS:
        name = f'reasoning-{plan}'
        base = reasoning_runs['baseline'].get(name, {})
        cand = reasoning_runs['candidate'].get(name, {})
        comparison = comparisons.get(name, {})
        status = _coverage_status(base.get('status', 'FAIL'), cand.get('status', 'FAIL'),
                                  comparison.get('status', 'FAIL'))
        reasoning_statuses.append(status)
        reasoning_coverage['plans'].append({'plan': plan, 'status': status,
                                            'report_status': cand.get('report_status')})
        reasoning_coverage['slide_types'][plan] = cand.get('slide_types') or []
    if reasoning_statuses:
        reasoning_coverage['status'] = _coverage_status(*reasoning_statuses)

    relationship_coverage = {'status': 'FAIL', 'cases': [], 'themes': [],
                             'evidence': {}, 'outputs': 0}
    relationship_statuses = []
    for name, _index in RELATIONSHIP_CASES:
        relationship_coverage['cases'].append(name)
        relationship_coverage['evidence'][name] = {}
        for theme, _profile in RELATIONSHIP_THEMES:
            case_name = f'relationship-{name}-{theme}'
            base = relationship_runs['baseline'].get(case_name, {})
            cand = relationship_runs['candidate'].get(case_name, {})
            comparison = comparisons.get(case_name, {})
            status = _coverage_status(base.get('status', 'FAIL'), cand.get('status', 'FAIL'),
                                      comparison.get('status', 'FAIL'))
            relationship_statuses.append(status)
            relationship_coverage['outputs'] += 1
            relationship_coverage['evidence'][name][theme] = {
                'evidence': cand.get('evidence') or {},
                'status': status,
                'qa_status': cand.get('qa_status'),
            }
    relationship_coverage['themes'] = [theme for theme, _profile in RELATIONSHIP_THEMES]
    if relationship_statuses:
        relationship_coverage['status'] = _coverage_status(*relationship_statuses)

    coverage.update({
        'matrix': matrix_coverage,
        'multimodal': multimodal_coverage,
        'analytics': analytics_coverage,
        'reasoning': reasoning_coverage,
        'relationships': relationship_coverage,
    })
    coverage['status'] = _coverage_status(
        matrix_coverage.get('status', 'FAIL'),
        multimodal_coverage.get('status', 'FAIL'),
        analytics_coverage.get('status', 'FAIL'),
        reasoning_coverage.get('status', 'FAIL'),
        relationship_coverage.get('status', 'FAIL'))
    if coverage['status'] != 'PASS' and not failures:
        failures.append('actual case coverage is incomplete')

    node_modules = {
        'baseline': module_roles['baseline'].get('path'),
        'candidate': module_roles['candidate'].get('path'),
    }
    result = {
        'schema_version': contract['candidate_version'],
        'status': 'PASS' if not failures else 'FAIL',
        'gate': 'installed_candidate_runtime_vs_locked_v1_3_1_runtime',
        'capability_parity': CONTRACT_NAME,
        'contract': contract,
        'execution': {
            'installed_runtime_cli': True,
            'fixed_argv': True,
            'imports_installed_code': False,
            'injects_developer_overlay': False,
            'source_inputs': 'Spec, plan and data JSON only',
            'same_host': True,
            'python': {
                'executable': str(Path(sys.executable).name),
                'version': sys.version.split()[0],
                'isolated_prefix': sys.prefix != sys.base_prefix,
            },
        },
        'source_harness': {
            'root': '<SOURCE_ROOT>',
            'evidence': source,
            'spec_data': generated,
            'cases': [{'name': case['name'], 'kind': case['kind'],
                       'origin': case['origin'], 'sha256': case['sha256']}
                      for case in spec_case_list],
            'matrix': {'source': MATRIX_SOURCE, 'validation': matrix_validation},
            'note': ('The Source tree supplies Spec, plan and data JSON as input data. '
                     'The harness executes each installed runtime production CLI with fixed '
                     'argv; it does not import developer or release tools from installed roots '
                     'and does not inject a developer code overlay.'),
        },
        'installed_runtime': {
            'baseline': {
                'root': '<BASELINE_ROOT>',
                'evidence': baseline,
                'node_modules': module_roles['baseline'],
            },
            'candidate': {
                'root': '<CANDIDATE_ROOT>',
                'evidence': candidate,
                'node_modules': module_roles['candidate'],
            },
            'python': {
                'executable': str(Path(sys.executable).name),
                'version': sys.version.split()[0],
                'isolated_prefix': sys.prefix != sys.base_prefix,
            },
            'same_host': True,
            'commands': {
                side: {name: run.get('commands') or [] for name, run in side_runs.items()}
                for side, side_runs in (
                    ('baseline', {
                        **runs['baseline'], **matrix_runs['baseline'],
                        **multimodal_runs['baseline'], **analytics_runs['baseline'],
                        **reasoning_runs['baseline'], **relationship_runs['baseline'],
                    }),
                    ('candidate', {
                        **runs['candidate'], **matrix_runs['candidate'],
                        **multimodal_runs['candidate'], **analytics_runs['candidate'],
                        **reasoning_runs['candidate'], **relationship_runs['candidate'],
                    }),
                )
            },
        },
        'coverage': coverage,
        'comparisons': comparisons,
        'failures': failures,
        'visual_qa': 'NOT_RUN',
        'company_platform_security': 'NOT_VERIFIED',
        'note': ('Actual installed-runtime production CLIs were executed with fixed argv and '
                 'Source-owned JSON inputs. The harness does not import developer or release '
                 'tools from installed roots and does not inject a developer code overlay. '
                 'Native PPTX, scene, QA JSON, reasoning, analytics data and same-host rendered '
                 'pixels are compared to the locked v1.3.1 Runtime ZIP. This is not visual '
                 'approval or enterprise-platform acceptance.'),
    }
    result['artifacts'] = {
        'root': str(artifact_root),
        'marker': ARTIFACT_MARKER,
        'retained_on_failure': True,
        'note': ('PPTX, scene, QA, logs, render and Montage evidence is retained under this '
                 'directory for independent review, including failed cases.'),
    }
    result = sanitize_value(result, roots)
    manifest, manifest_sha256 = artifact_manifest(artifact_root)
    result['artifacts'].update({
        'manifest_count': len(manifest),
        'manifest_sha256': manifest_sha256,
        'files': manifest,
    })
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    (artifact_root / 'result.json').write_text(payload, encoding='utf-8')
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding='utf-8')
    print(payload, end='')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
