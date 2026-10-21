# 构见·战略演示 V1.2 可行性复核

2026-10-21 · 战略推理、确定性校验与发布打包。

[English](FEASIBILITY_REVIEW.md) · [产品介绍](PRODUCT_OVERVIEW.zh-CN.md) · [Benchmark A–J](BENCHMARKS_V1_2.md) · [质量与验证](QUALITY_AND_VALIDATION.md)

状态词：**PROVEN** 表示在声明的证据与范围内已执行；**PARTIAL** 表示覆盖有限或不完整；**DESIGNED** 表示契约存在但无忠实实现；**BLOCKED** 表示必需能力无法运行；**NOT_VERIFIED** 表示未实际执行。状态由证据范围限定，不是产品级保证。

| 维度 | 状态 | 证据与边界 |
|---|---|---|
| 架构 | PROVEN | 共享 Schema → Composition → 原生 PPTX → 哈希绑定 Scene → QA；推理层为增量，Renderer 核心保留。 |
| Reasoning Plan 契约 | PROVEN，契约内 | Agent 编写来源、主张、取舍、计算、绑定与主题，编译前校验。Codex 在 `2c622db` 独立重跑 15/15 引擎检查。未宣称独立推理模型。 |
| 确定性算术 | PROVEN，四种算子 | `sum`、`difference`、`ratio`、`percent_change`，检查单位/指标/窗口/分母/零值并给出容差。无任意公式、统计显著性检验或因果推断。 |
| 来源核对 | PARTIAL | 结构化 JSON 可用 JSON Pointer 对照源字节并校验 SHA256。PDF/图片/文本/原生 PPTX 台账为 `REVIEWER_REQUIRED`；定位或引用不等于来源为真。 |
| 最终产物校验 | PROVEN，信任范围受限 | 给定可信期望哈希后，读取精确 PPTX 字节，检查图表缓存、表格、KPI 文本、备注、内嵌报告及计划/Spec 哈希。不证明来源真实性或视觉质量。 |
| 主题决策 | PROVEN，选择层面 | reference > brand > 显式用户 > automatic > default；显式 dark 与 printable 冲突会记录。light/brand-blue/dark 三变体已构建渲染。配置差异不等于 15 套视觉批准设计。 |
| 多模态/原生图片 | PROVEN，契约内 | 原生 PNG/JPEG/WEBP、保护性裁剪/焦点/透明度/遮罩、图注与像素文字来源。无 PPTX 图像后处理。 |
| 资产理解 | PARTIAL | 分类与来源由 Agent 提供，代码执行策略。无分类器、OCR 或通用视觉理解。 |
| 原生来源检查 | PROVEN，限定样例 | 两份合成原生来源 PPTX 保留 9 列表格（含负责人/复核日）、4 个图表值及内嵌图片，并给出文件/页/形状定位。任意复杂来源重建仍为 Partial。 |
| 标题/布局 | PROVEN，契约内 | 字形测量/等价估算、短标题/副标题、动态分割线与正文流、显式标题容量错误。长标题回归已渲染；估算不等于 PowerPoint 精确排字。 |
| 来源与场景 | PROVEN | 原生、像素、标注、数据与判断来源类型，以及实际原生对象关系。 |
| 空间 QA | PROVEN，显式场景内 | 原生坐标/顺序读回、遮挡、安全区、文字/横线间距、密度与保守文字容量警告。不推断任意导入稿意图。 |
| 视觉质量 | PARTIAL | 最终独立实际 VQA 覆盖 Linux LibreOffice 上 8 个案例/58 页合成素材，绑定精确 PPTX 与页面哈希，状态 `PASS_WITH_KNOWN_LIMITATIONS`。这不覆盖全部 15 个 Profile、15 个历史 Benchmark 场景或原生 PowerPoint；八个渲染不等于八个通用视觉批准。 |
| 打包 | PROVEN（本地） | 确定性安装包测试可生成相同字节，检查单一根 SKILL、固定时间戳/权限、必需资产、无 PPTX/PDF/缓存。最终干净解压安装证据单独记录。 |
| 安装 | PROVEN，Linux x86_64 | 从安装 ZIP 在 Unicode/空格、无符号链接路径执行隔离 `.venv`、`npm ci`/bootstrap、doctor、测试、示例构建与渲染。macOS/Windows/ARM64 未验证。 |
| 可维护性 | PROVEN，结构层面 | 推理、资产、标题、场景由小型共享模块实现；未整体重写引擎或增加重量级运行时依赖。 |
| Profile/字体 | PARTIAL | 15 个真实 token 配置（不止配色）；Linux 字体解析已验证。未嵌入字体，不证明完整字形覆盖与接收端效果。 |
| PPT 接入/保真 | PARTIAL | 文字、图片、图表、表格、组、母版/布局候选可映射；复杂重建与歧义语义仍不完整。 |
| 可扩展性 | PROVEN，边界层面 | 资产、来源、关系与推理 JSON 不导入 PptxGenJS；原生适配位于渲染边界。 |
| 多输出 | DESIGNED | HTML/Web Renderer 未实现。 |
| QA 可靠性 | PARTIAL | 有负向回归、哈希绑定与实际复核；无精确 PowerPoint 排字、通用美学标准或自主修复。 |
| 发布流程 | NOT_VERIFIED | 手动 `workflow_dispatch` 流程已更新并静态检查，但本阶段未派发，未创建标签或公开 Release。 |
| 开源就绪 | PARTIAL | 单一 Skill 入口、合成声明、安装包与展示包已本地构建检查；GitHub 发布设置与匿名资产下载仍是待执行手工步骤。 |
| 商业就绪 | PARTIAL | 仅文档。Community 保持 Apache-2.0；Supporter/Pro 为未来候选，无收款、账户或上架。Agensi 托管运行未验证。 |
| 文档准确性 | PROVEN，审计声明内 | Create、推理、原生图片与有限 QA 路径可执行；Edit/Rebuild/Reference/Vision/Repair 边界已声明。历史发布文档不改写。 |

