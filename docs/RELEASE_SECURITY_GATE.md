# Release Security Gate / 发布安全门

Status: **PR #1 is merged on `main` at `e5a83df`; all `main` CI/security checks
PASS. The read-only release rehearsal `40506964205` FAILed at the security gate
with 21 raw HIGH `PDF_STRUCTURAL_THREAT` findings, and its write-capable publish
job was SKIPped. The PDF structural policy remains `PENDING_CODEX_REVIEW`; the
PDF candidate changes in this checkout have not run in CI.**
This document describes the permanent package security gate. It does not claim a
security clearance. Company-platform acceptance is separately tracked.

状态：**PR #1 已合并到 `main`（`e5a83df`），`main` 的全部 CI/安全门检查为 PASS。
只读 Release 演练 `40506964205` 在安全门处因 21 个原始 HIGH
`PDF_STRUCTURAL_THREAT` 发现而 FAIL，具备写权限的 publish 作业被 SKIP。PDF 结构策略
仍为 `PENDING_CODEX_REVIEW`；当前检出中的 PDF 候选改动尚未在 CI 运行。**
本文描述常驻的软件包安全门，不代表已获得安全认证。公司平台验收另行跟踪。

## Summary / 概述

**English.** Every shipped archive is built from an approved commit, checked by
the existing product preflight, then scanned by a pinned, hash-locked Cisco
Skill Scanner in an isolated environment. A HIGH or CRITICAL finding blocks the
release unless an independent reviewer has recorded an exact, content-bound
review. A separate, narrowly scoped PDF structural review may adjudicate only
`PDF_STRUCTURAL_THREAT` findings whose metadata is exactly
`{"/OpenAction": 1}`; it never edits raw severities. That policy is currently
`PENDING_CODEX_REVIEW`, so it does not unblock anything. Raw evidence is always
retained, and JavaScript behavioral and semantic analysis are explicitly
`NOT_RUN`.

**中文.** 每个发布包都从已批准的提交构建，先经过既有产品预检，再在隔离环境中由固定版本、
哈希锁定的 Cisco Skill Scanner 扫描。除非独立评审记录了与内容精确绑定的审查结论，否则
HIGH 或 CRITICAL 发现会阻止发布。另有一个范围很窄的 PDF 结构复核，只能裁定元数据精确为
`{"/OpenAction": 1}` 的 `PDF_STRUCTURAL_THREAT` 发现，且绝不修改原始严重级别。该策略当前为
`PENDING_CODEX_REVIEW`，不会解除任何阻断。原始证据始终保留，JavaScript 行为分析与语义分析
明确标记为 `NOT_RUN`。

## Architecture / 架构

- `scripts/security_preflight.py` — the original product preflight, retained
  unchanged. The gate invokes it as a separate process **before** the third-party
  scanner.
- `scripts/scan_skill_package.py` — the shared entry point with `scan`
  and `verify` subcommands.
- `scripts/advisory_check.py` — the shared live dependency-advisory helper used
  by local, PR, and release runs.
- `scripts/negative_skill_fixture.py` — generates the inert negative-control
  fixture in a private temporary directory from readable literal strings.
- `scripts/pdf_structural_check.py` — the bounded, real-parser PDF structural
  checker. It emits hash-bound facts and can only apply the narrow policy below.
- `scripts/pdf_negative_fixture.py` — generates a private inert PDF negative
  control containing an inert JavaScript action dictionary.
- `security/pdf-parser-requirements.txt` — the separate, single-package
  hash-locked `pypdf` wheel used only by the PDF checker. It is **not** part of
  the 100-package scanner lock and is **not** in the product runtime or
  Bootstrap.
- `security/pdf-structural-policy.json` — the tracked PDF policy. Its current
  status is `PENDING_CODEX_REVIEW`; only an independent Codex review may change
  that status.
