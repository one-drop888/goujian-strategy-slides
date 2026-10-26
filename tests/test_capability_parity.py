import base64
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import capability_parity as parity  # noqa: E402


def zip_bytes(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            if isinstance(data, str):
                data = data.encode('utf-8')
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return buffer.getvalue()


def xlsx_bytes(timestamp='2026-10-26T10:00:00Z', value='120'):
    return zip_bytes({
        'xl/worksheets/sheet1.xml': (
            '<worksheet><sheetData><row r="1"><c r="A1"><v>' + value + '</v></c></row>'
            '</sheetData></worksheet>'
        ),
        'docProps/core.xml': (
            '<cp:coreProperties><dcterms:created>' + timestamp + '</dcterms:created>'
            '<dcterms:modified>' + timestamp + '</dcterms:modified></cp:coreProperties>'
        ),
    })


def pptx_bytes(timestamp='2026-10-26T10:00:00Z', chart_value='120', slide_text='Revenue',
               media=b'image-a', font='Noto Sans', include_chart=True, raster_replacement=False,
               xlsx_value='120'):
    members = {
        '[Content_Types].xml': '<Types/>',
        'docProps/core.xml': (
            '<cp:coreProperties><dcterms:created>' + timestamp + '</dcterms:created>'
            '<dcterms:modified>' + timestamp + '</dcterms:modified></cp:coreProperties>'
        ),
        'ppt/slides/slide1.xml': (
            '<p:sld><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>'
            + slide_text + '</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
        ),
        'ppt/theme/theme1.xml': '<a:theme><a:latin typeface="' + font + '"/></a:theme>',
        'ppt/media/image1.png': media,
        'ppt/embeddings/Microsoft_Excel_Worksheet1.xlsx': xlsx_bytes(value=xlsx_value),
    }
    if include_chart:
        members['ppt/charts/chart1.xml'] = (
            '<c:chartSpace><c:chart><c:plotArea><c:barChart><c:ser><c:val><c:numRef>'
            '<c:numCache><c:pt><c:v>' + chart_value + '</c:v></c:pt></c:numCache>'
            '</c:numRef></c:val></c:ser></c:barChart></c:plotArea></c:chart></c:chartSpace>'
        )
    if raster_replacement:
        members['ppt/media/chart1.png'] = b'rasterized-chart'
    return members


class PptxParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, members):
        path = self.root / name
        path.write_bytes(zip_bytes(members))
        return path

    def test_timestamp_only_changes_pass(self):
        baseline = self.write('baseline.pptx', pptx_bytes(timestamp='2026-10-26T10:00:00Z'))
        candidate = self.write('candidate.pptx', pptx_bytes(timestamp='2026-10-27T11:11:11Z'))
        result = parity.compare_pptx_files(baseline, candidate)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(result['changed_members'], [])

    def test_changed_chart_data_fails(self):
        baseline = self.write('baseline.pptx', pptx_bytes(chart_value='120'))
        candidate = self.write('candidate.pptx', pptx_bytes(chart_value='121'))
        result = parity.compare_pptx_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('ppt/charts/chart1.xml', result['changed_members'])

    def test_deleted_native_shape_fails(self):
        baseline = self.write('baseline.pptx', pptx_bytes(slide_text='Revenue'))
        candidate = self.write('candidate.pptx', pptx_bytes(slide_text=''))
        result = parity.compare_pptx_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('ppt/slides/slide1.xml', result['changed_members'])

    def test_raster_replacement_fails(self):
        baseline = self.write('baseline.pptx', pptx_bytes())
        candidate = self.write('candidate.pptx', pptx_bytes(include_chart=False, raster_replacement=True))
        result = parity.compare_pptx_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('ppt/charts/chart1.xml', result['missing_members'])
        self.assertIn('ppt/media/chart1.png', result['unexpected_members'])

    def test_changed_media_fails(self):
        baseline = self.write('baseline.pptx', pptx_bytes(media=b'image-a'))
        candidate = self.write('candidate.pptx', pptx_bytes(media=b'image-b'))
        result = parity.compare_pptx_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('ppt/media/image1.png', result['changed_members'])

    def test_font_fallback_fails(self):
        baseline = self.write('baseline.pptx', pptx_bytes(font='Noto Sans CJK SC'))
        candidate = self.write('candidate.pptx', pptx_bytes(font='Fallback Sans'))
        result = parity.compare_pptx_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('ppt/theme/theme1.xml', result['changed_members'])

    def test_embedded_workbook_value_change_fails(self):
        baseline = self.write('baseline.pptx', pptx_bytes(xlsx_value='120'))
        candidate = self.write('candidate.pptx', pptx_bytes(xlsx_value='999'))
        result = parity.compare_pptx_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('ppt/embeddings/Microsoft_Excel_Worksheet1.xlsx', result['changed_members'])
        self.assertTrue(result['workbook_part_differences'])
        self.assertEqual(result['workbook_part_differences'][0]['part'], 'xl/worksheets/sheet1.xml')


