"""Measure font glyph advances in slide inches; no shell or font-name interpolation."""
import json, subprocess, sys
from PIL import ImageFont
data=json.load(sys.stdin)
fontfile=subprocess.check_output(['fc-match','-f','%{file}',data['font']+(':style=Bold' if data.get('bold') else '')],text=True,timeout=3).strip()
scale=4
font=ImageFont.truetype(fontfile,round(data['size']*scale))
print(json.dumps({'advances':{c:font.getlength(c)/(72*scale)*1.04 for c in set(data['text'])},'font_file':fontfile}))
