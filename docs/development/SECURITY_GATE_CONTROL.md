# Permanent release security gate — control record

Owner and independent acceptance: Codex. Engineering executor: Qoder CN CLI.

## Baseline and scope

- Frozen public v1.3.1: `25f269f8db333e27f23915ecb472eed6cb2709c6`.
- Official runtime SHA256: `7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd`.
- Historical tag, Release and assets must not change. No version bump or new Release is authorized by gate completion alone.
- Product runtime, renderers, numeric semantics, fonts/images, analysis and QA retain their existing capabilities.
- This control file tracks engineering decisions. Raw local logs stay in ignored `out/security-gate-control/`; CI archives its own reports on success and failure.

## Observed GitHub state (2026-10-28)

- PR #1 (`feat/permanent-skill-security-gate`) is merged; `main` is `e5a83dfcfe51df11e5def444e356ae9f1fb75cab`.
- `main` continuation run `40506891052`: all three jobs PASS, including the package security gate — Core-only (Node 18, Python 3.9), Secure image tier (Node 18, Python 3.11) and Secure image tier (Node 24, Python 3.14).
- Read-only release rehearsal `40506964205` (`Validate and security-gate (no mutation)`) FAILED at step 24, "Security-gate the actual runtime, source and showcase archives", with 21 raw HIGH `PDF_STRUCTURAL_THREAT` findings. The write-capable `Publish Release (explicit publish=true only)` job was SKIPped; no tag, Release or asset changed.
- Branch protection is verified: required status checks, strict branch, `enforce_admins`, no force pushes or deletions.
- `security/pdf-structural-policy.json` remains `PENDING_CODEX_REVIEW`. The local PDF candidate on `fix/pdf-destination-security-review` has not been pushed and has not run in CI; local evidence is not CI evidence.

## Initial live observations

- 2026-10-27: local main clean at the frozen commit; Qoder CN CLI reports 1.1.78.
- GitHub repository is public; current account has repository admin permission. Main has no branch protection and no rulesets. This is an observed gap, not an enforced control.
- Cisco official PyPI package 2.3.1 requires Python >=3.11,<3.15 and declares Apache-2.0. Linux x86_64 wheel SHA256: `e3ea642577578ddb41872b640253a44f7a11858d5d30fa426040b69528a6df23`. Tool and transitive dependency verification is complete in Phase 1; live advisories are re-queried on every PR/push/release run.
- PIOS search returned no applicable shared record; no Goujian project ID is known. No isolated-test PIOS output is treated as production authority.
- Company v1.3.1 upload is FAIL. Three exact `exec(` bytes occur in static detector regex strings at security_preflight.py:90,91,714; server-side attribution remains unverified.

## Architecture decisions

1. Keep `scripts/security_preflight.py` and all existing rules/tests. The new scanner orchestrates it rather than replacing it.
2. One shared package scanning entry point for local/PR/push/release. Scan a safely extracted, hash-bound snapshot of each actual runtime/source/showcase ZIP. Recheck identity before accepting evidence or publishing.
3. Cisco remains a separate development/release dependency in an isolated Python environment. Do not add scanner/LLM packages to the production runtime or Bootstrap.
4. Pin the official scanner and transitive installation artifacts; retain provenance, licenses and advisory evidence. Pin newly used Actions to audited commit references.
5. Static and behavioral checks run without model credentials. No cloud/LLM calls, repository secrets or private company data. SEMANTIC_SCAN=NOT_RUN until separately approved.
6. Default blocking threshold is HIGH/CRITICAL. Preserve raw findings. Any false-positive adjudication must be explicit, independently reviewed, tied to unchanged input content and recorded alongside raw evidence; no blanket exclusions or keyword concealment.
7. Fail closed on scanner errors, missing analyzer evidence, malformed results, input/hash drift, stale reviews and missing required release receipts. Always retain failure artifacts.
8. Negative controls must demonstrate actual third-party detection plus orchestration failure behavior; target sample source is data and is never executed.
9. PR/push workflow has minimal permissions and no fork secrets. The existing Release workflow must call the same entry on its actual ZIPs before tag/release/upload operations. A non-publishing rehearsal must exercise this path without changing old releases.
10. Required GitHub status checks must be actually configured and verified. Merge through normal protected-branch rules only after independent review and real Actions success. Do not use admin bypass or synthetic success statuses.

## Workstreams and current state

