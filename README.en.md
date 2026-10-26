# Goujian Strategy Slides｜构见·战略演示

[简体中文](README.md) · [English (this page)](README.en.md) · [Installation](#installation) · [Cases and validation](docs/BENCHMARKS_V1_3.md)

**Presentation Intelligence for AI Agents**

Think clearly. Structure strategically. Present decisively.

Goujian helps an agent turn complex material into an evidence-based, decision-useful presentation. The agent handles interpretation and design; deterministic code validates numbers, builds native editable PPTX and checks the result. Use it for business reviews, sales diagnostics, research, project performance and technical proposals.

**Think → Structure → Visualize → Build → Validate**

**Question → Evidence → Judgment → Action**

> Great presentations are not collections of beautiful slides. They are structured arguments designed to make complex information understandable and actionable.

High information density ≠ high text density.

![Business review: revenue trend and key metrics](docs/visual/v1.3/gallery-executive-dense/slide-04.png)

*Project-authored synthetic data, actually rendered from a V1.3 native PPTX. See [cases and validation scope](docs/BENCHMARKS_V1_3.md).*

## V1.3: analytical and visual intelligence

- **Explicit numeric meaning.** Distinguish fractions, stored percentages and percentage points. Share declared units, precision, missing-value policy and currency scales across titles, KPIs, charts and tables, with recorded transformations.
- **Charts built for a relationship.** Native bar, column, line, area, pie and doughnut charts use distinct series treatments. Actual, target and history can differ in color, dash and marker; the author chooses emphasis. Histograms require explicit equal-width numeric bins.
- **A reviewable argument.** Reasoning Plans record sources, claims, calculations and content dispositions. An optional Narrative Graph connects questions, evidence, slides and decisions. Duplicate candidates prompt review without deleting useful summary/detail pages.
- **Measured titles and retained evidence.** A readable single line is considered before balanced wrapping. Images, charts, text and annotations share compositions; screenshots remain pixel evidence while native text, tables and supported charts stay editable.
- **Checks on the actual output.** The Quality Gate combines spec validation, PPTX/workbook readback, geometry, fonts, spatial checks and rendering. Visual approval requires an independent review of the final pages.

**Semantic Accuracy → Visual Encoding → Perceptual Clarity → Management Insight**

[Generated cases and before/after](docs/BENCHMARKS_V1_3.md) · [Product overview](docs/PRODUCT_OVERVIEW.md) · [Feasibility and validation scope](docs/FEASIBILITY_REVIEW.md) · [Migration](docs/MIGRATION_V1_3.md)

## Installation

Core compatibility: Node.js18+ and Python3.9+. Use a maintained Node LTS release (24 recommended); the minimum is not a security-support promise. **Secure image processing, pixel text measurement and full rendering require Python3.11+ / Pillow13.** Older Python supports the Pillow-free core tier. Install the complete repository, not only `skill/`.

```bash
git clone https://github.com/one-drop888/goujian-strategy-slides.git
cd goujian-strategy-slides
npm run bootstrap -- --dry-run --json
npm run bootstrap
. .venv/bin/activate
npm run doctor -- --json
npm test
npm run validate:example
npm run build:example
npm run qa:example
```

Bootstrap installs project npm dependencies and a local `.venv`, not system tools. PowerShell activation: `.\.venv\Scripts\Activate.ps1`. Select an interpreter explicitly with `npm run bootstrap -- --python /path/to/python3.11`. Use `npm run test:core` for the Python3.9/3.10 core tier.

Actual rendering also needs LibreOffice, Poppler and fonts (Noto Sans / Noto Sans CJK SC by default). Follow [installation and recovery](docs/INSTALLATION.md). Doctor reports availability; it does not certify rendering or visual quality.

Alternatively download the installer and SHA256 from [GitHub Releases](https://github.com/one-drop888/goujian-strategy-slides/releases). Extract it, enter `goujian-strategy-slides/`, let your agent discover its only root `SKILL.md`, and install as above. One product, one core: adapters connect it to different agent platforms.

V1.3.1 is an enterprise security compatibility patch: the primary installer is the minimal runtime, with a complete source archive and an optional review archive. Product capabilities, native rendering and historical acceptance evidence are unchanged. Company-platform and Agensi approval remain unverified: `COMPANY_PLATFORM_SECURITY=NOT_VERIFIED`. [Patch notes](docs/V1_3_1_RELEASE_NOTES.md) · [Security and capability parity](docs/SECURITY_PARITY_V1_3_1.md)

## Use it

Establish the audience and decision question, then have your agent read `SKILL.md`. Start with an analytical input, an auditable plan or an existing JSON spec:

```bash
npm run analyze:business
npm run analyze:sales
npm run analyze:project

node skill/scripts/validate_plan.js skill/reasoning/fixtures/q4-six-actions/plan.json --json
node skill/scripts/compile_plan.js skill/reasoning/fixtures/q4-six-actions/plan.json --out out/q4.pptx --spec-out out/q4.spec.json

node skill/scripts/build_deck.js skill/examples/executive-review.json out/review.pptx
python3 skill/scripts/quality_gate.py out/review.pptx --spec skill/examples/executive-review.json --out out/review-qa.json --render-dir out/review-render
```

The three analytical recipes check periods, denominators, deduplication, mature cohorts and reconciliation. Test drives are optional behavior, never assumed to cause sales. Missing facts remain visible; over-capacity content is split or rejected, not silently dropped. See [analytical inputs](docs/ANALYTICAL_LIBRARY.md), [numeric/visual contracts](skill/references/analytical-visual-intelligence.md) and [narrative graph](skill/references/narrative-graph.md).

Keep the original spec, sources, PPTX, scene and QA. `effective_spec` is an internal transformed representation, not a new rebuild input. After a change, rebuild, render and review again; an old hash-bound review cannot approve new bytes.

## Boundaries

| Capability | Current scope |
|---|---|
| Create/rebuild | An agent authors the spec/plan; no built-in general source-to-deck reasoning model |
| Native editing | Text, shapes, tables and supported charts; text inside an image remains pixels |
| Existing PPTX | Single DrawingML text-node replacements; reconstruction/reference-style reasoning is agent-assisted, not lossless round-trip editing |
| Charts | Six native families; bar/column stacking and explicit equal-bin histograms. Missing or single-point areas require a line, KPI or table alternative. Scatter, bubble, waterfall and dual-axis/combo remain unsupported; use a faithful alternative |
| Evidence and claims | Structured source bytes and bounded arithmetic can be checked. Authenticity, causality, significance and business judgment require review |
| Visual QA | Structure + actual render + reviewer record; no autonomous aesthetic approval or deterministic visual repair |
| Platforms | Executed Linux scope is documented; native Windows/macOS/ARM64 PowerPoint remains unverified |
| Distribution security | Actual ZIP integrity/static preflight; company-platform and Agensi approval require separate real uploads |

The Community core remains **Apache-2.0**. Goujian Pro is a separate product design, not an available paid feature; correctness fixes stay in Community. [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICE.md) · [Changelog](CHANGELOG.md)
