"""Measure font glyph advances in slide inches; no shell or font-name interpolation."""
import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from core.qa import secure_deps

def main():
    secure_deps.require_secure_image_stack('font glyph measurement')
    from PIL import ImageFont
    data=json.load(sys.stdin)
    fontfile=subprocess.check_output(['fc-match','-f','%{file}',data['font']+(':style=Bold' if data.get('bold') else '')],text=True,timeout=3,shell=False).strip()
    scale=4
    font=ImageFont.truetype(fontfile,round(data['size']*scale))
    print(json.dumps({'advances':{c:font.getlength(c)/(72*scale)*1.04 for c in set(data['text'])},'font_file':fontfile}))

if __name__=='__main__':
    try:main()
    except Exception as error:print(str(error),file=sys.stderr);raise SystemExit(2)
