"""Semantic/spatial checks against a hash-bound record of actual native draw calls."""
import hashlib, json, re, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import importlib.util
_s=importlib.util.spec_from_file_location('text_fit',Path(__file__).with_name('text_fit.py'));_fit=importlib.util.module_from_spec(_s);_s.loader.exec_module(_fit)

P='http://schemas.openxmlformats.org/presentationml/2006/main'

def intersection(a,b):
    return max(0,min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x']))*max(0,min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y']))

def audit(graph):
    issues=[];metrics={'source_coverage':None,'duplicate_content':0,'unresolved_assets':0,'detached_annotation':0,'semantic_occlusion':0}
    def issue(si,code,objects,message,severity='ERROR'):
        issues.append({'slide':si,'code':code,'objects':objects,'severity':severity,'message':message})
    declared=set(graph.get('declared_assets',[]));used={a['id'] for a in graph.get('assets',[])}
    if declared:metrics['source_coverage']=len(used&declared)/len(declared)
    metrics['unresolved_assets']=len(declared-used)
    if declared-used:issue(0,'UNUSED_SOURCE_ASSET',sorted(declared-used),'Declared source assets are not used; review source coverage','WARN')
    for slide in graph['slides']:
        si=slide['slide'];nodes=slide['nodes'];ids={n['id'] for n in nodes};rels=slide.get('relationships',[])
        linked={(r['from'],r['to'],r['type']) for r in rels}
        if len(ids)!=len(nodes):issue(si,'DUPLICATE_ID',[],'Scene node IDs must be unique')
        for r in rels:
            if r['from'] not in ids or r['to'] not in ids:issue(si,'UNRESOLVED_RELATION',[r['from'],r['to']],'Relation points to a missing rendered object')
        title=slide.get('title') or {}
        if len(title.get('lines',[]))==2:
            issue(si,'TITLE_WRAP',['claim'],'Two-line title allowed after measured alternatives','NOTE')
            widths=title.get('line_widths',[])
            if widths and min(widths)<max(widths)*.35:issue(si,'POOR_TITLE_WRAP',['claim'],'Short orphan title line by measured glyph width','WARN')
        if title.get('measurement')=='conservative-approximation':issue(si,'TEXT_MEASUREMENT_APPROXIMATE',['claim'],'Font advance unavailable; render review required','WARN')
        for n in nodes:
            b=n['bbox'];role=n['role']
            if role not in {'background','decoration','divider','source'} and (b['x']<.3 or b['y']<.25 or b['x']+b['w']>13.033 or b['y']+b['h']>7.12):issue(si,'SAFE_AREA_VIOLATION',[n['id']],'Informative object enters the slide safety margin')
            if n.get('contrast',{}).get('ratio',21)<4.5:issue(si,'LOW_CONTRAST',[n['id']],'Local text contrast below 4.5:1')
            if role=='subtitle' and n.get('font_size',0)>=title.get('size',100):issue(si,'HIERARCHY_WEAK',[n['id']],'Subtitle should be smaller than the title','WARN')
            if n.get('kind')=='text' and n.get('text') and n.get('font_family'):
                height=_fit.estimated_height(n['text'],n['font_family'],n.get('font_size',18),n.get('bold',False),b['w'])
                if height and height>b['h']*1.08:issue(si,'TEXT_FIT_RISK',[n['id']],'Estimated glyph-based text height exceeds the actual native box; render review or splitting required','WARN')
                if height:
                    offset=(b['h']-height)/2 if n.get('valign') in {'mid','middle'} else b['h']-height if n.get('valign')=='bottom' else 0
                    n['_ink_bbox']={**b,'y':b['y']+offset,'h':height}
            if role=='annotation' and not any(r['from']==n['id'] and r['type']=='annotates' for r in rels):
                metrics['detached_annotation']+=1;issue(si,'DETACHED_ANNOTATION',[n['id']],'Annotation has no source/evidence binding')
            p=n.get('provenance',{})
            if p.get('source_asset') and p['source_asset'] not in used:issue(si,'DETACHED_IMAGE_TEXT',[n['id']],'Image-derived content refers to an absent source asset')
            if n.get('kind')=='text' and p.get('kind')=='image_text' and p.get('render_mode')=='embedded':issue(si,'FALSE_EDITABLE_TEXT',[n['id']],'Embedded image text must not be represented as a native text box')
            if role in {'claim','subtitle'}:
                for rule in (r for r in nodes if r['role']=='divider'):
                    gap=rule['bbox']['y']-b['y']-b['h']
                    if gap+1e-5<title.get('gap',.14):issue(si,'TITLE_DIVIDER_COLLISION' if role=='claim' else 'SUBTITLE_DIVIDER_COLLISION',[n['id'],rule['id']],'Text/divider visual gap is below the typography scale')
            if n.get('kind')=='image' and n.get('asset_type') in {'document_screenshot','chart_screenshot','table_screenshot','ui_screenshot'} and b['w']<3:issue(si,'EVIDENCE_READABILITY',[n['id']],'Evidence displayed narrowly; inspect text at native slide size','WARN')
        evidence=[n for n in nodes if n['role']=='evidence']
        for n in nodes:
            if n['role']=='claim' and any(e['z']<n['z'] for e in evidence):issue(si,'READING_ORDER_CONFLICT',[n['id']],'Native reading order puts evidence before claim','WARN')
        for i,a in enumerate(nodes):
            for b in nodes[i+1:]:
                ra,rb=a['role'],b['role'];ba,bb=a['bbox'],b['bbox']
                if a['kind']=='text' and b['kind']=='text' and a.get('text') and a.get('text')==b.get('text') and ra==rb and intersection(ba,bb)>0:
                    metrics['duplicate_content']+=1;issue(si,'DUPLICATE_CONTENT',[a['id'],b['id']],'Identical text with same role overlaps in the same source context')
                # Caption/annotation overlaps require explicit relations; background overlap is intentional.
                if 'background' in {ra,rb} or 'decoration' in {ra,rb}:continue
                pair={a['kind'],b['kind']}
                area=intersection(ba,bb);small=min(ba['w']*ba['h'],bb['w']*bb['h'])
                if a['kind']==b['kind']=='text' and a.get('text') and b.get('text') and area>.015 and min(ba['y']+ba['h'],bb['y']+bb['h'])-max(ba['y'],bb['y'])>.015:
                    issue(si,'TEXT_TEXT_COLLISION',[a['id'],b['id']],'Native informative text boxes overlap; separate value, explanation and label regions')
                annotation=((a['id'],b['id'],'annotates') in linked or (b['id'],a['id'],'annotates') in linked)
                if area>.02 and small and area/small>.04 and not annotation and ('image' in pair or ra==rb=='evidence' and pair&{'chart','table'}):
                    metrics['semantic_occlusion']+=1;issue(si,'SEMANTIC_OCCLUSION',[a['id'],b['id']],'Evidence/image/text regions intersect without an intentional relationship')
                    if b['z']>a['z']:issue(si,'Z_ORDER_CONFLICT',[a['id'],b['id']],'Later native object obstructs earlier informative content')
                for text,rule in [(a,b),(b,a)]:
                    t,r=text.get('_ink_bbox',text['bbox']),rule['bbox'];gap=max(.04,text.get('font_size',12)/72*.25)
                    if text['kind']=='text' and rule['role'] in {'divider','rule'} and min(t['x']+t['w'],r['x']+r['w'])>max(t['x'],r['x']) and t['y']-gap<=r['y']<=t['y']+t['h']+gap:issue(si,'TEXT_RULE_COLLISION',[text['id'],rule['id']],'Glyph-based text region intersects or nearly touches a rule')
        density=sum(n['bbox']['w']*n['bbox']['h'] for n in nodes if n['role'] not in {'background','decoration','divider'})/(13.333*7.5)
        if density>.86:issue(si,'DENSITY_HIGH',[],'Informative bounding regions occupy over 86% of the canvas','WARN')
    status='FAIL' if any(i['severity']=='ERROR' for i in issues) else 'PASS_WITH_NOTES' if issues else 'PASS'
    return {'status':status,'metrics':metrics,'issues':issues,'limitations':['Spatial relationships are explicit, not inferred human intent. Contrast uses local raster samples; visual review remains required.']}

