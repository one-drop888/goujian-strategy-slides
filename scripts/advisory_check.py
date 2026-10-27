#!/usr/bin/env python3
"""Live public advisory checks for the release dependency graph.

Queries the public OSV batch API for the hash-locked scanner graph, the
production npm lock graph and the pinned render requirements. The helper also
validates the JSON produced by a live ``npm audit --omit=dev`` run. Only public
package coordinates and public advisory metadata are recorded; no private
content, credentials or model calls are involved.

Any service error, malformed response or known advisory fails the check. The
helper never upgrades, edits or installs a dependency.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / 'security/security-gate.json'
DEFAULT_SCANNER_LOCK = ROOT / 'security/requirements-lock.txt'
DEFAULT_PACKAGE_LOCK = ROOT / 'package-lock.json'
DEFAULT_REQUIREMENTS = ROOT / 'requirements-render.txt'
CHECK_NAME = 'GOUJIAN_PUBLIC_ADVISORY_CHECK'


class AdvisoryFailure(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def fail(code, detail):
    raise AdvisoryFailure(code, detail)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def read_json(path, code='MALFORMED_JSON'):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        fail(code, '{}: {}'.format(path, error))


def load_config(path):
    config = read_json(path, 'INVALID_CONFIG')
    advisory = config.get('advisory')
    if not isinstance(advisory, dict):
        fail('INVALID_CONFIG', 'advisory section is missing')
    endpoint = advisory.get('osv_endpoint')
    if not isinstance(endpoint, str) or not endpoint.startswith('https://'):
        fail('INVALID_CONFIG', 'advisory osv_endpoint must be an HTTPS URL')
    timeout = advisory.get('timeout_seconds')
    if not isinstance(timeout, int) or timeout <= 0:
        fail('INVALID_CONFIG', 'advisory timeout_seconds must be a positive integer')
    return config, endpoint, timeout


def parse_pinned_requirements(path):
    coordinates = []
    text = Path(path).read_text(encoding='utf-8')
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        requirement = line.split(';', 1)[0].strip()
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s;]+)$', requirement)
        if not match:
            fail('UNPINNED_REQUIREMENT', 'requirement is not an exact pin: {}'.format(line[:120]))
        name, version = match.groups()
        coordinates.append({
            'ecosystem': 'PyPI', 'name': name, 'version': version,
            'source': Path(path).name,
        })
    if not coordinates:
        fail('EMPTY_GRAPH', 'no pinned requirements found in {}'.format(path))
    return coordinates


def parse_scanner_lock(path, config):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import scan_skill_package as gate  # shared strict lock parser

    try:
        lock = gate.load_lock(Path(path), config)
    except gate.GateFailure as error:
        fail('INVALID_SCANNER_LOCK', error.detail)
    text = Path(path).read_text(encoding='utf-8')
    coordinates = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s;]+)', line)
        if match:
            name, version = match.groups()
            coordinates.append({
                'ecosystem': 'PyPI', 'name': name, 'version': version,
                'source': 'scanner-lock',
            })
    if len(coordinates) != lock['packages']:
        fail('INVALID_SCANNER_LOCK', 'scanner lock coordinate count changed')
    return coordinates


def parse_pdf_parser_lock(path, config):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import scan_skill_package as gate  # shared strict lock/policy parsers

    expected = ROOT / config['pdf_review']['parser_requirements']
    if Path(path).resolve() != expected.resolve():
        fail('INVALID_PDF_PARSER_LOCK',
             'PDF parser lock is not the single file referenced by the gate config')
    policy_path = ROOT / config['pdf_review']['policy']
    try:
        policy = gate.load_pdf_policy(policy_path, config)
        lock = gate.load_pdf_parser_lock(Path(path), policy)
    except gate.GateFailure as error:
        fail('INVALID_PDF_PARSER_LOCK', error.detail)
    return [{
        'ecosystem': 'PyPI', 'name': lock['package'], 'version': lock['version'],
        'source': 'pdf-parser-lock',
    }]


def parse_package_lock(path):
    data = read_json(path, 'INVALID_PACKAGE_LOCK')
    packages = data.get('packages')
    if not isinstance(packages, dict):
        fail('INVALID_PACKAGE_LOCK', 'package-lock packages section is missing')
    coordinates = []
    for key, entry in packages.items():
        if not key.startswith('node_modules/') or not isinstance(entry, dict):
            continue
        if entry.get('dev') is True or entry.get('optional') is True:
            continue
        if entry.get('link') is True:
            continue
        name = entry.get('name')
        if not name:
            name = key.rsplit('node_modules/', 1)[-1]
        version = entry.get('version')
        if not isinstance(version, str) or not re.match(r'^[0-9][0-9A-Za-z.+-]*$', version):
            fail('INVALID_PACKAGE_LOCK', 'production dependency has no exact version: {}'.format(key))
        coordinates.append({
            'ecosystem': 'npm', 'name': name, 'version': version,
            'source': 'package-lock production',
        })
    if not coordinates:
        fail('EMPTY_GRAPH', 'package-lock has no production dependencies')
    return coordinates


def deduplicate(coordinates):
    seen = {}
    for item in coordinates:
        key = (item['ecosystem'], item['name'], item['version'])
        seen.setdefault(key, item)
    return [seen[key] for key in sorted(seen)]


def query_osv(coordinates, endpoint, timeout, transport=None):
    queries = [{
        'package': {'ecosystem': item['ecosystem'], 'name': item['name']},
        'version': item['version'],
    } for item in coordinates]
    body = json.dumps({'queries': queries}, sort_keys=True).encode('utf-8')
    request = urllib.request.Request(
        endpoint, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    started = utc_now()
    begin = time.monotonic()
    try:
        if transport is not None:
            status, raw = transport(request, timeout)
        else:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        fail('ADVISORY_SERVICE_ERROR',
             'OSV returned HTTP {}: {}'.format(error.code, error.reason))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        fail('ADVISORY_SERVICE_ERROR', 'OSV request failed: {}'.format(error))
    elapsed_ms = int((time.monotonic() - begin) * 1000)
    finished = utc_now()
    if not isinstance(status, int) or status != 200:
        fail('ADVISORY_SERVICE_ERROR', 'OSV returned HTTP {}'.format(status))
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        fail('ADVISORY_MALFORMED_RESPONSE', 'OSV response is not valid JSON')
    results = payload.get('results')
    if not isinstance(results, list) or len(results) != len(queries):
        fail('ADVISORY_MALFORMED_RESPONSE',
             'OSV response does not match the submitted query count')
    findings = []
    for coordinate, result in zip(coordinates, results):
        if not isinstance(result, dict):
            fail('ADVISORY_MALFORMED_RESPONSE', 'OSV result entry is not an object')
        vulns = result.get('vulns') or []
        if not isinstance(vulns, list):
            fail('ADVISORY_MALFORMED_RESPONSE', 'OSV vulns entry is not a list')
        for vuln in vulns:
            if not isinstance(vuln, dict) or not vuln.get('id'):
                fail('ADVISORY_MALFORMED_RESPONSE', 'OSV advisory has no id')
            findings.append({
                'ecosystem': coordinate['ecosystem'],
                'name': coordinate['name'],
                'version': coordinate['version'],
                'advisory_id': vuln.get('id'),
                'aliases': vuln.get('aliases') or [],
                'summary': vuln.get('summary'),
            })
    return {
        'endpoint': endpoint,
        'started_at': started,
        'finished_at': finished,
        'elapsed_ms': elapsed_ms,
        'http_status': status,
        'query_count': len(queries),
        'request_sha256': sha256_bytes(body),
        'response_sha256': sha256_bytes(raw),
        'findings': findings,
    }


def validate_npm_audit(path, exit_code):
    if exit_code not in (0, 1):
        fail('ADVISORY_SERVICE_ERROR',
             'npm audit exited {}; only 0/1 are advisory outcomes'.format(exit_code))
    data = read_json(path, 'ADVISORY_MALFORMED_RESPONSE')
    if data.get('auditReportVersion') not in (2, 3):
        fail('ADVISORY_MALFORMED_RESPONSE', 'npm audit report version is not 2 or 3')
    vulnerabilities = data.get('vulnerabilities')
    if not isinstance(vulnerabilities, dict):
        fail('ADVISORY_MALFORMED_RESPONSE', 'npm audit vulnerabilities section is missing')
    findings = []
    for name, item in sorted(vulnerabilities.items()):
        if not isinstance(item, dict):
            fail('ADVISORY_MALFORMED_RESPONSE', 'npm audit entry is not an object')
        severity = str(item.get('severity') or '').lower()
        if severity not in ('critical', 'high', 'moderate', 'low', 'info'):
            fail('ADVISORY_MALFORMED_RESPONSE',
                 'npm audit entry has an unknown severity: {}'.format(name))
        if severity == 'info':
            continue
        findings.append({
            'name': name,
            'severity': severity,
            'range': item.get('range'),
            'fix_available': item.get('fixAvailable'),
        })
    if exit_code == 0 and findings:
        fail('ADVISORY_MALFORMED_RESPONSE',
             'npm audit reported exit 0 with vulnerabilities present')
    return {
        'report_sha256': sha256_file(path),
        'exit_code': exit_code,
        'metadata_vulnerabilities':
            (data.get('metadata') or {}).get('vulnerabilities') or {},
        'findings': findings,
    }


def run(args, transport=None, npm_audit_data=None):
    started = utc_now()
    config, endpoint, timeout = load_config(args.config)
    pdf_parser_lock = (Path(args.pdf_parser_lock) if getattr(args, 'pdf_parser_lock', None)
                       else ROOT / config['pdf_review']['parser_requirements'])
    coordinates = []
    coordinates.extend(parse_scanner_lock(args.scanner_lock, config))
    coordinates.extend(parse_pdf_parser_lock(pdf_parser_lock, config))
    coordinates.extend(parse_package_lock(args.package_lock))
    coordinates.extend(parse_pinned_requirements(args.requirements))
    coordinates = deduplicate(coordinates)
    if args.max_queries and len(coordinates) > args.max_queries:
        fail('GRAPH_TOO_LARGE',
             '{} coordinates exceed the batch limit {}'.format(len(coordinates), args.max_queries))
    osv = query_osv(coordinates, endpoint, timeout, transport=transport)
    sources = {
        'scanner_lock': {'path': str(args.scanner_lock), 'sha256': sha256_file(args.scanner_lock)},
        'pdf_parser_lock': {'path': str(pdf_parser_lock),
                            'sha256': sha256_file(pdf_parser_lock)},
        'package_lock': {'path': str(args.package_lock), 'sha256': sha256_file(args.package_lock)},
        'requirements': {'path': str(args.requirements), 'sha256': sha256_file(args.requirements)},
    }
    npm_audit = None
    if args.npm_audit_json:
        if npm_audit_data is not None:
            npm_audit = npm_audit_data
        else:
            npm_audit = validate_npm_audit(args.npm_audit_json, args.npm_audit_exit_code)
        sources['npm_audit'] = {
            'path': str(args.npm_audit_json),
            'sha256': sha256_file(args.npm_audit_json),
        }
    findings = osv['findings'] + (npm_audit['findings'] if npm_audit else [])
    report = {
        'schema_version': 1,
        'check': CHECK_NAME,
        'status': 'FAIL' if findings else 'PASS',
        'created_at': utc_now(),
        'started_at': started,
        'coordinates': {
            'total': len(coordinates),
            'ecosystems': sorted({item['ecosystem'] for item in coordinates}),
            'items': coordinates,
        },
        'sources': sources,
        'osv': osv,
        'npm_audit': npm_audit,
        'findings': findings,
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                       encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(DEFAULT_CONFIG))
    parser.add_argument('--scanner-lock', default=str(DEFAULT_SCANNER_LOCK))
    parser.add_argument('--pdf-parser-lock', default=None,
                        help='defaults to the gate config pdf_review.parser_requirements')
    parser.add_argument('--package-lock', default=str(DEFAULT_PACKAGE_LOCK))
    parser.add_argument('--requirements', default=str(DEFAULT_REQUIREMENTS))
    parser.add_argument('--npm-audit-json')
    parser.add_argument('--npm-audit-exit-code', type=int, default=0)
    parser.add_argument('--max-queries', type=int, default=1000)
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except AdvisoryFailure as error:
        print(json.dumps({'status': 'FAIL', 'code': error.code,
                          'detail': error.detail}, ensure_ascii=False, indent=2))
        return 1
    except Exception as error:  # fail closed on unexpected errors
        print(json.dumps({'status': 'FAIL', 'code': 'INTERNAL_ERROR',
                          'detail': '{}: {}'.format(type(error).__name__, error)},
                         ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({
        'status': report['status'],
        'coordinates': report['coordinates']['total'],
        'findings': len(report['findings']),
        'out': args.out,
    }, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
