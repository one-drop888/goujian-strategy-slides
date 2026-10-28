# Changelog

## [1.3.2] — 2026-10-29

### 企业运行时优化 / Enterprise runtime optimization

- 运行时仅移出 4 个源码专用成员：`scripts/package_runtime.py`、`scripts/security_preflight.py` 和两个敌意来源负向夹具；完整源码包保留这些工具与全部负向测试。运行时明确声明 185 个文件，加上映射的 `package.json` 共 186 个成员；其余生产模块、Schema、配方、注册表、QA/渲染/字体/图片/Reasoning 资产和校验测试保持不变。
- 命令归属迁移：运行时不再提供 `package`/`preflight`，并在运行时清单中声明为省略；源码保留 `package`、`package:source`、`package:showcase`、`preflight`、`security:scan`、`security:verify` 和 `test:pdf`。预检与打包器的必需文件/命令守卫按画像区分，检测规则、依赖/元数据/映射与严格清单语义不变。
- 源码打包器新增 `--runtime-root` 数据模式与 `--expect-sha256`：把已安装运行时当作数据读取，绑定批准源码清单与运行时 `package.json` 身份，拒绝额外、缺失、符号链接或被篡改的成员及不安全输出位置，并断言确定性重建 ZIP 的 SHA256 与原始运行时一致。CI 与 Release 的干净安装、预打标签和发布后复打包均使用源码打包器绝对路径，不在运行时内执行打包器。
- 复用现有能力对等引擎，新增固定的 `CAPABILITY_PARITY_V1_3_1_TO_V1_3_2` 契约和冻结的 v1.3.1 安装包 SHA256 校验；原 `CAPABILITY_PARITY_V1_3_0_TO_V1_3_1` 契约与默认行为保持不变。CI/Release 同时运行两个契约，并继续保留 v1.2.1 历史回归。
- 版本、锁文件根版本、Skill 元数据和运行时元数据更新为 1.3.2；产品运行依赖未变，无 JSON Spec 格式变化。隔离扫描工具改用官方兼容的 `filelock 4.2.1` 与 `litellm 1.103.10`，修复两项公开依赖告警，其余 98 项锁定依赖不变。产品能力、原生渲染、图表、数值语义、艺术方向和历史验收证据不变。
- 安全结论保持有界：发布验收以该版本冻结提交对应的安全门、干净安装、能力对等、CI 和 Release 验证产物为准，不能继承历史版本的 PASS。公司平台与 Agensi 仍未实际验收：`COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`；历史 v1.3.1 文档与发布不被改写。

- Removed only four source-only members from the runtime: `scripts/package_runtime.py`, `scripts/security_preflight.py` and the two hostile-source negative fixtures. The complete source archive retains those tools and all negative tests. The runtime explicitly declares 185 files plus the mapped `package.json`, for 186 archive members; every other production module, schema, recipe, registry, QA/render/font/image/Reasoning asset and validation test remains.
- Moved command ownership: the runtime no longer provides `package`/`preflight` and declares them omitted; the source retains `package`, `package:source`, `package:showcase`, `preflight`, `security:scan`, `security:verify` and `test:pdf`. Packager and preflight required-file/command guards are profile-appropriate; detection rules and dependency, metadata, mapping and strict-manifest semantics are unchanged.
- The source packager adds a data-only `--runtime-root` mode with `--expect-sha256`. It reads an installed runtime as data, binds it to the approved source manifest and runtime `package.json` identity, rejects extra, missing, symlinked or tampered members and unsafe output locations, and asserts that the deterministic rebuilt ZIP matches the original runtime SHA256. CI and Release clean-install, pre-tag and post-publish repackaging use the source packager by absolute path and do not execute a packager inside the runtime.
- Reused the existing capability-parity engine and added the fixed `CAPABILITY_PARITY_V1_3_1_TO_V1_3_2` contract with a locked v1.3.1 installer SHA256 check. The original `CAPABILITY_PARITY_V1_3_0_TO_V1_3_1` contract and default behaviour are unchanged; CI and Release run both and retain the v1.2.1 historical regression.
- Bumped the version, lockfile root, Skill metadata and runtime metadata to 1.3.2. No production-runtime dependency or JSON Spec format change. The isolated scanner uses the officially compatible `filelock 4.2.1` and `litellm 1.103.10` to fix two public advisories; its other 98 locked dependencies are unchanged. Product capabilities, native rendering, charts, numeric semantics, art direction and historical acceptance evidence are unchanged.
- Security claims stay bounded: release acceptance depends on security-gate, clean-install, capability-parity, CI and Release artifacts for this version’s frozen commit; historical PASS results do not carry over. Company-platform and Agensi acceptance remain unverified (`COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`), and historical v1.3.1 documents and releases are not rewritten.

