# 构见·战略演示

[English](PRODUCT_OVERVIEW.md) | [简体中文](PRODUCT_OVERVIEW.zh-CN.md) | [返回根目录](../README.md) · [安装](../README.md#安装) · [Benchmark A–J](BENCHMARKS_V1_2.md) · [可行性复核](FEASIBILITY_REVIEW.zh-CN.md)

## 面向 AI Agent 的 Presentation Intelligence

构见·战略演示是一套面向 AI Agent 的开源演示文稿智能 Skill，帮助 Agent 将复杂信息转化为清晰、有结构、能支持判断与行动的演示文稿。

**Think clearly. Structure strategically. Present decisively.**

它把一份高质量商业汇报背后的思考过程产品化：

**思考 → 结构 → 可视化 → 构建 → 验证**

将管理叙事、Storyline、Action Title、Semantic Archetype、Composition Grammar、数据可视化、Profile 驱动的视觉设计、原生可编辑 PPTX 与 Quality Gate 整合成统一工作流。Agent 负责判断；确定性代码负责校验、构建和暴露边界。

> 好的演示文稿不是漂亮页面的集合，而是一套帮助人理解复杂问题，并形成判断与行动的结构化论证。

核心管理表达模型：**Question → Evidence → Judgment → Action**，即 **问题 → 证据 → 判断 → 行动**。

**高信息密度 ≠ 高文字密度。** 图表、对比、结构与表格应承担信息表达，文字用于解释、判断和行动。

## 服务对象

- 需要复盘结果、定位差距、落实责任的管理团队。
- 需要连接样本方法、定量信号、定性原话与有限度解释的研究团队。
- 需要解释方案取舍、风险、运营模型与分阶段实施的产品和技术团队。
- 希望复用完整演示工作流的 AI Agent。

## V1.2 的工作方式

Agent 先明确决策、证据、约束和内容取舍，再编写 Reasoning Plan；确定性校验检查结构、算术、引用闭合、覆盖、数字绑定和主题选择，然后编译为导出 Spec 与原生可编辑 PPTX。场景与推理 sidecar 绑定构建结果，结构 QA 与实际渲染供语义/视觉复核使用。

Reasoning Plan 是 **Agent 编写** 的输入，不是项目内置的通用推理模型。校验器支持 `sum`、`difference`、`ratio`、`percent_change`，并检查单位、时间窗口、指标与分母；没有任意公式、统计显著性检验或因果推断。结构化 JSON 来源可用 JSON Pointer 对照源字节；图片、PDF、文本和原生 PPTX 的数值台账仍需复核者提取。来源被引用不等于来源为真。

Library 包含 28 个 Storyline、86 个语义条目、27 个 Composition Recipe、15 个 Profile、15 个模板配方。**其中 74 个语义条目已实现、6 个 Partial、6 个仅设计**；仅设计条目不能构建。数量表示表达词汇的范围，不代表 86 套独立设计或同等完整的专用版式。

## 主题与视觉

主题选择遵循 reference profile > brand profile > 显式用户 profile > automatic intent > default 的优先级。显式 dark 可以覆盖自动 light 选择，但 dark 与 printable 等冲突会写入主题记录，而不是静默忽略。所选 Profile 实际驱动字体字号、间距、表格、指标、图表网格与配色。

V1.2 展示包含三条主题变体和八类深色原生图表。标题使用字形测量与保守估算，支持短标题/副标题、动态分割线与正文流；字体测量不是实际排字证明，结构 QA 不能证明所有渲染文字碰撞都不存在。最终画面必须实际检查。

图片、原生图表、表格与解释共享同一构建流程，并保存来源、像素文字属性、裁剪区域与场景关系。资产分类、语义改写与视觉修复仍由 Agent 完成；没有自动 OCR、任意 PPTX 无损编辑、自主视觉修复或跨 Renderer 布局引擎。

## V1.2 交付与复核

八个展示案例覆盖高管经营复盘、Q4 行动、多源整合、三套主题、八类深色图表和长标题。每例保留输入参考、导出 Spec、PPTX、推理 sidecar、QA、实际 LibreOffice 渲染、Montage 与哈希清单。安装 ZIP 是独立轻量运行时，展示 ZIP 是可选复核资产。

独立最终视觉验收已在写入停止后完成：Codex 在 Linux LibreOffice 上检查了 8 个展示案例的全部 58 页合成素材，结论为 `PASS_WITH_KNOWN_LIMITATIONS`，并绑定精确 PPTX 与页面哈希。该验收不等于出版批准。15 个历史 Benchmark 场景的视觉验收仍为 `NOT_RUN`，15 个 Profile 也未全部完成视觉测试；原生 PowerPoint（macOS/Windows/ARM64）未执行，Agensi/公司平台托管运行未验证。

Community 核心（含 doctor、QA 与缺陷修复）保持 Apache-2.0 免费。Supporter 与 Pro 是未来候选，不在本仓库开户、收款或上架；Pro 增加业务工作流包，不引入第二套渲染引擎。详见[商业就绪说明](COMMERCIAL_READINESS.md)。

完整边界见[可行性复核](FEASIBILITY_REVIEW.zh-CN.md)、[质量与验证](QUALITY_AND_VALIDATION.md)、[Benchmark A–J](BENCHMARKS_V1_2.md)与[根目录 README](../README.md)。V1.1 及更早的发布文档保持历史记录，不追溯改写。