- `tests/test_pdf_structural_review.py` — real-parser positive/negative tests,
  including attachment, embedded-file, spoofed `/A`, indirect, escaped,
  compressed, encrypted, malformed, resource-limit and forged-metadata cases.
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
.venv-security/bin/python -m pip install \
  --require-hashes --only-binary=:all: \
  --index-url https://pypi.org/simple \
  -r security/pdf-parser-requirements.txt
.venv-security/bin/skill-scanner --version   # expects 2.3.1
.venv-security/bin/python -c "import pypdf; print(pypdf.__version__)"  # 6.21.3
.venv-security/bin/python -m unittest tests.test_pdf_structural_review -v
```

`npm run test:pdf` runs the same suite, but only when `python3` resolves to the
isolated scanner environment above. The product runtime and the ordinary
`npm test` suite do not import or require `pypdf`.

`scan` resolves the scanner from `--scanner` when given, otherwise from
`.venv-security/bin/skill-scanner`; there is no task-specific default path.

Build and scan an actual archive (never scan a working tree):

```bash
python3 scripts/package_runtime.py dist/goujian-strategy-slides-v1.3.1.zip --json
sha="$(sha256sum dist/goujian-strategy-slides-v1.3.1.zip | cut -d' ' -f1)"
.venv-security/bin/python scripts/scan_skill_package.py scan dist/goujian-strategy-slides-v1.3.1.zip \
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
.venv-security/bin/python scripts/scan_skill_package.py verify out/security-gate/runtime/receipt.json \
  --archive dist/goujian-strategy-slides-v1.3.1.zip \
  --version 1.3.1 --commit "$(git rev-parse HEAD)" --repo . \
  --artifact-dir out/security-gate/runtime
```

`verify` needs no scanner, model keys, or network. It re-extracts the archive,
recomputes the tree, re-reads every raw report, and re-evaluates the review
ledger. It also:

- recomputes the Git-blob source identity at the approved commit and rejects any
  archive from another commit or with changed bytes, even if internally
  consistent;
- requires the complete named check set (no missing or unrecognized checks),
  each with status `PASS`;
- re-runs the PDF structural checker on the exact extracted PDF when the
  receipt has eligible PDF findings, and requires the recomputed facts to equal
  the retained facts byte-for-byte. If there are no eligible PDF findings, the
  receipt must carry an explicit `EXPLICIT_ZERO` PASS rather than `NOTRUN`;
- scopes the ledger to the current profile: reviews for files absent from this
  profile are reported as not applicable, while changed file/root-SKILL/tool/
  policy bytes make an applicable approval stale and fail the gate;
- requires the receipt's `source_tree_state` to be `clean`, because an archive
  built from a dirty tree cannot prove that it equals the named commit;
- rejects inconsistent, stale, or identity-mismatched receipts.

`verify` is therefore **stdlib-only only when no PDF facts need recomputation**.
When eligible PDF findings exist, run it with a Python that has the same
hash-locked `pypdf` wheel installed (the scanner virtual environment in CI, or
the publisher's small PDF-verifier environment). A missing parser, checker
error, pending policy, changed policy/checker/parser identity, forged facts, or
PDF hash drift always fails closed.

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

pdf_fixture_root="$(mktemp -d)"
python3 scripts/pdf_negative_fixture.py --out "$pdf_fixture_root"
pdf="$pdf_fixture_root/pdf-negative-fixture.pdf"
pdf_sha="$(sha256sum "$pdf" | cut -d' ' -f1)"
.venv-security/bin/skill-scanner scan "$pdf_fixture_root" \
  --policy low-noise --use-behavioral --format json \
  --output-json out/security-gate/negative/pdf-scanner.json \
  --fail-on-severity high   # expected to block the raw PDF finding
.venv-security/bin/python scripts/pdf_structural_check.py \
  --pdf "$pdf" --expected-sha256 "$pdf_sha" \
  --policy security/pdf-structural-policy.json \
  --out out/security-gate/negative/pdf-checker-facts.json   # expected exit 1
```

