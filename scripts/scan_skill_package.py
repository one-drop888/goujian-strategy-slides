#!/usr/bin/env python3
"""Shared Goujian skill-package security gate.

Two independent operations live here:

``scan``
    Bind the archive to an expected version/commit (and optional SHA256), run
    the existing product preflight first, copy and extract the ZIP into a
    private directory with bounded safety checks, then invoke the pinned Cisco
    skill scanner with a fixed argument vector and a minimal environment. Raw
    JSON/SARIF/stdout/stderr are retained whether the gate passes or fails.
    HIGH/CRITICAL findings block unless an exact, independently approved review
    entry matches the rule, path, line, file hash, root SKILL hash, scanner
    version and policy.

``verify``
    Re-check a receipt before a release mutation. It re-hashes the actual ZIP,
    re-extracts it safely, checks the version/commit/config/lock/ledger
    bindings, re-hashes every raw report and recomputes the review-bound gate.
    It never invokes the Cisco scanner, but it is stdlib-only only when the
    receipt has no eligible PDF facts. With eligible PDF facts it re-runs the
    real-parser PDF checker on the extracted PDF and therefore needs the same
    hash-locked ``pypdf`` wheel.

The scanner environment is a separate development/tool dependency. It is not
part of the Goujian runtime, Bootstrap or production modules.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
DEFAULT_CONFIG = ROOT / 'security/security-gate.json'
DEFAULT_LOCAL_SCANNER = ROOT / '.venv-security/bin/skill-scanner'
GATE_NAME = 'GOUJIAN_SKILL_PACKAGE_SECURITY_GATE'
RECEIPT_SCHEMA = '1'
VALID_SEVERITIES = {'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'}
BLOCKING_SEVERITIES = {'CRITICAL', 'HIGH'}
MANDATORY_ANALYZERS = {'static_analyzer', 'behavioral_analyzer'}
PROFILES = ('runtime', 'source', 'showcase')
SHOWCASE_GENERATED_PREFIX = 'out/v1.3-showcase/'
REQUIRED_CHECKS = (
    'preflight',
    'source_identity',
    'scanner_version',
    'scanner_reports',
    'analyzer_evidence',
    'policy_fingerprint',
    'input_stability',
    'review_binding',
    'gate_threshold',
    'coverage_disclosure',
    'pdf_structural_review',
)
PDF_RULE_ID = 'PDF_STRUCTURAL_THREAT'
PDF_POLICY_ID = 'PDF_STRUCTURAL_OPENACTION_XYZ_LOCAL_PAGE_V1'
PDF_REQUIRED_KEYWORDS = {'/OpenAction': 1}
PDF_POLICY_STATUSES = {'PENDING_CODEX_REVIEW', 'APPROVED'}
PDF_CHECKER_REL = 'scripts/pdf_structural_check.py'
PDF_REQUIRED_CHECKS = frozenset({
    'file_hash', 'parser_available', 'strict_parse', 'not_encrypted',
    'xref_unambiguous', 'no_parser_warnings', 'root_catalog',
    'full_object_graph', 'within_limits', 'no_object_errors',
    'no_action_dictionaries', 'no_forbidden_keys',
    'no_forbidden_object_values', 'no_other_open_actions',
    'no_unsupported_a_contexts', 'no_invalid_a_values',
    'open_action_exact', 'open_action_page_local',
})
PDF_OPEN_ACTION_SHAPE = ['page-indirect-ref', '/XYZ', 'null', 'null', '0']
PDF_OPEN_ACTION_SUFFIX = [
    {'index': 1, 'type': 'name', 'value': '/XYZ'},
    {'index': 2, 'type': 'null', 'value': None},
    {'index': 3, 'type': 'null', 'value': None},
    {'index': 4, 'type': 'number', 'value': 0, 'text': '0'},
]
# Kept in sync with scripts/package_runtime.py by a unit regression test.
SOURCE_TOP_LEVEL = (
    'SKILL.md', 'core', 'skill', 'adapters', 'docs', 'tests', 'scripts', 'security',
    '.github', 'distribution', 'package.json', 'package-lock.json',
    'requirements-render.txt', 'README.md', 'README.zh-CN.md', 'README.en.md',
    'CONTRIBUTING.md', 'AGENTS.md', 'CHANGELOG.md', 'LICENSE',
    'THIRD_PARTY_NOTICE.md', '.gitignore',
)
SOURCE_EXCLUDED_TOP_LEVEL = {
    'node_modules', '.venv', 'venv', 'out', 'dist', 'build', '__pycache__', '.git',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', '.scratch', '.qoder',
}
SOURCE_EXCLUDED_SUFFIXES = ('.pyc', '.pptx', '.pdf')
SAFE_ENV_KEYS = {
    'PATH', 'LANG', 'LC_ALL', 'TZ', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE',
    'HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME',
}
FORBIDDEN_NAMES = {'.env', '.env.local', '.npmrc', '.netrc', '.DS_Store',
                   'id_rsa', 'id_ed25519'}
FORBIDDEN_SUFFIXES = ('.pyc', '.pem', '.key', '.p12', '.pfx', '.zip')
FORBIDDEN_DIRS = {'node_modules', '.venv', 'venv', '.git', '__pycache__',
                  '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', '.qoder'}
REVIEW_FIELDS = ('id', 'rule_id', 'path', 'line', 'file_sha256',
                 'root_skill_sha256', 'scanner_version', 'policy',
                 'policy_fingerprint_sha256',
                 'reviewer', 'reason', 'evidence', 'approved')


class GateFailure(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def fail(code, detail):
    raise GateFailure(code, detail)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path, code='MALFORMED_JSON'):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        fail(code, f'{path}: {error}')


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def descriptor(path):
    path = Path(path)
    if path.is_symlink():
        fail('UNSAFE_ARTIFACT', f'required artifact is a symlink: {path}')
    if not path.is_file():
        fail('MISSING_REPORT', f'required artifact is missing: {path}')
    return {'file': path.name, 'sha256': sha256_file(path), 'bytes': path.stat().st_size}


def safe_relative(path):
    """Normalize a scanner path while rejecting escapes and platform ambiguity."""
    if not isinstance(path, str) or not path:
        fail('UNSAFE_PATH', f'invalid package path: {path!r}')
    if path == '.':
        return '.'
    if '\\' in path or '\x00' in path or any(ord(char) < 32 for char in path):
        fail('UNSAFE_PATH', f'unsafe package path: {path!r}')
    if path.startswith('/') or re.match(r'^[A-Za-z]:', path):
        fail('UNSAFE_PATH', f'absolute package path: {path!r}')
    parts = PurePosixPath(path).parts
    if not parts or any(part in ('', '.', '..') for part in parts):
        fail('UNSAFE_PATH', f'unsafe package path: {path!r}')
    return PurePosixPath(*parts).as_posix()


def validate_archive_path(path):
    path = Path(path)
    if path.is_symlink():
        fail('UNSAFE_ARCHIVE', f'archive is a symlink: {path}')
    if not path.is_file():
        fail('UNSAFE_ARCHIVE', f'archive is not a regular file: {path}')
    if path.suffix.lower() != '.zip':
        fail('UNSAFE_ARCHIVE', f'archive must be a ZIP: {path}')
    return path


def load_config(path):
    config = read_json(path, 'INVALID_CONFIG')
    if config.get('schema_version') != 1:
        fail('INVALID_CONFIG', 'security gate config schema_version must be 1')
    scanner = config.get('scanner')
    if not isinstance(scanner, dict):
        fail('INVALID_CONFIG', 'scanner section is missing')
    if scanner.get('package') != 'cisco-ai-skill-scanner':
        fail('INVALID_CONFIG', 'scanner package must be cisco-ai-skill-scanner')
    if scanner.get('policy') != 'low-noise':
        fail('INVALID_CONFIG', 'scanner policy must be low-noise')
    if scanner.get('fail_on_severity') != 'high':
        fail('INVALID_CONFIG', 'fail-on severity must be high')
    if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+$', str(scanner.get('version'))):
        fail('INVALID_CONFIG', 'scanner version is invalid')
    if not re.match(r'^[0-9a-f]{64}$', str(scanner.get('wheel_sha256'))):
        fail('INVALID_CONFIG', 'scanner wheel hash is invalid')
    required = scanner.get('required_analyzers')
    allowed = scanner.get('allowed_analyzers')
    if not isinstance(required, list) or not required:
        fail('INVALID_CONFIG', 'required_analyzers must be a nonempty list')
    if not MANDATORY_ANALYZERS <= set(required):
        fail('INVALID_CONFIG',
             'required_analyzers must include static_analyzer and behavioral_analyzer')
    if not isinstance(allowed, list) or not set(required) <= set(allowed):
        fail('INVALID_CONFIG', 'allowed_analyzers must include required_analyzers')
    fingerprint = scanner.get('policy_fingerprint_sha256')
    if not isinstance(fingerprint, str) or not re.match(r'^[0-9a-f]{64}$', fingerprint):
        fail('INVALID_CONFIG', 'scanner policy_fingerprint_sha256 must be a pinned SHA256')
    env_keys = config.get('env_allowlist')
    if not isinstance(env_keys, list) or not set(env_keys) <= SAFE_ENV_KEYS:
        fail('INVALID_CONFIG', 'env_allowlist contains a non-allowlisted variable')
    limits = config.get('limits')
    if not isinstance(limits, dict):
        fail('INVALID_CONFIG', 'limits are missing')
    if not isinstance(config.get('lock'), dict) or not config['lock'].get('path'):
        fail('INVALID_CONFIG', 'lock section is missing')
    if not isinstance(config.get('review_ledger'), str) or not config['review_ledger']:
        fail('INVALID_CONFIG', 'review_ledger path is missing')
    pdf_review = config.get('pdf_review')
    if not isinstance(pdf_review, dict):
        fail('INVALID_CONFIG', 'pdf_review section is missing')
    for key in ('policy', 'parser_requirements'):
        if not isinstance(pdf_review.get(key), str) or not pdf_review[key]:
            fail('INVALID_CONFIG', f'pdf_review.{key} path is missing')
    for key in ('timeout_seconds', 'memory_bytes', 'cpu_seconds'):
        if not isinstance(pdf_review.get(key), int) or pdf_review[key] <= 0:
            fail('INVALID_CONFIG', f'invalid pdf_review limit: {key}')
    for key in ('max_archive_bytes', 'max_member_bytes', 'max_total_bytes',
                'max_compression_ratio', 'scan_timeout_seconds'):
        if not isinstance(limits.get(key), int) or limits[key] <= 0:
            fail('INVALID_CONFIG', f'invalid limit: {key}')
    coverage = config.get('behavioral_coverage')
    if not isinstance(coverage, dict) or coverage.get('javascript') != 'NOT_RUN' \
            or coverage.get('semantic') != 'NOT_RUN':
        fail('INVALID_CONFIG', 'behavioral coverage must disclose JavaScript/semantic NOT_RUN')
    return config


def load_lock(path, config):
    text = Path(path).read_text(encoding='utf-8')
    packages = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s;]+)\s+(.*)$', line)
        if not match:
            fail('INVALID_LOCK', f'unparseable locked requirement: {line[:120]}')
        name, version, rest = match.groups()
        if name in packages:
            fail('INVALID_LOCK', f'duplicate locked package: {name}')
        hashes = re.findall(r'--hash=sha256:([0-9a-f]{64})', rest)
        if not hashes or rest.replace(' ', '') != ''.join(f'--hash=sha256:{item}' for item in hashes):
            fail('INVALID_LOCK', f'package is not hash-locked exactly: {name}')
        expected = config['lock'].get('expected_package_count')
        packages[name] = {'version': version, 'sha256': hashes[0], 'hashes': hashes}
    if len(packages) != expected:
        fail('INVALID_LOCK', f'expected {expected} locked packages, found {len(packages)}')
    for name, version in (config['lock'].get('required_pins') or {}).items():
        if packages.get(name, {}).get('version') != version:
            fail('INVALID_LOCK', f'required pin {name}=={version} is missing')
    scanner = config['scanner']
    locked = packages.get(scanner['package'])
    if not locked or locked['version'] != scanner['version']:
        fail('INVALID_LOCK', 'scanner package is not pinned in the lock')
    if scanner['wheel_sha256'] not in locked['hashes']:
        fail('INVALID_LOCK', 'scanner wheel hash does not match the lock')
    return {'packages': len(packages), 'sha256': sha256_file(path),
            'scanner_package': scanner['package'], 'scanner_version': scanner['version']}


def config_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def checkout_relative(path):
    """Stable reviewed identity for a path inside this checkout.

    Paths outside the checkout (for example a temporary test policy) keep
    their actual location; tracked inputs compare as relative POSIX paths so a
    receipt remains verifiable from a differently rooted fresh clone.
    """
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def load_pdf_parser_lock(path, policy):
    text = Path(path).read_text(encoding='utf-8')
    requirements = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        requirements.append(line)
    if len(requirements) != 1:
        fail('INVALID_PDF_PARSER_LOCK',
             'the PDF parser lock must contain exactly one pinned requirement')
    match = re.match(
        r'^([A-Za-z0-9_.-]+)==([^\s;]+)\s+--hash=sha256:([0-9a-f]{64})$',
        requirements[0])
    if not match:
        fail('INVALID_PDF_PARSER_LOCK',
             f'the PDF parser requirement is not hash-locked exactly: {requirements[0][:160]}')
    name, version, wheel_sha = match.groups()
    parser = policy['parser']
    if name != parser['package'] or version != parser['version']:
        fail('INVALID_PDF_PARSER_LOCK',
             f'PDF parser lock {name}=={version} does not match the policy pin')
    if wheel_sha != parser['wheel_sha256']:
        fail('INVALID_PDF_PARSER_LOCK',
             'PDF parser wheel hash does not match the policy pin')
    if sha256_file(path) != parser['requirements_sha256']:
        fail('PDF_PARSER_LOCK_MISMATCH',
             'PDF parser requirements file changed after policy review')
    return {
        'path': str(path),
        'sha256': sha256_file(path),
        'packages': 1,
        'package': name,
        'version': version,
        'wheel_sha256': wheel_sha,
    }


def load_pdf_policy(path, config):
    policy = read_json(path, 'INVALID_PDF_POLICY')
    if policy.get('schema_version') != 1:
        fail('INVALID_PDF_POLICY', 'PDF policy schema_version must be 1')
    if policy.get('policy_id') != PDF_POLICY_ID:
        fail('INVALID_PDF_POLICY', f'PDF policy_id must be {PDF_POLICY_ID}')
    status = policy.get('status')
    if status not in PDF_POLICY_STATUSES:
        fail('INVALID_PDF_POLICY', 'PDF policy status is not recognized')
    binding = policy.get('rule_binding')
    if not isinstance(binding, dict) \
            or binding.get('rule_id') != PDF_RULE_ID \
            or binding.get('severity') != 'HIGH' \
            or binding.get('metadata_detected_keywords') != PDF_REQUIRED_KEYWORDS:
        fail('INVALID_PDF_POLICY',
             'PDF policy rule binding is not the exact PDF_STRUCTURAL_THREAT/HIGH/OpenAction rule')
    checker = policy.get('checker')
    if not isinstance(checker, dict) or checker.get('path') != PDF_CHECKER_REL:
        fail('INVALID_PDF_POLICY', 'PDF checker path is not the tracked checker')
    if not re.match(r'^[0-9a-f]{64}$', str(checker.get('sha256'))):
        fail('INVALID_PDF_POLICY', 'PDF checker sha256 is missing or malformed')
    checker_path = ROOT / PDF_CHECKER_REL
    checker_sha = sha256_file(checker_path)
    if checker_sha != checker['sha256']:
        fail('PDF_CHECKER_IDENTITY_MISMATCH',
             'tracked PDF checker bytes do not match the reviewed policy pin')
    parser = policy.get('parser')
    if not isinstance(parser, dict) or parser.get('package') != 'pypdf':
        fail('INVALID_PDF_POLICY', 'PDF parser must be pypdf')
    if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+$', str(parser.get('version'))):
        fail('INVALID_PDF_POLICY', 'PDF parser version is invalid')
    if not re.match(r'^[0-9a-f]{64}$', str(parser.get('wheel_sha256'))):
        fail('INVALID_PDF_POLICY', 'PDF parser wheel hash is invalid')
    if not re.match(r'^[0-9a-f]{64}$', str(parser.get('requirements_sha256'))):
        fail('INVALID_PDF_POLICY', 'PDF parser requirements hash is invalid')
    requirements_rel = parser.get('requirements')
    if requirements_rel != config['pdf_review']['parser_requirements']:
        fail('INVALID_PDF_POLICY',
             'PDF parser requirements path differs from the security gate config')
    requirements_path = config_path(requirements_rel)
    parser_lock = load_pdf_parser_lock(requirements_path, policy)
    semantics = policy.get('semantics')
    if not isinstance(semantics, dict):
        fail('INVALID_PDF_POLICY', 'PDF policy semantics are missing')
    for key in ('max_pdf_bytes', 'max_objects', 'max_depth'):
        if not isinstance(semantics.get(key), int) or semantics[key] <= 0:
            fail('INVALID_PDF_POLICY', f'invalid PDF semantic limit: {key}')
    approval = policy.get('approval') or {}
    if status == 'APPROVED':
        if not isinstance(approval.get('approved_by'), str) \
                or not approval['approved_by'].strip():
            fail('INVALID_PDF_POLICY',
                 'APPROVED PDF policy must name the independent approver')
        try:
            datetime.datetime.fromisoformat(
                str(approval.get('approved_at')).replace('Z', '+00:00'))
        except ValueError:
            fail('INVALID_PDF_POLICY',
                 'APPROVED PDF policy must carry an ISO-8601 approved_at')
    return {
        'path': str(path),
        'sha256': sha256_file(path),
        'id': policy['policy_id'],
        'status': status,
        'approved_by': approval.get('approved_by'),
        'approved_at': approval.get('approved_at'),
        'rule_id': binding['rule_id'],
        'severity': binding['severity'],
        'keywords': binding['metadata_detected_keywords'],
        'checker': {'path': str(checker_path), 'sha256': checker_sha,
                    'version': checker.get('version')},
        'parser': {
            'package': parser['package'],
            'version': parser['version'],
            'wheel': parser.get('wheel'),
            'wheel_sha256': parser['wheel_sha256'],
            'license': parser.get('license'),
            'requirements': requirements_rel,
            'requirements_sha256': parser.get('requirements_sha256'),
        },
        'requirements': parser_lock,
        'semantics': semantics,
    }


def validate_line(value, code='INVALID_REVIEW'):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        fail(code, f'review line must be a positive integer: {value!r}')
    return value


def review_identity(rule_id, path, line, file_sha256, root_skill_sha256,
                    scanner_version, policy):
    return '\x1f'.join([
        str(rule_id), str(path), str(line), str(file_sha256),
        str(root_skill_sha256), str(scanner_version), str(policy),
    ])


def load_ledger(path, config):
    ledger = read_json(path, 'INVALID_REVIEW_LEDGER')
    if ledger.get('schema_version') != 1:
        fail('INVALID_REVIEW_LEDGER', 'review ledger schema_version must be 1')
    if ledger.get('status') == 'PROPOSAL_NOT_APPROVED':
        fail('INVALID_REVIEW_LEDGER',
             'a review proposal is not an approved ledger; Codex approval is required')
    reviews = ledger.get('reviews')
    if not isinstance(reviews, list):
        fail('INVALID_REVIEW_LEDGER', 'reviews must be a list')
    seen = {}
    identities = {}
    for index, review in enumerate(reviews):
        label = f'reviews[{index}]'
        if not isinstance(review, dict):
            fail('INVALID_REVIEW_LEDGER', f'{label} must be an object')
        missing = [name for name in REVIEW_FIELDS if name not in review]
        if missing:
            fail('INVALID_REVIEW_LEDGER', f'{label} is missing {", ".join(missing)}')
        if review.get('approved') is not True:
            fail('INVALID_REVIEW_LEDGER', f'{label} is not approved')
        for name in ('id', 'rule_id', 'reviewer', 'reason', 'evidence'):
            if not isinstance(review.get(name), str) or not review[name].strip():
                fail('INVALID_REVIEW_LEDGER', f'{label}.{name} must be a nonempty string')
        path_value = review.get('path')
        if any(char in str(path_value) for char in '*?[]') or path_value == '.':
            fail('INVALID_REVIEW_LEDGER', f'{label}.path must be one exact file path')
        path_value = safe_relative(path_value)
        line = validate_line(review.get('line'), 'INVALID_REVIEW_LEDGER')
        for name in ('file_sha256', 'root_skill_sha256'):
            if not re.match(r'^[0-9a-f]{64}$', str(review.get(name))):
                fail('INVALID_REVIEW_LEDGER', f'{label}.{name} must be a SHA256')
        if review.get('scanner_version') != config['scanner']['version']:
            fail('INVALID_REVIEW_LEDGER', f'{label} was reviewed by a different scanner version')
        if review.get('policy') != config['scanner']['policy']:
            fail('INVALID_REVIEW_LEDGER', f'{label} was reviewed under a different policy')
        if review.get('policy_fingerprint_sha256') != config['scanner']['policy_fingerprint_sha256']:
            fail('INVALID_REVIEW_LEDGER',
                 f'{label} was reviewed under a different policy fingerprint')
        expires = review.get('expires_at')
        if expires is not None:
            try:
                expiry = datetime.datetime.fromisoformat(str(expires).replace('Z', '+00:00'))
            except ValueError:
                fail('INVALID_REVIEW_LEDGER', f'{label}.expires_at is not ISO-8601')
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=datetime.timezone.utc)
            if expiry < datetime.datetime.now(datetime.timezone.utc):
                fail('STALE_REVIEW', f'{label} expired at {expires}')
        identity = review_identity(review['rule_id'], path_value, line,
                                   review['file_sha256'], review['root_skill_sha256'],
                                   review['scanner_version'], review['policy'])
        if identity in identities:
            fail('INVALID_REVIEW_LEDGER', f'{label} duplicates another review')
        identities[identity] = review
        if review['id'] in seen:
            fail('INVALID_REVIEW_LEDGER', f'duplicate review id: {review["id"]}')
        seen[review['id']] = review
    return {'reviews': reviews, 'identities': identities,
            'sha256': sha256_file(path), 'count': len(reviews)}


def inspect_zip(archive, limits):
    archive = Path(archive)
    infos = []
    names = set()
    folded = set()
    total = 0
    with zipfile.ZipFile(archive) as package:
        if package.comment:
            fail('UNSAFE_ARCHIVE', 'ZIP comment is not allowed')
        for info in package.infolist():
            name = info.filename
            if name.endswith('/'):
                fail('UNSAFE_ARCHIVE', f'directory entry is not allowed: {name}')
            relative = safe_relative(name[len(PREFIX):] if name.startswith(PREFIX) else name)
            if not name.startswith(PREFIX):
                fail('UNSAFE_ARCHIVE', f'member outside the declared prefix: {name}')
            if name != PREFIX + relative:
                fail('UNSAFE_ARCHIVE', f'non-canonical member path: {name}')
            if name in names:
                fail('UNSAFE_ARCHIVE', f'duplicate member: {name}')
            if name.casefold() in folded:
                fail('UNSAFE_ARCHIVE', f'case-folded duplicate member: {name}')
            names.add(name)
            folded.add(name.casefold())
            if info.flag_bits & 0x1:
                fail('UNSAFE_ARCHIVE', f'encrypted member: {name}')
            mode = (info.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(mode)
            permissions = stat.S_IMODE(mode)
            if file_type not in (0, stat.S_IFREG):
                fail('UNSAFE_ARCHIVE', f'non-regular member or symlink: {name}')
            if permissions not in (0, 0o644, 0o755):
                fail('UNSAFE_ARCHIVE', f'unsafe file mode {permissions:o}: {name}')
            if mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
                fail('UNSAFE_ARCHIVE', f'setuid/setgid/sticky mode: {name}')
            parts = set(PurePosixPath(relative).parts)
            if parts & FORBIDDEN_DIRS:
                fail('UNSAFE_ARCHIVE', f'forbidden directory member: {name}')
            base = PurePosixPath(relative).name
            if base in FORBIDDEN_NAMES or base.startswith(('.env.', 'credentials', 'secrets')):
                fail('UNSAFE_ARCHIVE', f'private or secret-like member: {name}')
            if base.endswith(FORBIDDEN_SUFFIXES):
                fail('UNSAFE_ARCHIVE', f'forbidden member type: {name}')
            if info.file_size > limits['max_member_bytes']:
                fail('UNSAFE_ARCHIVE', f'member is too large: {name}')
            if info.compress_size and info.file_size > 1024 * 1024:
                ratio = info.file_size / info.compress_size
                if ratio > limits['max_compression_ratio']:
                    fail('UNSAFE_ARCHIVE', f'compression ratio is unsafe: {name}')
            total += info.file_size
            if total > limits['max_total_bytes']:
                fail('UNSAFE_ARCHIVE', 'archive expands beyond the total size limit')
            infos.append(info)
    if not infos:
        fail('UNSAFE_ARCHIVE', 'archive is empty')
    if [name for name in names if name.endswith('/SKILL.md')] != [PREFIX + 'SKILL.md']:
        fail('UNSAFE_ARCHIVE', 'archive must contain exactly one root SKILL.md')
    return infos


def extract_zip(archive, target, limits):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    total = 0
    with zipfile.ZipFile(archive) as package:
        for info in inspect_zip(archive, limits):
            relative = info.filename[len(PREFIX):]
            destination = target / PurePosixPath(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.is_symlink():
                fail('UNSAFE_ARCHIVE', f'symlink parent in extraction: {relative}')
            mode = 0o755 if stat.S_IMODE((info.external_attr >> 16) & 0xFFFF) == 0o755 else 0o644
            written = 0
            with package.open(info) as source:
                with destination.open('xb') as target_handle:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        total += len(chunk)
                        if written > limits['max_member_bytes']:
                            fail('UNSAFE_ARCHIVE', f'member exceeded the size limit: {relative}')
                        if total > limits['max_total_bytes']:
                            fail('UNSAFE_ARCHIVE', 'archive exceeded the total size limit')
                        target_handle.write(chunk)
            os.chmod(destination, mode)
    tree_sha, count = tree_digest(target)
    return {'files': count, 'sha256': tree_sha}


def tree_digest(root):
    root = Path(root)
    rows = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            fail('INPUT_DRIFT', f'symlink appeared in extracted tree: {path}')
        if path.is_file():
            rows.append('{}  {:o}  {}'.format(
                sha256_file(path), stat.S_IMODE(path.stat().st_mode),
                path.relative_to(root).as_posix()))
    digest = sha256_bytes(('\n'.join(rows) + '\n').encode('utf-8'))
    return digest, len(rows)


def prepare_output_dir(path):
    """Require a fresh, non-symlinked directory so old evidence is never reused."""
    path = Path(path)
    if not path.is_absolute():
        path = Path.cwd() / path
    for parent in [path, *path.parents]:
        if parent != path and parent.is_symlink():
            fail('OUTPUT_UNSAFE', f'output directory has a symlinked parent: {parent}')
    if path.is_symlink():
        fail('OUTPUT_UNSAFE', f'output directory is a symlink: {path}')
    if path.exists():
        if not path.is_dir():
            fail('OUTPUT_UNSAFE', f'output path is not a directory: {path}')
        if any(path.iterdir()):
            fail('OUTPUT_NOT_EMPTY',
                 f'output directory is not empty; refuse to reuse or overwrite evidence: {path}')
    else:
        try:
            path.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            fail('OUTPUT_NOT_EMPTY', f'output directory appeared concurrently: {path}')
        except OSError as error:
            fail('OUTPUT_UNSAFE', f'cannot create output directory {path}: {error}')
    if path.is_symlink() or not path.is_dir():
        fail('OUTPUT_UNSAFE', f'output directory is not a safe directory: {path}')
    return path


def bounded_copy(source, destination, limits, expected_sha):
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or not source.is_file():
        fail('UNSAFE_ARCHIVE', f'archive is not a regular file: {source}')
    size = source.stat().st_size
    if size > limits['max_archive_bytes']:
        fail('ARCHIVE_TOO_LARGE',
             f'archive is {size} bytes; limit {limits["max_archive_bytes"]}')
    try:
        free = shutil.disk_usage(destination.parent).free
    except OSError:
        free = None
    if free is not None and free < size * 2 + (16 * 1024 * 1024):
        fail('INSUFFICIENT_DISK', 'private snapshot copy has insufficient free disk space')
    total = 0
    with source.open('rb') as reader, destination.open('xb') as writer:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limits['max_archive_bytes']:
                fail('ARCHIVE_TOO_LARGE', 'archive grew beyond the bounded copy limit')
            writer.write(chunk)
    if total != size:
        fail('INPUT_DRIFT', 'archive size changed while it was copied')
    if sha256_file(destination) != expected_sha:
        fail('INPUT_DRIFT', 'private snapshot does not match the expected archive bytes')
    return {'file': destination.name, 'sha256': expected_sha, 'bytes': total}


def run_git(repo, *args, input_bytes=None):
    command = ['git', '-C', str(repo), *args]
    try:
        result = subprocess.run(command, input=input_bytes, capture_output=True,
                                timeout=300)
    except (OSError, subprocess.SubprocessError) as error:
        fail('SOURCE_MATCH_UNAVAILABLE', f'git is unavailable: {error}')
    if result.returncode != 0:
        detail = result.stderr.decode('utf-8', errors='replace').strip()[:400]
        fail('SOURCE_MATCH_UNAVAILABLE', f'git {" ".join(args)} failed: {detail}')
    return result.stdout


def git_tree(repo, commit):
    output = run_git(repo, 'ls-tree', '-r', '-z', '--full-tree', commit)
    tree = {}
    for entry in output.split(b'\x00'):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b'\t', 1)
            mode, kind, object_id = metadata.split(b' ')
        except ValueError:
            fail('SOURCE_MATCH_UNAVAILABLE', 'git ls-tree returned an unparseable entry')
        if kind != b'blob':
            fail('SOURCE_MISMATCH', f'commit contains a non-blob entry: {raw_path!r}')
        tree[raw_path.decode('utf-8')] = {
            'mode': mode.decode('ascii'), 'object': object_id.decode('ascii'),
        }
    return tree


def git_blobs(repo, object_ids):
    unique = sorted(set(object_ids))
    if not unique:
        return {}
    request = ''.join(item + '\n' for item in unique).encode('ascii')
    output = run_git(repo, 'cat-file', '--batch', input_bytes=request)
    blobs = {}
    offset = 0
    for object_id in unique:
        newline = output.find(b'\n', offset)
        if newline < 0:
            fail('SOURCE_MATCH_UNAVAILABLE', 'git cat-file output ended unexpectedly')
        header = output[offset:newline].split(b' ')
        if len(header) != 3 or header[1] != b'blob':
            fail('SOURCE_MATCH_UNAVAILABLE', f'git cat-file failed for {object_id}')
        size = int(header[2])
        start = newline + 1
        end = start + size
        blobs[object_id] = output[start:end]
        offset = end + 1
    return blobs


def source_expected_paths(tree, profile):
    if profile == 'runtime':
        return None
    if profile != 'source':
        return None
    expected = set()
    for path in tree:
        parts = PurePosixPath(path).parts
        if not parts or parts[0] not in SOURCE_TOP_LEVEL:
            continue
        if set(parts) & SOURCE_EXCLUDED_TOP_LEVEL:
            continue
        if path.endswith(SOURCE_EXCLUDED_SUFFIXES):
            continue
        expected.add(path)
    return expected


def verify_source_identity(root, profile, commit, repo):
    """Prove archive members equal blobs at the approved Git commit."""
    root = Path(root)
    repo = Path(repo)
    if not repo.is_dir():
        fail('SOURCE_MATCH_UNAVAILABLE', f'git repository is not a directory: {repo}')
    resolved = run_git(repo, 'rev-parse', '--verify', f'{commit}^{{commit}}') \
        .decode('utf-8', errors='replace').strip()
    if resolved != commit:
        fail('SOURCE_MATCH_UNAVAILABLE',
             f'commit {commit} does not resolve to itself in {repo}')
    tree = git_tree(repo, commit)
    actual = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            fail('SOURCE_MISMATCH', f'symlink in archive tree: {path}')
        if path.is_file():
            actual[path.relative_to(root).as_posix()] = path
    mapping_source = None
    expected_members = None
    generated = []
    if profile in ('runtime', 'showcase'):
        manifest_path = 'distribution/runtime-manifest.json'
        if manifest_path not in tree:
            fail('SOURCE_MISMATCH', f'{manifest_path} is not tracked at {commit}')
        mapping_source = 'distribution/runtime-package.json'
        if mapping_source not in tree:
            fail('SOURCE_MISMATCH', f'{mapping_source} is not tracked at {commit}')
        blobs = git_blobs(repo, [tree[manifest_path]['object'],
                                 tree[mapping_source]['object']])
        try:
            manifest = json.loads(blobs[tree[manifest_path]['object']].decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            fail('SOURCE_MISMATCH', 'runtime manifest at the commit is not valid JSON')
        runtime_files = manifest.get('runtime_files')
        if not isinstance(runtime_files, list) or not runtime_files:
            fail('SOURCE_MISMATCH', 'runtime manifest has no runtime_files')
        expected_members = set(runtime_files) | {'package.json'}
        if profile == 'showcase':
            generated = sorted(
                path for path in actual if path.startswith(SHOWCASE_GENERATED_PREFIX))
            expected_members |= set(generated)
    expected = source_expected_paths(tree, profile)
    if expected is not None:
        expected_members = expected
    if expected_members is not None and set(actual) != expected_members:
        missing = sorted(expected_members - set(actual))
        extra = sorted(set(actual) - expected_members)
        fail('SOURCE_MISMATCH',
             f'archive member set differs from {commit}: '
             f'missing={missing[:6]} extra={extra[:6]}')
    blobs = {}
    needed = []
    for relative in actual:
        if profile == 'showcase' and relative.startswith(SHOWCASE_GENERATED_PREFIX):
            continue
        source_relative = mapping_source if relative == 'package.json' and mapping_source \
            else relative
        if source_relative not in tree:
            fail('SOURCE_MISMATCH', f'{relative} is not tracked at {commit}')
        needed.append(tree[source_relative]['object'])
    blobs = git_blobs(repo, needed)
    rows = []
    compared = 0
    for relative in sorted(actual):
        if profile == 'showcase' and relative.startswith(SHOWCASE_GENERATED_PREFIX):
            continue
        source_relative = mapping_source if relative == 'package.json' and mapping_source \
            else relative
        object_id = tree[source_relative]['object']
        actual_bytes = actual[relative].read_bytes()
        if actual_bytes != blobs[object_id]:
            fail('SOURCE_MISMATCH',
                 f'{relative} differs from {commit}:{source_relative}')
        rows.append(f'{relative}  {sha256_bytes(actual_bytes)}')
        compared += 1
    if not compared:
        fail('SOURCE_MISMATCH', 'archive contains no comparable tracked members')
    return {
        'commit': commit,
        'profile': profile,
        'repo': str(repo),
        'compared_members': compared,
        'mapped_members': ['package.json -> ' + mapping_source] if mapping_source else [],
        'generated_exception': generated,
        'member_digest_sha256': sha256_bytes(('\n'.join(rows) + '\n').encode('utf-8')),
    }


def scanner_environment(config, run_root):
    env = {key: os.environ[key] for key in config['env_allowlist'] if key in os.environ}
    home = Path(run_root) / 'home'
    tmp = Path(run_root) / 'tmp'
    cache = Path(run_root) / 'cache'
    for path in (home, tmp, cache):
        path.mkdir(parents=True, exist_ok=True)
    env.update({
        'PATH': env.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
        'LANG': 'C.UTF-8',
        'LC_ALL': 'C.UTF-8',
        'TZ': 'UTC',
        'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'HOME': str(home),
        'TMPDIR': str(tmp),
        'XDG_CACHE_HOME': str(cache),
        'XDG_CONFIG_HOME': str(home / '.config'),
    })
    return env


def child_rlimit_target(requested, soft, hard, infinite):
    """Clamp a requested limit; never loosen an existing soft/hard limit."""
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 0:
        raise ValueError(f'invalid resource limit: {requested!r}')
    target = requested
    if hard != infinite:
        target = min(target, hard)
    if soft != infinite:
        target = min(target, soft)
    return target


def run_bounded(command, cwd, env, timeout, limits=None):
    preexec = None
    if limits is not None:
        try:
            import resource
        except ImportError as error:
            fail('RESOURCE_LIMITS_UNAVAILABLE',
                 f'cannot enforce child resource limits: {error}')
        specs = (
            ('RLIMIT_AS', limits.get('memory_bytes')),
            ('RLIMIT_CPU', limits.get('cpu_seconds')),
            ('RLIMIT_NOFILE', limits.get('open_files', 64)),
            ('RLIMIT_FSIZE', limits.get('file_bytes', 64 * 1024 * 1024)),
        )
        missing = [name for name, value in specs
                   if value is not None and not hasattr(resource, name)]
        if missing:
            fail('RESOURCE_LIMITS_UNAVAILABLE',
                 'required RLIMIT is unavailable: ' + ', '.join(missing))

        def preexec():  # noqa: F811 - child-only resource limits
            infinite = getattr(resource, 'RLIM_INFINITY', -1)
            for name, value in specs:
                if value is None:
                    continue
                resource_id = getattr(resource, name)
                soft, hard = resource.getrlimit(resource_id)
                target = child_rlimit_target(value, soft, hard, infinite)
                resource.setrlimit(resource_id, (target, target))
    try:
        process = subprocess.Popen(
            command, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, preexec_fn=preexec)
    except subprocess.SubprocessError as error:
        fail('RESOURCE_LIMITS_FAILED',
             f'the child process could not apply its resource limits: {error}')
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr, 'completed'
    except subprocess.TimeoutExpired:
        if hasattr(os, 'killpg'):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        stdout, stderr = process.communicate()
        return None, stdout, stderr, 'timeout'


def run_preflight(archive, profile, out_dir, config, timeout):
    command = [sys.executable, str(ROOT / 'scripts/security_preflight.py'), str(archive)]
    if profile == 'runtime':
        command += ['--profile', 'runtime', '--strict-manifest']
    elif profile == 'source':
        command += ['--profile', 'source']
    elif profile == 'showcase':
        command += ['--profile', 'runtime', '--allow-showcase']
    else:
        fail('INVALID_PROFILE', f'unknown profile: {profile}')
    report_path = Path(out_dir) / 'preflight.json'
    command += ['--json', str(report_path)]
    env = scanner_environment(config, Path(out_dir) / 'preflight-env')
    status, stdout, stderr, outcome = run_bounded(command, ROOT, env, timeout)
    write_bytes(Path(out_dir) / 'preflight.stdout.log', stdout)
    write_bytes(Path(out_dir) / 'preflight.stderr.log', stderr)
    report = None
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding='utf-8'))
        except ValueError:
            fail('MALFORMED_PREFLIGHT_REPORT', 'preflight report is not valid JSON')
    if outcome != 'completed':
        fail('PREFLIGHT_TIMEOUT', 'preflight exceeded its timeout')
    if status != 0:
        detail = 'preflight rejected the archive'
        if report and report.get('violations'):
            detail += ': ' + '; '.join(
                str(item.get('code')) for item in report['violations'][:8])
        fail('PREFLIGHT_FAILED', detail)
    if not report or report.get('status') != 'PASS':
        fail('PREFLIGHT_FAILED', 'preflight did not report PASS')
    report_sha = sha256_file(report_path)
    return {'status': 'PASS', 'profile': report.get('profile'),
            'file': 'preflight.json', 'report': 'preflight.json',
            'sha256': report_sha, 'report_sha256': report_sha,
            'bytes': report_path.stat().st_size,
            'archive_sha256': report.get('sha256')}


def run_scanner(scanner, target, out_dir, config, timeout):
    scanner = Path(scanner)
    if scanner.is_symlink() or not scanner.is_file():
        fail('SCANNER_UNAVAILABLE', f'scanner is not a regular file: {scanner}')
    env = scanner_environment(config, Path(out_dir) / 'scanner-env')
    version_status, version_out, version_err, version_outcome = run_bounded(
        [str(scanner), '--version'], Path(out_dir) / 'scanner-env',
        env, 60)
    if version_outcome != 'completed' or version_status != 0:
        fail('SCANNER_UNAVAILABLE', 'scanner version probe failed')
    match = re.search(r'([0-9]+\.[0-9]+\.[0-9]+)',
                      (version_out + version_err).decode('utf-8', errors='replace'))
    actual_version = match.group(1) if match else None
    expected_version = config['scanner']['version']
    if actual_version != expected_version:
        fail('SCANNER_VERSION_MISMATCH',
             f'expected skill-scanner {expected_version}, found {actual_version!r}')
    json_path = Path(out_dir) / 'scanner.json'
    sarif_path = Path(out_dir) / 'scanner.sarif'
    command = [
        str(scanner), 'scan', str(target),
        '--policy', config['scanner']['policy'],
        '--use-behavioral',
        '--format', 'json',
        '--format', 'sarif',
        '--output-json', str(json_path),
        '--output-sarif', str(sarif_path),
        '--fail-on-severity', config['scanner']['fail_on_severity'],
    ]
    status, stdout, stderr, outcome = run_bounded(
        command, Path(out_dir) / 'scanner-env', env, timeout)
    write_bytes(Path(out_dir) / 'scanner.stdout.log', stdout)
    write_bytes(Path(out_dir) / 'scanner.stderr.log', stderr)
    return {
        'command': command,
        'version': actual_version,
        'binary_sha256': sha256_file(scanner),
        'status': outcome,
        'exit_code': status,
        'env_keys': sorted(env),
        'json_path': json_path,
        'sarif_path': sarif_path,
        'stdout': stdout,
        'stderr': stderr,
    }


def normalize_finding_path(root, value):
    root = Path(root)
    if value == '.' or value is None:
        return '.'
    candidate = Path(str(value))
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(root.resolve())
        except ValueError:
            fail('MALFORMED_REPORT', f'finding path escapes the package: {value}')
        return safe_relative(relative.as_posix())
    return safe_relative(str(value))


def validate_scanner_report(raw, config):
    if not isinstance(raw, dict):
        fail('MALFORMED_REPORT', 'scanner JSON must be an object')
    findings = raw.get('findings')
    if not isinstance(findings, list):
        fail('MALFORMED_REPORT', 'scanner JSON findings must be a list')
    if raw.get('findings_count') != len(findings):
        fail('MALFORMED_REPORT', 'findings_count does not match findings')
    used = raw.get('analyzers_used')
    if not isinstance(used, list) or not used:
        fail('MISSING_ANALYZER', 'analyzers_used is missing or empty')
    missing = [name for name in config['scanner']['required_analyzers'] if name not in used]
    if missing:
        fail('MISSING_ANALYZER', 'required analyzer evidence is missing: ' + ', '.join(missing))
    unexpected = [name for name in used if name not in config['scanner']['allowed_analyzers']]
    if unexpected:
        fail('UNEXPECTED_ANALYZER', 'unexpected analyzer evidence: ' + ', '.join(unexpected))
    failed = raw.get('analyzers_failed')
    if failed:
        fail('ANALYZER_ERROR', 'analyzers_failed is not empty: ' + json.dumps(failed))
    metadata = raw.get('scan_metadata')
    if not isinstance(metadata, dict):
        fail('MALFORMED_REPORT', 'scan_metadata is missing')
    if metadata.get('policy_name') != config['scanner']['policy']:
        fail('POLICY_MISMATCH', f'policy is {metadata.get("policy_name")!r}, '
                                f'expected {config["scanner"]["policy"]!r}')
    fingerprint = metadata.get('policy_fingerprint_sha256')
    if not isinstance(fingerprint, str) or not re.match(r'^[0-9a-f]{64}$', fingerprint):
        fail('POLICY_MISMATCH', 'scanner policy fingerprint is missing or malformed')
    if fingerprint != config['scanner']['policy_fingerprint_sha256']:
        fail('POLICY_MISMATCH',
             'scanner policy fingerprint differs from the trusted config pin')
    contract = metadata.get('rule_contract')
    if not isinstance(contract, dict) or contract.get('status') != 'passed' \
            or contract.get('invalid_findings') != 0 or contract.get('errors'):
        fail('ANALYZER_ERROR', 'rule contract did not pass')
    cel = metadata.get('cel')
    if not isinstance(cel, dict):
        fail('ANALYZER_ERROR', 'CEL evidence is missing')
    if cel.get('errors'):
        fail('ANALYZER_ERROR', 'CEL reported errors')
    if cel.get('suppressed') or cel.get('fallbacks') \
            or cel.get('projection_incomplete'):
        fail('ANALYZER_ERROR', 'CEL suppressed or degraded findings unexpectedly')
    for finding in findings:
        if not isinstance(finding, dict):
            fail('MALFORMED_REPORT', 'finding entry is not an object')
        if finding.get('severity') not in VALID_SEVERITIES:
            fail('MALFORMED_REPORT', f'unknown severity: {finding.get("severity")!r}')
        if not isinstance(finding.get('rule_id'), str) or not finding['rule_id']:
            fail('MALFORMED_REPORT', 'finding rule_id is missing')
    return {
        'findings': findings,
        'analyzers_used': used,
        'analyzers_failed': failed or [],
        'policy_name': metadata.get('policy_name'),
        'policy_fingerprint_sha256': fingerprint,
        'rule_contract': contract,
        'cel': cel,
    }


def validate_sarif(raw, finding_count):
    if not isinstance(raw, dict) or not isinstance(raw.get('runs'), list) or not raw['runs']:
        fail('MALFORMED_SARIF', 'SARIF must contain at least one run')
    result_count = 0
    for run in raw['runs']:
        invocations = run.get('invocations')
        if not isinstance(invocations, list) or not invocations:
            fail('MALFORMED_SARIF', 'SARIF run has no invocations')
        for invocation in invocations:
            if invocation.get('executionSuccessful') is not True:
                fail('MALFORMED_SARIF', 'SARIF executionSuccessful is not true')
            for notification in invocation.get('toolExecutionNotifications') or []:
                if notification.get('level') == 'error':
                    fail('MALFORMED_SARIF', 'SARIF contains an execution error notification')
        results = run.get('results')
        if not isinstance(results, list):
            fail('MALFORMED_SARIF', 'SARIF results must be a list')
        result_count += len(results)
    if result_count != finding_count:
        fail('MALFORMED_SARIF',
             f'SARIF results {result_count} do not match findings {finding_count}')


def finding_file_hash(root, relative):
    if relative == '.':
        return None
    path = Path(root) / PurePosixPath(relative)
    if not path.is_file() or path.is_symlink():
        return None
    return sha256_file(path)


def classify(severity, reviewed):
    if severity in BLOCKING_SEVERITIES:
        return 'reviewed-exception' if reviewed else 'blocking-unreviewed'
    if severity == 'MEDIUM':
        return 'conditional-review'
    if severity == 'LOW':
        return 'triage-noise'
    return 'informational'


def binary_byte_offset(finding):
    snippet = str(finding.get('snippet') or '')
    match = re.search(r'byte offset\s+(\d+)', snippet)
    if match:
        return int(match.group(1))
    metadata = finding.get('metadata')
    if isinstance(metadata, dict):
        for key in ('byte_offset', 'offset', 'match_offset'):
            value = metadata.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
    return None


def location_of(finding):
    line = finding.get('line_number')
    if line is None:
        return 'whole_file_signal', None
    if line == 0:
        offset = binary_byte_offset(finding)
        if offset is not None or '[binary' in str(finding.get('snippet') or '').lower():
            return 'binary_byte_offset', offset
        return 'zero_line_marker', None
    return 'source_line', None


def present_paths(root):
    root = Path(root)
    found = set()
    for path in root.rglob('*'):
        if path.is_file() and not path.is_symlink():
            found.add(path.relative_to(root).as_posix())
    return found


def triage_record(severity, reviewed, review):
    if reviewed:
        return {
            'owner': 'independent-reviewer',
            'disposition': 'retained-reviewed-exception',
            'review_status': 'APPROVED_EXACT_MATCH',
            'rationale': review.get('reason'),
        }
    if severity in BLOCKING_SEVERITIES:
        return {
            'owner': 'security-reviewer',
            'disposition': 'requires-independent-review',
            'review_status': 'PENDING_INDEPENDENT_REVIEW',
            'rationale': 'Blocks release until an exact, content-bound review is approved.',
        }
    if severity == 'MEDIUM':
        return {
            'owner': 'security-reviewer',
            'disposition': 'retained-triage-required',
            'review_status': 'TRIAGE_RECORDED_NOT_A_WAIVER',
            'rationale': ('Non-blocking at the pinned HIGH threshold; raw finding retained '
                          'and assigned for documented security triage.'),
        }
    if severity == 'LOW':
        return {
            'owner': 'release-maintainers',
            'disposition': 'retained-triage-required',
            'review_status': 'TRIAGE_RECORDED_NOT_A_WAIVER',
            'rationale': ('Below the blocking threshold; raw finding retained for documented '
                          'release-maintainer triage. This record does not waive anything.'),
        }
    return {
        'owner': 'release-maintainers',
        'disposition': 'retained-informational',
        'review_status': 'INFORMATION_ONLY',
        'rationale': 'Informational raw finding retained without suppression.',
    }


def evaluate_findings(raw_findings, root, root_skill_sha, config, ledger):
    blocking = []
    summaries = []
    identities = ledger['identities']
    matched = set()
    present = present_paths(root)
    for finding in raw_findings:
        severity = finding['severity']
        relative = normalize_finding_path(root, finding.get('file_path'))
        file_sha = finding_file_hash(root, relative)
        line = finding.get('line_number')
        if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line < 0):
            fail('MALFORMED_REPORT', f'invalid finding line: {line!r}')
        location_kind, byte_offset = location_of(finding)
        identity = None
        reviewed = False
        review = None
        if severity in BLOCKING_SEVERITIES and line is not None and file_sha:
            identity = review_identity(finding['rule_id'], relative, line, file_sha,
                                       root_skill_sha, config['scanner']['version'],
                                       config['scanner']['policy'])
            if identity in identities:
                reviewed = True
                review = identities[identity]
                matched.add(identity)
        if severity in BLOCKING_SEVERITIES and not reviewed:
            blocking.append(finding)
        triage = triage_record(severity, reviewed, review)
        summaries.append({
            'finding_id': finding.get('id'),
            'rule_id': finding['rule_id'],
            'severity': severity,
            'path': relative,
            'line': line,
            'location_kind': location_kind,
            'byte_offset': byte_offset,
            'file_sha256': file_sha,
            'root_skill_sha256': root_skill_sha,
            'classification': classify(severity, reviewed),
            'review_identity': identity,
            **triage,
        })
    stale = []
    not_applicable = []
    for identity, review in identities.items():
        path = safe_relative(review['path'])
        if path not in present:
            not_applicable.append({
                'id': review['id'],
                'path': path,
                'reason': 'reviewed file is not present in this package profile',
            })
        elif identity not in matched:
            stale.append({'id': review['id'], 'path': path})
    if stale:
        fail('STALE_REVIEW',
             f'{len(stale)} applicable review(s) no longer match current bytes/lines: '
             + ', '.join(item['id'] for item in stale[:8]))
    scope = {
        'matched': len(matched),
        'not_applicable': sorted(not_applicable, key=lambda item: item['id']),
        'applicable_stale': 0,
    }
    return summaries, blocking, matched, scope


def build_proposal(summaries, report_sha, scanner_version, policy,
                   policy_fingerprint, root_skill_sha):
    reviews = []
    for item in summaries:
        reviews.append({
            'id': 'proposal-' + sha256_bytes(json.dumps(
                [item['rule_id'], item['path'], item['line'], item['file_sha256'],
                 item['root_skill_sha256']], sort_keys=True).encode('utf-8'))[:16],
            'rule_id': item['rule_id'],
            'path': item['path'],
            'line': item['line'],
            'location_kind': item['location_kind'],
            'byte_offset': item['byte_offset'],
            'file_sha256': item['file_sha256'],
            'root_skill_sha256': item['root_skill_sha256'],
            'scanner_version': scanner_version,
            'policy': policy,
            'policy_fingerprint_sha256': policy_fingerprint,
            'reviewer': 'PENDING_INDEPENDENT_REVIEW',
            'reason': 'PENDING independent review; this proposal is not approval',
            'evidence': {'raw_report_sha256': report_sha,
                         'finding_id': item['finding_id'],
                         'severity': item['severity'],
                         'classification': item['classification']},
            'approved': False,
            'severity': item['severity'],
            'disposition': item['disposition'],
        })
    return {
        'schema_version': 1,
        'status': 'PROPOSAL_NOT_APPROVED',
        'generated_at': utc_now(),
        'root_skill_sha256': root_skill_sha,
        'scanner_version': scanner_version,
        'policy': policy,
        'policy_fingerprint_sha256': policy_fingerprint,
        'review_count': len(reviews),
        'reviews': reviews,
    }


def count_severities(findings):
    counts = {}
    for finding in findings:
        severity = finding['severity']
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def select_pdf_findings(findings, root):
    eligible = []
    by_path = {}
    for finding in findings:
        metadata = finding.get('metadata')
        keywords = metadata.get('detected_keywords') if isinstance(metadata, dict) else None
        if finding.get('rule_id') != PDF_RULE_ID \
                or str(finding.get('severity', '')).upper() != 'HIGH' \
                or keywords != PDF_REQUIRED_KEYWORDS:
            continue
        if finding.get('line_number') is not None:
            fail('PDF_ELIGIBLE_LOCATION',
                 'an eligible PDF finding unexpectedly has a line number')
        raw_path = finding.get('file_path')
        relative = normalize_finding_path(root, raw_path)
        if relative == '.' or not relative.lower().endswith('.pdf'):
            fail('PDF_TARGET_UNSUPPORTED',
                 f'eligible PDF finding does not name a PDF file: {raw_path!r}')
        file_sha = finding_file_hash(root, relative)
        if not file_sha:
            fail('PDF_TARGET_MISSING',
                 f'eligible PDF finding target is missing or unsafe: {relative}')
        previous = by_path.get(relative)
        if previous is not None and previous['file_sha256'] != file_sha:
            fail('PDF_TARGET_DRIFT', f'two different bytes for eligible PDF {relative}')
        entry = {
            'finding_id': finding.get('id') or 'unknown',
            'path': relative,
            'file_sha256': file_sha,
            'line': None,
        }
        eligible.append(entry)
        by_path[relative] = entry
    return eligible, by_path


def pdf_int(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def validate_pdf_facts(facts, policy, expected_sha, config):
    if not isinstance(facts, dict):
        fail('PDF_FACTS_MISMATCH', 'PDF facts are not a JSON object')
    if facts.get('check') != 'GOUJIAN_PDF_STRUCTURAL_CHECK' \
            or facts.get('schema_version') != 1:
        fail('PDF_FACTS_MISMATCH', 'PDF facts check identity is not recognized')
    recorded_policy = facts.get('policy') or {}
    if recorded_policy.get('id') != policy['id'] \
            or recorded_policy.get('sha256') != policy['sha256'] \
            or recorded_policy.get('rule_id') != policy['rule_id'] \
            or recorded_policy.get('severity') != policy['severity'] \
            or recorded_policy.get('metadata_detected_keywords') != policy['keywords']:
        fail('PDF_POLICY_MISMATCH', 'PDF facts were produced under a different policy')
    recorded_checker = facts.get('checker') or {}
    if recorded_checker.get('name') != PDF_CHECKER_REL \
            or recorded_checker.get('sha256') != policy['checker']['sha256'] \
            or recorded_checker.get('version') != policy['checker']['version']:
        fail('PDF_CHECKER_IDENTITY_MISMATCH',
             'PDF facts were produced by a different checker')
    recorded_parser = facts.get('parser') or {}
    if recorded_parser.get('package') != policy['parser']['package'] \
            or recorded_parser.get('version') != policy['parser']['version'] \
            or recorded_parser.get('wheel_sha256') != policy['parser']['wheel_sha256']:
        fail('PDF_PARSER_MISMATCH', 'PDF facts were produced by a different parser pin')
    recorded_pdf = facts.get('pdf') or {}
    if recorded_pdf.get('sha256') != expected_sha:
        fail('PDF_HASH_MISMATCH', 'PDF facts are bound to different file bytes')
    if not pdf_int(recorded_pdf.get('bytes'), 1) \
            or recorded_pdf['bytes'] > policy['semantics']['max_pdf_bytes']:
        fail('PDF_FACTS_MISMATCH', 'PDF facts report an invalid document size')
    limits = facts.get('process_limits') or {}
    if limits.get('bounded') is not True:
        fail('PDF_RESOURCE_LIMITS_MISSING',
             'the checker child did not prove bounded parser resource limits')
    for name, config_key in (('RLIMIT_AS', 'memory_bytes'),
                             ('RLIMIT_CPU', 'cpu_seconds')):
        soft = (limits.get(name) or {}).get('soft')
        if not pdf_int(soft, 1) or soft > config['pdf_review'][config_key]:
            fail('PDF_RESOURCE_LIMITS_MISSING',
                 f'{name} is not bounded by the configured limit')
    if facts.get('status') != 'PASS':
        return False
    if facts.get('failures'):
        fail('PDF_FACTS_MISMATCH', 'PDF facts claim PASS while listing failures')
    checks = facts.get('checks')
    if not isinstance(checks, dict):
        fail('PDF_FACTS_MISMATCH', 'PDF facts have no check results')
    names = set(checks)
    if names != PDF_REQUIRED_CHECKS:
        fail('PDF_FACTS_MISMATCH',
             'PDF check set differs: missing {} unknown {}'.format(
                 sorted(PDF_REQUIRED_CHECKS - names), sorted(names - PDF_REQUIRED_CHECKS)))
    for name, entry in checks.items():
        if not isinstance(entry, dict) or entry.get('status') != 'PASS':
            fail('PDF_FACTS_MISMATCH', f'PDF check {name} is not PASS')

    semantics = policy['semantics']
    parsed = facts.get('parsed')
    if not isinstance(parsed, dict):
        fail('PDF_FACTS_MISMATCH', 'PDF facts have no parsed section')
    if parsed.get('strict') is not True \
            or parsed.get('warnings') != [] or parsed.get('warning_records') != []:
        fail('PDF_FACTS_MISMATCH', 'PDF facts did not come from a warning-free strict parse')
    if parsed.get('object_errors') != []:
        fail('PDF_FACTS_MISMATCH', 'PDF facts list object parse errors')
    objects = parsed.get('objects')
    expected_objects = parsed.get('expected_objects')
    xref_objects = parsed.get('xref_objects')
    compressed = parsed.get('compressed_objects')
    free_entries = parsed.get('free_entries')
    generations = parsed.get('xref_generations')
    depth = parsed.get('max_depth_observed')
    pages = parsed.get('pages')
    if not pdf_int(objects, 1) or not pdf_int(expected_objects, 1):
        fail('PDF_FACTS_MISMATCH', 'PDF facts report no object coverage')
    if objects != expected_objects:
        fail('PDF_FACTS_MISMATCH',
             'not every xref/object-stream object was inspected')
    if not pdf_int(xref_objects) or not pdf_int(compressed) \
            or not pdf_int(free_entries) or not pdf_int(generations, 1):
        fail('PDF_FACTS_MISMATCH', 'PDF facts report invalid xref counts')
    if expected_objects != xref_objects + compressed:
        fail('PDF_FACTS_MISMATCH', 'PDF facts xref/object-stream counts are inconsistent')
    if objects > semantics['max_objects']:
        fail('PDF_FACTS_MISMATCH', 'PDF facts exceed the reviewed object limit')
    if not pdf_int(depth) or depth > semantics['max_depth']:
        fail('PDF_FACTS_MISMATCH', 'PDF facts exceed the reviewed depth limit')
    if not pdf_int(pages, 1):
        fail('PDF_FACTS_MISMATCH', 'PDF facts report no positive page count')

    action = facts.get('open_action')
    if not isinstance(action, dict) \
            or action.get('direct_array') is not True \
            or action.get('value_type') != 'array' \
            or action.get('length') != 5 \
            or action.get('sha_shape') != PDF_OPEN_ACTION_SHAPE:
        fail('PDF_FACTS_MISMATCH', 'PDF facts do not prove the exact OpenAction shape')
    page = action.get('page')
    if not isinstance(page, dict) or page.get('index') != 0 \
            or page.get('type') != 'indirect' or page.get('local_page') is not True \
            or page.get('page_type') != '/Page' \
            or not pdf_int(page.get('object')) or not pdf_int(page.get('generation')):
        fail('PDF_FACTS_MISMATCH',
             'PDF facts do not prove a local destination page')
    elements = action.get('elements')
    expected_page = {
        'index': 0, 'type': 'indirect', 'object': page['object'],
        'generation': page['generation'], 'local_page': True, 'page_type': '/Page',
    }
    if not isinstance(elements, list) or len(elements) != 5 \
            or elements[0] != expected_page or elements[1:] != PDF_OPEN_ACTION_SUFFIX:
        fail('PDF_FACTS_MISMATCH',
             'PDF facts do not prove the exact local-page XYZ array')

    dangerous = facts.get('dangerous')
    if not isinstance(dangerous, dict):
        fail('PDF_FACTS_MISMATCH', 'PDF facts have no dangerous section')
    for key in ('action_dictionaries', 'forbidden_keys', 'forbidden_object_values',
                'other_open_actions', 'unsupported_a_contexts', 'invalid_a_values'):
        if dangerous.get(key) != []:
            fail('PDF_FACTS_MISMATCH', f'PDF facts list dangerous {key}')
    proof = facts.get('proof')
    if not isinstance(proof, dict):
        fail('PDF_FACTS_MISMATCH', 'PDF facts have no structural proof')
    safe = proof.get('safe_view')
    danger = proof.get('dangerous_view')
    if not isinstance(safe, dict) or not isinstance(danger, dict):
        fail('PDF_FACTS_MISMATCH', 'PDF structural proof sections are missing')
    if safe.get('catalog_object') != 'trailer /Root' \
            or safe.get('open_action_owner') != 'catalog' \
            or safe.get('page_count') != pages \
            or safe.get('destination_page') != page \
            or safe.get('action_dictionaries') != 0:
        fail('PDF_FACTS_MISMATCH', 'PDF safe-view proof contradicts the parsed facts')
    for key in ('action_dictionary_count', 'forbidden_key_count',
                'forbidden_object_value_count', 'other_open_action_count',
                'unsupported_a_context_count', 'invalid_a_value_count'):
        if danger.get(key) != 0:
            fail('PDF_FACTS_MISMATCH', f'PDF dangerous-view {key} is not zero')
    if danger.get('objects_checked') != objects \
            or danger.get('xref_objects_checked') != xref_objects \
            or danger.get('compressed_objects_checked') != compressed \
            or danger.get('free_entries_skipped') != free_entries:
        fail('PDF_FACTS_MISMATCH', 'PDF dangerous-view proof contradicts object coverage')
    return True


def run_pdf_checker(pdf_path, expected_sha, policy, config, evidence_dir, work_root, label):
    facts_path = Path(evidence_dir) / f'{label}.json'
    stdout_path = Path(evidence_dir) / f'{label}.stdout.log'
    stderr_path = Path(evidence_dir) / f'{label}.stderr.log'
    command = [
        sys.executable, str(ROOT / PDF_CHECKER_REL),
        '--pdf', str(pdf_path),
        '--expected-sha256', expected_sha,
        '--policy', policy['path'],
        '--out', str(facts_path),
    ]
    env = scanner_environment(config, Path(work_root) / f'pdf-env-{label}')
    status, stdout, stderr, outcome = run_bounded(
        command, Path(work_root), env, config['pdf_review']['timeout_seconds'],
        limits={
            'memory_bytes': config['pdf_review']['memory_bytes'],
            'cpu_seconds': config['pdf_review']['cpu_seconds'],
        })
    write_bytes(stdout_path, stdout or b'')
    write_bytes(stderr_path, stderr or b'')
    if outcome == 'timeout':
        fail('PDF_REVIEW_TIMEOUT', 'the bounded PDF checker exceeded its timeout')
    if outcome != 'completed':
        fail('PDF_CHECKER_FAILED',
             f'the PDF checker did not complete: outcome {outcome!r}')
    facts = None
    if facts_path.is_file() and not facts_path.is_symlink():
        facts = read_json(facts_path, 'MALFORMED_PDF_FACTS')
    if facts is None:
        fail('PDF_FACTS_MISSING', 'the PDF checker did not produce a facts file')
    facts_ok = validate_pdf_facts(facts, policy, expected_sha, config)
    if status != 0 and facts_ok:
        fail('PDF_CHECKER_FAILED',
             'the PDF checker exited nonzero while its facts claimed PASS')
    return {
        'status': status,
        'outcome': outcome,
        'facts': facts,
        'facts_ok': facts_ok,
        'facts_path': facts_path,
        'stdout_path': stdout_path,
        'stderr_path': stderr_path,
        'command': command,
        'env_keys': sorted(env),
        'stdout_sha256': sha256_bytes(stdout or b''),
        'stderr_sha256': sha256_bytes(stderr or b''),
    }


def run_pdf_structural_review(target, findings, config, policy, evidence_dir, work_root):
    eligible, _ = select_pdf_findings(findings, target)
    report = {
        'status': 'PASS',
        'reason': 'EXPLICIT_ZERO',
        'policy': {
            'path': checkout_relative(policy['path']),
            'sha256': policy['sha256'],
            'id': policy['id'],
            'status': policy['status'],
            'approved_by': policy['approved_by'],
            'approved_at': policy['approved_at'],
        },
        'checker': {
            'path': PDF_CHECKER_REL,
            'sha256': policy['checker']['sha256'],
            'version': policy['checker']['version'],
        },
        'parser': policy['parser'],
        'requirements': {
            'path': policy['parser']['requirements'],
            'sha256': policy['requirements']['sha256'],
            'packages': policy['requirements']['packages'],
            'package': policy['requirements']['package'],
            'version': policy['requirements']['version'],
            'wheel_sha256': policy['requirements']['wheel_sha256'],
        },
        'rule_binding': {
            'rule_id': policy['rule_id'],
            'severity': policy['severity'],
            'metadata_detected_keywords': policy['keywords'],
        },
        'limits': policy['semantics'],
        'provenance': {
            'policy_path': str(policy['path']),
            'checker_path': str(ROOT / PDF_CHECKER_REL),
            'requirements_path': str(policy['requirements']['path']),
            'checkout_root': str(ROOT),
        },
        'eligible': len(eligible),
        'unique_pdfs': 0,
        'adjudicated': 0,
        'blocking': 0,
        'items': [],
        'raw_findings_retained': True,
        'classification': 'SEMANTIC_STRUCTURAL_CLASSIFIER_PLUS_ROOT_POLICY_REVIEW',
    }
    if not eligible:
        return report
    report['reason'] = ('POLICY_PENDING' if policy['status'] != 'APPROVED'
                        else 'PENDING_RUN')
    grouped = {}
    for entry in eligible:
        grouped.setdefault(entry['path'], []).append(entry)
    unique = sorted(grouped)
    report['unique_pdfs'] = len(unique)
    for index, relative in enumerate(unique):
        entries = grouped[relative]
        reference = entries[0]
        pdf_path = Path(target) / PurePosixPath(relative)
        if not pdf_path.is_file() or pdf_path.is_symlink():
            fail('PDF_TARGET_MISSING', f'eligible PDF target is missing: {relative}')
        label = f'pdf-review-{index:02d}'
        try:
            run = run_pdf_checker(pdf_path, reference['file_sha256'], policy, config,
                                  evidence_dir, work_root, label)
        except GateFailure as error:
            report['status'] = 'FAIL'
            report['reason'] = 'FACTS_ERROR'
            for entry in entries:
                report['items'].append({
                    'finding_id': entry['finding_id'],
                    'path': relative,
                    'pdf_sha256': entry['file_sha256'],
                    'decision': 'BLOCKED',
                    'reason': error.code,
                    'detail': error.detail,
                })
            continue
        if run['facts_ok']:
            decision = ('ADJUDICATED_STRUCTURAL_SAFE'
                        if policy['status'] == 'APPROVED'
                        else 'PENDING_INDEPENDENT_REVIEW')
        else:
            decision = 'BLOCKED'
        for entry in entries:
            report['items'].append({
                'finding_id': entry['finding_id'],
                'path': relative,
                'pdf_sha256': entry['file_sha256'],
                'decision': decision,
                'facts': descriptor(run['facts_path']),
                'facts_sha256': sha256_file(run['facts_path']),
                'checker_exit_code': run['status'],
                'checker_outcome': run['outcome'],
                'checker_stdout': descriptor(run['stdout_path']),
                'checker_stderr': descriptor(run['stderr_path']),
                'command': run['command'],
                'env_keys': run['env_keys'],
                'parser': run['facts'].get('parser'),
                'checks': run['facts'].get('checks'),
                'failures': run['facts'].get('failures') or [],
                'open_action': run['facts'].get('open_action'),
                'dangerous': run['facts'].get('dangerous'),
                'proof': run['facts'].get('proof'),
            })
            if decision == 'BLOCKED':
                report['status'] = 'FAIL'
                report['reason'] = 'FACTS_FAILED'
            elif decision == 'ADJUDICATED_STRUCTURAL_SAFE':
                report['adjudicated'] += 1
    if policy['status'] != 'APPROVED' and report['status'] == 'PASS':
        report['status'] = 'PENDING'
    if report['status'] == 'PASS':
        report['reason'] = 'ALL_ELIGIBLE_FINDINGS_ADJUDICATED'
    elif report['status'] == 'PENDING':
        report['reason'] = 'POLICY_PENDING'
    report['blocking'] = report['eligible'] - report['adjudicated']
    return report


def apply_pdf_review(summaries, review):
    by_key = {(item['finding_id'], item['path']): item for item in review['items']}
    adjudicated = 0
    for summary in summaries:
        item = by_key.get((summary.get('finding_id'), summary.get('path')))
        if not item:
            continue
        summary['pdf_structural_review'] = {
            'eligible': True,
            'policy_id': review['policy']['id'],
            'policy_status': review['policy']['status'],
            'checker_sha256': review['checker']['sha256'],
            'facts_sha256': item.get('facts_sha256'),
            'decision': item['decision'],
            'raw_severity_retained': summary['severity'],
        }
        is_adjudicated = item['decision'] == 'ADJUDICATED_STRUCTURAL_SAFE'
        summary['effective_blocking'] = not is_adjudicated
        if is_adjudicated:
            adjudicated += 1
            summary['raw_classification'] = summary['classification']
            summary['classification'] = 'adjudicated-structural-safe'
            summary['owner'] = 'independent-policy-reviewer'
            summary['disposition'] = 'retained-policy-adjudicated'
            summary['review_status'] = 'APPROVED_EXACT_POLICY'
            summary['rationale'] = (
                'Raw HIGH retained. Deterministic structural checker plus the tracked, '
                'independently approved policy proved the exact benign /OpenAction shape '
                'and the absence of executable actions in the full parsed object graph.')
    return adjudicated


PDF_REVIEW_IDENTITY_FIELDS = (
    'status', 'reason', 'eligible', 'unique_pdfs', 'adjudicated', 'blocking',
    'raw_findings_retained', 'classification',
)
PDF_REVIEW_SECTIONS = ('policy', 'checker', 'parser', 'requirements', 'rule_binding', 'limits')


def compare_pdf_reviews(artifact_dir, recomputed_dir, recorded, recomputed):
    if not isinstance(recorded, dict):
        fail('INVALID_RECEIPT', 'receipt has no PDF structural review record')
    if recorded.get('status') != 'PASS':
        fail('PDF_REVIEW_NOT_PASS', 'receipt PDF structural review is not PASS')
    for field in PDF_REVIEW_IDENTITY_FIELDS:
        if recorded.get(field) != recomputed.get(field):
            fail('PDF_REVIEW_MISMATCH', f'recomputed PDF review differs: {field}')
    for section in PDF_REVIEW_SECTIONS:
        if recorded.get(section) != recomputed.get(section):
            fail('PDF_REVIEW_MISMATCH', f'recomputed PDF review differs: {section}')
    recorded_items = recorded.get('items')
    recomputed_items = recomputed.get('items')
    if not isinstance(recorded_items, list) or not isinstance(recomputed_items, list) \
            or len(recorded_items) != len(recomputed_items):
        fail('PDF_REVIEW_MISMATCH', 'PDF review item set changed')
    if recomputed.get('blocking') != 0:
        fail('PDF_REVIEW_MISMATCH', 'recomputed PDF review still has blocking findings')
    for old, new in zip(recorded_items, recomputed_items):
        for field in ('finding_id', 'path', 'pdf_sha256', 'decision', 'facts_sha256'):
            if old.get(field) != new.get(field):
                code = 'PDF_FACTS_MISMATCH' if field in ('pdf_sha256', 'facts_sha256') \
                    else 'PDF_REVIEW_MISMATCH'
                fail(code, f'PDF review item differs in {field}')
        if old.get('failures') != new.get('failures'):
            fail('PDF_FACTS_MISMATCH', 'PDF review item failures changed')
        if old.get('decision') != 'ADJUDICATED_STRUCTURAL_SAFE':
            fail('PDF_REVIEW_NOT_PASS',
                 'receipt lists an eligible finding that was not policy-adjudicated')
        retained_path = check_receipt_artifact(artifact_dir, old.get('facts'),
                                               'retained PDF facts')
        check_receipt_artifact(artifact_dir, old.get('checker_stdout'),
                               'retained PDF checker stdout')
        check_receipt_artifact(artifact_dir, old.get('checker_stderr'),
                               'retained PDF checker stderr')
        if old.get('facts_sha256') != old['facts'].get('sha256') \
                or sha256_file(retained_path) != old.get('facts_sha256'):
            fail('PDF_FACTS_MISMATCH', 'retained PDF facts hash is inconsistent')
        recomputed_path = check_receipt_artifact(recomputed_dir, new.get('facts'),
                                                 'recomputed PDF facts')
        if read_json(retained_path, 'MALFORMED_PDF_FACTS') != \
                read_json(recomputed_path, 'MALFORMED_PDF_FACTS'):
            fail('PDF_FACTS_MISMATCH', 'retained PDF facts differ from recomputed facts')
    if recomputed.get('eligible') != len(recomputed_items):
        fail('PDF_REVIEW_MISMATCH', 'PDF review eligible count does not match its items')


def compare_pdf_summaries(recorded_findings, review):
    summaries = recorded_findings.get('items')
    if not isinstance(summaries, list):
        fail('INVALID_RECEIPT', 'receipt finding items are missing')
    by_key = {(item['finding_id'], item['path']): item for item in review['items']}
    for summary in summaries:
        item = by_key.get((summary.get('finding_id'), summary.get('path')))
        if item is None:
            continue
        evidence = summary.get('pdf_structural_review')
        if not isinstance(evidence, dict):
            fail('PDF_REVIEW_MISMATCH', 'eligible finding lacks its PDF review record')
        if evidence.get('policy_id') != review['policy']['id'] \
                or evidence.get('policy_status') != review['policy']['status'] \
                or evidence.get('checker_sha256') != review['checker']['sha256'] \
                or evidence.get('facts_sha256') != item.get('facts_sha256') \
                or evidence.get('decision') != item.get('decision'):
            fail('PDF_REVIEW_MISMATCH', 'recorded PDF review item identity changed')
        if evidence.get('raw_severity_retained') != summary.get('severity'):
            fail('PDF_REVIEW_MISMATCH', 'recorded raw severity was modified')
        expected_blocking = item['decision'] != 'ADJUDICATED_STRUCTURAL_SAFE'
        if summary.get('effective_blocking') != expected_blocking:
            fail('PDF_REVIEW_MISMATCH', 'recorded effective blocking decision changed')
        if not expected_blocking and summary.get('classification') != \
                'adjudicated-structural-safe':
            fail('PDF_REVIEW_MISMATCH', 'adjudicated finding is not labeled as such')


def scan_command(args):
    out_dir = prepare_output_dir(args.out_dir)
    receipt = {
        'schema_version': RECEIPT_SCHEMA,
        'gate': GATE_NAME,
        'status': 'FAIL',
        'created_at': utc_now(),
        'failure_reasons': [],
        'checks': {},
        'limitations': [
            'JavaScript behavioral dataflow is NOT_RUN by the pinned scanner.',
            'Semantic/LLM analysis is NOT_RUN; no model credentials are used.',
            'Company-platform acceptance is NOT_VERIFIED and is not inferred from this gate.',
            'The scanner environment is a separate tool dependency and is not part of the runtime.',
            'MEDIUM/LOW findings are retained with an owner and triage rationale; they are '
            'not approved and do not waive anything.',
        ],
    }
    work_root = None
    try:
        config_file = Path(args.config)
        config = load_config(config_file)
        lock_path = Path(args.lock) if args.lock else ROOT / config['lock']['path']
        ledger_path = Path(args.review_ledger) if args.review_ledger \
            else ROOT / config['review_ledger']
        lock = load_lock(lock_path, config)
        ledger = load_ledger(ledger_path, config)
        pdf_policy = load_pdf_policy(config_path(config['pdf_review']['policy']), config)
        archive = validate_archive_path(args.archive)
        archive_sha = sha256_file(archive)
        archive_bytes = archive.stat().st_size
        if args.expected_sha256 and archive_sha != args.expected_sha256:
            fail('ARCHIVE_HASH_MISMATCH',
                 f'expected {args.expected_sha256}, found {archive_sha}')
        if not re.match(r'^[0-9a-f]{40}$', str(args.commit)):
            fail('INVALID_COMMIT', 'commit must be a 40-character lowercase SHA')
        if args.profile not in PROFILES:
            fail('INVALID_PROFILE', f'unknown profile: {args.profile}')
        repo = Path(args.repo).resolve()
        worktree = run_git(repo, 'status', '--porcelain').decode(
            'utf-8', errors='replace').strip()
        observed_state = 'clean' if not worktree else 'dirty'
        if args.source_tree_state == 'clean' and observed_state != 'clean':
            fail('SOURCE_TREE_NOT_CLEAN',
                 'the caller declared clean but the Git worktree has tracked or untracked changes')
        receipt.update({
            'archive': {'path': str(archive), 'sha256': archive_sha,
                        'bytes': archive_bytes, 'profile': args.profile,
                        'expected_sha256': args.expected_sha256},
            'package': {'version': args.version, 'commit': args.commit,
                        'source_tree_state': args.source_tree_state,
                        'source_tree_state_observed': observed_state},
            'config': {'path': str(config_file), 'sha256': sha256_file(config_file),
                       'scanner_version': config['scanner']['version'],
                       'policy': config['scanner']['policy'],
                       'policy_fingerprint_sha256':
                           config['scanner']['policy_fingerprint_sha256']},
            'lock': {'path': str(lock_path), **lock},
            'review_ledger': {'path': str(ledger_path), 'sha256': ledger['sha256'],
                              'active_reviews': ledger['count']},
        })
        work_root = Path(tempfile.mkdtemp(prefix='goujian-gate-'))
        snapshot = work_root / 'snapshot.zip'
        snapshot_copy = bounded_copy(archive, snapshot, config['limits'], archive_sha)
        receipt['snapshot'] = {'sha256': snapshot_copy['sha256'],
                               'bytes': snapshot_copy['bytes'],
                               'purpose': 'bounded private opaque copy used for preflight and extraction'}
        preflight = run_preflight(snapshot, args.profile, out_dir, config,
                                  config['limits']['scan_timeout_seconds'])
        if preflight.get('archive_sha256') != archive_sha:
            fail('INPUT_DRIFT', 'preflight observed different archive bytes')
        receipt['preflight'] = preflight
        receipt['checks']['preflight'] = {'status': 'PASS'}
        target = work_root / 'target'
        tree_before = extract_zip(snapshot, target, config['limits'])
        package_json = target / 'package.json'
        if not package_json.is_file():
            fail('PACKAGE_IDENTITY', 'extracted package.json is missing')
        package = read_json(package_json, 'PACKAGE_IDENTITY')
        if package.get('version') != args.version:
            fail('VERSION_MISMATCH',
                 f'archive version {package.get("version")!r} != {args.version!r}')
        skill_path = target / 'SKILL.md'
        root_skill_sha = sha256_file(skill_path)
        receipt['package'].update({
            'name': package.get('name'),
            'root_skill_sha256': root_skill_sha,
        })
        receipt['tree'] = {'files_before': tree_before['files'],
                           'sha256_before': tree_before['sha256']}
        receipt['source_identity'] = verify_source_identity(
            target, args.profile, args.commit, repo)
        receipt['checks']['source_identity'] = {'status': 'PASS'}
        scanner = (str(Path(args.scanner).resolve()) if args.scanner else
                   (str(DEFAULT_LOCAL_SCANNER) if DEFAULT_LOCAL_SCANNER.is_file() else None))
        if not scanner:
            fail('SCANNER_UNAVAILABLE',
                 'pass --scanner or install the pinned scanner under .venv-security')
        run = run_scanner(scanner, target, out_dir, config,
                          args.scanner_timeout or config['limits']['scan_timeout_seconds'])
        receipt['scanner'] = {
            'path': str(scanner),
            'version': run['version'],
            'binary_sha256': run['binary_sha256'],
            'policy': config['scanner']['policy'],
            'policy_fingerprint_sha256': config['scanner']['policy_fingerprint_sha256'],
            'fail_on_severity': config['scanner']['fail_on_severity'],
            'argv': run['command'],
            'env_keys': run['env_keys'],
            'status': run['status'],
            'exit_code': run['exit_code'],
            'stdout_sha256': sha256_bytes(run['stdout']),
            'stderr_sha256': sha256_bytes(run['stderr']),
        }
        if run['status'] == 'timeout':
            fail('SCANNER_TIMEOUT', 'scanner exceeded its timeout and was terminated')
        if run['status'] != 'completed':
            fail('SCANNER_TOOL_ERROR', 'scanner did not complete')
        if not Path(run['json_path']).is_file() or not Path(run['sarif_path']).is_file():
            fail('MISSING_REPORT', 'scanner did not write both JSON and SARIF reports')
        if Path(run['json_path']).is_symlink() or Path(run['sarif_path']).is_symlink():
            fail('UNSAFE_ARTIFACT', 'scanner wrote a symlinked report')
        json_raw = Path(run['json_path']).read_bytes()
        sarif_raw = Path(run['sarif_path']).read_bytes()
        try:
            raw_report = json.loads(json_raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            fail('MALFORMED_REPORT', 'scanner JSON report is not valid JSON')
        validated = validate_scanner_report(raw_report, config)
        try:
            sarif = json.loads(sarif_raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            fail('MALFORMED_SARIF', 'scanner SARIF report is not valid JSON')
        validate_sarif(sarif, len(validated['findings']))
        if run['exit_code'] not in (0, 1):
            fail('SCANNER_TOOL_ERROR',
                 f'scanner exited {run["exit_code"]}; only 0/1 are finding outcomes')
        receipt['reports'] = {
            'json': descriptor(run['json_path']),
            'sarif': descriptor(run['sarif_path']),
            'stdout': {'file': 'scanner.stdout.log',
                       'sha256': sha256_bytes(run['stdout']),
                       'bytes': len(run['stdout'])},
            'stderr': {'file': 'scanner.stderr.log',
                       'sha256': sha256_bytes(run['stderr']),
                       'bytes': len(run['stderr'])},
        }
        summaries, blocking, matched, review_scope = evaluate_findings(
            validated['findings'], target, root_skill_sha, config, ledger)
        receipt['checks']['pdf_structural_review'] = {
            'status': 'FAIL', 'reason': 'NOT_COMPLETED'}
        pdf_review = run_pdf_structural_review(
            target, validated['findings'], config, pdf_policy, out_dir, work_root)
        adjudicated = apply_pdf_review(summaries, pdf_review)
        effective_blocking = max(0, len(blocking) - adjudicated)
        receipt['pdf_structural_review'] = pdf_review
        receipt['checks']['pdf_structural_review'] = {
            'status': 'PASS' if pdf_review['status'] == 'PASS' else 'FAIL',
            'reason': pdf_review['reason'],
            'eligible': pdf_review['eligible'],
            'adjudicated': pdf_review['adjudicated'],
            'blocking': pdf_review['blocking'],
        }
        tree_after = tree_digest(target)
        archive_after = sha256_file(archive)
        snapshot_after = sha256_file(snapshot)
        receipt['tree'].update({'files_after': tree_after[1],
                                'sha256_after': tree_after[0]})
        if tree_after != (tree_before['sha256'], tree_before['files']):
            fail('INPUT_DRIFT', 'extracted target tree changed during scanning')
        if archive_after != archive_sha:
            fail('INPUT_DRIFT', 'archive bytes changed during scanning')
        if snapshot_after != archive_sha:
            fail('INPUT_DRIFT', 'private snapshot changed during scanning')
        receipt['analyzers'] = {
            'used': validated['analyzers_used'],
            'failed': validated['analyzers_failed'],
            'required': config['scanner']['required_analyzers'],
            'policy_fingerprint_sha256': validated['policy_fingerprint_sha256'],
            'rule_contract': validated['rule_contract'],
            'cel': validated['cel'],
            'javascript_behavioral': 'NOT_RUN',
            'semantic': 'NOT_RUN',
        }
        proposal = build_proposal(summaries, sha256_bytes(json_raw),
                                  config['scanner']['version'],
                                  config['scanner']['policy'],
                                  validated['policy_fingerprint_sha256'],
                                  root_skill_sha)
        proposal_path = out_dir / 'review-proposal.json'
        write_json(proposal_path, proposal)
        receipt['review_ledger'].update({
            'matched_reviews': len(matched),
            'active_reviews': ledger['count'],
            'applicable_reviews': review_scope['matched'],
            'not_applicable_reviews': review_scope['not_applicable'],
            'proposal': descriptor(proposal_path),
        })
        counts = count_severities(validated['findings'])
        receipt['findings'] = {
            'total': len(summaries),
            'severity_counts': counts,
            'blocking_total': len(blocking),
            'blocking_policy_adjudicated': adjudicated,
            'blocking_unreviewed': effective_blocking,
            'items': summaries,
        }
        receipt['checks'].update({
            'scanner_version': {'status': 'PASS'},
            'scanner_reports': {'status': 'PASS'},
            'analyzer_evidence': {'status': 'PASS'},
            'policy_fingerprint': {'status': 'PASS'},
            'input_stability': {'status': 'PASS'},
            'review_binding': {'status': 'PASS' if not effective_blocking else 'FAIL'},
            'gate_threshold': {'status': 'PASS' if not effective_blocking else 'FAIL'},
            'coverage_disclosure': {'status': 'PASS'},
        })
        if pdf_review['status'] == 'PENDING':
            fail('PDF_POLICY_PENDING',
                 'eligible PDF findings require the independently approved PDF policy')
        if pdf_review['status'] == 'FAIL':
            fail('PDF_STRUCTURAL_REVIEW_FAILED',
                 'the PDF structural checker blocked one or more eligible findings')
        if effective_blocking:
            fail('UNREVIEWED_BLOCKING',
                 f'{effective_blocking} HIGH/CRITICAL finding(s) lack an exact approved review')
        receipt['status'] = 'PASS'
        missing_checks = set(REQUIRED_CHECKS) - set(receipt['checks'])
        if missing_checks:
            fail('INTERNAL_ERROR', 'receipt is missing required checks: '
                 + ', '.join(sorted(missing_checks)))
    except GateFailure as error:
        receipt['status'] = 'FAIL'
        receipt['failure_reasons'].append({'code': error.code, 'detail': error.detail})
        receipt['checks'].setdefault('gate_threshold', {'status': 'FAIL'})
    except Exception as error:  # fail closed, keep a receipt and any raw artifacts
        receipt['status'] = 'FAIL'
        receipt['failure_reasons'].append({
            'code': 'INTERNAL_ERROR',
            'detail': f'{type(error).__name__}: {error}',
        })
    finally:
        if work_root is not None:
            shutil.rmtree(work_root, ignore_errors=True)
    receipt_path = out_dir / 'receipt.json'
    write_json(receipt_path, receipt)
    summary = {
        'status': receipt['status'],
        'gate': GATE_NAME,
        'archive': receipt.get('archive', {}).get('path'),
        'sha256': receipt.get('archive', {}).get('sha256'),
        'profile': receipt.get('archive', {}).get('profile'),
        'severity_counts': receipt.get('findings', {}).get('severity_counts', {}),
        'blocking_unreviewed': receipt.get('findings', {}).get('blocking_unreviewed'),
        'pdf_review': {
            'status': receipt.get('pdf_structural_review', {}).get('status'),
            'reason': receipt.get('pdf_structural_review', {}).get('reason'),
            'eligible': receipt.get('pdf_structural_review', {}).get('eligible'),
            'adjudicated': receipt.get('pdf_structural_review', {}).get('adjudicated'),
            'blocking': receipt.get('pdf_structural_review', {}).get('blocking'),
        },
        'review_receipt': str(receipt_path),
        'review_proposal': str(out_dir / 'review-proposal.json')
        if (out_dir / 'review-proposal.json').is_file() else None,
        'failure_reasons': receipt['failure_reasons'],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if receipt['status'] == 'PASS' else 1


def check_receipt_artifact(artifact_dir, descriptor_value, label):
    if not isinstance(descriptor_value, dict):
        fail('INVALID_RECEIPT', f'{label} descriptor is missing')
    name = descriptor_value.get('file')
    if not isinstance(name, str) or Path(name).name != name or name in ('.', '..'):
        fail('INVALID_RECEIPT', f'{label} artifact path is not a local file name')
    path = Path(artifact_dir) / name
    if not path.is_file() or path.is_symlink():
        fail('MISSING_ARTIFACT', f'{label} artifact is missing: {path}')
    actual = sha256_file(path)
    if actual != descriptor_value.get('sha256'):
        fail('FORGED_OR_CHANGED_ARTIFACT', f'{label} hash does not match the receipt')
    if path.stat().st_size != descriptor_value.get('bytes'):
        fail('FORGED_OR_CHANGED_ARTIFACT', f'{label} size does not match the receipt')
    return path


def verify_command(args):
    receipt_path = Path(args.receipt)
    if not receipt_path.is_file() or receipt_path.is_symlink():
        fail('MISSING_RECEIPT', f'receipt is missing: {receipt_path}')
    receipt = read_json(receipt_path, 'INVALID_RECEIPT')
    if receipt.get('gate') != GATE_NAME or receipt.get('schema_version') != RECEIPT_SCHEMA:
        fail('INVALID_RECEIPT', 'receipt gate/schema is not recognized')
    if receipt.get('status') != 'PASS':
        fail('RECEIPT_NOT_PASS', 'only a PASS receipt can precede a release mutation')
    created = receipt.get('created_at')
    try:
        created_at = datetime.datetime.fromisoformat(str(created).replace('Z', '+00:00'))
    except ValueError:
        fail('INVALID_RECEIPT', 'created_at is not ISO-8601')
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.timezone.utc)
    age_hours = (datetime.datetime.now(datetime.timezone.utc) - created_at).total_seconds() / 3600
    if age_hours > args.max_age_hours:
        fail('STALE_RECEIPT', f'receipt is {age_hours:.1f}h old; limit {args.max_age_hours}h')
    archive = Path(args.archive or receipt.get('archive', {}).get('path'))
    archive = validate_archive_path(archive)
    actual_sha = sha256_file(archive)
    if actual_sha != receipt['archive'].get('sha256'):
        fail('ARCHIVE_HASH_MISMATCH', 'actual archive does not match the receipt')
    if archive.stat().st_size != receipt['archive'].get('bytes'):
        fail('ARCHIVE_HASH_MISMATCH', 'actual archive size does not match the receipt')
    if args.expected_sha256 and actual_sha != args.expected_sha256:
        fail('ARCHIVE_HASH_MISMATCH', 'actual archive does not match the expected SHA256')
    if not re.match(r'^[0-9a-f]{40}$', str(args.commit)):
        fail('INVALID_COMMIT', 'commit must be a 40-character lowercase SHA')
    if receipt.get('package', {}).get('commit') != args.commit:
        fail('COMMIT_MISMATCH', 'receipt commit does not match the expected commit')
    if receipt.get('package', {}).get('version') != args.version:
        fail('VERSION_MISMATCH', 'receipt version does not match the expected version')
    if receipt.get('package', {}).get('source_tree_state') != 'clean':
        fail('SOURCE_TREE_NOT_CLEAN',
             'receipt was produced from a dirty or unknown source tree; it cannot '
             'prove that the archive equals the named commit')
    if receipt.get('package', {}).get('source_tree_state_observed') != 'clean':
        fail('SOURCE_TREE_NOT_CLEAN',
             'the scanning worktree was observed dirty; the receipt is diagnostic only')
    if args.config:
        config_file = Path(args.config)
    else:
        config_file = ROOT / 'security/security-gate.json'
    config = load_config(config_file)
    if sha256_file(config_file) != receipt.get('config', {}).get('sha256'):
        fail('CONFIG_MISMATCH', 'security gate config changed after scanning')
    if receipt['config'].get('scanner_version') != config['scanner']['version'] \
            or receipt['config'].get('policy') != config['scanner']['policy'] \
            or receipt['config'].get('policy_fingerprint_sha256') != \
            config['scanner']['policy_fingerprint_sha256']:
        fail('CONFIG_MISMATCH', 'receipt scanner config does not match the pinned config')
    lock_path = Path(args.lock) if args.lock else ROOT / config['lock']['path']
    lock = load_lock(lock_path, config)
    if lock['sha256'] != receipt.get('lock', {}).get('sha256'):
        fail('LOCK_MISMATCH', 'scanner lock changed after scanning')
    if lock['packages'] != receipt.get('lock', {}).get('packages'):
        fail('LOCK_MISMATCH', 'scanner lock package count changed')
    ledger_path = Path(args.review_ledger) if args.review_ledger \
        else ROOT / config['review_ledger']
    ledger = load_ledger(ledger_path, config)
    if ledger['sha256'] != receipt.get('review_ledger', {}).get('sha256'):
        fail('LEDGER_MISMATCH', 'review ledger changed after scanning')
    pdf_policy = load_pdf_policy(config_path(config['pdf_review']['policy']), config)
    if args.scanner_sha256 and receipt.get('scanner', {}).get('binary_sha256') != args.scanner_sha256:
        fail('SCANNER_IDENTITY_MISMATCH', 'scanner binary hash does not match the receipt')
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else receipt_path.parent
    preflight_path = check_receipt_artifact(artifact_dir, receipt.get('preflight'), 'preflight')
    preflight = read_json(preflight_path, 'INVALID_PREFLIGHT_REPORT')
    if preflight.get('status') != 'PASS':
        fail('PREFLIGHT_FAILED', 'retained preflight report is not PASS')
    if preflight.get('sha256') != actual_sha:
        fail('ARCHIVE_HASH_MISMATCH', 'preflight report is bound to different archive bytes')
    json_path = check_receipt_artifact(artifact_dir, receipt.get('reports', {}).get('json'),
                                       'scanner JSON')
    sarif_path = check_receipt_artifact(artifact_dir, receipt.get('reports', {}).get('sarif'),
                                        'scanner SARIF')
    check_receipt_artifact(artifact_dir, receipt.get('reports', {}).get('stdout'),
                           'scanner stdout')
    check_receipt_artifact(artifact_dir, receipt.get('reports', {}).get('stderr'),
                           'scanner stderr')
    raw_report = read_json(json_path, 'MALFORMED_REPORT')
    raw_sarif = read_json(sarif_path, 'MALFORMED_SARIF')
    validated = validate_scanner_report(raw_report, config)
    validate_sarif(raw_sarif, len(validated['findings']))
    if receipt.get('scanner', {}).get('version') != config['scanner']['version']:
        fail('SCANNER_VERSION_MISMATCH', 'receipt scanner version differs from the pin')
    if receipt.get('scanner', {}).get('policy') != config['scanner']['policy'] \
            or receipt.get('scanner', {}).get('fail_on_severity') != 'high' \
            or receipt.get('scanner', {}).get('policy_fingerprint_sha256') != \
            config['scanner']['policy_fingerprint_sha256']:
        fail('POLICY_MISMATCH', 'receipt scanner policy differs from the pin')
    if receipt.get('scanner', {}).get('status') != 'completed' \
            or receipt.get('scanner', {}).get('exit_code') not in (0, 1):
        fail('SCANNER_TOOL_ERROR', 'receipt does not show a completed finding outcome')
    analyzer_receipt = receipt.get('analyzers')
    if not isinstance(analyzer_receipt, dict):
        fail('INVALID_RECEIPT', 'receipt analyzer evidence is missing')
    if analyzer_receipt.get('used') != validated['analyzers_used'] \
            or analyzer_receipt.get('failed') != validated['analyzers_failed']:
        fail('ANALYZER_MISMATCH', 'receipt analyzer evidence differs from raw JSON')
    if analyzer_receipt.get('rule_contract') != validated['rule_contract'] \
            or analyzer_receipt.get('cel') != validated['cel']:
        fail('ANALYZER_MISMATCH', 'receipt contract/CEL evidence differs from raw JSON')
    work_root = Path(tempfile.mkdtemp(prefix='goujian-verify-'))
    try:
        target = work_root / 'target'
        tree = extract_zip(archive, target, config['limits'])
        if tree['sha256'] != receipt.get('tree', {}).get('sha256_before') \
                or tree['sha256'] != receipt.get('tree', {}).get('sha256_after') \
                or tree['files'] != receipt.get('tree', {}).get('files_before'):
            fail('TREE_MISMATCH', 'archive tree does not match the receipt')
        package = read_json(target / 'package.json', 'PACKAGE_IDENTITY')
        if package.get('version') != args.version:
            fail('VERSION_MISMATCH', 'archive package version does not match')
        root_skill_sha = sha256_file(target / 'SKILL.md')
        if root_skill_sha != receipt.get('package', {}).get('root_skill_sha256'):
            fail('TREE_MISMATCH', 'root SKILL.md hash does not match the receipt')
        profile = receipt.get('archive', {}).get('profile')
        if profile not in PROFILES:
            fail('INVALID_RECEIPT', 'receipt archive profile is not recognized')
        source_identity = verify_source_identity(
            target, profile, args.commit, Path(args.repo))
        recorded_identity = receipt.get('source_identity')
        if not isinstance(recorded_identity, dict):
            fail('INVALID_RECEIPT', 'receipt source identity is missing')
        for field in ('commit', 'profile', 'compared_members', 'mapped_members',
                      'generated_exception', 'member_digest_sha256'):
            if source_identity.get(field) != recorded_identity.get(field):
                fail('SOURCE_MISMATCH',
                     f'recomputed source identity differs from the receipt: {field}')
        summaries, blocking, matched, review_scope = evaluate_findings(
            validated['findings'], target, root_skill_sha, config, ledger)
        pdf_evidence = work_root / 'pdf-review'
        pdf_evidence.mkdir(parents=True, exist_ok=True)
        pdf_review = run_pdf_structural_review(
            target, validated['findings'], config, pdf_policy, pdf_evidence, work_root)
        adjudicated = apply_pdf_review(summaries, pdf_review)
        effective_blocking = max(0, len(blocking) - adjudicated)
        if pdf_review['status'] == 'PENDING':
            fail('PDF_POLICY_PENDING',
                 'eligible PDF findings require the independently approved PDF policy')
        if pdf_review['status'] == 'FAIL':
            fail('PDF_STRUCTURAL_REVIEW_FAILED',
                 'the PDF structural checker blocked one or more eligible findings')
        compare_pdf_reviews(artifact_dir, pdf_evidence,
                            receipt.get('pdf_structural_review'), pdf_review)
        compare_pdf_summaries(receipt.get('findings') or {}, pdf_review)
        counts = count_severities(validated['findings'])
        recorded_findings = receipt.get('findings', {})
        if recorded_findings.get('total') != len(summaries) \
                or recorded_findings.get('severity_counts') != counts:
            fail('FINDINGS_MISMATCH', 'receipt finding summary does not match raw JSON')
        if recorded_findings.get('blocking_total') != len(blocking) \
                or recorded_findings.get('blocking_policy_adjudicated') != adjudicated \
                or recorded_findings.get('blocking_unreviewed') != effective_blocking:
            fail('FINDINGS_MISMATCH', 'receipt blocking summary does not match recomputation')
        if effective_blocking:
            fail('UNREVIEWED_BLOCKING',
                 f'{effective_blocking} HIGH/CRITICAL finding(s) lack an exact approved review')
        recorded_ledger = receipt.get('review_ledger', {})
        if recorded_ledger.get('matched_reviews') != len(matched) \
                or recorded_ledger.get('applicable_reviews') != review_scope['matched'] \
                or recorded_ledger.get('not_applicable_reviews') != review_scope['not_applicable']:
            fail('LEDGER_MISMATCH', 'receipt review scope is inconsistent with the ledger')
        checks = receipt.get('checks')
        if not isinstance(checks, dict):
            fail('INVALID_RECEIPT', 'receipt checks are missing')
        missing_checks = set(REQUIRED_CHECKS) - set(checks)
        unexpected_checks = set(checks) - set(REQUIRED_CHECKS)
        if missing_checks:
            fail('INCOMPLETE_CHECKS', 'receipt is missing required checks: '
                 + ', '.join(sorted(missing_checks)))
        if unexpected_checks:
            fail('INVALID_RECEIPT', 'receipt contains unrecognized checks: '
                 + ', '.join(sorted(unexpected_checks)))
        for name, check in checks.items():
            if not isinstance(check, dict) or check.get('status') != 'PASS':
                fail('CHECK_NOT_PASS', f'receipt check did not pass: {name}')
        if receipt.get('analyzers', {}).get('javascript_behavioral') != 'NOT_RUN' \
                or receipt.get('analyzers', {}).get('semantic') != 'NOT_RUN':
            fail('COVERAGE_CLAIM', 'receipt does not disclose JavaScript/semantic NOT_RUN')
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
    summary = {
        'status': 'PASS',
        'gate': GATE_NAME,
        'archive': str(archive),
        'sha256': actual_sha,
        'commit': args.commit,
        'version': args.version,
        'receipt': str(receipt_path),
        'reviews_matched': len(matched),
        'severity_counts': count_severities(validated['findings']),
        'pdf_review': {
            'status': receipt.get('pdf_structural_review', {}).get('status'),
            'reason': receipt.get('pdf_structural_review', {}).get('reason'),
            'eligible': receipt.get('pdf_structural_review', {}).get('eligible'),
            'adjudicated': receipt.get('pdf_structural_review', {}).get('adjudicated'),
        },
        'semantic': 'NOT_RUN',
        'javascript_behavioral': 'NOT_RUN',
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    scan = sub.add_parser('scan', help='scan and gate an actual ZIP archive')
    scan.add_argument('archive', help='runtime, source or showcase ZIP')
    scan.add_argument('--profile', required=True, choices=('runtime', 'source', 'showcase'))
    scan.add_argument('--version', required=True, help='expected package version')
    scan.add_argument('--commit', required=True, help='expected 40-character commit SHA')
    scan.add_argument('--repo', default=str(ROOT),
                      help='Git repository holding the approved commit (default: project root)')
    scan.add_argument('--source-tree-state', required=True,
                      choices=('clean', 'dirty', 'unknown'),
                      help='worktree state at build time; verify only trusts clean')
    scan.add_argument('--expected-sha256', help='optional expected archive SHA256')
    scan.add_argument('--config', default=str(DEFAULT_CONFIG))
    scan.add_argument('--lock', help='override the pinned scanner lock')
    scan.add_argument('--review-ledger', help='override the trusted review ledger')
    scan.add_argument('--scanner', help='pinned skill-scanner executable')
    scan.add_argument('--scanner-timeout', type=float,
                      help='override the bounded scanner timeout (seconds)')
    scan.add_argument('--out-dir', required=True, help='retained evidence directory')
    verify = sub.add_parser('verify', help='verify a receipt before a release mutation')
    verify.add_argument('receipt')
    verify.add_argument('--archive', help='actual ZIP to bind (default: receipt path)')
    verify.add_argument('--expected-sha256', help='expected archive SHA256')
    verify.add_argument('--version', required=True)
    verify.add_argument('--commit', required=True)
    verify.add_argument('--repo', default=str(ROOT),
                        help='Git repository holding the approved commit (default: project root)')
    verify.add_argument('--config')
    verify.add_argument('--lock')
    verify.add_argument('--review-ledger')
    verify.add_argument('--artifact-dir', help='directory holding receipt artifacts')
    verify.add_argument('--scanner-sha256', help='optional expected scanner binary hash')
    verify.add_argument('--max-age-hours', type=float, default=24.0)
    args = parser.parse_args(argv)
    try:
        if args.command == 'scan':
            return scan_command(args)
        return verify_command(args)
    except GateFailure as error:
        print(json.dumps({'status': 'FAIL', 'code': error.code, 'detail': error.detail},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'code': 'INTERNAL_ERROR',
                          'detail': f'{type(error).__name__}: {error}'},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