def inspect(pptx,scene_path=None):
    pptx=Path(pptx);sidecar=Path(scene_path or str(pptx)+'.scene.json')
    if not sidecar.exists():return {'status':'UNAVAILABLE','reason':'No native scene record; arbitrary imported decks need inspection and visual review'}
    graph=json.loads(sidecar.read_text(encoding='utf-8'))
    if graph.get('pptx_sha256')!=hashlib.sha256(pptx.read_bytes()).hexdigest():return {'status':'FAIL','reason':'Scene record hash does not match PPTX'}
    native_issues=[]
    with zipfile.ZipFile(pptx) as z:
        for s in graph['slides']:
            root=ET.fromstring(z.read(f"ppt/slides/slide{s['slide']}.xml"))
            names={el.attrib.get('name') for el in root.findall(f'.//{{{P}}}cNvPr')}
            expected={'gj:'+n['id'] for n in s['nodes']}
            if not expected<=names:
                native_issues.append({'severity':'ERROR','slide':s['slide'],'code':'NATIVE_SCENE_MISMATCH','missing':sorted(expected-names)})
            nodes={n['id']:n for n in s['nodes']}
            tree=root.find(f'.//{{{P}}}spTree')
            if tree is not None:
                for order,el in enumerate(tree):
                    tag=el.find(f'.//{{{P}}}cNvPr')
                    name=tag.attrib.get('name','') if tag is not None else ''
                    node=nodes.get(name.removeprefix('gj:'))
                    if node is None:continue
                    a='http://schemas.openxmlformats.org/drawingml/2006/main'
                    xf=el.find(f'.//{{{a}}}xfrm')
                    if xf is None:xf=el.find(f'.//{{{P}}}xfrm')
                    if xf is not None:
                        off=xf.find(f'{{{a}}}off');ext=xf.find(f'{{{a}}}ext')
                        if off is not None and ext is not None:node['bbox']=dict(zip(('x','y','w','h'),[int(v)/914400 for v in [off.attrib['x'],off.attrib['y'],ext.attrib['cx'],ext.attrib['cy']]]))
                    node['z']=order
    result=audit(graph)
    if native_issues:result['status']='FAIL';result['issues'].extend(native_issues)
    result['fonts']=graph.get('fonts',[])
    return result

if __name__=='__main__':
    result=inspect(sys.argv[1]);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(2 if result['status']=='FAIL' else 0)
