#!/usr/bin/env python3
"""Compare locked and candidate capability outcomes.

Two fixed contracts are supported. The default preserves V1.3.0 -> V1.3.1;
`--contract CAPABILITY_PARITY_V1_3_1_TO_V1_3_2` selects the frozen V1.3.1
baseline for the V1.3.2 candidate. Versions and locked installer hashes come
only from these fixed entries, never from caller-supplied values.

This verifier consumes independently generated `out/v1.3-showcase` trees. It
does not rebuild showcase artifacts itself: the baseline tree must already be
produced from the immutable baseline tag/installer and the candidate tree from
the candidate checkout under the same environment. It then compares native
PPTX parts, embedded workbook parts, media bytes, rendered PNG pixels, specs,
scenes and QA evidence. Only collection timestamps and declared output-path
metadata are normalized; data, titles, layout, fonts, series and measurement
values are compared exactly.

Automated parity is not visual review and not company-platform approval.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

CAPABILITY_PARITY_V1_3_0_TO_V1_3_1 = 'CAPABILITY_PARITY_V1_3_0_TO_V1_3_1'
CAPABILITY_PARITY_V1_3_1_TO_V1_3_2 = 'CAPABILITY_PARITY_V1_3_1_TO_V1_3_2'
CONTRACTS = {
    CAPABILITY_PARITY_V1_3_0_TO_V1_3_1: {
        'baseline_version': '1.3.0',
        'candidate_version': '1.3.1',
        'baseline_release': 'v1.3.0',
        'locked_baseline_zip_sha256': '7df25c241d74c3bb34fc5569e021320fec675bded72c1e44d439a6f8485ad519',
    },
    CAPABILITY_PARITY_V1_3_1_TO_V1_3_2: {
        'baseline_version': '1.3.1',
        'candidate_version': '1.3.2',
        'baseline_release': 'v1.3.1',
        'locked_baseline_zip_sha256': '7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd',
    },
}
DEFAULT_CONTRACT = CAPABILITY_PARITY_V1_3_0_TO_V1_3_1
BASELINE_VERSION = CONTRACTS[DEFAULT_CONTRACT]['baseline_version']
CANDIDATE_VERSION = CONTRACTS[DEFAULT_CONTRACT]['candidate_version']
LOCKED_BASELINE_ZIP_SHA256 = CONTRACTS[DEFAULT_CONTRACT]['locked_baseline_zip_sha256']
EXPECTED_MATRIX = {
    'cells': 96,
    'accepted': 72,
    'rejected': 24,
    'native_family_count': 6,
    'families': {'bar', 'column', 'line', 'area', 'pie', 'doughnut'},
}
TIMESTAMP_KEYS = {
    'generated_at', 'render_started_at', 'render_completed_at', 'built_at', 'reviewed_at',
}
DERIVED_PPTX_KEYS = {'pptx_sha256', 'pptx_content_sha256'}
SCENE_CONTENT_SCOPE = 'pre_embed_zip_diagnostic_not_recomputable_from_final_pptx'
SUPPLEMENTAL_WRAPPER_HASH_PATHS = (
    ('pptx', 'sha256'),
    ('scene', 'sha256'),
    ('render', 'pdf', 'sha256'),
)
TITLE_MEASUREMENT_METHOD = 'pillow-glyph-advances-with-4pct-safety'
RECIPE_INPUTS = ('business-performance', 'sales-conversion', 'project-analytics')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rel(path, root):
    return Path(path).relative_to(root).as_posix()


def normalize_value(value, roots, key=None):
    """Normalize only named collection timestamps, PPTX-derived wrappers and roots.

    Business event timestamps, provenance hashes, URLs and measurement values are
    deliberately left exact.
    """
    if key in TIMESTAMP_KEYS:
        return '<TIMESTAMP>'
    if key in DERIVED_PPTX_KEYS:
        return '<PPTX-DERIVED>'
    if isinstance(value, dict):
        return {name: normalize_value(item, roots, name) for name, item in value.items()}
    if isinstance(value, list):
        return [normalize_value(item, roots) for item in value]
    if isinstance(value, str):
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*://', value):
            return value
        for root in roots:
            marker = '<ROOT>'
            value = value.replace(str(root), marker)
            value = value.replace(str(Path(root).resolve()), marker)
        return value
    return value


def json_differences(expected, actual, path=''):
    differences = []
    if type(expected) is not type(actual):
        return [(path, repr(expected)[:120], repr(actual)[:120])]
    if isinstance(expected, dict):
        for name in sorted(set(expected) | set(actual)):
            if name not in expected:
                differences.append((path + '/' + name, '<missing>', repr(actual[name])[:120]))
            elif name not in actual:
                differences.append((path + '/' + name, repr(expected[name])[:120], '<missing>'))
            else:
                differences.extend(json_differences(expected[name], actual[name], path + '/' + name))
        return differences
    if isinstance(expected, list):
        if len(expected) != len(actual):
            differences.append((path + '/length', str(len(expected)), str(len(actual))))
        for index, (left, right) in enumerate(zip(expected, actual)):
            differences.extend(json_differences(left, right, f'{path}/{index}'))
        return differences
    if expected != actual:
        differences.append((path, repr(expected)[:120], repr(actual)[:120]))
    return differences


def scoped_scene_root_hash(data):
    """True only for a scene wrapper whose root content hash is declared derived."""
    return (isinstance(data, dict)
            and data.get('content_sha256_scope') == SCENE_CONTENT_SCOPE
            and isinstance(data.get('content_sha256'), str))


def prepare_scene_root(data):
    """Drop only the declared root wrapper hash; nested content hashes stay exact."""
    if not scoped_scene_root_hash(data):
        return data, False
    prepared = dict(data)
    prepared.pop('content_sha256')
    return prepared, True


def reasoning_report_binding(data, pptx_path):
    """Bind scene reasoning.report_sha256 to the raw embedded report part.

    Both sides must hash their own embedded part and the canonical reports must
    match; the hash is only derived because the report carries build metadata.
    """
    reasoning = data.get('reasoning') if isinstance(data, dict) else None
    if not isinstance(reasoning, dict):
        return {'declared': False}
    if reasoning.get('embedded_part') != 'docProps/goujian-reasoning.json':
        return {'declared': False}
    if not isinstance(reasoning.get('report_sha256'), str):
        return {'declared': False}
    if pptx_path is None or not Path(pptx_path).is_file():
        return {'declared': True, 'bound': False, 'reason': 'paired PPTX missing'}
    try:
        with zipfile.ZipFile(pptx_path) as archive:
            part = archive.read('docProps/goujian-reasoning.json')
    except (KeyError, zipfile.BadZipFile, OSError) as error:
        return {'declared': True, 'bound': False, 'reason': f'embedded report unavailable: {error}'}
    bound = sha256_bytes(part) == reasoning['report_sha256']
    return {'declared': True, 'bound': bound,
            'canonical': canonical_reasoning_json(part) if bound else None,
            'reason': None if bound else 'scene report_sha256 does not match embedded report bytes'}


def prepare_scene_report_hash(data, pptx_path):
    """Drop reasoning.report_sha256 only when bound to a canonically equal report."""
    binding = reasoning_report_binding(data, pptx_path)
    if not binding.get('bound'):
        return data, binding, False
    prepared = dict(data)
    prepared['reasoning'] = dict(prepared['reasoning'])
    prepared['reasoning'].pop('report_sha256')
    return prepared, binding, True


def compare_json_files(expected_path, actual_path, roots, limit=12, scene=False, paired_pptx=None):
    if not Path(expected_path).is_file() or not Path(actual_path).is_file():
        return {'status': 'FAIL', 'reason': 'missing JSON artifact',
                'baseline': str(expected_path), 'candidate': str(actual_path)}
    expected_raw = read_json(expected_path)
    actual_raw = read_json(actual_path)
    normalized = []
    if scene:
        left_scoped = scoped_scene_root_hash(expected_raw)
        right_scoped = scoped_scene_root_hash(actual_raw)
        applied = left_scoped and right_scoped
        if applied:
            expected_raw, _ = prepare_scene_root(expected_raw)
            actual_raw, _ = prepare_scene_root(actual_raw)
        normalized.append({
            'field': '/content_sha256',
            'applied': applied,
            'scope': SCENE_CONTENT_SCOPE,
            'rule': 'root scene wrapper hash only, with declared scope',
        })
        if paired_pptx is not None:
            left_report, left_binding, left_report_applied = prepare_scene_report_hash(
                expected_raw, paired_pptx[0])
            right_report, right_binding, right_report_applied = prepare_scene_report_hash(
                actual_raw, paired_pptx[1])
            report_applied = (left_report_applied and right_report_applied
                              and left_binding.get('canonical') == right_binding.get('canonical'))
            if left_binding.get('declared') or right_binding.get('declared'):
                if report_applied:
                    expected_raw = left_report
                    actual_raw = right_report
                normalized.append({
                    'field': '/reasoning/report_sha256',
                    'applied': report_applied,
                    'rule': ('ignored only when both scenes declare the embedded reasoning part, each hash '
                             'matches its own raw embedded part, and the canonical reports are equal'),
                    'baseline_bound': left_binding.get('bound'),
                    'candidate_bound': right_binding.get('bound'),
                    'reason': left_binding.get('reason') or right_binding.get('reason'),
                })
    expected = normalize_value(expected_raw, roots)
    actual = normalize_value(actual_raw, roots)
    differences = json_differences(expected, actual)
    result = {'status': 'PASS' if not differences else 'FAIL', 'differences': len(differences),
              'examples': [{'path': item[0], 'baseline': item[1], 'candidate': item[2]}
                           for item in differences[:limit]]}
    if normalized:
        result['normalized'] = normalized
    return result


def strip_core_timestamps(data):
    text = data.decode('utf-8', errors='replace')
    text = re.sub(r'<dcterms:created[^>]*>.*?</dcterms:created>', '<dcterms:created/>', text, flags=re.S)
    text = re.sub(r'<dcterms:modified[^>]*>.*?</dcterms:modified>', '<dcterms:modified/>', text, flags=re.S)
    return text.encode('utf-8')


def normalize_staged_asset_paths(data):
    """Replace only the run-scoped temp directory used for generated image staging."""
    return re.sub(rb'/tmp/goujian-assets-[A-Za-z0-9]+/', b'<TEMP-ASSETS>/', data)


def canonical_reasoning_json(data):
    try:
        value = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return data
    if not isinstance(value, dict):
        return data
    value.pop('generated_at', None)
    value.pop('pptx_content_sha256', None)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def canonical_inner_package(data, label):
    """Canonicalize an embedded XLSX by dropping only its creation/modification times."""
    result = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                payload = archive.read(info.filename)
                if info.filename == 'docProps/core.xml':
                    payload = strip_core_timestamps(payload)
                result[info.filename] = sha256_bytes(payload)
    except zipfile.BadZipFile:
        return {label + ':invalid-zip': sha256_bytes(data)}
    return result


def canonical_pptx(path):
    parts = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            data = archive.read(name)
            if name == 'docProps/core.xml':
                parts[name] = sha256_bytes(strip_core_timestamps(data))
            elif name == 'docProps/goujian-reasoning.json':
                parts[name] = sha256_bytes(canonical_reasoning_json(data))
            elif name.endswith('.xml') or name.endswith('.rels'):
                parts[name] = sha256_bytes(normalize_staged_asset_paths(data))
            elif name.startswith('ppt/embeddings/') and name.lower().endswith('.xlsx'):
                parts[name] = canonical_inner_package(data, name)
            else:
                parts[name] = sha256_bytes(data)
    return parts


def categorize_pptx_member(name):
    if re.fullmatch(r'ppt/slides/slide\d+\.xml', name):
        return 'slides'
    if re.fullmatch(r'ppt/charts/chart\d+\.xml', name):
        return 'charts'
    if re.fullmatch(r'ppt/media/[^/]+', name):
        return 'media'
    if name.startswith('ppt/embeddings/') and name.lower().endswith('.xlsx'):
        return 'workbooks'
    if name.startswith('docProps/'):
        return 'document_properties'
    return 'package'


def compare_pptx_files(baseline_path, candidate_path, limit=12):
    if not Path(baseline_path).is_file() or not Path(candidate_path).is_file():
        return {'status': 'FAIL', 'reason': 'missing PPTX artifact',
                'baseline': str(baseline_path), 'candidate': str(candidate_path)}
    baseline = canonical_pptx(baseline_path)
    candidate = canonical_pptx(candidate_path)
    missing = sorted(set(baseline) - set(candidate))
    unexpected = sorted(set(candidate) - set(baseline))
    changed = sorted(name for name in set(baseline) & set(candidate) if baseline[name] != candidate[name])
    counts = {}
    for name in baseline:
        counts[categorize_pptx_member(name)] = counts.get(categorize_pptx_member(name), 0) + 1
    workbook_differences = []
    for name in changed:
        left, right = baseline[name], candidate[name]
        if isinstance(left, dict) and isinstance(right, dict):
            for part in sorted(set(left) | set(right)):
                if left.get(part) != right.get(part):
                    workbook_differences.append({'member': name, 'part': part})
    status = 'PASS' if not (missing or unexpected or changed) else 'FAIL'
    return {
        'status': status,
        'members': len(baseline),
        'categories': counts,
        'missing_members': missing[:limit],
        'unexpected_members': unexpected[:limit],
        'changed_members': changed[:limit],
        'changed_member_count': len(changed),
        'workbook_part_differences': workbook_differences[:limit],
        'normalized': ['docProps/core.xml created/modified timestamps',
                       'run-scoped temporary asset staging directory in XML parts',
                       'docProps/goujian-reasoning.json generated_at and pptx_content_sha256',
                       'embedded XLSX docProps/core.xml created/modified timestamps'],
    }


def compare_png_files(baseline_path, candidate_path):
    if not Path(baseline_path).is_file() or not Path(candidate_path).is_file():
        return {'status': 'FAIL', 'reason': 'missing rendered PNG'}
    baseline_bytes = Path(baseline_path).read_bytes()
    candidate_bytes = Path(candidate_path).read_bytes()
    if baseline_bytes == candidate_bytes:
        return {'status': 'PASS', 'bytes_identical': True, 'different_pixels': 0,
                'pixel_method': 'byte-identical; channel comparison not needed'}
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return {'status': 'FAIL', 'reason': 'Pillow is required for pixel comparison'}
    baseline_image = Image.open(baseline_path)
    candidate_image = Image.open(candidate_path)
    modes = [baseline_image.mode, candidate_image.mode]
    baseline = baseline_image.convert('RGBA')
    candidate = candidate_image.convert('RGBA')
    if baseline.size != candidate.size:
        return {'status': 'FAIL', 'reason': 'render size changed', 'image_modes': modes,
                'baseline_size': baseline.size, 'candidate_size': candidate.size}
    difference = ImageChops.difference(baseline, candidate)
    # RGBA getbbox() ignores RGB differences on fully transparent pixels, so use
    # an explicit union of per-channel masks.
    mask = None
    for band in difference.split():
        band_mask = band.point(lambda value: 255 if value else 0)
        mask = band_mask if mask is None else ImageChops.lighter(mask, band_mask)
    different = mask.histogram()[255]
    if different == 0:
        return {'status': 'PASS', 'bytes_identical': False, 'different_pixels': 0,
                'image_modes': modes, 'pixel_method': 'RGBA channels including alpha'}
    return {'status': 'FAIL', 'bytes_identical': False, 'different_pixels': different,
            'total_pixels': baseline.size[0] * baseline.size[1], 'image_modes': modes,
            'pixel_method': 'RGBA channels including alpha'}


def title_measurement_evidence(scene_path):
    """Require real Pillow title layout evidence from a scene, not a capability flag."""
    try:
        data = read_json(scene_path)
    except (OSError, json.JSONDecodeError) as error:
        return {'status': 'FAIL', 'reason': f'unreadable scene: {error}'}
    slides = data.get('slides') if isinstance(data, dict) else None
    if not isinstance(slides, list):
        return {'status': 'FAIL', 'reason': 'scene has no slides list'}
    methods = []
    fallback = []
    missing = []
    for index, slide in enumerate(slides):
        title = slide.get('title') if isinstance(slide, dict) else None
        method = title.get('measurement') if isinstance(title, dict) else None
        if method is None:
            missing.append(index)
            continue
        methods.append(method)
        if method != TITLE_MEASUREMENT_METHOD:
            fallback.append({'slide': index, 'measurement': method})
    ok = bool(methods) and not missing and not fallback
    return {
        'status': 'PASS' if ok else 'FAIL',
        'slides_checked': len(slides),
        'titles_measured': len(methods),
        'missing_measurement_slides': missing,
        'fallback_measurements': fallback,
        'required_method': TITLE_MEASUREMENT_METHOD,
        'note': 'Pillow availability alone is not proof; every scene title layout must record the real glyph-advance method.',
    }


def walk_relative_files(root, suffix, skip_prefixes=()):
    root = Path(root)
    found = set()
    if not root.is_dir():
        return found
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        relative = rel(path, root)
        if not relative.endswith(suffix):
            continue
        if any(relative.startswith(prefix) for prefix in skip_prefixes):
            continue
        found.add(relative)
    return found


def compare_png_trees(baseline_showcase, candidate_showcase, limit=12):
    def current_render(name):
        return '/before/' not in name and not Path(name).name.startswith('contact-before-')
    baseline = {name for name in walk_relative_files(baseline_showcase, '.png')
                if current_render(name)}
    candidate = {name for name in walk_relative_files(candidate_showcase, '.png')
                 if current_render(name)}
    missing = sorted(baseline - candidate)
    unexpected = sorted(candidate - baseline)
    changed = []
    for name in sorted(baseline & candidate):
        result = compare_png_files(Path(baseline_showcase) / name, Path(candidate_showcase) / name)
        if result['status'] != 'PASS':
            changed.append({'path': name, **result})
    return {
        'status': 'PASS' if not (missing or unexpected or changed) else 'FAIL',
        'baseline_pngs': len(baseline),
        'candidate_pngs': len(candidate),
        'missing': missing[:limit],
        'unexpected': unexpected[:limit],
        'changed': changed[:limit],
        'changed_count': len(changed),
        'method': 'byte-identical, otherwise Pillow RGBA channel equality including alpha',
    }


def compare_scene_measurements(root, checks):
    """Reject any showcase scene whose title layout used a fallback approximation."""
    root = Path(root)
    files = sorted(root.glob('out/v1.3-showcase/**/*.scene.json'))
    failures = []
    slides_checked = 0
    for path in files:
        evidence = title_measurement_evidence(path)
        slides_checked += evidence.get('slides_checked') or 0
        if evidence['status'] != 'PASS':
            failures.append({
                'path': rel(path, root),
                'reason': evidence.get('reason'),
                'missing_measurement_slides': evidence.get('missing_measurement_slides'),
                'fallback_measurements': evidence.get('fallback_measurements'),
            })
    checks['scene_title_measurements'] = {
        'status': 'PASS' if files and not failures else 'FAIL',
        'scene_files_checked': len(files),
        'slides_checked': slides_checked,
        'failures': failures[:8],
        'required_method': TITLE_MEASUREMENT_METHOD,
        'rule': 'Pillow availability alone is insufficient; every scene title layout must record real glyph advances.',
    }
    return bool(files) and not failures


def resolve_artifact(root, relative):
    root = Path(root)
    candidates = [root / relative, root / 'out/v1.3-showcase' / relative]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def compare_artifact_pair(baseline_root, candidate_root, expected, actual, kind, paired_pptx=None):
    baseline_path = resolve_artifact(baseline_root, expected)
    candidate_path = resolve_artifact(candidate_root, actual)
    if baseline_path is None or candidate_path is None:
        return {'status': 'FAIL', 'reason': 'artifact path not found',
                'baseline': expected, 'candidate': actual}
    if kind == 'pptx':
        return compare_pptx_files(baseline_path, candidate_path)
    if kind == 'png':
        return compare_png_files(baseline_path, candidate_path)
    if kind in ('json', 'scene'):
        scene = kind == 'scene' or actual.endswith('.scene.json')
        return compare_json_files(baseline_path, candidate_path,
                                  [baseline_root, candidate_root], scene=scene,
                                  paired_pptx=paired_pptx)
    baseline_bytes = baseline_path.read_bytes()
    candidate_bytes = candidate_path.read_bytes()
    return {'status': 'PASS' if baseline_bytes == candidate_bytes else 'FAIL',
            'bytes_identical': baseline_bytes == candidate_bytes}


def check_required(checks, name, result):
    checks[name] = result
    return result['status'] == 'PASS'


def check_equal(checks, name, baseline, candidate, limit=8):
    if baseline == candidate:
        checks[name] = {'status': 'PASS', 'value': baseline}
        return True
    checks[name] = {'status': 'FAIL', 'baseline': baseline, 'candidate': candidate}
    return False


def strip_supplemental_wrapper_hashes(supplemental):
    """Remove only the three declared artifact-wrapper hashes, leaving all others exact."""
    if not isinstance(supplemental, dict):
        return supplemental
    result = json.loads(json.dumps(supplemental))
    for path in SUPPLEMENTAL_WRAPPER_HASH_PATHS:
        node = result
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict):
            node.pop(path[-1], None)
    return result


def supplemental_wrapper_evidence(baseline, candidate, baseline_root, candidate_root, roots):
    """Prove canonical PPTX, scoped scene and rendered PNG equality before hashes are ignored."""
    evidence = {'status': 'FAIL', 'pptx': None, 'scene': None, 'render_pngs': None}
    ok = True

    def resolved(root, descriptor):
        relative = (descriptor or {}).get('path')
        return resolve_artifact(root, relative) if relative else None

    left_pptx = resolved(baseline_root, baseline.get('pptx'))
    right_pptx = resolved(candidate_root, candidate.get('pptx'))
    if left_pptx and right_pptx:
        result = compare_pptx_files(left_pptx, right_pptx)
        evidence['pptx'] = {'status': result['status'],
                            'members': result.get('members'),
                            'changed_member_count': result.get('changed_member_count')}
        ok &= result['status'] == 'PASS'
    else:
        evidence['pptx'] = {'status': 'FAIL', 'reason': 'missing supplemental PPTX'}
        ok = False

    left_scene = resolved(baseline_root, baseline.get('scene'))
    right_scene = resolved(candidate_root, candidate.get('scene'))
    if left_scene and right_scene:
        result = compare_json_files(left_scene, right_scene, roots, scene=True)
        evidence['scene'] = {'status': result['status'],
                             'differences': result.get('differences'),
                             'normalized': result.get('normalized')}
        ok &= result['status'] == 'PASS'
    else:
        evidence['scene'] = {'status': 'FAIL', 'reason': 'missing supplemental scene'}
        ok = False

    render_pngs = {'status': 'PASS', 'pages': 0, 'montage': None, 'contact_sheets': 0}
    left_pages = ((baseline.get('render') or {}).get('pages') or [])
    right_pages = ((candidate.get('render') or {}).get('pages') or [])
    left_paths = [(page or {}).get('path') for page in left_pages]
    right_paths = [(page or {}).get('path') for page in right_pages]
    if left_paths != right_paths or not left_paths:
        render_pngs.update({'status': 'FAIL', 'reason': 'render page list changed'})
        ok = False
    else:
        for relative in left_paths:
            left_png = resolve_artifact(baseline_root, relative)
            right_png = resolve_artifact(candidate_root, relative)
            if left_png is None or right_png is None:
                render_pngs.update({'status': 'FAIL', 'reason': f'missing render page {relative}'})
                ok = False
                break
            if compare_png_files(left_png, right_png)['status'] != 'PASS':
                render_pngs.update({'status': 'FAIL', 'reason': f'changed render page {relative}'})
                ok = False
                break
        render_pngs['pages'] = len(left_paths)
    montage_path = ((baseline.get('render') or {}).get('montage') or {}).get('path')
    if montage_path:
        left_png = resolve_artifact(baseline_root, montage_path)
        right_png = resolve_artifact(candidate_root, montage_path)
        montage_ok = left_png is not None and right_png is not None and \
            compare_png_files(left_png, right_png)['status'] == 'PASS'
        render_pngs['montage'] = 'PASS' if montage_ok else 'FAIL'
        ok &= montage_ok
    for sheet in baseline.get('contact_sheets') or []:
        relative = (sheet or {}).get('path')
        if not relative:
            continue
        left_png = resolve_artifact(baseline_root, relative)
        right_png = resolve_artifact(candidate_root, relative)
        sheet_ok = left_png is not None and right_png is not None and \
            compare_png_files(left_png, right_png)['status'] == 'PASS'
        render_pngs['contact_sheets'] += 1
        if not sheet_ok:
            render_pngs['status'] = 'FAIL'
            ok = False
    if render_pngs['status'] == 'PASS' and not ok:
        render_pngs['status'] = 'FAIL'
    evidence['render_pngs'] = render_pngs
    evidence['status'] = 'PASS' if ok else 'FAIL'
    return evidence


def compare_supplemental_descriptors(baseline, candidate, baseline_root, candidate_root, checks):
    """Compare the supplemental descriptor, ignoring only proven derived wrapper hashes."""
    roots = [str(baseline_root), str(candidate_root)]
    evidence = supplemental_wrapper_evidence(baseline or {}, candidate or {},
                                             baseline_root, candidate_root, roots)
    left = normalize_value(strip_supplemental_wrapper_hashes(baseline or {}), roots)
    right = normalize_value(strip_supplemental_wrapper_hashes(candidate or {}), roots)
    differences = json_differences(left, right)
    status = 'PASS' if not differences and evidence['status'] == 'PASS' else 'FAIL'
    checks['matrix.supplemental'] = {
        'status': status,
        'differences': len(differences),
        'examples': [{'path': item[0], 'baseline': item[1], 'candidate': item[2]}
                     for item in differences[:8]],
        'ignored_wrapper_hashes': ['/pptx/sha256', '/scene/sha256', '/render/pdf/sha256'],
        'underlying': evidence,
        'rule': 'Wrapper hashes ignored only after canonical PPTX, scoped scene and rendered PNG equality; every other hash stays exact.',
    }
    return status == 'PASS'


def matrix_outcome_checks(baseline_matrix, candidate_matrix, checks):
    """Compare the declared 96-cell outcomes without touching artifact files."""
    ok = True
    for label, value in (('baseline', baseline_matrix), ('candidate', candidate_matrix)):
        counts = value.get('fixture_counts') or {}
        expected = {
            'cells': EXPECTED_MATRIX['cells'],
            'accepted': EXPECTED_MATRIX['accepted'],
            'rejected': EXPECTED_MATRIX['rejected'],
        }
        ok &= check_equal(checks, f'matrix.{label}.fixture_counts', expected,
                          {key: counts.get(key) for key in expected})
        ok &= check_equal(checks, f'matrix.{label}.family_count', EXPECTED_MATRIX['native_family_count'],
                          value.get('native_family_count'))
        ok &= check_equal(checks, f'matrix.{label}.families', sorted(EXPECTED_MATRIX['families']),
                          sorted(value.get('families') or []))
        ok &= check_equal(checks, f'matrix.{label}.status', 'PASS', value.get('status'))
        ok &= check_equal(checks, f'matrix.{label}.accepted_cells', EXPECTED_MATRIX['accepted'],
                          len(value.get('accepted_cell_ids') or []))
        ok &= check_equal(checks, f'matrix.{label}.rejected_cells', EXPECTED_MATRIX['rejected'],
                          len(value.get('rejected_cells') or []))
    ok &= check_equal(checks, 'matrix.accepted_cell_ids',
                      sorted(baseline_matrix.get('accepted_cell_ids') or []),
                      sorted(candidate_matrix.get('accepted_cell_ids') or []))

    def rejection_signature(value):
        return sorted((item.get('id'), item.get('family'), item.get('case'), item.get('code'))
                      for item in value.get('rejected_cells') or [])

    ok &= check_equal(checks, 'matrix.rejection_codes',
                      rejection_signature(baseline_matrix), rejection_signature(candidate_matrix))
    for theme in ('light', 'dark'):
        left = (baseline_matrix.get('themes') or {}).get(theme) or {}
        right = (candidate_matrix.get('themes') or {}).get(theme) or {}
        ok &= check_equal(checks, f'matrix.{theme}.status', 'PASS', left.get('status'))
        ok &= check_equal(checks, f'matrix.{theme}.candidate_status', 'PASS', right.get('status'))
        ok &= check_equal(checks, f'matrix.{theme}.accepted_count',
                          left.get('accepted_cells'), right.get('accepted_cells'))
    return ok


def compare_matrix(baseline, candidate, baseline_root, candidate_root, checks):
    baseline_matrix = baseline.get('matrix') or {}
    candidate_matrix = candidate.get('matrix') or {}
    ok = matrix_outcome_checks(baseline_matrix, candidate_matrix, checks)
    for theme in ('light', 'dark'):
        left = (baseline_matrix.get('themes') or {}).get(theme) or {}
        right = (candidate_matrix.get('themes') or {}).get(theme) or {}
        left_cells = {cell.get('id'): cell for cell in (left.get('readback') or {}).get('cells') or []}
        right_cells = {cell.get('id'): cell for cell in (right.get('readback') or {}).get('cells') or []}
        ok &= check_equal(checks, f'matrix.{theme}.cell_ids', sorted(left_cells), sorted(right_cells))
        differences = []
        for cell_id in sorted(set(left_cells) & set(right_cells)):
            left_value = normalize_value(left_cells[cell_id], [baseline_root, candidate_root])
            right_value = normalize_value(right_cells[cell_id], [baseline_root, candidate_root])
            diffs = json_differences(left_value, right_value)
            if diffs:
                differences.append({'id': cell_id, 'example': diffs[0]})
        checks[f'matrix.{theme}.native_readback'] = {
            'status': 'PASS' if not differences else 'FAIL',
            'cells_compared': len(set(left_cells) & set(right_cells)),
            'differences': differences[:8],
        }
        ok &= not differences
    for theme in ('light', 'dark'):
        theme_manifest = (baseline_matrix.get('themes') or {}).get(theme) or {}
        for key, kind in (('pptx', 'pptx'), ('spec', 'json'), ('scene', 'scene')):
            descriptor = theme_manifest.get(key) or {}
            if not descriptor.get('path'):
                checks[f'matrix.artifact.{theme}.{key}'] = {
                    'status': 'FAIL', 'reason': 'missing artifact descriptor'}
                ok = False
                continue
            relative = descriptor['path']
            ok &= check_required(checks, f'matrix.artifact.{theme}.{key}',
                                 compare_artifact_pair(baseline_root, candidate_root, relative, relative, kind))
    supplemental = baseline_matrix.get('supplemental') or {}
    for key, kind in (('pptx', 'pptx'), ('spec', 'json'), ('scene', 'scene')):
        descriptor = supplemental.get(key) or {}
        if not descriptor.get('path'):
            checks[f'matrix.artifact.supplemental.{key}'] = {
                'status': 'FAIL', 'reason': 'missing artifact descriptor'}
            ok = False
            continue
        relative = descriptor['path']
        ok &= check_required(checks, f'matrix.artifact.supplemental.{key}',
                             compare_artifact_pair(baseline_root, candidate_root, relative, relative, kind))
    ok &= compare_supplemental_descriptors(
        supplemental, candidate_matrix.get('supplemental') or {},
        baseline_root, candidate_root, checks)
    for name in ('rejections', 'unsupported'):
        left = normalize_value(baseline_matrix.get(name) or {}, [baseline_root, candidate_root])
        right = normalize_value(candidate_matrix.get(name) or {}, [baseline_root, candidate_root])
        differences = json_differences(left, right)
        checks[f'matrix.{name}'] = {
            'status': 'PASS' if not differences else 'FAIL',
            'differences': len(differences),
            'examples': [{'path': item[0], 'baseline': item[1], 'candidate': item[2]}
                         for item in differences[:8]],
        }
        ok &= not differences
    return ok


def compare_gallery(baseline, candidate, baseline_root, candidate_root, checks):
    baseline_gallery = baseline.get('gallery') or {}
    candidate_gallery = candidate.get('gallery') or {}
    ok = True
    ok &= check_equal(checks, 'gallery.baseline_status', 'PASS', baseline_gallery.get('status'))
    ok &= check_equal(checks, 'gallery.candidate_status', 'PASS', candidate_gallery.get('status'))
    profiles = ('executive-dense', 'corporate', 'dark-executive')
    for profile in profiles:
        left = (baseline_gallery.get('variants') or {}).get(profile) or {}
        right = (candidate_gallery.get('variants') or {}).get(profile) or {}
        ok &= check_equal(checks, f'gallery.{profile}.baseline_status', 'PASS', left.get('status'))
        ok &= check_equal(checks, f'gallery.{profile}.candidate_status', 'PASS', right.get('status'))
        ok &= check_equal(checks, f'gallery.{profile}.slides', left.get('slides'), right.get('slides'))
        ok &= check_equal(checks, f'gallery.{profile}.qa', left.get('qa'), right.get('qa'))
        ok &= check_equal(checks, f'gallery.{profile}.visual_qa', 'NOT_RUN', right.get('visual_qa'))
        for suffix in ('spec', 'scene'):
            artifact = left.get(suffix) or {}
            if not artifact.get('path'):
                checks[f'gallery.{profile}.{suffix}'] = {'status': 'FAIL', 'reason': 'missing artifact descriptor'}
                ok = False
                continue
            kind = 'scene' if suffix == 'scene' else 'json'
            relative = artifact['path']
            ok &= check_required(checks, f'gallery.{profile}.{suffix}',
                                 compare_artifact_pair(baseline_root, candidate_root, relative, relative, kind))
        pptx = left.get('pptx') or {}
        if pptx.get('path'):
            ok &= check_required(checks, f'gallery.{profile}.pptx',
                                 compare_artifact_pair(baseline_root, candidate_root, pptx['path'], pptx['path'], 'pptx'))
        else:
            checks[f'gallery.{profile}.pptx'] = {'status': 'FAIL', 'reason': 'missing pptx descriptor'}
            ok = False
        qa_path = resolve_artifact(baseline_root, f'out/v1.3-showcase/gallery/{profile}/qa-gallery-{profile}.json')
        if qa_path is None:
            qa_path = resolve_artifact(baseline_root, f'gallery/{profile}/qa-gallery-{profile}.json')
        if qa_path is not None:
            relative = rel(qa_path, Path(baseline_root))
            ok &= check_required(checks, f'gallery.{profile}.qa_json',
                                 compare_artifact_pair(baseline_root, candidate_root, relative, relative, 'json'))
            qa_report = read_json(resolve_artifact(candidate_root, relative))
            pillow = ((qa_report.get('capabilities') or {}).get('tools') or {}).get('pillow')
            scene_descriptor = right.get('scene') or {}
            scene_path = resolve_artifact(candidate_root, scene_descriptor.get('path') or '')
            measurement = (title_measurement_evidence(scene_path) if scene_path
                           else {'status': 'FAIL', 'reason': 'missing candidate scene'})
            measured = pillow is True and measurement['status'] == 'PASS'
            checks[f'gallery.{profile}.measurement_method'] = {
                'status': 'PASS' if measured else 'FAIL',
                'pillow': pillow,
                **measurement,
            }
            ok &= measured
    for name in ('reconciliation', 'narrative', 'histogram', 'dashboards', 'cohorts',
                 'comparison_bases', 'title_fit'):
        left = normalize_value(baseline_gallery.get(name) or {}, [baseline_root, candidate_root])
        right = normalize_value(candidate_gallery.get(name) or {}, [baseline_root, candidate_root])
        differences = json_differences(left, right)
        checks[f'gallery.{name}'] = {
            'status': 'PASS' if not differences else 'FAIL',
            'differences': len(differences),
            'examples': [{'path': item[0], 'baseline': item[1], 'candidate': item[2]}
                         for item in differences[:8]],
        }
        ok &= not differences
    return ok


def compare_ledger(baseline, candidate, baseline_root, candidate_root, checks):
    left = baseline.get('ledger') or {}
    right = candidate.get('ledger') or {}
    ok = check_equal(checks, 'ledger.baseline_status', 'PASS', left.get('status'))
    ok &= check_equal(checks, 'ledger.candidate_status', 'PASS', right.get('status'))
    ok &= check_equal(checks, 'ledger.visual_qa', 'NOT_RUN', right.get('visual_qa'))
    for key in ('spec', 'scene'):
        artifact = left.get(key) or {}
        if artifact.get('path'):
            ok &= check_required(checks, f'ledger.{key}',
                                 compare_artifact_pair(baseline_root, candidate_root,
                                                       artifact['path'], artifact['path'],
                                                       'scene' if key == 'scene' else 'json'))
    if (left.get('pptx') or {}).get('path'):
        ok &= check_required(checks, 'ledger.pptx',
                             compare_artifact_pair(baseline_root, candidate_root,
                                                   left['pptx']['path'], left['pptx']['path'], 'pptx'))
    for key in ('narrative', 'issues'):
        left_value = normalize_value(left.get(key), [baseline_root, candidate_root])
        right_value = normalize_value(right.get(key), [baseline_root, candidate_root])
        differences = json_differences(left_value, right_value)
        checks[f'ledger.{key}'] = {
            'status': 'PASS' if not differences else 'FAIL',
            'differences': len(differences),
            'examples': [{'path': item[0], 'baseline': item[1], 'candidate': item[2]}
                         for item in differences[:8]],
        }
        ok &= not differences
    return ok


def relationship_entries(baseline_root, candidate_root):
    left_path = Path(baseline_root) / 'out/v1.3-showcase/relationships/manifest.json'
    right_path = Path(candidate_root) / 'out/v1.3-showcase/relationships/manifest.json'
    if not left_path.is_file() or not right_path.is_file():
        return None
    return read_json(left_path), read_json(right_path)


def compare_relationships(baseline_root, candidate_root, checks):
    pair = relationship_entries(baseline_root, candidate_root)
    if pair is None:
        checks['relationships.manifest'] = {'status': 'FAIL', 'reason': 'missing relationships manifest'}
        return False
    left, right = pair
    ok = check_equal(checks, 'relationships.baseline_status', 'PASS', left.get('status'))
    ok &= check_equal(checks, 'relationships.candidate_status', 'PASS', right.get('status'))
    ok &= check_equal(checks, 'relationships.visual_qa', 'NOT_RUN', right.get('visual_qa'))
    left_outputs = {(item.get('case'), item.get('theme')): item for item in left.get('outputs') or []}
    right_outputs = {(item.get('case'), item.get('theme')): item for item in right.get('outputs') or []}
    ok &= check_equal(checks, 'relationships.output_count', len(left_outputs), len(right_outputs))
    ok &= check_equal(checks, 'relationships.output_keys', sorted(left_outputs), sorted(right_outputs))
    for key in sorted(set(left_outputs) & set(right_outputs)):
        label = f'relationships.{key[0]}.{key[1]}'
        left_output = left_outputs[key]
        right_output = right_outputs[key]
        ok &= check_equal(checks, label + '.qa', left_output.get('qa', {}).get('status'),
                          right_output.get('qa', {}).get('status'))
        for artifact in ('spec', 'scene', 'pptx'):
            descriptor = left_output.get(artifact) or {}
            if not descriptor.get('path'):
                checks[label + '.' + artifact] = {'status': 'FAIL', 'reason': 'missing descriptor'}
                ok = False
                continue
            kind = 'pptx' if artifact == 'pptx' else ('scene' if artifact == 'scene' else 'json')
            ok &= check_required(checks, label + '.' + artifact,
                                 compare_artifact_pair(baseline_root, candidate_root,
                                                       descriptor['path'], descriptor['path'], kind))
        left_evidence = normalize_value(left_output.get('evidence'), [baseline_root, candidate_root])
        right_evidence = normalize_value(right_output.get('evidence'), [baseline_root, candidate_root])
        differences = json_differences(left_evidence, right_evidence)
        checks[label + '.evidence'] = {
            'status': 'PASS' if not differences else 'FAIL',
            'differences': len(differences),
            'examples': [{'path': item[0], 'baseline': item[1], 'candidate': item[2]}
                         for item in differences[:8]],
        }
        ok &= not differences
    return ok


def compare_scenarios(baseline, candidate, baseline_root, candidate_root, checks):
    left = {(item.get('slug') or item.get('id')): item for item in baseline.get('scenarios') or []}
    right = {(item.get('slug') or item.get('id')): item for item in candidate.get('scenarios') or []}
    ok = check_equal(checks, 'scenarios.keys', sorted(left), sorted(right))
    for slug in sorted(set(left) & set(right)):
        left_scenario = left[slug]
        right_scenario = right[slug]
        left_after = left_scenario.get('after') or {}
        right_after = right_scenario.get('after') or {}
        ok &= check_equal(checks, f'scenario.{slug}.after_status', 'PASS', right_after.get('status'))
        ok &= check_equal(checks, f'scenario.{slug}.qa', left_after.get('qa'), right_after.get('qa'))
        ok &= check_equal(checks, f'scenario.{slug}.visual_qa', 'NOT_RUN', right_after.get('visual_qa'))
        input_path = (left_scenario.get('input') or {}).get('path') or f'scenarios/{slug}/input.json'
        ok &= check_required(checks, f'scenario.{slug}.raw_input',
                             compare_artifact_pair(baseline_root, candidate_root, input_path, input_path, 'bytes'))
        for artifact in ('spec', 'scene', 'data'):
            descriptor = left_after.get(artifact) or {}
            if not descriptor.get('path'):
                continue
            kind = 'scene' if artifact == 'scene' else 'json'
            ok &= check_required(checks, f'scenario.{slug}.{artifact}',
                                 compare_artifact_pair(baseline_root, candidate_root,
                                                       descriptor['path'], descriptor['path'], kind))
        if (left_after.get('pptx') or {}).get('path'):
            ok &= check_required(checks, f'scenario.{slug}.pptx',
                                 compare_artifact_pair(baseline_root, candidate_root,
                                                       left_after['pptx']['path'], left_after['pptx']['path'], 'pptx'))
    return ok


def node_command():
    return shutil.which('node') or 'node'


def run_node(root, args, label, timeout=900):
    environment = os.environ.copy()
    environment['NODE_PATH'] = str(Path(root) / 'node_modules')
    started = time.time()
    result = subprocess.run([node_command(), *args], cwd=str(root), env=environment,
                            capture_output=True, text=True, timeout=timeout)
    return {
        'label': label,
        'command': [node_command(), *args],
        'exit': result.returncode,
        'duration_seconds': round(time.time() - started, 3),
        'stdout': result.stdout[-2000:],
        'stderr': result.stderr[-2000:],
    }


def compare_generated_outputs(label, baseline_temp, candidate_temp, baseline_root, candidate_root, checks, files):
    ok = True
    for name in files:
        baseline_file = Path(baseline_temp) / name
        candidate_file = Path(candidate_temp) / name
        if not baseline_file.is_file() or not candidate_file.is_file():
            checks[f'integration.{label}.{name}'] = {
                'status': 'FAIL', 'reason': 'generated artifact missing',
                'baseline_exists': baseline_file.is_file(),
                'candidate_exists': candidate_file.is_file(),
            }
            ok = False
            continue
        kind = 'pptx' if name.endswith('.pptx') else (
            'scene' if name.endswith('.scene.json') else 'json')
        paired_pptx = None
        if name.endswith('.scene.json'):
            pptx_name = name[:-len('.scene.json')]
            paired_pptx = (baseline_file.parent / pptx_name, candidate_file.parent / pptx_name)
        checks[f'integration.{label}.{name}'] = compare_artifact_pair(
            baseline_temp, candidate_temp, name, name, kind, paired_pptx=paired_pptx)
        ok &= checks[f'integration.{label}.{name}']['status'] == 'PASS'
        if name.endswith('.scene.json'):
            measurement = title_measurement_evidence(candidate_file)
            checks[f'integration.{label}.{name}.measurement'] = measurement
            ok &= measurement['status'] == 'PASS'
    return ok


def run_integration_checks(baseline_root, candidate_root, checks, work_root):
    ok = True
    node = node_command()
    commands = []
    for label, relative in (('multimodal', 'skill/examples/multimodal-integration.json'),):
        baseline_temp = Path(work_root) / 'baseline' / label
        candidate_temp = Path(work_root) / 'candidate' / label
        baseline_temp.mkdir(parents=True, exist_ok=True)
        candidate_temp.mkdir(parents=True, exist_ok=True)
        outputs = ['multimodal.pptx', 'multimodal.pptx.scene.json']
        for side, root, temp in (('baseline', baseline_root, baseline_temp),
                                 ('candidate', candidate_root, candidate_temp)):
            result = run_node(root, ['skill/scripts/build_deck.js', relative, str(temp / 'multimodal.pptx')],
                              f'{side}-{label}')
            commands.append(result)
            if result['exit'] != 0:
                checks[f'integration.{label}.{side}_build'] = {'status': 'FAIL', **result}
                ok = False
        checks[f'integration.{label}.build'] = {'status': 'PASS' if ok else 'FAIL', 'commands': commands}
        ok &= compare_generated_outputs(label, baseline_temp, candidate_temp, baseline_root, candidate_root,
                                        checks, outputs)
    q4 = 'skill/reasoning/fixtures/q4-six-actions/plan.json'
    baseline_temp = Path(work_root) / 'baseline' / 'q4'
    candidate_temp = Path(work_root) / 'candidate' / 'q4'
    baseline_temp.mkdir(parents=True, exist_ok=True)
    candidate_temp.mkdir(parents=True, exist_ok=True)
    q4_outputs = ['q4.pptx', 'q4.spec.json', 'q4.pptx.scene.json']
    q4_commands = []
    for side, root, temp in (('baseline', baseline_root, baseline_temp),
                             ('candidate', candidate_root, candidate_temp)):
        result = run_node(root, ['skill/scripts/compile_plan.js', q4, '--out', str(temp / 'q4.pptx'),
                                 '--spec-out', str(temp / 'q4.spec.json')], f'{side}-q4')
        q4_commands.append(result)
        if result['exit'] != 0:
            checks[f'integration.q4.{side}_build'] = {'status': 'FAIL', **result}
            ok = False
    checks['integration.q4.build'] = {'status': 'PASS' if ok else 'FAIL', 'commands': q4_commands}
    ok &= compare_generated_outputs('q4', baseline_temp, candidate_temp, baseline_root, candidate_root,
                                    checks, q4_outputs)

    for recipe in RECIPE_INPUTS:
        baseline_temp = Path(work_root) / 'baseline' / 'recipe-' / recipe
        candidate_temp = Path(work_root) / 'candidate' / 'recipe-' / recipe
        baseline_temp.mkdir(parents=True, exist_ok=True)
        candidate_temp.mkdir(parents=True, exist_ok=True)
        source = f'skill/analytics/{recipe}.json'
        outputs = [f'{recipe}.pptx', f'{recipe}.pptx.spec.json', f'{recipe}.pptx.scene.json']
        recipe_commands = []
        recipe_ok = True
        for side, root, temp in (('baseline', baseline_root, baseline_temp),
                                 ('candidate', candidate_root, candidate_temp)):
            result = run_node(root, ['scripts/analyze.js', source, str(temp / f'{recipe}.pptx')],
                              f'{side}-recipe-{recipe}')
            recipe_commands.append(result)
            if result['exit'] != 0:
                checks[f'integration.recipe.{recipe}.{side}_build'] = {'status': 'FAIL', **result}
                recipe_ok = False
        ok &= recipe_ok
        checks[f'integration.recipe.{recipe}.build'] = {
            'status': 'PASS' if recipe_ok else 'FAIL',
            'commands': recipe_commands,
            'input_sha256': sha256_bytes((Path(baseline_root) / source).read_bytes())
            if (Path(baseline_root) / source).is_file() else None,
            'candidate_input_sha256': sha256_bytes((Path(candidate_root) / source).read_bytes())
            if (Path(candidate_root) / source).is_file() else None,
        }
        if (Path(baseline_root) / source).is_file() and (Path(candidate_root) / source).is_file():
            same_input = ((Path(baseline_root) / source).read_bytes()
                          == (Path(candidate_root) / source).read_bytes())
            checks[f'integration.recipe.{recipe}.raw_input'] = {
                'status': 'PASS' if same_input else 'FAIL'}
            ok &= same_input
        ok &= compare_generated_outputs(f'recipe-{recipe}', baseline_temp, candidate_temp,
                                        baseline_root, candidate_root, checks, outputs)
    return ok


def performance_sample(baseline_root, candidate_root, repeats):
    results = []
    example = 'skill/examples/executive-review.json'
    for side, root in (('baseline', baseline_root), ('candidate', candidate_root)):
        samples = []
        with tempfile.TemporaryDirectory() as temp:
            for index in range(repeats + 1):
                output = Path(temp) / f'deck-{index}.pptx'
                started = time.time()
                result = subprocess.run(
                    [node_command(), 'skill/scripts/build_deck.js', example, str(output)],
                    cwd=str(root), env={**os.environ, 'NODE_PATH': str(Path(root) / 'node_modules')},
                    capture_output=True, text=True, timeout=900)
                elapsed = time.time() - started
                if index:
                    samples.append(round(elapsed, 3))
                if result.returncode != 0:
                    return {'status': 'NOT_RUN', 'reason': f'{side} build failed', 'stderr': result.stderr[-500:]}
        results.append({'side': side, 'warmup_ignored': True, 'samples_seconds': samples,
                        'median_seconds': sorted(samples)[len(samples) // 2] if samples else None})
    return {'status': 'INFORMATIONAL', 'repeats': repeats, 'results': results,
            'note': 'Local wall-clock sample only; not a machine-independent claim.'}


def version_failures(baseline_version, candidate_version, rule):
    failures = []
    if baseline_version != rule['baseline_version']:
        failures.append(f'baseline version is {baseline_version}, expected {rule["baseline_version"]}')
    if candidate_version != rule['candidate_version']:
        failures.append(f'candidate version is {candidate_version}, expected {rule["candidate_version"]}')
    return failures


def baseline_archive_evidence(zip_path, baseline_root, locked_sha256=None):
    """Prove the compared baseline tree is the locked archive's member bytes."""
    zip_path = Path(zip_path)
    root = Path(baseline_root)
    locked_sha256 = LOCKED_BASELINE_ZIP_SHA256 if locked_sha256 is None else locked_sha256
    if not zip_path.is_file():
        return {'status': 'FAIL', 'reason': 'baseline ZIP is missing', 'zip_sha256': None,
                'locked_zip_verified': False}
    digest = sha256_bytes(zip_path.read_bytes())
    locked = digest == locked_sha256
    with zipfile.ZipFile(zip_path) as archive:
        members = {info.filename: sha256_bytes(archive.read(info.filename))
                   for info in archive.infolist() if not info.is_dir()}
    prefixes = {name.split('/')[0] for name in members}
    prefix = next(iter(prefixes)) if len(prefixes) == 1 else ''
    missing = []
    changed = []
    compared = 0
    for name, member_hash in members.items():
        relative = name[len(prefix) + 1:] if prefix and name.startswith(prefix + '/') else name
        target = root / relative
        if not target.is_file():
            missing.append(relative)
            continue
        compared += 1
        if sha256_bytes(target.read_bytes()) != member_hash:
            changed.append(relative)
    status = 'PASS' if locked and not missing and not changed else 'FAIL'
    return {
        'status': status,
        'zip_sha256': digest,
        'locked_zip_sha256': locked_sha256,
        'locked_zip_verified': locked,
        'package_root_prefix': prefix,
        'archive_members': len(members),
        'tree_members_compared': compared,
        'missing_count': len(missing),
        'changed_count': len(changed),
        'missing_members': missing[:12],
        'changed_members': changed[:12],
        'rule': 'Every locked archive member must exist byte-identically in the compared baseline tree; a ZIP checksum alone is insufficient.',
    }


