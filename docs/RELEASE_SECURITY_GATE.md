# Release Security Gate / 发布安全门

Status: **Implementation available in this checkout; current enforcement requires
actual branch-protection and Actions evidence.**
This document describes the permanent package security gate. It does not claim a
security clearance. Company-platform acceptance is separately tracked.

状态：**实现已在此代码检出中可用；当前的实际强制执行仍需真实的 branch protection 与
Actions 证据。** 本文描述常驻的软件包安全门，不代表已获得安全认证。公司平台验收另行
跟踪。

## Summary / 概述

**English.** Every shipped archive is built from an approved commit, checked by
the existing product preflight, then scanned by a pinned, hash-locked Cisco
Skill Scanner in an isolated environment. A HIGH or CRITICAL finding blocks the
release unless an independent reviewer has recorded an exact, content-bound
review. Raw evidence is always retained, and JavaScript behavioral and semantic
analysis are explicitly `NOT_RUN`.

**中文.** 每个发布包都从已批准的提交构建，先经过既有产品预检，再在隔离环境中由固定版本、
哈希锁定的 Cisco Skill Scanner 扫描。除非独立评审记录了与内容精确绑定的审查结论，否则
HIGH 或 CRITICAL 发现会阻止发布。原始证据始终保留，JavaScript 行为分析与语义分析明确
标记为 `NOT_RUN`。

## Architecture / 架构

- `scripts/security_preflight.py` — the original product preflight, retained
  unchanged. The gate invokes it as a separate process **before** the third-party
  scanner.
- `scripts/scan_skill_package.py` — the shared stdlib entry point with `scan`
  and `verify` subcommands.
- `scripts/advisory_check.py` — the shared live dependency-advisory helper used
  by local, PR, and release runs.
- `scripts/negative_skill_fixture.py` — generates the inert negative-control
  fixture in a private temporary directory from readable literal strings.
- `security/security-gate.json` — scanner pin, policy and policy fingerprint,
  required analyzers, environment allowlist, size/time limits, advisory
  endpoint, behavioral coverage disclosure.
- `security/requirements-lock.txt` — 100 fully hash-pinned wheels.
- `security/scanner-provenance.json` and `security/dependency-licenses.json` —
  official package coordinates, verified wheel hashes and declared license
  metadata for the isolated scanner. These are not a legal opinion or a
  reproducible-build attestation.
- `security/review-ledger.json` — the trusted, versioned review ledger. It holds
  thirty-eight exact, independently approved reviews (34 CRITICAL, 4 HIGH) bound
  to rule, path, line, file SHA256, root `SKILL.md` SHA256, scanner version,
  policy, and policy fingerprint. Any new or changed finding needs a new
  independent review.
- `.github/workflows/skill-security.yml` — push/PR/manual package gate.
- `.github/workflows/release.yml` — read-only validation job plus a separate,
  explicit write-only publisher job.
- `AGENTS.md` — concise repository instructions pointing future agents at this
  guide.

The scanner and its dependencies are an isolated development/release tool. They
are **never** added to the product runtime, `package.json`, or Bootstrap.

扫描器及其依赖是隔离的开发/发布工具，**绝不**加入产品运行时、`package.json` 或 Bootstrap。

## Local usage / 本地使用

The current wheel lock targets **Linux x86_64, CPython 3.14**. Use that Python
version for this separate tool; the product's Python >=3.9 support is unchanged.
Install from the lock file only, outside the product environment:

```bash
python3.14 -m venv .venv-security
.venv-security/bin/python -m pip install \
  --require-hashes --only-binary=:all: \
  --index-url https://pypi.org/simple \
  -r security/requirements-lock.txt
.venv-security/bin/skill-scanner --version   # expects 2.3.1
```

`scan` resolves the scanner from `--scanner` when given, otherwise from
`.venv-security/bin/skill-scanner`; there is no task-specific default path.

Build and scan an actual archive (never scan a working tree):

