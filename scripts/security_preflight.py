#!/usr/bin/env python3
"""Preflight the actual Goujian installer ZIP before any release action.

Checks are intentionally direct and auditable:

* structure, one root SKILL.md, safe POSIX paths, duplicate names;
* Unix file mode and symlink flags, known static ZIP timestamps;
* full decompression of every member plus bounded zip-bomb guards;
* declared npm dependencies against the locked tree and the secure Pillow
  requirement;
* Python source through ``ast`` and JavaScript through a lexical
  string/comment stripper, so inert examples in strings, comments or escaped
  regexes are not misclassified as executable behaviour.

There is no per-file allowlist. Argument-array subprocess calls such as
``execFileSync(...)``/``subprocess.run([...])`` and list-based ``subprocess``
calls remain accepted; shell strings, ``shell=True``, ``os.system``,
``eval``/``exec``, ``new Function`` and ``child_process.exec`` are rejected.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
KNOWN_STATIC_DATETIME = (2026, 1, 1, 0, 0, 0)
REQUIRED_FILES = {
    'SKILL.md', 'README.md', 'README.zh-CN.md', 'README.en.md', 'LICENSE',
    'THIRD_PARTY_NOTICE.md', 'package.json', 'package-lock.json',
    'requirements-render.txt', 'core/renderer/index.js', 'core/renderer/charts.js',
    'core/schema/deck.schema.json', 'core/qa/secure_deps.py',
    'scripts/security_preflight.py', 'tests/test_security_preflight.py',
    'skill/scripts/build_deck.js',
}
FORBIDDEN_NAMES = {'.env', '.env.local', '.npmrc', '.netrc', '.DS_Store', 'id_rsa', 'id_ed25519'}
FORBIDDEN_SUFFIXES = ('.pyc', '.pem', '.key', '.p12', '.pfx', '.zip')
FORBIDDEN_DIRS = {'node_modules', '.venv', 'venv', '.git', '__pycache__', '.pytest_cache'}
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_RATIO = 1000
SUBPROCESS_NAMES = {'run', 'Popen', 'call', 'check_call', 'check_output'}
DANGEROUS_DOTTED = {'eval', 'exec', 'compile', 'builtins.eval', 'builtins.exec', 'builtins.compile',
                    'os.system', 'os.popen', 'pickle.load', 'pickle.loads', 'marshal.loads',
                    'yaml.load', 'yaml.unsafe_load'}
JS_PATTERNS = [
    ('EXEC', re.compile(r'(?<![.\w$])exec\s*\(')),
    ('EXEC_SYNC', re.compile(r'(?<![.\w$])execSync\s*\(')),
    ('CHILD_PROCESS_EXEC', re.compile(r'\b(?:child_process|childProcess|cp|proc)\s*\.\s*exec(?:Sync)?\s*\(')),
    ('CHILD_PROCESS_EXEC', re.compile(r'\)\s*\.\s*exec(?:Sync)?\s*\(')),
    ('SHELL_TRUE', re.compile(r'\bshell\s*:\s*true\b')),
    ('NEW_FUNCTION', re.compile(r'\bnew\s+Function\s*\(')),
    ('EVAL', re.compile(r'(?<![.\w$])eval\s*\(')),
    ('VM_EXEC', re.compile(r'\bvm\s*\.\s*run(?:InNewContext|InThisContext|InContext)?\s*\(')),
]


def finding(kind, member, line, detail):
    return {'kind': kind, 'member': member, 'line': line, 'detail': detail}


def violation(code, detail, member=None):
    return {'code': code, 'detail': detail, 'member': member}


def load_secure_deps():
    spec = importlib.util.spec_from_file_location('goujian_secure_deps', ROOT / 'core/qa/secure_deps.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unsafe_path_reason(name):
    if not name:
        return 'empty archive member name'
    if '\\' in name:
        return 'backslash path separator'
    if '\x00' in name or any(ord(char) < 32 for char in name):
        return 'control character in path'
    if name.startswith('/'):
        return 'absolute path'
    if re.match(r'^[A-Za-z]:', name):
        return 'Windows drive path'
    if '//' in name or re.search(r'(^|/)\.(/|$)', name):
        return 'empty or current path segment'
    if not name.startswith(PREFIX):
        return 'path outside the declared archive prefix'
    relative = name[len(PREFIX):]
    if not relative:
        return 'archive prefix without a file name'
    parts = PurePosixPath(relative).parts
    if any(part in ('', '.', '..') for part in parts):
        return 'empty, current or parent path segment'
    return None


def unix_mode(info):
    if info.create_system != 3:
        return None
    return (info.external_attr >> 16) & 0o170777


def is_symlink(info):
    mode = unix_mode(info)
    return bool(mode is not None and stat.S_ISLNK(mode))


def permission_reason(info):
    mode = unix_mode(info)
    if mode is None:
        return 'member does not carry a Unix mode'
    permissions = stat.S_IMODE(mode)
    if stat.S_ISLNK(mode):
        return None
    if permissions != 0o644:
        return f'expected file mode 0644, found {permissions:04o}'
    return None


def strip_javascript_noise(source):
    """Blank strings, templates and comments while preserving line numbers."""
    output = []
    index = 0
    length = len(source)
    state = 'code'
    quote = ''
    while index < length:
        char = source[index]
        if state == 'code':
            if source.startswith('//', index):
                state = 'line_comment'
                output.append('  ')
                index += 2
                continue
            if source.startswith('/*', index):
                state = 'block_comment'
                output.append('  ')
                index += 2
                continue
            if char in ("'", '"'):
                state = 'string'
                quote = char
                output.append(' ')
                index += 1
                continue
            if char == '`':
                state = 'template'
                output.append(' ')
                index += 1
                continue
            output.append(char)
            index += 1
            continue
        if state == 'line_comment':
            if char == '\n':
                state = 'code'
                output.append('\n')
            else:
                output.append(' ')
            index += 1
            continue
        if state == 'block_comment':
            if source.startswith('*/', index):
                state = 'code'
                output.append('  ')
                index += 2
            else:
                output.append('\n' if char == '\n' else ' ')
                index += 1
            continue
        escaped = char == '\\' and index + 1 < length
        if escaped:
            following = source[index + 1]
            output.append('\n' if following == '\n' else ' ')
            index += 2
            continue
        if state == 'string' and char == quote:
            state = 'code'
            output.append(' ')
            index += 1
            continue
        if state == 'template' and char == '`':
            state = 'code'
            output.append(' ')
            index += 1
            continue
        output.append('\n' if char == '\n' else ' ')
        index += 1
    return ''.join(output)


def line_of(text, position):
    return text.count('\n', 0, position) + 1


def scan_javascript_source(member, source):
    scrubbed = strip_javascript_noise(source)
    findings = []
    for kind, pattern in JS_PATTERNS:
        for match in pattern.finditer(scrubbed):
            findings.append(finding(kind, member, line_of(scrubbed, match.start()),
                                    f'JavaScript execution pattern {kind}'))
    return findings


def dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else node.attr
    return None


def keyword_value(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def scan_python_source(member, source):
    try:
        tree = ast.parse(source, filename=member)
    except SyntaxError as error:
        return [finding('PYTHON_SYNTAX', member, error.lineno or 0, 'Python source does not parse')]
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted_name(node.func)
        if not name:
            continue
        if name in DANGEROUS_DOTTED:
            kind = 'PYTHON_DYNAMIC_EXECUTION' if name.split('.')[-1] in {'eval', 'exec', 'compile'} else 'PYTHON_SHELL_EXECUTION'
            findings.append(finding(kind, member, node.lineno, f'dangerous call {name}'))
            continue
        parts = name.split('.')
        if parts[0] == 'subprocess' and parts[-1] in SUBPROCESS_NAMES:
            shell = keyword_value(node, 'shell')
            if shell is not None:
                if isinstance(shell, ast.Constant) and shell.value is False:
                    pass
                elif isinstance(shell, ast.Constant) and shell.value is True:
                    findings.append(finding('SHELL_TRUE', member, node.lineno, 'subprocess call enables a shell'))
                else:
                    findings.append(finding('SHELL_DYNAMIC', member, node.lineno, 'subprocess shell mode is not a literal False'))
            if node.args:
                command = node.args[0]
                if isinstance(command, ast.Constant) and isinstance(command.value, str):
                    findings.append(finding('STRING_COMMAND', member, node.lineno, 'subprocess receives a string command instead of an argument array'))
                elif isinstance(command, ast.JoinedStr):
                    findings.append(finding('STRING_COMMAND', member, node.lineno, 'subprocess receives an interpolated string command'))
    return findings


def parse_frontmatter(text):
    if not text.startswith('---'):
        return None, None
    end = text.find('\n---', 3)
    if end < 0:
        return None, None
    body = text[3:end].strip('\n')
    top, nested = {}, {}
    for line in body.splitlines():
        match = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if match:
            top[match.group(1)] = match.group(2).strip()
            continue
        match = re.match(r'^\s+([A-Za-z_][\w-]*):\s*(.*)$', line)
        if match:
            nested[match.group(1)] = match.group(2).strip()
    return top, nested


def unquote(value):
    text = str(value or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1]
    return text


def dependency_violations(package_text, lock_text, requirements_text):
    problems = []
    try:
        package = json.loads(package_text)
        lock = json.loads(lock_text)
    except (TypeError, ValueError) as error:
        return [violation('DEPENDENCY', f'dependency manifest is not valid JSON: {error}')]
    root_entry = lock.get('packages', {}).get('', {})
    version = package.get('version')
    if not version:
        problems.append(violation('DEPENDENCY', 'package.json has no version'))
    if lock.get('version') != version or root_entry.get('version') != version:
        problems.append(violation('DEPENDENCY', 'package.json and package-lock versions disagree'))
    dependencies = package.get('dependencies') or {}
    locked_dependencies = root_entry.get('dependencies') or {}
    if dependencies != locked_dependencies:
        problems.append(violation('DEPENDENCY', 'package.json dependencies differ from the lockfile root'))
    exact = re.compile(r'^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$')
    for name, declared in sorted(dependencies.items()):
        if not exact.match(str(declared)):
            problems.append(violation('DEPENDENCY', f'{name} is not pinned to an exact version', name))
            continue
        entry = (lock.get('packages') or {}).get(f'node_modules/{name}')
        if not entry:
            problems.append(violation('DEPENDENCY', f'{name} is missing from the locked tree', name))
            continue
        if entry.get('version') != declared:
            problems.append(violation('DEPENDENCY', f'{name} lock version {entry.get("version")} does not match {declared}', name))
        if entry.get('link'):
            problems.append(violation('DEPENDENCY', f'{name} is linked outside the package tree', name))
        if not entry.get('integrity'):
            problems.append(violation('DEPENDENCY', f'{name} has no lock integrity value', name))
        resolved = str(entry.get('resolved') or '')
        if not resolved.startswith('https://registry.npmjs.org/'):
            problems.append(violation('DEPENDENCY', f'{name} resolves outside the official npm registry', name))
    overrides = package.get('overrides') or {}
    for name, declared in sorted(overrides.items()):
        if not exact.match(str(declared)):
            problems.append(violation('DEPENDENCY', f'override {name} is not pinned exactly', name))
        entry = (lock.get('packages') or {}).get(f'node_modules/{name}')
        if not entry or entry.get('version') != declared:
            problems.append(violation('DEPENDENCY', f'override {name} is not represented in the lockfile', name))
    try:
        secure = load_secure_deps()
        for error in secure.validate_requirements_text(requirements_text):
            problems.append(violation('REQUIREMENTS', error, 'requirements-render.txt'))
    except Exception as error:  # helper itself must remain importable in the archive
        problems.append(violation('REQUIREMENTS', f'secure dependency helper failed: {error}', 'requirements-render.txt'))
    return problems


def preflight(archive_path, allow_showcase=False):
    path = Path(archive_path)
    report = {
        'status': 'FAIL',
        'archive': str(path),
        'sha256': None,
        'entries': 0,
        'compressed_bytes': 0,
        'uncompressed_bytes': 0,
        'checks': {},
        'code_execution': {
            'status': 'FAIL',
            'python_parser': 'ast',
            'javascript_parser': 'lexical-string-comment-stripped',
            'files_scanned': 0,
            'findings': [],
        },
        'violations': [],
    }
    problems = report['violations']
    if not path.is_file():
        problems.append(violation('MISSING_ARCHIVE', f'archive does not exist: {path}'))
        return report
    report['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as error:
        problems.append(violation('BAD_ARCHIVE', f'not a readable ZIP: {error}'))
        return report
    with archive:
        infos = archive.infolist()
        report['entries'] = len(infos)
        report['compressed_bytes'] = sum(info.compress_size for info in infos)
        names = [info.filename for info in infos]
        checks = report['checks']
        checks['structure'] = {'status': 'PASS', 'entries': len(infos)}
        checks['paths'] = {'status': 'PASS'}
        checks['permissions'] = {'status': 'PASS'}
        checks['symlinks'] = {'status': 'PASS'}
        checks['skill'] = {'status': 'PASS'}
        checks['frontmatter'] = {'status': 'PASS'}
        checks['datetime'] = {'status': 'PASS', 'known': list(KNOWN_STATIC_DATETIME)}
        checks['decompression'] = {'status': 'PASS'}
        checks['dependencies'] = {'status': 'PASS'}
        checks['code_execution'] = {'status': 'PASS'}

        def mark(check, code, detail, member=None):
            checks[check]['status'] = 'FAIL'
            problems.append(violation(code, detail, member))

        if len(names) != len(set(names)):
            mark('structure', 'DUPLICATE_ENTRY', 'archive contains duplicate member names')
        lowered = [name.lower() for name in names]
        if len(lowered) != len(set(lowered)):
            mark('structure', 'DUPLICATE_ENTRY', 'archive contains case-insensitive duplicate names')

        for info in infos:
            name = info.filename
            if info.is_dir():
                mark('structure', 'DIRECTORY_ENTRY', 'archive contains a directory entry', name)
            reason = unsafe_path_reason(name)
            if reason:
                mark('paths', 'UNSAFE_PATH', reason, name)
            if info.flag_bits & 0x1:
                mark('structure', 'ENCRYPTED_MEMBER', 'archive member is encrypted', name)
            if is_symlink(info):
                mark('symlinks', 'SYMLINK', 'archive member is a symlink', name)
            else:
                permission = permission_reason(info)
                if permission:
                    mark('permissions', 'PERMISSIONS', permission, name)
            if info.date_time != KNOWN_STATIC_DATETIME:
                mark('datetime', 'STATIC_DATETIME_REGRESSION',
                     f'expected {KNOWN_STATIC_DATETIME}, found {info.date_time}', name)
            relative = name[len(PREFIX):] if name.startswith(PREFIX) else name
            parts = set(PurePosixPath(relative).parts)
            if parts & FORBIDDEN_DIRS:
                mark('structure', 'FORBIDDEN_MEMBER', 'generated or vendored directory is not allowed', name)
            if 'out' in parts:
                if not allow_showcase:
                    mark('structure', 'FORBIDDEN_MEMBER', 'installer archives must not include generated out/ files', name)
                elif not relative.startswith('out/v1.3-showcase/'):
                    mark('structure', 'FORBIDDEN_MEMBER', 'showcase archives may include out/ only under out/v1.3-showcase/', name)
            base = PurePosixPath(relative).name
            if base in FORBIDDEN_NAMES or base.startswith(('.env.', 'credentials', 'secrets')):
                mark('structure', 'FORBIDDEN_MEMBER', 'private or secret-like file is not allowed', name)
            if base.endswith(FORBIDDEN_SUFFIXES):
                mark('structure', 'FORBIDDEN_MEMBER', 'compiled, credential, key or nested ZIP member is not allowed', name)
            suffix = PurePosixPath(relative).suffix.lower()
            if suffix in ('.pptx', '.pdf') and not (allow_showcase and relative.startswith('out/v1.3-showcase/')):
                mark('structure', 'FORBIDDEN_MEMBER', 'installer archives must not carry PPTX or PDF output', name)

        skill_names = [name for name in names if name.endswith('/SKILL.md')]
        if skill_names != [PREFIX + 'SKILL.md']:
            mark('skill', 'MULTIPLE_SKILL', f'expected exactly {PREFIX}SKILL.md, found {skill_names}')
        missing = sorted(PREFIX + name for name in REQUIRED_FILES if PREFIX + name not in names)
        if missing:
            mark('structure', 'MISSING_FILE', 'required installer files are missing: ' + ', '.join(missing))

        contents = {}
        total = 0
        for info in infos:
            if info.file_size > MAX_MEMBER_BYTES:
                mark('decompression', 'ZIP_BOMB', f'member exceeds {MAX_MEMBER_BYTES} bytes', info.filename)
            if info.compress_size and info.file_size > 1024 * 1024 and info.file_size / info.compress_size > MAX_RATIO:
                mark('decompression', 'ZIP_BOMB', 'member compression ratio exceeds the safe bound', info.filename)
            try:
                data = archive.read(info.filename)
            except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                mark('decompression', 'DECOMPRESSION', f'member could not be decompressed: {error}', info.filename)
                continue
            total += len(data)
            contents[info.filename] = data
        report['uncompressed_bytes'] = total
        if total > MAX_TOTAL_BYTES:
            mark('decompression', 'ZIP_BOMB', f'archive expands beyond {MAX_TOTAL_BYTES} bytes')
        if archive.testzip() is not None:
            mark('decompression', 'DECOMPRESSION', 'archive CRC check failed')

        def text_member(relative):
            data = contents.get(PREFIX + relative)
            if data is None:
                return None
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                mark('structure', 'TEXT_ENCODING', 'text member is not valid UTF-8', PREFIX + relative)
                return None

        skill_text = text_member('SKILL.md')
        package_text = text_member('package.json')
        lock_text = text_member('package-lock.json')
        requirements_text = text_member('requirements-render.txt')
        if skill_text is not None:
            top, nested = parse_frontmatter(skill_text)
            if top is None:
                mark('frontmatter', 'FRONTMATTER', 'SKILL.md has no delimited frontmatter', PREFIX + 'SKILL.md')
            else:
                if unquote(top.get('name')) != 'goujian-strategy-slides':
                    mark('frontmatter', 'FRONTMATTER', 'SKILL.md name must be goujian-strategy-slides', PREFIX + 'SKILL.md')
                version = unquote(top.get('version') or nested.get('version'))
                package_version = None
                if package_text:
                    try:
                        package_version = json.loads(package_text).get('version')
                    except ValueError:
                        package_version = None
                if not version or (package_version and version != package_version):
                    mark('frontmatter', 'FRONTMATTER',
                         f'SKILL.md version {version!r} does not match package.json {package_version!r}',
                         PREFIX + 'SKILL.md')
                description = top.get('description')
                if not description or not description.startswith('"'):
                    mark('frontmatter', 'FRONTMATTER', 'SKILL.md description must be a JSON string', PREFIX + 'SKILL.md')
                else:
                    try:
                        if not json.loads(description):
                            mark('frontmatter', 'FRONTMATTER', 'SKILL.md description is empty', PREFIX + 'SKILL.md')
                    except ValueError:
                        mark('frontmatter', 'FRONTMATTER', 'SKILL.md description is not valid JSON', PREFIX + 'SKILL.md')
        if package_text is not None and lock_text is not None and requirements_text is not None:
            for problem in dependency_violations(package_text, lock_text, requirements_text):
                checks['dependencies']['status'] = 'FAIL'
                problems.append(problem)

        code_extensions = {'.py': 'python', '.js': 'javascript', '.cjs': 'javascript', '.mjs': 'javascript'}
        findings = []
        scanned = 0
        for name, data in contents.items():
            extension = PurePosixPath(name).suffix.lower()
            language = code_extensions.get(extension)
            if not language:
                continue
            try:
                source = data.decode('utf-8')
            except UnicodeDecodeError:
                findings.append(finding('TEXT_ENCODING', name, 0, 'source file is not valid UTF-8'))
                continue
            scanned += 1
            if language == 'python':
                findings.extend(scan_python_source(name, source))
            else:
                findings.extend(scan_javascript_source(name, source))
        report['code_execution']['files_scanned'] = scanned
        report['code_execution']['findings'] = findings
        if findings:
            checks['code_execution']['status'] = 'FAIL'
            for item in findings:
                problems.append(violation('CODE_EXECUTION',
                                          f'{item["kind"]}: {item["detail"]}', item['member']))
        else:
            report['code_execution']['status'] = 'PASS'

    report['status'] = 'FAIL' if problems else 'PASS'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', help='actual installer ZIP to inspect')
    parser.add_argument('--allow-showcase', action='store_true',
                        help='allow PPTX/PDF members only under out/v1.3-showcase/')
    parser.add_argument('--json', help='write the full report to this path')
    args = parser.parse_args(argv)
    report = preflight(args.archive, allow_showcase=args.allow_showcase)
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {
        'status': report['status'],
        'archive': report['archive'],
        'sha256': report['sha256'],
        'entries': report['entries'],
        'uncompressed_bytes': report['uncompressed_bytes'],
        'code_files_scanned': report['code_execution']['files_scanned'],
        'violations': len(report['violations']),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for item in report['violations']:
        print(f"{item['code']}: {item['detail']}" + (f" [{item['member']}]" if item.get('member') else ''), file=sys.stderr)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
