#!/usr/bin/env python3
"""Real-parser PDF structural review tests.

Run this suite with the SDK Python that has the hash-locked pypdf wheel
installed (``npm run test:pdf`` under the scanner virtualenv). The tests build
inert PDFs as raw bytes, never execute or fetch them, and exercise both the
standalone checker and the shared scan/verify gate.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
PDF_REL = 'out/v1.3-showcase/test/deck.pdf'
PDF_RULE = 'PDF_STRUCTURAL_THREAT'
PDF_KEYWORDS = {'/OpenAction': 1}


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load('goujian_pdf_gate', 'scripts/scan_skill_package.py')
scan_tests = load('goujian_pdf_scan_tests', 'tests/test_scan_skill_package.py')
pdf_fixture = load('goujian_pdf_negative_fixture', 'scripts/pdf_negative_fixture.py')
BASE_POLICY = ROOT / 'security/pdf-structural-policy.json'
CHECKER = ROOT / 'scripts/pdf_structural_check.py'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def classic_pdf(objects, trailer_extra=b''):
    """Build a classic-xref PDF from object bodies; object numbers start at 1."""
    output = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output += f'{number} 0 obj\n'.encode('ascii') + body + b'\nendobj\n'
    xref = len(output)
    output += f'xref\n0 {len(objects) + 1}\n'.encode('ascii')
    output += b'0000000000 65535 f \n'
    for offset in offsets:
        output += f'{offset:010d} 00000 n \n'.encode('ascii')
    output += (f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R'.encode('ascii')
               + trailer_extra + b' >>\nstartxref\n')
    output += f'{xref}\n%%EOF\n'.encode('ascii')
    return bytes(output)


def objstm_pdf(dangerous):
    """Build an xref-stream PDF with one object stored in an /ObjStm."""
    import struct

    output = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
    offsets = {}
    bodies = {
        1: b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
        2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        3: b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
    }
    for number, body in bodies.items():
        offsets[number] = len(output)
        output += f'{number} 0 obj\n'.encode('ascii') + body + b'\nendobj\n'
    embedded = (b'<< /S /JavaScript /JS (x) >>' if dangerous
                else b'<< /Type /XObject >>')
    first = len(b'5 0 ')
    payload = b'5 0 ' + embedded
    offsets[4] = len(output)
    output += (b'4 0 obj\n' +
               f'<< /Type /ObjStm /N 1 /First {first} /Length {len(payload)} >>\n'.encode('ascii') +
               b'stream\n' + payload + b'\nendstream\nendobj\n')
    xref_offset = len(output)

    def entry(kind, field2, field3):
        return bytes([kind]) + struct.pack('>I', field2) + struct.pack('>H', field3)

    entries = [entry(0, 0, 65535)]
    for number in (1, 2, 3, 4):
        entries.append(entry(1, offsets[number], 0))
    entries.append(entry(2, 4, 0))
    entries.append(entry(1, xref_offset, 0))
    data = b''.join(entries)
    output += (b'6 0 obj\n' +
               f'<< /Type /XRef /Size 7 /Root 1 0 R /W [1 4 2] /Index [0 7] '
               f'/Length {len(data)} >>\n'.encode('ascii') +
               b'stream\n' + data + b'\nendstream\nendobj\n')
    output += f'startxref\n{xref_offset}\n%%EOF\n'.encode('ascii')
    return bytes(output)


BENIGN = [
    b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
    b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
]


def benign_pdf():
    return classic_pdf(BENIGN)


def finding(path=PDF_REL, severity='HIGH', keywords=None, finding_id='PDF-TEST-1'):
    return {
        'id': finding_id,
        'rule_id': PDF_RULE,
        'severity': severity,
        'file_path': path,
        'line_number': None,
        'metadata': {'detected_keywords': dict(keywords or PDF_KEYWORDS)},
    }


class PdfTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='goujian-pdf-tests-')
        cls.base = Path(cls.temp.name)
        cls.config = gate.load_config(ROOT / 'security/security-gate.json')
        cls.pending = gate.load_pdf_policy(BASE_POLICY, cls.config)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def out_dir(self, name):
        path = self.base / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def policy_variant(self, name, status=None, **semantics):
        data = json.loads(BASE_POLICY.read_text(encoding='utf-8'))
        if status is not None:
            data['status'] = status
            if status == 'APPROVED':
                data['approval'] = {
                    'required': 'INDEPENDENT_CODEX_REVIEW',
                    'approved_by': 'test-independent-reviewer',
                    'approved_at': '2026-10-27T00:00:00Z',
                    'scope': data['approval']['scope'],
                }
        data['semantics'].update(semantics)
        path = self.out_dir('policies') / name
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        return path

    def run_checker(self, pdf_path, policy=BASE_POLICY, expected_sha=None,
                    interpreter=None, extra=()):
        work = Path(tempfile.mkdtemp(prefix='pdf-checker-', dir=self.base))
        facts_path = work / 'facts.json'
        command = [
            interpreter or sys.executable, str(CHECKER),
            '--pdf', str(pdf_path),
            '--expected-sha256', expected_sha or sha256(pdf_path),
            '--policy', str(policy),
            '--out', str(facts_path),
            *extra,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
        facts = None
        if facts_path.is_file():
            facts = json.loads(facts_path.read_text(encoding='utf-8'))
        return completed, facts

    def assert_blocked(self, completed, facts, *codes):
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIsNotNone(facts)
        self.assertEqual(facts['status'], 'FAIL')
        found = {item['code'] for item in facts['failures']}
        self.assertTrue(set(codes) <= found,
                        'expected {} in {}, stdout={}'.format(codes, found, completed.stdout))


class CheckerTests(PdfTestCase):
    def write_pdf(self, name, data):
        path = self.out_dir('pdfs') / name
        path.write_bytes(data)
        return path

    def test_benign_direct_local_xyz_passes_with_full_graph_facts(self):
        completed, facts = self.run_checker(self.write_pdf('benign.pdf', benign_pdf()))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(facts['status'], 'PASS')
        self.assertEqual(facts['parsed']['objects'], facts['parsed']['expected_objects'])
        self.assertEqual(facts['dangerous']['action_dictionaries'], [])
        self.assertEqual(facts['open_action']['sha_shape'],
                         ['page-indirect-ref', '/XYZ', 'null', 'null', '0'])
        self.assertTrue(facts['open_action']['page']['local_page'])
        self.assertEqual(facts['proof']['dangerous_view']['action_dictionary_count'], 0)

    def test_object_stream_is_fully_inspected_when_safe(self):
        completed, facts = self.run_checker(self.write_pdf('objstm-safe.pdf', objstm_pdf(False)))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(facts['parsed']['compressed_objects'], 1)
        self.assertEqual(facts['parsed']['objects'], facts['parsed']['expected_objects'])

    def test_unreachable_dangerous_object_stream_blocks(self):
        completed, facts = self.run_checker(self.write_pdf('objstm-danger.pdf', objstm_pdf(True)))
        self.assert_blocked(completed, facts, 'ACTION_DICTIONARY')

    def test_catalog_javascript_action_dictionary_blocks(self):
        data = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction 4 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /S /JavaScript /JS (app.alert(1);) >>',
        ])
        completed, facts = self.run_checker(self.write_pdf('js.pdf', data))
        self.assert_blocked(completed, facts, 'ACTION_DICTIONARY', 'OPENACTION_SHAPE')

    def test_indirect_open_action_array_blocks(self):
        data = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction 4 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'[3 0 R /XYZ null null 0]',
        ])
        completed, facts = self.run_checker(self.write_pdf('indirect-array.pdf', data))
        self.assert_blocked(completed, facts, 'OPENACTION_SHAPE')

    def test_wrong_destination_shape_blocks(self):
        for value, name in (
                (b'[3 0 R /Fit]', b'fit'),
                (b'[3 0 R /XYZ null null 1]', b'zoom'),
                (b'[3 0 R /XYZ 0 null 0]', b'left')):
            data = classic_pdf([
                b'<< /Type /Catalog /Pages 2 0 R /OpenAction ' + value + b' >>',
                b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            ])
            completed, facts = self.run_checker(self.write_pdf('shape-' + name.decode() + '.pdf', data))
            self.assert_blocked(completed, facts, 'OPENACTION_SHAPE')

    def test_foreign_or_nonpage_destination_blocks(self):
        data = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [4 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /Type /XObject /Subtype /Form /BBox [0 0 10 10] >>',
        ])
        completed, facts = self.run_checker(self.write_pdf('foreign.pdf', data))
        self.assert_blocked(completed, facts, 'OPENACTION_PAGE')

    def test_remote_launch_uri_and_aa_actions_block(self):
        cases = {
            'gotor': b'<< /S /GoToR /F (other.pdf) /D [0 /Fit] >>',
            'launch': b'<< /S /Launch /F (calc.exe) >>',
            'uri': b'<< /S /URI /URI (https://example.invalid) >>',
        }
        for name, action in cases.items():
            data = classic_pdf([
                b'<< /Type /Catalog /Pages 2 0 R /OpenAction ' + action + b' >>',
                b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            ])
            completed, facts = self.run_checker(self.write_pdf(name + '.pdf', data))
            self.assert_blocked(completed, facts, 'ACTION_DICTIONARY')
        aa = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] '
            b'/AA << /O << /S /JavaScript /JS (x) >> >> >>',
        ])
        completed, facts = self.run_checker(self.write_pdf('aa.pdf', aa))
        self.assert_blocked(completed, facts, 'FORBIDDEN_ACTION_KEY', 'ACTION_DICTIONARY')

    def test_annotation_and_outline_actions_block(self):
        annotation = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Annots [4 0 R] >>',
            b'<< /Type /Annot /Subtype /Link /Rect [0 0 10 10] '
            b'/A << /S /URI /URI (https://example.invalid) >> >>',
        ])
        completed, facts = self.run_checker(self.write_pdf('annotation.pdf', annotation))
        self.assert_blocked(completed, facts, 'ACTION_DICTIONARY')
        outline = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] '
            b'/Outlines 4 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /Type /Outlines /First 5 0 R /Last 5 0 R /Count 1 >>',
            b'<< /Title (x) /Parent 4 0 R /A << /S /JavaScript /JS (x) >> >>',
        ])
        completed, facts = self.run_checker(self.write_pdf('outline.pdf', outline))
        self.assert_blocked(completed, facts, 'ACTION_DICTIONARY')

    def test_name_escaped_javascript_keys_block(self):
        data = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /S /J#61vaScript /J#53 (app.alert(1);) >>',
        ])
        completed, facts = self.run_checker(self.write_pdf('escaped.pdf', data))
        self.assert_blocked(completed, facts, 'ACTION_DICTIONARY', 'FORBIDDEN_ACTION_KEY')

    def test_codex_adversarial_attachment_and_embedded_objects_block(self):
        attachment = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Annots [4 0 R] >>',
            b'<< /Type /Annot /Subtype /FileAttachment /Rect [0 0 10 10] '
            b'/FS << /Type /Filespec /F (inert-external-test.txt) >> >>',
        ])
        completed, facts = self.run_checker(
            self.write_pdf('attachment.pdf', attachment))
        self.assert_blocked(completed, facts, 'FORBIDDEN_ACTION_KEY',
                            'FORBIDDEN_OBJECT_VALUE')
        embedded = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /Type /EmbeddedFile /Length 18 >>\nstream\ninert test payload\nendstream',
        ])
        completed, facts = self.run_checker(
            self.write_pdf('embedded.pdf', embedded))
        self.assert_blocked(completed, facts, 'FORBIDDEN_OBJECT_VALUE')

    def test_codex_spoofed_structure_role_action_blocks(self):
        annotation = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Annots [4 0 R] >>',
            b'<< /Type /Annot /Subtype /Link /Rect [0 0 10 10] /S /P '
            b'/A << /S /GoujianUnknownAction >> >>',
        ])
        completed, facts = self.run_checker(
            self.write_pdf('spoofed-annot.pdf', annotation))
        self.assert_blocked(completed, facts, 'UNSUPPORTED_A_CONTEXT')
        struct = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /Type /StructElem /S /Figure /A << /S /GoujianUnknownAction >> >>',
        ])
        completed, facts = self.run_checker(
            self.write_pdf('spoofed-struct.pdf', struct))
        self.assert_blocked(completed, facts, 'INVALID_A_VALUE')

    def test_legitimate_struct_element_layout_attributes_pass(self):
        data = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /Type /StructElem /S /Figure '
            b'/A << /O /Layout /Placement 0 >> >>',
            b'<< /Type /StructElem /S /Table /A ['
            b'<< /O /Layout /BBox [0 0 10 10] /Placement 1 >> '
            b'<< /O /Table /Scope /Both >>] >>',
        ])
        completed, facts = self.run_checker(
            self.write_pdf('struct-layout.pdf', data))
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(facts['status'], 'PASS')
        self.assertEqual(facts['dangerous']['invalid_a_values'], [])
        self.assertEqual(facts['dangerous']['unsupported_a_contexts'], [])

    def test_bounded_gate_child_proves_its_own_limits(self):
        pdf = self.write_pdf('bounded.pdf', benign_pdf())
        evidence = self.out_dir('bounded-evidence')
        work = self.out_dir('bounded-work')
        result = gate.run_pdf_checker(
            pdf, sha256(pdf), self.pending, self.config, evidence, work, 'bounded')
        limits = result['facts']['process_limits']
        self.assertTrue(limits['bounded'])
        self.assertLessEqual(limits['RLIMIT_AS']['soft'],
                             self.config['pdf_review']['memory_bytes'])
        self.assertLessEqual(limits['RLIMIT_CPU']['soft'],
                             self.config['pdf_review']['cpu_seconds'])
        self.assertGreater(limits['RLIMIT_AS']['soft'], 0)
        self.assertGreater(limits['RLIMIT_CPU']['soft'], 0)
        self.assertTrue(result['facts_ok'])

    def test_encrypted_pdf_blocks(self):
        keys = b'<' + b'00' * 32 + b'>'
        data = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /Filter /Standard /V 1 /R 2 /O ' + keys + b' /U ' + keys + b' /P -4 >>',
        ], trailer_extra=b' /Encrypt 4 0 R /ID [<' + b'00' * 16 + b'> <' + b'00' * 16 + b'>]')
        completed, facts = self.run_checker(self.write_pdf('encrypted.pdf', data))
        self.assert_blocked(completed, facts, 'ENCRYPTED')

    def test_duplicate_keys_and_broken_xref_block(self):
        duplicate = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
        ])
        completed, facts = self.run_checker(self.write_pdf('duplicate.pdf', duplicate))
        self.assert_blocked(completed, facts, 'DUPLICATE_KEY')
        broken = classic_pdf(BENIGN, trailer_extra=b' /Prev 1')
        completed, facts = self.run_checker(self.write_pdf('broken-xref.pdf', broken))
        self.assert_blocked(completed, facts, 'AMBIGUOUS_XREF')
        truncated = benign_pdf()[:120]
        completed, facts = self.run_checker(self.write_pdf('truncated.pdf', truncated))
        self.assert_blocked(completed, facts, 'PARSER_ERROR')

    def test_changed_bytes_and_parser_limits_block(self):
        pdf = self.write_pdf('changed.pdf', benign_pdf())
        completed, facts = self.run_checker(
            pdf, expected_sha='0' * 64)
        self.assert_blocked(completed, facts, 'PDF_HASH_MISMATCH')
        shallow = self.policy_variant('shallow.json', max_depth=2)
        completed, facts = self.run_checker(
            self.write_pdf('shallow.pdf', benign_pdf()), policy=shallow)
        self.assert_blocked(completed, facts, 'DEPTH_LIMIT')
        small = self.policy_variant('small.json', max_objects=1)
        completed, facts = self.run_checker(
            self.write_pdf('small.pdf', benign_pdf()), policy=small)
        self.assert_blocked(completed, facts, 'OBJECT_LIMIT')

    def test_missing_parser_dependency_fails_closed(self):
        work = Path(tempfile.mkdtemp(prefix='pdf-no-site-', dir=self.base))
        facts_path = work / 'facts.json'
        pdf = self.write_pdf('no-parser.pdf', benign_pdf())
        command = [sys.executable, '-S', str(CHECKER), '--pdf', str(pdf),
                   '--expected-sha256', sha256(pdf), '--policy', str(BASE_POLICY),
                   '--out', str(facts_path)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(completed.returncode, 0)
        facts = json.loads(facts_path.read_text(encoding='utf-8'))
        self.assertEqual(facts['status'], 'FAIL')
        self.assertIn('PARSER_UNAVAILABLE',
                      {item['code'] for item in facts['failures']})

    def test_negative_fixture_is_inert_and_blocked(self):
        destination = Path(tempfile.mkdtemp(prefix='pdf-fixture-', dir=self.base)) / 'skill'
        metadata = pdf_fixture.materialize(destination)
        self.assertEqual(metadata['files'], ['SKILL.md', 'pdf-negative-fixture.pdf'])
        self.assertFalse(metadata['executed'])
        self.assertEqual(len(list(destination.rglob('SKILL.md'))), 1)
        pdf = destination / 'pdf-negative-fixture.pdf'
        completed, facts = self.run_checker(pdf)
        self.assert_blocked(completed, facts, 'ACTION_DICTIONARY', 'OPENACTION_SHAPE')


class ReviewPolicyTests(PdfTestCase):
    def review(self, pdf_bytes, policy, findings):
        target = Path(tempfile.mkdtemp(prefix='pdf-target-', dir=self.base))
        pdf_path = target / 'deck.pdf'
        pdf_path.write_bytes(pdf_bytes)
        findings = [dict(item, file_path='deck.pdf') for item in findings]
        evidence = Path(tempfile.mkdtemp(prefix='pdf-evidence-', dir=self.base))
        work = Path(tempfile.mkdtemp(prefix='pdf-work-', dir=self.base))
        report = gate.run_pdf_structural_review(
            target, findings, self.config, policy, evidence, work)
        return report, evidence, work

    def approved_policy(self):
        path = self.policy_variant('approved.json', status='APPROVED')
        return gate.load_pdf_policy(path, self.config)

    def test_pending_policy_blocks_even_when_facts_pass(self):
        report, _, _ = self.review(benign_pdf(), self.pending, [finding()])
        self.assertEqual(report['status'], 'PENDING')
        self.assertEqual(report['reason'], 'POLICY_PENDING')
        self.assertEqual(report['eligible'], 1)
        self.assertEqual(report['adjudicated'], 0)
        self.assertEqual(report['blocking'], 1)
        self.assertEqual(report['items'][0]['decision'], 'PENDING_INDEPENDENT_REVIEW')

    def test_approved_policy_adjudicates_exact_local_xyz_only(self):
        policy = self.approved_policy()
        report, _, _ = self.review(benign_pdf(), policy, [finding()])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['reason'], 'ALL_ELIGIBLE_FINDINGS_ADJUDICATED')
        self.assertEqual(report['adjudicated'], 1)
        self.assertEqual(report['blocking'], 0)
        summaries = [{'finding_id': 'PDF-TEST-1', 'path': 'deck.pdf', 'severity': 'HIGH',
                      'classification': 'blocking-unreviewed'}]
        self.assertEqual(gate.apply_pdf_review(summaries, report), 1)
        self.assertEqual(summaries[0]['severity'], 'HIGH')
        self.assertEqual(summaries[0]['classification'], 'adjudicated-structural-safe')
        self.assertEqual(summaries[0]['pdf_structural_review']['decision'],
                         'ADJUDICATED_STRUCTURAL_SAFE')
        self.assertFalse(summaries[0]['effective_blocking'])

    def test_forged_benign_metadata_cannot_hide_javascript(self):
        policy = self.approved_policy()
        malicious = classic_pdf([
            b'<< /Type /Catalog /Pages 2 0 R /OpenAction 4 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
            b'<< /S /JavaScript /JS (app.alert(1);) >>',
        ])
        report, _, _ = self.review(malicious, policy, [finding()])
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['items'][0]['decision'], 'BLOCKED')
        self.assertIn('ACTION_DICTIONARY',
                      {item['code'] for item in report['items'][0]['failures']})

    def test_forged_metadata_cannot_hide_attachment_or_spoofed_action(self):
        policy = self.approved_policy()
        cases = {
            'attachment': (classic_pdf([
                b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
                b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Annots [4 0 R] >>',
                b'<< /Type /Annot /Subtype /FileAttachment /Rect [0 0 10 10] '
                b'/FS << /Type /Filespec /F (inert.txt) >> >>',
            ]), 'FORBIDDEN_OBJECT_VALUE'),
            'embedded': (classic_pdf([
                b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
                b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
                b'<< /Type /EmbeddedFile /Length 5 >>\nstream\ninert\nendstream',
            ]), 'FORBIDDEN_OBJECT_VALUE'),
            'spoofed': (classic_pdf([
                b'<< /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0] >>',
                b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Annots [4 0 R] >>',
                b'<< /Type /Annot /Subtype /Link /Rect [0 0 10 10] /S /P '
                b'/A << /S /GoujianUnknownAction >> >>',
            ]), 'UNSUPPORTED_A_CONTEXT'),
        }
        for name, (pdf, code) in cases.items():
            report, _, _ = self.review(pdf, policy, [finding()])
            self.assertEqual(report['status'], 'FAIL', name)
            self.assertEqual(report['items'][0]['decision'], 'BLOCKED', name)
            self.assertIn(code, {item['code'] for item in report['items'][0]['failures']},
                          name)

    def test_other_rules_severities_or_keywords_are_not_classified(self):
        policy = self.approved_policy()
        cases = [
            finding(severity='CRITICAL'),
            finding(keywords={'/OpenAction': 1, '/JS': 1}),
            {**finding(), 'rule_id': 'SOME_OTHER_RULE'},
        ]
        for item in cases:
            report, _, _ = self.review(benign_pdf(), policy, [item])
            self.assertEqual(report['eligible'], 0)
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(report['reason'], 'EXPLICIT_ZERO')
            self.assertEqual(report['adjudicated'], 0)

    def test_verify_comparison_detects_fact_and_pdf_drift(self):
        policy = self.approved_policy()
        first, evidence_a, work_a = self.review(benign_pdf(), policy, [finding()])
        second, evidence_b, work_b = self.review(benign_pdf(), policy, [finding()])
        gate.compare_pdf_reviews(evidence_a, evidence_b, first, second)
        facts_name = first['items'][0]['facts']['file']
        tampered = evidence_a / facts_name
        tampered.write_bytes(tampered.read_bytes() + b' ')
        with self.assertRaises(gate.GateFailure) as caught:
            gate.compare_pdf_reviews(evidence_a, evidence_b, first, second)
        self.assertIn(caught.exception.code,
                      {'FORGED_OR_CHANGED_ARTIFACT', 'PDF_FACTS_MISMATCH'})
        changed = benign_pdf().replace(b'200 200', b'201 201')
        third, evidence_c, work_c = self.review(changed, policy, [finding()])
        with self.assertRaises(gate.GateFailure):
            gate.compare_pdf_reviews(evidence_b, evidence_c, second, third)


class GatePdfTests(PdfTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(tempfile.mkdtemp(prefix='goujian-pdf-gate-'))
        cls.archive = cls.root / 'showcase.zip'
        scan_tests.packager.build(cls.archive)
        with zipfile.ZipFile(cls.archive, 'a', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(scan_tests.zip_info(PREFIX + PDF_REL), benign_pdf())
        cls.repo = cls.root / 'repo'
        cls.repo.mkdir()
        with zipfile.ZipFile(cls.archive) as archive:
            for info in archive.infolist():
                relative = info.filename[len(PREFIX):]
                destination = cls.repo / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(info))
        cls.commit = scan_tests.GateTests.init_repo(cls.repo)
        cls.scanner_dir = cls.root / 'scanner'
        cls.scanner_dir.mkdir()
        cls.scanner = cls.scanner_dir / 'skill-scanner'
        cls.scanner.write_text(scan_tests.FAKE_SCANNER, encoding='utf-8')
        os.chmod(cls.scanner, 0o755)
        cls.empty_ledger = cls.root / 'empty-ledger.json'
        scan_tests.GateTests.write_ledger(cls.empty_ledger, [])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)
        super().tearDownClass()

    def config_with_policy(self, name, policy):
        data = json.loads((ROOT / 'security/security-gate.json').read_text(encoding='utf-8'))
        data['pdf_review']['policy'] = str(policy)
        path = self.root / name
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        return path

    def write_mode(self, findings):
        mode = {
            'policy_fingerprint_sha256':
                self.config['scanner']['policy_fingerprint_sha256'],
            'findings': findings,
        }
        (self.scanner_dir / 'mode.json').write_text(json.dumps(mode), encoding='utf-8')

    def run_gate(self, *args):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = gate.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def scan(self, config, findings):
        self.write_mode(findings)
        out = Path(tempfile.mkdtemp(prefix='scan-out-', dir=self.root))
        code, stdout, stderr = self.run_gate(
            'scan', str(self.archive), '--profile', 'showcase',
            '--version', '1.3.1', '--commit', self.commit,
            '--repo', str(self.repo), '--source-tree-state', 'clean',
            '--config', str(config), '--lock', str(ROOT / 'security/requirements-lock.txt'),
            '--review-ledger', str(self.empty_ledger),
            '--scanner', str(self.scanner), '--out-dir', str(out))
        receipt = json.loads((out / 'receipt.json').read_text(encoding='utf-8'))
        return code, receipt, out, stdout, stderr

    def verify(self, receipt, out, config):
        return self.run_gate(
            'verify', str(out / 'receipt.json'), '--archive', str(self.archive),
            '--version', '1.3.1', '--commit', self.commit,
            '--repo', str(self.repo), '--config', str(config),
            '--lock', str(ROOT / 'security/requirements-lock.txt'),
            '--review-ledger', str(self.empty_ledger), '--artifact-dir', str(out))

    def test_approved_policy_scan_and_verify_pass_then_reject_tamper(self):
        approved = gate.load_pdf_policy(
            self.policy_variant('e2e-approved.json', status='APPROVED'), self.config)
        config = self.config_with_policy('e2e-approved-config.json', approved['path'])
        code, receipt, out, stdout, stderr = self.scan(config, [finding()])
        self.assertEqual(code, 0, (stdout, stderr, receipt.get('failure_reasons')))
        self.assertEqual(receipt['status'], 'PASS')
        self.assertEqual(receipt['checks']['pdf_structural_review']['status'], 'PASS')
        self.assertEqual(receipt['pdf_structural_review']['adjudicated'], 1)
        self.assertEqual(receipt['pdf_structural_review']['blocking'], 0)
        self.assertEqual(receipt['findings']['blocking_total'], 1)
        self.assertEqual(receipt['findings']['blocking_policy_adjudicated'], 1)
        self.assertEqual(receipt['findings']['blocking_unreviewed'], 0)
        item = receipt['findings']['items'][0]
        self.assertEqual(item['severity'], 'HIGH')
        self.assertEqual(item['classification'], 'adjudicated-structural-safe')
        code, stdout, stderr = self.verify(receipt, out, config)
        self.assertEqual(code, 0, (stdout, stderr))
        facts = out / receipt['pdf_structural_review']['items'][0]['facts']['file']
        facts.write_bytes(facts.read_bytes() + b' ')
        code, stdout, stderr = self.verify(receipt, out, config)
        self.assertEqual(code, 1)
        self.assertIn('FORGED_OR_CHANGED_ARTIFACT', stderr)

    def test_pending_policy_blocks_the_whole_gate(self):
        config = self.config_with_policy('e2e-pending-config.json', BASE_POLICY)
        code, receipt, out, stdout, stderr = self.scan(config, [finding()])
        self.assertEqual(code, 1)
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertEqual(receipt['checks']['pdf_structural_review']['status'], 'FAIL')
        self.assertIn({'code': 'PDF_POLICY_PENDING'},
                      [{'code': item['code']} for item in receipt['failure_reasons']])
        self.assertEqual(receipt['findings']['severity_counts'], {'HIGH': 1})
        self.assertEqual(receipt['findings']['blocking_unreviewed'], 1)

    def test_no_eligible_findings_is_explicit_zero_not_notrun(self):
        config = self.config_with_policy('e2e-zero-config.json', BASE_POLICY)
        code, receipt, out, stdout, stderr = self.scan(config, [])
        self.assertEqual(code, 0, (stdout, stderr))
        report = receipt['pdf_structural_review']
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['reason'], 'EXPLICIT_ZERO')
        self.assertEqual(report['eligible'], 0)
        self.assertEqual(report['items'], [])
        self.assertEqual(receipt['checks']['pdf_structural_review']['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
