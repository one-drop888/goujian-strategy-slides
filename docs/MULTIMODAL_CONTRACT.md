# V1.1 assets, composition and visual validation

## Native asset pipeline

Assets are local PNG/JPEG/WEBP files, resolved against the spec file's directory, not the process working directory. Original files are never modified. Pillow prepares cropped/masked/transparent derivatives before PptxGenJS serializes native picture objects. No python-pptx postprocessing is used. GIF/SVG/EMF/WMF ingestion may identify an asset but V1.1 does not render those formats directly.

```json
{
  "title": "Customer evidence",
  "profile": "research",
  "assets": [{
    "id": "interview",
    "path": "assets/interview-evidence.png",
    "type": "document_screenshot",
    "role": "evidence",
    "source": "Synthetic source PPTX, slide 1",
    "fit": "contain",
    "caption": "Interview excerpt; synthetic sample",
    "provenance": [{
      "kind": "image_text",
      "source_asset": "interview",
      "source_region": {"x": 0, "y": 0, "w": 1, "h": 1},
      "confidence": 1,
      "render_mode": "embedded"
    }]
  }],
  "slides": [{
    "type": "image-insight",
    "title": "Follow-up gaps merit a controlled pilot",
    "asset_ids": ["interview"],
    "insight": "The interview suggests a hypothesis; it does not establish causality."
  }]
}
```

Required fields: `id`, `path`, `type`, `role`, `source`. Actual `mime`, `width`, `height`, `aspect_ratio` and source SHA256 are recorded from the file. IDs must be unique. Paths are explicit local files; remote URL fetching is not implemented. Images over 32 megapixels are rejected before decoding; resize a separate derivative explicitly.

Types: `photography`, `product_image`, `document_screenshot`, `ui_screenshot`, `chart_screenshot`, `table_screenshot`, `diagram`, `background`, `decorative_asset`. Classification is supplied by the agent/author, not inferred by a built-in visual model. Photography/product/background can cover/crop. Document/UI/chart/table/diagram assets default to contain. Cropping protected evidence requires `allow_crop: true` and a `safe_area` that remains inside the final crop.

Protected evidence keeps a rectangular mask and full opacity. Nonrectangular masks and fading are reserved for non-evidence visual assets. Referenced annotation regions must remain inside the visible crop.

`crop` and `safe_area` use normalized `{x,y,w,h}`; `focal_point` uses `{x,y}`. Explicit crops retain their aspect ratio using contain. `fit` supports contain/cover/crop, `opacity` is 0–1, `mask` is rect/ellipse/rounded. Source files, captions, attribution and provenance are retained. A hero crop that cannot fill its contrast-sampling frame is rejected instead of stretching the source.

## Editable content versus pixel text

Provenance `kind`: `native_text`, `image_text`, `ocr`, `generated_annotation`, `source_data`, `derived_insight`. `render_mode`: `editable`, `embedded`, `reference_only`. Image text/OCR requires `source_asset`, normalized `source_region`, `confidence` and render mode. OCR confidence must come from a real extraction/reviewer; this project does not perform OCR.

Embedded text belongs to image provenance, not a fake editable text panel. An agent may explicitly transcribe verified text into an editable object with OCR/generated-annotation provenance. Deleting the picture also deletes its embedded pixels; the scene report makes this distinction explicit. Generated interpretation remains a separate editable native object.

## Four reusable compositions

| Composition | Semantic routes | Payload |
|---|---|---|
| multimodal-split | image-insight, image-evidence, image-text-split | asset_ids + insight/body, or explicit panels |
| multimodal-gallery | image-grid, image-gallery, image-comparison | 1–4 asset_ids; comparison requires 2; optional takeaway |
| multimodal-hero | image-hero, image-background | exactly 1 background/photographic asset + title/subtitle |
| multimodal-annotated | document-evidence | 1 asset + 1–4 annotations with text/source_region |

Explicit `panels` (1–4) use unique `id`, `kind` (text/image/chart/table), optional `role` and `provenance`. Image panels require `asset_id`; text panels require `text`; tables require headers and rectangular rows (half-page capacity 6 × 6); charts require matching labels/series values (nonnegative, bar/column/line). Recoverable data is rebuilt through native panels; automatic screenshot data recovery is not claimed. Assets and native panels remain adjacent rather than occluding each other.

`annotations` bind to normalized source regions and emit both a native highlight and native explanation linked to the screenshot. Do not crop outside the annotation's evidence region. The builder fails if an annotation would point outside the visible crop.

