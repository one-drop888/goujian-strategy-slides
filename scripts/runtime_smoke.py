#!/usr/bin/env python3
"""Installed-runtime smoke test.

Runs representative production commands from the installed runtime payload. It is
not the full development suite: the complete `tests/` suite stays in the source
package. Optional image/font/build/render steps are reported as NOT_RUN on a
Pillow-free core tier instead of being silently treated as passing.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.qa import data_fidelity, secure_deps

TEMP_PREFIX = 'goujian-runtime-smoke-'
PROBE = 'scripts/probe_env.py'
SPEC_EXAMPLES = 'skill/examples'
ANALYTICS = 'skill/analytics/business-performance.json'
ANALYTICS_SPEC = 'skill/examples/executive-business-review.json'
PLAN = 'skill/reasoning/fixtures/q4-six-actions/plan.json'
MULTIMODAL = 'skill/examples/multimodal-integration.json'
ASSET = 'skill/examples/assets/showroom-illustration.png'
OPTIONAL_STEPS = (
    'plan:compile',
    'font:measure',
    'image:prepare',
    'build:multimodal',
    'qa:multimodal',
    'render:multimodal',
)


class SmokeError(RuntimeError):
    pass


def run(args, stdin=None, timeout=300):
    return subprocess.run(args, cwd=str(ROOT), input=stdin, capture_output=True,
                          text=True, timeout=timeout, shell=False)


def tail(text, limit=700):
    lines = [line for line in str(text or '').strip().splitlines() if line.strip()]
    return '\n'.join(lines[-6:])[:limit]


def add(steps, step_id, status, detail, required=True):
    steps.append({'id': step_id, 'status': status, 'required': required, 'detail': detail})


def require(proc, label):
    if proc.returncode != 0:
        raise SmokeError(f'{label} failed (exit {proc.returncode}): {tail(proc.stderr or proc.stdout)}')
    return proc


def pptx_parts(path):
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=('auto', 'core', 'secure'), default='auto',
                        help='auto selects secure when Python>=3.11 and Pillow>=13 are available')
    parser.add_argument('--json', action='store_true', help='print machine-readable JSON only')
    args = parser.parse_args(argv)

    image_status = secure_deps.secure_image_status()
    secure_available = image_status['status'] == 'AVAILABLE'
    if args.tier == 'secure' and not secure_available:
        result = {'status': 'FAIL', 'tier': 'secure', 'error': image_status['reason'],
                  'steps': [], 'visual_qa': 'NOT_RUN'}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
              f'FAIL: secure tier requested but unavailable: {image_status["reason"]}')
        return 2
    tier = 'secure' if args.tier == 'auto' and secure_available else ('core' if args.tier == 'auto' else args.tier)

    steps = []
    failures = []
    with tempfile.TemporaryDirectory(prefix=TEMP_PREFIX) as tmp:
        tmp = Path(tmp)

        try:
            proc = require(run([sys.executable, 'tests/validate_examples.py'], timeout=600), 'example spec validation')
            add(steps, 'spec:examples', 'PASS', tail(proc.stdout, 200))
            proc = require(run(['node', 'skill/scripts/validate_plan.js', PLAN, '--json'], timeout=120), 'plan validation')
            plan = json.loads(proc.stdout)
            if plan.get('status') != 'PASS':
                raise SmokeError(f'plan validation status {plan.get("status")}')
            add(steps, 'plan:validate', 'PASS', f'plan {plan.get("plan_id")} valid')

            plot = tmp / 'business.pptx'
            require(run(['node', 'scripts/analyze.js', ANALYTICS, str(plot)], timeout=240), 'analytics build')
            parts = pptx_parts(plot)
            charts = [name for name in parts if name.startswith('ppt/charts/chart')]
            workbooks = [name for name in parts if name.startswith('ppt/embeddings/')]
            if not charts or not workbooks:
                raise SmokeError(f'native chart/workbook missing: charts={len(charts)} workbooks={len(workbooks)}')
            add(steps, 'analysis:business', 'PASS', f'{len(charts)} native chart parts, {len(workbooks)} embedded workbook(s)')

            fidelity = data_fidelity.inspect(plot, ROOT / ANALYTICS, ROOT / ANALYTICS_SPEC)
            if fidelity.get('status') != 'PASS' or not fidelity.get('native_chart_values_checked'):
                raise SmokeError(f'native data fidelity did not pass: {json.dumps(fidelity, ensure_ascii=False)[:400]}')
            add(steps, 'native:data-fidelity', 'PASS',
                f'{fidelity.get("native_cells_checked")} cells and {fidelity.get("native_chart_values_checked")} chart values checked')

            if tier == 'secure':
                qa_path = tmp / 'qa-analytics.json'
                require(run([sys.executable, 'skill/scripts/quality_gate.py', str(plot), '--spec', ANALYTICS_SPEC,
                             '--analytics-input', ANALYTICS, '--out', str(qa_path)], timeout=300), 'analytics QA')
                qa = json.loads(qa_path.read_text(encoding='utf-8'))
                if qa.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
                    raise SmokeError(f'analytics QA status {qa.get("status")}')
                if (qa.get('checks') or {}).get('data_fidelity', {}).get('status') != 'PASS':
                    raise SmokeError('analytics QA data fidelity did not pass')
                if qa.get('VISUAL_QA') != 'NOT_RUN':
                    raise SmokeError('runtime smoke must not claim a visual pass')
                add(steps, 'qa:analytics', qa['status'], 'full structural/semantic/native QA passed; VISUAL_QA=NOT_RUN')
            else:
                add(steps, 'qa:analytics', 'NOT_RUN',
                    'full QA includes Pillow glyph-based spatial checks; core tier validated native data fidelity separately',
                    required=False)
        except (SmokeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
            failures.append(str(error))
            add(steps, 'core-checks', 'FAIL', str(error))

        if tier == 'secure':
            try:
                measurement = run([sys.executable, 'core/style/measure_text.py'],
                                  stdin=json.dumps({'text': '构见 ABC', 'font': 'Noto Sans CJK SC', 'size': 24}),
                                  timeout=60)
                require(measurement, 'Pillow font measurement')
                metrics = json.loads(measurement.stdout)
                if not metrics.get('advances') or not Path(metrics.get('font_file', '')).is_file():
                    raise SmokeError('font measurement did not return glyph advances and a real font file')
                add(steps, 'font:measure', 'PASS',
                    f'Pillow glyph advances for {len(metrics["advances"])} characters from {metrics["font_file"]}')

                prepared = tmp / 'prepared.png'
                image = run([sys.executable, 'core/renderer/prepare_asset.py'],
                            stdin=json.dumps({'asset': {'type': 'illustration'}, 'path': str(ROOT / ASSET),
                                              'output': str(prepared), 'ratio': 16 / 9,
                                              'crop': {'x': 0, 'y': 0, 'w': 1, 'h': 1}}),
                            timeout=60)
                require(image, 'raster asset preparation')
                if not prepared.is_file() or prepared.stat().st_size == 0:
                    raise SmokeError('prepared image was not written')
                add(steps, 'image:prepare', 'PASS', f'prepared raster {prepared.stat().st_size} bytes')

                deck = tmp / 'multimodal.pptx'
                spec = tmp / 'multimodal.spec.json'
                proc = require(run(['node', 'skill/scripts/compile_plan.js', PLAN,
                                    '--out', str(tmp / 'plan.pptx'), '--spec-out', str(tmp / 'plan.spec.json'), '--json'],
                                   timeout=240), 'plan compilation')
                compiled = json.loads(proc.stdout)
                for key in ('outPath', 'specOut', 'reasoning', 'scene'):
                    if not Path(compiled.get(key, '')).is_file():
                        raise SmokeError(f'plan compilation did not produce {key}')
                add(steps, 'plan:compile', 'PASS', 'reasoning plan compiled with native deck and sidecars')

                proc = require(run(['node', 'skill/scripts/build_deck.js', MULTIMODAL, str(deck)], timeout=300), 'multimodal build')
                parts = pptx_parts(deck)
                media = [name for name in parts if name.startswith('ppt/media/')]
                if not media:
                    raise SmokeError('multimodal build embedded no media')
                add(steps, 'build:multimodal', 'PASS', f'{len(media)} embedded media part(s)')

                qa_path = tmp / 'qa-multimodal.json'
                require(run([sys.executable, 'skill/scripts/quality_gate.py', str(deck), '--spec', MULTIMODAL,
                             '--out', str(qa_path)], timeout=300), 'multimodal QA')
                qa = json.loads(qa_path.read_text(encoding='utf-8'))
                if qa.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
                    raise SmokeError(f'multimodal QA status {qa.get("status")}')
                if qa.get('VISUAL_QA') != 'NOT_RUN':
                    raise SmokeError('runtime smoke must not claim a visual pass')
                add(steps, 'qa:multimodal', qa['status'], 'structural/semantic QA passed; VISUAL_QA=NOT_RUN')

                render_dir = tmp / 'render'
                render = run([sys.executable, 'skill/scripts/render_deck.py', str(deck), str(render_dir)], timeout=180)
                require(render, 'multimodal render')
                if render.returncode == 0:
                    rendered = json.loads(render.stdout)
                    if rendered.get('status') == 'UNAVAILABLE':
                        add(steps, 'render:multimodal', 'UNAVAILABLE', rendered.get('reason', 'renderer unavailable'),
                            required=False)
                    elif rendered.get('status') == 'PASS' and rendered.get('pages'):
                        add(steps, 'render:multimodal', 'PASS', f'{len(rendered["pages"])} rendered pages')
                    else:
                        raise SmokeError(f'unexpected render status {rendered.get("status")}')
            except (SmokeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
                failures.append(str(error))
                add(steps, 'secure-check', 'FAIL', str(error))
        else:
            reason = ('core tier selected: Pillow secure image stack is not available/selected; '
                      'image preparation, Pillow font measurement, deck build and render are NOT_RUN')
            for step_id in OPTIONAL_STEPS:
                add(steps, step_id, 'NOT_RUN', reason, required=False)

    status = 'FAIL' if failures else 'PASS'
    result = {
        'status': status,
        'tier': tier,
        'secure_image_status': image_status,
        'steps': steps,
        'not_run_optional_images': [step['id'] for step in steps if step['status'] == 'NOT_RUN'],
        'visual_qa': 'NOT_RUN',
        'boundary': ('Installed-runtime production smoke only. It validates examples, plan/analytics, native chart/workbook '
                     'evidence, QA and representative builds; it is not the full development test suite and does not '
                     'claim visual or company-platform approval.'),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for step in steps:
            print(f"{step['status']:10} {step['id']}: {step['detail']}")
        print(f"runtime smoke: {status} ({tier} tier); VISUAL_QA=NOT_RUN")
        for failure in failures:
            print(f'FAIL: {failure}', file=sys.stderr)
    return 2 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
