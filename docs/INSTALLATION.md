# Installation and recovery

Install the complete repository or release installer. A wrapped ZIP extracts to `goujian-strategy-slides/` with the only `SKILL.md` at that directory root. This is the skill root; `core/`, `skill/`, `scripts/` and package files must remain beside it. Platform display names do not change the skill ID `goujian-strategy-slides`.

## Runtime tiers

| Tier | Requirements | Scope |
|---|---|---|
| Core | Node18+, Python3.9+, project npm dependencies | Native text/shapes/tables/charts, schema, calculations, core checks |
| Secure images/full QA | Python3.11+, Pillow13.0.0, core tier | Image decoding, pixel text measurement, full test suite |
| Render | Secure tier + LibreOffice, Poppler, fontconfig and fonts | Linux-tested PDF/PNG render and montage; recipient Office parity remains unverified |

Use a maintained Node LTS release (24 recommended) and a supported Python release with current security patches. The older core floor records compatibility, not vendor security support.

No old Pillow fallback is installed on Python3.9/3.10. Presence of an affected Pillow version is not readiness. The runtime reports this limitation; it does not weaken security checks to obtain a PASS. No font file or Office runtime is bundled.

## Release archives and test contract (V1.3.1)

| Archive | Use | What its tests prove |
|---|---|---|
| `goujian-strategy-slides-v1.3.1.zip` | Primary installation (minimal runtime) | `npm test` / `npm run test:core` run the real installed-runtime smoke: schema, representative charts, analysis and plan flows. Core mode discloses Pillow-dependent image steps as NOT_RUN. It is not the full development suite. |
| `goujian-strategy-slides-v1.3.1-source.zip` | Complete source/development | The original full source test and benchmark workflow, using the root `package.json`. |
| `goujian-strategy-slides-v1.3.1-showcase.zip` | Review evidence only | Not an installation target; adds only `out/v1.3-showcase/` to the runtime payload. |

The runtime ZIP's `package.json` is explicitly mapped from `distribution/runtime-package.json`; every other runtime member must match the approved commit. The 189 declared runtime files are the protected production set; the mapped `package.json` is development metadata, so the 190 archive members are not all byte-identical. Dependencies, version, name and overrides are identical across the runtime and source archives. Development-only benchmark, showcase and fixture commands are omitted from the runtime manifest and documented as such.

### 发行包与测试契约（中文摘要）

- 主安装包 `goujian-strategy-slides-v1.3.1.zip` 为精简运行时。它的 `npm test` / `test:core` 是真实的已安装运行时冒烟验证，不是完整开发测试套件；无 Pillow 的核心层会明确披露未执行的图片步骤。
- `-source.zip` 为完整源码/开发包，保留原有全量测试与基准工作流；`-showcase.zip` 仅用于评审，新增 `out/v1.3-showcase/`，不是安装包。
- 两个安装包使用同一版本、同一提交和同一锁定依赖。运行时包内 `package.json` 由 `distribution/runtime-package.json` 显式映射，其余成员须与批准提交逐字节一致。
- 最终 ZIP 预检使用 runtime/source/legacy 三种画像，扫描全部文本成员并区分可执行代码与惰性字符串/注释。公司平台与 Agensi 的实际上传/审核仍未执行，`COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`；公开静态预检 PASS 不等于企业平台批准。

