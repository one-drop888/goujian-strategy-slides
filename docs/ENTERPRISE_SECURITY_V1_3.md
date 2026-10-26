# Enterprise Skill security and distribution · V1.3

Public package security and private platform approval are separate gates. The user confirmed no company-platform access for this delivery and authorized Community publication after its public gates pass. No private platform log, credential or internal business dataset is included.

## Public package checks

Preflight the complete actual ZIP with `scripts/security_preflight.py`, not only GitHub source. It checks archive integrity/paths/duplicate entries, one root Skill, YAML-compatible metadata/version, permissions/symlinks, shipped Python/JavaScript/instructions/references, known dynamic execution patterns and dependency declarations. Inert negative-test material is classified transparently; runtime threats are not hidden, encoded or removed from the scanner rules.

The V1.2.1 Doctor static datetime import remains. Necessary fixed local module loading and subprocess calls use known local paths/argument arrays. Bootstrap dependency downloads are explicit registry installs into project npm state and `.venv`; no hidden runtime installer, global permission/config changes or automatic customer-data upload is added.

Public dependency snapshot: [executed report](evidence/v1.3/dependency-security.json). Official npm audit returned0 known vulnerabilities for the lockfile; official PyPI/OSV returned0 advisory records for Pillow13.0.0 at the recorded time. Pillow13 requires Python3.11+ and uses MIT-CMU; old Python retains a Pillow-free core tier, with no vulnerable fallback. These results do not promise absence of unknown vulnerabilities or certify the host OS/runtime.

Release assets supply separate installer/showcase checksums and preflight evidence bound to the actual archive bytes. The installer must contain the committed source bytes; only the optional showcase adds the explicitly allowed generated subtree. No ZIP is committed into the repository, and no old tag/release is overwritten.

## Platform acceptance

```yaml
ENTERPRISE_SECURITY_GATE:
  INSTALLER_STATIC_SCAN: PASS # local complete-ZIP preflight; release assets carry a fresh hash-bound report
  DEPENDENCY_SECURITY: PASS # dated declared-dependency snapshot; see linked report
  SKILL_METADATA_VALIDATION: PASS # local archive verified; exact release archive rechecked by workflow
  PACKAGE_INTEGRITY: PASS # local archive verified; exact release archive rechecked by workflow
  KNOWN_PATTERN_REGRESSION: PASS # local archive verified; exact release archive rechecked by workflow
  V1.2.1_FIX_PRESERVED: PASS # source and candidate ZIP static datetime import retained
  COMPANY_PLATFORM_UPLOAD: NOT_VERIFIED
  COMPANY_PLATFORM_SECURITY: NOT_VERIFIED
  AGENSI_PLATFORM_SECURITY: NOT_VERIFIED
  FINAL_RESULT: NOT_VERIFIED # company/marketplace approval is not established by public CI
```

Public PASS fields describe executed candidate checks; the Release assets provide fresh reports for the exact published ZIP bytes. Company approval requires a real upload, its SHA256 and actual scanner/approval result. Agensi additionally needs hosted loading, permissions, local Core/dependency interaction and output delivery checks. Do not substitute GitHub CI for either journey. Record sensitive platform evidence privately; publish only an appropriate status and package identity.

A platform rejection should be diagnosed by exact file/pattern and actual execution risk. Replace unnecessary dynamic execution with equivalent static code; preserve cleanup conditions, deletion scope, permission checks and true safety notices. Never split strings, encode a dangerous call, disable scanning or change a platform rule merely to get a green result.
