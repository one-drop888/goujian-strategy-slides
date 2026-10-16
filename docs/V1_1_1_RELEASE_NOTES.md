# Goujian Strategy Slides v1.1.1

## 简体中文

这是 V1.1 的口径校验修复补丁。经营分析现在会交叉核对主指标趋势中可用的上月值、去年同月值与单独填写的同比/环比基期。相互矛盾的输入在计算和构建前明确失败，不再生成互相矛盾的图表与结论。

新增永久回归，分析测试 24/24、Python QA 测试 17/17 通过；原有回归与 15 个 Benchmark 保留。三类可运行分析、原生可编辑 PPTX、多模态、来源追踪、标题/空间/对比度 QA 和六套 51 页视觉验收保持不变。该修复不改变已验收样例的数值或视觉布局。

v1.1.0 发布取消请求生效晚于 tag/Release 创建，因此按维护原则保留原 tag 和 ZIP，使用用户授权的 v1.1.1 发布修复，未覆盖历史。没有依赖升级。产品范围、数据与跨平台边界见 README 和 `docs/V1_1_RELEASE_VALIDATION.md`。

## English

This patch rejects inconsistent primary-metric previous-month/year baselines when matching trend observations are available. Contradictory inputs fail before calculation or PPTX generation.

The permanent baseline regression brings the analytical Node suite to 24 tests, with 17 Python QA tests and the existing regression scripts. All 15 benchmark scenarios remain. Native editable PPTX, three runnable analytical families, multimodal/source/layout QA and six reviewed decks (51 pages) retain their V1.1 behavior. Accepted sample calculations and visual layouts are unchanged.

The v1.1.0 release/tag/assets remain immutable: its cancellation request took effect after publication. The user authorized v1.1.1 as the corrective release. No dependencies were upgraded. General reasoning and repair remain Agent-assisted; Windows/macOS/native PowerPoint and company-platform certification are unverified.

## Install / 安装

Download `goujian-strategy-slides-v1.1.1.zip` and `SHA256SUMS.txt`. Verify SHA256 and extract the complete folder with its only root `SKILL.md`. Follow README for Node/Python/Pillow/fonts and optional native render dependencies. See the full V1.1 release notes for the broader feature set.