class JsonParityTests(unittest.TestCase):
    def test_business_lifecycle_timestamp_keys_are_not_collection_metadata(self):
        for key in ('timestamp', 'created_at', 'modified_at', 'started_at', 'completed_at'):
            left = parity.normalize_value({key: '2026-10-26T10:00:00Z'}, [])
            right = parity.normalize_value({key: '2026-10-27T10:00:00Z'}, [])
            self.assertNotEqual(left, right, key)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.baseline_root = self.root / 'baseline'
        self.candidate_root = self.root / 'candidate'
        self.baseline_root.mkdir()
        self.candidate_root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, root, payload):
        path = root / 'report.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_timestamps_and_output_paths_are_normalized(self):
        baseline = self.write(self.baseline_root, {
            'generated_at': '2026-10-26T10:00:00Z',
            'pptx': str(self.baseline_root / 'deck.pptx'),
            'pptx_sha256': 'a' * 64,
            'values': [1, 2, 3],
            'title': 'Revenue',
        })
        candidate = self.write(self.candidate_root, {
            'generated_at': '2026-10-27T11:11:11Z',
            'pptx': str(self.candidate_root / 'deck.pptx'),
            'pptx_sha256': 'b' * 64,
            'values': [1, 2, 3],
            'title': 'Revenue',
        })
        result = parity.compare_json_files(baseline, candidate,
                                           [str(self.baseline_root), str(self.candidate_root)])
        self.assertEqual(result['status'], 'PASS', result)

    def test_changed_value_fails(self):
        baseline = self.write(self.baseline_root, {'values': [1, 2, 3], 'title': 'Revenue'})
        candidate = self.write(self.candidate_root, {'values': [1, 2, 4], 'title': 'Revenue'})
        result = parity.compare_json_files(baseline, candidate,
                                           [str(self.baseline_root), str(self.candidate_root)])
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['examples'][0]['path'], '/values/2')

    def test_changed_title_fails(self):
        baseline = self.write(self.baseline_root, {'values': [1], 'title': 'Revenue'})
        candidate = self.write(self.candidate_root, {'values': [1], 'title': 'Revenue '})
        result = parity.compare_json_files(baseline, candidate,
                                           [str(self.baseline_root), str(self.candidate_root)])
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['examples'][0]['path'], '/title')


PNG_ONE = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
PNG_TWO = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


def scene_payload(pptx_hash='a' * 64, measurement=parity.TITLE_MEASUREMENT_METHOD,
                  nested_hash='c' * 64, include_scope=True):
    payload = {
        'version': '1.3',
        'pptx_sha256': pptx_hash,
        'content_sha256': pptx_hash,
        'slides': [{'title': {'title': 'Revenue', 'measurement': measurement,
                              'layout_strategy': 'measured-one-line'}}],
        'narrative': {'bindings': [{'evidence_id': 'E1', 'content_sha256': nested_hash}]},
    }
    if include_scope:
        payload['content_sha256_scope'] = parity.SCENE_CONTENT_SCOPE
    return payload


class ScopedNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.baseline_root = self.root / 'baseline'
        self.candidate_root = self.root / 'candidate'
        self.baseline_root.mkdir()
        self.candidate_root.mkdir()
        self.roots = [str(self.baseline_root), str(self.candidate_root)]

    def tearDown(self):
        self.temp.cleanup()

    def compare(self, baseline, candidate, scene=True):
        left = self.baseline_root / 'report.json'
        right = self.candidate_root / 'report.json'
        left.write_text(json.dumps(baseline), encoding='utf-8')
        right.write_text(json.dumps(candidate), encoding='utf-8')
        return parity.compare_json_files(left, right, self.roots, scene=scene)

    def test_scene_root_content_sha256_with_declared_scope_passes(self):
        result = self.compare(scene_payload(pptx_hash='a' * 64),
                              scene_payload(pptx_hash='b' * 64))
        self.assertEqual(result['status'], 'PASS', result)
        self.assertTrue(result['normalized'][0]['applied'])

    def test_scene_content_sha256_without_scope_fails(self):
        result = self.compare(scene_payload(pptx_hash='a' * 64, include_scope=False),
                              scene_payload(pptx_hash='b' * 64, include_scope=False))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('/content_sha256', [item['path'] for item in result['examples']])

    def test_nested_content_sha256_change_fails(self):
        result = self.compare(scene_payload(nested_hash='c' * 64),
                              scene_payload(nested_hash='d' * 64))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('/narrative/bindings/0/content_sha256',
                      [item['path'] for item in result['examples']])

    def test_changed_provenance_sha256_fails(self):
        result = self.compare({'source_sha256': 'a' * 64}, {'source_sha256': 'b' * 64}, scene=False)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['examples'][0]['path'], '/source_sha256')

    def test_changed_business_event_time_fails(self):
        result = self.compare({'event_time': '2026-10-26T10:00:00Z'},
                              {'event_time': '2026-10-27T11:11:11Z'}, scene=False)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['examples'][0]['path'], '/event_time')

    def test_changed_file_url_fails_even_with_roots(self):
        baseline = {'file_url': 'file://' + str(self.baseline_root / 'asset.png')}
        candidate = {'file_url': 'file://' + str(self.candidate_root / 'asset.png')}
        result = self.compare(baseline, candidate, scene=False)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['examples'][0]['path'], '/file_url')

    def report_pptx(self, report, timestamp):
        members = pptx_bytes(timestamp=timestamp)
        part = json.dumps(report, indent=2) + '\n'
        members['docProps/goujian-reasoning.json'] = part
        return zip_bytes(members), part

    def reasoning_scene(self, part, report_sha256=None):
        payload = scene_payload()
        payload['reasoning'] = {
            'status': 'VALIDATED',
            'plan_sha256': 'p' * 64,
            'spec_sha256': 's' * 64,
            'report_sha256': report_sha256 or parity.sha256_bytes(part.encode('utf-8')),
            'embedded_part': 'docProps/goujian-reasoning.json',
        }
        return payload

    def compare_with_reports(self, baseline_report, candidate_report, baseline_scene=None,
                             candidate_scene=None):
        baseline_pptx, baseline_part = self.report_pptx(baseline_report, '2026-10-26T10:00:00Z')
        candidate_pptx, candidate_part = self.report_pptx(candidate_report, '2026-10-27T10:00:00Z')
        baseline_pptx_path = self.baseline_root / 'q4.pptx'
        candidate_pptx_path = self.candidate_root / 'q4.pptx'
        baseline_pptx_path.write_bytes(baseline_pptx)
        candidate_pptx_path.write_bytes(candidate_pptx)
        left = baseline_scene or self.reasoning_scene(baseline_part)
        right = candidate_scene or self.reasoning_scene(candidate_part)
        left_path = self.baseline_root / 'q4.pptx.scene.json'
        right_path = self.candidate_root / 'q4.pptx.scene.json'
        left_path.write_text(json.dumps(left), encoding='utf-8')
        right_path.write_text(json.dumps(right), encoding='utf-8')
        result = parity.compare_json_files(
            left_path, right_path, self.roots, scene=True,
            paired_pptx=(baseline_pptx_path, candidate_pptx_path))
        return result, baseline_part, candidate_part

    def test_bound_reasoning_report_hash_ignored_when_canonical_reports_equal(self):
        baseline_report = {'status': 'VALIDATED', 'generated_at': '2026-10-26T10:00:00Z',
                           'pptx_content_sha256': 'c' * 64, 'plan_sha256': 'p' * 64}
        candidate_report = {'status': 'VALIDATED', 'generated_at': '2026-10-27T11:11:11Z',
                            'pptx_content_sha256': 'd' * 64, 'plan_sha256': 'p' * 64}
        result, _, _ = self.compare_with_reports(baseline_report, candidate_report)
        self.assertEqual(result['status'], 'PASS', result)
        applied = {item['field']: item['applied'] for item in result['normalized']}
        self.assertTrue(applied['/reasoning/report_sha256'])

    def test_reasoning_report_hash_not_ignored_when_embedded_report_differs(self):
        baseline_report = {'status': 'VALIDATED', 'generated_at': '2026-10-26T10:00:00Z',
                           'plan_sha256': 'p' * 64}
        candidate_report = {'status': 'REVIEW_REQUIRED', 'generated_at': '2026-10-27T11:11:11Z',
                            'plan_sha256': 'p' * 64}
        result, _, _ = self.compare_with_reports(baseline_report, candidate_report)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('/reasoning/report_sha256',
                      [item['path'] for item in result['examples']])

    def test_reasoning_report_hash_not_bound_to_embedded_bytes_fails(self):
        report = {'status': 'VALIDATED', 'generated_at': '2026-10-26T10:00:00Z'}
        candidate_report = dict(report, generated_at='2026-10-27T11:11:11Z')
        candidate_part = json.dumps(candidate_report, indent=2) + '\n'
        result, _, _ = self.compare_with_reports(
            report, candidate_report,
            baseline_scene=self.reasoning_scene('not-the-embedded-part'),
            candidate_scene=self.reasoning_scene(candidate_part))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('/reasoning/report_sha256',
                      [item['path'] for item in result['examples']])

    def test_title_measurement_helper_accepts_real_method(self):
        scene = self.baseline_root / 'real.scene.json'
        scene.write_text(json.dumps(scene_payload()), encoding='utf-8')
        result = parity.title_measurement_evidence(scene)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(result['titles_measured'], 1)

    def test_title_measurement_helper_rejects_conservative_approximation(self):
        scene = self.baseline_root / 'fallback.scene.json'
        scene.write_text(json.dumps(scene_payload(measurement='conservative-approximation')),
                         encoding='utf-8')
        result = parity.title_measurement_evidence(scene)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['fallback_measurements'][0]['measurement'],
                         'conservative-approximation')


class SupplementalWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.baseline_root = self.root / 'baseline'
        self.candidate_root = self.root / 'candidate'
        for root in (self.baseline_root, self.candidate_root):
            (root / 'matrix/supplemental/render').mkdir(parents=True)
        self.write_pair()

    def tearDown(self):
        self.temp.cleanup()

    def write_pair(self, chart_value='120', page_bytes=PNG_ONE):
        for root, timestamp in ((self.baseline_root, '2026-10-26T10:00:00Z'),
                                (self.candidate_root, '2026-10-27T10:00:00Z')):
            (root / 'matrix/supplemental/supplemental.pptx').write_bytes(
                zip_bytes(pptx_bytes(timestamp=timestamp, chart_value=chart_value)))
            (root / 'matrix/supplemental/supplemental.pptx.scene.json').write_text(
                json.dumps(scene_payload(pptx_hash=('a' * 64 if root == self.baseline_root else 'b' * 64))),
                encoding='utf-8')
            (root / 'matrix/supplemental/render/slide-1.png').write_bytes(page_bytes)

    def descriptors(self):
        return ({
            'status': 'PASS',
            'spec': {'path': 'matrix/supplemental/supplemental.spec.json', 'sha256': '1' * 64},
            'pptx': {'path': 'matrix/supplemental/supplemental.pptx', 'sha256': '2' * 64},
            'scene': {'path': 'matrix/supplemental/supplemental.pptx.scene.json', 'sha256': '3' * 64},
            'render': {
                'status': 'PASS',
                'pages': [{'path': 'matrix/supplemental/render/slide-1.png', 'sha256': '4' * 64,
                           'page': 1}],
                'pdf': {'path': 'matrix/supplemental/render/deck.pdf', 'sha256': '5' * 64},
            },
        }, {
            'status': 'PASS',
            'spec': {'path': 'matrix/supplemental/supplemental.spec.json', 'sha256': '1' * 64},
            'pptx': {'path': 'matrix/supplemental/supplemental.pptx', 'sha256': '6' * 64},
            'scene': {'path': 'matrix/supplemental/supplemental.pptx.scene.json', 'sha256': '7' * 64},
            'render': {
                'status': 'PASS',
                'pages': [{'path': 'matrix/supplemental/render/slide-1.png', 'sha256': '4' * 64,
                           'page': 1}],
                'pdf': {'path': 'matrix/supplemental/render/deck.pdf', 'sha256': '8' * 64},
            },
        })

    def test_wrapper_hashes_ignored_only_after_underlying_equality(self):
        baseline, candidate = self.descriptors()
        checks = {}
        ok = parity.compare_supplemental_descriptors(
            baseline, candidate, self.baseline_root, self.candidate_root, checks)
        self.assertTrue(ok, checks['matrix.supplemental'])
        self.assertEqual(checks['matrix.supplemental']['underlying']['status'], 'PASS')

    def test_underlying_pptx_change_is_not_masked(self):
        (self.candidate_root / 'matrix/supplemental/supplemental.pptx').write_bytes(
            zip_bytes(pptx_bytes(timestamp='2026-10-27T10:00:00Z', chart_value='999')))
        baseline, candidate = self.descriptors()
        checks = {}
        ok = parity.compare_supplemental_descriptors(
            baseline, candidate, self.baseline_root, self.candidate_root, checks)
        self.assertFalse(ok)
        self.assertEqual(checks['matrix.supplemental']['underlying']['pptx']['status'], 'FAIL')

    def test_underlying_render_page_change_is_not_masked(self):
        (self.candidate_root / 'matrix/supplemental/render/slide-1.png').write_bytes(PNG_TWO)
        baseline, candidate = self.descriptors()
        checks = {}
        ok = parity.compare_supplemental_descriptors(
            baseline, candidate, self.baseline_root, self.candidate_root, checks)
        self.assertFalse(ok)
        self.assertEqual(checks['matrix.supplemental']['underlying']['render_pngs']['status'], 'FAIL')

    def test_other_supplemental_hashes_stay_exact(self):
        baseline, candidate = self.descriptors()
        candidate['spec']['sha256'] = '9' * 64
        checks = {}
        ok = parity.compare_supplemental_descriptors(
            baseline, candidate, self.baseline_root, self.candidate_root, checks)
        self.assertFalse(ok)
        self.assertIn('/spec/sha256',
                      [item['path'] for item in checks['matrix.supplemental']['examples']])


class BaselineArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tree = self.root / 'tree'
        self.tree.mkdir()
        self.zip_path = self.root / 'baseline.zip'
        self.zip_path.write_bytes(zip_bytes({'pkg/a.txt': 'alpha', 'pkg/core/b.js': 'beta'}))
        (self.tree / 'a.txt').write_text('alpha', encoding='utf-8')
        (self.tree / 'core').mkdir()
        (self.tree / 'core/b.js').write_text('beta', encoding='utf-8')
        self.digest = parity.sha256_bytes(self.zip_path.read_bytes())

    def tearDown(self):
        self.temp.cleanup()

    def test_matching_tree_members_pass_when_digest_is_locked(self):
        with mock.patch.object(parity, 'LOCKED_BASELINE_ZIP_SHA256', self.digest):
            result = parity.baseline_archive_evidence(self.zip_path, self.tree)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(result['archive_members'], 2)
        self.assertEqual(result['tree_members_compared'], 2)

    def test_unrelated_zip_digest_alone_cannot_prove_baseline(self):
        result = parity.baseline_archive_evidence(self.zip_path, self.tree)
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(result['locked_zip_verified'])

    def test_changed_tree_member_fails(self):
        (self.tree / 'core/b.js').write_text('changed', encoding='utf-8')
        with mock.patch.object(parity, 'LOCKED_BASELINE_ZIP_SHA256', self.digest):
            result = parity.baseline_archive_evidence(self.zip_path, self.tree)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['changed_members'], ['core/b.js'])

    def test_missing_tree_member_fails(self):
        (self.tree / 'a.txt').unlink()
        with mock.patch.object(parity, 'LOCKED_BASELINE_ZIP_SHA256', self.digest):
            result = parity.baseline_archive_evidence(self.zip_path, self.tree)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['missing_members'], ['a.txt'])


