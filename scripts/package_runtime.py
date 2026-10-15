#!/usr/bin/env python3
"""Build the complete V1 distributable ZIP, excluding generated output and local caches."""
from pathlib import Path
import json, sys, zipfile
ROOT=Path(__file__).resolve().parents[1]
INCLUDE=['SKILL.md','core','skill','adapters','docs','tests','scripts','.github','package.json','package-lock.json','requirements-render.txt','README.md','README.zh-CN.md','README.en.md','CONTRIBUTING.md','CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICE.md','.gitignore']
EXCLUDE_DIRS={'node_modules','out','dist','__pycache__','.git','.pytest_cache'}
def add_tree(z,p,base):
    if p.is_dir():
        for x in sorted(p.rglob('*')):
            if any(part in EXCLUDE_DIRS for part in x.parts):continue
            if x.is_file() and not x.name.endswith(('.pyc','.pptx','.pdf')):z.write(x,(base/x.relative_to(ROOT)).as_posix())
    elif p.exists():z.write(p,(base/p.relative_to(ROOT)).as_posix())
def main(out):
    skill_entries=[p for p in ROOT.rglob('SKILL.md') if not any(part in EXCLUDE_DIRS for part in p.relative_to(ROOT).parts)]
    if skill_entries != [ROOT/'SKILL.md']:
        raise ValueError(f'Expected only root SKILL.md; found: {[str(p.relative_to(ROOT)) for p in skill_entries]}')
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for rel in INCLUDE:add_tree(z,ROOT/rel,Path('goujian-strategy-slides'))
        names=z.namelist()
        if len(names)!=len(set(names)) or [n for n in names if n.endswith('/SKILL.md')] != ['goujian-strategy-slides/SKILL.md']:
            raise ValueError('Archive contains duplicate entries or more than one SKILL.md')
    print(out)
if __name__=='__main__':
    version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
    main(sys.argv[1] if len(sys.argv)>1 else ROOT/f'dist/goujian-strategy-slides-v{version}.zip')
