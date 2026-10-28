#!/usr/bin/env python3
"""Check deterministic runtime, full-source and optional showcase archives."""
import hashlib
import importlib.util
import json
import posixpath
import re
import shutil
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
# V1.3.2 moved exactly these four members from Runtime to Source-only.
SOURCE_ONLY_MEMBERS = (
    'scripts/security_preflight.py',
    'scripts/package_runtime.py',
    'skill/reasoning/fixtures/hostile-source/plan.json',
    'skill/reasoning/fixtures/hostile-source/sources/hostile.md',
)
EXPECTED_RUNTIME_DECLARED = 185
EXPECTED_RUNTIME_MEMBERS = 186
SOURCE_ONLY_COMMANDS = ('package', 'preflight')
PRODUCTION_COMMANDS = ('validate:all', 'test', 'test:core')
SOURCE_RELEASE_COMMANDS = ('package', 'package:source', 'preflight',
                           'security:scan', 'security:verify', 'test:pdf')


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
    for omitted in ('benchmark', 'benchmark:v13', 'fixtures', 'fixtures:phase2', 'showcase',
                    'package:showcase') + SOURCE_ONLY_COMMANDS:
        assert omitted not in scripts, omitted
    for required in PRODUCTION_COMMANDS:
        assert required in scripts, required
    # Source keeps the release/security commands the runtime omits.
    for required in SOURCE_RELEASE_COMMANDS:
        assert required in source_package['scripts'], required
    for command in scripts.values():
        for match in re.finditer(r'(?:^|\s)(?:python3|node)\s+([A-Za-z0-9_./-]+)', command):
            target = match.group(1)
            if target.startswith('out/'):
                continue
            assert PREFIX + target in names, f'runtime command references missing member {target}'


def run_repack(packager, out, root, expect_sha256=None, extra=()):
    command = [sys.executable, str(packager), str(out), '--runtime-root', str(root)]
    if expect_sha256 is not None:
        command += ['--expect-sha256', expect_sha256]
    command += list(extra)
    return subprocess.run(command, capture_output=True, text=True)


def assert_source_only_repack_guards(temp, install_root, packager, digest):
    def copy_case(name):
        target = temp / name
        shutil.copytree(install_root, target)
        return target

    tampered = copy_case('runtime-tampered')
    skill = tampered / 'SKILL.md'
    skill.write_bytes(skill.read_bytes() + b'\ntampered\n')
    result = run_repack(packager, temp / 'tampered.zip', tampered, expect_sha256=digest)
    assert result.returncode != 0, 'expected-SHA repack accepted a tampered member'
    assert 'does not match the expected' in result.stderr, result.stderr

    metadata = copy_case('runtime-metadata')
    manifest = metadata / 'distribution/runtime-manifest.json'
    manifest.write_bytes(manifest.read_bytes() + b' ')
    result = run_repack(packager, temp / 'metadata.zip', metadata)
    assert result.returncode != 0, 'repack accepted metadata that differs from the Source identity'
    assert 'approved Source identity' in result.stderr, result.stderr

    extra = copy_case('runtime-extra')
    (extra / 'stowaway.js').write_text('x = 1\n', encoding='utf-8')
    result = run_repack(packager, temp / 'extra.zip', extra)
    assert result.returncode != 0, 'repack accepted a file outside the manifest'
    assert 'outside the approved manifest' in result.stderr, result.stderr

    missing = copy_case('runtime-missing')
    (missing / 'skill/scripts/build_deck.js').unlink()
    result = run_repack(packager, temp / 'missing.zip', missing)
    assert result.returncode != 0, 'repack accepted a missing member'
    assert 'missing or not a regular file' in result.stderr, result.stderr

    linked = copy_case('runtime-symlink')
    target = linked / 'skill/scripts/build_deck.js'
    target.unlink()
    target.symlink_to(ROOT / 'skill/scripts/build_deck.js')
    result = run_repack(packager, temp / 'symlink.zip', linked)
    assert result.returncode != 0, 'repack accepted a symlinked member'
    assert 'symlink' in result.stderr.lower(), result.stderr

    result = run_repack(packager, install_root / 'inside.zip', install_root)
    assert result.returncode != 0, 'repack wrote output inside the installed runtime'
    assert 'must not be written inside' in result.stderr, result.stderr

    for flag in ('--source', '--showcase'):
        result = run_repack(packager, temp / 'mixed.zip', install_root, extra=(flag,))
        assert result.returncode != 0, f'--runtime-root accepted {flag}'
        assert 'cannot be combined' in result.stderr, result.stderr

    result = run_repack(packager, temp / 'badsha.zip', install_root, expect_sha256='not-a-digest')
    assert result.returncode != 0, 'repack accepted a malformed expected SHA'
    assert 'lowercase 64-character' in result.stderr, result.stderr

    result = subprocess.run([sys.executable, str(packager), '--runtime-root', str(install_root)],
                            capture_output=True, text=True)
    assert result.returncode != 0, 'repack accepted a missing output path'
    assert 'explicit output path' in result.stderr, result.stderr


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
        assert len(manifest['runtime_files']) == EXPECTED_RUNTIME_DECLARED, len(manifest['runtime_files'])
        assert len(names) == EXPECTED_RUNTIME_MEMBERS, len(names)
        expected = {PREFIX + item for item in manifest['runtime_files']} | {PREFIX + 'package.json'}
        assert set(names) == expected, 'runtime archive members differ from the explicit manifest + package mapping'
        assert {PREFIX + item for item in REQUIRED_RUNTIME} <= set(names)
        for relative in SOURCE_ONLY_MEMBERS:
            assert relative not in manifest['runtime_files'], relative
            assert PREFIX + relative not in set(names), relative
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
        install_root = extracted / 'goujian-strategy-slides'
        source_packager = ROOT / 'scripts/package_runtime.py'
        digest = hashlib.sha256(first.read_bytes()).hexdigest()
        repacked = temp / 'repacked.zip'
        result = subprocess.run([sys.executable, str(source_packager), str(repacked),
                                 '--runtime-root', str(install_root),
                                 '--expect-sha256', digest, '--json'],
                                cwd=temp, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert hashlib.sha256(repacked.read_bytes()).hexdigest() == digest, \
            'runtime archive is not reproducible from the installed runtime payload'
        assert json.loads(result.stdout)['entries'] == EXPECTED_RUNTIME_MEMBERS
        assert_source_only_repack_guards(temp, install_root, source_packager, digest)

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
