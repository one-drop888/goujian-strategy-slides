# Goujian Strategy Slides V1.2 feasibility review

2026-10-21 · Strategic intelligence, deterministic validation and release packaging.

[简体中文](FEASIBILITY_REVIEW.zh-CN.md) · [Product overview](PRODUCT_OVERVIEW.md) · [Benchmarks A–J](BENCHMARKS_V1_2.md) · [Quality and validation](QUALITY_AND_VALIDATION.md)

Status vocabulary: **PROVEN** within the stated evidence and scope; **PARTIAL** for bounded or incomplete coverage; **DESIGNED** for a contract without a faithful implementation; **BLOCKED** when a required capability cannot run; **NOT_VERIFIED** when the claim or platform was not executed. These labels are scoped by evidence, not product-wide guarantees.

| Dimension | Status | Evidence and boundary |
|---|---|---|
| Architecture | PROVEN | Shared schema → composition → native PPTX → hash-bound scene → QA pipeline. Reasoning layer is additive; renderer core retained. |
| Reasoning plan contract | PROVEN within contract | Agent-authored sources, claims, dispositions, calculations, bindings and theme are validated before compile. 15/15 independent engine checks were rerun by Codex at `2c622db`. No independent reasoning model is claimed. |
| Deterministic arithmetic | PROVEN for four operators | `sum`, `difference`, `ratio`, `percent_change`, with unit/metric/window/denominator/zero checks and explicit tolerance. No arbitrary formulas, statistical significance or causal inference. |
| Source verification | PARTIAL | Structured JSON values can be checked with JSON Pointers and source SHA256. PDF/image/text/native-PPTX ledgers remain `REVIEWER_REQUIRED`; a locator or citation is not source truth. |
| Final artifact verification | PROVEN within trust scope | With a trusted expected hash, verification reads the exact PPTX bytes and checks chart caches, tables, KPI text, notes, embedded report and plan/spec hashes. It does not prove source truth or visual quality. |
| Theme decision | PROVEN for selection | Reference > brand > explicit user > automatic > default precedence; explicit dark and printable conflicts are recorded. light/brand-blue/dark variants were built and rendered. Configuration diversity is not 15 visually approved designs. |
| Multimodal / native images | PROVEN within contract | Native PNG/JPEG/WEBP, protected crop/focal/opacity/masks, captions and pixel-text provenance. No PPTX image postprocessing. |
| Asset reasoning | PARTIAL | The agent supplies categories and provenance; code enforces policy. No classifier, OCR or universal visual understanding. |
| Native source inspection | PROVEN for supplied fixtures | Two synthetic native source decks preserved a nine-column table with owner/review date, four chart values and embedded images with file/slide/shape locators. Arbitrary complex source reconstruction remains partial. |
| Title/layout | PROVEN within contract | Measured/equivalent estimates, short-title/subtitle, dynamic divider/body flow, explicit header-capacity errors. Long-title regression rendered; measurement is not exact PowerPoint shaping. |
| Provenance / scene | PROVEN | Native, pixel, annotation, data and insight provenance plus actual native object relationships. |
| Spatial QA | PROVEN within explicit scenes | Native geometry/order readback, occlusion, safe area, text/rule gap, density and conservative text-fit warnings. No arbitrary imported-intent inference. |
| Visual quality | PARTIAL | Eight current showcase cases and actual LibreOffice renders exist. Codex inspected representative pages and recorded pre-final findings; full-size final VQA is pending after writing stops. Eight renders are not eight visual approvals. |
| Packaging | PROVEN locally | Deterministic installer test builds identical bytes and checks one root SKILL, fixed timestamps/permissions, required assets, no PPTX/PDF or caches. Final clean-unzip installation evidence is recorded separately. |
| Installation | PROVEN on Linux x86_64 | isolate `.venv`, `npm ci`/bootstrap, doctor, tests, example build and render were executed from the installer ZIP in a Unicode/space path without symlinks. macOS/Windows/ARM64 are not verified. |
| Maintainability | PROVEN structurally | Small shared modules for reasoning, assets, titles and scene capture. No wholesale engine rewrite or heavyweight runtime dependency. |
| Profiles / fonts | PARTIAL | Fifteen real token configurations beyond color; Linux font resolution is proven. Fonts are not embedded; complete glyph coverage and recipient rendering are not proven. |
| PPT ingestion / fidelity | PARTIAL | Text, pictures, charts, tables, groups and master/layout candidates are mapped; complex reconstruction and ambiguous semantics remain partial. |
| Extensibility | PROVEN at boundary | Asset, provenance, relationship and reasoning JSON do not import PptxGenJS; the native adapter stays at the renderer boundary. |
| Multi-renderer | DESIGNED | HTML/Web renderer is not implemented. |
| QA reliability | PARTIAL | Negative regressions, hash-binding and actual review exist. No exact PowerPoint shaping, universal aesthetic oracle or autonomous repair. |
| Release workflow | NOT_VERIFIED | The manual `workflow_dispatch` workflow is updated and statically checked, but was not dispatched in this phase. No tag or public Release was created. |
| Open-source readiness | PARTIAL | Single Skill entry, synthetic notices, installer and showcase are locally built and checked. GitHub publication settings and anonymous asset download are outstanding manual steps. |
| Commercial readiness | PARTIAL | Documentation only. Community remains Apache-2.0. Supporter/Pro are future candidates with no checkout, account or listing. Agensi hosted runtime is NOT_VERIFIED. |
| Documentation accuracy | PROVEN for audited claims | Create, reasoning, native image and bounded QA paths execute. Edit/rebuild/reference/vision/repair boundaries are stated. Historical release documents are unchanged. |

28 Storylines · 86 semantic entries (74 IMPLEMENTED / 6 PARTIAL / 6 DESIGNED) · 27 Compositions · 15 Profiles · 15 Template Recipes · 15 Benchmark scenarios.

## Evidence anchors

- Engine acceptance: [Codex final acceptance](evidence/v1.2/reviews/codex-final-acceptance.json) — 15/15 at `2c622db`, engine acceptance only.
- Partial full-size review and remaining copy defects: [round-2 preview review](evidence/v1.2/reviews/codex-round2-preview-review.md); fixed copy is reflected in the showcase build.
- Source PPTX scope: [source acceptance](evidence/v1.2/reviews/codex-source-pptx-acceptance.md); actual inspection records are in the optional showcase (`source-inspection.json`).
- Dependency audit: [official npm audit record](evidence/v1.2/reviews/codex-dependency-audit-official.json) — 0 known advisories with the official registry.
- Showcase and previews: [showcase documentation](SHOWCASE_V1_2.md), `docs/visual/v1.2/`.
- A–J evidence matrix: [Benchmarks A–J](BENCHMARKS_V1_2.md).

## Verdict

**V1.2 RELEASE CANDIDATE for the documented Agent-assisted workflow.**

The reasoning contract, bounded arithmetic, native build, theme selection, source inspection and packaging are proven within their declared scopes. Semantic faithfulness, source truth, causal claims, visual quality and cross-platform rendering are not certified by code. Final independent visual acceptance and public publication remain separate gates.

Three runnable analytical families remain PROVEN for their declared schemas: business monthly data, mature nonlinear sales cohorts and CNY project snapshots. Source truth and causal inference are outside code certification. See [analytical boundaries](ANALYTICAL_LIBRARY.md).
