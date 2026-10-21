# V1.2 showcase and previews

The V1.2 showcase is an optional review artifact built from the current engine and synthetic fixtures. It is not required at runtime and is not included in the installer ZIP.

![V1.2 actual renders](visual/v1.2/hero.png)

*Actual LibreOffice renders on the executed Linux host. All content is synthetic or project-authored; it is not real business evidence.*

## Eight cases

| Case | Kind | Pages | What it demonstrates | Hash manifest |
|---|---|---|---|---|
| Executive incomplete business | Reasoning deck | 7 | KPI reconciliation, unknown causes, proposed data actions, appendix baselines | `out/v1.2-showcase/cases/executive-incomplete-business/manifest.json` |
| Q4 six actions | Reasoning deck | 7 | Six action IDs, three groups, four dependency edges, responsibility roles, timing and one explicit prereq→next convention | `out/v1.2-showcase/cases/q4-six-actions/manifest.json` |
| Multisource consolidation | Reasoning deck | 7 | Nine-column native table, native chart, screenshot evidence, source coverage appendix | `out/v1.2-showcase/cases/multimodal-consolidation/manifest.json` |
| Theme light | Theme variant | 7 | Default light Q4 decision deck | `out/v1.2-showcase/cases/theme-light/manifest.json` |
| Theme brand-blue | Theme variant | 7 | Synthetic brand profile applied to the same plan | `out/v1.2-showcase/cases/theme-brand-blue/manifest.json` |
| Theme dark | Theme variant | 7 | Explicit dark profile with recorded conflicts | `out/v1.2-showcase/cases/theme-dark/manifest.json` |
| Dark chart types | Native chart diagnostic | 8 | Eight native chart types on a dark theme | `out/v1.2-showcase/cases/dark-chart-types/manifest.json` |
| Long title | Legacy title regression | 8 | Measured title, short title/subtitle, divider and body flow | `out/v1.2-showcase/cases/long-title/manifest.json` |

Each case manifest records the reference inputs and their hashes, exported spec, native PPTX, reasoning sidecar where applicable, hash-bound scene, QA report, actual render report, montage, PDF and per-page PNG hashes. The showcase root also records engine-source fingerprints, native source inspection, sanitized review records and a checksum manifest.

## Copy fixes in this build

Two actual copy/layout defects and four late content corrections were applied without changing the layout engine or shrinking fonts.

Earlier layout fixes:

- **Q4 summary:** the body statement was shortened to prevent a lone “做” wrapping onto its own line, while preserving all six action IDs A1–A6 and the three groups (经营基础 / 转化测试 / 上市闸门). All Q4 variants (light, brand-blue, dark) were rerendered.
- **Multimodal chart-page subtitle:** the long backend-status line was replaced with `合成简报2026-Q3 · 源表比例，转化分母与统计口径待补充`. Detailed denominator, cohort, dedup, cross-period and significance limits remain in claims, speaker notes and the appendix.

Late content corrections:

- **Q4 dependency direction and wording:** the visible roadmap and appendix now both use 前置→后续: A1→A2, A2→A3, A4→A5, A1→A6. The synthetic source keeps its original 行动→前置 order under an explicit `依赖边（行动 → 前置）` label, so both directions remain traceable. The unsupported `四个复核节点` / `六位责任人` wording was replaced by `六项行动的顺序、责任角色与四条依赖关系`; all six action IDs, three groups, six dates and four edges remain.
- **Multimodal followup and pilot:** the unsupported claim that the South workflow could be copied to the Southwest was removed. The proposal now verifies the conversion denominator, cohort, dedup and cross-period definitions plus the actual followup workflow in both regions before evaluating a candidate Southwest pilot. Comparison and evaluation are defined before the pilot, all outcomes are recorded (not only adverse results), roles/timing are marked 待确认, and the 24 convenience interviews remain hypothesis-only.
- **Executive trend title:** the title is now exactly `收入逐月升至960万元，环比6.67%，仍差目标40万元`. Six observed monthly points are not presented as six proven growth intervals; no data, chart or layout changed.
- **Source ledgers:** affected fixture source hashes and locators were updated deterministically; all reasoning-plan validation and source-closure checks pass.

The optional ZIP also retains the first V1.2 dogfood montages for all three representative decks under `out/v1.2-showcase/before/*-first-round-montage.png`. These are explicitly unapproved historical synthetic outputs, provided to compare the full iteration with the final case montages. Exact intermediate Git commits are not asserted; original render timestamps and PNG hashes are recorded in `before/README.json`.

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
- Partial full-size visual review from an earlier render round: pages 4–7 of the Q4 deck, pages 5–7 of the dark chart diagnostic and the round-2 montages. Those findings drove fixes but do not approve the current rebuild.
- Final independent actual VQA of the current build: **PASS_WITH_KNOWN_LIMITATIONS**. Codex reviewed all 58 pages across the 8 cases from actual Linux LibreOffice renders with synthetic fixtures, bound to exact PPTX and page hashes; the source-byte equivalence attestation is recorded separately. This is not publication approval.
- The 15 legacy benchmark scenarios remain visual `NOT_RUN`; all 15 profiles were not fully visually tested. Native PowerPoint macOS/Windows/ARM64: `NOT_RUN`. Agensi hosted runtime: `NOT_VERIFIED`.

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

The showcase may be attached to the v1.2.0 Release as an optional asset carrying the final reviewed hashes, with a separate checksum filename so it cannot overwrite the installer's `SHA256SUMS.txt`. Do not upload a freshly regenerated showcase with an old visual PASS; bind the exact reviewed hashes. Publication is a separate task and is not performed by this phase; no GitHub Release exists yet.
