#!/usr/bin/env python3
"""Create a best-effort V1 profile from extract_style.py output.
Native paint evidence is preferred; contrast corrections are recorded rather
than reproducing unreadable reference colors.
"""
import json, sys, re
from pathlib import Path

def clean(c,default):
    return c.upper() if isinstance(c,str) and re.fullmatch(r'[0-9A-Fa-f]{6}',c) else default
def rgb(value):
    value=clean(value,'000000')
    return [int(value[i:i+2],16) for i in (0,2,4)]
def hexed(values):
    return ''.join(f'{max(0,min(255,round(v))):02X}' for v in values)
def mix(a,b,amount):
    x,y=rgb(a),rgb(b)
    return hexed([x[i]+(y[i]-x[i])*amount for i in range(3)])
def luminance(value):
    def channel(v):
        v/=255
        return v/12.92 if v<=.03928 else ((v+.055)/1.055)**2.4
    r,g,b=rgb(value)
    return .2126*channel(r)+.7152*channel(g)+.0722*channel(b)
def contrast(a,b):
    la,lb=luminance(a),luminance(b)
    return (max(la,lb)+.05)/(min(la,lb)+.05)
def ensure(foreground,background,minimum):
    if contrast(foreground,background)>=minimum:return foreground,False
    target='000000' if contrast('000000',background)>=contrast('FFFFFF',background) else 'FFFFFF'
    low,high,best=0.0,1.0,target
    for _ in range(24):
        mid=(low+high)/2
        candidate=mix(foreground,target,mid)
        if contrast(candidate,background)>=minimum:best=candidate;high=mid
        else:low=mid
    if contrast(best,background)<minimum:best=target
    return best,True

def top_color(entries):
    return entries[0]['color'] if entries else None

def main(report,out,pid='reference-derived'):
    d=json.loads(Path(report).read_text(encoding='utf-8'))
    colors=d.get('theme_colors',{}); fonts=d.get('fonts',{}); typo=d.get('typography',{}); native=d.get('native_evidence',{})
    explicit=fonts.get('explicit_top') or []; cjk='Noto Sans CJK SC'; latin=fonts.get('minor_latin') or fonts.get('major_latin') or 'Noto Sans'
    for f in explicit:
        name=f['font'] if isinstance(f,dict) else f
        if any(x in name.lower() for x in ['yahei','noto sans cjk','pingfang','heiti','source han']):cjk=name;break
    background=clean(top_color(native.get('background_candidates',[])),clean(colors.get('lt1'),'FFFFFF'))
    text_candidates=[item['color'] for item in native.get('title_colors',[])]+[item['color'] for item in native.get('text_colors',[])]+[clean(colors.get('dk1'),'202124')]
    text=clean(text_candidates[0] if text_candidates else None,'202124')
    corrections=[]
    for candidate in text_candidates:
        candidate=clean(candidate,text)
        if contrast(candidate,background)>=4.5:text=candidate;break
    text,adjusted=ensure(text,background,4.5)
    if adjusted:corrections.append({'role':'text','reason':'reference text color did not meet 4.5:1 on the extracted background'})
    accent=clean(top_color(native.get('chart_series_colors',[])),clean(colors.get('accent1'),'1F5EFF'))
    accent,adjusted=ensure(accent,background,3.0)
    if adjusted:corrections.append({'role':'accent','reason':'reference accent did not meet 3:1 on the extracted background'})
    muted=ensure(mix(text,background,.45),background,4.5)[0]
    panel=mix(background,text,.06);line=mix(background,text,.20);accent_soft=mix(background,accent,.12)
    evidence=dict(d.get('layout',{}))
    images=native.get('images',[])
    profile={'id':pid,'name':'Reference Derived','purpose':'Best-effort profile extracted from native PPTX paint and layout evidence','canvas':'wide',
             'background':background,
             'font':{'latin':latin,'cjk':cjk,'title_size':max(24,min(32,round(typo.get('font_size_p90',27)))),'body_size':max(16,min(22,round(typo.get('font_size_median',18))))},
             'colors':{'text':text,'muted':muted,'accent':accent,'accent_soft':accent_soft,'panel':panel,'line':line},
             'style':{'action_titles':True,'density':'medium','cards':'low','chart_first':True},
             'reference_evidence':{'source':d.get('source'),'title_rect_median':d.get('layout',{}).get('title_rect_median'),
                                   'shape_count_median':d.get('layout',{}).get('shape_count_median'),
                                   'background_candidates':native.get('background_candidates',[]),
                                   'text_colors':native.get('text_colors',[]),
                                   'title_colors':native.get('title_colors',[]),
                                   'chart_series_colors':native.get('chart_series_colors',[]),
                                   'chart_label_colors':native.get('chart_label_colors',[]),
                                   'image_count':len(images),
                                   'density':native.get('density',{}),
                                   'contrast_corrections':corrections,
                                   'theme_color_warning':'Theme XML accent alone may differ from native chart paint; chart paint statistics were preferred.',
                                   'limitations':native.get('limitations',[]) or ['Reference extraction is PARTIAL; review native images, masters and SmartArt.']}}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(p)
if __name__=='__main__':
    if len(sys.argv)<3:raise SystemExit('usage: profile_from_reference.py style-report.json profile.json [profile-id]')
    main(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else 'reference-derived')
