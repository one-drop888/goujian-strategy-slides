# Goujian Strategy Slides｜构见·战略演示

[English](README.en.md) | [简体中文](README.md)（默认）

**面向 AI Agent 的 Presentation Intelligence**

**Think clearly. Structure strategically. Present decisively.**

构见·战略演示是一套面向 AI Agent 的开源、生产级演示文稿智能 Skill。这里的“生产级”指可执行、可检查、边界明确的工作流；不代表任何输入都能无人审核交付。

它将高质量商业汇报背后的思考过程产品化：

**思考 → 结构 → 可视化 → 构建 → 验证**

将管理叙事、Storyline、Action Title、Semantic Archetype、Composition Grammar、数据可视化、Profile 驱动设计、原生可编辑 PPTX 与 Quality Gate 整合为统一流程。Agent 负责判断，确定性代码负责构建和检查。

> 好的演示文稿不是漂亮页面的集合，而是一套帮助人理解复杂问题，并形成判断与行动的结构化论证。

**Question → Evidence → Judgment → Action**

**问题 → 证据 → 判断 → 行动** · **高信息密度 ≠ 高文字密度**

![经营复盘：可编辑指标、统一基期趋势、原因与行动](docs/visual/executive-review-after.png)

*V1 实际渲染示例。全部示例均为合成演示内容，不代表真实经营事实。*

## V1.1 提供什么

- 28 个管理 Storyline、15 个 Template Recipe，覆盖经营、战略、研究、销售、项目、上市、营销、技术、培训与成本决策。
- 86 个语义目录条目：**74 个已实现、6 个 Partial、6 个仅设计**。仅设计条目会被构建器明确拒绝。
- 27 个 Composition Recipe，由 22 个可复用渲染函数实现；不等于 86 套独立版式。
- 15 个 Profile，实际驱动字体字号、间距、标题/封面、表头/隔行底色、指标样式、图表网格及配色。
- 12 套可执行 Benchmark、JSON Schema 与负载校验、几何/字体检查、可选渲染与 Montage。

阅读[产品介绍](docs/PRODUCT_OVERVIEW.zh-CN.md)、[可行性报告](docs/FEASIBILITY_REVIEW.zh-CN.md)、[Library 审计](docs/LIBRARY_AUDIT.md)与[视觉迭代记录](docs/VISUAL_REVIEW.md)。

## V1.1 多模态与视觉智能

图片、原生图表、表格与解释通过四种可复用组合连接。PNG/JPEG/WEBP 原生进入 PPTX；截图默认完整保留，像素文字与可编辑文字明确区分。标题按字形宽度测量，支持 `title_short` / `subtitle`、动态分割线和正文流。构建同时输出绑定 PPTX 哈希的场景记录，空间 QA 可检查证据遮挡、文字/横线冲突和来源关系。

资产分类、结论改写和视觉修复仍由 Agent 负责；没有自动 OCR、任意 PPTX 无损编辑或自主视觉推理引擎。参阅[多模态契约](docs/MULTIMODAL_CONTRACT.md)、[代码基线审计](docs/V1_1_GROUND_TRUTH.md)与[本轮验证](docs/V1_1_VALIDATION.md)。

## 安装

需要 **Node.js 18+、Python 3.9+**，确保 PATH 中有 `node`、`npm`、`python3`。图片与完整测试需要 Pillow；本机字体测量使用 Fontconfig。基础几何检查使用标准库。必须安装完整仓库，不能只复制 `skill/`。

V1.1 工程包（尚未创建 GitHub Release） 解压后是一个 `goujian-strategy-slides/` 文件夹，其中只有文件夹根目录的 `SKILL.md` 一个技能入口。导入 Skill 平台时上传完整 ZIP；若平台自行解包，应以该根目录作为技能目录。平台侧导入与安全扫描仍须在目标平台复测。

```bash
git clone https://github.com/one-drop888/goujian-strategy-slides.git
cd goujian-strategy-slides
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-render.txt
npm install
npm test
npm run validate:example
npm run build:example
npm run qa:example
```

输出位于 `out/executive-review.pptx` 和 `out/quality-report.json`。`npm ci` 使用仓库内 lockfile 复现依赖；本项目不依赖 npm 包发布。

