# Goujian Strategy Slides v1.3.1

**Enterprise security compatibility patch｜企业安全兼容补丁**

## 简体中文

V1.3.1 是面向企业安全扫描兼容的补丁版本。它不改变产品能力、艺术方向、原生图表、数值语义或历史验收证据，重点是把运行时中不必要的动态执行改为等价的静态实现，并让最终 ZIP 的安全预检更完整、更可审计。

主要变化：

- Python 内部模块加载改为普通静态导入；旧的 `core/qa/spec-check.py` 路径继续保留为兼容入口，公共符号与 CLI 不变。
- 分析回读使用的固定 `node -e` 载荷替换为静态入口 `core/qa/recompute_analytics.js`，仍通过 JSON stdin/stdout、固定路径和超时调用。
- Doctor/Bootstrap 的固定 `python -c` 探针替换为静态入口 `scripts/probe_env.py`；解释器选择、隔离 `.venv` 和受限依赖安装行为不变。
- 保留必要的字体测量、Pillow 图片处理、LibreOffice/Poppler 渲染和 fontconfig 查询；这些调用继续使用已知可执行文件和参数数组，并为部分原本未限时的调用补充超时与错误报告。
- 主安装 ZIP 为精简运行时；完整源码/开发 ZIP 保留完整测试与基准工作流。运行时 `npm test` 执行真实的已安装运行时冒烟验证，并如实披露未执行的可选图片步骤；它不冒充完整开发测试套件。
- 发布工作流在创建 tag 前，从最终运行时 ZIP 在独立 Unicode 目录中执行干净安装：项目本地 Bootstrap 安装锁定 npm 依赖与隔离 Pillow，并运行 secure/core 冒烟、文档化构建/QA/渲染、三个分析配方、受保护文件哈希比较与可重现重打包；不链接 node_modules，不叠加开发文件，不替换已发布的生产模块。
- `security_preflight.py` 支持 runtime/source/legacy 三种分布画像，检查最终 ZIP 的全部文本成员，区分可执行代码、惰性字符串/注释、文档与配置，并输出成员路径、行号、上下文和用途。旧的 v1.3.0 基线仍可按 legacy 结构画像审计。
- 企业平台报告的原始字面量为 `wxect`。本版本没有隐藏、编码、别名化或拆分任何执行模式；扫描器自身和开发文档中的该字面量会作为库存条目公开列出，而不是伪装成可执行行为。
- 公司平台与 Agensi 的实际上传/审核仍未执行：`COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`。公开静态预检 PASS 不等于企业平台批准。
- 继续使用 Apache-2.0，保留第三方说明与既有历史证据；不重写产品能力，不替换旧 tag/release。

运行时与源码包使用同一版本、同一提交和同一锁定依赖。完整运行契约、验证边界和未执行项见[安全与能力对等说明](SECURITY_PARITY_V1_3_1.md)、[安装与恢复](INSTALLATION.md)与[变更记录](../CHANGELOG.md)。本地 `out/` 日志不是公开证据；发布时随附的 JSON 回执才是外部证据，最终校验和以冻结时的发布清单为准。

## English

V1.3.1 is a compatibility patch for enterprise security scanning. It does not change product capabilities, art direction, native charts, numeric semantics or historical acceptance evidence. It replaces unnecessary runtime dynamic execution with equivalent static implementations and makes final-ZIP preflight more complete and auditable.

- Python internal module loading now uses ordinary static imports. The old `core/qa/spec-check.py` path remains as a compatibility entry with unchanged public symbols and CLI.
- The fixed `node -e` analytics-readback payload is replaced by `core/qa/recompute_analytics.js`, still invoked by fixed path through JSON stdin/stdout with a timeout.
- Fixed `python -c` Doctor/Bootstrap probes are replaced by `scripts/probe_env.py`. Interpreter selection, the isolated `.venv` and locked dependency installation are unchanged.
- Necessary font measurement, Pillow image processing, LibreOffice/Poppler rendering and fontconfig queries remain, using known executables and argument arrays. Timeouts and error reporting were added to calls that previously had no time limit.
- The primary installer is the minimal runtime. A separate complete source/development ZIP retains the full test and benchmark workflow. Runtime `npm test` performs an honest installed-runtime smoke check and discloses optional image steps that did not run; it does not impersonate the full development suite.
- Before creating a tag, the release workflow clean-installs the final runtime ZIP into an independent Unicode-named directory: project-local Bootstrap installs locked npm dependencies and isolated Pillow, then secure/core smoke, documented build/QA/render, all three analysis recipes, protected-file hashes and byte-reproducible repackaging run. It does not link `node_modules`, overlay development files or replace a shipped production module.
- `security_preflight.py` supports runtime/source/legacy distribution profiles, inspects every text member of the final ZIP, separates executable code from inert strings/comments, documentation and configuration, and records member path, line, context and purpose. The archived v1.3.0 baseline remains auditable under the legacy structural profile.
- The raw company-reported literal is `wxect`. This release does not hide, encode, alias or split any execution pattern. Occurrences in the scanner itself and development documentation are exposed as inventory entries, not mislabelled as executable behaviour.
- Company-platform and Agensi upload/review were not executed: `COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`. A public static preflight PASS is not enterprise-platform approval.
- Apache-2.0, third-party notices and historical evidence are preserved. No old tag or release is replaced.

Runtime and source archives share one version, commit and lockfile. See the [security and capability-parity note](SECURITY_PARITY_V1_3_1.md), [installation and recovery](INSTALLATION.md) and [changelog](../CHANGELOG.md) for the full contract and unexecuted items. Local `out/` logs are not public evidence; the JSON receipts published with the release are the external evidence, and final checksums are set at freeze time.
