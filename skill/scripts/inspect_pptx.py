#!/usr/bin/env python3
"""Inspect an existing PPTX into a machine-readable slide/shape/text report."""
import hashlib, json, sys, zipfile, re, posixpath
from pathlib import Path
import xml.etree.ElementTree as ET
P='http://schemas.openxmlformats.org/presentationml/2006/main'; A='http://schemas.openxmlformats.org/drawingml/2006/main'; EMU=914400
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
C='http://schemas.openxmlformats.org/drawingml/2006/chart'

def text(el): return ''.join((x.text or '') for x in el.findall(f'.//{{{A}}}t')).strip()
def rect(el):
    xf=el.find(f'.//{{{A}}}xfrm')
    if xf is None:return None
    off=xf.find(f'{{{A}}}off'); ext=xf.find(f'{{{A}}}ext')
    if off is None or ext is None:return None
    try:return [round(int(off.attrib['x'])/EMU,3),round(int(off.attrib['y'])/EMU,3),round(int(ext.attrib['cx'])/EMU,3),round(int(ext.attrib['cy'])/EMU,3)]
    except:return None

def inspect(path,asset_dir=None):
    digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    out={'source':str(path),'source_sha256':digest,'slides':[],'assets':[],'limitations':['SmartArt, grouped transforms and master/layout reconstruction remain PARTIAL. Proximity relationships are candidates requiring agent review. OCR is not performed; picture text remains embedded.']}
    assets={};unresolved=[];total=0
    if asset_dir:Path(asset_dir).mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        names=z.namelist(); slide_names=sorted([n for n in names if re.match(r'ppt/slides/slide\d+\.xml$',n)],key=lambda x:int(re.search(r'(\d+)',Path(x).stem).group(1)))
        for i,n in enumerate(slide_names,1):
            root=ET.fromstring(z.read(n)); shapes=[]; full=[]
            relpart=posixpath.join(posixpath.dirname(n),'_rels',posixpath.basename(n)+'.rels')
            rels={}
            if relpart in names:
                for r in ET.fromstring(z.read(relpart)):
                    if r.attrib.get('TargetMode')=='External':continue
                    target=r.attrib.get('Target','')
                    resolved=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(n),target))
                    rels[r.attrib['Id']]=resolved
            def visit(parent,in_group=False):
                nonlocal total
                for el in parent:
                    tag=el.tag.split('}')[-1]
                    if tag not in {'sp','pic','graphicFrame','grpSp'}:continue
                    total+=1;nv=el.find(f'.//{{{P}}}cNvPr');sid=nv.attrib.get('id',str(total)) if nv is not None else str(total)
                    obj={'id':f's{i}-shape{sid}','rect':rect(el),'text':text(el) if tag!='grpSp' else '', 'source_mapping':{'pptx_sha256':digest,'slide_part':n,'shape_id':sid},'coordinate_status':'PARTIAL_GROUP_LOCAL' if in_group else 'SLIDE'}
                    if tag=='grpSp':obj['kind']='group';obj['status']='PARTIAL'
                    elif tag=='pic':
                        obj['kind']='picture';obj['provenance']={'kind':'image_text','render_mode':'embedded','confidence':1,'source_region':{'x':0,'y':0,'w':1,'h':1}}
                        blip=el.find(f'.//{{{A}}}blip');target=rels.get(blip.attrib.get(f'{{{R}}}embed')) if blip is not None else None
                        if target and target in names:
                            data=z.read(target);key=hashlib.sha256(data).hexdigest();aid='asset-'+key[:16]
                            obj['asset_id']=aid;obj['provenance']['source_asset']=aid
                            if aid not in assets:
                                suffix=Path(target).suffix.lower();suffix=suffix if suffix in {'.png','.jpg','.jpeg','.webp','.gif','.emf','.wmf','.svg'} else '.bin'
                                file=Path(asset_dir)/(aid+suffix) if asset_dir else None
                                if file:
                                    if file.exists() and file.read_bytes()!=data:raise ValueError('Asset output already exists with different content')
                                    if not file.exists():file.write_bytes(data)
                                assets[aid]={'id':aid,'source_part':target,'sha256':key,'path':str(file) if file else None,'source_mapping':obj['source_mapping'],'type':'UNCLASSIFIED','status':'EXTRACTED' if file else 'IDENTIFIED'}
                            crop=el.find(f'.//{{{A}}}srcRect');obj['source_crop']=dict(crop.attrib) if crop is not None else None
                        else:unresolved.append(obj['id']);obj['status']='UNRESOLVED_ASSET'
                    elif el.find(f'.//{{{A}}}tbl') is not None:
                        obj['kind']='table';obj['provenance']={'kind':'source_data','render_mode':'editable'}
                        obj['rows']=[[text(cell) for cell in row.findall(f'{{{A}}}tc')] for row in el.findall(f'.//{{{A}}}tr')]
                    elif el.find(f'.//{{{C}}}chart') is not None:
                        obj['kind']='chart';ref=el.find(f'.//{{{C}}}chart');target=rels.get(ref.attrib.get(f'{{{R}}}id'))
                        obj['source_part']=target;obj['provenance']={'kind':'source_data','render_mode':'editable'}
                        obj['series']=[]
                        if target in names:
                            chart=ET.fromstring(z.read(target))
                            for ser in chart.findall(f'.//{{{C}}}ser'):
                                vals=[v.text for v in ser.findall(f'.//{{{C}}}val//{{{C}}}pt/{{{C}}}v')]
                                labels=[v.text for v in ser.findall(f'.//{{{C}}}cat//{{{C}}}pt/{{{C}}}v')]
                                obj['series'].append({'labels':labels,'values':vals,'recovery':'CACHED_DATA_PARTIAL'})
                    else:obj['kind']='native_text' if obj['text'] else 'shape';obj['provenance']={'kind':'native_text' if obj['text'] else 'generated_annotation','render_mode':'editable'}
                    if obj['text']:full.append(obj['text'])
                    shapes.append(obj)
                    if tag=='grpSp':visit(el,True)
            tree=root.find(f'.//{{{P}}}spTree')
            if tree is not None:visit(tree)
            candidates=[]
            for picture in (x for x in shapes if x['kind']=='picture' and x['rect']):
                x,y,w,h=picture['rect']
                for label in (o for o in shapes if o['kind']=='native_text' and o['rect']):
                    lx,ly,lw,lh=label['rect'];gap=max(0,ly-y-h,y-ly-lh)
                    if gap<.7 and min(x+w,lx+lw)>max(x,lx):candidates.append({'from':label['id'],'to':picture['id'],'type':'caption_of','status':'CANDIDATE','confidence':.5})
            out['slides'].append({'slide':i,'text':'\n'.join(full),'shapes':shapes,'relationships':candidates,'master_background_candidates':[p for p in rels.values() if '/slideLayouts/' in p]})
        out['master_parts']=[n for n in names if re.match(r'ppt/slideMasters/slideMaster\d+\.xml$',n)]
    out['assets']=list(assets.values());out['fidelity']={'source_coverage':{'identified_objects':total,'mapped_objects':sum(len(s['shapes']) for s in out['slides'])},'duplicate_assets':sum(1 for s in out['slides'] for o in s['shapes'] if o['kind']=='picture')-len(assets),'unresolved_assets':unresolved,'detached_annotation':'UNKNOWN_REQUIRES_SEMANTIC_REVIEW','semantic_occlusion':'REQUIRES_SCENE_OR_VISUAL_REVIEW'}
    return out

def main():
    if len(sys.argv)<3:raise SystemExit('usage: inspect_pptx.py input.pptx output.json [asset-output-directory]')
    if Path(sys.argv[1]).resolve()==Path(sys.argv[2]).resolve():raise SystemExit('Inspection output must differ from source PPTX')
    r=inspect(sys.argv[1],sys.argv[3] if len(sys.argv)>3 else None); p=Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(p)
if __name__=='__main__':main()
