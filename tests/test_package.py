#!/usr/bin/env python3
"""Check the installable distribution, not just the source tree."""
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
REQUIRED = {
    'SKILL.md', 'package.json', 'package-lock.json',
    'core/renderer/index.js', 'core/schema/deck.schema.json',
    'skill/storylines/registry.json', 'skill/archetypes/registry.json',
    'skill/compositions/registry.json', 'skill/templates/registry.json',
    'skill/profiles/executive-clean/profile.json',
    'skill/scripts/build_deck.js', 'skill/scripts/quality_gate.py',
    'skill/examples/executive-review.json',
}

def main():
    assert not (ROOT / 'skill/SKILL.md').exists()
    with tempfile.TemporaryDirectory(prefix='goujian-package-test-') as temp:
        archive = Path(temp) / 'install.zip'
        result = subprocess.run(['python3', 'scripts/package_runtime.py', str(archive)], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            assert package.testzip() is None
            assert len(names) == len(set(names))
            assert [name for name in names if name.endswith('/SKILL.md')] == [PREFIX + 'SKILL.md']
            assert {PREFIX + name for name in REQUIRED} <= set(names)
            frontmatter = package.read(PREFIX + 'SKILL.md').decode('utf-8').split('---', 2)[1]
            assert 'name: goujian-strategy-slides' in frontmatter
            assert 'version: "1.0.1"' in frontmatter
            line = next(line for line in frontmatter.splitlines() if line.startswith('description: '))
            description = json.loads(line.removeprefix('description: '))
            assert '专业AI PPT制作技能' in description and '原生可编辑PPTX' in description
    print('PASS: installable ZIP has one Skill entry, valid metadata and required runtime files')

if __name__ == '__main__':
    main()
