#!/usr/bin/env python3
import argparse, json, importlib.util, hashlib, shutil, subprocess, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SEMANTIC_QA=ROOT/'skill/scripts/semantic_qa.js'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
specmod=load('specqa',ROOT/'core/qa/spec-check.py'); geom=load('geom',ROOT/'core/qa/pptx_geometry.py'); fonts=load('fonts',ROOT/'core/qa/font_check.py'); rend=load('render',ROOT/'skill/scripts/render_deck.py')
fidelity=load('fidelity',ROOT/'core/qa/data_fidelity.py')
spatial=load('spatial',ROOT/'core/qa/spatial.py');caps=load('capabilities',ROOT/'core/qa/capabilities.py')

def semantic_qa(pptx,spec,out,scene=None,profile=None,plan=None):
    node=shutil.which('node')
    if not node:
        return {'status':'UNAVAILABLE','reason':'node executable is unavailable; semantic checks were not run.'}
    report=out.parent/(out.stem+'.semantic-qa.json')
    cmd=[node,str(SEMANTIC_QA),'--pptx',str(pptx),'--spec',str(spec),'--out',str(report),'--repo-root',str(ROOT),'--spec-dir',str(spec.parent)]
    if scene:cmd+=['--scene',str(scene)]
    if profile:cmd+=['--profile',str(profile)]
    if plan:cmd+=['--plan',str(plan)]
    try:
        proc=subprocess.run(cmd,cwd=str(ROOT),capture_output=True,text=True,timeout=180,check=False)
    except (OSError,subprocess.TimeoutExpired) as error:
        return {'status':'FAIL','reason':f'local semantic QA runner failed: {error}','report':str(report)}
    if proc.returncode not in (0,1):
        return {'status':'FAIL','reason':'semantic QA runner failed; an older report cannot establish success','exit_code':proc.returncode,'report':str(report)}
    if not report.exists():
        detail=(proc.stderr or proc.stdout or 'no report written').strip().splitlines()[-1:]
        return {'status':'FAIL','reason':'semantic QA runner produced no report','detail':detail,'exit_code':proc.returncode,'report':str(report)}
    try:
        result=json.loads(report.read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:
        return {'status':'FAIL','reason':f'semantic QA report could not be read: {error}','exit_code':proc.returncode,'report':str(report)}
    if result.get('status')=='FAIL' and proc.returncode!=1:
        result['runner_exit_code']=proc.returncode
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('pptx'); ap.add_argument('--spec'); ap.add_argument('--out',required=True); ap.add_argument('--render-dir'); ap.add_argument('--analytics-input',help='Recompute analytical input and compare spec/native numeric evidence'); ap.add_argument('--visual-review',help='JSON review with pptx_sha256, reviewer, status=PASS, slides_reviewed and notes'); ap.add_argument('--scene',help='Build scene JSON used to hash-bind the semantic report'); ap.add_argument('--profile',help='Profile id used for the build; re-derives the visual encoding'); ap.add_argument('--plan',help='Reasoning plan JSON used for narrative structure checks')
    a=ap.parse_args(); pptx=Path(a.pptx); checks={}
    inputs=[pptx,Path(str(pptx)+'.scene.json')]+[Path(value) for value in (a.spec,a.analytics_input,a.visual_review,a.scene,a.plan) if value]
    if a.spec:
        source=json.loads(Path(a.spec).read_text(encoding='utf-8'))
        inputs += [Path(a.spec).parent/asset['path'] for asset in source.get('assets',[]) if isinstance(asset,dict) and 'path' in asset]
    if a.profile and Path(a.profile).is_file():inputs.append(Path(a.profile))
    outputs=[Path(a.out)]
    if a.spec:outputs.append(Path(a.out).with_name(Path(a.out).stem+'.semantic-qa.json'))
    def same(left,right):
        return left.resolve()==right.resolve() or (left.exists() and right.exists() and left.samefile(right))
    for output in outputs:
        if any(same(output,source) for source in inputs):ap.error('QA output must not overwrite an input or its scene')
    if len(outputs)>1 and same(outputs[0],outputs[1]):ap.error('QA outputs must be distinct')
    if a.render_dir:
        render=Path(a.render_dir).resolve()
        for source in inputs:
            if source.resolve().parent==render and (source.name in ('deck.pdf','montage.png') or re.fullmatch(r'slide-\d+\.png',source.name)):
                ap.error('Render artifacts would overwrite a protected input')
    if a.spec:
        data=json.loads(Path(a.spec).read_text(encoding='utf-8')); checks['spec']=specmod.result_for(data)
    for name in ('scene','profile','plan'):
        if getattr(a,name) and not a.spec:ap.error(f'--{name} requires --spec')
    if a.analytics_input:
        if not a.spec:ap.error('--analytics-input requires --spec')
        checks['data_fidelity']=fidelity.inspect(pptx,a.analytics_input,a.spec)
    if a.spec:
        checks['semantic_qa']=semantic_qa(pptx,Path(a.spec),Path(a.out),scene=Path(a.scene) if a.scene else None,profile=a.profile,plan=Path(a.plan) if a.plan else None)
    else:
        checks['semantic_qa']={'status':'NOT_RUN','reason':'No source spec was supplied; semantic fidelity cannot be re-derived.'}
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
