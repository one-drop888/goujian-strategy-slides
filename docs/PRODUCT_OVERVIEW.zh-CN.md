# 构见·战略演示

[English](PRODUCT_OVERVIEW.md) | [简体中文](PRODUCT_OVERVIEW.zh-CN.md)

## 面向 AI Agent 的 Presentation Intelligence

构见·战略演示是一套面向 AI Agent 的开源、生产级演示文稿智能 Skill，帮助 Agent 将复杂信息转化为清晰、有结构、能支持判断与行动的演示文稿。

**Think clearly. Structure strategically. Present decisively.**

它试图把一份高质量商业汇报背后的思考过程真正产品化：

**思考 → 结构 → 可视化 → 构建 → 验证**

将管理叙事、Storyline、Action Title、Semantic Archetype、Composition Grammar、数据可视化、Profile 驱动的视觉设计、原生可编辑 PPTX 与 Quality Gate 整合成统一工作流。

> 好的演示文稿不是漂亮页面的集合，而是一套帮助人理解复杂问题，并形成判断与行动的结构化论证。

核心管理表达模型：**Question → Evidence → Judgment → Action**，即 **问题 → 证据 → 判断 → 行动**。

**高信息密度 ≠ 高文字密度。** 图表、对比、结构与表格应承担信息表达，文字用于解释、判断和行动。

## 服务对象

- 需要复盘结果、定位差距、落实责任的管理团队。
- 需要连接样本方法、定量信号、定性原话与有限度解释的研究团队。
- 需要解释方案取舍、风险、运营模型与分阶段实施的产品和技术团队。
- 希望复用完整演示工作流的 AI Agent。

## 工作方式

Agent 先明确决策、证据和约束，选择 Storyline 与每页语义目的，再形成 JSON Presentation Spec。可复用 Composition 与明确的 Profile 驱动 PPTX 后端。可执行校验拒绝错误及超出容量的输入，渲染与实际视觉审查形成闭环。

Library 包含 28 个 Storyline、78 个语义条目、23 个 Composition Recipe、15 个 Profile、15 个模板配方。**其中 65 个语义条目已实现、6 个 Partial、7 个仅设计**；仅设计条目不能构建。数量表示表达词汇的范围，不代表 78 套独立设计或同等完整的专用版式。

## V1 边界

V1 首先以 PowerPoint/PPTX 为核心输出。文本、形状、表格及受支持图表数据保持原生可编辑。已有稿件可进行有限文本编辑、Agent 主导的结构重建以及风格统计提取。

Planner 是小型启发式助手；证据选择、因果判断、模板解释和视觉修复仍需要 Agent 或人。“生产级”指可执行、可检查、边界明确，不是所有输入都可以无人审核交付。完整边界见 [README](../README.zh-CN.md)与[可行性报告](FEASIBILITY_REVIEW.zh-CN.md)。

Presentation Intelligence 层独立于 PptxGenJS，为 HTML Slides、Web Presentation 等输出保留空间；跨 Renderer 的共享几何布局引擎属于未来工作。V1 不实现 HTML、动画、任意 PPTX 完全无损编辑或自动确定性视觉修复。

只有一个产品和一套 Presentation Library。平台适配器只提供薄层执行指引，不拆分公共版、公司版或个人版。
