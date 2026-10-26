"""Report available validation levels without treating tool presence or missing rendering as visual approval."""
import importlib.util, json, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
JS_REQUIRED=('ajv','jszip','pptxgenjs')

def _load_secure_deps():
    path=ROOT/'core/qa/secure_deps.py'
    spec=importlib.util.spec_from_file_location('goujian_secure_deps',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

secure_deps=_load_secure_deps()

def js_ready(probe=None):
    which=probe.which if probe is not None and hasattr(probe,'which') else shutil.which
    if not which('node'):return False
    for name in JS_REQUIRED:
        version=None
        if probe is not None and hasattr(probe,'package_version'):version=probe.package_version(name)
        else:
            try:version=json.loads((ROOT/'node_modules'/name/'package.json').read_text(encoding='utf-8')).get('version')
            except (OSError,ValueError):version=None
        if not version:return False
    return True

def _python_version(probe=None):
    if probe is not None and hasattr(probe,'python_version'):
        try:return tuple(probe.python_version())[:3]
        except TypeError:pass
    return tuple(sys.version_info[:3])

def _pillow_version(probe=None):
    if probe is not None and hasattr(probe,'pillow_version'):
        try:value=probe.pillow_version()
        except Exception:return None
        return value[0] if isinstance(value,tuple) else value
    return secure_deps.pillow_version()[0]

def detect(probe=None,python_ready=None,secure_status=None):
    which=probe.which if probe is not None else shutil.which
    find_spec=(probe.find_spec if probe is not None and hasattr(probe,'find_spec') else importlib.util.find_spec)
    tools={name:which(name) for name in ['libreoffice','soffice','pdftoppm','fc-list','fc-match','fc-list']}
    try: tools['pillow']=bool(find_spec('PIL'))
    except (ImportError,ValueError): tools['pillow']=False
    python=_python_version(probe)
    python_ok=python>=(3,9) if python_ready is None else bool(python_ready)
    spec_ok=js_ready(probe)
    secure=secure_status or secure_deps.secure_image_status(python=python,pillow=_pillow_version(probe))
    render_tools=bool((tools['libreoffice'] or tools['soffice']) and tools['pdftoppm'])
    native=bool(python_ok and render_tools and secure['status']=='AVAILABLE')
    levels={'0_spec':'AVAILABLE' if spec_ok and python_ok else 'UNAVAILABLE',
            '1_geometry_spatial':'AVAILABLE' if python_ok else 'UNAVAILABLE',
            '2_pptx_inspection':'AVAILABLE' if python_ok else 'UNAVAILABLE',
            '3_native_render':'AVAILABLE' if native else 'UNAVAILABLE',
            '4_vision_review':'REQUIRES_REVIEWER','5_repair_rerender':'REQUIRES_AGENT'}
    if native:
        render_note='Dependencies found; render execution is not proven by detection.'
    elif secure['status']=='INSECURE':
        render_note=f'Native render is unavailable for untrusted assets: {secure["reason"]}.'
    elif not render_tools:
        render_note='LibreOffice/soffice and pdftoppm are required for native rendering.'
    elif not python_ok:
        render_note='Python >= 3.9 is required for local QA.'
    else:
        render_note=secure['reason']+'.'
    ladder={
        'SPEC_ONLY':{'status':'AVAILABLE' if spec_ok and python_ok else 'UNAVAILABLE',
                     'note':'Schema and spec validation run locally with Node, AJV and the Python validator.' if spec_ok and python_ok else 'Requires Node.js, installed AJV/JS deps and Python >= 3.9.',
                     'recovery':None if spec_ok and python_ok else 'Install Node.js 18+ and run npm run bootstrap (or python3 scripts/bootstrap.py).'},
        'STRUCTURAL_QA':{'status':'AVAILABLE' if python_ok else 'UNAVAILABLE','note':'Geometry, spatial and text-fit checks use Python stdlib; font inventory is UNAVAILABLE without fc-list.'},
        'PPTX_INSPECTION':{'status':'AVAILABLE' if python_ok else 'UNAVAILABLE','note':'ZIP/XML inspection requires only Python stdlib.'},
        'SECURE_IMAGE_RENDER':{'status':secure['status'],'note':secure['reason']+'; untrusted image processing and full render require this tier.',
                               'recovery':None if secure['status']=='AVAILABLE' else f'Use Python >= {secure["min_python"]} and install requirements-render.txt (Pillow {secure["min_pillow"]}).'},
        'NATIVE_RENDER':{'status':'AVAILABLE' if native else 'UNAVAILABLE','note':render_note,
                         'recovery':None if native else 'Run npm run bootstrap under Python >= 3.11, then install LibreOffice plus Poppler.'},
        'VISUAL_REVIEW':{'status':'REQUIRES_REVIEWER','note':'Never set to PASS automatically; requires a hash-bound reviewer record.'},
        'VISUAL_REPAIR':{'status':'REQUIRES_AGENT','note':'Repair requires agent action and a fresh review.'},
    }
    return {'tools':tools,'levels':levels,'ladder':ladder,'secure_image':secure,
            'core_tier':{'status':'AVAILABLE' if python_ok else 'UNAVAILABLE','python':secure_deps.version_text(python),
                         'requires':'Python >= 3.9; no Pillow needed for spec/geometry/inspection'},
            'VISUAL_QA':'NOT_RUN' if native else 'UNAVAILABLE'}

if __name__=='__main__':print(json.dumps(detect(),indent=2))
