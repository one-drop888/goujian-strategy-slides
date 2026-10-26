# Security and capability parity · V1.3.1

This note records what V1.3.1 changes, what it deliberately keeps, and what has actually been verified. It is a public status record, not enterprise-platform approval. Local working-tree logs are not public evidence; the release workflow publishes the named receipts beside the archives when a release is created.

## What changed

- Runtime Python module loading uses ordinary imports. `core/qa/spec-check.py` remains a compatibility shim for the old path and CLI; its public symbols are unchanged.
- The fixed analytics-readback `node -e` payload is now the static `core/qa/recompute_analytics.js` entry, invoked by a fixed path with JSON stdin/stdout and a timeout.
- Fixed Doctor/Bootstrap `python -c` probes are now `scripts/probe_env.py` with explicit argv modes. Interpreter selection, `.venv` isolation and locked dependency installation are unchanged.
- Necessary process boundaries remain explicit: Pillow measurement/asset preparation, fontconfig queries, schema/analytics/QA Node entries, LibreOffice/Poppler rendering and Bootstrap installs. They retain known executables and argument arrays, with existing input checks and explicit timeouts; no shell string or dynamic module path was introduced. Output capture is not universally size-bounded.
- `scripts/security_preflight.py` now runs profile-aware checks over every text member of the final ZIP. It reports the raw literal, execution-related keywords, network/install/delete/path behaviour, and separates runtime blocks from development-only reporting. The archived v1.3.0 baseline remains readable under the legacy structural profile.

## Distribution contract

| Archive | Purpose | Test contract | Package metadata |
|---|---|---|---|
| `goujian-strategy-slides-v1.3.1.zip` | Primary runtime installation | `npm test` and `npm run test:core` run the real installed-runtime smoke; optional Pillow/image steps are disclosed as unrun in core mode | Runtime ZIP `package.json` is byte-mapped from `distribution/runtime-package.json` |
| `goujian-strategy-slides-v1.3.1-source.zip` | Complete source/development | Original full source test suite and benchmark workflow | Root `package.json` and lockfile |
| `goujian-strategy-slides-v1.3.1-showcase.zip` | Optional review evidence | Not an installation; adds only `out/v1.3-showcase/` to the runtime payload | Same runtime package mapping |

The runtime payload is an explicit 189-file manifest plus one mapped `package.json`. The 189 declared runtime files are the protected production set; the archive `package.json` is explicitly mapped development metadata, not a shipped production module. The 190 archive members are therefore not all byte-identical to the source tree. No shipped production module is overlaid, restored or replaced during acceptance. Package metadata keeps the same name, version, dependencies and overrides; development benchmark/showcase/fixture commands are omitted from the runtime manifest and documented as such.

## Security status

| Gate | Status | Public receipt |
|---|---|---|
| Final-ZIP static preflight | PASS in local acceptance for the candidate runtime, source and locked legacy baseline; the release workflow re-runs it on the final archives before publishing | `release-runtime-preflight.json`, `release-source-preflight.json`, `release-showcase-preflight.json` |
| Locked baseline archive member equality | PASS: 408/408 members of the locked v1.3.0 installer are byte-identical to the compared baseline tree; the installer SHA256 is verified | `release-capability-parity.json` → `baseline.archive_member_equality` |
| Runtime clean install before tag creation | Required release gate: extracts the actual runtime ZIP into an independent Unicode-named directory, rejects `node_modules`, `.venv`, symlinks and development overlays, runs project-local Bootstrap dry/real/idempotent, secure and core installed-runtime smoke, documented build/QA/render, all three recipes, protected-hash comparison and byte-reproducible repackaging | `release-runtime-clean-install.json` |
| Capability parity v1.3.0 → v1.3.1 | PASS after the final lifecycle-key exactness correction: 185 checks, 184 PASS, performance sample `NOT_RUN`; 96/72/24 matrix, three recipes, gallery/ledger/relationships, multimodal and q4 reasoning; 183/183 PNGs identical under RGBA channel comparison including alpha; 18 scene files / 151 slide titles measured by `pillow-glyph-advances-with-4pct-safety`; 37 negative tests | `release-capability-parity.json` |
| Full source suite on shipped runtime production files | PASS in local acceptance in an isolated tree: all 189 declared runtime production files byte-identical; only the source `package.json` was used as development metadata. The runtime archive's mapped `package.json` means not all 190 archive members are byte-identical | Release workflow full source suite; the local acceptance record is not a published receipt |
| Runtime dynamic module loading / dynamic require / shell strings / fixed inline payloads | Rejected by the scanner | Negative and alias/bypass tests in the source suite |
| Static argument-array processes | Retained and inventoried | Member, line, context and purpose in the preflight report |
| `wxect` literal | Reported exactly and case-insensitively; not hidden or aliased | Runtime inventory lists the scanner's own occurrences; the archived baseline contains 0 |
| Known company scanner rule | UNKNOWN | No rule ID, file or line was supplied |
| Company-platform upload/security | `COMPANY_PLATFORM_SECURITY=NOT_VERIFIED` | No actual upload or approval record |
| Agensi platform security | `NOT_VERIFIED` | No actual hosted acceptance |
| Clean tagged-clone verification | NOT_RUN before this source freeze; the release workflow performs it after publishing and also requires the pre-tag runtime clean-install gate | Release workflow |
| Final archive checksums | Not claimed here. The release workflow writes them at freeze | `SHA256SUMS.txt`, `release-manifest.json` |

## Checked-in acceptance summary

- The final archives are built deterministically from the approved commit. Every runtime member except the declared `package.json` mapping must equal the approved commit bytes.
- Static preflight, locked baseline member equality, scoped capability parity, the 37 negative parity tests, the pre-tag runtime clean install and the post-publish tagged-clone verification are release gates.
- Local acceptance evidence is retained in the working tree and is not a public receipt. The JSON files published beside the release archives are the external receipts; they can be linked once the release exists.
- Automated `VISUAL_QA` remains `NOT_RUN`. Codex separately completed a `PASS_WITH_NOTES` sample review of multimodal pages1–9 (including full-size table/quote pages), the dark gallery, light chart matrix and close-date timeline. The nine multimodal renders match the baseline byte-for-byte and retain the native objects. This is a patch non-regression review, not universal aesthetic or recipient-Office certification. [Review record](https://github.com/one-drop888/goujian-strategy-slides/blob/v1.3.1/docs/development/V1_3_1_VISUAL_REVIEW.json). Company-platform security remains `NOT_VERIFIED`.
- No final checksum is claimed before freeze.

## Boundaries that did not move

Apache-2.0 remains, third-party notices remain, and historical release evidence is not rewritten. No dependency upgrade, renderer fork, product capability change, Pro/Social work or old tag/release replacement is part of this patch.
