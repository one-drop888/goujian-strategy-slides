#!/usr/bin/env python3
"""Check the deterministic installer and optional showcase archive."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'goujian-strategy-slides/'
REQUIRED = {
    'core/analytics/index.js', 'core/schema/analytics.schema.json', 'scripts/analyze.js',
    'skill/analytics/business-performance.json', 'skill/analytics/sales-conversion.json', 'skill/analytics/project-analytics.json',
    'SKILL.md', 'package.json', 'package-lock.json',
    'core/renderer/index.js', 'core/schema/deck.schema.json',
    'skill/storylines/registry.json', 'skill/archetypes/registry.json',
    'skill/compositions/registry.json', 'skill/templates/registry.json',
    'skill/profiles/executive-clean/profile.json',
    'skill/scripts/build_deck.js', 'skill/scripts/quality_gate.py',
    'skill/examples/executive-review.json',
    'skill/examples/assets/channel-evidence.png',
    'skill/reasoning/fixtures/q4-six-actions/plan.json',
}


def load_packager():
    spec = importlib.util.spec_from_file_location('goujian_package_runtime', ROOT / 'scripts/package_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_archive(archive, required):
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        assert package.testzip() is None
        assert len(names) == len(set(names))
        assert [name for name in names if name.endswith('/SKILL.md')] == [PREFIX + 'SKILL.md']
        assert required <= set(names)
        assert not any('/out/' in name or '/node_modules/' in name or '/.venv/' in name for name in names)
        for info in package.infolist():
            assert info.date_time == (2026, 1, 1, 0, 0, 0), info.filename
            assert (info.external_attr >> 16) & 0o777 == 0o644, info.filename


def main():
    assert not (ROOT / 'skill/SKILL.md').exists()
    packager = load_packager()
    with tempfile.TemporaryDirectory(prefix='goujian-package-test-') as temp:
        temp = Path(temp)
        first, second = temp / 'first.zip', temp / 'second.zip'
        result = subprocess.run(['python3', 'scripts/package_runtime.py', str(first)], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        result = subprocess.run(['python3', 'scripts/package_runtime.py', str(second)], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(second.read_bytes()).hexdigest()
        assert_archive(first, {PREFIX + name for name in REQUIRED})
        with zipfile.ZipFile(first) as package:
            frontmatter = package.read(PREFIX + 'SKILL.md').decode('utf-8').split('---', 2)[1]
            assert 'name: goujian-strategy-slides' in frontmatter
            version = json.loads(package.read(PREFIX + 'package.json'))['version']
            assert version == '1.2.0'
            assert f'version: "{version}"' in frontmatter
            line = next(line for line in frontmatter.splitlines() if line.startswith('description: '))
            description = json.loads(line.removeprefix('description: '))
            assert '专业AI PPT制作技能' in description and '原生可编辑PPTX' in description
            assert not any(name.endswith(('.pptx', '.pdf')) for name in package.namelist())

        fake = ROOT / 'out' / '.package-test-showcase'
        try:
            shutil.rmtree(fake, ignore_errors=True)
            (fake / 'decks').mkdir(parents=True)
            (fake / 'decks' / 'example.pptx').write_bytes(b'not-a-real-pptx')
            (fake / 'readme.txt').write_text('showcase fixture\n', encoding='utf-8')
            packager.SHOWCASE_REL = Path('out/.package-test-showcase')
            showcase = temp / 'showcase.zip'
            result = packager.build(showcase, showcase=True)
            assert result['entries'] > 0
            with zipfile.ZipFile(showcase) as package:
                names = package.namelist()
                assert PREFIX + 'out/.package-test-showcase/decks/example.pptx' in names
                assert PREFIX + 'out/.package-test-showcase/readme.txt' in names
                assert [name for name in names if name.endswith('/SKILL.md')] == [PREFIX + 'SKILL.md']
        finally:
            shutil.rmtree(fake, ignore_errors=True)
    print('PASS: deterministic installer, one Skill entry, required assets, safe paths and optional showcase')


if __name__ == '__main__':
    main()
