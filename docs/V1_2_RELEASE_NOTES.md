# Goujian Strategy Slides v1.2.0 — Release Notes / 发布说明

**Status: READY WITH KNOWN LIMITATIONS for the documented Agent-assisted workflow.** Public tag and GitHub Release are created only by the approved `workflow_dispatch` release task. This document does not claim that publication has occurred; final independent visual acceptance has been completed within the stated scope, and publication remains a separate gate.

**状态：文档化 Agent 辅助工作流的 READY WITH KNOWN LIMITATIONS。** 公开标签与 GitHub Release 只由获批的 `workflow_dispatch` 发布任务创建；本文不代表已经发布，最终独立视觉验收已在声明范围内完成，公开发布仍是独立门禁。

## English

### Highlights

- **Reasoning Plan:** Agent-authored sources, claims, dispositions, calculations, numeric bindings and theme decisions are validated before compilation. Compilation emits the native PPTX, exported spec, hash-bound scene, reasoning sidecar, embedded report and claim-linked speaker notes.
- **Bounded deterministic arithmetic:** `sum`, `difference`, `ratio` and `percent_change` with explicit units, metrics, windows, denominators and zero guards. No arbitrary formulas, statistical significance or causal inference.
- **Layered source verification:** JSON sources can be checked against source bytes with hashes and JSON Pointers. PDF/image/text/native-PPTX ledgers remain reviewer-required; citations are not source truth.
- **Final hash verification:** with a trusted expected SHA256, verification checks the exact PPTX bytes, chart caches, tables, KPI text, notes and embedded report. It does not prove source authenticity or visual quality.
- **Theme decisions:** reference > brand > explicit user > automatic > default, with dark/printable conflict disclosure. Three theme variants and eight dark native chart types were built and rendered.
- **Showcase and copy fixes:** eight synthetic cases with actual renders, inputs, specs, sidecars, QA and hash manifests. The Q4 orphan-word wrap and the overlong multimodal subtitle were corrected. Late content corrections aligned Q4 dependency arrows on one explicit 前置→后续 convention (source keeps its labeled 行动→前置 order), removed an unsupported “copy South workflow” claim in favor of verifying definitions and actual workflows before a candidate pilot with pre-defined evaluation and all outcomes recorded, and replaced the executive title that implied six proven growth intervals. Detailed limitations remain in claims, notes and appendix.
- **Packaging and release gate:** deterministic single-SKILL installer, separate optional showcase, fixed timestamps/permissions, no caches/PPTX in the installer, and a manual approved-SHA release workflow with immutable annotated tag and no overwrite of existing assets/history.

### Artifacts

- `goujian-strategy-slides-v1.2.0.zip` — lightweight runtime, one root `SKILL.md`, no PPTX or build caches.
- `SHA256SUMS.txt` — installer checksum.
- Optional showcase: `goujian-strategy-slides-v1.2.0-showcase.zip` with its own checksum filename, carrying the final reviewed hashes; upload belongs to the separate release task.

### Verification and limits

- Independent engine acceptance: 15/15 at `2c622db`; engine acceptance only.
- Actual Linux host: Ubuntu 26.04.1 LTS x86_64; Node 24.18.0; Python 3.14.4; LibreOfficeDev 26.8.0.0 alpha0; Poppler 26.05.0.
- Native Microsoft PowerPoint on macOS/Windows/ARM64: `NOT_RUN`.
- Agensi/company-hosted runtime: `NOT_VERIFIED`.
- Final independent actual VQA: `PASS_WITH_KNOWN_LIMITATIONS` for 8 cases / 58 pages, Linux LibreOffice with synthetic fixtures, bound to exact PPTX and page hashes. Not native PowerPoint, not all 15 profiles, not the 15 legacy benchmark scenarios.
- Python test discovery: 34 passed plus 1 opt-in network skip; the separate real clean-install bootstrap integration passed 9/9.
- No font is bundled or embedded. Font measurement is an estimate; recipient rendering may differ.
- No HTML renderer, automatic OCR, arbitrary lossless PPTX editing, autonomous visual repair or second rendering engine.
- No dependency version upgrades in this release.

### Upgrade

