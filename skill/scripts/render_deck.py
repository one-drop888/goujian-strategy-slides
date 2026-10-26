#!/usr/bin/env python3
"""Isolated LibreOffice conversion; fresh output only, optional Pillow montage."""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from core.qa import secure_deps

def run(cmd):
    return subprocess.run(cmd,text=True,capture_output=True,timeout=120,shell=False,
                          env={**os.environ,'SAL_USE_VCLPLUGIN':'svp'})

def render(pptx,outdir,dpi=140):
    pptx=Path(pptx).resolve(); outdir=Path(outdir).resolve()
    lo=shutil.which('libreoffice') or shutil.which('soffice'); ppm=shutil.which('pdftoppm')
    if not lo or not ppm:
        return {'status':'UNAVAILABLE','reason':'LibreOffice and pdftoppm are required','pages':[]}
    try:
        secure_deps.require_secure_image_stack('native render/montage')
        from PIL import Image, ImageDraw
    except ImportError:
        return {'status':'UNAVAILABLE','reason':'Pillow is required: pip install -r requirements-render.txt in a Python >= 3.11 environment','pages':[]}
    except Exception as error:
        return {'status':'UNAVAILABLE','reason':str(error),'pages':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='goujian-render-') as td:
            tmp=Path(td); profile=(tmp/'lo-profile').as_uri()
            p=run([lo,f'-env:UserInstallation={profile}','--headless','--convert-to','pdf','--outdir',td,str(pptx)])
            pdf=tmp/(pptx.stem+'.pdf')
            if p.returncode!=0 or not pdf.exists():
                return {'status':'FAIL','reason':(p.stderr or p.stdout or 'No PDF produced').strip(),'pages':[]}
            q=run([ppm,'-png','-r',str(dpi),str(pdf),str(tmp/'slide')])
            if q.returncode!=0:return {'status':'FAIL','reason':(q.stderr or q.stdout).strip(),'pages':[]}
            pages=sorted(tmp.glob('slide-*.png'),key=lambda p:int(re.search(r'(\d+)$',p.stem).group(1)))
            if not pages:return {'status':'FAIL','reason':'renderer produced no pages','pages':[]}
            outdir.mkdir(parents=True,exist_ok=True)
            # Cleanup is limited to prior slide images from this renderer, after successful conversion.
            for stale in outdir.glob('slide-*.png'):stale.unlink()
            for p in pages:shutil.copy2(p,outdir/p.name)
            shutil.copy2(pdf,outdir/'deck.pdf')
            thumbs=[]
            for p in pages:
                with Image.open(p) as src:im=src.convert('RGB')
                im.thumbnail((480,270)); canvas=Image.new('RGB',(500,300),'white')
                canvas.paste(im,((500-im.width)//2,10)); ImageDraw.Draw(canvas).text((10,280),p.stem,fill='black'); thumbs.append(canvas)
            cols=min(3,len(thumbs)); rows=(len(thumbs)+cols-1)//cols
            montage=Image.new('RGB',(cols*500,rows*300),(238,238,238))
            for i,im in enumerate(thumbs):montage.paste(im,((i%cols)*500,(i//cols)*300))
            montage_path=outdir/'montage.png';montage.save(montage_path)
            return {'status':'PASS','pages':[str(outdir/p.name) for p in pages],'montage':str(montage_path),'pdf':str(outdir/'deck.pdf')}
    except (subprocess.TimeoutExpired,OSError) as e:
        return {'status':'FAIL','reason':str(e),'pages':[]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pptx');ap.add_argument('outdir');ap.add_argument('--dpi',type=int,default=140);ap.add_argument('--json')
    a=ap.parse_args();r=render(a.pptx,a.outdir,a.dpi);print(json.dumps(r,ensure_ascii=False,indent=2))
    if a.json:
        p=Path(a.json);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if r['status'] in {'PASS','UNAVAILABLE'} else 2)
if __name__=='__main__':main()
