# Permanent release security gate — control record

Owner and independent acceptance: Codex. Engineering executor: Qoder CN CLI.

## Baseline and scope

- Frozen public v1.3.1: `25f269f8db333e27f23915ecb472eed6cb2709c6`.
- Official runtime SHA256: `7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd`.
- Historical tag, Release and assets must not change. No version bump or new Release is authorized by gate completion alone.
- Product runtime, renderers, numeric semantics, fonts/images, analysis and QA retain their existing capabilities.
- This control file tracks engineering decisions. Raw local logs stay in ignored `out/security-gate-control/`; CI archives its own reports on success and failure.

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
| PR/push + pre-publication workflow integration | Qoder, Codex review | IMPLEMENTED locally, Actions NOT_RUN | immutable actions, artifact retention, release rehearsal |
| Functional and visual non-regression | Qoder, Codex acceptance | IN_PROGRESS | existing regressions, actual PPTX/render parity as applicable |
| Documentation + v1.3.1 regex evidence | Qoder, Codex editorial review | IMPLEMENTED, acceptance pending | exact source lines, bounded claims, operating instructions |
| PR, real CI, protection, safe merge | Qoder execution, Codex Go/No-Go | PENDING (no GitHub writes) | commit/PR/run URLs and live protection configuration |
| Default-branch release-path rehearsal | Qoder execution, Codex acceptance | PENDING (local rehearsal only) | actual pre-publication gate success without publishing |

## Final status contract

SOURCE_AND_PACKAGE_SECURITY, CI_AND_RELEASE_GATE and COMPANY_PLATFORM_SECURITY are separate outcomes. Semantic, cross-platform visual and native PowerPoint checks remain separately reported. No NOT_RUN is converted to PASS. Company platform acceptance cannot be inferred from Cisco or GitHub Actions.

## Phase 1 acceptance (2026-10-27)

Real Cisco 2.3.1 is verified against its official wheel and upstream tag. An initial filelock 3.32.7 resolution had a HIGH advisory; the approved isolated scanner lock uses compatible filelock 3.20.3, with zero advisories across all 100 packages. Rejected evidence remains retained. Runtime dependencies do not change.

Eight raw CRITICAL findings were the initial independent-review candidates: three detector regex strings, four fixed-argv child_process imports, and one intentionally hostile input fixture. Codex subsequently audited the full unchanged v1.3.1 blocking set and approved **33 exact identities** (31 CRITICAL, 2 HIGH) in `security/review-ledger.json`, bound to rule, path, line, file SHA256, root `SKILL.md` SHA256, scanner version, policy, and the observed policy fingerprint. The ledger must not be overwritten or reset; new or changed findings require a new independent review. The third-party CLI needs an explicit HIGH threshold; its default exit status is not a gate.

Vendor coverage is bounded: static detection plus Python/Bash behavioral analysis; JavaScript behavioral dataflow and LLM semantics are NOT_RUN. Do not describe this as full semantic security. Provision the scanner separately, never redistribute its environment inside Goujian archives.
