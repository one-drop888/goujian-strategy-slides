#!/usr/bin/env python3
"""Best-effort PPTX geometry audit.
Detects objects outside slide bounds and unintended peer intersections. Containment overlaps
(e.g. text inside a card) are ignored because they are usually intentional.
"""
import json, sys, zipfile, re
from pathlib import Path
import xml.etree.ElementTree as ET

P='http://schemas.openxmlformats.org/presentationml/2006/main'; A='http://schemas.openxmlformats.org/drawingml/2006/main'
EMU=914400

def slide_size(z):
    root=ET.fromstring(z.read('ppt/presentation.xml')); s=root.find(f'{{{P}}}sldSz')
    return (int(s.attrib.get('cx',12192000))/EMU,int(s.attrib.get('cy',6858000))/EMU)

def name_of(el):
    for tag in [f'.//{{{P}}}cNvPr',f'.//{{{A}}}cNvPr']:
        n=el.find(tag)
        if n is not None: return n.attrib.get('name','object')
    return 'object'

def rect_of(el):
    xfrm=el.find(f'.//{{{A}}}xfrm')
    if xfrm is None: xfrm=el.find(f'.//{{{P}}}xfrm')
    if xfrm is None: return None
    off=xfrm.find(f'{{{A}}}off'); ext=xfrm.find(f'{{{A}}}ext')
    if off is None or ext is None: return None
    try:return tuple(int(v)/EMU for v in [off.attrib['x'],off.attrib['y'],ext.attrib['cx'],ext.attrib['cy']])
    except Exception:return None

def overlap(a,b):
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    ix=max(0,min(ax+aw,bx+bw)-max(ax,bx)); iy=max(0,min(ay+ah,by+bh)-max(ay,by)); area=ix*iy
    return area, min(aw*ah,bw*bh)

def contains(a,b,t=.03):
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    return bx>=ax-t and by>=ay-t and bx+bw<=ax+aw+t and by+bh<=ay+ah+t

def inspect(path):
    path=Path(path); issues=[]; summary=[]
    with zipfile.ZipFile(path) as z:
        W,H=slide_size(z)
        slides=sorted([n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$',n)],key=lambda x:int(re.search(r'(\d+)',Path(x).stem).group(1)))
        for si,n in enumerate(slides,1):
            root=ET.fromstring(z.read(n)); objs=[]
            if root.findall(f'.//{{{P}}}grpSp'):
                issues.append({'severity':'WARN','slide':si,'kind':'group-transform','message':'Grouped shapes require visual review; local coordinates are not absolute.'})
            for kind,tag in [('shape',f'.//{{{P}}}sp'),('graphic',f'.//{{{P}}}graphicFrame'),('picture',f'.//{{{P}}}pic')]:
                for el in root.findall(tag):
                    r=rect_of(el)
                    if not r: continue
                    name=name_of(el); objs.append((name,kind,r))
                    x,y,w,h=r
                    if x < -.02 or y < -.02 or x+w > W+.02 or y+h > H+.02:
                        issues.append({'severity':'ERROR','slide':si,'kind':'overflow','object':name,'rect':[round(v,3) for v in r],'message':'Object extends outside slide bounds'})
            peer=[]
            for i in range(len(objs)):
                for j in range(i+1,len(objs)):
                    n1,k1,r1=objs[i]; n2,k2,r2=objs[j]
                    # Ignore tiny lines, containment, and background-sized objects.
                    if min(r1[2],r1[3],r2[2],r2[3]) < .08: continue
                    if contains(r1,r2) or contains(r2,r1): continue
                    area,small=overlap(r1,r2)
                    if small and area/small>.28 and area>.08:
                        peer.append((n1,n2,area/small))
            # cap noisy reports per slide
            for n1,n2,ratio in sorted(peer,key=lambda x:-x[2])[:6]:
                issues.append({'severity':'WARN','slide':si,'kind':'peer-overlap','objects':[n1,n2],'ratio':round(ratio,3),'message':'Peer objects overlap substantially; visually verify'})
            summary.append({'slide':si,'objects':len(objs),'peer_overlap_candidates':len(peer)})
    status='FAIL' if any(x['severity']=='ERROR' for x in issues) else ('PASS_WITH_NOTES' if issues else 'PASS')
    return {'status':status,'limitations':['Bounding-box checks do not prove text fit, glyph coverage, or chart-label readability. Grouped/rotated shapes require visual review.'],'slide_size_inches':[W,H],'slides':summary,'issues':issues}

def main():
    if len(sys.argv)<2: raise SystemExit('usage: pptx_geometry.py input.pptx [report.json]')
    r=inspect(sys.argv[1]); print(json.dumps(r,ensure_ascii=False,indent=2))
    if len(sys.argv)>2:
        p=Path(sys.argv[2]); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(2 if r['status']=='FAIL' else 0)
if __name__=='__main__': main()
