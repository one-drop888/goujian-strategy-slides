"""Report available validation levels without treating missing rendering as visual approval."""
import importlib.util, json, shutil

def detect():
    tools={name:shutil.which(name) for name in ['libreoffice','soffice','pdftoppm','fc-list']}
    tools['pillow']=bool(importlib.util.find_spec('PIL'))
    native=bool((tools['libreoffice'] or tools['soffice']) and tools['pdftoppm'] and tools['pillow'])
    return {'tools':tools,'levels':{'0_spec':'AVAILABLE','1_geometry_spatial':'AVAILABLE','2_pptx_inspection':'AVAILABLE','3_native_render':'AVAILABLE' if native else 'UNAVAILABLE','4_vision_review':'REQUIRES_REVIEWER','5_repair_rerender':'REQUIRES_AGENT'},'VISUAL_QA':'NOT_RUN' if native else 'UNAVAILABLE'}

if __name__=='__main__':print(json.dumps(detect(),indent=2))
