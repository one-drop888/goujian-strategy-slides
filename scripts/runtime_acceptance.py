#!/usr/bin/env python3
"""Acceptance for an installed candidate runtime against the locked v1.3.1 runtime.

This is a Source-only harness. The Source tree generates or supplies JSON Spec
data, and both installed runtimes receive that data as ordinary input. The
harness never imports or executes code from an installed runtime root; it runs
each runtime's own documented CLI in that root. Native PPTX parts, scene JSON,
QA JSON and same-host rendered pixels are compared with the existing
capability_parity functions.

The baseline must be the locked v1.3.1 Runtime ZIP. Versions and the baseline
SHA256 are fixed by CAPABILITY_PARITY_V1_3_1_TO_V1_3_2; callers cannot supply
alternative versions or hashes.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
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
INSTALL_STATE_DIRS = {'node_modules', '.venv', 'out', 'dist', 'build',
                      '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
SPEC_CASES = (
    {'name': 'q4-generated', 'kind': 'source-generated-spec'},
    {'name': 'executive-review', 'kind': 'source-provided-spec'},
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


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
    for path in root.rglob('*'):
        if path.is_symlink():
            symlinks.append(path.relative_to(root).as_posix())
    if symlinks:
        failures.append(f'baseline contains symlinks: {symlinks[:3]}')
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


def resolve_node_modules(root, fallback):
    local = Path(root) / 'node_modules'
    if local.is_dir():
        return local
    if fallback and Path(fallback).is_dir():
        return Path(fallback)
    return None


def run_command(root, argv, node_modules, roots, label, timeout=900):
    environment = os.environ.copy()
    environment['PATH'] = str(Path(sys.executable).parent) + os.pathsep + environment.get('PATH', '')
    if node_modules:
        environment['NODE_PATH'] = str(node_modules)
    started = time.time()
    result = subprocess.run(argv, cwd=str(root), env=environment, capture_output=True,
                            text=True, timeout=timeout)
    return {
        'label': label,
        'argv': sanitize_value(argv, roots),
        'cwd': '<ROOT>',
        'exit': result.returncode,
        'duration_seconds': round(time.time() - started, 3),
        'stdout_tail': sanitize(result.stdout[-2000:], roots),
        'stderr_tail': sanitize(result.stderr[-2000:], roots),
    }


def generate_source_spec(source_root, work, node_modules, roots):
    source_out = Path(work) / 'source-harness'
    source_out.mkdir(parents=True, exist_ok=True)
    plan = Path(source_root) / 'skill/reasoning/fixtures/q4-six-actions/plan.json'
    spec = source_out / 'q4.spec.json'
    pptx = source_out / 'source-q4.pptx'
    argv = [shutil.which('node') or 'node', 'skill/scripts/compile_plan.js', str(plan),
            '--out', str(pptx), '--spec-out', str(spec)]
    command = run_command(source_root, argv, node_modules, roots, 'source-generate-q4-spec')
    ok = command['exit'] == 0 and spec.is_file()
    return {
        'status': 'PASS' if ok else 'FAIL',
        'kind': 'source-generated-spec',
        'plan': {'path': 'skill/reasoning/fixtures/q4-six-actions/plan.json',
                 'sha256': sha256_file(plan) if plan.is_file() else None},
        'generated_spec': {'sha256': sha256_file(spec) if spec.is_file() else None},
        'command': command,
    }


def spec_cases(source_root, generated, roots):
    cases = []
    for definition in SPEC_CASES:
        if definition['name'] == 'q4-generated':
            path = Path(generated['generated_spec_path'])
            origin = generated['plan']['path']
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


def run_runtime_case(side, root, node_modules, spec_case, work, roots):
    label = f'{side}-{spec_case["name"]}'
    out = Path(work) / 'runtime-output' / side / spec_case['name']
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / 'deck.pptx'
    qa_json = out / 'qa.json'
    qa_render = out / 'qa-render'
    render = out / 'render'
    commands = [
        run_command(root, [shutil.which('node') or 'node', 'skill/scripts/build_deck.js',
                           str(spec_case['path']), str(pptx)], node_modules, roots, f'{label}-build'),
        run_command(root, [sys.executable, 'skill/scripts/quality_gate.py', str(pptx),
                           '--spec', str(spec_case['path']), '--out', str(qa_json),
                           '--render-dir', str(qa_render)], node_modules, roots, f'{label}-qa'),
        run_command(root, [sys.executable, 'skill/scripts/render_deck.py', str(pptx),
                           str(render)], node_modules, roots, f'{label}-render'),
    ]
    failures = []
    for command in commands:
        if command['exit'] != 0:
            failures.append(f'{command["label"]} exited {command["exit"]}')
    for path, label_name in ((pptx, 'PPTX'), (Path(str(pptx) + '.scene.json'), 'scene'),
                             (qa_json, 'QA JSON')):
        if not path.is_file():
            failures.append(f'{label_name} missing')
    quality = None
    if qa_json.is_file():
        quality = read_json(qa_json)
        if quality.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            failures.append(f'QA status is {quality.get("status")!r}')
        if quality.get('VISUAL_QA') != 'NOT_RUN':
            failures.append(f'QA VISUAL_QA is {quality.get("VISUAL_QA")!r}')
    for directory, label_name in ((qa_render, 'QA render'), (render, 'render')):
        pngs = [path for path in Path(directory).rglob('*.png') if path.is_file()] \
            if Path(directory).is_dir() else []
        if not pngs:
            failures.append(f'{label_name} produced no PNG')
    scene = Path(str(pptx) + '.scene.json')
    measurement = parity.title_measurement_evidence(scene) if scene.is_file() else {
        'status': 'FAIL', 'reason': 'scene missing'}
    if measurement.get('status') != 'PASS':
        failures.append(f'{label} title measurement is not real Pillow evidence')
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'commands': commands,
        'artifacts': {
            'pptx': pptx,
            'scene': scene,
            'qa_json': qa_json,
            'qa_semantic_json': out / 'qa.semantic-qa.json',
            'qa_render': qa_render,
            'render': render,
        },
        'qa_status': quality.get('status') if quality else None,
        'title_measurement': measurement,
    }


def compare_case(spec_case, baseline_run, candidate_run, baseline_root, candidate_root):
    base = baseline_run['artifacts']
    cand = candidate_run['artifacts']
    base_output = str(Path(base['pptx']).parent)
    cand_output = str(Path(cand['pptx']).parent)
    roots = [str(baseline_root), str(candidate_root), base_output, cand_output]
    comparisons = {}
    failures = []
    comparisons['pptx'] = parity.compare_pptx_files(base['pptx'], cand['pptx'])
    scene = parity.compare_json_files(
        base['scene'], cand['scene'], roots, scene=True,
        paired_pptx=(base['pptx'], cand['pptx']))
    comparisons['scene'] = scene
    comparisons['qa_json'] = parity.compare_json_files(base['qa_json'], cand['qa_json'], roots)
    if base['qa_semantic_json'].is_file() and cand['qa_semantic_json'].is_file():
        comparisons['qa_semantic_json'] = parity.compare_json_files(
            base['qa_semantic_json'], cand['qa_semantic_json'], roots)
    comparisons['qa_render_pngs'] = parity.compare_png_trees(base['qa_render'], cand['qa_render'])
    comparisons['render_pngs'] = parity.compare_png_trees(base['render'], cand['render'])
    for name, result in comparisons.items():
        if result.get('status') != 'PASS':
            failures.append(f'{spec_case["name"]} {name} comparison failed')
    return {'status': 'PASS' if not failures else 'FAIL', 'failures': failures,
            'comparisons': comparisons}


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
    parser.add_argument('--node-modules', help='dependency-only fallback when a root has no node_modules')
    parser.add_argument('--contract', default=CONTRACT_NAME, choices=[CONTRACT_NAME])
    parser.add_argument('--json', help='write the result JSON to this path')
    parser.add_argument('--performance', action='store_true', help='accepted for symmetry; not used')
    args = parser.parse_args(argv)

    contract = contract_rule(args.contract)
    source_root = Path(args.source_root).resolve()
    runtime_root = Path(args.runtime_root).resolve()
    baseline_root = Path(args.baseline_root).resolve()
    baseline_zip = Path(args.baseline_zip).resolve()
    roots = [source_root, runtime_root, baseline_root, str(ROOT)]
    failures = []

    work = Path(tempfile.mkdtemp(prefix='goujian-runtime-acceptance-'))
    roots = [*roots, str(work)]
    try:
        for output in (work,):
            for protected in (source_root, runtime_root, baseline_root):
                if inside(output, protected):
                    raise SystemExit(f'refusing to write acceptance output inside {protected}')

        source = source_evidence(source_root, contract)
        candidate = candidate_runtime_evidence(runtime_root)
        baseline = baseline_runtime_evidence(baseline_zip, baseline_root, contract)
        for name, evidence in (('source', source), ('candidate runtime', candidate),
                               ('baseline runtime', baseline)):
            if evidence['status'] != 'PASS':
                failures.append(f'{name} identity failed')

        source_modules = resolve_node_modules(source_root, args.node_modules)
        candidate_modules = resolve_node_modules(runtime_root, args.node_modules)
        baseline_modules = resolve_node_modules(baseline_root, args.node_modules)
        for label, modules in (('source', source_modules), ('candidate', candidate_modules),
                               ('baseline', baseline_modules)):
            if modules is None:
                failures.append(f'{label} has no node_modules and no fallback was provided')

        generated = {'status': 'FAIL', 'failures': ['not run']}
        cases = []
        runs = {}
        comparisons = {}
        if not failures:
            generated = generate_source_spec(source_root, work, source_modules, roots)
            if generated['status'] != 'PASS':
                failures.append('Source spec generation failed')
            else:
                generated['generated_spec_path'] = str(
                    Path(work) / 'source-harness/q4.spec.json')
                cases = spec_cases(source_root, generated, roots)
                for case in cases:
                    if not case['sha256']:
                        failures.append(f'{case["name"]} spec is missing')
                if not failures:
                    for side, root, modules in (('baseline', baseline_root, baseline_modules),
                                                ('candidate', runtime_root, candidate_modules)):
                        runs[side] = {}
                        for case in cases:
                            run = run_runtime_case(side, root, modules, case, work, roots)
                            runs[side][case['name']] = run
                            if run['status'] != 'PASS':
                                failures.extend(run['failures'])
                    for case in cases:
                        comparison = compare_case(case, runs['baseline'][case['name']],
                                                  runs['candidate'][case['name']],
                                                  baseline_root, runtime_root)
                        comparisons[case['name']] = comparison
                        failures.extend(comparison['failures'])

        result = {
            'schema_version': contract['candidate_version'],
            'status': 'PASS' if not failures else 'FAIL',
            'gate': 'installed_candidate_runtime_vs_locked_v1_3_1_runtime',
            'capability_parity': CONTRACT_NAME,
            'contract': contract,
            'source_harness': {
                'root': '<SOURCE_ROOT>',
                'evidence': source,
                'spec_data': generated,
                'cases': [{'name': case['name'], 'kind': case['kind'],
                           'origin': case['origin'], 'sha256': case['sha256']}
                          for case in cases],
                'note': ('Spec JSON is generated or supplied by the Source tree and passed to both '
                         'installed runtimes as input data. The harness does not import or execute '
                         'code from an installed runtime root.'),
            },
            'installed_runtime': {
                'baseline': {
                    'root': '<BASELINE_ROOT>',
                    'evidence': baseline,
                    'node_modules': '<BASELINE_NODE_MODULES>' if baseline_modules else None,
                },
                'candidate': {
                    'root': '<CANDIDATE_ROOT>',
                    'evidence': candidate,
                    'node_modules': '<CANDIDATE_NODE_MODULES>' if candidate_modules else None,
                },
                'python': {
                    'executable': str(Path(sys.executable).name),
                    'version': sys.version.split()[0],
                    'isolated_prefix': sys.prefix != sys.base_prefix,
                },
                'same_host': True,
                'commands': {side: {name: run['commands'] for name, run in side_runs.items()}
                             for side, side_runs in runs.items()},
            },
            'comparisons': comparisons,
            'failures': failures,
            'visual_qa': 'NOT_RUN',
            'company_platform_security': 'NOT_VERIFIED',
            'note': ('Actual installed-runtime CLI runs with Source-owned Spec input. Native PPTX, '
                     'scene, QA JSON and same-host rendered pixels are compared to the locked v1.3.1 '
                     'Runtime ZIP. This is not visual approval or enterprise-platform acceptance.'),
        }
        result = sanitize_value(result, roots)
        payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.json:
            output = Path(args.json)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding='utf-8')
        print(payload, end='')
        return 0 if result['status'] == 'PASS' else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
