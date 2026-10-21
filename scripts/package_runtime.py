#!/usr/bin/env python3
"""Build deterministic Goujian ZIPs: lightweight installer plus optional showcase."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides'
INCLUDE = ['SKILL.md', 'core', 'skill', 'adapters', 'docs', 'tests', 'scripts', '.github',
           'package.json', 'package-lock.json', 'requirements-render.txt', 'README.md',
           'README.zh-CN.md', 'README.en.md', 'CONTRIBUTING.md', 'CHANGELOG.md', 'LICENSE',
           'THIRD_PARTY_NOTICE.md', '.gitignore']
EXCLUDE_DIRS = {'node_modules', '.venv', 'venv', 'out', 'dist', 'build', '__pycache__', '.git',
                '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', '.scratch', '.qoder'}
FORBIDDEN_NAMES = {'.env', '.env.local', '.npmrc', '.netrc', '.DS_Store', 'id_rsa', 'id_ed25519'}
FORBIDDEN_SUFFIXES = ('.pyc', '.pem', '.key', '.p12', '.pfx', '.zip')
SHOWCASE_REL = Path('out/v1.2-showcase')
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
FILE_MODE = 0o644


def fail(message):
    raise ValueError(message)


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


def build(out, showcase=False):
    skill_entries = [p for p in ROOT.rglob('SKILL.md')
                     if not (set(p.relative_to(ROOT).parts) & EXCLUDE_DIRS)]
    if skill_entries != [ROOT / 'SKILL.md']:
        fail(f'Expected only root SKILL.md; found: {[str(p.relative_to(ROOT)) for p in skill_entries]}')
    files = []
    for rel in INCLUDE:
        files.extend(collect(ROOT / rel, include_pptx=False))
    if showcase:
        showcase_root = ROOT / SHOWCASE_REL
        if not showcase_root.is_dir():
            fail(f'Showcase subtree not found: {SHOWCASE_REL.as_posix()}')
        files.extend(collect(showcase_root, include_pptx=True, allow_out=True))
    entries = {}
    for source in files:
        archive_name = f'{PREFIX}/{(source.relative_to(ROOT)).as_posix()}'
        if archive_name in entries:
            fail(f'Duplicate archive entry: {archive_name}')
        entries[archive_name] = source
    ordered = sorted(entries)
    if [name for name in ordered if name.endswith('/SKILL.md')] != [f'{PREFIX}/SKILL.md']:
        fail('Archive must contain exactly one root SKILL.md')
    if any(name.startswith('/') or '/../' in name or name.startswith('../') for name in ordered):
        fail('Archive contains an unsafe path')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ordered:
            write_entry(archive, entries[name], name)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    with zipfile.ZipFile(out) as archive:
        if archive.testzip() is not None:
            fail('Archive integrity check failed')
        names = archive.namelist()
        if len(names) != len(set(names)):
            fail('Archive contains duplicate entries')
        if any(info.is_dir() for info in archive.infolist()):
            fail('Archive unexpectedly contains directory entries')
    return {'archive': str(out), 'entries': len(ordered), 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', nargs='?', help='ZIP output path')
    parser.add_argument('--showcase', action='store_true',
                        help='Include the approved out/v1.2-showcase subtree (PPTX/render/QA assets)')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    args = parser.parse_args()
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    suffix = '-showcase' if args.showcase else ''
    out = Path(args.out) if args.out else ROOT / 'dist' / f'goujian-strategy-slides-v{version}{suffix}.zip'
    result = build(out, showcase=args.showcase)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result['archive'])
        print(f"entries={result['entries']} sha256={result['sha256']}")


if __name__ == '__main__':
    main()
