#!/usr/bin/env python3
"""Preflight an actual Goujian release ZIP before any release action.

Checks are intentionally direct and auditable:

* structure, one root SKILL.md, safe POSIX paths, duplicate names;
* Unix file mode and symlink flags, known static ZIP timestamps;
* full decompression of every member plus bounded zip-bomb guards;
* profile-aware required files and package metadata (runtime, full source or
  the archived legacy layout);
* declared npm dependencies against the locked tree and the secure Pillow
  requirement;
* a complete line-level text inventory for every text-bearing member,
  including docs, policies, tests and configuration. The company-reported
  literal is reported exactly and case-insensitively, separately from
  ``exec``;
* Python source through ``ast`` with import/alias resolution and JavaScript
  through a lexical string/comment stripper, so inert examples in strings,
  comments or escaped regexes are not misclassified as executable behaviour.

There is no per-file allowlist that excuses unsafe execution. Argument-array
process calls such as ``execFileSync(...)``/``subprocess.run([...])`` and
list-based ``subprocess`` calls remain accepted; shell strings, ``shell=True``,
``os.system``, ``eval``/``exec``, dynamic module loading, dynamic ``require``
and ``child_process.exec`` are rejected in production scope. Fixed inline
``node -e``/``python -c`` payloads are rejected in the shipped runtime; they
are reported as development behaviour in the full source test suite and as
reported for the archived legacy baseline; existing dangerous-execution rules still block in every profile.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import stat
import sys
import tokenize
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.qa import secure_deps

PREFIX = 'goujian-strategy-slides/'
KNOWN_STATIC_DATETIME = (2026, 1, 1, 0, 0, 0)
PROFILES = ('runtime', 'source', 'legacy')

COMMON_REQUIRED = {
    'SKILL.md', 'README.md', 'README.zh-CN.md', 'README.en.md', 'LICENSE',
    'THIRD_PARTY_NOTICE.md', 'package.json', 'package-lock.json',
    'requirements-render.txt', 'core/renderer/index.js', 'core/renderer/charts.js',
    'core/schema/deck.schema.json', 'core/qa/secure_deps.py',
    'scripts/security_preflight.py', 'skill/scripts/build_deck.js',
}
NEW_PATCH_FILES = {
    'core/__init__.py', 'core/qa/__init__.py', 'skill/__init__.py',
    'skill/scripts/__init__.py', 'core/qa/spec_check.py',
    'core/qa/recompute_analytics.js', 'scripts/probe_env.py',
    'scripts/runtime_smoke.py', 'tests/validate_examples.py',
    'distribution/runtime-manifest.json', 'distribution/runtime-package.json',
}
RUNTIME_REQUIRED = COMMON_REQUIRED | NEW_PATCH_FILES
SOURCE_REQUIRED = COMMON_REQUIRED | NEW_PATCH_FILES | {'tests/test_security_preflight.py'}
LEGACY_REQUIRED = COMMON_REQUIRED | {'tests/test_security_preflight.py'}
# Historical public name retained for callers that do not pass a profile.
REQUIRED_FILES = SOURCE_REQUIRED

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
SHELL_EXECUTABLES = {'sh', 'bash', 'zsh', 'dash', 'cmd', 'cmd.exe', 'powershell', 'pwsh'}
PYTHON_EXECUTABLES = {'python', 'python3', 'python3.9', 'python3.10', 'python3.11',
                      'python3.12', 'python3.13', 'python3.14'}
NODE_EXECUTABLES = {'node', 'nodejs'}
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

TEXT_SUFFIXES = {
    '.py', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.jsx', '.md', '.markdown',
    '.json', '.yml', '.yaml', '.txt', '.sh', '.bash', '.toml', '.cfg', '.ini',
    '.html', '.htm', '.css', '.xml', '.svg', '.csv', '.sha256', '.lock',
}
TEXT_BASENAMES = {'LICENSE', 'NOTICE', 'Makefile', 'Dockerfile', 'Gemfile',
                  '.gitignore', '.gitattributes', '.editorconfig', '.npmrc'}
INVENTORY_PATTERNS = [
    ('EXEC_FILE_SYNC', re.compile(r'\bexecFileSync\s*\('), 'MEDIUM',
     'controlled argument-array process call'),
    ('EXEC_FILE', re.compile(r'\bexecFile\s*\('), 'MEDIUM',
     'controlled argument-array process call'),
    ('EXEC_SYNC', re.compile(r'(?<![.\w$])execSync\s*\('), 'HIGH',
     'shell-string execution'),
    ('EXEC', re.compile(r'(?<![.\w$])exec\s*\('), 'HIGH',
     'shell-string execution'),
    ('SPAWN', re.compile(r'\b(?:spawn|spawnSync)\s*\('), 'MEDIUM',
     'controlled child-process invocation'),
    ('CHILD_PROCESS', re.compile(r'\b(?:node:)?child_process\b'), 'INFO',
     'Node child-process module reference'),
    ('SUBPROCESS', re.compile(r'\bsubprocess\s*\.'), 'MEDIUM',
     'Python process invocation'),
    ('EXEC_MODULE', re.compile(r'\bexec_module\s*\('), 'HIGH',
     'path-loaded module execution'),
    ('SPEC_FROM_FILE', re.compile(r'\bspec_from_file_location\s*\('), 'HIGH',
     'path-loaded module specification'),
    ('IMPORTLIB', re.compile(r'\bimportlib\b'), 'INFO',
     'Python import machinery reference'),
    ('NODE_EVAL', re.compile(r'\bnode(?:js)?\s+[\'"]?-e\b'), 'HIGH',
     'fixed inline JavaScript payload'),
    ('PYTHON_CODE', re.compile(r'\bpython[0-9.]*\s+[\'"]?-c\b'), 'HIGH',
     'fixed inline Python payload'),
    ('EVAL', re.compile(r'(?<![.\w$])eval\s*\('), 'HIGH',
     'dynamic evaluation'),
    ('NEW_FUNCTION', re.compile(r'\bnew\s+Function\s*\('), 'HIGH',
     'dynamic function construction'),
    ('VM_RUN', re.compile(r'\bvm\s*\.\s*run(?:InNewContext|InThisContext|InContext)?\s*\('), 'HIGH',
     'dynamic VM execution'),
    ('OS_SYSTEM', re.compile(r'\bos\s*\.\s*(?:system|popen)\s*\('), 'HIGH',
     'shell command execution'),
    ('IMPORT_BUILTIN', re.compile(r'\b__import__\s*\('), 'HIGH',
     'dynamic module import'),
    ('SHELL_MODE', re.compile(r'\bshell\s*(?::|=)\s*true\b', re.IGNORECASE), 'HIGH',
     'shell mode enabled'),
    ('SHELL_WRAPPER', re.compile(
        r'(?:^|[\'"/])(?:sh|bash|zsh|dash|cmd(?:\.exe)?|powershell|pwsh)(?:[\'"]|\b)[^\n]{0,80}(?:\s-c\b|\s/c\b)'),
     'HIGH', 'shell wrapper with inline command'),
    ('DYNAMIC_IMPORT', re.compile(r'\bimport\s*\('), 'MEDIUM',
     'dynamic JavaScript import'),
    ('REQUIRE', re.compile(r'\brequire\s*\('), 'INFO',
     'CommonJS module load'),
    ('NETWORK', re.compile(
        r'\b(?:https?\.(?:request|get)|fetch\s*\(|net\.(?:connect|createConnection)|socket\.|requests\.|urllib|http\.client|curl\b|wget\b)'),
     'INFO', 'network access inventory'),
    ('INSTALL', re.compile(
        r'\b(?:npm\s+(?:install|ci)|pip3?\s+install|python[0-9.]*\s+-m\s+pip\s+install)\b'),
     'MEDIUM', 'dependency installation boundary'),
    ('DELETE', re.compile(r'\b(?:rmtree|unlink(?:Sync)?|rmSync|remove|rmdir)\s*\(|\brm\s+-rf\b'),
     'MEDIUM', 'filesystem deletion inventory'),
    ('PATH_ESCAPE', re.compile(r'(?:\.\./|\.\.\\)'), 'INFO',
     'parent-path reference'),
    ('PATH_RESOLVE', re.compile(r'\b(?:path\.(?:join|resolve|normalize)|\.resolve)\s*\('), 'INFO',
     'path resolution inventory'),
    ('ENV_ACCESS', re.compile(r'\bprocess\.env\b|\bos\.environ\b'), 'INFO',
     'environment access inventory'),
]
DEVELOPMENT_FILES = {
    'scripts/benchmark.py', 'scripts/build_showcase.js', 'scripts/create_v11_fixtures.js',
    'scripts/dogfood_phase2.js', 'scripts/dogfood_round2.js', 'scripts/social_preview.py',
    'scripts/v13_benchmark.js',
}


def finding(kind, member, line, detail, column=0, context='', purpose='', scope='production'):
    return {
        'kind': kind,
        'member': member,
        'line': line,
        'column': column,
        'detail': detail,
        'context': context,
        'purpose': purpose,
        'scope': scope,
    }


def violation(code, detail, member=None):
    return {'code': code, 'detail': detail, 'member': member}


def load_secure_deps():
    return secure_deps


def profile_required(profile):
    return {'runtime': RUNTIME_REQUIRED, 'source': SOURCE_REQUIRED, 'legacy': LEGACY_REQUIRED}[profile]


def detect_profile(names):
    relative = {name[len(PREFIX):] if name.startswith(PREFIX) else name for name in names}
    if 'distribution/runtime-manifest.json' not in relative:
        if 'tests/test_security_preflight.py' in relative and 'core/qa/spec-check.py' in relative:
            return 'legacy', 'pre-runtime layout with hyphenated QA modules'
        return 'source', 'no runtime manifest and no legacy layout marker'
    if 'tests/test_security_preflight.py' not in relative:
        return 'runtime', 'runtime manifest present without the development test suite'
    return 'source', 'runtime manifest present together with the full development test suite'


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


def strip_javascript_noise(source, keep_strings=False):
    """Blank comments, and by default string contents, preserving offsets.

    The output has exactly the same length and newline positions as ``source``,
    so positions found in the scrubbed view can be reused on the original text.
    With ``keep_strings`` the literal bodies stay verbatim while comments are
    still blanked; that view is used to read a call argument for the
    static-versus-dynamic decision.
    """
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
                output.append(char if keep_strings else ' ')
                index += 1
                continue
            if char == '`':
                state = 'template'
                output.append(char if keep_strings else ' ')
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
        if keep_strings:
            if char == '\\' and index + 1 < length:
                output.append(source[index:index + 2])
                index += 2
                continue
            if state == 'string' and char == quote:
                state = 'code'
            elif state == 'template' and char == '`':
                state = 'code'
            output.append(char)
            index += 1
            continue
        if char == '\\' and index + 1 < length:
            following = source[index + 1]
            output.append(' ')
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


def static_string_call_argument(source, start):
    """Return the single string-literal argument that begins at ``start``.

    ``None`` means the call takes anything other than one complete literal
    (a variable, a concatenation, a path expression or a template with
    substitution), which is a runtime-selected argument.
    """
    index = start
    length = len(source)
    while index < length and source[index] in ' \t\r\n':
        index += 1
    if index >= length:
        return None
    quote = source[index]
    if quote not in ("'", '"', '`'):
        return None
    index += 1
    content = []
    while index < length:
        char = source[index]
        if char == '\\' and index + 1 < length:
            content.append(source[index:index + 2])
            index += 2
            continue
        if char == quote:
            index += 1
            break
        if quote == '`' and char == '$' and source[index + 1:index + 2] == '{':
            return None
        content.append(char)
        index += 1
    else:
        return None
    while index < length and source[index] in ' \t\r\n':
        index += 1
    if index < length and source[index] == ')':
        return ''.join(content)
    return None


def line_of(text, position):
    return text.count('\n', 0, position) + 1


def column_of(text, position):
    return position - (text.rfind('\n', 0, position) + 1) + 1


def line_context(source, line):
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()[:240]
    return ''


def python_inert_spans(source):
    spans = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type in (tokenize.STRING, tokenize.COMMENT):
                spans.append((token.start, token.end))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    return spans


def position_in_spans(line, column, spans):
    if not spans:
        return False
    for (start_line, start_column), (end_line, end_column) in spans:
        if start_line <= line <= end_line:
            if start_line == end_line:
                if start_column <= column <= end_column:
                    return True
            elif line == start_line:
                if column >= start_column:
                    return True
            elif line == end_line:
                if column <= end_column:
                    return True
            else:
                return True
    return False


def text_kind(relative):
    path = PurePosixPath(relative)
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_BASENAMES


def scope_of(relative, profile):
    if profile == 'runtime':
        return 'production'
    path = PurePosixPath(relative)
    if path.parts and path.parts[0] == 'tests':
        return 'development'
    if relative in DEVELOPMENT_FILES or (path.parts and path.parts[0] == 'benchmark'):
        return 'development'
    return 'production'


def inventory_scope(relative, profile):
    if scope_of(relative, profile) == 'development':
        return 'development'
    path = PurePosixPath(relative)
    if path.parts and path.parts[0] in ('docs', 'adapters'):
        return 'documentation'
    if path.suffix.lower() in {'.md', '.markdown'} or path.name in {'LICENSE', 'NOTICE'}:
        return 'documentation'
    if path.suffix.lower() in {'.json', '.yml', '.yaml', '.toml', '.cfg', '.ini', '.lock'}:
        return 'configuration'
    if path.suffix.lower() in {'.txt', '.sha256'}:
        return 'policy_text'
    return 'production'


def scan_inventory(member, source, relative, profile):
    suffix = PurePosixPath(relative).suffix.lower()
    if suffix == '.py':
        language = 'python'
        py_spans = python_inert_spans(source)
        js_scrubbed_lines = None
    elif suffix in {'.js', '.cjs', '.mjs', '.ts', '.tsx', '.jsx'}:
        language = 'javascript'
        py_spans = None
        js_scrubbed_lines = strip_javascript_noise(source).splitlines()
    else:
        language = 'text'
        py_spans = None
        js_scrubbed_lines = None
    scope = inventory_scope(relative, profile)
    hits = []
    for category, pattern, severity, purpose in INVENTORY_PATTERNS:
        for match in pattern.finditer(source):
            line = line_of(source, match.start())
            column = column_of(source, match.start())
            if language == 'python':
                if py_spans is None:
                    classification = 'unparsed_code'
                else:
                    classification = ('inert_string_or_comment'
                                      if position_in_spans(line, column - 1, py_spans)
                                      else 'executable_code')
            elif language == 'javascript':
                scrubbed_line = js_scrubbed_lines[line - 1] if line - 1 < len(js_scrubbed_lines) else ''
                classification = 'executable_code' if pattern.search(scrubbed_line) else 'inert_string_or_comment'
            else:
                classification = 'text'
            effective = severity
            if classification in ('inert_string_or_comment', 'text') or scope in ('documentation', 'configuration', 'policy_text'):
                effective = 'INFO'
            hits.append({
                'category': category,
                'member': member,
                'line': line,
                'column': column,
                'match': match.group(0)[:120],
                'context': line_context(source, line),
                'severity': effective,
                'classification': classification,
                'scope': scope,
                'purpose': purpose,
            })
    return hits


def scan_literal(member, source, literal):
    exact = []
    folded = []
    for match in re.finditer(re.escape(literal), source):
        exact.append({
            'member': member,
            'line': line_of(source, match.start()),
            'column': column_of(source, match.start()),
            'context': line_context(source, line_of(source, match.start())),
        })
    for match in re.finditer(re.escape(literal), source, re.IGNORECASE):
        folded.append({
            'member': member,
            'line': line_of(source, match.start()),
            'column': column_of(source, match.start()),
            'context': line_context(source, line_of(source, match.start())),
        })
    return exact, folded


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


def collect_python_aliases(tree):
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    aliases[alias.name.split('.')[0]] = alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                local = alias.asname or alias.name
                aliases[local] = f'{module}.{alias.name}' if module else alias.name
    return aliases


def resolve_dotted(name, aliases):
    if not name:
        return name
    first, *rest = name.split('.')
    base = aliases.get(first)
    if base is None:
        return name
    return '.'.join([base] + rest)


def literal_prefix(node):
    """Leading string literals of an argument list, stopping at the first non-literal.

    This still exposes the executable and flags of ``["sh", "-c", user_value]``
    where the payload itself is dynamic.
    """
    if isinstance(node, (ast.List, ast.Tuple)):
        values = []
        for element in node.elts:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                break
            values.append(element.value)
        return values
    return None


def executable_name(value):
    return PurePosixPath(str(value).replace('\\', '/')).name.lower()


def scan_python_source(member, source, scope='production', profile='runtime'):
    def item(kind, node, detail, purpose):
        return finding(kind, member, getattr(node, 'lineno', 0), detail,
                       column=getattr(node, 'col_offset', 0) + 1,
                       context=line_context(source, getattr(node, 'lineno', 0)),
                       purpose=purpose, scope=scope)

    try:
        tree = ast.parse(source, filename=member)
    except SyntaxError as error:
        syntax = finding('PYTHON_SYNTAX', member, error.lineno or 0, 'Python source does not parse',
                         column=(error.offset or 0), context=line_context(source, error.lineno or 0),
                         purpose='source must be auditable', scope=scope)
        return [syntax], []
    aliases = collect_python_aliases(tree)
    blocking = []
    reported = []

    def route(found, allow_development=False):
        if allow_development and (profile == 'legacy' or scope == 'development'):
            reported.append(found)
        else:
            blocking.append(found)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = resolve_dotted(dotted_name(node.func), aliases)
        if not name:
            continue
        getattr_target = None
        if name in ('getattr', 'builtins.getattr') and len(node.args) >= 2:
            if isinstance(node.args[0], (ast.Name, ast.Attribute)):
                if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    getattr_target = resolve_dotted(dotted_name(node.args[0]), aliases) + '.' + node.args[1].value
        effective_name = getattr_target or name
        if effective_name in DANGEROUS_DOTTED:
            kind = ('PYTHON_DYNAMIC_EVAL' if effective_name.split('.')[-1] in {'eval', 'exec', 'compile'}
                    else 'PYTHON_SHELL_EXECUTION')
            route(item(kind, node, f'dangerous call {effective_name}', 'arbitrary code execution'))
            continue
        if effective_name.split('.')[-1] == 'exec_module' or effective_name.endswith('spec_from_file_location'):
            route(item('PYTHON_DYNAMIC_MODULE_LOAD', node,
                       f'path-loaded module execution via {effective_name}',
                       'loads code from a runtime path instead of a static import'),
                  allow_development=True)
            continue
        if effective_name in ('__import__', 'importlib.import_module'):
            argument = node.args[0] if node.args else None
            literal = isinstance(argument, ast.Constant) and isinstance(argument.value, str)
            found = item('PYTHON_DYNAMIC_MODULE_LOAD', node,
                         f'dynamic import via {effective_name}',
                         'fixed static module' if literal else 'runtime-selected module')
            route(found, allow_development=True)
            continue
        parts = effective_name.split('.')
        if parts[0] == 'subprocess' and parts[-1] in SUBPROCESS_NAMES:
            shell = keyword_value(node, 'shell')
            if shell is not None:
                if isinstance(shell, ast.Constant) and shell.value is False:
                    pass
                elif isinstance(shell, ast.Constant) and shell.value is True:
                    route(item('SHELL_TRUE', node, 'subprocess call enables a shell',
                               'shell string interpretation'))
                else:
                    route(item('SHELL_DYNAMIC', node,
                               'subprocess shell mode is not a literal False',
                               'shell mode must be statically disabled'))
            command_node = node.args[0] if node.args else keyword_value(node, 'args')
            if command_node is not None:
                if isinstance(command_node, ast.Constant) and isinstance(command_node.value, str):
                    route(item('STRING_COMMAND', node,
                               'subprocess receives a string command instead of an argument array',
                               'shell metacharacters could be interpreted'))
                elif isinstance(command_node, ast.JoinedStr):
                    route(item('STRING_COMMAND', node,
                               'subprocess receives an interpolated string command',
                               'shell metacharacters could be interpreted'))
                values = literal_prefix(command_node)
                if values:
                    executable = executable_name(values[0])
                    if executable in SHELL_EXECUTABLES and any(value in ('-c', '/c') for value in values[1:]):
                        route(item('PYTHON_SHELL_WRAPPER', node,
                                   f'shell wrapper {values[0]!r} receives an inline command',
                                   'shell command injection boundary'))
                    if executable in PYTHON_EXECUTABLES and '-c' in values[1:]:
                        route(item('PYTHON_FIXED_CODE_FLAG', node,
                                   'python receives a fixed -c payload',
                                   'inline code payload instead of a static module'),
                              allow_development=True)
                    if executable in NODE_EXECUTABLES and any(value in ('-e', '--eval') for value in values[1:]):
                        route(item('PYTHON_FIXED_CODE_FLAG', node,
                                   'node receives a fixed -e payload',
                                   'inline code payload instead of a static module'),
                              allow_development=True)
    return blocking, reported


def js_child_process_vars(scrubbed, preserved):
    """Names bound to the whole child_process module by a static require."""
    names = set()
    for match in re.finditer(
            r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\(\s*[\'"](?:node:)?child_process[\'"]\s*\)',
            preserved):
        position = preserved.find('require', match.start(), match.end())
        if position >= 0 and scrubbed[position:position + 7] == 'require':
            names.add(match.group(1))
    return names


def js_alias_patterns(scrubbed, preserved):
    """Find child_process aliases whose declaration is real executable code.

    ``preserved`` keeps string literals so ``require('child_process')`` is
    readable; ``scrubbed`` proves the ``require`` keyword itself is not inside
    a string or comment (both views share offsets).
    """
    patterns = []
    for name in sorted(js_child_process_vars(scrubbed, preserved)):
        patterns.append((re.compile(r'\b' + re.escape(name) + r'\s*\.\s*exec(?:Sync)?\s*\('),
                         'CHILD_PROCESS_EXEC_ALIAS', f'{name}.exec call'))
        patterns.append((re.compile(r'\b' + re.escape(name) + r'\s*\[\s*[\'"](?:exec|execSync)[\'"]\s*\]\s*\('),
                         'CHILD_PROCESS_EXEC_ALIAS', f'{name}[exec] call'))
    for match in re.finditer(
            r'\b(?:const|let|var)\s*\{([^}]*)\}\s*=\s*require\(\s*[\'"](?:node:)?child_process[\'"]\s*\)',
            preserved):
        position = preserved.find('require', match.start(), match.end())
        if position < 0 or scrubbed[position:position + 7] != 'require':
            continue
        for part in match.group(1).split(','):
            bits = [bit.strip() for bit in part.split(':', 1)]
            source_name = bits[0]
            local = bits[1] if len(bits) > 1 and bits[1] else source_name
            if source_name in ('exec', 'execSync') and re.match(r'^[A-Za-z_$][\w$]*$', local):
                patterns.append((re.compile(r'(?<![.\w$])' + re.escape(local) + r'\s*\('),
                                 'CHILD_PROCESS_EXEC_ALIAS', f'destructured {source_name} alias {local}'))
    return patterns


def scan_javascript_source(member, source, scope='production', profile='runtime'):
    scrubbed = strip_javascript_noise(source)
    preserved = strip_javascript_noise(source, keep_strings=True)
    blocking = []
    reported = []

    def record(kind, position, detail, purpose, allow_development=False):
        found = finding(kind, member, line_of(scrubbed, position), detail,
                        column=column_of(scrubbed, position),
                        context=line_context(source, line_of(scrubbed, position)),
                        purpose=purpose, scope=scope)
        if allow_development and (profile == 'legacy' or scope == 'development'):
            reported.append(found)
        else:
            blocking.append(found)

    def add(pattern, kind, detail, purpose, allow_development=False):
        for match in pattern.finditer(scrubbed):
            record(kind, match.start(), detail, purpose, allow_development)

    def add_preserved(pattern, kind, detail, purpose, allow_development=False):
        for match in pattern.finditer(preserved):
            if scrubbed[match.start():match.start() + 1].isspace():
                continue
            if not scrubbed[match.start():match.start() + 1]:
                continue
            record(kind, match.start(), detail, purpose, allow_development)

    for kind, pattern in JS_PATTERNS:
        add(pattern, kind, f'JavaScript execution pattern {kind}',
            'arbitrary code or shell execution')
    for pattern, kind, detail in js_alias_patterns(scrubbed, preserved):
        add_preserved(pattern, kind, detail, 'child_process.exec through an alias')
    for name in sorted(js_child_process_vars(scrubbed, preserved)):
        dynamic_member = re.compile(r'\b' + re.escape(name) + r'\s*\[([^\]]*)\]\s*\(')
        for match in dynamic_member.finditer(preserved):
            if scrubbed[match.start():match.start() + 1].isspace():
                continue
            key = match.group(1).strip()
            if re.match(r'^[\'"][^\'"]*[\'"]$', key):
                continue
            record('CHILD_PROCESS_DYNAMIC_ACCESS', match.start(),
                   f'{name}[runtime-key] call selects a child_process method dynamically',
                   'dynamic dispatch can bypass the exec deny rule')

    call_re = re.compile(
        r'\b(?:execFileSync|execFile|spawnSync|spawn)\s*\(\s*([\'"])([^\'"]+)\1\s*,\s*\[([^\]]*)\]')
    for match in call_re.finditer(preserved):
        if scrubbed[match.start():match.start() + 1].isspace():
            continue
        executable = executable_name(match.group(2))
        args = re.findall(r'[\'"]([^\'"]*)[\'"]', match.group(3))
        if executable in SHELL_EXECUTABLES and any(value in ('-c', '/c') for value in args):
            record('JAVASCRIPT_SHELL_WRAPPER', match.start(),
                   f'shell wrapper {match.group(2)!r} receives an inline command',
                   'shell command injection boundary')
        if executable in PYTHON_EXECUTABLES and '-c' in args:
            record('JAVASCRIPT_FIXED_CODE_FLAG', match.start(),
                   'python receives a fixed -c payload',
                   'inline code payload instead of a static module', True)
        if executable in NODE_EXECUTABLES and any(value in ('-e', '--eval') for value in args):
            record('JAVASCRIPT_FIXED_CODE_FLAG', match.start(),
                   'node receives a fixed -e payload',
                   'inline code payload instead of a static module', True)

    for keyword, kind, label in (
            ('require', 'JAVASCRIPT_DYNAMIC_MODULE_LOAD', 'require'),
            ('import', 'JAVASCRIPT_DYNAMIC_MODULE_LOAD', 'import()')):
        call = re.compile(r'\b' + keyword + r'\s*\(')
        for match in call.finditer(scrubbed):
            argument = static_string_call_argument(preserved, match.end())
            if argument is not None:
                continue
            record(kind, match.start(),
                   f'{label} receives a runtime-selected module name',
                   'dynamic module loading is not a fixed static dependency', True)
    add(re.compile(r'\bnode(?:js)?\s+[\'"]?-e\b'), 'JAVASCRIPT_FIXED_CODE_FLAG',
        'inline node -e payload',
        'inline code payload instead of a static module', allow_development=True)
    return blocking, reported


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


def runtime_metadata_violations(profile, contents, allow_showcase=False, strict_manifest=False):
    problems = []
    notes = []
    if PREFIX + 'package.json' not in contents:
        return problems, notes
    package_data = contents[PREFIX + 'package.json']
    try:
        package = json.loads(package_data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as error:
        return [violation('RUNTIME_METADATA', f'package.json is not valid UTF-8 JSON: {error}',
                          PREFIX + 'package.json')], notes
    if profile == 'runtime':
        runtime_relative = 'distribution/runtime-package.json'
        runtime_data = contents.get(PREFIX + runtime_relative)
        if runtime_data is None:
            problems.append(violation('RUNTIME_METADATA', 'runtime package mapping is missing',
                                      PREFIX + runtime_relative))
        elif runtime_data != package_data:
            problems.append(violation('RUNTIME_PACKAGE_MAPPING',
                                      'package.json must byte-match distribution/runtime-package.json',
                                      PREFIX + 'package.json'))
        manifest_data = contents.get(PREFIX + 'distribution/runtime-manifest.json')
        if manifest_data is None:
            problems.append(violation('RUNTIME_MANIFEST', 'runtime manifest is missing',
                                      PREFIX + 'distribution/runtime-manifest.json'))
        else:
            try:
                manifest = json.loads(manifest_data.decode('utf-8'))
            except (UnicodeDecodeError, ValueError) as error:
                problems.append(violation('RUNTIME_MANIFEST', f'runtime manifest is not valid JSON: {error}',
                                          PREFIX + 'distribution/runtime-manifest.json'))
                manifest = None
            if manifest is not None:
                if manifest.get('distribution') != 'runtime':
                    problems.append(violation('RUNTIME_MANIFEST', 'manifest distribution must be runtime',
                                              PREFIX + 'distribution/runtime-manifest.json'))
                mapping = manifest.get('package_mapping') or {}
                if (mapping.get('archive_path') != 'package.json'
                        or mapping.get('source_path') != 'distribution/runtime-package.json'):
                    problems.append(violation(
                        'RUNTIME_MANIFEST',
                        'manifest package mapping must map package.json to distribution/runtime-package.json',
                        PREFIX + 'distribution/runtime-manifest.json'))
                runtime_files = manifest.get('runtime_files') or []
                declared = {PREFIX + name for name in runtime_files}
                missing = sorted(name for name in declared if name not in contents)
                if missing:
                    problems.append(violation('RUNTIME_MANIFEST',
                                              'declared runtime files are missing: ' + ', '.join(missing[:10])))
                expected = declared | {PREFIX + 'package.json'}
                extras = sorted(name for name in contents if name not in expected
                                and not (allow_showcase and name[len(PREFIX):].startswith('out/v1.3-showcase/')))
                if extras:
                    detail = 'archive members outside the declared runtime payload: ' + ', '.join(extras[:10])
                    if strict_manifest:
                        problems.append(violation('RUNTIME_MANIFEST', detail))
                    else:
                        notes.append(detail)
                scripts = package.get('scripts') or {}
                for command in ('test', 'test:core', 'validate:all', 'preflight', 'package'):
                    if command not in scripts:
                        problems.append(violation('RUNTIME_METADATA',
                                                  f'runtime package is missing command {command}',
                                                  PREFIX + 'package.json'))
                if ('runtime_smoke.py' not in str(scripts.get('test', ''))
                        or '--tier auto' not in str(scripts.get('test', ''))):
                    problems.append(violation('RUNTIME_METADATA',
                                              'runtime test must invoke scripts/runtime_smoke.py --tier auto',
                                              PREFIX + 'package.json'))
                if '--tier core' not in str(scripts.get('test:core', '')):
                    problems.append(violation('RUNTIME_METADATA',
                                              'runtime test:core must invoke --tier core',
                                              PREFIX + 'package.json'))
                if 'tests/validate_examples.py' not in str(scripts.get('validate:all', '')):
                    problems.append(violation('RUNTIME_METADATA',
                                              'runtime validate:all must invoke tests/validate_examples.py',
                                              PREFIX + 'package.json'))
    elif profile == 'source':
        scripts = package.get('scripts') or {}
        if 'package:source' not in scripts:
            problems.append(violation('SOURCE_METADATA', 'source package is missing package:source',
                                      PREFIX + 'package.json'))
        if 'test:runtime' not in scripts:
            problems.append(violation('SOURCE_METADATA', 'source package is missing test:runtime',
                                      PREFIX + 'package.json'))
        if 'benchmark' not in scripts:
            problems.append(violation('SOURCE_METADATA',
                                      'source package must retain the full development benchmark command',
                                      PREFIX + 'package.json'))
    return problems, notes


def preflight(archive_path, allow_showcase=False, profile='auto', strict_manifest=False):
    path = Path(archive_path)
    report = {
        'status': 'FAIL',
        'archive': str(path),
        'sha256': None,
        'profile': None,
        'profile_reason': None,
        'entries': 0,
        'compressed_bytes': 0,
        'uncompressed_bytes': 0,
        'checks': {},
        'inventory': {
            'text_files': 0,
            'binary_files': 0,
            'hits': 0,
            'severity': {},
            'classification': {},
            'categories': {},
            'literals': {'wxect': {'exact': 0, 'casefold': 0,
                                   'exact_matches': [], 'casefold_matches': []}},
            'entries': [],
            'behavior': {},
        },
        'code_execution': {
            'status': 'FAIL',
            'mode': 'enforced',
            'python_parser': 'ast',
            'javascript_parser': 'lexical-string-comment-stripped',
            'files_scanned': 0,
            'findings': [],
            'development_findings': [],
            'report_only_findings': [],
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
        if profile == 'auto':
            profile, reason = detect_profile(names)
        else:
            reason = 'explicit profile selection'
        if profile not in PROFILES:
            problems.append(violation('PROFILE', f'unknown profile: {profile}'))
            report['status'] = 'FAIL'
            return report
        report['profile'] = profile
        report['profile_reason'] = reason
        report['code_execution']['mode'] = 'enforced'
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
        checks['metadata'] = {'status': 'PASS', 'profile': profile, 'notes': []}
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
                    mark('structure', 'FORBIDDEN_MEMBER',
                         'installer archives must not include generated out/ files', name)
                elif not relative.startswith('out/v1.3-showcase/'):
                    mark('structure', 'FORBIDDEN_MEMBER',
                         'showcase archives may include out/ only under out/v1.3-showcase/', name)
            base = PurePosixPath(relative).name
            if base in FORBIDDEN_NAMES or base.startswith(('.env.', 'credentials', 'secrets')):
                mark('structure', 'FORBIDDEN_MEMBER', 'private or secret-like file is not allowed', name)
            if base.endswith(FORBIDDEN_SUFFIXES):
                mark('structure', 'FORBIDDEN_MEMBER',
                     'compiled, credential, key or nested ZIP member is not allowed', name)
            suffix = PurePosixPath(relative).suffix.lower()
            if suffix in ('.pptx', '.pdf') and not (allow_showcase and relative.startswith('out/v1.3-showcase/')):
                mark('structure', 'FORBIDDEN_MEMBER',
                     'installer archives must not carry PPTX or PDF output', name)

        skill_names = [name for name in names if name.endswith('/SKILL.md')]
        if skill_names != [PREFIX + 'SKILL.md']:
            mark('skill', 'MULTIPLE_SKILL', f'expected exactly {PREFIX}SKILL.md, found {skill_names}')
        required = profile_required(profile)
        missing = sorted(PREFIX + name for name in required if PREFIX + name not in names)
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
                    mark('frontmatter', 'FRONTMATTER',
                         'SKILL.md name must be goujian-strategy-slides', PREFIX + 'SKILL.md')
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
                    mark('frontmatter', 'FRONTMATTER',
                         'SKILL.md description must be a JSON string', PREFIX + 'SKILL.md')
                else:
                    try:
                        if not json.loads(description):
                            mark('frontmatter', 'FRONTMATTER', 'SKILL.md description is empty',
                                 PREFIX + 'SKILL.md')
                    except ValueError:
                        mark('frontmatter', 'FRONTMATTER', 'SKILL.md description is not valid JSON',
                             PREFIX + 'SKILL.md')
        if package_text is not None and lock_text is not None and requirements_text is not None:
            dependency_problems = dependency_violations(package_text, lock_text, requirements_text)
            for problem in dependency_problems:
                checks['dependencies']['status'] = 'FAIL'
                problems.append(problem)

        metadata_problems, metadata_notes = runtime_metadata_violations(
            profile, contents, allow_showcase=allow_showcase, strict_manifest=strict_manifest)
        checks['metadata']['notes'] = metadata_notes
        for problem in metadata_problems:
            checks['metadata']['status'] = 'FAIL'
            problems.append(problem)

        code_extensions = {'.py': 'python', '.js': 'javascript',
                           '.cjs': 'javascript', '.mjs': 'javascript'}
        findings = []
        development_findings = []
        report_only_findings = []
        scanned = 0
        text_sources = {}
        exact_wxect = []
        casefold_wxect = []
        inventory_entries = []
        for name, data in contents.items():
            relative = name[len(PREFIX):] if name.startswith(PREFIX) else name
            extension = PurePosixPath(name).suffix.lower()
            language = code_extensions.get(extension)
            if language:
                try:
                    source = data.decode('utf-8')
                except UnicodeDecodeError:
                    findings.append(finding('TEXT_ENCODING', name, 0,
                                            'source file is not valid UTF-8'))
                    continue
                scanned += 1
                scope = scope_of(relative, profile)
                if language == 'python':
                    blocking, reported = scan_python_source(name, source, scope, profile)
                else:
                    blocking, reported = scan_javascript_source(name, source, scope, profile)
                findings.extend(blocking)
                development_findings.extend(item for item in reported
                                             if item['scope'] == 'development')
                report_only_findings.extend(item for item in reported
                                             if item['scope'] != 'development')
            if not text_kind(relative):
                continue
            try:
                source = data.decode('utf-8')
            except UnicodeDecodeError:
                mark('structure', 'TEXT_ENCODING', 'text member is not valid UTF-8', name)
                continue
            text_sources[name] = source
            exact, folded = scan_literal(name, source, 'wxect')
            exact_wxect.extend(exact)
            casefold_wxect.extend(folded)
            inventory_entries.extend(scan_inventory(name, source, relative, profile))

        report['code_execution']['files_scanned'] = scanned
        report['code_execution']['findings'] = findings
        report['code_execution']['development_findings'] = development_findings
        report['code_execution']['report_only_findings'] = report_only_findings
        if findings:
            checks['code_execution']['status'] = 'FAIL'
            for item in findings:
                problems.append(violation('CODE_EXECUTION',
                                          f'{item["kind"]}: {item["detail"]}', item['member']))
        else:
            report['code_execution']['status'] = 'PASS'
        if report_only_findings:
            checks['code_execution']['reported'] = len(report_only_findings)
        if development_findings:
            checks['code_execution']['development_reported'] = len(development_findings)

        inventory_entries.sort(key=lambda item: (item['member'], item['line'],
                                                 item['column'], item['category']))
        severity = {}
        classification = {}
        categories = {}
        for item in inventory_entries:
            severity[item['severity']] = severity.get(item['severity'], 0) + 1
            classification[item['classification']] = classification.get(item['classification'], 0) + 1
            categories[item['category']] = categories.get(item['category'], 0) + 1
        behavior = {
            category: {
                'count': categories.get(category, 0),
                'members': sorted({item['member'] for item in inventory_entries
                                   if item['category'] == category}),
            }
            for category in ('NETWORK', 'INSTALL', 'DELETE', 'PATH_ESCAPE', 'PATH_RESOLVE')
        }
        report['inventory'] = {
            'text_files': len(text_sources),
            'binary_files': len(contents) - len(text_sources),
            'hits': len(inventory_entries),
            'severity': severity,
            'classification': classification,
            'categories': categories,
            'literals': {
                'wxect': {
                    'exact': len(exact_wxect),
                    'casefold': len(casefold_wxect),
                    'exact_matches': exact_wxect,
                    'casefold_matches': casefold_wxect,
                }
            },
            'entries': inventory_entries,
            'behavior': behavior,
        }

    report['status'] = 'FAIL' if problems else 'PASS'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', nargs='?',
                        help='installer ZIP to inspect (default: the built runtime archive for this version)')
    parser.add_argument('--allow-showcase', action='store_true',
                        help='allow PPTX/PDF members only under out/v1.3-showcase/')
    parser.add_argument('--profile', choices=('auto',) + PROFILES, default='auto',
                        help='distribution profile (default: detect from the archive)')
    parser.add_argument('--strict-manifest', action='store_true',
                        help='reject archive members outside the declared runtime payload')
    parser.add_argument('--json', help='write the full report to this path')
    args = parser.parse_args(argv)
    if not args.archive:
        version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8')).get('version')
        default = ROOT / 'dist' / f'goujian-strategy-slides-v{version}.zip'
        if not default.is_file():
            parser.error(f'no archive supplied and the default runtime archive is missing: {default}; '
                         'run `npm run package` first')
        args.archive = str(default)
    report = preflight(args.archive, allow_showcase=args.allow_showcase,
                       profile=args.profile, strict_manifest=args.strict_manifest)
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8')
    summary = {
        'status': report['status'],
        'archive': report['archive'],
        'profile': report['profile'],
        'sha256': report['sha256'],
        'entries': report['entries'],
        'uncompressed_bytes': report['uncompressed_bytes'],
        'code_files_scanned': report['code_execution']['files_scanned'],
        'text_files_scanned': report['inventory']['text_files'],
        'inventory_hits': report['inventory']['hits'],
        'wxect_exact': report['inventory']['literals']['wxect']['exact'],
        'wxect_casefold': report['inventory']['literals']['wxect']['casefold'],
        'development_findings': len(report['code_execution']['development_findings']),
        'report_only_findings': len(report['code_execution']['report_only_findings']),
        'violations': len(report['violations']),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for item in report['violations']:
        print(f"{item['code']}: {item['detail']}" +
              (f" [{item['member']}]" if item.get('member') else ''), file=sys.stderr)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
