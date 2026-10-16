# V1.1 architecture

Goujian is one product and one distributable Presentation Library.

| Layer | Implementation | Boundary |
|---|---|---|
| Schema | `core/schema/validate.js`: Ajv Draft 2020-12 + composition payload guards | Shape/capacity validation, not factual correctness or exact text fitting |
| Planner | Keyword storyline/archetype routing and measured title resolution | Partial semantic reasoning; rewriting remains agent/author-assisted |
| Storyline | 28 registry entries with questions, triggers and sequences | Agent chooses/adapts; sequence is guidance, not enforced page order |
| Archetype | 86 semantic entries with explicit status and limitations | 74 implemented, 6 partial, 6 rejected as designed-only |
| Composition | Portable JSON normalization, role-aware deduplication and registry mapping | 27 recipes → 22 rendering functions; four reusable multimodal grammars |
| Asset / provenance | Local raster contract, source region/confidence/render mode and protected evidence | Agent supplies classification; no OCR or universal visual understanding |
| Profile | Inheritance, spec-local lookup, schema/style/font resolution | Typography, spacing, table/chart/title/image tokens; no font embedding |
| Renderer | `core/renderer/`: PPTX orchestration, primitives, structural slides, data slides | Native PPTX objects; wide canvas; backend-specific geometry |
| QA | `core/qa/`, `quality_gate.py`, `render_deck.py` | Executable bounded checks plus explicit reviewer attestation |
| Scene | Hash-bound native object record with semantic relationships | Spatial QA reads actual serialized native geometry and order; no arbitrary imported intent inference |

```text
Agent reasoning / source interpretation
           ↓
Presentation Spec (JSON)
           ↓
Storyline + semantic archetype → composition resolver
                                      + profile resolver
                                             ↓
                                        PPTX backend
                                             ↓
                                Geometry / Fonts / Render
                                             ↓
                                     Visual review → repair
```

## Dependency direction

Only `core/renderer/index.js` imports PptxGenJS. Planning, schemas, semantic metadata and normalization use ordinary JSON/JavaScript. A future HTML renderer can reuse that content contract without importing PowerPoint code.

The composition registry currently describes routing and purpose. It is **not** a backend-neutral box/constraint graph. Coordinates, native chart options and table behavior remain in renderer modules. An HTML backend would implement equivalent compositions and its own font measurement; a shared geometry model should follow concrete second-backend needs, not precede them.

## Maintenance decisions

The original builder's chart/table code was separated into `slides/data.js`, and shared typography/rules/footers live in `primitives/base.js`. `slides/basic.js` remains the largest module and still includes some legacy diagram sizing. Further decomposition belongs with tests for new behavior, not a speculative plugin framework.

Unknown compositions, unsupported special charts, missing matrix coordinates, nonfinite/mismatched chart values and over-capacity content fail before writing. `renderer` is not an accepted override. Profile inheritance detects cycles and resolves relative parent files from the child file's directory.

Evidence metadata is preserved in speaker notes. It is an author-provided record, not verified source truth. Visual records bind to the exact PPTX SHA256 and reviewed slide numbers; they attest that inspection happened, not that a machine proved visual quality.

V1.1 records actual native draw calls at `scene-adapter.js`; the existing body coordinate frame adapts to measured header height. Raster preparation occurs before native serialization in an isolated temporary directory; source files are never overwritten. Asset schema, provenance and relationship JSON do not import PptxGenJS. See [multimodal contract](../MULTIMODAL_CONTRACT.md) for exact supported semantics and limits.