The fixtures write inert `SKILL.md`, a dangerous-looking Python sample and an
inert PDF action dictionary as **data**. Nothing in them is ever executed,
rendered or fetched.

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
10. **Narrow PDF structural review** — only `PDF_STRUCTURAL_THREAT` findings
    with severity `HIGH` and metadata exactly `{"/OpenAction": 1}` are eligible.
    The bounded checker parses the unchanged PDF with the pinned real parser,
    inspects every classic-xref and object-stream object (including unused or
    compressed objects), and passes only when the root catalog has one direct
    `/OpenAction` array of exactly `[local actual page ref /XYZ null null 0]`,
    the page belongs to the document, and the full graph has no action
    dictionary, attachment/media/embedded-file value, forbidden key, other
    `/OpenAction`, unsupported `/A` context, invalid StructElem layout
    attribute, parser warning/error, encryption, ambiguous/incremental xref,
    duplicate key, or resource-limit overrun. `pypdf` object semantics are used;
    `/S` in StructElem layout attributes and ExtGState transparency is not
    treated as an action. Any unsupported shape fails closed. The policy is
    currently pending independent approval; a pending policy leaves the finding
    blocking.

## Coverage and limits / 覆盖范围与限制

| Surface | State |
|---|---|
| Static detection (Python, JS, docs, config) | ANALYZED |
| Python behavioral analysis | ANALYZED |
| Bash behavioral analysis | ANALYZED |
| PDF structural OpenAction adjudication (narrow policy) | ANALYZED, POLICY PENDING |
| PDF rendering, execution, JavaScript or semantic behavior | **NOT_RUN** |
| JavaScript behavioral dataflow | **NOT_RUN** |
| Semantic / LLM intent and alignment | **NOT_RUN** |
| Company platform security | **NOT_VERIFIED** |

The PDF review is a deterministic structural check, not an execution sandbox.
It never renders or runs a PDF and does not claim that a PDF is harmless in
general; it proves only the exact policy shape above on the exact bytes.
PDF 复核是确定性结构检查，不是执行沙箱；它只证明精确字节满足上述策略形状，
不声称 PDF 在一般意义上无害。

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
- The PDF findings that blocked release rehearsal 40506964205 have
  `line_number: null`. A line-less finding must **not** be approved through a
  generic `"unknown line"` ledger entry. The only line-less path implemented
  here is the exact PDF structural policy: rule `PDF_STRUCTURAL_THREAT`,
  severity `HIGH`, metadata exactly `{"/OpenAction": 1}`, bound to the exact
  file SHA256 and the pinned policy/checker/parser identities. Every other
  line-less HIGH/CRITICAL remains blocking.
- A policy decision is not manual per-file approval and not a severity edit.
  When the independent review sets the policy to `APPROVED`, the gate records
  `raw_classification`, keeps the raw `HIGH` severity and raw scanner JSON/SARIF
  unchanged, labels the item `adjudicated-structural-safe`, and separately
  computes `effective_blocking`. The receipt records the policy id/SHA, checker
  SHA, parser version/wheel hash, eligible count, adjudicated count, blocking
  count, object/page facts and the hash of the exact facts file.
- The tracked policy is currently `PENDING_CODEX_REVIEW`, so even verified
  structural facts do not unblock a finding. Qoder must not set `APPROVED`.
- `verify` re-runs the checker on the exact extracted PDF and compares the
  recomputed facts with the retained facts byte-for-byte. A changed PDF, forged
  facts, changed checker/policy/parser identity, missing parser, checker error,
  pending policy or explicit-zero mismatch fails closed.
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
  pdf-review/           # one hashed facts file plus stdout/stderr per eligible PDF
    pdf-review-00.json
    pdf-review-00.stdout.log
    pdf-review-00.stderr.log
out/security-gate/advisory/
  npm-audit.json
  osv-check.json