## [1.3.1] — 2026-10-26

### 企业安全兼容补丁 / Enterprise security compatibility patch

- 将运行时内部路径模块加载改为普通静态导入，保留 `core/qa/spec-check.py` 兼容入口与公共符号；将固定 `node -e` 分析回读替换为静态 `core/qa/recompute_analytics.js`，将固定 `python -c` 探针替换为 `scripts/probe_env.py`。必要的字体测量、Pillow、LibreOffice/Poppler、fontconfig 和锁定依赖安装仍以已知可执行文件与参数数组显式执行，并补充超时与有界输出。
- 主安装 ZIP 改为精简运行时，新增完整源码/开发 `-source` ZIP 与可选 `-showcase` 评审包。运行时 `npm test`/`test:core` 执行真实的已安装运行时冒烟，并披露未执行的可选图片步骤；完整源码包保留原有全量测试与基准工作流。运行时 `package.json` 由版本化的 `distribution/runtime-package.json` 显式映射，运行时清单逐文件声明，只有该映射允许与提交字节不同。
- `scripts/security_preflight.py` 增加 runtime/source/legacy 画像，扫描最终 ZIP 的全部文本成员，输出成员、行号、上下文、分类与用途；区分可执行代码、惰性字符串/注释、文档和配置，并分别报告 `wxect` 精确/大小写不敏感字面量。危险的动态模块加载、动态 `require`、shell 字符串和固定内联载荷在运行时被拒绝；受控参数数组与固定静态模块保持透明。旧 v1.3.0 基线仍可按 legacy 结构画像审计。
- 新增静态导入、静态分析和静态探针回归测试、别名/绕过负向测试、运行时/源码/基线三种画像预检和 `CAPABILITY_PARITY_V1_3_0_TO_V1_3_1` 对等验证入口。版本、锁文件、Skill 元数据、运行时元数据更新为 1.3.1；补充中英双语补丁说明、安装契约和安全/对等文档。
- 未改变产品能力、原生渲染、图表、数值语义、艺术方向或历史验收证据；无依赖升级。Apache-2.0 与第三方说明保留。公司平台上传/安全与 Agensi 仍未实际验收：`COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`。未知公司扫描规则不能由公开静态预检 PASS 推断；旧 tag/release 不被覆盖。

- Replaced runtime internal path-module loading with ordinary static imports while retaining the `core/qa/spec-check.py` compatibility entry and its public symbols. Replaced the fixed `node -e` analytics readback with the static `core/qa/recompute_analytics.js` and the fixed `python -c` probes with `scripts/probe_env.py`. Necessary font measurement, Pillow, LibreOffice/Poppler, fontconfig and locked dependency installation remain explicit, using known executables and argument arrays with added timeouts and bounded output.
- The primary installer is now the minimal runtime. Added a complete source/development `-source` ZIP and an optional `-showcase` review archive. Runtime `npm test`/`test:core` run a real installed-runtime smoke and disclose optional image steps that did not run; the source archive retains the original full test and benchmark workflow. Runtime `package.json` is explicitly mapped from versioned `distribution/runtime-package.json`, and the runtime manifest declares every file; only that mapping may differ from committed bytes.
- `scripts/security_preflight.py` now supports runtime/source/legacy profiles over every text member of the final ZIP, recording member, line, context, classification and purpose. It separates executable code from inert strings/comments, documentation and configuration, and reports the `wxect` literal both exactly and case-insensitively. Dangerous dynamic module loading, dynamic `require`, shell strings and fixed inline payloads are rejected in the runtime; controlled argument arrays and fixed static modules remain transparent. The archived v1.3.0 baseline remains auditable under the legacy structural profile.
- Added regression tests for static imports, static analysis and probes; alias/bypass negatives; runtime/source/baseline preflight profiles; and the `CAPABILITY_PARITY_V1_3_0_TO_V1_3_1` parity entry. Bumped version, lockfile, Skill metadata and runtime metadata to 1.3.1; added bilingual patch notes, installation contract and security/parity documentation.
- Product capabilities, native rendering, charts, numeric semantics, art direction and historical acceptance evidence are unchanged; no dependencies were upgraded. Apache-2.0 and third-party notices are retained. Company-platform upload/security and Agensi remain unverified: `COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`. An unknown company scanner rule cannot be inferred from a public static preflight PASS, and no old tag/release is replaced.

