#!/usr/bin/env python3
"""Compatibility shim for the historical hyphenated spec validator path."""
import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from core.qa.spec_check import (TOPIC_TITLES,ACTION_WORDS,DESCRIPTIVE_OK,
                                load_ids,title_score,check,result_for,main)

if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit('usage: spec-check.py deck.json [report.json]')
    main(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
