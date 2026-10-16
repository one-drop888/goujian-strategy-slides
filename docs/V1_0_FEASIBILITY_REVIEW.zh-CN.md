# V1.0 可行性审查

[English](FEASIBILITY_REVIEW.md) | [简体中文](FEASIBILITY_REVIEW.zh-CN.md)

**最终判断：V1.0 RELEASE READY WITH KNOWN LIMITATIONS。**

构见·战略演示适合作为面向生产使用、由 Agent 协助的可编辑管理演示工作流；目前仍需要 Agent 完成证据判断和视觉复核。它还不是全自动资料转演示系统，也不是任意 PPTX 无损编辑器。审查日期：2026-10-14。本报告覆盖优化后的源码与实际执行的本地样例；公开发布和远端复验属于独立操作，以 Release 工作流及最终发布报告为证。

## 分项可行性

`PROVEN` 表示在所述范围内实际执行并验证；`PARTIAL` 表示已有可用实现但存在重要边界；`DESIGNED` 表示只有设计意图、尚无可用输出；`BLOCKED` 表示执行受阻。它们是证据状态，不是成熟度评分。

| 领域 | 状态 | 证据与边界 |
|---|---|---|
| 架构可行性 | PROVEN | Schema → 语义解析 → Profile → PPTX → QA 全链运行；规划与 Composition 层不导入 PptxGenJS |
| 产品可行性 | PROVEN | 10 类管理场景、60 页，覆盖证据、判断与行动；均为合成样例，不能代表真实用户采用情况 |
| 视觉与美学 | PROVEN | 三轮有限迭代；检查了三类前后对照、10 套最终 Montage、23 类 Composition Gallery 和 15 个 Profile 探针；由视觉 Agent 评审，未经独立人工评审组验收 |
| 安装可行性 | PROVEN | 干净解包后安装、测试、校验、构建和 QA；仅证明 Linux 环境，渲染工具独立安装 |
| 可维护性 | PARTIAL | 共享基础元素、数据页拆分、锁文件和负面回归测试；结构页模块仍较大，部分布局采用固定尺寸 |
| 可扩展性 | PROVEN | Registry 解析、Profile 继承、参考样式生成 Profile 并构建均已执行；新增语义仍需字段与渲染测试 |
| 多 Renderer 就绪度 | PARTIAL | 语义 JSON 与 Composition 路由可复用；没有共享几何引擎，也没有 HTML Backend |
| 开源就绪度 | PROVEN | Apache-2.0、依赖声明、完整运行包、双语入口、贡献指南与 CI/Release 工作流齐备；不等同于独立来源/法律认证 |
| 文档准确性 | PROVEN | 公开 npm 命令实际运行，能力逐项对应代码与边界，没有把未来 Renderer 宣传成当前能力 |
| QA 可靠性 | PARTIAL | Schema/容量、几何、字体可用性、渲染与哈希绑定评审可执行；不能证明事实真伪、精确文字适配和普遍视觉质量 |

## 架构逐层独立判断

| 层 | 状态 | 结论 |
|---|---|---|
| Schema | IMPLEMENTED | Ajv Draft 2020-12 与 Composition 字段/容量校验在生成文件前执行 |
| Planner | PARTIAL | 存在关键词路由与标题辅助；源资料推理、Storyline 调整由 Agent 完成 |
| Storyline | IMPLEMENTED | 28 个不同推荐序列；相近复盘变体不等于独立推理引擎 |
| Archetype | PARTIAL | 78 条：65 已实现、6 Partial、7 仅设计；特殊图表不再用错误近似静默替代 |
| Composition | IMPLEMENTED | 23 个路由配方复用 21 个渲染函数；不是跨后端约束求解器 |
| Profile | IMPLEMENTED | 15 个预设驱动字体、间距、表格、图表、指标、标题、封面和颜色；部分图示仍有固定尺寸 |
| Renderer | IMPLEMENTED | 原生文字、形状、表格及受支持图表；只支持宽屏 PPTX |
| QA | PARTIAL | 可执行检查加显式评审记录；渲染工具和 Fontconfig 为可选依赖 |
| HTML / 未来输出 | DESIGNED | 可复用语义层；几何实现和字体测量需要新建 Backend |

