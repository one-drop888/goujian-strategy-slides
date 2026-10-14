#!/usr/bin/env python3
"""Build and audit every published example. Visual review remains an explicit step."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(args):
    result=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--render',action='store_true');ap.add_argument('--out',default='out/benchmarks')
    a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);results=[]
    archetypes=json.loads((ROOT/'skill/archetypes/registry.json').read_text())['archetypes']
    mapping={x['id']:x['composition'] for x in archetypes}
    for p in sorted((ROOT/'skill/examples').glob('*.json')):
        if p.name=='manifest.json':continue
        d=json.loads(p.read_text(encoding='utf-8'));pptx=out/(p.stem+'.pptx');report=out/(p.stem+'-qa.json')
        try:
            run(['node','skill/scripts/build_deck.js',str(p),str(pptx)])
            cmd=[sys.executable,'skill/scripts/quality_gate.py',str(pptx),'--spec',str(p),'--out',str(report)]
            if a.render:cmd+=['--render-dir',str(out/p.stem)]
            run(cmd);qa=json.loads(report.read_text())
            result={'scenario':p.stem,'slides':len(d['slides']),'profile':d['profile'],'storyline':d['storyline'],
                    'compositions':list(dict.fromkeys(s.get('composition') or mapping[s['type']] for s in d['slides'])),
                    'pptx_sha256':hashlib.sha256(pptx.read_bytes()).hexdigest(),
                    'status':qa['status'],'checks':{k:v['status'] for k,v in qa['checks'].items()}}
        except (RuntimeError,OSError,ValueError) as e:result={'scenario':p.stem,'status':'FAIL','reason':str(e)}
        results.append(result);print(p.stem,result['status'],flush=True)
    (out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(2 if any(r['status']=='FAIL' for r in results) else 0)
if __name__=='__main__':main()
