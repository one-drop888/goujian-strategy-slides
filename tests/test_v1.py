#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(rel):return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def run(*args):return subprocess.run(args,cwd=ROOT,text=True,capture_output=True)

def test_library_scale():
    assert load('skill/storylines/registry.json')['count'] >= 20
    assert load('skill/archetypes/registry.json')['count'] >= 60
    assert 15 <= load('skill/compositions/registry.json')['count'] <= 25
    assert len(list((ROOT/'skill/profiles').glob('*/profile.json'))) >= 10
    assert load('skill/templates/registry.json')['count'] >= 10

def test_registry_integrity():
    arch=load('skill/archetypes/registry.json')['archetypes']; comps={x['id']:x for x in load('skill/compositions/registry.json')['compositions']}
    ids=[x['id'] for x in arch]; assert len(ids)==len(set(ids))
    for x in arch:
        assert x['composition'] in comps, x
        assert comps[x['composition']]['renderer']==x['renderer'], x

def test_profile_contract():
    for p in (ROOT/'skill/profiles').glob('*/profile.json'):
        d=json.loads(p.read_text(encoding='utf-8')); assert d['id']==p.parent.name; assert d['colors']['accent']; assert d['font']['cjk']

def test_unified_product():
    r=(ROOT/'README.md').read_text(encoding='utf-8'); a=(ROOT/'docs/architecture/ARCHITECTURE.md').read_text(encoding='utf-8')
    assert 'one product' in r.lower(); assert 'one product' in a.lower(); assert not (ROOT/'adapters/company-platform').exists()
    assert (ROOT/'SKILL.md').exists()

def test_example_build_and_geometry():
    out=ROOT/'out/test-v1.pptx'; out.parent.mkdir(exist_ok=True)
    p=run('node','skill/scripts/build_deck.js','skill/examples/executive-review.json',str(out)); assert p.returncode==0,p.stdout+p.stderr; assert out.exists() and out.stat().st_size>10000
    q=run('python3','core/qa/pptx_geometry.py',str(out)); assert q.returncode==0,q.stdout+q.stderr
    data=json.loads(q.stdout); assert data['status'] in {'PASS','PASS_WITH_NOTES'}

if __name__=='__main__':
    test_library_scale(); test_registry_integrity(); test_profile_contract(); test_unified_product(); test_example_build_and_geometry(); print('PASS: V1 architecture and build smoke tests')