def verify(baseline_root, candidate_root, baseline_zip=None, performance=False, repeats=3,
           contract=DEFAULT_CONTRACT):
    baseline_root = Path(baseline_root).resolve()
    candidate_root = Path(candidate_root).resolve()
    rule = CONTRACTS.get(contract)
    checks = {}
    failures = []
    result = {
        'schema_version': rule['candidate_version'] if rule else None,
        'capability_parity': contract,
        'baseline': {'root': str(baseline_root), 'version': None, 'zip_sha256': None,
                     'locked_zip_sha256': rule['locked_baseline_zip_sha256'] if rule else None,
                     'locked_zip_verified': False},
        'candidate': {'root': str(candidate_root), 'version': None},
        'checks': checks,
        'status': 'FAIL',
        'failures': failures,
        'visual_review': 'NOT_RUN',
        'company_platform_security': 'NOT_VERIFIED',
        'normalization': {
            'timestamps': 'only named collection timestamps (generated_at, created_at, ...) replaced; business-valued ISO strings stay exact',
            'paths': 'the two supplied root prefixes replaced in plain path strings; URI values are never rewritten',
            'derived_hashes': ('pptx_sha256/pptx_content_sha256 wrappers; root scene content_sha256 only with declared '
                               'scope; supplemental pptx/scene/pdf wrapper hashes only after canonical underlying comparisons'),
            'not_normalized': ['data', 'titles', 'layout', 'fonts', 'series', 'measurement', 'images',
                               'provenance hashes', 'event timestamps', 'file URLs', 'nested content hashes'],
        },
    }
    if rule is None:
        failures.append(f'unknown capability parity contract: {contract}')
        result['failures'] = failures
        return result
    archive = None
    if baseline_zip:
        archive = baseline_archive_evidence(baseline_zip, baseline_root, rule['locked_baseline_zip_sha256'])
        result['baseline']['zip_sha256'] = archive['zip_sha256']
        result['baseline']['locked_zip_verified'] = archive['locked_zip_verified']
        result['baseline']['archive_member_equality'] = archive
        if not archive['locked_zip_verified']:
            failures.append(f'baseline ZIP SHA-256 does not match the locked {rule["baseline_release"]} installer')
        if archive['status'] != 'PASS':
            failures.append('baseline tree bytes do not match the locked archive members')
            result['failures'] = failures
            return result
    else:
        failures.append('locked baseline ZIP not supplied; archive member equality is unproven')
        result['failures'] = failures
        return result
    baseline_manifest_path = baseline_root / 'out/v1.3-showcase/showcase.manifest.json'
    candidate_manifest_path = candidate_root / 'out/v1.3-showcase/showcase.manifest.json'
    if not baseline_manifest_path.is_file() or not candidate_manifest_path.is_file():
        failures.append('both roots must contain out/v1.3-showcase/showcase.manifest.json')
        result['failures'] = failures
        return result
    baseline = read_json(baseline_manifest_path)
    candidate = read_json(candidate_manifest_path)
    result['baseline']['version'] = baseline.get('version')
    result['candidate']['version'] = candidate.get('version')
    failures.extend(version_failures(baseline.get('version'), candidate.get('version'), rule))
    for suite in ('matrix', 'gallery', 'ledger'):
        if (baseline.get(suite) or {}).get('status') != 'PASS':
            failures.append(f'baseline {suite} is not PASS')
        if (candidate.get(suite) or {}).get('status') != 'PASS':
            failures.append(f'candidate {suite} is not PASS')
    checks['versions'] = {'status': 'PASS' if not failures else 'FAIL',
                          'baseline': baseline.get('version'), 'candidate': candidate.get('version')}
    matrix_ok = compare_matrix(baseline, candidate, str(baseline_root), str(candidate_root), checks)
    gallery_ok = compare_gallery(baseline, candidate, str(baseline_root), str(candidate_root), checks)
    ledger_ok = compare_ledger(baseline, candidate, str(baseline_root), str(candidate_root), checks)
    relationships_ok = compare_relationships(str(baseline_root), str(candidate_root), checks)
    scenarios_ok = compare_scenarios(baseline, candidate, str(baseline_root), str(candidate_root), checks)
    png_checks = compare_png_trees(str(baseline_root / 'out/v1.3-showcase'),
                                   str(candidate_root / 'out/v1.3-showcase'))
    checks['rendered_pngs'] = png_checks
    measurement_ok = compare_scene_measurements(str(candidate_root), checks)
    integration_ok = False
    with tempfile.TemporaryDirectory() as work_root:
        integration_ok = run_integration_checks(str(baseline_root), str(candidate_root), checks, work_root)
    if performance:
        checks['performance'] = performance_sample(str(baseline_root), str(candidate_root), repeats)
    else:
        checks['performance'] = {'status': 'NOT_RUN',
                                 'note': 'Run with --performance for a fair repeated local sample.'}
    required = {
        'matrix': matrix_ok,
        'gallery': gallery_ok,
        'ledger': ledger_ok,
        'relationships': relationships_ok,
        'scenarios': scenarios_ok,
        'rendered_pngs': png_checks['status'] == 'PASS',
        'scene_title_measurements': measurement_ok,
        'integration': integration_ok,
        'baseline_archive_member_equality': archive is not None and archive['status'] == 'PASS',
        'versions': not failures,
    }
    for name, passed in required.items():
        if not passed and name != 'versions':
            failures.append(f'{name} comparison failed')
    checks['summary'] = {'status': 'PASS' if all(required.values()) else 'FAIL',
                         'required': required}
    result['status'] = 'PASS' if all(required.values()) else 'FAIL'
    result['failures'] = failures
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline_root', help='checkout/extraction containing out/v1.3-showcase')
    parser.add_argument('candidate_root', help='candidate checkout containing out/v1.3-showcase')
    parser.add_argument('--baseline-zip', help='optional locked baseline installer ZIP to hash-check')
    parser.add_argument('--contract', choices=sorted(CONTRACTS), default=DEFAULT_CONTRACT,
                        help='fixed capability parity contract; versions and locked SHA come from the contract')
    parser.add_argument('--performance', action='store_true', help='run an informational repeated timing sample')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--json', help='write the result JSON to this path')
    args = parser.parse_args()
    result = verify(args.baseline_root, args.candidate_root, args.baseline_zip,
                    performance=args.performance, repeats=args.repeats, contract=args.contract)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(payload, encoding='utf-8')
    summary = {
        'capability_parity': result['capability_parity'],
        'status': result['status'],
        'baseline_version': result['baseline']['version'],
        'candidate_version': result['candidate']['version'],
        'locked_zip_verified': result['baseline']['locked_zip_verified'],
        'failures': result['failures'],
        'visual_review': result['visual_review'],
        'company_platform_security': result['company_platform_security'],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
