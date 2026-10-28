#!/usr/bin/env python3
"""Build deterministic Goujian ZIPs.

Default output is the minimal runtime payload declared by
`distribution/runtime-manifest.json`; its archive `package.json` is mapped from
`distribution/runtime-package.json`. `--source` builds the complete
source/development archive with the root package.json and full test workflow.
`--showcase` adds the review-only `out/v1.3-showcase` subtree to the runtime.
`--runtime-root PATH` repackages an already extracted installed runtime as
data, using the Source manifest and this Source implementation only.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides'
SOURCE_INCLUDE = ['SKILL.md', 'core', 'skill', 'adapters', 'docs', 'tests', 'scripts', 'security',
                  '.github', 'distribution', 'package.json', 'package-lock.json',
                  'requirements-render.txt', 'README.md', 'README.zh-CN.md', 'README.en.md',
                  'CONTRIBUTING.md', 'AGENTS.md', 'CHANGELOG.md', 'LICENSE', 'THIRD_PARTY_NOTICE.md',
                  '.gitignore']
EXCLUDE_DIRS = {'node_modules', '.venv', '.venv-security', 'venv', 'out', 'dist', 'build', '__pycache__', '.git',
                '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', '.scratch', '.qoder'}
FORBIDDEN_NAMES = {'.env', '.env.local', '.npmrc', '.netrc', '.DS_Store', 'id_rsa', 'id_ed25519'}
FORBIDDEN_SUFFIXES = ('.pyc', '.pem', '.key', '.p12', '.pfx', '.zip')
SHOWCASE_REL = Path('out/v1.3-showcase')
RUNTIME_MANIFEST = Path('distribution/runtime-manifest.json')
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
FILE_MODE = 0o644
MAPPING_FIELDS = ('name', 'version', 'license', 'dependencies', 'engines', 'overrides', 'repository')
INSTALL_STATE_DIRS = EXCLUDE_DIRS


def fail(message):
    raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def manifest_source(relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or any(ord(char) < 32 for char in relative)
            or relative.startswith('/') or re.match(r'^[A-Za-z]:', relative)
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        fail(f'Unsafe runtime manifest path: {relative!r}')
    path = ROOT
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            fail(f'Refusing symlink in runtime manifest path: {relative}')
    if not path.is_file():
        fail(f'Declared runtime file is missing or not a regular file: {relative}')
    return path


def installed_root(path):
    root = Path(path)
    if root.is_symlink():
        fail('Installed runtime root must not be a symlink')
    if not root.is_dir():
        fail(f'Installed runtime root is not a directory: {root}')
    return root


def installed_member(root, relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or any(ord(char) < 32 for char in relative)
            or relative.startswith('/') or re.match(r'^[A-Za-z]:', relative)
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        fail(f'Unsafe installed runtime path: {relative!r}')
    path = Path(root)
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            fail(f'Refusing symlink in installed runtime: {relative}')
    if not path.is_file():
        fail(f'Installed runtime member is missing or not a regular file: {relative}')
    return path


def installed_extras(root, expected):
    extras = []
    for path in sorted(Path(root).rglob('*')):
        relative = path.relative_to(root).as_posix()
        parts = relative.split('/')
        if any(part in INSTALL_STATE_DIRS for part in parts[:-1]):
            continue
        if path.is_symlink():
            fail(f'Refusing symlink in installed runtime: {relative}')
        if not path.is_file() or relative in expected or relative.endswith('.pyc'):
            continue
        extras.append(relative)
    return extras


def protected_source_paths(entries):
    protected = {Path(__file__).resolve()}
    for relative in ('package.json', RUNTIME_MANIFEST, 'distribution/runtime-package.json',
                     'SKILL.md', 'package-lock.json'):
        protected.add((ROOT / relative).resolve())
    for name, value in (entries or {}).items():
        if isinstance(value, (str, Path)):
            protected.add(Path(value).resolve())
        if name.startswith(PREFIX + '/'):
            canonical = ROOT / name[len(PREFIX) + 1:]
            if canonical.is_file():
                protected.add(canonical.resolve())
    return protected


def validate_output_location(out, root=None, entries=None):
    out_resolved = Path(out).resolve()
    if root is not None:
        root_resolved = Path(root).resolve()
        if out_resolved == root_resolved or root_resolved in out_resolved.parents:
            fail('Output ZIP must not be written inside the installed runtime root')
    if out_resolved in protected_source_paths(entries):
        fail(f'Output ZIP must not overwrite a Source input or the active packager: {out}')


def allowed_path(path, include_pptx, allow_out=False):
    rel = path.relative_to(ROOT)
    parts = set(rel.parts)
    excluded = EXCLUDE_DIRS - ({'out'} if allow_out else set())
    if parts & excluded:
        return False
    if path.is_symlink():
        fail(f'Refusing symlink in archive input: {rel}')
    if path.name in FORBIDDEN_NAMES or path.name.startswith(('.env.', 'credentials', 'secrets')):
        fail(f'Refusing private or secret-like file: {rel}')
    if path.name.endswith(FORBIDDEN_SUFFIXES):
        return False
    if not include_pptx and path.suffix.lower() in ('.pptx', '.pdf'):
        return False
    return True


def collect(path, include_pptx, allow_out=False):
    if path.is_symlink():
        fail(f'Refusing symlink in archive input: {path}')
    if path.is_dir():
        found = []
        for child in sorted(path.rglob('*')):
            if not allowed_path(child, include_pptx, allow_out):
                continue
            if child.is_file():
                found.append(child)
        return found
    if path.exists():
        return [path] if allowed_path(path, include_pptx, allow_out) else []
    fail(f'Required archive input is missing: {path.relative_to(ROOT)}')


def write_entry(archive, source, archive_name):
    data = source.read_bytes()
    info = zipfile.ZipInfo(archive_name, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = FILE_MODE << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def load_runtime_manifest():
    manifest = read_json(manifest_source(RUNTIME_MANIFEST.as_posix()))
    if manifest.get('distribution') != 'runtime':
        fail('Runtime manifest must declare distribution=runtime')
    mapping = manifest.get('package_mapping') or {}
    if mapping.get('archive_path') != 'package.json':
        fail('Runtime package mapping must target archive package.json')
    manifest_source(mapping.get('source_path'))
    files = manifest.get('runtime_files')
    if not isinstance(files, list) or not files or not all(isinstance(item, str) for item in files):
        fail('Runtime manifest must declare a nonempty file list')
    if len(files) != len(set(files)) or 'package.json' in files:
        fail('Duplicate runtime manifest entry or mapped package.json collision')
    return manifest


def compare_package_mapping(source_package, runtime_package):
    mismatches = []
    for field in MAPPING_FIELDS:
        if source_package.get(field) != runtime_package.get(field):
            mismatches.append(field)
    if mismatches:
        fail(f'Runtime package mapping differs from package.json for: {", ".join(mismatches)}')


def runtime_script_targets(command):
    targets = []
    for match in re.finditer(r'(?:^|\s)(?:python3|node)\s+([A-Za-z0-9_./-]+)', command):
        target = match.group(1)
        if target.startswith('-'):
            continue
        if target.endswith(('.py', '.js')):
            targets.append(target)
    return targets


def validate_runtime_commands(manifest, entries):
    package = read_json(manifest_source(manifest['package_mapping']['source_path']))
    scripts = package.get('scripts') or {}
    omitted = manifest.get('omitted_commands') or []
    for name in omitted:
        if name in scripts:
            fail(f'Development command must be omitted from the runtime manifest: {name}')
    for name in ('package', 'preflight'):
        if name not in omitted:
            fail(f'Runtime manifest must declare the Source-only command as omitted: {name}')
    archive_targets = {name for name in entries if name.startswith(PREFIX + '/')}
    for name, command in scripts.items():
        for target in runtime_script_targets(command):
            if target.startswith('out/'):
                continue
            archive_name = f'{PREFIX}/{target}'
            if archive_name not in archive_targets:
                fail(f'Runtime command {name!r} references missing payload member: {target}')
    for required in ('validate:all', 'test', 'test:core'):
        if required not in scripts:
            fail(f'Runtime manifest must keep production command: {required}')


def runtime_entries(showcase=False):
    manifest = load_runtime_manifest()
    entries = {}
    for rel in manifest.get('runtime_files') or []:
        source = manifest_source(rel)
        if not allowed_path(source, include_pptx=False):
            fail(f'Declared runtime file is excluded by policy: {rel}')
        entries[f'{PREFIX}/{rel}'] = source
    mapping = manifest['package_mapping']
    mapped = manifest_source(mapping['source_path'])
    entries[f'{PREFIX}/{mapping["archive_path"]}'] = mapped
    compare_package_mapping(read_json(ROOT / 'package.json'), read_json(mapped))
    validate_runtime_commands(manifest, entries)
    if showcase:
        entries.update(showcase_entries(manifest))
    return entries, manifest


def runtime_root_entries(root):
    manifest = load_runtime_manifest()
    mapping = manifest['package_mapping']
    identities = {
        RUNTIME_MANIFEST.as_posix(): manifest_source(RUNTIME_MANIFEST.as_posix()),
        mapping['source_path']: manifest_source(mapping['source_path']),
    }
    for relative, source in identities.items():
        installed = installed_member(root, relative)
        if installed.read_bytes() != source.read_bytes():
            fail(f'Installed runtime metadata differs from the approved Source identity: {relative}')
    package_path = installed_member(root, mapping['archive_path'])
    if package_path.read_bytes() != identities[mapping['source_path']].read_bytes():
        fail('Installed runtime package.json differs from distribution/runtime-package.json')
    package = read_json(package_path)
    compare_package_mapping(read_json(ROOT / 'package.json'), package)
    if manifest.get('schema_version') != package.get('version'):
        fail('Runtime manifest schema_version does not match the installed runtime version')
    entries = {}
    expected = set()
    for relative in manifest.get('runtime_files') or []:
        installed = installed_member(root, relative)
        canonical = manifest_source(relative)
        if installed.read_bytes() != canonical.read_bytes():
            fail(f'Installed runtime payload differs from the approved Source bytes: {relative}')
        entries[f'{PREFIX}/{relative}'] = installed
        expected.add(relative)
    entries[f'{PREFIX}/{mapping["archive_path"]}'] = package_path
    expected.add(mapping['archive_path'])
    extras = installed_extras(root, expected)
    if extras:
        fail('Installed runtime contains files outside the approved manifest: ' + ', '.join(extras[:5]))
    validate_runtime_commands(manifest, entries)
    return entries



def showcase_entries(manifest):
    showcase_root = ROOT / SHOWCASE_REL
    if not showcase_root.is_dir():
        fail(f'Showcase subtree not found: {SHOWCASE_REL.as_posix()}')
    entries = {}
    for source in collect(showcase_root, include_pptx=True, allow_out=True):
        entries[f'{PREFIX}/{source.relative_to(ROOT).as_posix()}'] = source
    version = read_json(ROOT / 'package.json')['version']
    marker = f'{PREFIX}/{(SHOWCASE_REL / Path(manifest["showcase"]["archive_marker"]).name).as_posix()}'
    entries[marker] = (
        f'# Showcase review artifact\n\n'
        f'- product: Goujian Strategy Slides\n'
        f'- version: {version}\n'
        f'- installation_required: false\n'
        f'- purpose: Frozen review evidence only. Install from the runtime ZIP without this subtree.\n'
    ).encode('utf-8')
    return entries


def source_entries():
    skill_entries = [p for p in ROOT.rglob('SKILL.md')
                     if not (set(p.relative_to(ROOT).parts) & EXCLUDE_DIRS)]
    if skill_entries != [ROOT / 'SKILL.md']:
        fail(f'Expected only root SKILL.md; found: {[str(p.relative_to(ROOT)) for p in skill_entries]}')
    entries = {}
    for rel in SOURCE_INCLUDE:
        for source in collect(ROOT / rel, include_pptx=False):
            entries[f'{PREFIX}/{source.relative_to(ROOT).as_posix()}'] = source
    return entries


def write_entries(out, entries):
    ordered = sorted(entries)
    if [name for name in ordered if name.endswith('/SKILL.md')] != [f'{PREFIX}/SKILL.md']:
        fail('Archive must contain exactly one root SKILL.md')
    if any(name.startswith('/') or '/../' in name or name.startswith('../') for name in ordered):
        fail('Archive contains an unsafe path')
    if len(ordered) != len(set(ordered)):
        fail('Archive contains duplicate entries')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ordered:
            value = entries[name]
            if isinstance(value, bytes):
                info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = FILE_MODE << 16
                archive.writestr(info, value, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            else:
                write_entry(archive, value, name)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    with zipfile.ZipFile(out) as archive:
        if archive.testzip() is not None:
            fail('Archive integrity check failed')
        names = archive.namelist()
        if len(names) != len(set(names)):
            fail('Archive contains duplicate entries')
        if any(info.is_dir() for info in archive.infolist()):
            fail('Archive unexpectedly contains directory entries')
    return digest, len(ordered)


def build(out, showcase=False, source=False, runtime_root=None, expect_sha256=None):
    root = None
    if runtime_root is not None:
        if source or showcase:
            fail('--runtime-root cannot be combined with --source or --showcase')
        root = installed_root(runtime_root)
        entries = runtime_root_entries(root)
        mode = 'runtime'
    elif showcase and source:
        fail('--source and --showcase are mutually exclusive')
    elif source:
        entries = source_entries()
        mode = 'source'
    else:
        entries, _manifest = runtime_entries(showcase=showcase)
        mode = 'showcase' if showcase else 'runtime'
    validate_output_location(out, root, entries)
    digest, count = write_entries(out, entries)
    if expect_sha256 is not None and digest != expect_sha256:
        fail(f'Rebuilt archive SHA-256 {digest} does not match the expected {expect_sha256}')
    return {'archive': str(out), 'mode': mode, 'entries': count, 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', nargs='?', help='ZIP output path')
    parser.add_argument('--source', action='store_true',
                        help='Build the complete source/development archive instead of the runtime payload')
    parser.add_argument('--showcase', action='store_true',
                        help='Add the approved out/v1.3-showcase review artifact to the runtime payload')
    parser.add_argument('--runtime-root', metavar='PATH',
                        help='Repackage an extracted installed runtime directory as data; '
                             'requires an explicit output path and cannot be combined with --source/--showcase')
    parser.add_argument('--expect-sha256', metavar='HEX',
                        help='With --runtime-root, fail unless the rebuilt archive has this SHA-256')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    args = parser.parse_args()
    if args.runtime_root:
        if not args.out:
            parser.error('--runtime-root requires an explicit output path')
        if args.source or args.showcase:
            parser.error('--runtime-root cannot be combined with --source or --showcase')
        if args.expect_sha256 and not re.match(r'^[0-9a-f]{64}$', args.expect_sha256):
            parser.error('--expect-sha256 must be a lowercase 64-character SHA-256 digest')
    elif args.expect_sha256:
        parser.error('--expect-sha256 is only valid with --runtime-root')
    if args.runtime_root:
        out = Path(args.out)
    else:
        version = read_json(ROOT / 'package.json')['version']
        suffix = '-source' if args.source else ('-showcase' if args.showcase else '')
        out = Path(args.out) if args.out else ROOT / 'dist' / f'goujian-strategy-slides-v{version}{suffix}.zip'
    result = build(out, showcase=args.showcase, source=args.source,
                   runtime_root=args.runtime_root, expect_sha256=args.expect_sha256)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result['archive'])
        print(f"mode={result['mode']} entries={result['entries']} sha256={result['sha256']}")


if __name__ == '__main__':
    main()