28 Storylines · 86 semantic entries（74 IMPLEMENTED / 6 PARTIAL / 6 DESIGNED）· 27 Compositions · 15 Profiles · 15 Template Recipes · 15 Benchmark scenarios。

## 证据锚点

- 引擎验收：[Codex final acceptance](evidence/v1.2/reviews/codex-final-acceptance.json) — `2c622db` 处 15/15，仅代表引擎验收。
- 最终实际视觉验收：[Codex final visual acceptance](evidence/v1.2/reviews/codex-final-visual-acceptance.json) — 8 案例/58 页，`PASS_WITH_KNOWN_LIMITATIONS`，仅 Linux LibreOffice。
- 已验收渲染的来源字节等价性：[final source provenance](evidence/v1.2/reviews/final-source-provenance.json) — 91 个文件、0 不一致；历史 dirty 构建元数据单独保留。
- 部分全尺寸复核与剩余文案问题：[round-2 preview review](evidence/v1.2/reviews/codex-round2-preview-review.md)；修复后文案已进入展示构建。
- 来源 PPTX 范围：[source acceptance](evidence/v1.2/reviews/codex-source-pptx-acceptance.md)；实际检查记录在可选展示包的 `source-inspection.json`。
- 依赖审计：[official npm audit record](evidence/v1.2/reviews/codex-dependency-audit-official.json) — 官方 registry 下 0 已知漏洞。
- 展示与预览：[展示说明](SHOWCASE_V1_2.md)、`docs/visual/v1.2/`。
- A–J 证据矩阵：[Benchmark A–J](BENCHMARKS_V1_2.md)。

## 结论

**V1.2 为文档化 Agent 辅助工作流的 READY WITH KNOWN LIMITATIONS。**

推理契约、有限算术、原生构建、主题选择、来源检查与打包在各自声明范围内已证明。语义忠实度、来源真实性、因果结论、视觉质量与跨平台渲染不由代码认证。最终独立视觉验收已在 8 案例/58 页的 Linux LibreOffice 范围内完成；15 个历史 Benchmark 场景的视觉验收仍为 `NOT_RUN`，15 个 Profile 也未全部完成视觉测试。公开发布仍是独立门禁，尚未执行。

三类可运行分析在声明 Schema 内仍为 PROVEN：完整月份经营数据、成熟非线性销售队列及 CNY 项目累计快照。来源真实性与因果推断不在代码认证范围内。参阅[分析边界](ANALYTICAL_LIBRARY.md)。
