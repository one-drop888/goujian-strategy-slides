"""Report available validation levels without treating tool presence or missing rendering as visual approval."""
import importlib.util, json, shutil

def detect(probe=None):
    which=probe.which if probe is not None else shutil.which
    find_spec=(probe.find_spec if probe is not None and hasattr(probe,'find_spec') else importlib.util.find_spec)
    tools={name:which(name) for name in ['libreoffice','soffice','pdftoppm','fc-list','fc-match']}
    try: tools['pillow']=bool(find_spec('PIL'))
    except (ImportError,ValueError): tools['pillow']=False
    native=bool((tools['libreoffice'] or tools['soffice']) and tools['pdftoppm'] and tools['pillow'])
    levels={'0_spec':'AVAILABLE','1_geometry_spatial':'AVAILABLE','2_pptx_inspection':'AVAILABLE',
            '3_native_render':'AVAILABLE' if native else 'UNAVAILABLE',
            '4_vision_review':'REQUIRES_REVIEWER','5_repair_rerender':'REQUIRES_AGENT'}
    ladder={
        'SPEC_ONLY':{'status':'AVAILABLE','note':'Schema and spec validation run locally.'},
        'STRUCTURAL_QA':{'status':'AVAILABLE','note':'Geometry, spatial and text-fit checks use Python stdlib; font inventory is UNAVAILABLE without fc-list.'},
        'PPTX_INSPECTION':{'status':'AVAILABLE','note':'ZIP/XML inspection requires only Python stdlib.'},
        'NATIVE_RENDER':{'status':'AVAILABLE' if native else 'UNAVAILABLE',
                         'note':'Dependencies found; render execution is not proven by detection.' if native else 'LibreOffice/soffice, pdftoppm and Pillow are all required.',
                         'recovery':None if native else 'Run npm run bootstrap and install LibreOffice plus Poppler.'},
        'VISUAL_REVIEW':{'status':'REQUIRES_REVIEWER','note':'Never set to PASS automatically; requires a hash-bound reviewer record.'},
        'VISUAL_REPAIR':{'status':'REQUIRES_AGENT','note':'Repair requires agent action and a fresh review.'},
    }
    return {'tools':tools,'levels':levels,'ladder':ladder,'VISUAL_QA':'NOT_RUN' if native else 'UNAVAILABLE'}

if __name__=='__main__':print(json.dumps(detect(),indent=2))
