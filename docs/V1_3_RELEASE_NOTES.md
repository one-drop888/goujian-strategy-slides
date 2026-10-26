# Goujian Strategy Slides v1.3.0

**Analytical & Visual Intelligence｜分析与视觉智能**

## 简体中文

V1.3 改进复杂经营资料从数值到汇报的表达：明确百分比、百分点与金额尺度；让实际、目标、历史和不同系列更容易辨认；保留原始证据、缺失数据和内容取舍。

主要变化：

- 可选指标语义契约与统一格式化，同一事实用于标题、KPI、图表和表格；万元等显示缩放有记录，不修改原始事实。
- 六类原生图表统一编码与 QA，系列颜色、线型、Marker 和图例可核对。修复缺失值连线、类别标签被覆盖、份额/百分数格式混用等问题；未实现的图形类型仍明确拒绝；面积图的缺失数据或单点输入要求使用合适的折线图、KPI 或表格替代。
- 声明式叙事图连接主张、证据、页面与决策，提示跨页冗余而不自动删除内容。标题在可读范围内选择单行或均衡换行。
- 原生日期时间轴与有容量边界的分支/泳道/DAG；不把真实时间或分支压平成等距顺序。
- 实际 PPTX/工作簿回读、完整安装包预检、干净安装与真实渲染案例。Node/Python 环境恢复与唯一 Skill 入口继续保留。

核心兼容下限仍为 Node18+/Python3.9+，建议使用受维护的运行时。安全图片处理与完整渲染需 Python3.11+/Pillow13；旧 Python 运行无 Pillow 的核心层。详见[迁移](MIGRATION_V1_3.md)、[安装](INSTALLATION.md)、[验证范围](FEASIBILITY_REVIEW.zh-CN.md)与[真实案例](BENCHMARKS_V1_3.md)。

Community 继续采用 Apache-2.0。Pro 本轮只完成独立产品方案；没有新增收费门槛。公司平台与 Agensi 未实际上传验收，原生 Windows/macOS/ARM64 PowerPoint 未执行；Linux 渲染不代表这些平台认证。

## English

V1.3 improves how analytical facts become a management presentation: explicit percentages, percentage points and currency scales; distinguishable actual/target/history series; retained evidence, missing observations and content decisions.

- Optional numeric contracts share a fact across titles, KPIs, native charts and tables. Display normalization is recorded without rewriting raw facts.
- Unified encoding and readback for six native chart families, including legends, colors, dash/marker and embedded workbooks. Fixes include bridged gaps, overwritten categories and share-versus-percent formatting. Unsupported chart families remain rejected. Area charts with missing data or only one point require a suitable line, KPI or table alternative.
- A declared narrative graph links claims, evidence, slides and decisions, raising redundancy candidates without deleting material. Measured titles consider readable single-line and balanced-wrap candidates.
- Native date-scaled timelines and bounded acyclic branch/swimlane/DAG layouts preserve real time and relationships.
- Actual PPTX/workbook QA, complete-ZIP preflight, clean installation and generated render examples retain the single Skill entry and existing environment recovery workflow.

Core compatibility remains Node18+/Python3.9+; use maintained runtimes. Secure images/full rendering require Python3.11+/Pillow13, while older Python supports the Pillow-free core tier. Read the [migration guide](MIGRATION_V1_3.md), [installation](INSTALLATION.md), [validation scope](FEASIBILITY_REVIEW.md) and [benchmarks](BENCHMARKS_V1_3.md).

Community remains Apache-2.0. Pro is a separate product design, not a commercial launch. Company-platform/Agensi uploads and native Windows/macOS/ARM64 PowerPoint are not verified. A Linux render does not certify those environments.

## Assets and verification

Download the single-Skill installer and the optional generated showcase. Verify each archive against the separate `SHA256SUMS.txt` Release asset. The installer excludes generated PPTX/PDF output; the showcase adds the explicitly allowed V1.3 subtree. Both use the same versioned core and one root `SKILL.md`. No old release/tag is replaced.

Exact release commit/tag and asset hashes are authoritative on GitHub. Source-advisory checks are dated snapshots. Detailed executed tests, independent review and remaining limitations are recorded in the feasibility/acceptance documentation, not inferred from this feature list.
