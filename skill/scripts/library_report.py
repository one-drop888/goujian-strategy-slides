#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
a=load('skill/archetypes/registry.json');s=load('skill/storylines/registry.json');c=load('skill/compositions/registry.json');t=load('skill/templates/registry.json');profiles=sorted(x.parent.name for x in (ROOT/'skill/profiles').glob('*/profile.json'))
print(f"Goujian Strategy Slides V1 library\nTemplates: {t['count']}\nStorylines: {s['count']}\nArchetypes: {a['count']}\nCompositions: {c['count']}\nProfiles: {len(profiles)}")
print('\nProfiles: '+', '.join(profiles))
print('\nTemplates:')
for x in t['templates']:print(f"- {x['id']}: {x['name']} → {x['storyline']} / {x['default_profile']}")
print('\nStorylines:')
for x in s['storylines']:print(f"- {x['id']}: {x['name']}")