| Workstream | Executor | State | Required evidence |
|---|---|---|---|
| Official tool / dependency / real CLI audit | Qoder | COMPLETE (Phase 1) | versions, hashes, license/advisory inventory, baseline and negative scans |
| Shared package gate / negative tests | Qoder, Codex review | IMPLEMENTED, acceptance pending | fail-closed tests, real CLI results, input binding |
| PR/push + pre-publication workflow integration | Qoder, Codex review | IMPLEMENTED; `main` CI/security PASS; read-only release rehearsal FAILED at the PDF gate (21 HIGH) | immutable actions, artifact retention, release rehearsal logs |
| Functional and visual non-regression | Qoder, Codex acceptance | IN_PROGRESS | existing regressions, actual PPTX/render parity as applicable |
| Documentation + v1.3.1 regex evidence | Qoder, Codex editorial review | IMPLEMENTED, acceptance pending | exact source lines, bounded claims, operating instructions |
| PR, real CI, protection, safe merge | Qoder execution, Codex Go/No-Go | PR #1 merged (`e5a83df`); protection verified; `main` Actions PASS | commit/PR/run URLs and live protection configuration |
| Default-branch release-path rehearsal | Qoder execution, Codex acceptance | FAILED (read-only) `40506964205`: 21 HIGH PDF findings, publish SKIP | non-publishing gate success without publishing |

## Final status contract

SOURCE_AND_PACKAGE_SECURITY, CI_AND_RELEASE_GATE and COMPANY_PLATFORM_SECURITY are separate outcomes. Semantic, cross-platform visual and native PowerPoint checks remain separately reported. No NOT_RUN is converted to PASS. Company platform acceptance cannot be inferred from Cisco or GitHub Actions.

## Phase 1 acceptance (2026-10-27)

Real Cisco 2.3.1 is verified against its official wheel and upstream tag. An initial filelock 3.32.7 resolution had a HIGH advisory; the approved isolated scanner lock uses compatible filelock 3.20.3, with zero advisories across all 100 packages. Rejected evidence remains retained. Runtime dependencies do not change.

Eight raw CRITICAL findings were the initial independent-review candidates: three detector regex strings, four fixed-argv child_process imports, and one intentionally hostile input fixture. Codex subsequently audited the full unchanged v1.3.1 blocking set and approved **33 exact identities** (31 CRITICAL, 2 HIGH) in `security/review-ledger.json`, bound to rule, path, line, file SHA256, root `SKILL.md` SHA256, scanner version, policy, and the observed policy fingerprint. The ledger must not be overwritten or reset; new or changed findings require a new independent review. The third-party CLI needs an explicit HIGH threshold; its default exit status is not a gate.

Vendor coverage is bounded: static detection plus Python/Bash behavioral analysis; JavaScript behavioral dataflow and LLM semantics are NOT_RUN. Do not describe this as full semantic security. Provision the scanner separately, never redistribute its environment inside Goujian archives.

## Independent local acceptance (2026-10-27)

Codex independently ran 43 shared-gate, 12 advisory and 10 workflow tests: 65/65 passed. The frozen public runtime and a newly built clean-commit runtime passed actual Cisco scanning; the clean-commit receipt was independently re-verified. A real private negative control returned exit1 with 3 CRITICAL, 3 HIGH and 1 MEDIUM findings, without executing sample code. Five additional source-only findings in negative_skill_fixture.py:37-41 were independently proven to be AST Constant text (lines29-42) and approved with exact content identities. The ledger now has 38 reviews (34 CRITICAL, 4 HIGH); raw severity remains unchanged.

Core, skill, security_preflight.py and production dependency files are byte-unchanged from the frozen v1.3.1 baseline. Full regression, clean-install and same-host 183-PNG/18-canonical-PPTX comparison evidence is retained locally. Native PowerPoint and cross-platform visual equivalence remain NOT_RUN. The final 38-review package scans, real PR/push Actions, branch protection and non-publishing Release-path rehearsal must still be completed; these are not inferred from local tests.

## Release-path Python split (2026-10-27)

An independent pre-merge audit found that `release.yml` set up only CPython 3.11, while `security/requirements-lock.txt` is a Linux x86_64 CPython 3.14 wheel set; the PR/push security workflow already used 3.14.