```bash
python3 scripts/package_runtime.py dist/goujian-strategy-slides-v1.3.1.zip --json
sha="$(sha256sum dist/goujian-strategy-slides-v1.3.1.zip | cut -d' ' -f1)"
python3 scripts/scan_skill_package.py scan dist/goujian-strategy-slides-v1.3.1.zip \
  --profile runtime \
  --version 1.3.1 \
  --commit "$(git rev-parse HEAD)" \
  --repo . \
  --source-tree-state "$(test -z "$(git status --porcelain)" && echo clean || echo dirty)" \
  --expected-sha256 "$sha" \
  --scanner .venv-security/bin/skill-scanner \
  --out-dir out/security-gate/runtime
```

`--source-tree-state` is a caller declaration recorded in the receipt. It is not
proof of source identity; the gate independently compares packed members against
the named commit. The output directory must be new or empty and must not be a
symlink; stale JSON/SARIF is never reused.

`scan` exits `0` only on PASS and `1` on any blocking result, tool error, missing
analyzer evidence, malformed report, or input drift. It always writes a receipt.

Before a release mutation, re-verify the receipt against the exact archive:

```bash
python3 scripts/scan_skill_package.py verify out/security-gate/runtime/receipt.json \
  --archive dist/goujian-strategy-slides-v1.3.1.zip \
  --version 1.3.1 --commit "$(git rev-parse HEAD)" --repo . \
  --artifact-dir out/security-gate/runtime
```

`verify` is stdlib-only and needs no scanner, model keys, or network. It
re-extracts the archive, recomputes the tree, re-reads every raw report, and
re-evaluates the review ledger. It also:

- recomputes the Git-blob source identity at the approved commit and rejects any
  archive from another commit or with changed bytes, even if internally
  consistent;
- requires the complete named check set (no missing or unrecognized checks),
  each with status `PASS`;
- scopes the ledger to the current profile: reviews for files absent from this
  profile are reported as not applicable, while changed file/root-SKILL/tool/
  policy bytes make an applicable approval stale and fail the gate;
- requires the receipt's `source_tree_state` to be `clean`, because an archive
  built from a dirty tree cannot prove that it equals the named commit;
- rejects inconsistent, stale, or identity-mismatched receipts.

Run the live advisory check and the negative control locally:

```bash
mkdir -p out/security-gate/advisory out/security-gate/negative
set +e
npm audit --omit=dev --json > out/security-gate/advisory/npm-audit.json
npm_status=$?
set -e
python3 scripts/advisory_check.py \
  --npm-audit-json out/security-gate/advisory/npm-audit.json \
  --npm-audit-exit-code "$npm_status" \
  --out out/security-gate/advisory/osv-check.json

fixture_root="$(mktemp -d)"
python3 scripts/negative_skill_fixture.py --out "$fixture_root"
.venv-security/bin/skill-scanner scan "$fixture_root" \
  --policy low-noise --use-behavioral \
  --format json --format sarif \
  --output-json out/security-gate/negative/scanner.json \
  --output-sarif out/security-gate/negative/scanner.sarif \
  --fail-on-severity high   # expected to exit 1 with HIGH/CRITICAL hits
```

The fixture helper writes an inert `SKILL.md` and a dangerous-looking Python
sample as **data**. Nothing in it is ever executed.

## What the gate checks / 门禁检查项

1. **Archive safety** — one root `SKILL.md`, declared prefix, POSIX-safe names,
   no duplicates or case-fold duplicates, no encryption, no symlinks or special
   modes, bounded member count/size/compression ratio, no secrets or install
   state.
2. **Source identity** — the ZIP's members are compared with the Git blobs at
   the approved commit (`git cat-file`), including the runtime mapping from
   `package.json` to `distribution/runtime-package.json` and the declared
   generated-showcase exception.
3. **Sealed input first** — the archive is copied with a bounded stream to a
   private snapshot, the expected hash is asserted, the original preflight runs
   on that snapshot, and extraction and scanning use the same snapshot; the
   original archive is re-hashed at the end.
4. **Product preflight first** — the existing `runtime`/`source`/`showcase`
   profiles must PASS and are bound to the snapshot SHA.
5. **Not execution** — the target package is extracted and scanned as data. The
   gate never imports or runs shipped code.
