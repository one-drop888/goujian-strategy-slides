# 构见·战略演示

[English](PRODUCT_OVERVIEW.md) | [简体中文](PRODUCT_OVERVIEW.zh-CN.md) · [README](../README.md)

**面向 AI Agent 的 Presentation Intelligence**

构见·战略演示是一套面向 AI Agent 的开源、生产导向演示文稿智能 Skill。它把复杂材料组织成结构化论证，再生成原生可编辑 PowerPoint，并保留数据、来源、内容取舍与质量检查的记录。

Think clearly. Structure strategically. Present decisively.

**思考 → 结构 → 可视化 → 构建 → 验证**

经营汇报需要回答问题、呈现证据、形成有依据的判断，并明确下一步行动。构见以 **Question → Evidence → Judgment → Action（问题 → 证据 → 判断 → 行动）** 组织这项工作。高信息密度不等于高文字密度：明确的比较可以替代大段描述，精确查数时表格也可能优于图表。

> 好的演示文稿不是漂亮页面的集合，而是一套帮助人理解复杂问题，并形成判断与行动的结构化论证。

## 交付内容

- 一套复用原生 PPTX 引擎的表达库：Storyline、Semantic Archetype、Composition、Profile 和 Recipe。这些是语义与设计选择，不是彼此无关的页面模板堆积。
- 三类可执行分析流程：经营总览、非线性销售转化、项目绩效。输入、计算、时间窗口、分母和缺失事实均可核对。
- 可选的指标语义契约：明确比例、百分数、百分点、币种、缩放和精度，同一个事实可以用于标题、KPI、表格和原生图表。
- Agent 编写的 Reasoning Plan：记录来源、主张、算术与内容取舍；Narrative Graph 连接问题、证据、页面和决策，重复候选交给复核者判断。
- 按类别、数值尺度和业务角色区分的视觉编码，原生文字、图表、表格与形状，经过测量的标题和图文证据组合。
- 针对实际 PPTX 及嵌入工作簿的 QA，加上几何、字体、空间、真实渲染和独立视觉复核记录。

Agent 负责业务解释与设计选择，确定性代码负责计算、约束与记录。项目没有内置通用业务推理模型、任意统计显著性检验或因果推断系统。

## 同一个产品，接入不同 Agent 环境

Community 继续采用 Apache-2.0，只保留根目录唯一 `SKILL.md`。平台展示名称不改变 Skill ID，也不产生企业专用分支。安装整个仓库或运行包，不能只复制 `skill/`。

Node18+/Python3.9+ 是兼容下限，实际使用应选择仍受维护的安全补丁版本。安全图片处理与完整渲染需 Python3.11+/Pillow13，以及外部渲染工具和字体，参阅[安装说明](INSTALLATION.md)。

## 输出与边界

原生文本、形状、表格与已支持图表可在 PowerPoint 中编辑；截图中的像素文字不可编辑。已有 PPTX 的文本替换限定于单个 DrawingML 文本节点；任意无损回写、Master 克隆、自动 OCR 与自主视觉修复均未实现。

现有六类原生图表、显式等宽分箱和柱/条堆叠各有容量和语义约束。尚未支持的统计图或组合图会被拒绝，不用普通柱图冒充。来源真实性、商业判断和美学仍需复核。Linux 实测不能代表 Windows/macOS/ARM64 原生 PowerPoint 一致，也不能代表公司或 Agensi 平台审核通过。

V1.3 聚焦 **数据语义准确 → 图形编码正确 → 视觉快速识别 → 支持管理判断**。[Benchmark](BENCHMARKS_V1_3.md) 与[可行性报告](FEASIBILITY_REVIEW.zh-CN.md)记录实际执行范围。Pro 本轮独立完成产品设计；尚未上线收费，也不会把开源基础质量修复改为付费功能。
