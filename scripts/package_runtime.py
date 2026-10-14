#!/usr/bin/env python3
"""Build the complete V1 distributable ZIP, excluding generated output and local caches."""
from pathlib import Path
import sys, zipfile
ROOT=Path(__file__).resolve().parents[1]
INCLUDE=['SKILL.md','core','skill','adapters','docs','tests','scripts','.github','package.json','package-lock.json','requirements-render.txt','README.md','README.zh-CN.md','CONTRIBUTING.md','CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICE.md','.gitignore']
EXCLUDE_DIRS={'node_modules','out','dist','__pycache__','.git','.pytest_cache'}
def add_tree(z,p,base):
    if p.is_dir():
        for x in sorted(p.rglob('*')):
            if any(part in EXCLUDE_DIRS for part in x.parts):continue
            if x.is_file() and not x.name.endswith(('.pyc','.pptx','.pdf')):z.write(x,(base/x.relative_to(ROOT)).as_posix())
    elif p.exists():z.write(p,(base/p.relative_to(ROOT)).as_posix())
def main(out):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for rel in INCLUDE:add_tree(z,ROOT/rel,Path('goujian-strategy-slides'))
    print(out)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else ROOT/'dist/goujian-strategy-slides-v1.0.0.zip')
