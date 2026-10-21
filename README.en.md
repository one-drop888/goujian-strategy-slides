# Goujian Strategy Slides｜构见·战略演示

[English (this page)](README.en.md) · [简体中文](README.md) · [Chinese mirror](README.zh-CN.md) · [Installation](#installation) · [Reasoning plan](#reasoning-plan-agent-judgment-deterministic-checks) · [Capability boundaries](#capability-boundaries) · [Benchmarks A–J](docs/BENCHMARKS_V1_2.md)

**Presentation Intelligence for AI Agents**

**Think clearly. Structure strategically. Present decisively.**

Goujian Strategy Slides is an open-source presentation skill for AI agents. It turns the reasoning behind a strong business presentation into an executable workflow:

**Think → Structure → Visualize → Build → Validate**

It combines management storytelling, storylines, action titles, semantic archetypes, composition grammar, data visualization, profile-driven design, native editable PPTX and quality gates. The agent supplies judgment; deterministic code validates, builds and exposes boundaries.

> Great presentations are not collections of beautiful slides. They are structured arguments designed to help people understand complex information and decide what to do.

**Question → Evidence → Judgment → Action** · **High information density ≠ high text density**

![V1.2 actual renders: executive review, Q4 actions and multimodal consolidation](docs/visual/v1.2/hero.png)

*Actual LibreOffice renders from V1.2. Every example is synthetic or project-authored and is not a real business record.*

## What V1.2 includes

- **Reasoning Plan:** auditable JSON for sources, claims, content dispositions, deterministic calculations, numeric bindings and theme decisions, compiled to native editable PPTX, an exported spec, a hash-bound scene and a reasoning sidecar.
- **Bounded deterministic checks:** `sum`, `difference`, `ratio` and `percent_change`, with unit, time-window, metric, denominator and zero checks. There is no general formula engine, significance test or causal inference.
- **Layered source checking:** structured JSON sources can be compared with source bytes through JSON Pointers. Numeric ledgers extracted from PDFs, images, text or native PPTX remain reviewer-required; a citation is not proof of truth.
- **Theme decisions:** reference / brand / explicit user / automatic / default precedence is recorded; dark versus printable conflicts are disclosed. Three theme variants were actually rendered.
- **Eight showcase cases:** three reasoning decks, three theme variants, an eight-type dark native-chart diagnostic and a long-title regression. Each case carries reference inputs, exported spec, PPTX, render, QA and a hash manifest. See the [showcase](docs/SHOWCASE_V1_2.md).
- **Reproducible packaging:** the lightweight installer has one root `SKILL.md`, stable ordering, timestamps and permissions. The showcase is a separate optional artifact and never enters the installer.
- 28 management storylines, 86 semantic entries (74 IMPLEMENTED / 6 PARTIAL / 6 DESIGNED), 27 composition recipes, 15 profiles and 15 template recipes. Counts describe vocabulary, not 86 independent layouts.

The eight representative cases (58 pages) completed actual Linux LibreOffice visual review with `PASS_WITH_KNOWN_LIMITATIONS`, bound to the exact PPTX and page PNG hashes. Obtain release artifacts and checksums from [GitHub Releases](https://github.com/one-drop888/goujian-strategy-slides/releases); platform boundaries are stated below.

## Reasoning plan: agent judgment, deterministic checks

```text
Agent authors sources / claims / dispositions / calculations / numeric bindings / theme
                    ↓
validate_plan: structure · arithmetic · referential closure · coverage · bindings · theme
                    ↓
compile_plan: exported spec → composition + profile → native PPTX
                    ↓
Reasoning sidecar · scene · embedded report · structural QA · actual render
                    ↓
Semantic and visual reviewer (never an automatic approval)
```

The plan is agent-authored. This project has no independent general reasoning model. Validation proves only that declared structure and arithmetic fit the contract; source authenticity, semantic faithfulness, causality, aesthetics and recipient rendering still require review. See the [Reasoning Plan reference](skill/references/reasoning-plan.md) for JSON Pointer and final-hash trust scope.

```bash
# Validate only
node skill/scripts/validate_plan.js skill/reasoning/fixtures/q4-six-actions/plan.json --json

# Compile; --profile is an explicit user override, --force only replaces intended outputs
node skill/scripts/compile_plan.js skill/reasoning/fixtures/q4-six-actions/plan.json \
  --out out/q4.pptx --spec-out out/q4.spec.json --profile dark-executive
```

`compile_plan.js` never overwrites the plan, a source file or an asset. Correct the plan or source and validate again; do not use `--force` to bypass a conflict. Outputs include the PPTX, exported spec, `*.pptx.scene.json`, `*.pptx.reasoning.json`, an embedded report and speaker notes with claim traceability. Legacy deck JSON remains supported; decks built without a plan report reasoning `NOT_RUN`.

## Multimodal evidence and visual intelligence

Native images, charts, tables and interpretation share the same compositions. PNG/JPEG/WEBP assets enter PPTX directly. Screenshots default to contain; embedded pixel text and editable text remain distinct. Measured titles support `title_short` / `subtitle`, a dynamic divider and body flow. Builds emit a PPTX-hash-bound scene for spatial checks covering evidence occlusion, text/rule collisions and source relationships.

Asset classification, semantic rewriting and visual repair remain agent-assisted. There is no automatic OCR, arbitrary lossless PPTX editor, autonomous vision engine or cross-renderer layout engine. Font measurement is an estimate; structural QA cannot prove the absence of rendered text collisions, so inspect the final frame.

Keep slide-visible subtitles in plain business language. Put backend tokens such as `NOT_PROVIDED`, extraction limitations and method caveats in the report, notes or appendix. See the [multimodal contract](docs/MULTIMODAL_CONTRACT.md).

## Installation

Use **Node.js 18+ and Python 3.9+** with `node`, `npm` and `python3` on PATH. Install the complete repository; copying `skill/` alone is insufficient. Run commands from the repository root.

```bash
git clone https://github.com/one-drop888/goujian-strategy-slides.git
cd goujian-strategy-slides

# Preview actions; then run npm ci, create an isolated .venv and install Pillow
npm run bootstrap -- --dry-run --json
npm run bootstrap
. .venv/bin/activate

# Reports tool presence and versions; does not prove execution or visual approval
npm run doctor -- --json

npm test
npm run validate:example
npm run build:example
npm run qa:example
```

The equivalent manual flow is:

```bash
npm ci
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-render.txt
```

Outputs are written to `out/executive-review.pptx` and `out/quality-report.json`. `npm ci` reproduces the committed lockfile. No npm registry publication is required.

Core build, schema, geometry and PPTX inspection work without render tools. `qa:example` attempts rendering and reports `UNAVAILABLE` when dependencies are missing; that is **not** a visual pass. Optional full rendering requires:

- **LibreOffice** (`soffice`)
- **Poppler** (`pdftoppm`)
- **Noto Sans / Noto Sans CJK SC** plus Fontconfig
- Debian/Ubuntu packages: `libreoffice-impress poppler-utils fontconfig fonts-noto-core fonts-noto-cjk`

Fonts are not bundled or embedded. Recipients must install the fonts or use a custom profile with available families. The executed host is Linux x86_64; macOS needs the tools on PATH; Windows should use WSL2 for the documented commands. Native Windows, macOS, ARM64 and Microsoft PowerPoint rendering are `NOT_RUN`; do not infer cross-platform parity.

### Installer and showcase

```bash
npm run package            # dist/goujian-strategy-slides-v1.2.0.zip
npm run showcase           # out/v1.2-showcase (optional review build)
npm run package:showcase   # dist/goujian-strategy-slides-v1.2.0-showcase.zip
```

The installer extracts to one `goujian-strategy-slides/` folder with a single root [SKILL.md](SKILL.md). It contains the full runtime, examples, profiles, schemas and tests, but no `node_modules/`, `.venv/`, `out/`, caches or PPTX. The showcase ZIP is a separate optional review artifact, not a runtime requirement. Platform import and security scanning still require target-platform tests.

Obtain official versions, installers and checksums from [GitHub Releases](https://github.com/one-drop888/goujian-strategy-slides/releases). Publication requires an explicit version and approved main-branch SHA; ordinary pushes do not publish, and existing tags and assets are never overwritten.

## Benchmarks A–J

| ID | Scenario | Executed in this round |
|---|---|---|
| A | Executive review with incomplete evidence | Seven-page reasoning deck; evidence gaps and data actions remain explicit |
| B | Q4 six actions | Six action IDs, three groups and four dependency edges; actually rendered |
| C | Nonlinear sales analytics | Existing analytics family plus 24 analytics tests |
| D | Multisource consolidation | Nine-column native table, owner/review date, native chart and screenshot evidence |
| E | Eight dark native charts | Eight-page native-chart diagnostic; included in the final independent 58-page VQA |
| F | Long title and dynamic subtitle | Eight-page title/divider regression |
| G | Three theme variants | light / brand-blue / dark, seven rendered pages each |
| H | Native source-PPTX inspection | File/slide/shape locators, nine columns, chart values and embedded image hashes |
| I | Clean install and recovery | Unicode/space path, no symlinks, doctor/build/QA record |
| J | Agent end-to-end | Qoder through plan, build, render, QA, critique and bounded repair |

Exact evidence paths, statuses and limitations are in [Benchmarks A–J](docs/BENCHMARKS_V1_2.md). A–J is an evidence matrix; the final independent VQA covers the 8 showcase cases and 58 pages only. The 15 legacy benchmark scenarios remain visual `NOT_RUN`, and all 15 profiles were not fully visually tested. Native PowerPoint on macOS/Windows/ARM64 is `NOT_RUN`; Agensi/company-hosted runtime is `NOT_VERIFIED`.

## Capability boundaries

| Capability | V1.2 status | What actually runs |
|---|---|---|
| Create | Implemented | Validated semantic JSON → native editable PPTX |
| Reasoning Plan | Implemented within contract | Structure, arithmetic, references, coverage, bindings and theme checks; no independent reasoning model |
| Deterministic calculations | Implemented, bounded | Four operators with unit/window/metric/denominator checks; no statistics or causal inference |
| Source verification | Partial | JSON Pointer byte checks for structured JSON; other sources need a reviewer ledger |
| Final hash verification | Implemented, bounded | Exact PPTX bytes, chart caches, tables, KPIs, notes and embedded report; not source truth |
| Theme decision | Implemented | Precedence, dark-conflict disclosure and token-driven output; not recipient font proof |
| Edit | Partial | Replace text within individual nodes; no intelligent reflow |
| Rebuild | Partial | Agent inspects the source and authors a new spec; no lossless converter |
| Template reuse | Partial | Storyline/profile recipes; no imported master fidelity |
| Style extraction | Partial | Theme, font and geometry statistics; agent interprets the result |
| Native editable PPTX | Implemented | Text, shapes, tables and supported native charts |
| Overflow / overlap | Partial | Bounding boxes and peer-overlap candidates; no exact text-fit proof |
| Font QA | Partial | Local family availability; not glyph coverage, embedding or recipient rendering |
| Render / montage | Implemented, optional | LibreOffice → PDF → PNG; Pillow montage |
| Visual QA | Partial | Human/vision-agent review bound to PPTX hash; never an automatic proof |
| Repair loop | Partial | Agent changes the spec and rerenders; no automatic deterministic visual repair engine |
| Planner | Partial | Keyword routing helpers; evidence reasoning remains the agent's work |
| HTML renderer | Designed | No HTML output |

Waterfall/bridge, combo, scatter/bubble and heatmap have no faithful implementation. Abstract map, relationship and Sankey-like entries are explicitly partial. Canvas support is 16:9 only. Long content must be split or edited; passing a capacity check does not prove readability.

## Showcase, review and commercial scope

The eight actual renders, inputs, hashes and before/after comparisons are in the [showcase documentation](docs/SHOWCASE_V1_2.md) and `docs/visual/v1.2/`. Independent evidence includes 15/15 engine checks, final 8-case/58-page visual review and source-byte checks under [docs/evidence/v1.2/reviews/](docs/evidence/v1.2/reviews/). These results cover the declared synthetic fixtures on Linux; source semantics, causality and recipient rendering still require review.

The Community core, including doctor, QA and defect fixes, remains free under Apache-2.0. Supporter and Pro are future candidates only: no account, payment, listing or launch date is provided. Pro would reuse the same rendering engine. Running this project's complete Node/Python workflow inside Agensi has not been verified or certified. See [Commercial readiness](docs/COMMERCIAL_READINESS.md).

## Architecture and contributing

```text
Agent reasoning → Reasoning Plan → deterministic validation → exported spec
                                                               ↓
                                      Storyline / archetype → composition + profile
                                                               ↓
                                            native PPTX backend → scene / QA / render
                                                               ↓
                                            semantic and visual review → bounded repair
```

Planning and composition layers do not import PptxGenJS. Rendering coordinates remain in the PPTX backend; a shared cross-renderer layout engine is future work. See [architecture](docs/architecture/ARCHITECTURE.md), [quality and validation](docs/QUALITY_AND_VALIDATION.md), [migration from V1.1.1](docs/MIGRATION_V1_1_1_TO_V1_2.md) and [contributing](CONTRIBUTING.md).

There is one product and one Presentation Library across agent runtimes. Platform adapters reuse it rather than maintaining separate editions.

## License

[Apache-2.0](LICENSE). Runtime dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICE.md). JSZip is used under its MIT option; PptxGenJS, Ajv and image-size are MIT. No benchmark source code, commercial template, font file or proprietary visual asset was copied. Do not publish private source decks or unlicensed fonts/assets.
