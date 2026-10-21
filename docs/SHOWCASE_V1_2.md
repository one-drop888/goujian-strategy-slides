# V1.2 showcase and previews

The V1.2 showcase is an optional review artifact built from the current engine and synthetic fixtures. It is not required at runtime and is not included in the installer ZIP.

![V1.2 actual renders](visual/v1.2/hero.png)

*Actual LibreOffice renders on the executed Linux host. All content is synthetic or project-authored; it is not real business evidence.*

## Eight cases

| Case | Kind | Pages | What it demonstrates | Hash manifest |
|---|---|---|---|---|
| Executive incomplete business | Reasoning deck | 7 | KPI reconciliation, unknown causes, proposed data actions, appendix baselines | `out/v1.2-showcase/cases/executive-incomplete-business/manifest.json` |
| Q4 six actions | Reasoning deck | 7 | Six action IDs, three groups, four dependency edges, owner/timing and approval boundary | `out/v1.2-showcase/cases/q4-six-actions/manifest.json` |
| Multisource consolidation | Reasoning deck | 7 | Nine-column native table, native chart, screenshot evidence, source coverage appendix | `out/v1.2-showcase/cases/multimodal-consolidation/manifest.json` |
| Theme light | Theme variant | 7 | Default light Q4 decision deck | `out/v1.2-showcase/cases/theme-light/manifest.json` |
| Theme brand-blue | Theme variant | 7 | Synthetic brand profile applied to the same plan | `out/v1.2-showcase/cases/theme-brand-blue/manifest.json` |
| Theme dark | Theme variant | 7 | Explicit dark profile with recorded conflicts | `out/v1.2-showcase/cases/theme-dark/manifest.json` |
| Dark chart types | Native chart diagnostic | 8 | Eight native chart types on a dark theme | `out/v1.2-showcase/cases/dark-chart-types/manifest.json` |
| Long title | Legacy title regression | 8 | Measured title, short title/subtitle, divider and body flow | `out/v1.2-showcase/cases/long-title/manifest.json` |

Each case manifest records the reference inputs and their hashes, exported spec, native PPTX, reasoning sidecar where applicable, hash-bound scene, QA report, actual render report, montage, PDF and per-page PNG hashes. The showcase root also records engine-source fingerprints, native source inspection, sanitized review records and a checksum manifest.

## Copy fixes in this build

Two actual copy/layout defects were corrected before this build, without changing the layout engine or shrinking fonts:

- **Q4 summary:** the body statement was shortened to prevent a lone “做” wrapping onto its own line, while preserving all six action IDs A1–A6 and the three groups (经营基础 / 转化测试 / 上市闸门). All Q4 variants (light, brand-blue, dark) were rerendered.
- **Multimodal chart-page subtitle:** the long backend-status line was replaced with `合成简报2026-Q3 · 源表比例，转化分母与统计口径待补充`. Detailed denominator, cohort, dedup, cross-period and significance limits remain in claims, speaker notes and the appendix.

Before/after:

| Fix | Preview |
|---|---|
| Q4 summary body wrapping | [q4-before-after.png](visual/v1.2/q4-before-after.png) |
| Multimodal chart-page subtitle | [multimodal-before-after.png](visual/v1.2/multimodal-before-after.png) |
| Theme variants | [theme-variants.png](visual/v1.2/theme-variants.png) |
| Scenario overview | [scenario-previews.png](visual/v1.2/scenario-previews.png) |

The `before/` folder in the showcase keeps the pre-fix round-3 renders separate from current cases. Previews use only actual current renders and the separately labeled before renders; no mockup was drawn.

## Review status

- Independent engine acceptance: 15/15 checks at `2c622db`, recorded in [docs/evidence/v1.2/reviews/](evidence/v1.2/reviews/). This is engine acceptance, not publication approval.
- Partial full-size visual review: pages 4–7 of the Q4 deck, pages 5–7 of the dark chart diagnostic and the round-2 montages, with findings recorded. It is not a complete deck approval.
- Final actual VQA: **PENDING**. It occurs after the writer stops; this repository does not report it as passed.
- Native PowerPoint macOS/Windows/ARM64: `NOT_RUN`. Agensi hosted runtime: `NOT_VERIFIED`.

The showcase `review/review-status.json`, `showcase.manifest.json`, `before/README.json` and `engine-source-fingerprint.json` state this scope explicitly. The manifest binds exact artifact hashes and the accepted engine/source fingerprint; it does not make PPTX bytes reproducible across PptxGenJS/Office versions.

## Reproduce

From the repository root:

```bash
npm run bootstrap
. .venv/bin/activate
npm run doctor -- --json
npm test
npm run showcase
npm run package
npm run package:showcase
```

- Engine source is hashed by `out/v1.2-showcase/engine-source-fingerprint.json`.
- `showcase.sha256` lists SHA256 values for all files except itself; verify from the repository root.
- The optional showcase ZIP is written to `dist/goujian-strategy-slides-v1.2.0-showcase.zip`.
- If any engine, input, asset or fixture changes, affected cases must be rebuilt and reviewed again. Documentation-only changes do not rewrite the already rendered bytes.

## Data and rights

All fixtures, screenshots, charts and illustrations are synthetic or project-authored under Apache-2.0. The showroom illustration is AI-generated scenery, not documentary evidence. No third-party corporate template, logo, font file, private corpus or licensed visual asset is included. Fonts are not embedded; the rendered text uses locally installed Noto families, and recipient rendering may differ.

## Release use

The showcase may be attached to the v1.2.0 Release as an optional asset after final review, with a separate checksum filename so it cannot overwrite the installer's `SHA256SUMS.txt`. Do not upload a freshly regenerated showcase with an old visual PASS; bind the exact reviewed hashes. Publication is a separate task and is not performed by this phase.