Replace the installed folder with the new ZIP; do not merge over an old directory. Preserve custom specs/assets outside the folder, then run `npm run bootstrap`, `npm run doctor -- --json` and `npm test`. Legacy deck JSON remains supported; the Reasoning Plan is optional. See [Migrate from V1.1.1](MIGRATION_V1_1_1_TO_V1_2.md).

## 中文

### 主要变化

- **Reasoning Plan：** Agent 编写来源、主张、取舍、计算、数字绑定与主题决策，编译前做确定性校验；输出原生 PPTX、导出 Spec、哈希绑定场景、推理 sidecar、内嵌报告与 claim 追溯备注。
- **有限确定性算术：** `sum`、`difference`、`ratio`、`percent_change`，显式单位、指标、时间窗口、分母与零值保护。无任意公式、统计显著性检验或因果推断。
- **分层来源核对：** 结构化 JSON 可用哈希与 JSON Pointer 对照源字节；PDF/图片/文本/原生 PPTX 台账仍需复核者提取。引用不等于来源为真。
- **最终哈希校验：** 在可信期望 SHA256 下检查精确 PPTX 字节、图表缓存、表格、KPI 文本、备注和内嵌报告；不证明来源真实性或视觉质量。
- **主题决策：** reference > brand > 显式用户 > automatic > default，dark 与 printable 冲突会披露。三条主题变体与八类深色原生图表已构建渲染。
- **展示与文案修复：** 八个合成案例，含实际渲染、输入、Spec、sidecar、QA 与哈希清单。Q4 单字换行与过长的多模态副标题已修复。后期内容修正包括：Q4 依赖箭头统一为明确的“前置→后续”约定（源材料保留带标注的“行动→前置”写法）；移除无依据的“复制华南流程”主张，改为先核验口径与两区实际流程，再评估候选试点，试点前定义评估口径并记录全部结果；执行摘要标题不再暗示六段已证明的增长区间。详细限制保留在 claim、备注和附录。
- **打包与发布门禁：** 确定性单 SKILL 安装包、独立可选展示包、固定时间戳/权限、安装包不含缓存/PPTX；发布仅接受获批 SHA 的手动工作流，注解标签不可变，不覆盖既有资产/历史。

### 交付物

- `goujian-strategy-slides-v1.2.0.zip` — 轻量运行时，一个根目录 `SKILL.md`，无 PPTX 或构建缓存。
- `SHA256SUMS.txt` — 安装包校验和。
- 可选展示包：`goujian-strategy-slides-v1.2.0-showcase.zip`，使用独立校验和文件名并携带最终复核哈希；上传属于独立发布任务。

### 验证与边界

- 独立引擎验收：`2c622db` 处 15/15，仅代表引擎验收。
- 实际 Linux 主机：Ubuntu 26.04.1 LTS x86_64；Node 24.18.0；Python 3.14.4；LibreOfficeDev 26.8.0.0 alpha0；Poppler 26.05.0。
- macOS/Windows/ARM64 原生 Microsoft PowerPoint：`NOT_RUN`。
- Agensi/公司平台托管运行：`NOT_VERIFIED`。
- 最终独立实际 VQA：8 案例/58 页 `PASS_WITH_KNOWN_LIMITATIONS`，Linux LibreOffice 合成素材，绑定精确 PPTX 与页面哈希；不覆盖原生 PowerPoint、全部 15 个 Profile 或 15 个历史 Benchmark 场景。
- Python 测试发现：34 通过 + 1 个需显式启用的网络跳过；独立的真实干净安装 bootstrap 集成测试 9/9 通过。
- 字体不随包分发、不嵌入；字形测量为估算，接收端渲染可能不同。
- 无 HTML Renderer、自动 OCR、任意 PPTX 无损编辑、自主视觉修复或第二套渲染引擎。
- 本次不升级依赖版本。

### 升级

用新 ZIP 替换已安装文件夹，不要覆盖合并旧目录。保留目录外的自定义 Spec/资产，然后运行 `npm run bootstrap`、`npm run doctor -- --json` 与 `npm test`。legacy deck JSON 继续支持，Reasoning Plan 为可选。详见[从 V1.1.1 迁移](MIGRATION_V1_1_1_TO_V1_2.md)。
