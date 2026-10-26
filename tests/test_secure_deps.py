#!/usr/bin/env python3
"""Contract tests for the shared secure image-tier helper."""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('goujian_secure_deps', ROOT / 'core/qa/secure_deps.py')
secure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(secure)


class SecureDepsTests(unittest.TestCase):
    def test_repository_requirement_is_secure_and_python311_gated(self):
        text = (ROOT / 'requirements-render.txt').read_text(encoding='utf-8')
        self.assertEqual(secure.validate_requirements_text(text), [])
        self.assertIn('Pillow==13.0.0', text)
        self.assertIn('python_version >= "3.11"', text)

    def test_vulnerable_pillow_fallbacks_are_rejected(self):
        for version in ('11.3.0', '12.1.1'):
            errors = secure.validate_requirements_text(f'Pillow=={version}\n')
            self.assertTrue(errors, version)
            self.assertIn('unsupported Pillow declaration', ' '.join(errors))

    def test_requirement_marker_must_keep_python_311(self):
        self.assertTrue(secure.validate_requirements_text('Pillow==13.0.0\n'))
        self.assertTrue(secure.validate_requirements_text('Pillow==13.0.0; python_version >= "3.10"\n'))

    def test_missing_secure_declaration_is_rejected(self):
        errors = secure.validate_requirements_text('# nothing declared\n')
        self.assertIn('must declare the secure Pillow version', errors[0])

    def test_pillow_version_boundary(self):
        self.assertFalse(secure.pillow_is_secure('12.9.9'))
        self.assertTrue(secure.pillow_is_secure('13.0.0'))
        self.assertTrue(secure.pillow_is_secure('13.0.0.post1'))

    def test_secure_tier_requires_python311_and_pillow13(self):
        available = secure.secure_image_status(python=(3, 11, 9), pillow='13.0.0')
        self.assertEqual(available['status'], 'AVAILABLE')
        insecure = secure.secure_image_status(python=(3, 14, 0), pillow='12.1.1')
        self.assertEqual(insecure['status'], 'INSECURE')
        old_python = secure.secure_image_status(python=(3, 10, 14), pillow='13.0.0')
        self.assertEqual(old_python['status'], 'UNAVAILABLE')
        missing = secure.secure_image_status(python=(3, 11, 9), pillow=None)
        self.assertEqual(missing['status'], 'UNAVAILABLE')
        self.assertIn('Pillow', missing['reason'])

    def test_require_secure_image_stack_raises_without_silent_fallback(self):
        with mock.patch.object(secure, 'python_version', return_value=(3, 10, 14)), \
             mock.patch.object(secure, 'pillow_version', return_value=('13.0.0', None)):
            with self.assertRaisesRegex(secure.SecureDependencyError, r'requires the secure image tier'):
                secure.require_secure_image_stack('native render')
        with mock.patch.object(secure, 'python_version', return_value=(3, 14, 0)), \
             mock.patch.object(secure, 'pillow_version', return_value=('12.1.1', None)):
            with self.assertRaisesRegex(secure.SecureDependencyError, r'published advisories'):
                secure.require_secure_image_stack('native render')
        with mock.patch.object(secure, 'python_version', return_value=(3, 11, 9)), \
             mock.patch.object(secure, 'pillow_version', return_value=('13.0.0', None)):
            self.assertEqual(secure.require_secure_image_stack('native render')['status'], 'AVAILABLE')


if __name__ == '__main__':
    unittest.main()
