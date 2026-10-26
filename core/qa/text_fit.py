"""Conservative glyph-based text-height estimate, separate from exact PowerPoint layout."""
from functools import lru_cache
import re, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from core.qa import secure_deps

@lru_cache(maxsize=128)
def font_for(family,size,bold):
    secure_deps.require_secure_image_stack('font measurements')
    from PIL import ImageFont
    file=subprocess.check_output(['fc-match','-f','%{file}',family+(':style=Bold' if bold else '')],text=True,timeout=3,shell=False).strip()
    return ImageFont.truetype(file,round(size*4))

def estimated_height(text,family,size,bold,width):
    if width<=0:return None
    try:font=font_for(family,size,bold)
    except Exception:return None
    limit=width*72*4/1.04;lines=0
    for paragraph in text.split('\n'):
        current=0;lines+=1
        for word in re.findall(r'[A-Za-z0-9]+|[^A-Za-z0-9]',paragraph):
            advance=font.getlength(word)
            if current and current+advance>limit:lines+=1;current=advance
            else:current+=advance
    return lines*size/72*1.12
