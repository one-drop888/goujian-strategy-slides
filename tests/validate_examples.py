#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
examples=[p for p in sorted((ROOT/'skill/examples').glob('*.json')) if p.name!='manifest.json']
fail=[]
for p in examples:
    r=subprocess.run(['python3','skill/scripts/validate_spec.py',str(p)],cwd=ROOT,text=True,capture_output=True)
    if r.returncode!=0: fail.append((p.name,r.stdout+r.stderr))
if fail:
    for name,msg in fail: print('FAIL',name,msg)
    raise SystemExit(2)
print(f'PASS: {len(examples)} example specs validated')