在声明的有界 V1 核心范围内没有受阻功能。原生 Windows/macOS/PowerPoint 渲染**未测试**，不能写 PASS。

## 验证与安装

详见[验证记录](V1_VALIDATION.md)和[机器可读 Benchmark 证据](evidence/benchmark-summary.json)。运行包包含 `core/`、`skill/`、适配说明、脚本、测试、文档、Schema 和锁文件；仅复制 `skill/` 不构成完整安装。核心 Python 检查只使用标准库；渲染另需 Pillow、LibreOffice、Poppler 和已安装字体。

十类场景均检查 Storyline 适配、Action Title、页面变化、Composition、适用的数据图表、Profile、PPTX 生成、中文、几何和视觉质量。部分决策/培训 Deck 没有定量图表，这是内容选择。最终 60 页全部完成渲染；Training 保留 case-study 的 Partial 提示。默认字体改为本机安装的 Noto 系列，并显式设置图表字体后，本机 Font QA 通过。

负面测试覆盖不受支持图表、错误数据、超容量输入、缺失坐标、Graphic Frame 越界、工具不可用、危险原地编辑和失效视觉评审哈希。23 类 Gallery 检查原生 Chart XML/工作簿及不存在整页栅格化替代。受限文字编辑已重新渲染；参考样式提取后生成的新 Profile 已构建。

## Claims Audit

| 能力声明 | 状态 | 实际边界 |
|---|---|---|
| Create | PROVEN | 经校验的语义 Spec → PPTX |
| Edit | PARTIAL | 单个文字节点替换，写入新文件；无智能重排 |
| Rebuild | PARTIAL | Agent 检查后重建 Spec；非无损转换 |
| Template reuse | PARTIAL | 配方/Storyline/Profile 复用；非任意母版导入 |
| Style extraction | PARTIAL | 字体、主题、几何统计与 Profile 起点 |
| Native editable PPTX | PROVEN | 样例中原生文字、形状、表格、图表和嵌入工作簿；未在 Microsoft PowerPoint UI 实测编辑 |
| Overflow / overlap | PARTIAL | 边界框与同级重叠候选；对分组、旋转和文字排版有限制 |
| Font QA | PARTIAL | 检查声明字体族在本机是否可用；不证明字形覆盖、嵌入和接收端可用性 |
| Render / montage | PROVEN | LibreOffice / Poppler / Pillow 流水线已执行 |
| Visual QA | PARTIAL | 视觉 Agent 检查与绑定产物的评审声明 |
| Repair loop | PARTIAL | Agent 修改 Spec/代码、重建并复核；没有自动视觉修复引擎 |

## 对照公开参考后的优势与差距

[外部 Benchmark](EXTERNAL_BENCHMARK.md)依据一手文档定性比较，没有运行竞品，因此不能视为受控性能排名。构见最强的组合是显式管理推理、语义到可复用 Composition 的分层，以及带可检查质量证据的中英混排可编辑 PPTX 工作流。

三个主要差距是精细文字/布局测量、任意既有 Deck 的导入编辑保真，以及成熟 Web/多 Renderer 输出。本轮修复了弱字体层级、默认图表观感、无效 Profile Token、误导语义映射、Schema 未执行和安装/文档不准确等问题，没有进行缺乏现实需求的全面重写。

## 发布边界与路线图

- V1.1：文字适配测量、真实长篇高密度样例、可靠复杂图表与原生 Office 对照验证。
- V1.1：依据实际用户案例改进启发式规划和 Profile 对图示的控制。
- V2：HTML Backend、共享布局测量、更丰富的重建能力；动画与确定性自动视觉修复仍是未来工作。

用户仍需提供可信证据、逐套检查渲染产物，并拆分过长内容。本机一次 PASS 不代表任意字体、接收端、源文档或商业推断都已验证。
