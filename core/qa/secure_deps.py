"""Single source of truth for the optional secure image/render dependency tier.

The core spec/geometry/inspection tier keeps working on Python >= 3.9 with no
Pillow. Untrusted raster processing and the full render/montage toolchain
require Python >= 3.11 with a non-vulnerable Pillow. An older explicit Python
selection therefore stays core-only: it must never silently install the old
vulnerable Pillow versions.
"""
import importlib.metadata
import re
import sys

MIN_PYTHON_SECURE = (3, 11)
MIN_PILLOW = (13, 0, 0)
SECURE_PILLOW_REQUIREMENT = 'Pillow==13.0.0; python_version >= "3.11"'
SECURE_PILLOW_LICENSE = 'MIT-CMU'


class SecureDependencyError(RuntimeError):
    pass


def version_tuple(value):
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', str(value or ''))
    return tuple(int(part) for part in match.groups()) if match else None


def version_text(value):
    return '.'.join(str(part) for part in value) if value else None


def python_version():
    return tuple(sys.version_info[:3])


def pillow_version():
    try:
        return importlib.metadata.version('Pillow'), None
    except importlib.metadata.PackageNotFoundError:
        return None, None
    except Exception as error:  # metadata backends can fail independently
        return None, str(error)


def pillow_is_secure(version=None):
    parsed = version_tuple(version)
    return bool(parsed and parsed >= MIN_PILLOW)


_UNSET = object()


def secure_image_status(python=None, pillow=_UNSET):
    """Return AVAILABLE, UNAVAILABLE (toolchain absent) or INSECURE (old Pillow)."""
    python = tuple(python or python_version())[:3]
    if pillow is _UNSET:
        pillow, _ = pillow_version()
    python_ok = python >= MIN_PYTHON_SECURE
    pillow_ok = pillow_is_secure(pillow)
    if not python_ok:
        status = 'UNAVAILABLE'
        reason = (f'secure image/render tier requires Python >= {version_text(MIN_PYTHON_SECURE)}; '
                  f'active interpreter is {version_text(python)}')
    elif not pillow:
        status = 'UNAVAILABLE'
        reason = f'Pillow >= {version_text(MIN_PILLOW)} is not installed in this interpreter'
    elif not pillow_ok:
        status = 'INSECURE'
        reason = (f'Pillow {pillow} is affected by published advisories; untrusted image processing '
                  f'requires >= {version_text(MIN_PILLOW)}')
    else:
        status = 'AVAILABLE'
        reason = f'Python {version_text(python)} with Pillow {pillow}'
    return {
        'status': status,
        'python': version_text(python),
        'python_ok': python_ok,
        'pillow': pillow,
        'pillow_ok': pillow_ok,
        'min_python': version_text(MIN_PYTHON_SECURE),
        'min_pillow': version_text(MIN_PILLOW),
        'reason': reason,
    }


def require_secure_image_stack(feature='image processing'):
    status = secure_image_status()
    if status['status'] != 'AVAILABLE':
        raise SecureDependencyError(
            f'{feature} requires the secure image tier: {status["reason"]}. '
            f'Use Python >= {status["min_python"]} with Pillow {status["min_pillow"]} '
            f'(see requirements-render.txt); the core spec/QA tier remains available.')
    return status


def validate_requirements_text(text):
    """Reject vulnerable Pillow fallbacks and require the secure marker."""
    errors = []
    lines = [line.strip() for line in str(text or '').splitlines()]
    declared = [line for line in lines if line and not line.startswith('#')]
    pillow_lines = [line for line in declared if re.match(r'(?i)^pillow\b', line)]
    if not pillow_lines:
        errors.append('requirements-render.txt must declare the secure Pillow version')
    for line in pillow_lines:
        normalized = line.replace(' ', '')
        if not re.match(r'(?i)^pillow==13\.0\.0;python_version>=\s*["\']3\.11["\']$', normalized):
            errors.append(f'unsupported Pillow declaration: {line}')
        if re.match(r'(?i)^pillow==(?:11|12)\.', normalized):
            errors.append(f'vulnerable Pillow fallback is not allowed: {line}')
    return errors