Every release archive is additionally scanned by the pinned third-party Skill Scanner before any tag or Release. That gate fails closed on unreviewed HIGH/CRITICAL findings and always retains raw JSON/SARIF and logs. JavaScript behavioral and semantic analysis are explicitly NOT_RUN. See the [release security gate](https://github.com/one-drop888/goujian-strategy-slides/blob/main/docs/RELEASE_SECURITY_GATE.md) for the local command, review ledger, lock upgrade and failure artifacts.

每个发布包在打标签或发布前还会由固定版本的第三方 Skill Scanner 扫描。该门禁在存在未评审的 HIGH/CRITICAL 时失败关闭，并始终保留原始 JSON/SARIF 与日志；JavaScript 行为与语义分析明确为 NOT_RUN。本地命令、评审账本、锁升级与失败证据说明见[发布安全门](https://github.com/one-drop888/goujian-strategy-slides/blob/main/docs/RELEASE_SECURITY_GATE.md)。

## Install project dependencies

From the skill root:

```bash
npm run bootstrap -- --dry-run --json
npm run bootstrap
. .venv/bin/activate
npm run doctor -- --json
```

Bootstrap runs project-local `npm ci`, creates `.venv` with the selected Python and installs declared Python requirements there. It does not change global Python, npm configuration, install a system runtime, contact a business service or upload content. Registry downloads are visible planned actions. Repeat runs skip verified matching state; a missing dependency is recovered. Use `--force` for an intended reinstall. Select Python explicitly with `--python /path/to/python3.11`, or `GOUJIAN_PYTHON`; an explicitly selected unsupported interpreter fails rather than silently switching runtimes.

PowerShell: `.\.venv\Scripts\Activate.ps1`. If your system names Python `python` rather than `python3`, supply its absolute path to Bootstrap and ensure the activated environment's Python is selected for project commands. Doctor reports selected paths and missing tools. Do not change machine-wide execution policy merely to run this project.

Manual alternative:

```bash
npm ci
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-render.txt
```

If npm reports `EALLOWSCRIPTS` before installing dependencies, inspect the configuration named in npm's error. The acceptance host had a pre-existing `allow-scripts` setting that npm11 rejects for project installs. A clean test used a command-scoped empty user configuration with the same registry; it did not edit machine configuration. In a managed environment, correct the setting through the applicable npm policy rather than disabling required installation controls. Bootstrap reports this error and leaves global configuration intact.

## Render tools and fonts

Debian/Ubuntu (requires normal system package authorization):

```bash
sudo apt-get update
sudo apt-get install fontconfig fonts-noto-core fonts-noto-cjk libreoffice-impress poppler-utils
# Optional: labeled 12-page contact sheets in the full benchmark/showcase
sudo apt-get install imagemagick
```

On macOS/Windows, install Python, Node, LibreOffice, Poppler utilities and Noto fonts from their official distributions, and make the `node`, `npm`, `python3`, `soffice`, `pdftoppm` and font tools discoverable by the process that runs the agent. Restart that process after a PATH change if required. These native platforms have not been accepted as visually identical to Linux; use Doctor and inspect an actual native PowerPoint render before production delivery. [Python](https://www.python.org/downloads/) · [Node](https://nodejs.org/en/download) · [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) · [Poppler](https://poppler.freedesktop.org/) · [Noto](https://fonts.google.com/noto)

The core renderer makes its montage with Pillow. The full benchmark additionally uses the ImageMagick `montage` utility for labeled contact sheets of up to12 pages; without it those optional sheets report UNAVAILABLE while individual PNGs and the core montage remain available.

If a tool is absent, QA reports UNAVAILABLE/NOT_RUN. Geometry cannot substitute for rendering. An installed font may differ on another machine; retain font-resolution notes and inspect Chinese glyphs and title wrapping.

## First run

```bash
npm test
npm run validate:example
npm run build:example
npm run qa:example
npm run render:example
```

For the Pillow-free core tier, run `npm run test:core` instead of the full suite. `npm install` is supported; `npm ci` is preferred for a clean locked install. The build writes `out/executive-review.pptx` plus a scene sidecar. The QA report and render directory are separate; success generating a file is not visual approval.

Unicode paths are supported by argument-array subprocess calls; the release workflow clean-installs the actual runtime ZIP in a Unicode-named directory before tag creation and publishes the receipt. Windows symlink-dependent adversarial tests may require OS support and must report a skip rather than a false pass.

## Agent and platform import

Let the agent discover the root `SKILL.md`; adapters in `adapters/` use the same root and core. An upload platform may require the wrapped folder or its contents. Repack only from the same validated source, retain exactly one root skill entry, and rerun preflight after any change. The official release currently provides the wrapped single-skill ZIP; an undocumented company-specific fork is unnecessary.

```bash
npm run package
npm run preflight -- dist/goujian-strategy-slides-v1.3.1.zip --json out/package-preflight.json
# Or build the default runtime ZIP and let preflight find dist/goujian-strategy-slides-v1.3.1.zip
npm run preflight
```

Inspect the SHA256 checksum before extraction. Static preflight checks the actual archive, metadata, permissions, links, code patterns, text inventory and declared dependencies under runtime, source or legacy profiles. The archived v1.3.0 baseline is accepted under the legacy structural profile with code findings reported, not silently erased. The preflight reports the company-reported `wxect` literal separately from `exec`; it does not hide or rename it. It is not enterprise or marketplace certification. Company-platform upload/security and Agensi are **NOT_VERIFIED** until a real upload and approval record exist: `COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`. Do not publish internal platform logs or credentials. See [security and capability parity](SECURITY_PARITY_V1_3_1.md) and [release notes](V1_3_1_RELEASE_NOTES.md).