6. **Fixed scanner invocation** — `--policy low-noise --use-behavioral
   --format json --format sarif --output-json ... --output-sarif ...
   --fail-on-severity high`. No extra-argument passthrough, no payload-supplied
   configuration.
7. **Environment allowlist** — a fixed set of variables with temporary
   `HOME`/`TMPDIR`/cache; no model keys, proxies, or cloud/LLM flags.
8. **Report integrity** — required analyzers present, none failed, rule contract
   passed, CEL healthy (shadow suggestions are reported but do not suppress
   findings), SARIF invocation `executionSuccessful`, and result counts
   consistent with JSON.
9. **Input stability** — the snapshot and original ZIP are re-hashed and the
   extracted tree re-hashed after scanning; any drift fails the gate.

## Coverage and limits / 覆盖范围与限制

| Surface | State |
|---|---|
| Static detection (Python, JS, docs, config) | ANALYZED |
| Python behavioral analysis | ANALYZED |
| Bash behavioral analysis | ANALYZED |
| JavaScript behavioral dataflow | **NOT_RUN** |
| Semantic / LLM intent and alignment | **NOT_RUN** |
| Company platform security | **NOT_VERIFIED** |

The third-party scanner has no JavaScript dataflow analyzer, so JavaScript is
covered by static rules only. Do not describe this gate as full semantic
security. 第三方扫描器没有 JavaScript 数据流分析，JavaScript 仅有静态规则覆盖；
不得将其描述为完整的语义安全。

## Findings and review / 发现与评审

- The default blocking threshold is HIGH/CRITICAL. Raw findings are never
  deleted or rewritten.
- `scan` writes `review-proposal.json` marked `approved: false`; new proposals
  name the reviewer as `PENDING_INDEPENDENT_REVIEW`. The gate never
  self-approves.
- An approved entry must pin: rule id, exact relative path, line, file SHA256,
  root `SKILL.md` SHA256, scanner version, policy, and observed policy
  fingerprint. Wildcards, `.`/`..` paths, missing required fields, duplicates, expired
  entries, and entries for changed files are rejected.
- Real non-text findings (for example binary PNG IDAT matches) keep their
  reported line and byte offset and are recorded as non-text locations. An
  unknown HIGH/CRITICAL without an admissible exact location still blocks.
- MEDIUM and LOW findings keep their raw severity plus a triage record with
  owner, rationale, and disposition in the receipt. They are not silently
  marked `NOT_REQUIRED`; known MEDIUM/LOW triage is explicit and reviewable.

Only an independent reviewer may edit `security/review-ledger.json` after
reviewing the raw proposal and evidence. Any change to a reviewed file
invalidates its review.

## Dependency advisories / 依赖公告

`scripts/advisory_check.py` queries the public OSV `querybatch` endpoint for the
locked scanner graph, the production npm lock, and the pinned Pillow version,
and optionally validates `npm audit` output. It records the public coordinates,
request/response SHA256, start/finish timestamps, and elapsed time. Only public
package coordinates are sent; no source, prompts, keys, or private data. A
service error, timeout, malformed response, or ambiguous npm report is an
explicit FAIL, not "zero vulnerabilities". Nothing is upgraded implicitly; a lock
change requires a reviewed update.

## Failure artifacts / 失败证据

Both workflows upload evidence even on failure:

```
out/security-gate/<profile>/
  receipt.json          # gate decision, hashes, checks, findings, review matches
  preflight.json        # product preflight bound to the snapshot
  scanner.json          # raw scanner JSON
  scanner.sarif         # raw SARIF
  scanner.stdout.log
  scanner.stderr.log
  preflight.stdout.log
  preflight.stderr.log
  review-proposal.json  # proposed (never pre-approved) reviews
out/security-gate/advisory/
  npm-audit.json
  osv-check.json
```

## CI and release flow / CI 与发布流程

- `skill-security.yml` runs on every push, pull request, and manual dispatch. It
  has `contents: read`, no fork secrets, `persist-credentials: false`, and
  immutable action pins. It builds the actual runtime and source archives, runs
  the shared gate with `--repo`, runs the live advisory check with a pinned
  Node setup, runs a **real** negative control generated by
  `scripts/negative_skill_fixture.py` in a private temporary directory, and
  always uploads evidence, package hashes, and provenance (14-day retention).
