"""Report available validation levels without treating tool presence or missing rendering as visual approval."""
import importlib.util, json, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
JS_REQUIRED=('ajv','jszip','pptxgenjs')

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

def detect(probe=None,python_ready=None):
    which=probe.which if probe is not None else shutil.which
    find_spec=(probe.find_spec if probe is not None and hasattr(probe,'find_spec') else importlib.util.find_spec)
    tools={name:which(name) for name in ['libreoffice','soffice','pdftoppm','fc-list','fc-match']}
    try: tools['pillow']=bool(find_spec('PIL'))
    except (ImportError,ValueError): tools['pillow']=False
    python_ok=sys.version_info>=(3,9) if python_ready is None else bool(python_ready)
    spec_ok=js_ready(probe)
    native=bool(python_ok and (tools['libreoffice'] or tools['soffice']) and tools['pdftoppm'] and tools['pillow'])
    levels={'0_spec':'AVAILABLE' if spec_ok and python_ok else 'UNAVAILABLE',
            '1_geometry_spatial':'AVAILABLE' if python_ok else 'UNAVAILABLE',
            '2_pptx_inspection':'AVAILABLE' if python_ok else 'UNAVAILABLE',
            '3_native_render':'AVAILABLE' if native else 'UNAVAILABLE',
            '4_vision_review':'REQUIRES_REVIEWER','5_repair_rerender':'REQUIRES_AGENT'}
    ladder={
        'SPEC_ONLY':{'status':'AVAILABLE' if spec_ok and python_ok else 'UNAVAILABLE',
                     'note':'Schema and spec validation run locally with Node, AJV and the Python validator.' if spec_ok and python_ok else 'Requires Node.js, installed AJV/JS deps and Python >= 3.9.',
                     'recovery':None if spec_ok and python_ok else 'Install Node.js 18+ and run npm run bootstrap (or python3 scripts/bootstrap.py).'},
        'STRUCTURAL_QA':{'status':'AVAILABLE' if python_ok else 'UNAVAILABLE','note':'Geometry, spatial and text-fit checks use Python stdlib; font inventory is UNAVAILABLE without fc-list.'},
        'PPTX_INSPECTION':{'status':'AVAILABLE' if python_ok else 'UNAVAILABLE','note':'ZIP/XML inspection requires only Python stdlib.'},
        'NATIVE_RENDER':{'status':'AVAILABLE' if native else 'UNAVAILABLE',
                         'note':'Dependencies found; render execution is not proven by detection.' if native else 'Python, LibreOffice/soffice, pdftoppm and Pillow are all required.',
                         'recovery':None if native else 'Run npm run bootstrap and install LibreOffice plus Poppler.'},
        'VISUAL_REVIEW':{'status':'REQUIRES_REVIEWER','note':'Never set to PASS automatically; requires a hash-bound reviewer record.'},
        'VISUAL_REPAIR':{'status':'REQUIRES_AGENT','note':'Repair requires agent action and a fresh review.'},
    }
    return {'tools':tools,'levels':levels,'ladder':ladder,'VISUAL_QA':'NOT_RUN' if native else 'UNAVAILABLE'}

if __name__=='__main__':print(json.dumps(detect(),indent=2))
