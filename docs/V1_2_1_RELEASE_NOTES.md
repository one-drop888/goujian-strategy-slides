# Goujian Strategy Slides v1.2.1 — Release Notes / 发布说明

**Status: security-scanner compatibility patch for the documented workflow.** The engine, JSON contract, rendering, reasoning, themes, specifications and examples are unchanged from v1.2.0. Public tags and GitHub Releases are created only by the approved `workflow_dispatch` release task. This document does not claim that company-platform upload, import or scanning has passed.

**状态：文档化工作流的安全扫描兼容补丁。** 引擎、JSON 契约、渲染、推理、主题、规范与示例相对 v1.2.0 均未改变。公开标签与 GitHub Release 只由获批的 `workflow_dispatch` 发布任务创建；本文不声称公司平台的上传、导入或扫描已经通过。

## English

### Changes

- Replaced the Doctor's unnecessary dynamic datetime import with an ordinary static import. The generated timestamp keeps the same timezone-aware ISO 8601 representation with seconds precision (for example `2026-10-21T15:05:19+08:00`).
- Added a regression test covering timezone awareness, seconds precision, round-trip formatting and timestamp freshness. The added regression introduces no scanner-trigger call literal.
- Updated `package.json`, lockfile root versions, root `SKILL.md` metadata, release automation and current README installer references to 1.2.1.
- No dependency versions changed. No file under `core/`, `skill/` or `adapters/` changed; rendering, reasoning, themes, specification and example bytes remain identical to v1.2.0.

### Artifacts

- `goujian-strategy-slides-v1.2.1.zip` — lightweight runtime, one root `SKILL.md`, no PPTX or build caches.
- `SHA256SUMS.txt` — installer checksum.
- No showcase ZIP is rebuilt or published for this patch. The optional v1.2.0 showcase remains a separate historical review artifact.

### Verification and limits

- Full `npm test` passed at version 1.2.1, including the new timestamp regression.
- Example chain: spec validation `PASS`; native build 8 slides; QA `PASS_WITH_NOTES` with render `PASS`; visual review `NOT_RUN`.
- `npm run benchmark -- --render`: 15/15 scenarios `PASS_WITH_NOTES`, render checks `PASS`, visual review `NOT_RUN`.
- Real clean-install bootstrap integration passed 9/9, including Unicode/space path installation, isolated `.venv`, rerun skips and interpreter repair.
- Local installed-ZIP audit found the reported dynamic datetime import absent. Other dynamic module loads use fixed repository-local paths and are documented separately; the audit does not certify an external scanner or company-platform result.
- Company-platform upload, import and security scanning: `NOT_VERIFIED`. No PASS claim is made.
- Native Microsoft PowerPoint on macOS/Windows/ARM64 remains `NOT_RUN`; the executed host is Linux x86_64.

### Upgrade

Replace the installed folder with the new ZIP; do not merge over an old directory. Preserve custom specs and assets outside the folder, then run `npm run bootstrap`, `npm run doctor -- --json` and `npm test`. Installer behavior and the JSON contract are unchanged.

## 中文

### 主要变化

- 将 Doctor 中不必要的 datetime 动态导入替换为普通的静态导入。生成的时间戳保持原有格式：带时区的 ISO 8601、精确到秒（例如 `2026-10-21T15:05:19+08:00`）。
- 新增回归测试，覆盖时区信息、秒级精度、往返格式与时间戳新鲜度；新增测试未引入扫描器触发的调用写法。
- 将 `package.json`、lockfile 根版本、根目录 `SKILL.md` 元数据、发布自动化与当前 README 安装包引用更新为 1.2.1。
- 依赖版本未变；`core/`、`skill/` 与 `adapters/` 下没有任何文件变化，渲染、推理、主题、规范与示例字节均与 v1.2.0 一致。

### 交付物

- `goujian-strategy-slides-v1.2.1.zip` — 轻量运行时，一个根目录 `SKILL.md`，无 PPTX 或构建缓存。
- `SHA256SUMS.txt` — 安装包校验和。
- 本次不重新构建或发布展示 ZIP；可选的 v1.2.0 展示包仍是独立的历史复核资产。

### 验证与边界

- 版本 1.2.1 下完整 `npm test` 通过，包括新增的时间戳回归测试。
- 示例链路：Spec 校验 `PASS`；原生构建 8 页；QA `PASS_WITH_NOTES`，渲染 `PASS`；视觉复核 `NOT_RUN`。
- `npm run benchmark -- --render`：15/15 场景 `PASS_WITH_NOTES`，渲染检查 `PASS`，视觉复核 `NOT_RUN`。
- 真实干净安装 bootstrap 集成测试 9/9 通过，覆盖 Unicode/空格路径、隔离 `.venv`、重复运行跳过与解释器修复。
- 对本地安装 ZIP 的审计确认用户报告的 datetime 动态导入已不存在。其他动态模块加载均使用固定的仓库内路径并单独记录；该审计不构成外部扫描器或公司平台结果的认证。
- 公司平台上传、导入与安全扫描：`NOT_VERIFIED`，不作 PASS 声明。
- macOS/Windows/ARM64 原生 Microsoft PowerPoint 仍为 `NOT_RUN`；实际执行主机为 Linux x86_64。

### 升级

用新 ZIP 替换已安装文件夹，不要覆盖合并旧目录。保留目录外的自定义 Spec 与资产，然后运行 `npm run bootstrap`、`npm run doctor -- --json` 与 `npm test`。安装行为与 JSON 契约未变。