The minimal fix keeps the original product CPython 3.11 setup and every product validation, build, clean-install and capability-parity step unchanged. Immediately before the isolated scanner install, `release.yml` adds a second pinned `actions/setup-python` step that selects CPython 3.14, so `python3 -m venv` creates the scanner environment required by the lock. There is no second product engine, no dependency update and no product output change. The gate and receipt logic are stdlib-only in code, but package scans and any receipt whose PDF structural facts must be recomputed run under that isolated environment; the publisher installs only the separate hash-locked `pypdf` verifier before receipt verification. Missing parser evidence fails closed.

A structural regression in `tests/test_workflow_security.py` fails if the scanner 3.14 setup stops preceding the scanner install, or if the product 3.11 setup is removed or moved after the product build. Implementation is available in this checkout; current enforcement requires actual branch-protection and Actions evidence. No PASS is claimed for CI, branch protection, the non-publishing Release-path rehearsal or company-platform acceptance.

## PDF structural review candidate (2026-10-27)

Release rehearsal `40506964205` was blocked by 21 raw HIGH `PDF_STRUCTURAL_THREAT` findings. All 21 are eligible only because their severity is `HIGH`, their rule is exactly `PDF_STRUCTURAL_THREAT`, their `line_number` is null, and their metadata is exactly `{"/OpenAction": 1}`. Raw severity, raw JSON/SARIF and all 38 ledger reviews remain unchanged.

The candidate adds `scripts/pdf_structural_check.py`, a bounded deterministic checker using the official `pypdf` 6.21.3 wheel (`c8ca4d9a360dbd5d4b9bb7a8389e2a9ae6a106bee722b496f918040ba2daa17e`, BSD-3-Clause) from the separate one-package lock `security/pdf-parser-requirements.txt`. The checker is pinned by SHA256 `f55536fe1f3823a183463e8cbe4f22e30930e8bdc2934a72267af8c384c7b66e`. It parses the unchanged PDF strictly, inspects classic-xref and object-stream objects including unused/compressed objects, and passes only the exact direct local-page `/XYZ null null 0` destination with no action dictionary, attachment/media/embedded-file value, forbidden key, other `/OpenAction`, unsupported `/A` context, invalid StructElem layout attribute, warning, encryption, ambiguous xref, duplicate key or resource overrun. Child resource limits are observed and recorded, and a forged caller cannot substitute benign metadata: the checker re-derives facts from the bytes.

Local proof on the exact 21 files: 21/21 PASS under the strict facts contract, 6932 objects inspected (maximum 1037), zero parser warnings, zero action dictionaries, zero forbidden object values, zero unsupported/invalid `/A`, and 21/21 direct local-page exact shapes. The three independent Codex adversarial probes still exit 1 with `FORBIDDEN_ACTION_KEY`/`FORBIDDEN_OBJECT_VALUE`, `FORBIDDEN_OBJECT_VALUE`, and `UNSUPPORTED_A_CONTEXT`. The independent facts probe now rejects all five cases: missing checks, contradictory proof counts, unknown checks, nonzero checker exit with PASS facts, and a failed resource-limit launch. The real-parser suite passes 47/47; gate + advisory + workflow + PDF suites pass 116/116 under the PDF environment; ordinary `npm test` was not rerun because no product-runtime bytes changed.

Four preapproval blockers found by independent review were fixed in the wrapper without changing the checker or the policy: `run_bounded(limits=...)` fails closed when the resource module, a required `RLIMIT` or `setrlimit` is unavailable and never loosens zero or stricter soft limits; `validate_pdf_facts` requires the exact complete 18-name check set plus typed, mutually consistent parsed/proof/open-action/dangerous facts and identity pins; `run_pdf_checker` refuses to approve facts from a child that did not complete with exit code 0; and PDF receipt sections now bind checkout-relative logical paths and hashes, with actual invocation locations kept only as provenance, so a receipt scans in one checkout and verifies in a differently rooted one.

The tracked policy `security/pdf-structural-policy.json` remains `PENDING_CODEX_REVIEW`. Qoder did not approve it, did not edit any ledger, and did not set any raw severity. A pending policy leaves every finding blocking; any checker/parser/policy identity drift, missing parser, error or forged facts fails closed. The candidate itself has not been pushed and has not run in CI; local evidence is not CI evidence. Independent Codex review must decide the policy first. The full local visual showcase was regenerated from the pinned v1.2.1 baseline with fingerprint `9d20bb5fcfb8c50915dafdbc59669f14897cc89bbc806e74c8f313cfa7a84f5b`; rendered PNG bytes are unchanged.
