#!/usr/bin/env python3
"""Safe-ish basic text editing for existing PPTX.
Replaces text inside DrawingML <a:t> nodes while preserving the surrounding run styling.
Does not reflow layouts or edit charts/images/SmartArt.
"""
import json, sys, zipfile, tempfile, shutil
from pathlib import Path
import xml.etree.ElementTree as ET
A='http://schemas.openxmlformats.org/drawingml/2006/main'
def main(src,replacements_path,out):
    src=Path(src);out=Path(out); repl=json.loads(Path(replacements_path).read_text(encoding='utf-8'))
    if src.resolve()==out.resolve():raise SystemExit('Input and output must differ; source is never overwritten')
    if not isinstance(repl,dict):raise SystemExit('replacements JSON must be an object: {"old":"new"}')
    if any(not k for k in repl):raise SystemExit('Empty replacement keys are not allowed')
    changed=0; out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(src,'r') as zin, zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data=zin.read(info.filename)
            if info.filename.startswith('ppt/slides/slide') and info.filename.endswith('.xml'):
                try:
                    root=ET.fromstring(data); local=0
                    for t in root.findall(f'.//{{{A}}}t'):
                        cur=t.text or ''; new=cur
                        for old,val in repl.items():
                            if old in new:new=new.replace(old,str(val))
                        if new!=cur:t.text=new;local+=1
                    if local:data=ET.tostring(root,encoding='utf-8',xml_declaration=True);changed+=local
                except ET.ParseError as e:raise ValueError(f'Invalid slide XML: {info.filename}') from e
            zout.writestr(info,data)
    print(json.dumps({'status':'PASS' if changed else 'NO_MATCH','output':str(out),'text_nodes_changed':changed},ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit('usage: edit_pptx_text.py input.pptx replacements.json output.pptx')
    main(*sys.argv[1:])
