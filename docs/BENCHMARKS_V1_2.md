# Benchmarks A–J (V1.2)

This matrix replaces registry counts with ten executed or explicitly unexecuted evidence cases. A–J is not a claim that every output passed visual review. Paths are relative to the repository root; the showcase directory is an optional local artifact and is not committed.

## Executed environment

| Item | Value |
|---|---|
| Host | Ubuntu 26.04.1 LTS, kernel 7.0.0-38-generic, x86_64 |
| Node / npm | 24.18.0 / 11.19.1 |
| Python / Pillow | 3.14.4 / 12.1.1 |
| Renderer | LibreOfficeDev 26.8.0.0 alpha0; Poppler 26.05.0 |
| Native Microsoft PowerPoint | NOT_RUN (macOS, Windows, ARM64) |
| Agensi / company-hosted runtime | NOT_VERIFIED |

The actual rendered images come from LibreOffice on this Linux host. They are not evidence of Microsoft PowerPoint fidelity, recipient font availability or cross-platform parity.

## Matrix

| ID | Scenario | Actual evidence | Status | Limitations |
|---|---|---|---|---|
| **A** | Executive review with incomplete evidence | `out/v1.2-showcase/cases/executive-incomplete-business/manifest.json` (7 pages), actual render and montage, exported spec, reasoning sidecar, QA `PASS_WITH_NOTES`, structural QA `PASS` | Build + structural checks PASS; final independent VQA `PASS_WITH_KNOWN_LIMITATIONS` (8-case/58-page scope) | Synthetic business JSON; product-mix and discount causes remain unknown; agent recommendations are visibly proposed, not supplied facts |
| **B** | Q4 six actions | `out/v1.2-showcase/cases/q4-six-actions/manifest.json` (7 pages), actual render, [before/after preview](visual/v1.2/q4-before-after.png) | Build + structural checks PASS; final independent VQA `PASS_WITH_KNOWN_LIMITATIONS` (8-case/58-page scope) | Six action IDs, three groups and four dependency edges preserved; deadlines/roles are synthetic; no ROI or schedule simulation |
| **C** | Nonlinear sales analytics | [tests/test_analytics.js](../tests/test_analytics.js), [tests/test_analytics_qa.py](../tests/test_analytics_qa.py), [analytical contract](ANALYTICAL_LIBRARY.md), [example input](../skill/analytics/sales-conversion.json) | Test suite PASS (24 analytics cases in the Node suite plus QA coverage) | Mature-cohort schema only; association is not causal lift; optional trial branch; source truth remains the data owner's responsibility |
| **D** | Multisource consolidation | `out/v1.2-showcase/cases/multimodal-consolidation/manifest.json` (7 pages), `out/v1.2-showcase/source-inspection.json`, [before/after preview](visual/v1.2/multimodal-before-after.png) | Build + native source checks PASS; QA `PASS_WITH_NOTES`; final independent VQA `PASS_WITH_KNOWN_LIMITATIONS` (8-case/58-page scope) | The nine-column table, owner and review date come from the supplied synthetic source PPTX; conversion denominator/cohort/dedup/cross-period limits remain unknown; 24 interviews are a convenience sample; no significance test |
| **E** | Eight dark native chart types | `out/v1.2-showcase/cases/dark-chart-types/manifest.json` (8 pages), actual renders and montage, [final review record](evidence/v1.2/reviews/dark-chart-types.visual-review.json) | Build + structural checks PASS; final independent VQA `PASS_WITH_KNOWN_LIMITATIONS`; LibreOffice doughnut/area label density limits recorded | Diagnostic fixture, not a professional deck; native PowerPoint not run |
| **F** | Long title and dynamic subtitle | `out/v1.2-showcase/cases/long-title/manifest.json` (8 pages), actual render, montage | Build + structural checks PASS; final independent VQA `PASS_WITH_KNOWN_LIMITATIONS` (8-case/58-page scope) | Regression fixture with intentionally repeated regional pages, not a variety showcase; title measurement is an estimate |
| **G** | Three theme variants | `out/v1.2-showcase/cases/theme-light/manifest.json`, `out/v1.2-showcase/cases/theme-brand-blue/manifest.json`, `out/v1.2-showcase/cases/theme-dark/manifest.json`; 7 pages each; [theme preview](visual/v1.2/theme-variants.png) | Build + theme records PASS; actual renders; final independent VQA `PASS_WITH_KNOWN_LIMITATIONS` | Three representative variants, not all 15 profiles; configuration diversity is not 15 visually approved designs; fonts not embedded |
| **H** | Native source-PPTX inspection | `out/v1.2-showcase/source-inspection.json`, two source PPTX files and inspect reports under `out/v1.2-showcase/sources/`, [acceptance scope](evidence/v1.2/reviews/codex-source-pptx-acceptance.md) | 10/10 recorded native source checks PASS | Supplied synthetic fixtures only; table/chart/image provenance is not OCR or arbitrary complex-deck recovery; numeric extraction from native decks remains reviewer-required as a source ledger |
| **I** | Clean install, recovery and Unicode | [installation evidence](evidence/v1.2/installation.json) | Installer deterministic test PASS; clean-unzip install executed in a Unicode/space path without symlinks; build and QA recorded | Linux x86_64 only; no native Windows/macOS/ARM64 execution; no company platform import |
| **J** | Agent end-to-end | `out/v1.2-showcase/showcase.manifest.json`, [workflow evidence](evidence/v1.2/qoder-workflow.json), `out/v1.2-showcase/before/README.json`, `out/v1.2-showcase/review/review-status.json` | Plan → build → render → QA → critique → bounded repair executed on final code; final independent VQA completed within the 8-case/58-page scope | Agent-assisted workflow; independent acceptance is scoped, not publication approval; fixed copy only (no new layout engine/font shrinking) |

