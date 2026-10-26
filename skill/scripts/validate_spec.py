#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from core.qa import spec_check

if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit('usage: validate_spec.py deck.json [report.json]')
    spec_check.main(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else None)
