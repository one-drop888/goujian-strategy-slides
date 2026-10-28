# Phase 1b focused independent-review repair

- Branch: `fix/enterprise-runtime-package`
- Base commit: `9d4902d963da0d8ba5bdd97a213cca5ae6856c86`
- Implementation commit: `3054ab46cb3b1064479b513eb38b7fea6a4506fc`
- Scope: Phase 1b findings only. No product-engine redesign, no dependency,
  scanner-lock, security-policy or 38-entry ledger changes.

## Root findings

| # | Root finding | Status | Resolution and evidence |
|---|---|---|---|
| 1 | Output guard must protect the active packager and every selected Source input in all modes, including symlink outputs resolving to Source | RESOLVED | `scripts/package_runtime.py` validates the canonical output against the active packager and every selected input after symlink resolution in runtime, source and showcase modes. `tests/test_package.py::assert_output_location_guard` proves overwrite and symlink-to-input refusal while normal `out`/`dist`/temp outputs still build. |
| 2 | Installed-member byte comparison against canonical Source before archive write; tampered core comment must fail without `--expect-sha256` | RESOLVED | `scripts/package_runtime.py` compares each declared installed member to the canonical Source bytes before writing; rebuilt-ZIP SHA, installed-read SHA, missing, symlink and extra guards remain. `tests/test_package.py::assert_source_only_repack_guards` covers the tampered member and symlinked member probes. |
| 3 | `capability_parity.baseline_archive_evidence` must fail closed on digest mismatch before `ZipFile` open/decompress/path lookup | RESOLVED | Digest check runs before archive access and preserves the fixed contract enum and historical default. `tests/test_capability_parity.py::test_wrong_digest_fails_before_zip_is_opened_or_parsed` patches `ZipFile` to raise and proves it is never called. |
| 4 | Frozen official v1.3.1 Runtime preflight PASS; v1.3.2 strict; historical profiles preserved; 26 AST detector nodes unchanged | RESOLVED | `tests/test_security_preflight.py::test_locked_official_v131_runtime_passes_historical_audit` loads the actual 190-member official ZIP when present; strict v1.3.2 runtime/source and legacy audit notes are covered by the 30-test suite; `test_executable_risk_detectors_are_ast_identical_to_v1_3_1` preserves all 26 detector nodes. |
| 5 | Actual Runtime CLI coverage from Source-generated Spec data, full matrix, multimodal, analytics, reasoning, relationships; candidate owns `node_modules` | RESOLVED | `scripts/runtime_acceptance.py` executes each installed runtime's production CLIs with fixed argv. It covers 96 matrix cells (72 accepted / 24 named rejections), multimodal, 3 analytical recipes, 3 reasoning plans and 4 relationship cases × 2 themes. Candidate fallback is rejected; baseline/source fallback must match the lock. |
| 6 | Retain Spec/PPTX/scene/QA/log/render/Montage evidence on success and failure under a fresh explicit directory; wire into CI/Release uploads | RESOLVED | `prepare_artifact_root` refuses stale/non-empty/overlapping directories and writes an owned marker. Failed cases keep raw logs and artifacts; the run writes `result.json` plus a SHA-256 manifest. CI and Release use run-scoped `--artifact-dir` values and upload them. |
| 7 | Correct docstrings/report, undefined label, and failed-build/missing-output short-circuits | RESOLVED | The harness docstring and result notes state that installed production CLIs run with fixed argv and that no installed developer/release code or overlay is imported. All title-measurement branches use a defined case label. `run_spec_case` returns structured FAIL for zero-exit builds without PPTX, missing JSON, failed glyph measurement and unreadable generated JSON; `compare_runs` short-circuits failed/missing-output cases and returns a FAIL record. `tests/test_runtime_acceptance.py::RunSpecCaseFailureTests` covers retention. |
| 8 | SKILL first Runtime paragraph: official complete Runtime ZIP or full Source checkout | RESOLVED (awaits Codex review) | `SKILL.md` now begins “Install the official complete Runtime ZIP **or** a full Source checkout. Run commands from the installed skill root.” Version 1.3.2, description and methods are unchanged. |
| 9 | Release notes must not permanently claim validation was not executed | RESOLVED | `docs/V1_3_2_RELEASE_NOTES.md` now records a dated 2026-10-28 implementation checkpoint with stable product/migration facts, the fixed parity contract/baseline SHA, and an acceptance policy that binds final evidence to the frozen candidate's external release record. No permanent NOT_RUN or unsupported PASS remains. |