## What each case proves

- **A/B/D** exercise the plan contract, source/claim closure, deterministic calculations, numeric bindings and native build; they do not prove the underlying synthetic story is true.
- **C** proves the declared analytics schemas and formulas on supplied inputs; it does not certify source data, causal inference or statistical significance.
- **D/H** prove that the supplied synthetic native source deck preserves a nine-column table, owner/review date, chart values and embedded images with file/slide/shape locators. They do not make screenshots editable or verify arbitrary imported decks.
- **E/F** are diagnostics/regressions for native charts and measured titles, not showcases of deck-level variety.
- **G** proves the theme decision path and token application for three variants; it does not prove all profiles or recipient environments.
- **I/J** prove an installable and recoverable workflow on the executed host with bounded agent repair. They do not prove autonomous visual repair, cross-platform parity or publication approval.

## Not run or not verified

- Native Microsoft PowerPoint on macOS, Windows or ARM64: **NOT_RUN**.
- Agensi hosted execution and company platform import/scanning: **NOT_VERIFIED**.
- Final independent VQA of the 8-case / 58-page showcase: **PASS_WITH_KNOWN_LIMITATIONS** on Linux LibreOffice with synthetic fixtures, bound to exact PPTX and page hashes.
- The 15 legacy benchmark scenarios remain visual **NOT_RUN**; all 15 profiles were not fully visually tested.
- Native Microsoft PowerPoint visual acceptance of these 8 decks on macOS, Windows or ARM64: **NOT_RUN**.
- Exact PPTX byte reproducibility across Office/PptxGenJS versions: **NOT_CLAIMED**; artifact hashes bind only the exact built bytes.

## Reproduction

```bash
npm run bootstrap
. .venv/bin/activate
npm run doctor -- --json
npm test
npm run showcase
npm run package
npm run package:showcase
```

`npm run showcase` regenerates `out/v1.2-showcase` from the current engine, fixtures and review records. Regenerating invalidates the reviewed hashes and requires a new visual acceptance. The optional showcase may be attached to a release separately; it is never bundled into the installer.
