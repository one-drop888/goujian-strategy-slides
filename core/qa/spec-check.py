#!/usr/bin/env python3
import json, sys, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TOPIC_TITLES={x.lower() for x in ['背景','现状','分析','总结','问题','方案','规划','计划','进展','数据','结果','策略','营销','销售','项目','渠道','用户','竞品','风险','结论','background','overview','analysis','strategy','plan','update','results','sales','marketing','risk']}
ACTION_WORDS=['增长','下降','高于','低于','转向','应','需要','导致','驱动','集中','改善','差距','风险','机会','优先','increase','decline','should','drive','gap','risk','opportun','shift']
DESCRIPTIVE_OK={'cover','section','agenda','research-method','table'}

def load_ids():
    a=json.loads((ROOT/'skill/archetypes/registry.json').read_text(encoding='utf-8'))
    s=json.loads((ROOT/'skill/storylines/registry.json').read_text(encoding='utf-8'))
    p=[x.parent.name for x in (ROOT/'skill/profiles').glob('*/profile.json')]
    return {x['id'] for x in a['archetypes']}|{'statement','kpi','chart','action'}, {x['id'] for x in s['storylines']}, set(p)

def title_score(title):
    t=(title or '').strip(); score=0
    if len(t)>=10: score+=1
    if any(c in t for c in '，,:：；;'): score+=1
    lo=t.lower()
    if any(w.lower() in lo for w in ACTION_WORDS): score+=2
    if lo.rstrip('：:.。') in TOPIC_TITLES or len(t)<=4: score-=2
    return score

def check(data):
    valid_types, valid_storylines, valid_profiles=load_ids(); issues=[]
    try:
        proc=subprocess.run(['node',str(ROOT/'core/schema/validate.js')],input=json.dumps(data,ensure_ascii=False),text=True,capture_output=True)
        errors=json.loads(proc.stdout)['errors']
    except (OSError,ValueError,KeyError) as e:
        return [('ERROR','schema','Executable schema validation unavailable: '+str(e))]
    if errors: return [('ERROR','schema',e) for e in errors]
    reg=json.loads((ROOT/'skill/archetypes/registry.json').read_text(encoding='utf-8'))
    archetypes={a['id']:a for a in reg['archetypes']}
    slides=data.get('slides') or []
    if not data.get('title'): issues.append(('ERROR','title','Deck title is required'))
    if not slides: issues.append(('ERROR','slides','At least one slide is required')); return issues
    if data.get('storyline') and data['storyline'] not in valid_storylines: issues.append(('WARN','storyline',f"Unknown storyline: {data['storyline']}"))
    if data.get('profile') and data['profile'] not in valid_profiles: issues.append(('WARN','profile',f"Profile is not built-in: {data['profile']}"))
    if len(slides)>35: issues.append(('WARN','slides',f'Deck has {len(slides)} slides; verify every page earns its place'))

    comps=[]; action_scores=[]
    for i,s in enumerate(slides):
        t=s.get('type'); path=f'slides[{i}]'
        if t not in valid_types: issues.append(('ERROR',path+'.type',f'Unsupported semantic type: {t}')); continue
        title=(s.get('title') or '').strip()
        if t not in {'cover','section'} and not title: issues.append(('ERROR',path+'.title','Content slide title is required'))
        if len(title)>100: issues.append(('WARN',path+'.title',f'Long title: {len(title)} chars'))
        score=title_score(title); action_scores.append(score)
        if t not in DESCRIPTIVE_OK and title and score<0: issues.append(('WARN',path+'.title','Topic-label title; prefer an evidence-backed action title when possible'))
        meta=archetypes.get(t,{})
        if meta.get('status')=='PARTIAL': issues.append(('WARN',path,meta['limitation']))
        comp=s.get('composition') or meta.get('composition') or t; comps.append(comp)

        items=s.get('items') or []
        if t in {'kpi','kpi-dashboard','big-number','baseline'} and len(items)>6: issues.append(('WARN',path+'.items','More than 6 KPI items require explicit slide splitting'))
        if t in {'comparison','benchmark','segmentation','regional-performance','scenario-analysis'} and len(s.get('columns') or [])>4: issues.append(('WARN',path+'.columns','Comparison has more than 4 columns'))
        if t in {'chart','trend','line','bar','column','area','combo','scatter','bubble','histogram','waterfall','bridge','variance','cost-structure','cohort','distribution'}:
            if not (s.get('series') or []): issues.append(('ERROR',path+'.series','Data/chart archetype requires series'))
            if not s.get('source') and not s.get('evidence'): issues.append(('WARN',path,'Decision-relevant chart has no explicit source/evidence metadata'))
            if not s.get('unit'): issues.append(('NOTE',path+'.unit','Chart has no explicit unit'))
            if not s.get('period'): issues.append(('NOTE',path+'.period','Chart has no explicit period'))
        if t in {'evidence-quote','case-study'} and not (s.get('attribution') or s.get('source') or s.get('evidence')):
            issues.append(('WARN',path,'Quoted/case evidence has no attribution or source'))
        if t=='research-method':
            labels=' '.join(str(x.get('label','')) for x in items if isinstance(x,dict)).lower()
            if not any(k in labels for k in ['sample','样本','method','方法','period','周期']): issues.append(('NOTE',path,'Research method page should make sample/method/period visible'))
        for ev_i,ev in enumerate(s.get('evidence') or []):
            if ev.get('kind')=='assumption' and not ev.get('note'): issues.append(('NOTE',f'{path}.evidence[{ev_i}]','Assumption should state its basis/limitation'))

    # Anti-template heuristic: repeated same declared type 4+ times consecutively.
    run=1
    for i in range(1,len(slides)):
        if comps[i]==comps[i-1]: run+=1
        else: run=1
        if run==4 and slides[i].get('type') not in {'table','scorecard'}:
            series=[s.get('analytical_series') for s in slides[i-3:i+1]]
            intentional=all(series) and all(s==series[0] for s in series[1:])
            if not intentional:issues.append(('WARN',f'slides[{i-3}:{i+1}]','4 consecutive slides use the same composition without shared analytical_series id/metrics/task'))
    content_scores=[x for x in action_scores if x is not None]
    if len(content_scores)>=5 and sum(1 for x in content_scores if x<0)/len(content_scores)>.45:
        issues.append(('WARN','slides','Many titles are topic labels; deck may read like a document outline rather than a management argument'))
    return issues

def result_for(data):
    issues=check(data)
    return {'status':'FAIL' if any(x[0]=='ERROR' for x in issues) else ('PASS_WITH_NOTES' if issues else 'PASS'),'slides':len(data.get('slides') or []),'issues':[{'severity':a,'path':b,'message':c} for a,b,c in issues]}

def main(path, report=None):
    p=Path(path); data=json.loads(p.read_text(encoding='utf-8')); result=result_for(data)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if report:
        rp=Path(report); rp.parent.mkdir(parents=True,exist_ok=True); rp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(2 if result['status']=='FAIL' else 0)
if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit('usage: spec-check.py deck.json [report.json]')
    main(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
