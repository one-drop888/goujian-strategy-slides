# Goujian Strategy Slides v1.1.0

## 简体中文

构见·战略演示 V1.1 的主题是 Multimodal Composition & Visual Intelligence。它保留 Think → Structure → Visualize → Build → Validate 与 Question → Evidence → Judgment → Action，以原生可编辑 PPTX 为核心输出。

- 原生图片、证据截图、图表、表格与解释进入同一构建流程；保留来源、像素文字与原生文字的边界，不需要 python-pptx 插图后处理。
- 标题字形测量、副标题、动态分割线、六 KPI 完整性与九列表格；空间 QA 检查语义遮挡、文字横线、来源关系及局部对比度。
- 经营、非线性销售转化、项目绩效三套可替换数据的分析 Recipe，覆盖 18 项分析任务。提供严格输入 Schema、数值计算、缺失值与分母处理、拆页和输入到原生图表/表格的数据保真检查。
- 强化经营 Dashboard、决策摘要与 Editorial Hero；证据截图保持完整，Hero 只处理标题局部安全区，不统一压暗整图。
- README 默认简体中文并提供英文切换；双语产品与可行性说明；安装包仅一个根 SKILL.md，Apache-2.0 保持不变。

本地验收：现有测试、新增分析/数据保真回归、15 场景构建/渲染，以及六套代表 Deck 的视觉检查与修复。详细数量、哈希和 Before/After 见 `docs/V1_1_RELEASE_VALIDATION.md`。

边界：资产理解、结论判断及视觉修复仍需 Agent；没有自动 OCR、任意 PPTX 无损重建或 HTML Renderer。项目成本契约首批支持 CNY 累计快照；销售分析需要规范客户 ID，关联不等于因果。Windows/macOS/原生 PowerPoint 与公司平台认证尚未验证。其余九套场景仅完成自动渲染，未作完整视觉批准。

## English

V1.1 connects native multimodal construction, source provenance, measured hierarchy and semantic spatial QA. Native editable text, charts and tables remain central; screenshots retain their embedded pixel text. Image preparation occurs before PPTX serialization, with no python-pptx insertion pass.

Three runnable analytical recipe families cover business performance, nonlinear sales conversion and project performance. Replace JSON inputs to regenerate editable PPTX, computed evidence and a scene sidecar. Strict schemas and fidelity checks cover units, reconciliation, mature cohort denominators, optional trial behavior, nulls, explicit pagination and native numeric evidence.

Visual refinements integrate metrics with native trends, structure decision summaries and replace the hard hero panel with a local contrast-calculated soft scrim. Source screenshots are never darkened for decoration. Fifteen benchmark scenarios retain the existing architecture and library; no template/profile count expansion.

See the release validation report for executed tests and six reviewed decks. General reasoning, OCR, arbitrary lossless editing and autonomous visual repair remain partial or unimplemented. Linux LibreOffice/Poppler verification does not certify identical native PowerPoint output on every platform. All example data is synthetic. Apache-2.0 licensing remains unchanged.

## Install / 安装

Download `goujian-strategy-slides-v1.1.0.zip` and `SHA256SUMS.txt`, verify the checksum, then extract the complete folder. Follow README for Node.js, Python/Pillow, fonts and optional LibreOffice/Poppler. The folder root contains the only `SKILL.md`. Upload the ZIP unchanged to platforms supporting a wrapped Skill folder; platform-specific import/security certification still requires platform testing.
