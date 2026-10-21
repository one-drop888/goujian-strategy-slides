# Quality and validation

V1.2 separates executed checks, deterministic verification and visual judgment. Run `npm run capabilities` to detect the available levels; missing native rendering reports `VISUAL_QA=UNAVAILABLE`.

## Capability ladder

| Level | What runs | What it does not prove |
|---|---|---|
| 0 · Spec | JSON Schema, semantic payloads, count limits, title/evidence heuristics | Source truth, causality, good storytelling |
| 1 · Geometry / spatial | Bounding boxes, peer intersections, hash-bound scene readback, semantic occlusion, safe area, text/rule gap, conservative text-fit and title-wrap checks | Exact PowerPoint text shaping, all intended overlaps, arbitrary imported-scene intent |
| 2 · PPTX inspection | ZIP/XML readback of text, tables, charts, images, groups and shape locators | That extracted values are authentic or complete for arbitrary decks |
| 3 · Native render | Isolated LibreOffice conversion, fresh PDF/PNGs, page-count match | Identical Microsoft PowerPoint rendering, visual approval |
| 4 · Vision review | Reviewer record bound to the exact PPTX hash and all reviewed slide numbers | Automated or infallible aesthetic judgment |
| 5 · Repair / rerender | Agent or human changes the spec/source and rerenders | Autonomous deterministic visual repair |

A tool can be present and still fail at execution. `npm run doctor -- --json` reports presence/version and recovery, never visual approval. `npm run capabilities` reports `NATIVE_RENDER=AVAILABLE` when dependencies are found, but detection is not a successful render.

## V1.2 check matrix

| Check | What it checks | What it does not prove |
|---|---|---|
| Reasoning plan | Schema, claims, dispositions, source/claim closure, critical-value coverage, dedup preservation, theme selection | Source authenticity, paraphrase fairness, causal validity |
| Arithmetic | `sum`, `difference`, `ratio`, `percent_change`; units, metrics, windows, denominators, zero guards and declared-result tolerance | Arbitrary formulas, weighted/unit-converted math, significance or causality |
| Source ledger | JSON hash and JSON-Pointer numeric comparison for structured JSON | PDF/image/text/native-PPTX ledgers; those are `REVIEWER_REQUIRED` |
| Numeric bindings | JSON Pointer resolution, completeness, deterministic formatting and post-build chart/table/KPI/note readback | Whether the chosen number is the right evidence |
| Final hash | Exact PPTX SHA256, chart caches, tables, KPI text, notes, embedded report and plan/spec hashes | Source truth or visual quality; a false trusted expectation can only produce false consistency |
| Geometry | Shapes, pictures and graphic-frame bounding boxes; major peer intersections | Text fitting, rotated/grouped geometry, all overlap intent |
| Spatial | Hash-bound scene and serialized native geometry/order, semantic occlusion, safe area, text/rule gap, source relations, conservative fit/wrap checks | Exact PowerPoint shaping or complete absence of rendered collisions |
| Fonts | Explicit slide/chart/theme families compared with Fontconfig | Glyph coverage, embedding, recipient font availability |
| Render | Isolated LibreOffice conversion, fresh PDF/PNGs, matching page count | Identical Microsoft PowerPoint rendering |
| Montage | Ordered thumbnail artifact | Visual approval |
| Visual review | Reviewer record bound to PPTX hash and all slide numbers | Automated or infallible aesthetic judgment |

Missing optional tools report `UNAVAILABLE`; checks not attempted report `NOT_RUN`; notes yield `PASS_WITH_NOTES`. Any `FAIL` makes the quality gate exit nonzero. A successful process exit with notes is not a complete visual pass.

## Run the checks

```bash
node skill/scripts/validate_plan.js plan.json --json
node skill/scripts/compile_plan.js plan.json --out out/deck.pptx --spec-out out/deck.spec.json
python3 skill/scripts/quality_gate.py out/deck.pptx --spec out/deck.spec.json \
  --out out/qa.json --render-dir out/render
```

For legacy deck JSON, validate/build as before:

```bash
python3 skill/scripts/validate_spec.py deck.json out/spec-qa.json
node skill/scripts/build_deck.js deck.json out/deck.pptx
python3 skill/scripts/quality_gate.py out/deck.pptx --spec deck.json \
  --out out/quality-report.json --render-dir out/render
```

Inspect the montage for page rhythm and individual pages for titles, small labels, evidence, text fit, Chinese glyphs and relationships. Fix the source spec or shared renderer and rebuild. Render success is not visual approval.

## Record a visual review

Record a JSON review only after inspecting the actual current output:

```json
{
  "pptx_sha256": "replace-with-the-actual-64-character-file-hash",
  "reviewer": "reviewer identity",
  "status": "PASS",
  "slides_reviewed": [1, 2, 3],
  "notes": "Observed title hierarchy, correct chart units, readable table and Chinese text; no clipping observed."
}
```

```bash
python3 skill/scripts/quality_gate.py out/deck.pptx --spec deck.json \
  --out out/qa-reviewed.json --render-dir out/render --visual-review review.json
```

Do not reuse a review after rebuilding. A digest or slide-coverage mismatch fails. The record remains a reviewer attestation; anyone can write JSON, so it is not a cryptographic proof of actual inspection. A prior review cannot approve a rebuilt file with a different hash.

## Font and render limitations

Render jobs use separate LibreOffice profiles and timeouts. Stale slide PNGs are replaced only after a new conversion succeeds. Pillow is also used for native image preparation and font measurement in V1.2, and is required by the complete test suite. Basic geometry/font inventory checks still use the standard library.

Without font measurement, text-fit estimates are unavailable and title measurement falls back conservatively. Even with measurement, fonts are not embedded: the estimate uses locally resolved families and cannot prove glyph coverage or recipient rendering. Structural QA cannot prove the absence of rendered text collisions. Check actual LibreOffice/PowerPoint output at full size; native Microsoft PowerPoint is `NOT_RUN` in this release.

## Regression coverage

Regression tests include graphic-frame overflow, unavailable font/render tools, source-overwrite prevention, stale visual attestation, unsupported chart semantics, mismatched/non-numeric data, missing coordinates and over-capacity input.

V1.1 added permanent A–H cases: section identity/prefix duplication; contained screenshot/table occlusion; local image contrast and protected cropping; embedded versus editable text provenance; six KPIs with no loss; repeated regional series; long-title resolution; dynamic subtitle/divider flow. Unicode/space/parentheses/&/★ filenames, native asset routes, ingestion mappings and local profiles are also tested.

V1.2 adds reasoning-plan schema/arithmetic/binding/coverage regressions, source-hash and JSON-Pointer checks, protected theme precedence, deterministic packaging, package safety and explicit native verification against expected hashes. These checks are still bounded by the contracts above. A benchmark's render PASS does not imply vision PASS; only inspected current outputs receive a reviewer record.

## Showcase review boundary

The eight V1.2 showcase cases were built from the current engine and actual LibreOffice renders. Some pages were inspected by Codex before the final copy fixes; the two known copy defects (Q4 orphan body word and the long multimodal subtitle) were corrected and affected cases rerendered. Final independent actual VQA was then completed for all 8 cases / 58 pages on Linux LibreOffice with synthetic fixtures, bound to exact PPTX and page hashes, and recorded as `PASS_WITH_KNOWN_LIMITATIONS`. This is not publication approval; the 15 legacy benchmark scenarios remain visual `NOT_RUN`, and all 15 profiles were not fully visually tested. See [Benchmarks A–J](BENCHMARKS_V1_2.md) and the [showcase](SHOWCASE_V1_2.md).
