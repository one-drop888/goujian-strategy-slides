#!/usr/bin/env python3
"""Create a best-effort V1 profile from extract_style.py output."""
import json, sys, re
from pathlib import Path
def clean(c,default): return c if isinstance(c,str) and re.fullmatch(r'[0-9A-Fa-f]{6}',c) else default
def main(report,out,pid='reference-derived'):
    d=json.loads(Path(report).read_text(encoding='utf-8')); colors=d.get('theme_colors',{}); fonts=d.get('fonts',{}); typo=d.get('typography',{})
    explicit=fonts.get('explicit_top') or []; cjk='Noto Sans CJK SC'; latin=fonts.get('minor_latin') or fonts.get('major_latin') or 'Noto Sans'
    for f in explicit:
        name=f['font'] if isinstance(f,dict) else f
        if any(x in name.lower() for x in ['yahei','noto sans cjk','pingfang','heiti','source han']):cjk=name;break
    profile={'id':pid,'name':'Reference Derived','purpose':'Best-effort profile extracted from a reference PPTX','canvas':'wide','background':clean(colors.get('lt1'),'FFFFFF'),'font':{'latin':latin,'cjk':cjk,'title_size':max(24,min(32,round(typo.get('font_size_p90',27)))),'body_size':max(16,min(22,round(typo.get('font_size_median',18))))},'colors':{'text':clean(colors.get('dk1'),'202124'),'muted':'6B7280','accent':clean(colors.get('accent1'),'1F5EFF'),'accent_soft':'EEF3FF','panel':'F5F7FA','line':'D9DEE7'},'style':{'action_titles':True,'density':'medium','cards':'low','chart_first':True},'reference_evidence':{'source':d.get('source'),'title_rect_median':d.get('layout',{}).get('title_rect_median'),'shape_count_median':d.get('layout',{}).get('shape_count_median')}}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(p)
if __name__=='__main__':
    if len(sys.argv)<3:raise SystemExit('usage: profile_from_reference.py style-report.json profile.json [profile-id]')
    main(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else 'reference-derived')
