#!/usr/bin/env python3
"""Extract reusable design evidence from a reference PPTX.
This is a best-effort structural/style extractor, not pixel-perfect cloning.
"""
import json, sys, zipfile, re, statistics
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
A='http://schemas.openxmlformats.org/drawingml/2006/main'; P='http://schemas.openxmlformats.org/presentationml/2006/main'; EMU=914400

def rect(el):
    x=el.find(f'.//{{{A}}}xfrm');
    if x is None:return None
    off=x.find(f'{{{A}}}off'); ext=x.find(f'{{{A}}}ext')
    if off is None or ext is None:return None
    try:return [int(off.attrib['x'])/EMU,int(off.attrib['y'])/EMU,int(ext.attrib['cx'])/EMU,int(ext.attrib['cy'])/EMU]
    except:return None

def text(el): return ''.join((t.text or '') for t in el.findall(f'.//{{{A}}}t')).strip()
def font_sizes(el):
    vals=[]
    for r in el.findall(f'.//{{{A}}}rPr')+el.findall(f'.//{{{A}}}defRPr'):
        if r.attrib.get('sz'):
            try: vals.append(int(r.attrib['sz'])/100)
            except:pass
    return vals

def main(src,out):
    src=Path(src); out=Path(out)
    if not src.exists():raise SystemExit(f'Missing: {src}')
    result={'source':str(src),'canvas':{},'fonts':{},'theme_colors':{},'typography':{},'layout':{},'slides':[],'notes':['Auto-extracted evidence; visually verify before production use.']}
    with zipfile.ZipFile(src) as z:
        names=set(z.namelist())
        if 'ppt/presentation.xml' in names:
            root=ET.fromstring(z.read('ppt/presentation.xml')); s=root.find(f'{{{P}}}sldSz')
            if s is not None:
                cx=int(s.attrib.get('cx',0));cy=int(s.attrib.get('cy',0));result['canvas']={'cx':cx,'cy':cy,'width_in':round(cx/EMU,3),'height_in':round(cy/EMU,3),'ratio':round(cx/cy,4) if cy else None}
        if 'ppt/theme/theme1.xml' in names:
            root=ET.fromstring(z.read('ppt/theme/theme1.xml'))
            major=root.find(f'.//{{{A}}}themeElements/{{{A}}}fontScheme/{{{A}}}majorFont/{{{A}}}latin');minor=root.find(f'.//{{{A}}}themeElements/{{{A}}}fontScheme/{{{A}}}minorFont/{{{A}}}latin')
            if major is not None:result['fonts']['major_latin']=major.attrib.get('typeface')
            if minor is not None:result['fonts']['minor_latin']=minor.attrib.get('typeface')
            cs=root.find(f'.//{{{A}}}themeElements/{{{A}}}clrScheme')
            if cs is not None:
                for child in list(cs):
                    key=child.tag.split('}')[-1]; val=None
                    for c in list(child): val=c.attrib.get('val') or c.attrib.get('lastClr');
                    if val:result['theme_colors'][key]=val
        fonts=[];sizes=[];title_positions=[];shape_counts=[];signatures=[]
        slide_names=sorted([n for n in names if re.match(r'ppt/slides/slide\d+\.xml$',n)],key=lambda x:int(re.search(r'(\d+)',Path(x).stem).group(1)))
        for idx,n in enumerate(slide_names,1):
            try:r=ET.fromstring(z.read(n))
            except:continue
            shapes=[]; text_boxes=[]
            for el in r.findall(f'.//{{{P}}}sp'):
                rr=rect(el);tt=text(el);fs=font_sizes(el);sizes.extend(fs)
                for tag in ['latin','ea']:
                    for fe in el.findall(f'.//{{{A}}}{tag}'):
                        if fe.attrib.get('typeface'):fonts.append(fe.attrib['typeface'])
                if rr:
                    shapes.append(rr)
                    if tt:text_boxes.append((rr,tt,max(fs) if fs else 0))
            # title candidate = highest font size, tie by top position
            title=None
            if text_boxes:
                title=sorted(text_boxes,key=lambda x:(-x[2],x[0][1]))[0]
                title_positions.append(title[0])
            shape_counts.append(len(shapes))
            norm=[]
            W=result['canvas'].get('width_in') or 13.333;H=result['canvas'].get('height_in') or 7.5
            for x,y,w,h in sorted(shapes,key=lambda q:(q[1],q[0]))[:20]:norm.append([round(x/W,1),round(y/H,1),round(w/W,1),round(h/H,1)])
            sig=json.dumps(norm,separators=(',',':'));signatures.append(sig)
            result['slides'].append({'slide':idx,'shape_count':len(shapes),'text_box_count':len(text_boxes),'title_candidate':title[1][:120] if title else None,'title_rect':[round(v,3) for v in title[0]] if title else None,'title_font_size':title[2] if title else None})
        if fonts:result['fonts']['explicit_top']=[{'font':x,'count':n} for x,n in Counter(fonts).most_common(10)]
        if sizes:
            result['typography']={'font_size_median':round(statistics.median(sizes),1),'font_size_p90':round(sorted(sizes)[int(.9*(len(sizes)-1))],1),'top_sizes':[{'size':x,'count':n} for x,n in Counter(round(v,1) for v in sizes).most_common(10)]}
        if title_positions:
            result['layout']['title_rect_median']=[round(statistics.median([r[i] for r in title_positions]),3) for i in range(4)]
        if shape_counts:result['layout']['shape_count_median']=round(statistics.median(shape_counts),1)
        common=Counter(signatures).most_common(8);result['layout']['repeated_layout_signatures']=[{'count':n,'signature':json.loads(sig)} for sig,n in common if n>1]
        result['layout']['slide_count']=len(slide_names)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(out)
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: extract_style.py input.pptx output.json')
    main(sys.argv[1],sys.argv[2])
