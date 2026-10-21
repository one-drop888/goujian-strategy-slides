# V1.2 architecture

Goujian is one product and one distributable Presentation Library. V1.2 adds an auditable reasoning layer and release packaging without replacing the renderer core.

| Layer | Implementation | Boundary |
|---|---|---|
| Reasoning Plan | `core/schema/reasoning-plan.schema.json`, `core/reasoning/validate-plan.js` | Agent-authored sources, claims, dispositions, calculations, bindings and theme; not independent reasoning |
| Arithmetic | `core/reasoning/calculations.js` | `sum`, `difference`, `ratio`, `percent_change` with units/windows/denominators; no arbitrary formulas or statistics |
| Source ledger | Source path/hash and optional JSON-Pointer values in plan validation | JSON sources can be byte-checked; PDF/image/text/native-PPTX values are reviewer-required |
| Theme | `core/reasoning/theme-decision.js`, profile resolver | Reference > brand > explicit user > automatic > default; conflict record; no font embedding |
| Compile / verify | `core/reasoning/compile.js`, `verify.js`, `embed.js` | Exported spec, native PPTX, scene/reasoning sidecars, embedded report, exact-byte verification |
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
| Packaging | `scripts/package_runtime.py`, `tests/test_package.py` | Deterministic single-SKILL installer and separate showcase artifact; no build caches or PPTX in installer |
| Release | `.github/workflows/release.yml` | Manual approved-SHA dispatch; no push trigger; annotated immutable tag; not dispatched in this phase |

```text
Agent reasoning / source interpretation
           ↓
Reasoning Plan (JSON): sources · claims · dispositions · calculations · bindings · theme
           ↓
Deterministic validation: structure · arithmetic · closure · coverage · bindings · theme
           ↓
Exported Presentation Spec (JSON)
           ↓
Storyline + semantic archetype → composition resolver
                                      + profile resolver
                                             ↓
                                        PPTX backend
                                             ↓
                   Scene + reasoning sidecar + embedded report
                                             ↓
                                Geometry / Fonts / Render
                                             ↓
                                     Visual review → repair
```

## Reasoning and verification trust

`validate_plan.js` performs deterministic structural and semantic checks before build. When a structured JSON source declares `path`, `sha256` and numeric `values[].json_pointer`, validation hashes the source, resolves each pointer and compares the declared number with the source bytes. Other source formats or absent structured values receive `REVIEWER_REQUIRED`; an agent summary or locator is never promoted to machine-verified truth.

`compile_plan.js` writes the PPTX and sidecars. Final verification requires an `expected_pptx_sha256` supplied by a trusted sidecar or scene. It checks the exact PPTX bytes, chart caches against the exported spec, native tables, KPI text, speaker-note claim references, and the embedded plan/spec/report hashes. This detects a mismatch between the expected artifact and the declared contract. It does not establish that the plan's interpretation is fair, the source is authentic or the rendered page is visually acceptable.

Theme selection is deterministic and recorded in the reasoning sidecar: reference profile > brand profile > explicit user profile (`--profile`, plan user profile, deck profile) > automatic intent matching > default. An explicit dark request may override automatic/default light selection; conflicts such as dark versus printable remain visible. The chosen profile drives the build, but theme configuration diversity is not a claim that every profile has received equal visual review.

## Dependency direction

Only `core/renderer/index.js` imports PptxGenJS. Planning, schemas, semantic metadata, reasoning validation and normalization use ordinary JSON/JavaScript. A future HTML renderer can reuse the contract without importing PowerPoint code.

The composition registry describes routing and purpose. It is **not** a backend-neutral box/constraint graph. Coordinates, native chart options and table behavior remain in renderer modules. An HTML backend would implement equivalent compositions and its own font measurement; a shared geometry model should follow concrete second-backend needs.

## Maintenance decisions

The original builder's chart/table code was separated into `slides/data.js`; shared typography/rules/footers live in `primitives/base.js`. `slides/basic.js` remains the largest module and includes some legacy diagram sizing. Further decomposition belongs with tests for new behavior, not a speculative plugin framework.

Unknown compositions, unsupported special charts, missing matrix coordinates, nonfinite/mismatched chart values and over-capacity content fail before writing. `renderer` is not an accepted override. Profile inheritance detects cycles and resolves relative parent files from the child directory.

Evidence metadata is preserved in speaker notes. It is an author-provided record, not verified source truth. Visual records bind to the exact PPTX SHA256 and reviewed slide numbers; they attest that inspection happened, not that a machine proved visual quality.

V1.1 records actual native draw calls at `scene-adapter.js`; the body coordinate frame adapts to measured header height. Raster preparation occurs before native serialization in an isolated temporary directory; source files are never overwritten. Asset schema, provenance, relationship and reasoning JSON do not import PptxGenJS. See the [multimodal contract](../MULTIMODAL_CONTRACT.md) and [Reasoning Plan reference](../../skill/references/reasoning-plan.md).

## Packaging and release direction

The installer is built from an explicit include whitelist with stable ordering, fixed timestamps/permissions, one root `SKILL.md`, and rejection of symlinks, caches, private paths and duplicate entries. The optional showcase is packaged separately and is not required at runtime. The release workflow runs only by manual dispatch of an approved main-branch SHA, verifies remote state, rebuilds and tests, and stops on an existing tag/release. This phase does not execute that workflow.