核心构建和校验不需要渲染工具。`qa:example` 会尝试渲染；缺少依赖时显示 `UNAVAILABLE`，不能当作视觉通过。可选依赖：

```bash
python3 -m venv .venv
# Linux/macOS，在当前 shell 激活环境
. .venv/bin/activate
python3 -m pip install -r requirements-render.txt
```

另需安装 **LibreOffice、Poppler（pdftoppm）、Noto Sans 与 Noto Sans CJK SC**。Debian/Ubuntu 对应系统包：`libreoffice-impress poppler-utils fontconfig fonts-noto-core fonts-noto-cjk`。字体不随仓库分发，也不会嵌入 PPTX；接收方需要安装字体，或改用已安装字体的自定义 Profile。

本轮实测平台为 Linux。macOS 需要将上述工具放入 PATH。Windows 建议使用 WSL2 执行文档中的 `python3` 命令；原生 Windows 以及 PowerPoint/macOS 渲染尚未验证。字体检查依赖 `fc-list`，缺少 Fontconfig 时返回 `UNAVAILABLE`。

## 与 Agent 配合

让 Agent 的技能发现机制加载**整个仓库文件夹**及根目录 [SKILL.md](SKILL.md)。Adapters 是接入说明，不代表已完成各平台实测。让 Agent 先确定决策、证据和不确定性，再编写[语义 Spec](docs/SPEC_CONTRACT.md)。

```bash
node skill/scripts/build_deck.js skill/examples/executive-review.json out/review.pptx --profile consulting
npm run library
npm run benchmark
npm run benchmark -- --render
```

`benchmark` 构建并检查全部 12 类场景；`--render` 生成 PNG 和 Montage。每套报告及 PPTX 哈希保存在 `out/benchmarks/`。实际检查画面后才能记录视觉通过。

[自定义 Profile](docs/CUSTOM_PROFILE_GUIDE.md)支持继承；[已有 PPTX 工作流](docs/EXISTING_PPTX_WORKFLOW.md)说明文本替换、检查与参考重建。

## 能力边界

| 能力 | V1 状态 | 实际能力 |
|---|---|---|
| Create | 已实现 | 合规语义 JSON → 原生可编辑 PPTX |
| Edit | Partial | 单个文本节点内替换，不自动重排 |
| Rebuild | Partial | Agent 检查原稿并重写 Spec，不是无损转换 |
| Template reuse | Partial | Storyline/Profile 配方，不克隆 PPTX 母版 |
| Style extraction | Partial | 提取主题、字体、几何统计，仍需解释与复核 |
| Native editable PPTX | 已实现 | 文本、形状、表格、受支持的原生图表 |
| Overflow / overlap | Partial | 边界框及相交候选，不证明文本完整容纳 |
| Font QA | Partial | 本机字体族可用性，不证明字形覆盖或字体嵌入 |
| Render / montage | 已实现，可选 | LibreOffice → PDF → PNG，Pillow 拼图 |
| Visual QA | Partial | 人或视觉 Agent 检查，记录绑定 PPTX 哈希 |
| Repair loop | Partial | Agent 修改并重渲染，无自动确定性视觉修复引擎 |
| Planner | Partial | 关键词路由助手，证据推理仍由 Agent 完成 |
| HTML Renderer | 仅设计 | V1 不输出 HTML |

瀑布/桥接、组合图、散点/气泡、热力图 尚无忠实实现。抽象地图、关系和类 Sankey 条目明确标为 Partial。仅支持 16:9 画布。长内容需要改写或拆页；容量校验通过不等于可读。

## 架构与贡献

```text
Agent 推理 → Presentation Spec → Storyline / Archetype → Composition + Profile
                                                               ↓
                                                     PPTX Renderer → QA → 视觉复核
```

规划和 Composition 层不导入 PptxGenJS；具体几何坐标仍属于 PPTX 后端，跨 Renderer 共享布局引擎属于后续工作。详见[架构](docs/architecture/ARCHITECTURE.md)和[贡献说明](CONTRIBUTING.md)。

项目只有一个产品和一套 Presentation Library，平台适配器共用它们。

## 许可证

[Apache-2.0](LICENSE)。依赖各自保留许可证，见[第三方声明](THIRD_PARTY_NOTICE.md)。本轮没有复制 Benchmark 源码、商业模板或专有视觉资产。请勿发布私有源文稿或无再分发许可的字体与素材。