## [1.3.0] — 2026-10-26

### Analytical and visual intelligence

- Added optional typed numeric contracts, shared formatting and explicit fraction/percent/pp/currency scale handling across native charts and text. Preserved raw facts and recorded display normalization.
- Added role/category/value encoding, stable series identity, dash/marker distinctions and native legend/format/workbook readback checks. Histogram bins are explicit; unsupported families are rejected.
- Added a declared narrative graph with evidence bindings, coverage and cross-slide redundancy candidates; useful summaries and detail are retained for review.
- Expanded measured title candidates within a readable floor, preserved authored category labels and missing temporal positions, and separated pie shares from stored-percent value formats.
- Added date-scaled native timelines and bounded acyclic branch/swimlane graphs, reusing the PPTX engine.
- Tightened numerical reconciliation and output-path protection; updated full-ZIP static preflight and kept the V1.2.1 static Doctor import fix.
- Updated fast-uri to3.1.9 and the secure optional image tier to Pillow13/Python3.11+. Python3.9/3.10 retain a core-only tier; no vulnerable fallback is installed.
- Added a96-cell light/dark chart matrix, three same-input V1.2.1 comparisons, synthetic business/narrative fixtures and actual render previews. Independent review scope is documented separately from automated QA.
- Updated bilingual product/installation/migration documentation. Community stays Apache-2.0; Pro is separate design work, not a paid product launch. Company/Agensi approval and native Windows/macOS PowerPoint are not claimed.


## 1.2.1 — 2026-10-21

- Replace the Doctor's dynamic datetime import with an ordinary static import while preserving the timezone-aware ISO 8601 timestamp with seconds precision. Add a regression test for timezone awareness, second precision and freshness.
- Update package, lockfile root, Skill metadata and release automation to 1.2.1. Add bilingual v1.2.1 release notes and current installer references.
- Security-scanner compatibility patch only: no dependency changes and no changes to core or skill rendering, reasoning, themes, specification or example bytes. Company-platform upload and scanning are not claimed as passed; independent ZIP acceptance remains separate.

## 1.2.0 — 2026-10-21

- Add the optional Agent-authored Reasoning Plan: sources, claims, content dispositions, deterministic calculations, JSON-Pointer numeric bindings, coverage/dependency validation and theme decisions. Compile to native PPTX, exported spec, hash-bound scene, reasoning sidecar, embedded report and claim-linked notes.
- Support `sum`, `difference`, `ratio` and `percent_change` with explicit unit/metric/time-window/denominator checks. JSON source values can be verified against source bytes; unstructured and native-PPTX ledgers remain reviewer-required. No causal, significance, OCR or autonomous reasoning claims.
- Add theme precedence and conflict records, including explicit dark selection; build light/brand-blue/dark variants and an eight-type dark native-chart diagnostic.
- Add final exact-byte verification against a trusted expected PPTX hash, plus native chart/table/KPI/notes and embedded-report checks.
- Correct the Q4 summary orphan-word wrap and the overlong multimodal business subtitle in synthetic fixtures; preserve all six action IDs/groups and move detailed backend limits to claims, notes and appendix.
- Add the eight-case optional showcase with actual LibreOffice renders, inputs, exported specs, QA, before variants, review records, source-PPTX inspection and hash manifests.
- Add deterministic single-SKILL packaging with fixed ordering/timestamps/permissions, safe-path checks, no caches/PPTX, and a separate showcase artifact. Add package tests and doctor/bootstrap/recovery evidence.
- Replace the release workflow with manual approved-SHA dispatch, exact-SHA checkout, clean tests/build/benchmark/doctor/package, deterministic rebuild check, immutable annotated tag and no existing-asset/history overwrite. Publication is not performed by this changelog.
- Update bilingual README/product/feasibility docs, architecture, reasoning-plan reference, QA ladder, migration, benchmarks A–J, commercial readiness and third-party notices. No dependency version upgrades; historical release documents remain unchanged.