out/security-gate/pdf-negative-control/
  fixture.json          # inert fixture manifest
  scanner.json          # raw scanner JSON for the PDF fixture
  findings.json         # extracted raw PDF findings
  checker-facts.json    # structural checker facts, expected status FAIL
  checker.stdout.log
  checker.stderr.log
```

The raw scanner JSON/SARIF and the raw HIGH findings are retained in every
case. The PDF facts files are the only machine-checked proof for eligible PDF
findings, and they are hash-bound to the exact PDF bytes, checker, policy and
parser wheel.

## CI and release flow / CI 与发布流程

- `skill-security.yml` runs on every push, pull request, and manual dispatch. It
  has `contents: read`, no fork secrets, `persist-credentials: false`, and
  immutable action pins. It installs the pinned scanner and the pinned `pypdf`
  wheel from the two hash-locked requirements files into the isolated scanner
  environment, runs the real-parser PDF suite, builds the actual runtime and
  source archives, runs the shared gate with `--repo` using that environment,
  runs the live advisory check with a pinned Node setup, runs a **real** text
  negative control generated by `scripts/negative_skill_fixture.py`, and runs a
  **real** PDF negative control generated by `scripts/pdf_negative_fixture.py`
  through both the scanner and the structural checker. It always uploads
  evidence, package hashes, and provenance (14-day retention).
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
    virtual environment, which installs both the scanner lock and the separate
    PDF lock and runs the PDF suite before any release scan. `scan` and `verify`
    in this job use that environment's interpreter, because re-verification
    recomputes PDF structural facts on the exact archives.
  - `publish` (`contents: write`, `needs: validate`) runs only when the manual
    `publish` input is the boolean `true` (default `false`). Before it
    re-verifies receipts, and before any `GH_TOKEN` is exposed to a step, it
    creates a small isolated PDF-verifier environment from the same
    `security/pdf-parser-requirements.txt` lock (not the 100-package scanner
    toolchain). It downloads this run's artifacts, re-verifies all three
    receipts and hashes against the approved commit and remote `main` with that
    interpreter, requires the manifest security section and evidence index
    hash, then reuses the existing overwrite guard, tag, publish, and
    post-publish verification steps. `security-evidence.json` is uploaded with
    the release assets.
- Receipt verification and source-identity logic use only the standard library;
  the named subprocesses do not. When a receipt contains eligible PDF findings,
  `verify` runs the real-parser checker in a bounded child and must run under a
  Python with the exact hash-locked `pypdf` wheel, or it fails closed on the
  missing parser. It never falls back to a PASS.
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

`security/pdf-parser-requirements.txt` is a separate single-package lock. Its
upgrade procedure is the same, with these additional steps: update the parser
version, official wheel SHA256, license and requirements-file SHA256 in
`security/pdf-structural-policy.json` and in the provenance/license inventories,
recompute the checker SHA256 if the checker changed, re-run the PDF suite and
the 21-file proof, and obtain a new independent policy approval. A parser or
wheel-hash change invalidates the previous approval; the policy must never be
re-blessed implicitly by a lock update.

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

### PDF structural review candidate / PDF 结构复核候选

Release rehearsal `40506964205` was blocked by 21 raw HIGH
`PDF_STRUCTURAL_THREAT` findings. Every one has `line_number: null` and metadata
exactly `{"/OpenAction": 1}`; no other rule, severity or metadata shape is
eligible. The 21 PDFs were parsed byte-for-byte with the pinned `pypdf` 6.21.3
wheel: all 21 PASS the narrow checks, 6932 objects were inspected in total
(largest file 1037), no parser warnings/recovery, no action dictionary, no
attachment/embedded-file/media/XFA value, no other `/OpenAction`, every
destination is a direct local-page `/XYZ null null 0` array, and the only `/A`
entries are StructElem layout attributes. This is a structural proof on those
exact bytes; it is not a rendering or execution sandbox.

At the initial checkpoint the policy was `PENDING_CODEX_REVIEW`, and all 21
findings remained blocking. Qoder did not approve it or change raw severities.
The independent decision below supersedes that checkpoint; it does not turn
the failed rehearsal into a successful run.

### PDF 结构复核候选

Release rehearsal `40506964205` 被 21 条原始 HIGH `PDF_STRUCTURAL_THREAT` 发现阻断。
这些发现的 `line_number` 均为 `null`，metadata 精确为 `{"/OpenAction": 1}`；
其他规则、严重级别或 metadata 形状都不在裁定范围内。上述结论仅针对这 21 个精确字节，
是结构证明，不是渲染或执行沙箱。初始检查点的策略为 `PENDING_CODEX_REVIEW`，
21 条发现均保持阻断；Qoder 未批准或修改原始严重级别。下述独立决定更新了该检查点，
但不把此前失败的演练改写为通过。

### Independent policy decision / 独立策略决定 — 2026-10-28

Codex approved the exact checker SHA256
`f55536fe1f3823a183463e8cbe4f22e30930e8bdc2934a72267af8c384c7b66e`
after reviewing the implementation and independently running 116/116 gate,
advisory, real-parser and workflow tests. An independent bounded reparse of all
21 original CI PDFs inspected 6932 objects. Five malformed-facts/process
probes and three dangerous-PDF probes were rejected; the real Cisco negative
PDF control returned CRITICAL and exit 1. Only the exact reviewed local-page
destination shape is eligible for structural adjudication. Raw HIGH findings
and JSON/SARIF are retained; any different hash, action, warning, unsupported
structure or checker failure blocks. This is not general PDF safety,
JavaScript execution analysis, or company-platform certification.

Codex 已批准与上述 SHA256 精确绑定的检查器，并独立验证 116/116 项测试、
21 份原始 CI PDF 的 6932 个对象，以及五项证据／进程反例和三项危险 PDF 反例。
真实 Cisco 恶意 PDF 对照返回 CRITICAL、退出码 1。仅已审查的本地页面定位形状
可据实裁定；原始 HIGH 与 JSON/SARIF 保留，任何异常继续阻断。这不是通用 PDF
安全、JavaScript 执行分析或公司平台认证。

The follow-up commit still needs its own actual package scans, protected-branch
Actions and non-publishing Release rehearsal. Local policy approval is not CI
or release-path acceptance.

## Licensing / 许可

The Cisco Skill Scanner is an external Apache-2.0 tool. It is installed only in
an isolated release environment and is **not** redistributed inside any Goujian
archive. Some transitive tool dependencies carry GPL/MPL licenses; they remain
confined to that isolated environment. This is not a legal block on the
unmodified, non-redistributed tool. Confirm the distribution position only if
the scanner environment itself is ever shipped to a third party.

`pypdf` 6.21.3 is a separate BSD-3-Clause tool, installed from the official
PyPI wheel whose SHA256 is pinned in `security/pdf-parser-requirements.txt`. It
is also confined to the isolated scanner/verifier environments and is **not**
in any Goujian archive, the product runtime, `package.json`, or Bootstrap. The
100-package scanner lock is unchanged; `security/scanner-provenance.json` and
`security/dependency-licenses.json` record `pypdf` under `separate_tools`, not
inside the 100-package count.

## Status contract / 状态契约

These are separate outcomes and must not be merged:

- `SOURCE_AND_PACKAGE_SECURITY` — this gate.
- `PDF_STRUCTURAL_POLICY` — `APPROVED` for the exact pinned checker after
  independent Codex review; changes require a new review. This decision is
  separate from package, CI and company-platform acceptance.
- `CI_AND_RELEASE_GATE` — the workflows above.
- `COMPANY_PLATFORM_SECURITY` — company-side acceptance, not inferred here.

Company-platform status: the old public `v1.3.1` upload remains **FAIL**; the
current compatibility submission is **BLOCKED**; the current candidate is
**NOT_VERIFIED**. Semantic, cross-platform visual, and native PowerPoint checks
remain separately reported. No `NOT_RUN` is converted to `PASS`.
