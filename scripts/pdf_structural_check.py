#!/usr/bin/env python3
"""Deterministic PDF structural facts for the Goujian security gate.

This helper is deliberately separate from the product runtime and from the
Cisco skill scanner. It is installed only into the isolated security tool
environment from a hash-locked pure-Python wheel and is invoked in a bounded
subprocess by ``scripts/scan_skill_package.py``.

The only semantic classification it can produce is the narrow policy in
``security/pdf-structural-policy.json``: a root catalog ``/OpenAction`` that is
a direct typed array of exactly ``[local page ref /XYZ null null 0]``, with a
complete, warning-free strict parse and no action dictionary, executable key or
other ``/OpenAction`` anywhere in the parsed object graph. Every other shape
fails closed. The helper never executes, renders or trusts a PDF and never
uses the network.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import sys
import warnings
from pathlib import Path

SCHEMA_VERSION = 1
CHECK_NAME = 'GOUJIAN_PDF_STRUCTURAL_CHECK'
CHECKER_VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]

ACTION_SUBTYPES = frozenset({
    '/GoTo', '/GoToR', '/GoToE', '/Launch', '/Thread', '/URI', '/Sound',
    '/Movie', '/Hide', '/Named', '/SubmitForm', '/ResetForm', '/ImportData',
    '/JavaScript', '/SetOCGState', '/Rendition', '/Trans', '/GoTo3DView',
    '/RichMediaExecute',
})
DANGEROUS_TYPES = frozenset({
    '/EmbeddedFile', '/Filespec', '/RichMedia', '/3D', '/XFA', '/Action',
})
DANGEROUS_SUBTYPES = frozenset({
    '/FileAttachment', '/RichMedia', '/3D', '/Movie', '/Sound', '/Screen',
    '/Widget',
})
LAYOUT_ATTRIBUTE_OWNERS = frozenset({'/Layout', '/List', '/PrintField', '/Table'})
FORBIDDEN_KEYS = frozenset({
    '/JS', '/JavaScript', '/AA', '/Launch', '/URI', '/SubmitForm', '/ResetForm',
    '/ImportData', '/GoToR', '/GoToE', '/Thread', '/Sound', '/Movie', '/Rendition',
    '/SetOCGState', '/RichMedia', '/XFA', '/EmbeddedFiles', '/AF', '/EF',
    '/FileAttachment', '/AcroForm', '/FS',
})
OPEN_ACTION_SHAPE = ('page-indirect-ref', '/XYZ', 'null', 'null', '0')


class PdfCheckFailure(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def observed_process_limits():
    result = {'bounded': False, 'resource_module': False}
    try:
        import resource
    except ImportError:
        return result
    result['resource_module'] = True
    infinite = getattr(resource, 'RLIM_INFINITY', -1)
    bounded = True
    for name in ('RLIMIT_AS', 'RLIMIT_CPU', 'RLIMIT_NOFILE', 'RLIMIT_FSIZE'):
        if not hasattr(resource, name):
            bounded = False
            continue
        soft, hard = resource.getrlimit(getattr(resource, name))
        result[name] = {'soft': soft, 'hard': hard}
        if soft == infinite:
            bounded = False
    result['bounded'] = bounded
    return result


def read_json(path, code):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise PdfCheckFailure(code, f'{path}: {error}')


def require(condition, code, detail):
    if not condition:
        raise PdfCheckFailure(code, detail)


def load_policy(policy_path):
    policy = read_json(policy_path, 'INVALID_POLICY')
    require(policy.get('schema_version') == 1, 'INVALID_POLICY',
            'policy schema_version must be 1')
    require(isinstance(policy.get('policy_id'), str) and policy['policy_id'],
            'INVALID_POLICY', 'policy_id is missing')
    binding = policy.get('rule_binding')
    require(isinstance(binding, dict), 'INVALID_POLICY', 'rule_binding is missing')
    require(binding.get('rule_id') == 'PDF_STRUCTURAL_THREAT', 'INVALID_POLICY',
            'rule_id binding is not PDF_STRUCTURAL_THREAT')
    require(binding.get('severity') == 'HIGH', 'INVALID_POLICY',
            'severity binding is not HIGH')
    require(binding.get('metadata_detected_keywords') == {'/OpenAction': 1},
            'INVALID_POLICY', 'metadata keyword binding is not {"/OpenAction": 1}')
    checker = policy.get('checker')
    require(isinstance(checker, dict), 'INVALID_POLICY', 'checker section is missing')
    require(checker.get('path') == 'scripts/pdf_structural_check.py', 'INVALID_POLICY',
            'checker path is not scripts/pdf_structural_check.py')
    require(checker.get('version') == CHECKER_VERSION, 'INVALID_POLICY',
            'checker version does not match this helper')
    actual_checker_sha = sha256_file(Path(__file__))
    require(checker.get('sha256') == actual_checker_sha, 'CHECKER_IDENTITY_MISMATCH',
            'policy checker sha256 does not match this helper')
    parser = policy.get('parser')
    require(isinstance(parser, dict), 'INVALID_POLICY', 'parser section is missing')
    require(parser.get('package') == 'pypdf', 'INVALID_POLICY',
            'parser package must be pypdf')
    require(re.match(r'^[0-9]+\.[0-9]+\.[0-9]+$', str(parser.get('version'))),
            'INVALID_POLICY', 'parser version is invalid')
    require(re.match(r'^[0-9a-f]{64}$', str(parser.get('wheel_sha256'))),
            'INVALID_POLICY', 'parser wheel hash is invalid')
    semantics = policy.get('semantics')
    require(isinstance(semantics, dict), 'INVALID_POLICY', 'semantics are missing')
    for key in ('max_pdf_bytes', 'max_objects', 'max_depth'):
        require(isinstance(semantics.get(key), int) and semantics[key] > 0,
                'INVALID_POLICY', f'invalid semantic limit: {key}')
    return policy, actual_checker_sha


def load_parser(policy):
    package = policy['parser']['package']
    try:
        import pypdf
        from pypdf import PdfReader
        from pypdf.generic import (
            ArrayObject, DictionaryObject, IndirectObject, NameObject,
            NullObject, NumberObject, StreamObject,
        )
    except ImportError as error:
        raise PdfCheckFailure('PARSER_UNAVAILABLE',
                              f'{package} is not installed: {error}')
    version = getattr(pypdf, '__version__', None)
    require(version == policy['parser']['version'], 'PARSER_IDENTITY_MISMATCH',
            f'installed {package} version {version!r} != pin {policy["parser"]["version"]!r}')
    return {
        'PdfReader': PdfReader,
        'ArrayObject': ArrayObject,
        'DictionaryObject': DictionaryObject,
        'IndirectObject': IndirectObject,
        'NameObject': NameObject,
        'NullObject': NullObject,
        'NumberObject': NumberObject,
        'StreamObject': StreamObject,
    }


class RecordHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append({
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        })


def capture_warnings():
    handler = RecordHandler()
    logger = logging.getLogger('pypdf')
    old_level = logger.level
    old_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    return handler, logger, old_level, old_propagate


def release_warnings(handle):
    handler, logger, old_level, old_propagate = handle
    logger.removeHandler(handler)
    logger.setLevel(old_level)
    logger.propagate = old_propagate


def value_type(value, classes):
    if isinstance(value, classes['IndirectObject']):
        return 'indirect'
    if isinstance(value, classes['ArrayObject']):
        return 'array'
    if isinstance(value, classes['DictionaryObject']):
        return 'dictionary'
    if isinstance(value, classes['StreamObject']):
        return 'stream'
    if isinstance(value, classes['NameObject']):
        return 'name'
    if isinstance(value, classes['NullObject']):
        return 'null'
    if isinstance(value, classes['NumberObject']):
        return 'number'
    return type(value).__name__


def walk_graph(reader, classes, policy, facts):
    """Inspect every xref/object-stream object once and build hit evidence."""
    max_depth = policy['semantics']['max_depth']
    max_objects = policy['semantics']['max_objects']
    seen = set()
    hits = {
        'action_dictionaries': [],
        'forbidden_keys': [],
        'forbidden_object_values': [],
        'other_open_actions': [],
        'unsupported_a_contexts': [],
        'invalid_a_values': [],
        'object_errors': [],
    }
    open_actions = []
    state = {'visited': 1, 'max_depth_observed': 0, 'depth_exceeded': False}
    action_keys = set()

    def add_action(owner, value):
        if isinstance(value, classes['DictionaryObject']):
            keys = sorted(str(key) for key in value.keys())
            entry = {
                'owner': owner,
                'type': str(value.get('/Type', '')),
                'subtype': str(value.get('/S', '')),
                'keys': keys,
            }
            marker = (entry['owner'], entry['type'], entry['subtype'], tuple(keys))
            if marker not in action_keys:
                action_keys.add(marker)
                hits['action_dictionaries'].append(entry)

    def is_action(value):
        if not isinstance(value, classes['DictionaryObject']):
            return False
        if str(value.get('/Type', '')) == '/Action':
            return True
        return str(value.get('/S', '')) in ACTION_SUBTYPES

    def layout_attribute_value(value, depth=0):
        if depth > 2:
            return False
        if isinstance(value, classes['IndirectObject']):
            try:
                value = value.get_object()
            except Exception:
                return False
        if isinstance(value, classes['ArrayObject']):
            return bool(value) and all(
                layout_attribute_value(item, depth + 1) for item in value)
        if isinstance(value, classes['DictionaryObject']):
            return str(value.get('/O', '')) in LAYOUT_ATTRIBUTE_OWNERS \
                and '/S' not in value and '/A' not in value
        return False

    def a_context_allowed(value):
        return isinstance(value, classes['DictionaryObject']) \
            and str(value.get('/Type', '')) == '/StructElem'

    def inspect_dict(value, owner, context):
        type_name = str(value.get('/Type', ''))
        subtype_name = str(value.get('/Subtype', ''))
        if type_name in DANGEROUS_TYPES:
            hits['forbidden_object_values'].append(
                {'owner': owner, 'key': '/Type', 'value': type_name})
        if subtype_name in DANGEROUS_SUBTYPES:
            hits['forbidden_object_values'].append(
                {'owner': owner, 'key': '/Subtype', 'value': subtype_name})
        if '/A' in value:
            if not a_context_allowed(value):
                hits['unsupported_a_contexts'].append({'owner': owner, 'keys': sorted(
                    str(key) for key in value.keys())})
            elif not layout_attribute_value(value['/A']):
                hits['invalid_a_values'].append({'owner': owner, 'keys': sorted(
                    str(key) for key in value.keys())})
        for key in value.keys():
            name = str(key)
            if not name.startswith('/'):
                name = '/' + name
            if name in FORBIDDEN_KEYS:
                hits['forbidden_keys'].append({'key': name, 'owner': owner})
            if name == '/OpenAction':
                open_actions.append({'owner': owner, 'context': context})
                if context != 'catalog' or owner != 'catalog':
                    hits['other_open_actions'].append(
                        {'owner': owner, 'context': context})
        if is_action(value):
            add_action(owner, value)

    def walk(value, depth, owner, context):
        if depth > max_depth:
            state['depth_exceeded'] = True
            return
        state['max_depth_observed'] = max(state['max_depth_observed'], depth)
        if isinstance(value, classes['IndirectObject']):
            marker = (value.idnum, value.generation)
            if marker in seen:
                return
            seen.add(marker)
            try:
                resolved = value.get_object()
            except Exception as error:  # fail closed, keep the object id
                hits['object_errors'].append({
                    'object': marker[0], 'generation': marker[1],
                    'error': f'{type(error).__name__}: {error}',
                })
                return
            state['visited'] += 1
            walk(resolved, depth + 1, f'{marker[0]} {marker[1]} R', 'value')
            return
        if isinstance(value, classes['StreamObject']):
            inspect_dict(value, owner, context)
            for key, child in value.items():
                walk(child, depth + 1, owner, context if key == '/OpenAction' else 'value')
            return
        if isinstance(value, classes['DictionaryObject']):
            inspect_dict(value, owner, context)
            for key, child in value.items():
                child_context = 'catalog' if (context == 'catalog' and owner == 'catalog'
                                              and str(key) == '/OpenAction') else 'value'
                walk(child, depth + 1, owner, child_context)
            return
        if isinstance(value, classes['ArrayObject']):
            for child in value:
                walk(child, depth + 1, owner, context)
            return

    try:
        pages = list(reader.pages)
        page_refs = []
        for page in pages:
            reference = getattr(page, 'indirect_reference', None)
            if reference is not None:
                page_refs.append((reference.idnum, reference.generation))
    except Exception as error:
        raise PdfCheckFailure('PAGE_TREE_ERROR',
                              f'cannot enumerate the document page tree: {error}')
    page_ref_set = set(page_refs)
    if len(page_refs) != len(page_ref_set):
        raise PdfCheckFailure('PAGE_TREE_DUPLICATE',
                              'the page tree references a page object more than once')
    if not pages:
        raise PdfCheckFailure('PAGE_TREE_EMPTY', 'the document has no pages')

    root_ref = reader.trailer.get('/Root')
    catalog = reader.root_object
    if isinstance(root_ref, classes['IndirectObject']):
        seen.add((root_ref.idnum, root_ref.generation))
    walk(catalog, 0, 'catalog', 'catalog')
    walk(reader.trailer, 0, 'trailer', 'trailer')

    entries = []
    free_entries = 0
    xref_generations = 0
    for generation, objects in sorted(reader.xref.items()):
        if not objects:
            continue
        xref_generations += 1
        for object_id in sorted(objects):
            if reader.xref_free_entry.get(generation, {}).get(object_id):
                free_entries += 1
                continue
            entries.append((int(object_id), int(generation), 'xref'))
    compressed = 0
    for object_id, location in sorted(reader.xref_objStm.items()):
        entries.append((int(object_id), 0, 'objstm'))
        compressed += 1
    unique_entries = sorted({(object_id, generation, kind)
                             for object_id, generation, kind in entries})
    state['xref_objects'] = len([item for item in unique_entries if item[2] == 'xref'])
    state['compressed_objects'] = compressed
    state['free_entries'] = free_entries
    state['xref_generations'] = xref_generations
    if len(pages) > max_objects:
        raise PdfCheckFailure('OBJECT_LIMIT', 'page count exceeds the object limit')
    enumerated = 0
    for object_id, generation, kind in unique_entries:
        if (object_id, generation) in seen:
            continue
        if enumerated >= max_objects:
            raise PdfCheckFailure('OBJECT_LIMIT',
                                  f'{max_objects} objects exceed the configured limit')
        enumerated += 1
        seen.add((object_id, generation))
        try:
            resolved = reader.get_object(classes['IndirectObject'](
                object_id, generation, reader))
        except Exception as error:
            hits['object_errors'].append({
                'object': object_id, 'generation': generation, 'kind': kind,
                'error': f'{type(error).__name__}: {error}',
            })
            continue
        state['visited'] += 1
        walk(resolved, 0, f'{object_id} {generation} R', 'value')
    if state['depth_exceeded']:
        raise PdfCheckFailure('DEPTH_LIMIT',
                              f'object graph exceeds max_depth {max_depth}')
    if len(open_actions) != 1:
        raise PdfCheckFailure('OPENACTION_COUNT',
                              f'expected one /OpenAction key, found {len(open_actions)}')
    if hits['object_errors']:
        raise PdfCheckFailure('OBJECT_PARSE_ERROR',
                              f'{len(hits["object_errors"])} object(s) could not be parsed')
    return {
        'hits': hits,
        'open_action_value': catalog.get('/OpenAction'),
        'page_refs': page_ref_set,
        'page_count': len(pages),
        'state': state,
    }


def describe_open_action(value, classes, page_refs):
    facts = {
        'direct_array': isinstance(value, classes['ArrayObject']),
        'value_type': value_type(value, classes),
        'length': len(value) if isinstance(value, classes['ArrayObject']) else None,
        'sha_shape': list(OPEN_ACTION_SHAPE),
        'page': None,
        'elements': [],
    }
    if not isinstance(value, classes['ArrayObject']):
        return facts, ['the catalog /OpenAction is not a direct typed array']
    problems = []
    for index, item in enumerate(value):
        kind = value_type(item, classes)
        element = {'index': index, 'type': kind}
        if isinstance(item, classes['IndirectObject']):
            element.update({'object': item.idnum, 'generation': item.generation})
            if index == 0:
                page = None
                try:
                    page = item.get_object()
                except Exception as error:
                    problems.append(f'page reference cannot be resolved: {error}')
                element['local_page'] = (item.idnum, item.generation) in page_refs
                element['page_type'] = str(page.get('/Type', '')) if page is not None else None
                facts['page'] = element.copy()
                if not element['local_page']:
                    problems.append('the destination page is not a page in this document')
                if element['page_type'] != '/Page':
                    problems.append('the destination object is not a /Page')
        elif isinstance(item, classes['NameObject']):
            element['value'] = str(item)
        elif isinstance(item, classes['NullObject']):
            element['value'] = None
        elif isinstance(item, classes['NumberObject']):
            element['value'] = int(item) if str(item) == '0' else str(item)
            element['text'] = str(item)
        else:
            element['value'] = str(item)
        facts['elements'].append(element)
    if len(value) != 5:
        problems.append(f'the /OpenAction array has {len(value)} elements, expected 5')
    elif not isinstance(value[0], classes['IndirectObject']):
        problems.append('element 0 is not an indirect page reference')
    elif not isinstance(value[1], classes['NameObject']) or str(value[1]) != '/XYZ':
        problems.append('element 1 is not /XYZ')
    elif not isinstance(value[2], classes['NullObject']):
        problems.append('element 2 is not null')
    elif not isinstance(value[3], classes['NullObject']):
        problems.append('element 3 is not null')
    elif not isinstance(value[4], classes['NumberObject']) or str(value[4]) != '0':
        problems.append('element 4 is not integer 0')
    return facts, problems


def check_pdf(args, policy, checker_sha):
    classes = load_parser(policy)
    pdf_path = Path(args.pdf)
    require(pdf_path.is_file() and not pdf_path.is_symlink(), 'PDF_UNAVAILABLE',
            f'PDF is missing or a symlink: {pdf_path}')
    size = pdf_path.stat().st_size
    require(size <= policy['semantics']['max_pdf_bytes'], 'PDF_TOO_LARGE',
            f'PDF is {size} bytes; limit {policy["semantics"]["max_pdf_bytes"]}')
    data = pdf_path.read_bytes()
    actual_sha = sha256_bytes(data)
    require(actual_sha == args.expected_sha256, 'PDF_HASH_MISMATCH',
            f'expected {args.expected_sha256}, found {actual_sha}')

    facts = {
        'schema_version': SCHEMA_VERSION,
        'check': CHECK_NAME,
        'status': 'FAIL',
        'checker': {
            'name': 'scripts/pdf_structural_check.py',
            'version': CHECKER_VERSION,
            'sha256': checker_sha,
        },
        'policy': {
            'id': policy['policy_id'],
            'sha256': sha256_file(args.policy),
            'rule_id': policy['rule_binding']['rule_id'],
            'severity': policy['rule_binding']['severity'],
            'metadata_detected_keywords':
                policy['rule_binding']['metadata_detected_keywords'],
        },
        'parser': {
            'package': policy['parser']['package'],
            'version': policy['parser']['version'],
            'wheel': policy['parser'].get('wheel'),
            'wheel_sha256': policy['parser']['wheel_sha256'],
            'license': policy['parser'].get('license'),
        },
        'pdf': {'sha256': actual_sha, 'bytes': size},
        'process_limits': observed_process_limits(),
        'parsed': {},
        'open_action': {},
        'dangerous': {},
        'checks': {},
        'failures': [],
    }
    failure_codes = []

    def failure(code, detail):
        if code not in failure_codes:
            failure_codes.append(code)
        facts['failures'].append({'code': code, 'detail': detail})

    def check(name, passed, detail=None):
        entry = {'status': 'PASS' if passed else 'FAIL'}
        if detail:
            entry['detail'] = detail
        facts['checks'][name] = entry
        return passed

    facts['checks']['file_hash'] = {'status': 'PASS'}
    facts['checks']['parser_available'] = {'status': 'PASS'}
    warning_handle = capture_warnings()

    def finish(result, codes):
        result['parsed']['warnings'] = warning_handle[0].records + caught_warnings
        result['parsed']['warning_records'] = list(caught_warnings)
        release_warnings(warning_handle)
        return result, codes

    def capture(records):
        caught_warnings.extend({
            'category': item.category.__name__,
            'message': str(item.message),
        } for item in records)

    caught_warnings = []
    reader = None
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            reader = classes['PdfReader'](io.BytesIO(data), strict=True)
            capture(caught)
    except Exception as error:  # strict parse only; never fall back
        detail = f'{type(error).__name__}: {error}'
        if 'Multiple definitions' in detail:
            failure('DUPLICATE_KEY', detail)
        elif 'xref' in detail.lower() or 'trailer' in detail.lower():
            failure('AMBIGUOUS_XREF', detail)
        else:
            failure('PARSER_ERROR', detail)
    parser_warnings = warning_handle[0].records + caught_warnings
    facts['parsed'] = {
        'strict': True,
        'warnings': parser_warnings,
        'objects': 0,
        'xref_objects': 0,
        'compressed_objects': 0,
        'free_entries': 0,
        'xref_generations': 0,
        'max_depth_observed': 0,
        'object_errors': [],
    }
    if reader is None:
        return finish(facts, failure_codes)
    facts['checks']['strict_parse'] = {'status': 'PASS'}

    encrypted = bool(getattr(reader, 'is_encrypted', False)) or '/Encrypt' in reader.trailer
    if not check('not_encrypted', not encrypted,
                 'encrypted PDFs are unsupported' if encrypted else None):
        failure('ENCRYPTED', 'encrypted PDFs are unsupported')
    ambiguous = [key for key in ('/Prev', '/XRefStm') if key in reader.trailer]
    if not check('xref_unambiguous', not ambiguous,
                 'incremental or hybrid xref is unsupported: ' + ', '.join(ambiguous)
                 if ambiguous else None):
        failure('AMBIGUOUS_XREF', 'incremental or hybrid xref is unsupported')
    if not check('no_parser_warnings', not parser_warnings,
                 f'{len(parser_warnings)} parser warning(s)' if parser_warnings else None):
        failure('PARSER_WARNING', 'the strict parser emitted warnings')
    if encrypted or ambiguous or parser_warnings:
        return finish(facts, failure_codes)

    try:
        catalog = reader.root_object
        root_ok = isinstance(catalog, classes['DictionaryObject']) \
            and str(catalog.get('/Type', '')) == '/Catalog'
    except Exception as error:
        detail = f'{type(error).__name__}: {error}'
        failure('DUPLICATE_KEY' if 'Multiple definitions' in detail else 'ROOT_CATALOG',
                f'root object is unavailable: {detail}')
        catalog = None
        root_ok = False
    if not check('root_catalog', root_ok,
                 'the trailer root is not a /Catalog dictionary' if not root_ok else None):
        failure('ROOT_CATALOG', 'the trailer root is not a /Catalog dictionary')
        return finish(facts, failure_codes)

    try:
        with warnings.catch_warnings(record=True) as caught_graph:
            warnings.simplefilter('always')
            graph = walk_graph(reader, classes, policy, facts)
            capture(caught_graph)
    except PdfCheckFailure as error:
        failure(error.code, error.detail)
        facts['parsed'].update({
            'objects': 0, 'xref_objects': 0, 'compressed_objects': 0,
            'free_entries': 0, 'xref_generations': 0,
        })
        return finish(facts, failure_codes)
    except Exception as error:
        failure('OBJECT_PARSE_ERROR', f'{type(error).__name__}: {error}')
        return finish(facts, failure_codes)
    parser_warnings = warning_handle[0].records + caught_warnings
    facts['parsed']['warnings'] = parser_warnings
    if parser_warnings:
        check('no_parser_warnings', False,
              f'{len(parser_warnings)} parser warning(s)')
        if 'PARSER_WARNING' not in failure_codes:
            failure('PARSER_WARNING', 'the strict parser emitted warnings')
    state = graph['state']
    hits = graph['hits']
    facts['parsed'].update({
        'objects': state['visited'],
        'xref_objects': state.get('xref_objects', 0),
        'compressed_objects': state.get('compressed_objects', 0),
        'free_entries': state.get('free_entries', 0),
        'xref_generations': state.get('xref_generations', 0),
        'max_depth_observed': state['max_depth_observed'],
        'object_errors': sorted(hits['object_errors'], key=lambda item: (
            item.get('object', -1), item.get('generation', -1), item.get('error', ''))),
        'pages': graph['page_count'],
    })
    expected_objects = state.get('xref_objects', 0) + state.get('compressed_objects', 0)
    facts['parsed']['expected_objects'] = expected_objects
    full_graph = (not hits['object_errors']
                  and state['visited'] == expected_objects)
    if not check('full_object_graph', full_graph,
                 f'{state["visited"]} of {expected_objects} xref/object-stream '
                 'objects inspected' if not full_graph else None):
        failure('OBJECT_GRAPH_INCOMPLETE',
                'not every xref/object-stream object was inspected')
    within_limits = (state['visited'] <= policy['semantics']['max_objects']
                     and state['max_depth_observed'] <= policy['semantics']['max_depth'])
    if not check('within_limits', within_limits,
                 'object or depth limit exceeded' if not within_limits else None):
        failure('OBJECT_LIMIT', 'object or depth limit exceeded')
    facts['dangerous'] = {
        'action_dictionaries': sorted(hits['action_dictionaries'],
                                      key=lambda item: (item['owner'], item['type'],
                                                        item['subtype'], item['keys'])),
        'forbidden_keys': sorted(hits['forbidden_keys'],
                                 key=lambda item: (item['key'], item['owner'])),
        'forbidden_object_values': sorted(
            hits['forbidden_object_values'],
            key=lambda item: (item['key'], item['value'], item['owner'])),
        'other_open_actions': sorted(hits['other_open_actions'],
                                     key=lambda item: (item['owner'], item['context'])),
        'unsupported_a_contexts': sorted(hits['unsupported_a_contexts'],
                                         key=lambda item: (item['owner'], item['keys'])),
        'invalid_a_values': sorted(hits['invalid_a_values'],
                                   key=lambda item: (item['owner'], item['keys'])),
    }
    if not check('no_object_errors', not hits['object_errors'],
                 f'{len(hits["object_errors"])} object(s) failed to parse'
                 if hits['object_errors'] else None):
        failure('OBJECT_PARSE_ERROR', 'at least one xref object failed to parse')
    if not check('no_action_dictionaries', not hits['action_dictionaries'],
                 f'{len(hits["action_dictionaries"])} action dictionary(ies)'
                 if hits['action_dictionaries'] else None):
        failure('ACTION_DICTIONARY', 'an action dictionary exists in the object graph')
    if not check('no_forbidden_keys', not hits['forbidden_keys'],
                 ', '.join(sorted({item['key'] for item in hits['forbidden_keys']}))
                 if hits['forbidden_keys'] else None):
        failure('FORBIDDEN_ACTION_KEY', 'a forbidden executable/attachment key exists')
    if not check('no_forbidden_object_values', not hits['forbidden_object_values'],
                 ', '.join(sorted({item['value'] for item in
                                   hits['forbidden_object_values']}))
                 if hits['forbidden_object_values'] else None):
        failure('FORBIDDEN_OBJECT_VALUE',
                'a forbidden attachment/media/action object value exists')
    if not check('no_other_open_actions', not hits['other_open_actions'],
                 f'{len(hits["other_open_actions"])} unexpected /OpenAction key(s)'
                 if hits['other_open_actions'] else None):
        failure('OPENACTION_UNEXPECTED', 'a /OpenAction key exists outside the catalog')
    if not check('no_unsupported_a_contexts', not hits['unsupported_a_contexts'],
                 f'{len(hits["unsupported_a_contexts"])} non-action /A context(s)'
                 if hits['unsupported_a_contexts'] else None):
        failure('UNSUPPORTED_A_CONTEXT', 'an unsupported /A context exists')
    if not check('no_invalid_a_values', not hits['invalid_a_values'],
                 f'{len(hits["invalid_a_values"])} invalid /A value(s)'
                 if hits['invalid_a_values'] else None):
        failure('INVALID_A_VALUE', 'a non-layout /A value exists')

    open_facts, problems = describe_open_action(
        graph['open_action_value'], classes, graph['page_refs'])
    facts['open_action'] = open_facts
    if not check('open_action_exact', not problems,
                 '; '.join(problems) if problems else None):
        failure('OPENACTION_SHAPE', '; '.join(problems))
    page_ok = bool(open_facts.get('page') and open_facts['page'].get('local_page')
                   and open_facts['page'].get('page_type') == '/Page')
    if not check('open_action_page_local', page_ok,
                 'the /OpenAction destination is not an actual page of this document'
                 if not page_ok else None):
        failure('OPENACTION_PAGE', 'the /OpenAction destination is not an actual page')
    facts['proof'] = {
        'safe_view': {
            'catalog_object': 'trailer /Root',
            'open_action_owner': 'catalog',
            'page_count': graph['page_count'],
            'destination_page': open_facts.get('page'),
            'action_dictionaries': 0,
        },
        'dangerous_view': {
            'objects_checked': state['visited'],
            'xref_objects_checked': state.get('xref_objects', 0),
            'compressed_objects_checked': state.get('compressed_objects', 0),
            'free_entries_skipped': state.get('free_entries', 0),
            'action_dictionary_count': len(hits['action_dictionaries']),
            'forbidden_key_count': len(hits['forbidden_keys']),
            'forbidden_object_value_count': len(hits['forbidden_object_values']),
            'other_open_action_count': len(hits['other_open_actions']),
            'unsupported_a_context_count': len(hits['unsupported_a_contexts']),
            'invalid_a_value_count': len(hits['invalid_a_values']),
        },
    }
    return finish(facts, failure_codes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    facts = {
        'schema_version': SCHEMA_VERSION,
        'check': CHECK_NAME,
        'status': 'FAIL',
        'checker': {
            'name': 'scripts/pdf_structural_check.py',
            'version': CHECKER_VERSION,
            'sha256': sha256_file(Path(__file__)),
        },
        'process_limits': observed_process_limits(),
        'failures': [],
    }
    try:
        if not re.match(r'^[0-9a-f]{64}$', str(args.expected_sha256)):
            raise PdfCheckFailure('INVALID_ARGUMENT', 'expected SHA256 is malformed')
        policy, checker_sha = load_policy(args.policy)
        produced, codes = check_pdf(args, policy, checker_sha)
        produced['failures'] = sorted(produced.get('failures', []),
                                      key=lambda item: (item['code'], item['detail']))
        produced['status'] = 'PASS' if not produced['failures'] else 'FAIL'
        facts = produced
    except PdfCheckFailure as error:
        facts['failures'].append({'code': error.code, 'detail': error.detail})
    except Exception as error:  # fail closed on any unexpected helper error
        facts['failures'].append({
            'code': 'INTERNAL_ERROR',
            'detail': f'{type(error).__name__}: {error}',
        })
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                      encoding='utf-8')
    summary = {
        'status': facts.get('status'),
        'check': CHECK_NAME,
        'pdf_sha256': facts.get('pdf', {}).get('sha256'),
        'failures': facts.get('failures', []),
        'out': str(output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if facts.get('status') == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