## 1.1.1 — 2026-10-16

- Reject contradictory primary-metric trend observations and separately supplied previous-month/year baselines before calculating or building.
- Add permanent cross-period baseline regression; retain all V1.1 native/editable, multimodal, analytical and visual capabilities.
- Preserve published v1.1.0 tag/assets; no dependency upgrades. See the v1.1.0 Release Notes for the disclosed input-validation limitation.

## 1.1.0 — 2026-10-16

- Native raster asset schema/pipeline, protected evidence cropping, focal point/opacity/masks, provenance and four reusable multimodal compositions. No python-pptx image postprocessing.
- Measured title/subtitle flow, bounded title rewriting, balanced wrapping, typography-scaled divider gaps and explicit header-capacity rejection.
- Hash-bound native scene records, semantic/spatial QA, local contrast resolution, font substitution reporting and spec-local profile resolution.
- Existing PPTX inspection now maps native text, pictures, tables, charts, groups and master/layout candidates with source identities; complex reconstruction remains partial.
- Six-KPI scorecard and nine-column native tables preserve all data; redundant renderer slices removed. Context-aware analytical-series repetition.
- Permanent A–H/Unicode/native ingestion regressions, fifteen rendered scenarios, six-deck visual repair/attestation evidence and fifteen-profile visual comparison.
- Three runnable analytical families cover 18 business/sales/project tasks with explicit units/windows, mature cohort denominators, optional trial behavior, missing data, reconciliation, native numeric fidelity checks and explicit pagination.
- Integrated dashboard and decision variants, local alpha-composited soft hero scrims and corrected native table padding; no profile/template count expansion.
- Retained product identity, one root Skill entry, JSON compatibility for legacy accepted specs and Apache-2.0 notices.


## 1.0.1 — 2026-10-15

Patch release for Skill installation compatibility; presentation capabilities and the JSON spec contract are unchanged.

- Kept the repository-root `SKILL.md` as the sole Skill entry in source and the installable ZIP. The `skill/` runtime library remains intact.
- Rewrote the Skill metadata description in clear Chinese, with existing PPTX and visual-review limits preserved in the instructions.
- Clarified a renderer cleanup comment that could be misread by static prompt-injection scanners; cleanup conditions and scope are unchanged.
- Made packaging reject duplicate Skill entries and added a distribution regression test.
- Revalidated source tests, the ten benchmark scenarios, installation from the ZIP, and the release checksum workflow. Company-platform import and scanning require a separate platform-side retest.

## 1.0.0 — 2026-10-14

First public release of Goujian Strategy Slides / 构见·战略演示.

- Management vocabulary: 28 storylines, 78 catalog entries (65 implemented / 6 partial / 7 designed), 23 composition recipes, 15 profiles, 15 template recipes.
- Native editable PPTX generation, ten synthetic benchmark scenarios and a composition fixture gallery.
- Final visual optimization: readable typography, restrained hierarchy, quantitative funnels, indexed comparisons, deliberate table styling and open comparison/portfolio layouts.
- Removed silent item truncation from the accepted contract and rejected unsupported chart semantics; corrected misleading synthetic example claims.
- Executed JSON Schema, payload boundaries, stronger geometry/font checks, isolated rendering, timeouts and hash-bound visual records.
- Existing-deck text edits preserve sources; reference profile generation remains best effort.
- Reproducible dependencies, packaging, CI/release workflow and bilingual product/feasibility documentation.

Compatibility note: valid legacy types remain routed. Payloads that previously rendered misleading fallbacks or silently dropped content can now fail with actionable errors. Wide 16:9 canvas only.

## 0.1.0 (pre-publication)

Initial renderer-oriented proof of concept. This is historical context, not a separate published release.
