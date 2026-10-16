"""Recompute a declared input and compare its spec and native serialized evidence."""
import json, math, subprocess, zipfile, posixpath
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
A='http://schemas.openxmlformats.org/drawingml/2006/main';C='http://schemas.openxmlformats.org/drawingml/2006/chart'
def inspect(pptx,input_path,spec_path):
    source=json.loads(Path(input_path).read_text(encoding='utf-8'))
    command="const fs=require('fs'),{analyze}=require('./core/analytics');process.stdout.write(JSON.stringify(analyze(JSON.parse(fs.readFileSync(0,'utf8')))));"
    result=subprocess.run(['node','-e',command],input=json.dumps(source),capture_output=True,text=True,cwd=ROOT,timeout=30)
    if result.returncode:return {'status':'FAIL','reason':result.stderr.strip()}
    reference=json.loads(result.stdout);spec=json.loads(Path(spec_path).read_text(encoding='utf-8'))
    if spec!=reference['spec']:return {'status':'FAIL','reason':'Presentation spec differs from recomputed analytical input'}
    issues=[];cells=0;values=0
    with zipfile.ZipFile(pptx) as z:
        for i,s in enumerate(spec['slides'],1):
            slide=ET.fromstring(z.read(f'ppt/slides/slide{i}.xml'));text=[n.text or '' for n in slide.iter(f'{{{A}}}t')]
            expected=[str(c) for row in s.get('rows',[]) for c in row]+[str(x['value']) for x in s.get('items',[]) if 'value' in x]
            for cell in expected:
                cells+=1
                if cell not in text:issues.append(f'Slide {i}: missing serialized value {cell}')
            series=(s.get('dashboard') or s).get('series',[])
            if series:
                rels=ET.fromstring(z.read(f'ppt/slides/_rels/slide{i}.xml.rels'))
                charts=[posixpath.normpath(posixpath.join('ppt/slides',r.attrib['Target'])).lstrip('/') for r in rels if r.attrib['Type'].endswith('/chart')]
                actual=[]
                for part in charts:
                    root=ET.fromstring(z.read(part))
                    for ser in root.iter(f'{{{C}}}ser'):
                        cache=ser.find(f'.//{{{C}}}numCache')
                        if cache is not None:actual.append([float(pt.find(f'{{{C}}}v').text) for pt in cache.findall(f'{{{C}}}pt')])
                expected_series=[x['values'] for x in series];values+=sum(map(len,expected_series))
                if len(actual)!=len(expected_series) or any(len(a)!=len(e) or any(not math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-10) for x,y in zip(a,e)) for a,e in zip(actual,expected_series)):issues.append(f'Slide {i}: native chart values differ from computed source')
    return {'status':'FAIL' if issues else 'PASS','input_sha256':reference['audit']['input_sha256'],'native_cells_checked':cells,'native_chart_values_checked':values,'issues':issues,'data_notes':reference['audit']['warnings'],'boundary':'Recomputes declared inputs and native cells/chart caches; does not authenticate source data or prove causality.'}
