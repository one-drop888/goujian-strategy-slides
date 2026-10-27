#!/usr/bin/env python3
"""Tests for the live public advisory helper.

Network transport is injected; no live OSV or npm service is contacted.
The tests cover coordinate extraction, deduplication, response binding,
fail-closed service errors and npm audit validation.
"""
import argparse
import importlib.util
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'security/security-gate.json'
LOCK = ROOT / 'security/requirements-lock.txt'
PACKAGE_LOCK = ROOT / 'package-lock.json'
REQUIREMENTS = ROOT / 'requirements-render.txt'


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


advisory = load('goujian_advisory_check', 'scripts/advisory_check.py')


def empty_transport(request, timeout):
    body = json.loads(request.data.decode('utf-8'))
    return 200, json.dumps({'results': [{} for _ in body['queries']]}).encode('utf-8')


def vulnerable_transport(request, timeout):
    body = json.loads(request.data.decode('utf-8'))
    results = [{} for _ in body['queries']]
    results[0] = {'vulns': [{'id': 'OSV-TEST-1', 'aliases': ['CVE-TEST-1'],
                             'summary': 'Test advisory'}]}
    return 200, json.dumps({'results': results}).encode('utf-8')


def failing_transport(request, timeout):
    raise urllib.error.HTTPError('https://api.osv.dev/v1/querybatch', 503,
                                 'Service Unavailable', {}, None)


class AdvisoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='goujian-advisory-tests-')
        cls.base = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def args(self, **overrides):
        values = {
            'config': str(CONFIG), 'scanner_lock': str(LOCK),
            'package_lock': str(PACKAGE_LOCK), 'requirements': str(REQUIREMENTS),
            'npm_audit_json': None, 'npm_audit_exit_code': 0,
            'max_queries': 1000, 'out': str(self.base / 'report.json'),
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def write_audit(self, name, payload, exit_code):
        path = self.base / name
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path, exit_code

    def test_scanner_lock_coordinates_match_the_strict_parser(self):
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        coordinates = advisory.parse_scanner_lock(LOCK, config)
        self.assertEqual(len(coordinates), 100)
        names = {item['name'] for item in coordinates}
        self.assertIn('cisco-ai-skill-scanner', names)

    def test_production_npm_and_render_coordinates_are_pinned(self):
        npm = advisory.parse_package_lock(PACKAGE_LOCK)
        names = {(item['name'], item['version']) for item in npm}
        self.assertIn(('ajv', '8.20.0'), names)
        render = advisory.parse_pinned_requirements(REQUIREMENTS)
        self.assertIn(('Pillow', '13.0.0'),
                      {(item['name'], item['version']) for item in render})

    def test_deduplication_keeps_one_coordinate(self):
        rows = [
            {'ecosystem': 'npm', 'name': 'x', 'version': '1.0.0', 'source': 'a'},
            {'ecosystem': 'npm', 'name': 'x', 'version': '1.0.0', 'source': 'b'},
        ]
        self.assertEqual(advisory.deduplicate(rows), [rows[0]])

    def test_clean_osv_response_is_bound_and_passes(self):
        coordinates = advisory.deduplicate(
            advisory.parse_pinned_requirements(REQUIREMENTS))
        result = advisory.query_osv(coordinates, 'https://api.osv.dev/v1/querybatch',
                                    10, transport=empty_transport)
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['query_count'], len(coordinates))
        self.assertRegex(result['request_sha256'], r'^[0-9a-f]{64}$')
        self.assertRegex(result['response_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(result['http_status'], 200)

    def test_advisory_response_blocks(self):
        coordinates = advisory.deduplicate(
            advisory.parse_pinned_requirements(REQUIREMENTS))
        result = advisory.query_osv(coordinates, 'https://api.osv.dev/v1/querybatch',
                                    10, transport=vulnerable_transport)
        self.assertEqual(result['findings'][0]['advisory_id'], 'OSV-TEST-1')
        self.assertEqual(result['findings'][0]['name'], 'Pillow')

    def test_service_error_fails_closed(self):
        coordinates = advisory.deduplicate(
            advisory.parse_pinned_requirements(REQUIREMENTS))
        with self.assertRaises(advisory.AdvisoryFailure) as caught:
            advisory.query_osv(coordinates, 'https://api.osv.dev/v1/querybatch',
                               10, transport=failing_transport)
        self.assertEqual(caught.exception.code, 'ADVISORY_SERVICE_ERROR')

    def test_malformed_and_truncated_responses_fail_closed(self):
        coordinates = advisory.deduplicate(
            advisory.parse_pinned_requirements(REQUIREMENTS))

        def malformed(request, timeout):
            return 200, b'{not json'

        def truncated(request, timeout):
            return 200, json.dumps({'results': []}).encode('utf-8')

        for transport in (malformed, truncated):
            with self.assertRaises(advisory.AdvisoryFailure) as caught:
                advisory.query_osv(coordinates, 'https://api.osv.dev/v1/querybatch',
                                   10, transport=transport)
            self.assertEqual(caught.exception.code, 'ADVISORY_MALFORMED_RESPONSE')

    def test_npm_audit_clean_report_passes(self):
        path, code = self.write_audit('clean-audit.json', {
            'auditReportVersion': 2,
            'vulnerabilities': {},
            'metadata': {'vulnerabilities': {'info': 0, 'low': 0, 'moderate': 0,
                                             'high': 0, 'critical': 0, 'total': 0}},
        }, 0)
        result = advisory.validate_npm_audit(path, code)
        self.assertEqual(result['findings'], [])

    def test_npm_audit_vulnerability_blocks(self):
        path, code = self.write_audit('vulnerable-audit.json', {
            'auditReportVersion': 2,
            'vulnerabilities': {'ajv': {'severity': 'high', 'range': '<1.0.0',
                                        'fixAvailable': False}},
            'metadata': {'vulnerabilities': {'high': 1, 'total': 1}},
        }, 1)
        result = advisory.validate_npm_audit(path, code)
        self.assertEqual(result['findings'][0]['name'], 'ajv')

    def test_inconsistent_or_unknown_npm_audit_fails_closed(self):
        inconsistent, _ = self.write_audit('inconsistent-audit.json', {
            'auditReportVersion': 2,
            'vulnerabilities': {'x': {'severity': 'high'}},
            'metadata': {'vulnerabilities': {'high': 1, 'total': 1}},
        }, 0)
        with self.assertRaises(advisory.AdvisoryFailure) as caught:
            advisory.validate_npm_audit(inconsistent, 0)
        self.assertEqual(caught.exception.code, 'ADVISORY_MALFORMED_RESPONSE')
        unknown, _ = self.write_audit('unknown-audit.json', {
            'auditReportVersion': 2,
            'vulnerabilities': {'x': {'severity': 'urgent'}},
            'metadata': {'vulnerabilities': {}},
        }, 1)
        with self.assertRaises(advisory.AdvisoryFailure):
            advisory.validate_npm_audit(unknown, 1)
        with self.assertRaises(advisory.AdvisoryFailure) as caught:
            advisory.validate_npm_audit(unknown, 2)
        self.assertEqual(caught.exception.code, 'ADVISORY_SERVICE_ERROR')

    def test_run_passes_with_clean_public_data(self):
        report = advisory.run(self.args(), transport=empty_transport)
        self.assertEqual(report['status'], 'PASS')
        self.assertGreater(report['coordinates']['total'], 100)
        self.assertEqual(report['findings'], [])

    def test_run_fails_with_public_advisory(self):
        report = advisory.run(self.args(), transport=vulnerable_transport)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(len(report['findings']), 1)


if __name__ == '__main__':
    unittest.main()
