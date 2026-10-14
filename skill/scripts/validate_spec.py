#!/usr/bin/env python3
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'core' / 'qa'))
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location('spec_check', ROOT/'core'/'qa'/'spec-check.py')
mod = module_from_spec(spec); spec.loader.exec_module(mod)

if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit('usage: validate_spec.py deck.json [report.json]')
    mod.main(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else None)
