#!/usr/bin/env python3
"""Inspect an existing PPTX into a machine-readable slide/shape/text report."""
import json, sys, zipfile, re
from pathlib import Path
import xml.etree.ElementTree as ET
P='http://schemas.openxmlformats.org/presentationml/2006/main'; A='http://schemas.openxmlformats.org/drawingml/2006/main'; EMU=914400

def text(el): return ''.join((x.text or '') for x in el.findall(f'.//{{{A}}}t')).strip()
def rect(el):
    xf=el.find(f'.//{{{A}}}xfrm')
    if xf is None:return None
    off=xf.find(f'{{{A}}}off'); ext=xf.find(f'{{{A}}}ext')
    if off is None or ext is None:return None
    try:return [round(int(off.attrib['x'])/EMU,3),round(int(off.attrib['y'])/EMU,3),round(int(ext.attrib['cx'])/EMU,3),round(int(ext.attrib['cy'])/EMU,3)]
    except:return None

def inspect(path):
    out={'source':str(path),'slides':[]}
    with zipfile.ZipFile(path) as z:
        names=z.namelist(); slide_names=sorted([n for n in names if re.match(r'ppt/slides/slide\d+\.xml$',n)],key=lambda x:int(re.search(r'(\d+)',Path(x).stem).group(1)))
        for i,n in enumerate(slide_names,1):
            root=ET.fromstring(z.read(n)); shapes=[]; full=[]
            for el in root.findall(f'.//{{{P}}}sp'):
                t=text(el); r=rect(el)
                if t: full.append(t)
                if t or r: shapes.append({'text':t,'rect':r})
            out['slides'].append({'slide':i,'text':'\n'.join(full),'shapes':shapes})
    return out

def main():
    if len(sys.argv)<3:raise SystemExit('usage: inspect_pptx.py input.pptx output.json')
    r=inspect(sys.argv[1]); p=Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(p)
if __name__=='__main__':main()