## Changed files at the implementation commit

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | Run-scoped acceptance artifact directory, coverage/family/rejection/relationship assertions, artifact upload |
| `.github/workflows/release.yml` | Same acceptance assertions, manifest coverage/evidence fields and verification, artifact upload |
| `SKILL.md` | First Runtime paragraph states ZIP or full Source |
| `docs/V1_3_2_RELEASE_NOTES.md` | Dated implementation checkpoint and acceptance policy |
| `scripts/capability_parity.py` | Digest fail-closed before archive parsing |
| `scripts/package_runtime.py` | Output/input guard across modes; canonical member bytes before write |
| `scripts/runtime_acceptance.py` | Full installed-CLI coverage, artifact retention, provenance and failure short-circuits |
| `scripts/security_preflight.py` | Historical v1.3.1 profiles and strict v1.3.2 guards |
| `tests/test_capability_parity.py` | Wrong-digest no-ZIP-open probe |
| `tests/test_package.py` | Output guard and tampered/symlinked member probes |
| `tests/test_pdf_structural_review.py` | Derives the archive version from `package.json` instead of a stale pin |
| `tests/test_runtime_acceptance.py` | Provenance, matrix, artifact, short-circuit and failure-retention tests |
| `tests/test_security_preflight.py` | Official 190-member v1.3.1 audit, historical profiles, AST identity |

Diff at the implementation commit: 13 files, 2553 insertions, 233 deletions.

## Verification

All runs below are local and use the scoped environments; raw failure output was
retained during development and repaired, not suppressed.

| Check | Command | Result |
|---|---|---|
| Runtime acceptance unit suite | `python3 tests/test_runtime_acceptance.py` | 32 tests OK |
| Capability parity | `python3 tests/test_capability_parity.py` | 45 tests OK |
| Security preflight | `python3 tests/test_security_preflight.py` | 30 tests OK |
| PDF structural review | `out/security-gate-control/venv/scanner/bin/python tests/test_pdf_structural_review.py` | 47 tests OK |
| Packager/deterministic archives/guards | `python3 tests/test_package.py` | PASS |
| Workflow security | `python3 tests/test_workflow_security.py` | 18 tests OK |
| Package scanner | `python3 tests/test_scan_skill_package.py` | 43 tests OK |
| Advisory fail-closed checks | `python3 tests/test_advisory_check.py` | 14 tests OK |
| Secure dependency tier | `python3 tests/test_secure_deps.py` | 7 tests OK |
| QA/gallery (secure Pillow) | `PATH=out/v13-control/secure-qa-venv/bin:$PATH out/v13-control/secure-qa-venv/bin/python tests/test_qa.py` | 9 tests OK |
| Bootstrap / doctor | `python3 tests/test_bootstrap.py`; `python3 tests/test_doctor.py` | 18 OK (1 skipped) / 16 OK |
| Workflow YAML parse | PyYAML `safe_load` for CI and Release | OK |
| Python compile | `python3 -m compileall -q core skill scripts tests` | OK |
| Public-core syntax floor | `ast.parse(..., feature_version=(3, 9))` over `core/`, `skill/`, `scripts/` | OK |

Full harness command (secure Pillow interpreter):

```text
out/v13-control/secure-qa-venv/bin/python scripts/runtime_acceptance.py \
  --source-root . \
  --runtime-root out/phase1b-candidate-runtime-1793176968 \
  --baseline-zip out/v132-control/official-v1.3.1-runtime.zip \
  --baseline-root out/v132-control/runtime-tree/goujian-strategy-slides \
  --node-modules node_modules \
  --artifact-dir out/phase1b-acceptance-artifacts-4 \
  --json out/phase1b-acceptance-4.json
```

Local harness result at the implementation commit: **PASS**. The rerun produced
96 cells / 72 accepted / 24 matched rejections with the exact by-code
distribution, 36 native charts per theme, multimodal 9 embedded images, 3
analytics recipes, 3 reasoning plans, 4 relationship cases × 2 themes (8
outputs), 20 passing comparisons and a 776-file artifact manifest
(`out/phase1b-acceptance-artifacts-4`, result
`out/phase1b-acceptance-4.json`, manifest SHA-256
`c1a16b0bca5a0d7a019570898720c16643e552904123be17710802cc0e008d84`).

## Boundaries preserved

- No dependency or lockfile change; no scanner pin/lock change; no PDF policy
  change; `security/review-ledger.json` remains at 38 entries and untouched.
- Exactly one repository `SKILL.md`.
- Archives are built only by `scripts/package_runtime.py`.
- No push, real CI dispatch, ledger refresh or formal Release was performed.
- `VISUAL_QA=NOT_RUN` and `COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`; no
  enterprise-platform approval is claimed.

## Pending external gates

- Codex review of the `SKILL.md` wording change and independent reprobe of all
  nine boundaries against the frozen commit.
- New exact, content-bound ledger approvals if the candidate scans require
  them; full package validation; real CI/Release after authorization.
