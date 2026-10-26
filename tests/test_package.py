#!/usr/bin/env python3
"""Check deterministic runtime, full-source and optional showcase archives."""
import hashlib
import importlib.util
import json
import posixpath
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
MAPPING_FIELDS = ('name', 'version', 'license', 'dependencies', 'engines', 'overrides', 'repository')
REQUIRED_RUNTIME = {
    'core/analytics/index.js', 'core/schema/analytics.schema.json', 'scripts/analyze.js',
    'skill/analytics/business-performance.json', 'skill/analytics/sales-conversion.json',
    'skill/analytics/project-analytics.json', 'SKILL.md', 'package.json', 'package-lock.json',
    'core/renderer/index.js', 'core/schema/deck.schema.json',
    'skill/storylines/registry.json', 'skill/archetypes/registry.json',
    'skill/compositions/registry.json', 'skill/templates/registry.json',
    'skill/profiles/executive-clean/profile.json',
    'skill/scripts/build_deck.js', 'skill/scripts/quality_gate.py',
    'skill/examples/executive-review.json', 'skill/examples/assets/channel-evidence.png',
    'skill/reasoning/fixtures/q4-six-actions/plan.json',
    'core/__init__.py', 'core/qa/__init__.py', 'core/qa/spec_check.py', 'core/qa/spec-check.py',
    'core/qa/recompute_analytics.js', 'skill/__init__.py', 'skill/scripts/__init__.py',
    'scripts/probe_env.py', 'scripts/runtime_smoke.py', 'tests/validate_examples.py',
    'distribution/runtime-manifest.json', 'distribution/runtime-package.json',
}


def load_packager():
    spec = importlib.util.spec_from_file_location('goujian_package_runtime', ROOT / 'scripts/package_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive_names(archive, allow_out=False):
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        names = package.namelist()
        assert len(names) == len(set(names))
        assert [name for name in names if name.endswith('/SKILL.md')] == [PREFIX + 'SKILL.md']
        assert not any('/node_modules/' in name or '/.venv/' in name for name in names)
        if not allow_out:
            assert not any('/out/' in name for name in names)
        for info in package.infolist():
            assert info.date_time == (2026, 1, 1, 0, 0, 0), info.filename
            assert (info.external_attr >> 16) & 0o777 == 0o644, info.filename
        return names


def local_markdown_links(text):
    for match in re.finditer(r'\[[^\]]*\]\(\s*<?([^)>\s]+)>?(?:\s+"[^"]*")?\s*\)', text):
        target = match.group(1)
        if target.startswith(('http://', 'https://', 'mailto:', '#', '/')):
            continue
        target = unquote(target).split('#', 1)[0].split('?', 1)[0]
        if target:
            yield target


def resolve_member(base_dir, target):
    return posixpath.normpath(posixpath.join(base_dir, target))


def assert_runtime_closure(archive, names):
    member_set = set(names)
    for name in names:
        relative = name[len(PREFIX):]
        if relative.endswith('.md'):
            with zipfile.ZipFile(archive) as package:
                text = package.read(name).decode('utf-8', errors='replace')
            for target in local_markdown_links(text):
                resolved = resolve_member(posixpath.dirname(relative), target)
                assert not resolved.startswith('..'), f'{relative} links outside the archive: {target}'
                assert PREFIX + resolved in member_set, f'{relative} links to missing runtime member {resolved}'
        if relative.endswith('.js'):
            with zipfile.ZipFile(archive) as package:
                text = package.read(name).decode('utf-8', errors='replace')
            for match in re.finditer(r"require\((['\"])([^'\"]+)\1\)", text):
                target = match.group(2)
                if not target.startswith('.'):
                    continue
                base = resolve_member(posixpath.dirname(relative), target)
                candidates = {base, base + '.js', base + '.json', base + '/index.js'}
                assert any(PREFIX + item in member_set for item in candidates), \
                    f'{relative} requires missing runtime member {target}'
        if relative.startswith('skill/examples/') and relative.endswith('.json') and '/v1.3/' not in '/' + relative:
            with zipfile.ZipFile(archive) as package:
                spec = json.loads(package.read(name))
            for asset in spec.get('assets') or []:
                if not isinstance(asset, dict) or 'path' not in asset:
                    continue
                resolved = resolve_member(posixpath.dirname(relative), asset['path'])
                assert PREFIX + resolved in member_set, f'{relative} references missing asset {resolved}'


def assert_runtime_commands(archive):
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        runtime_package = json.loads(package.read(PREFIX + 'package.json'))
        source_package = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))
    for field in MAPPING_FIELDS:
        assert runtime_package[field] == source_package[field], f'runtime package mapping differs: {field}'
    scripts = runtime_package['scripts']
    for omitted in ('benchmark', 'benchmark:v13', 'fixtures', 'fixtures:phase2', 'showcase', 'package:showcase'):
        assert omitted not in scripts
    for required in ('validate:all', 'package', 'preflight', 'test', 'test:core'):
        assert required in scripts
    for command in scripts.values():
        for match in re.finditer(r'(?:^|\s)(?:python3|node)\s+([A-Za-z0-9_./-]+)', command):
            target = match.group(1)
            if target.startswith('out/'):
                continue
            assert PREFIX + target in names, f'runtime command references missing member {target}'


