#!/usr/bin/env python3
import json, sys, zipfile, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import Counter
A='http://schemas.openxmlformats.org/drawingml/2006/main'

def used_fonts(path):
    fonts=[]
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.startswith(('ppt/slides/slide','ppt/charts/chart')) and n.endswith('.xml'):
                try:r=ET.fromstring(z.read(n))
                except Exception:continue
                for tag in ['latin','ea','cs']:
                    for el in r.findall(f'.//{{{A}}}{tag}'):
                        if el.attrib.get('typeface') and not el.attrib['typeface'].startswith('+'): fonts.append(el.attrib['typeface'])
        if 'ppt/theme/theme1.xml' in z.namelist():
            r=ET.fromstring(z.read('ppt/theme/theme1.xml'))
            for el in r.findall(f'.//{{{A}}}latin')+r.findall(f'.//{{{A}}}ea'):
                if el.attrib.get('typeface') and not el.attrib['typeface'].startswith('+'): fonts.append(el.attrib['typeface'])
    return Counter(fonts)

def system_families():
    try: out=subprocess.check_output(['fc-list',':','family'],text=True,stderr=subprocess.DEVNULL)
    except Exception:return None
    fam=set()
    for line in out.splitlines():
        for part in line.split(','): fam.add(part.strip().lower())
    return fam

def inspect(path):
    used=used_fonts(path); sysf=system_families(); missing=[]
    if sysf is not None:
        for f in used:
            if f.lower() not in sysf: missing.append(f)
    return {'status':'UNAVAILABLE' if sysf is None else ('PASS_WITH_NOTES' if missing else 'PASS'),'used':[{'font':k,'occurrences':v} for k,v in used.most_common()], 'missing_on_this_machine':missing,'note':'Missing fonts indicate possible substitution on this machine; they do not prove the recipient environment lacks the fonts.'}

def main():
    if len(sys.argv)<2: raise SystemExit('usage: font_check.py input.pptx [report.json]')
    r=inspect(sys.argv[1]); print(json.dumps(r,ensure_ascii=False,indent=2))
    if len(sys.argv)>2:
        p=Path(sys.argv[2]); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
