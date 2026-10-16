#!/usr/bin/env python3
import argparse, json, importlib.util, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
specmod=load('specqa',ROOT/'core/qa/spec-check.py'); geom=load('geom',ROOT/'core/qa/pptx_geometry.py'); fonts=load('fonts',ROOT/'core/qa/font_check.py'); rend=load('render',ROOT/'skill/scripts/render_deck.py')
fidelity=load('fidelity',ROOT/'core/qa/data_fidelity.py')
spatial=load('spatial',ROOT/'core/qa/spatial.py');caps=load('capabilities',ROOT/'core/qa/capabilities.py')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('pptx'); ap.add_argument('--spec'); ap.add_argument('--out',required=True); ap.add_argument('--render-dir'); ap.add_argument('--analytics-input',help='Recompute analytical input and compare spec/native numeric evidence'); ap.add_argument('--visual-review',help='JSON review with pptx_sha256, reviewer, status=PASS, slides_reviewed and notes')
    a=ap.parse_args(); pptx=Path(a.pptx); checks={}
    if a.spec:
        data=json.loads(Path(a.spec).read_text(encoding='utf-8')); checks['spec']=specmod.result_for(data)
    if a.analytics_input:
        if not a.spec:ap.error('--analytics-input requires --spec')
        checks['data_fidelity']=fidelity.inspect(pptx,a.analytics_input,a.spec)
    checks['geometry']=geom.inspect(pptx); checks['fonts']=fonts.inspect(pptx)
    checks['spatial']=spatial.inspect(pptx)
    if checks['spatial'].get('fonts'):checks['fonts']['resolution']=checks['spatial']['fonts']
    if a.render_dir: checks['render']=rend.render(pptx,a.render_dir)
    else: checks['render']={'status':'NOT_RUN'}
    checks['visual_review']={'status':'NOT_RUN','note':'Requires an explicit review record bound to this PPTX hash.'}
    if a.visual_review:
        record=json.loads(Path(a.visual_review).read_text(encoding='utf-8'))
        digest=hashlib.sha256(pptx.read_bytes()).hexdigest()
        expected=len(checks['geometry']['slides'])
        valid=(record.get('pptx_sha256')==digest and record.get('status')=='PASS' and record.get('reviewer') and record.get('slides_reviewed')==list(range(1,expected+1)) and record.get('notes'))
        checks['visual_review']={'status':'PASS' if valid else 'FAIL','record':record,'note':'Reviewer attestation; not automated visual judgment.'}
    if checks['render']['status']=='PASS' and len(checks['render']['pages'])!=len(checks['geometry']['slides']):
        checks['render']['status']='FAIL'; checks['render']['reason']='Rendered page count does not match PPTX slide count'
    blocking=any(v.get('status')=='FAIL' for v in checks.values() if isinstance(v,dict)); notes=any(v.get('status') in {'PASS_WITH_NOTES','UNAVAILABLE','NOT_RUN'} for v in checks.values() if isinstance(v,dict))
    status='FAIL' if blocking else ('PASS_WITH_NOTES' if notes else 'PASS')
    capability=caps.detect()
    visual='UNAVAILABLE' if checks['render']['status']=='UNAVAILABLE' or capability['VISUAL_QA']=='UNAVAILABLE' else checks['visual_review']['status']
    result={'status':status,'VISUAL_QA':visual,'capabilities':capability,'pptx':str(pptx),'checks':checks}
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(2 if status=='FAIL' else 0)
if __name__=='__main__':main()