def matrix_fixture():
    accepted = [f'A-{index}' for index in range(72)]
    rejected = [{'id': f'R-{index}', 'family': 'pie', 'case': f'case-{index}', 'code': f'CODE-{index}'}
                for index in range(24)]
    return {
        'status': 'PASS',
        'fixture_counts': {'cells': 96, 'accepted': 72, 'rejected': 24},
        'native_family_count': 6,
        'families': sorted(parity.EXPECTED_MATRIX['families']),
        'accepted_cell_ids': accepted,
        'rejected_cells': rejected,
        'themes': {
            theme: {'status': 'PASS', 'accepted_cells': 36, 'readback': {'cells': []}}
            for theme in ('light', 'dark')
        },
    }


class MatrixOutcomeTests(unittest.TestCase):
    def test_complete_matrix_outcomes_pass(self):
        checks = {}
        self.assertTrue(parity.matrix_outcome_checks(matrix_fixture(), matrix_fixture(), checks))
        self.assertEqual(checks['matrix.accepted_cell_ids']['status'], 'PASS')

    def test_changed_rejection_code_fails(self):
        candidate = matrix_fixture()
        candidate['rejected_cells'][0]['code'] = 'DIFFERENT-CODE'
        checks = {}
        self.assertFalse(parity.matrix_outcome_checks(matrix_fixture(), candidate, checks))
        self.assertEqual(checks['matrix.rejection_codes']['status'], 'FAIL')

    def test_missing_cell_fails(self):
        candidate = matrix_fixture()
        candidate['accepted_cell_ids'] = candidate['accepted_cell_ids'][:-1]
        candidate['fixture_counts']['accepted'] = 71
        checks = {}
        self.assertFalse(parity.matrix_outcome_checks(matrix_fixture(), candidate, checks))


class PixelParityTests(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow is not installed')
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make_png(self, name, pixel=(255, 0, 0, 255)):
        from PIL import Image
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new('RGBA', (2, 2), (0, 0, 0, 255))
        image.putpixel((0, 0), pixel)
        image.save(path)
        return path

    def test_identical_pixels_pass(self):
        baseline = self.make_png('baseline.png')
        candidate = self.make_png('candidate.png')
        result = parity.compare_png_files(baseline, candidate)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(result['different_pixels'], 0)

    def test_recipe_after_renders_are_checked_and_v12_before_renders_are_excluded(self):
        relative = 'scenarios/business-performance/after/slide-1.png'
        self.make_png('baseline/' + relative)
        self.make_png('candidate/' + relative)
        self.make_png('candidate/scenarios/business-performance/before/slide-1.png')
        self.make_png('candidate/scenarios/business-performance/contact-before-business-performance-1.png')
        result = parity.compare_png_trees(self.root / 'baseline', self.root / 'candidate')
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(result['baseline_pngs'], 1)
        self.make_png('candidate/' + relative, (0, 255, 0, 255))
        result = parity.compare_png_trees(self.root / 'baseline', self.root / 'candidate')
        self.assertEqual(result['status'], 'FAIL', result)
        self.assertEqual(result['changed_count'], 1)

    def test_changed_pixel_fails(self):
        baseline = self.make_png('baseline.png', (255, 0, 0, 255))
        candidate = self.make_png('candidate.png', (0, 255, 0, 255))
        result = parity.compare_png_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['different_pixels'], 1)

    def test_changed_alpha_channel_fails(self):
        baseline = self.make_png('baseline.png', (255, 0, 0, 255))
        candidate = self.make_png('candidate.png', (255, 0, 0, 128))
        result = parity.compare_png_files(baseline, candidate)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['different_pixels'], 1)
        self.assertIn('RGBA', result['pixel_method'])
        self.assertEqual(result['image_modes'], ['RGBA', 'RGBA'])


if __name__ == '__main__':
    unittest.main()
