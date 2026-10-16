# Quality and validation

V1.1 separates executed checks from visual judgment. Run `npm run capabilities` to detect levels 0–5; missing native rendering explicitly sets `VISUAL_QA=UNAVAILABLE`.

| Check | What it checks | What it does not prove |
|---|---|---|
| Spec | Executed JSON Schema, semantic payloads, count limits, title/evidence heuristics | Source truth, causality, good storytelling |
| Geometry | Shapes, pictures and graphic-frame bounding boxes; major peer intersections | Text fitting, rotated/grouped geometry, all overlap intent |
| Spatial | Hash-bound scene + serialized native geometry/order, semantic occlusion, safe area, text/rule gap, source relations, conservative text-fit and title-wrap checks | Arbitrary imported scene intent or exact PowerPoint text shaping |
| Fonts | Explicit slide/chart/theme families compared with Fontconfig | Glyph coverage, embedding, recipient font availability |
| Render | Isolated LibreOffice conversion, fresh PDF/PNGs, matching page count | Identical Microsoft PowerPoint rendering |
| Montage | Ordered thumbnail artifact | Visual approval |
| Visual review | Reviewer record bound to PPTX hash and all slide numbers | Automated or infallible aesthetic judgment |

Missing optional tools report `UNAVAILABLE`; checks not attempted report `NOT_RUN`; notes yield `PASS_WITH_NOTES`. Any `FAIL` makes the quality gate exit nonzero. A successful process exit with notes is not a complete visual pass.

```bash
python3 skill/scripts/quality_gate.py out/deck.pptx --spec deck.json --out out/qa.json --render-dir out/render
```

Inspect montage and relevant full-size pages. Record a JSON review only after inspection:

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
python3 skill/scripts/quality_gate.py out/deck.pptx --spec deck.json --out out/qa-reviewed.json --render-dir out/render --visual-review review.json
```

Do not reuse a review after rebuilding. A digest or slide-coverage mismatch fails. The record remains a reviewer attestation; anyone can write JSON, so it is not a cryptographic proof of actual visual inspection.

Render jobs use separate LibreOffice profiles and timeouts. Stale slide PNGs are replaced only after a new conversion succeeds. Pillow is also used for native image preparation and font measurement in V1.1, and is required by the complete test suite. Basic geometry/font inventory checks still use the standard library. Without font measurement, text-fit estimates are unavailable and title measurement falls back conservatively.

Regression tests include graphic-frame overflow, unavailable font/render tools, source-overwrite prevention, stale visual attestation, unsupported chart semantics, mismatched/non-numeric data, missing coordinates and over-capacity input.

V1.1 adds permanent A–H cases: section identity/prefix duplication; contained screenshot/table occlusion; local image contrast and protected cropping; embedded versus editable text provenance; six KPIs with no loss; repeated regional series; long-title resolution; dynamic subtitle/divider flow. Unicode/space/parentheses/&/★ filenames, native asset routes, ingestion mappings and local profiles are also tested. A benchmark's render PASS does not imply vision PASS; only inspected current outputs receive a reviewer record.