def main():
    assert not (ROOT / 'skill/SKILL.md').exists()
    sys.path.insert(0, str(ROOT))
    from scripts import runtime_smoke
    try:
        runtime_smoke.require(subprocess.CompletedProcess(['renderer'], 2, '', 'conversion failed'),
                              'multimodal render')
    except runtime_smoke.SmokeError as error:
        assert 'conversion failed' in str(error)
    else:
        raise AssertionError('Runtime smoke accepted a failed render command')
    packager = load_packager()
    assert packager.SHOWCASE_REL == Path('out/v1.3-showcase')
    manifest = json.loads((ROOT / 'distribution/runtime-manifest.json').read_text(encoding='utf-8'))
    runtime_package = json.loads((ROOT / 'distribution/runtime-package.json').read_text(encoding='utf-8'))
    source_package = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))
    for field in MAPPING_FIELDS:
        assert runtime_package[field] == source_package[field], f'runtime manifest differs from package.json: {field}'

    with tempfile.TemporaryDirectory(prefix='goujian-manifest-boundary-') as temp:
        original_root = packager.ROOT
        packager.ROOT = Path(temp) / 'root'
        packager.ROOT.mkdir()
        outside = Path(temp) / 'outside.json'
        outside.write_text('{}', encoding='utf-8')
        (packager.ROOT / 'linked.json').symlink_to(outside)
        (packager.ROOT / 'linked-dir').symlink_to(Path(temp), target_is_directory=True)
        try:
            for unsafe in ('../outside.json', str(outside), 'C:/outside.json',
                           './inside.json', 'a//b', 'a\\b', 'linked.json', 'linked-dir/outside.json'):
                try:
                    packager.manifest_source(unsafe)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f'Unsafe manifest source accepted: {unsafe}')
        finally:
            packager.ROOT = original_root

    with tempfile.TemporaryDirectory(prefix='goujian-package-test-') as temp:
        temp = Path(temp)
        first, second = temp / 'runtime-first.zip', temp / 'runtime-second.zip'
        result = subprocess.run([sys.executable, 'scripts/package_runtime.py', str(first), '--json'],
                                cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        result = subprocess.run([sys.executable, 'scripts/package_runtime.py', str(second)],
                                cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(second.read_bytes()).hexdigest()

        names = archive_names(first)
        expected = {PREFIX + item for item in manifest['runtime_files']} | {PREFIX + 'package.json'}
        assert set(names) == expected, 'runtime archive members differ from the explicit manifest + package mapping'
        assert {PREFIX + item for item in REQUIRED_RUNTIME} <= set(names)
        assert not any(name.startswith(PREFIX + 'tests/test_') for name in names)
        assert not any(name.endswith(('.pptx', '.pdf')) for name in names)
        with zipfile.ZipFile(first) as package:
            assert package.read(PREFIX + 'package.json') == (ROOT / 'distribution/runtime-package.json').read_bytes()
            frontmatter = package.read(PREFIX + 'SKILL.md').decode('utf-8').split('---', 2)[1]
            assert 'name: goujian-strategy-slides' in frontmatter
            assert f'version: "{source_package["version"]}"' in frontmatter
        assert_runtime_commands(first)
        assert_runtime_closure(first, names)

        extracted = temp / 'runtime-extracted'
        with zipfile.ZipFile(first) as package:
            package.extractall(extracted)
        repacked = extracted / 'repacked.zip'
        result = subprocess.run([sys.executable, 'scripts/package_runtime.py', str(repacked), '--json'],
                                cwd=extracted / 'goujian-strategy-slides', capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(repacked.read_bytes()).hexdigest(), \
            'runtime archive is not reproducible from its own declared payload'

        source = temp / 'source.zip'
        result = subprocess.run([sys.executable, 'scripts/package_runtime.py', str(source), '--source', '--json'],
                                cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        source_names = archive_names(source)
        with zipfile.ZipFile(source) as package:
            assert package.read(PREFIX + 'package.json') == (ROOT / 'package.json').read_bytes()
        for required in ('tests/test_contract.js', '.github/workflows/release.yml',
                         'scripts/benchmark.py', 'docs/INSTALLATION.md'):
            assert PREFIX + required in source_names
        assert not any(name.endswith(('.pptx', '.pdf')) for name in source_names)

        fake = ROOT / 'out' / '.package-test-showcase'
        try:
            (fake / 'decks').mkdir(parents=True)
            (fake / 'decks' / 'example.pptx').write_bytes(b'not-a-real-pptx')
            (fake / 'readme.txt').write_text('showcase fixture\n', encoding='utf-8')
            packager.SHOWCASE_REL = Path('out/.package-test-showcase')
            showcase = temp / 'showcase.zip'
            result = packager.build(showcase, showcase=True)
            assert result['mode'] == 'showcase' and result['entries'] > 0
            showcase_names = archive_names(showcase, allow_out=True)
            assert PREFIX + 'out/.package-test-showcase/decks/example.pptx' in showcase_names
            assert PREFIX + 'out/.package-test-showcase/readme.txt' in showcase_names
            marker = PREFIX + 'out/.package-test-showcase/REVIEW_ARTIFACT.md'
            assert marker in showcase_names
            with zipfile.ZipFile(showcase) as package:
                marker_text = package.read(marker).decode('utf-8')
                assert 'installation_required: false' in marker_text
                assert 'recommended' not in marker_text.lower()
                assert package.read(PREFIX + 'package.json') == (ROOT / 'distribution/runtime-package.json').read_bytes()
                assert not any(name.startswith(PREFIX + 'out/') and not name.startswith(PREFIX + 'out/.package-test-showcase/')
                               for name in showcase_names)
        finally:
            for path in sorted(fake.rglob('*'), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            if fake.exists():
                fake.rmdir()
    print('PASS: deterministic runtime/source package, explicit manifest, mapping/closure, repack, one Skill and optional showcase')


if __name__ == '__main__':
    main()
