# Goujian Strategy Slides v1.0.1 · 构见·战略演示

This patch fixes Skill installation compatibility. The installable ZIP and source tree contain **exactly one `SKILL.md`**, at the repository root. The storyline, archetype, composition, template, profile, PPTX renderer, JSON spec and quality-gate capabilities are unchanged.

- The Chinese Skill description now names professional PPT creation and common business scenarios more clearly. Its instructions still state the limits of existing-deck editing and automated visual repair.
- Packaging rejects extra Skill entrypoints and a regression test checks archive integrity, metadata and required runtime files.
- A renderer cleanup comment was clarified for static security review. Its execution conditions and deletion scope were not changed.
- The release workflow publishes a directly verifiable SHA256 checksum alongside the ZIP.

Install the complete `goujian-strategy-slides-v1.0.1.zip` archive; the Skill root is the contained `goujian-strategy-slides/` directory. Target company-platform import and scanning have **not** been verified in that environment and need a platform-side retest.

---

本维护版本修复 Skill 安装兼容性。源码与正式 ZIP 均**只保留仓库根目录的一个 `SKILL.md`**；Storyline、Archetype、Composition、Template、Profile、PPTX 构建、JSON Spec 和 Quality Gate 能力不变。

- 中文技能描述更清楚地说明专业 PPT 制作及典型业务场景，正文继续明确已有 PPT 编辑和自动视觉修复的能力边界。
- 打包脚本拒绝重复技能入口；回归测试检查压缩包完整性、元数据与运行资源。
- 澄清渲染器清理注释，便于静态安全审查；执行条件及删除范围不变。
- 发布流程同时提供可直接验证的 SHA256 校验文件。

请安装完整的 `goujian-strategy-slides-v1.0.1.zip`；其中 `goujian-strategy-slides/` 为技能根目录。**目标公司平台的导入及安全扫描仍需平台侧人工复测**。
