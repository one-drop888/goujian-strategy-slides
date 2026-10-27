#!/usr/bin/env python3
"""Materialize an inert negative-control skill fixture with a malicious PDF.

The PDF carries a catalog /OpenAction action dictionary with JavaScript. It is
generated at run time into a caller-owned private directory so the repository,
source archive, runtime archive and installed skill contain exactly one
SKILL.md. The PDF is parsed as data by the scanner and the structural checker;
it is never opened by a PDF viewer, executed or fetched.
"""
import argparse
import hashlib
import json
from pathlib import Path

SKILL_MD = '''---
name: pdf-structural-negative-fixture
description: "Defensive scanner-validation fixture. Contains an inert PDF with a JavaScript OpenAction for static structural review only. NEVER open or execute."
license: Apache-2.0
---

# Negative PDF Structural Fixture

This generated package exists only to prove that a malicious PDF is still
blocked even when a caller claims benign /OpenAction metadata.

The PDF is scanned and parsed as data. Do not open it in a viewer.
'''

MALICIOUS_ACTION = b'<< /S /JavaScript /JS (app.alert\\(1\\);) >>'


def build_pdf():
    """Return PDF bytes with a correct classic xref table."""
    header = b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n'
    bodies = [
        b'<< /Type /Catalog /Pages 2 0 R /OpenAction 4 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>',
        MALICIOUS_ACTION,
    ]
    output = bytearray(header)
    offsets = []
    for number, body in enumerate(bodies, 1):
        offsets.append(len(output))
        output += f'{number} 0 obj\n'.encode('ascii')
        output += body
        output += b'\nendobj\n'
    xref = len(output)
    output += b'xref\n0 5\n0000000000 65535 f \n'
    for offset in offsets:
        output += f'{offset:010d} 00000 n \n'.encode('ascii')
    output += f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode('ascii')
    return bytes(output)


def materialize(destination):
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError('destination must not be a symlink: {}'.format(destination))
    if destination.exists():
        if not destination.is_dir():
            raise ValueError('destination is not a directory: {}'.format(destination))
        if any(destination.iterdir()):
            raise ValueError('destination is not empty: {}'.format(destination))
    destination.mkdir(parents=True, exist_ok=True)
    skill = destination / 'SKILL.md'
    pdf = destination / 'pdf-negative-fixture.pdf'
    data = build_pdf()
    skill.write_text(SKILL_MD, encoding='utf-8')
    pdf.write_bytes(data)
    return {
        'destination': str(destination),
        'files': [skill.name, pdf.name],
        'pdf_sha256': hashlib.sha256(data).hexdigest(),
        'purpose': 'inert PDF structural negative-control fixture for scanner validation',
        'executed': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True,
                        help='private empty directory to receive the fixture')
    args = parser.parse_args()
    print(json.dumps(materialize(args.out), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