- `release.yml` has two jobs:
  - `validate` (`contents: read`) runs every existing regression, benchmark,
    parity, clean-install, smoke, and preflight check, then builds and gates the
    actual runtime/source/showcase archives, runs the live advisory check, and
    re-verifies all three receipts in the non-publishing rehearsal. It then
    writes `dist/security-evidence.json` and injects a hash-bound `security`
    section into `dist/release-manifest.json`. The unchanged product validation,
    build, clean-install and capability-parity steps keep the original CPython
    3.11 setup. Immediately before the isolated scanner install, a second pinned
    `actions/setup-python` step selects CPython 3.14 for the hash-locked scanner
    virtual environment. The shared gate, preflight and receipt verification are
    stdlib-only; the publisher keeps its existing stdlib verification.
  - `publish` (`contents: write`, `needs: validate`) runs only when the manual
    `publish` input is the boolean `true` (default `false`). It downloads this
    run's artifacts, re-verifies all three receipts and hashes against the
    approved commit and remote `main`, requires the manifest security section
    and evidence index hash, then reuses the existing overwrite guard, tag,
    publish, and post-publish verification steps. `security-evidence.json` is
    uploaded with the release assets.
- The default `publish=false` is a non-publishing rehearsal: the full validation,
  gate, receipt verification, and evidence binding run with no tag or Release.
- The historical `v1.3.1` tag, Release, and assets are immutable. The existing
  overwrite guard refuses to publish `v1.3.1` again.
- CI artifacts expire (14 days for the PR gate, 90 days for release
  validation). After publication, `security-evidence.json` attached to the
  Release is the durable evidence record; do not claim workflow artifacts are
  retained forever.

No GitHub status or workflow may fake a PASS. A red gate is the correct state
until reviews are independently approved.

## Lock upgrade / 锁升级

1. Resolve candidate versions from official PyPI and download wheels with
   published SHA256 hashes.
2. Re-run the advisory query (for example OSV) over the full resolved set.
3. Update `security/requirements-lock.txt` with every package and hash; update
   `required_pins` and `expected_package_count` in `security/security-gate.json`.
4. Re-run the unit suite, the local real scan, and the negative control.
5. Record the drift and the advisory result in the change review. Do not
   auto-upgrade or accept unpinned resolution.

## Known v1.3.1 evidence / 已知 v1.3.1 证据

The frozen v1.3.1 runtime ZIP is
`7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd` (190
members). The literal token `exec` immediately followed by `(` appears in static
detector regex strings at `scripts/security_preflight.py` lines 90, 91, and 714.
The original company upload failed with three reported errors involving that
same token.

**Bounded claim.** Those three source lines are a strong candidate for the
reported errors, tied to this immutable ZIP and its source. Server-side
attribution has **not** been verified. Do not state that the company server
proved those exact bytes caused the failure.

**边界声明.** 上述三行是公司上传报错的强候选，且与不可变的 v1.3.1 包及其源码绑定，
但服务端归因**尚未**验证。不得声称公司服务器已证明正是这三处字节导致失败。

## Licensing / 许可

The Cisco Skill Scanner is an external Apache-2.0 tool. It is installed only in
an isolated release environment and is **not** redistributed inside any Goujian
archive. Some transitive tool dependencies carry GPL/MPL licenses; they remain
confined to that isolated environment. This is not a legal block on the
unmodified, non-redistributed tool. Confirm the distribution position only if
the scanner environment itself is ever shipped to a third party.

## Status contract / 状态契约

These are separate outcomes and must not be merged:

- `SOURCE_AND_PACKAGE_SECURITY` — this gate.
- `CI_AND_RELEASE_GATE` — the workflows above.
- `COMPANY_PLATFORM_SECURITY` — company-side acceptance, not inferred here.

Company-platform status: the old public `v1.3.1` upload remains **FAIL**; the
current compatibility submission is **BLOCKED**; the current candidate is
**NOT_VERIFIED**. Semantic, cross-platform visual, and native PowerPoint checks
remain separately reported. No `NOT_RUN` is converted to `PASS`.