## Scene relationships and spatial QA

Build emits `deck.pptx.scene.json`, bound to that exact PPTX SHA256. Each slide records native object ID, kind, semantic role, bbox, z-order, text/font/provenance and measured title flow. Source/claim/evidence/caption/annotation/background relationships are generated or supplied via `relationships`: `{from,to,type}`. Supported types: parent_of, belongs_to, supports, annotates, caption_of, background_of, source_of. Unknown targets and duplicate IDs fail spatial QA.

Spatial QA verifies native object IDs and reads serialized bounds/order back from PPTX, checks contained screenshot/table occlusion, unbound annotations, safe area, title/subtitle/rule gaps, title-wrap quality, estimated text fit, density and reading order. It reports asset coverage, duplicate overlapping content, unresolved sources, detached annotation and semantic occlusion. Asset coverage is not proof that every source conclusion was preserved. Arbitrary imported decks without a scene record return UNAVAILABLE for semantic spatial QA.

Section deduplication uses page identity, section role, title prefix and common native source context; it does not apply global string deletion. The `01 / 01 / 01 总体经营达成` case is a permanent test. Embedded/master numbers cannot always be removed independently; inspect and reconstruct those sources explicitly.

For a retained embedded marker, asset provenance may declare `semantic_role: "section_number"`, its text and top-left source region. Matching native prefixes merge only in the same visible/contained source context at confidence >=0.9; low-confidence or cropped-out markers remain untouched.

## Titles and capacity

Use `title` for the original conclusion. Supply `title_short` for a faithful author rewrite and `subtitle` for scope/background. Original wording is retained in the scene record. A limited Q4 context cleanup and colon split run before safe font adjustment; this is not general semantic rewriting. Font glyph advances are measured with Pillow/Fontconfig and a 4% safety margin. Without measurement, a conservative glyph-class approximation is disclosed.

Prefer one line, allow balanced two lines, reject more than two or excessive subtitles. Title size may fall only to 92% of its profile size. Subtitle/divider/body follow actual measured header height. Content headers leaving less than 3.6 inches for evidence must be shortened or split. Body text-fit estimates are warnings, not exact PowerPoint layout proofs.

Six KPIs use a 3 × 2 grid. Full-width tables accept up to 9 columns × 8 rows, minimum 12pt type; short data can be compact, long material must be split by the agent. Larger inputs fail explicitly; rendering never slices items or columns silently. Analytical-series repetition is allowed only when id, metrics and task match across all repeated pages.

## Fonts, profiles and contrast

Fonts resolve from preferred per script, requested latin/cjk, explicit fallback arrays and installed platform candidates. QA records requested, resolved and substituted. Fontconfig absence is UNAVAILABLE; native Windows/macOS fallback is not proven. Font availability does not prove full glyph coverage or recipient font installation.

Profile resolution: built-in → spec-local profiles/ or spec directory → PRESENTATION_PROFILE_DIRS → explicit path. Omitted profile uses executive-clean; an unknown explicit profile fails rather than silently changing the design. Image gap, caption size and border tokens now drive rendering alongside typography/table/chart/divider tokens. Fifteen variants belong to shared visual families; no new blue profile was added.

Text over images samples the local region under the intended text box after crop/opacity compositing. A 1st-percentile contrast estimate chooses black or white at >=4.5:1; mixed regions use an opaque local scrim. This is not a universal proof about every pixel or every recipient's rendering. Inspect the final page.

## Run and review

```bash
npm run capabilities
npm test
npm run benchmark -- --render
node skill/scripts/build_deck.js skill/examples/multimodal-integration.json out/multimodal.pptx
python3 skill/scripts/quality_gate.py out/multimodal.pptx --spec skill/examples/multimodal-integration.json --out out/multimodal-qa.json --render-dir out/multimodal-render
python3 skill/scripts/inspect_pptx.py input.pptx out/inspection.json out/extracted-assets
```

Capability ladder: 0 Spec, 1 Geometry/spatial, 2 PPTX inspection, 3 Native render, 4 Vision review, 5 Agent repair + rerender. LibreOffice/pdftoppm/Pillow/fonts are detected. No renderer means VISUAL_QA=UNAVAILABLE, never visual PASS. Inspect montage and every required page; repair the spec/renderer, rebuild and rerender. Bind the reviewer attestation to the current PPTX hash as documented in [QA](QUALITY_AND_VALIDATION.md). Vision remains an explicit human/agent judgment, not a callable autonomous image model inside the package.
