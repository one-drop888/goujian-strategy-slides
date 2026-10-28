# Goujian Strategy Slides v1.3.2

**Enterprise runtime optimization patch｜企业运行时优化补丁**

This file is part of the complete source archive. The installed runtime omits release packaging and security-preflight tooling, so it links here through the public repository rather than shipping a local copy.

## 简体中文

V1.3.2 是企业运行时优化补丁。它不改变产品能力、原生图表、数值语义、艺术方向或历史验收证据，重点是让官方运行时只保留生产运行所需内容，并把发布与开发工具明确交给完整源码包。

主要变化：

- 运行时仅移出 4 个源码专用成员：`scripts/package_runtime.py`、`scripts/security_preflight.py`，以及两个敌意来源负向夹具 `skill/reasoning/fixtures/hostile-source/plan.json` 和 `skill/reasoning/fixtures/hostile-source/sources/hostile.md`。完整源码包保留这些工具、夹具和全部负向行为测试。
- 运行时明确声明 185 个文件，加上由 `distribution/runtime-package.json` 映射的 `package.json`，共 186 个成员。其余生产模块、Schema、配方、注册表、QA/渲染/字体/图片/Reasoning 资产与校验测试保留。
- 命令归属迁移：运行时不再提供 `package` 和 `preflight`，并在运行时清单中声明为省略；完整源码包保留 `package`、`package:source`、`package:showcase`、`preflight`、`security:scan`、`security:verify` 和 `test:pdf`。运行时仍提供 `test`、`test:core` 和 `validate:all`。
- 已安装运行时仍可确定性重建。源码打包器新增 `--runtime-root` 数据模式与 `--expect-sha256`：它把已安装运行时当作数据读取，不导入或执行目标目录中的工具；校验批准源码清单与运行时 `package.json` 身份，拒绝额外、缺失、符号链接或被篡改的成员及不安全输出位置，并断言重建 ZIP 的 SHA256 与原始运行时一致。`--source` 和 `--showcase` 与运行时根同时使用会被拒绝。
- 复用现有能力对等引擎，新增固定的 `CAPABILITY_PARITY_V1_3_1_TO_V1_3_2` 契约。它以冻结的 v1.3.1 提交与安装包为基线，并校验锁定的安装包 SHA256 `7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd`。原 v1.3.0→v1.3.1 契约与默认行为保持不变；CI 与 Release 同时运行两个契约，并保留 v1.2.1 历史回归。
- 版本、锁文件根版本、Skill 元数据和运行时元数据更新为 1.3.2。无依赖升级，无 JSON Spec 格式变化，不新增 HTML 或 Pro 功能。
- 预检与打包器的检测规则、Python AST 可执行风险判断、依赖/元数据/映射与严格清单语义保持不变；新增的只是按画像区分的必需文件与命令守卫。运行时不再携带发布工具，完整源码包继续保留发布安全门和 PDF 结构检查。
- 安全结论保持有界：本说明对应本地实现提交。发布安全门必须针对候选包重新运行并由独立复审更新绑定；v1.3.1 的既有批准绑定于冻结内容，不能自动延续。完整构建、真实扫描、干净安装与能力对等验证尚未执行，因此不宣称发布验证通过。公司平台与 Agensi 仍未实际验收：`COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`；公开静态预检 PASS 不等于企业平台批准。历史 v1.3.1 文档、tag 与 release 不被改写。

版本与契约细节见[安装与恢复](INSTALLATION.md)、[变更记录](../CHANGELOG.md)和[发布安全门](RELEASE_SECURITY_GATE.md)。历史 v1.3.1 安全与能力对等记录仍见 [SECURITY_PARITY_V1_3_1.md](SECURITY_PARITY_V1_3_1.md)。

## English

V1.3.2 is an enterprise runtime optimization patch. It does not change product capabilities, native charts, numeric semantics, art direction or historical acceptance evidence. It keeps the official runtime to what production execution needs and assigns release and development tooling explicitly to the complete source archive.

- Exactly four source-only members leave the runtime: `scripts/package_runtime.py`, `scripts/security_preflight.py`, and the hostile-source negative fixtures `skill/reasoning/fixtures/hostile-source/plan.json` and `skill/reasoning/fixtures/hostile-source/sources/hostile.md`. The complete source archive retains these tools, fixtures and all negative-behaviour tests.
- The runtime explicitly declares 185 files; with the `package.json` mapped from `distribution/runtime-package.json`, the archive has 186 members. Every other production module, schema, recipe, registry, QA/render/font/image/Reasoning asset and validation test remains.
- Command ownership moved: the runtime no longer provides `package` or `preflight` and declares them omitted, while the complete source archive retains `package`, `package:source`, `package:showcase`, `preflight`, `security:scan`, `security:verify` and `test:pdf`. The runtime still provides `test`, `test:core` and `validate:all`.
- An installed runtime remains deterministically rebuildable. The source packager adds a data-only `--runtime-root` mode with `--expect-sha256`: it reads the installed runtime as data and does not import or execute tools from the target root. It verifies the approved source manifest and runtime `package.json` identity, rejects extra, missing, symlinked or tampered members and unsafe output locations, and asserts that the rebuilt ZIP matches the original runtime SHA256. Combining `--source` or `--showcase` with a runtime root is rejected.
- The existing capability-parity engine gains the fixed `CAPABILITY_PARITY_V1_3_1_TO_V1_3_2` contract. It uses the frozen v1.3.1 commit and installer as baseline and verifies the locked installer SHA256 `7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd`. The original v1.3.0→v1.3.1 contract and default behaviour are unchanged; CI and Release run both contracts and retain the v1.2.1 historical regression.
- Version, lockfile root, Skill metadata and runtime metadata are now 1.3.2. No dependencies were upgraded, no JSON Spec format changed and no HTML or Pro feature was added.
- Preflight and packager detection rules, Python AST executable-risk classification, and dependency/metadata/mapping/strict-manifest semantics are unchanged; only required-file and command guards became profile-appropriate. The runtime no longer carries release tooling, while the source archive keeps the release security gate and PDF structural checker.
- Security claims stay bounded: this note describes a local implementation commit. The release security gate must run again for the candidate and an independent review must update its bindings; v1.3.1 approvals are bound to that frozen content and do not carry over automatically. The full build, real scans, clean install and capability-parity run have not been executed, so no release-validation PASS is claimed. Company-platform and Agensi acceptance remain unverified (`COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`); a public static preflight PASS is not enterprise-platform approval. Historical v1.3.1 documents, tags and releases are not rewritten.

See [installation and recovery](INSTALLATION.md), the [changelog](../CHANGELOG.md) and the [release security gate](RELEASE_SECURITY_GATE.md) for the version and contract details. The historical v1.3.1 security and capability-parity record remains in [SECURITY_PARITY_V1_3_1.md](SECURITY_PARITY_V1_3_1.md).
