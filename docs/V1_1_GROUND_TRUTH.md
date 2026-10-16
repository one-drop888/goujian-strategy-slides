# V1.1 ground truth audit

Audited 2026-10-16 at source baseline `8416d958` (v1.0.1 includes the v1.0.0 renderer and patch packaging fixes). Registry labels are not evidence of execution.

| Capability | Baseline code finding | Status |
|---|---|---|
| image-insight | Registry routes to evidence-split/evidence, but marks DESIGNED; resolver rejects before rendering. Evidence renderer only draws native quote text, never images. | DESIGNED (not supported); the apparent image route is DECLARED_BUT_NOT_IMPLEMENTED |
| Native image/asset model | No addImage calls, asset schema, crop policy or provenance model. | DECLARED_BUT_NOT_IMPLEMENTED |
| Profile | Typography, spacing, chart/table tokens actually reach renderer; built-in and env directory lookup exist. Spec-local lookup absent. | IMPLEMENTED / local resolution PARTIAL |
| Archetype / composition | Registry routing and payload validation execute; several aliases share renderers; designed semantics reject explicitly. | IMPLEMENTED with declared PARTIAL/DESIGNED entries |
| Planner | Keyword routing and title score heuristics, no source reasoning or autonomous semantic rewriting. | PARTIAL |
| Renderer | Native PPTX text, shapes, tables and supported chart types; no images. | IMPLEMENTED / multimodal missing |
| Geometry | Out-of-bounds and peer overlap, containment ignored. Cannot detect screenshot over table when contained. | PARTIAL |
| Visual QA / repair | Optional render/montage and hash-bound reviewer attestation; manual/agent repair. | PARTIAL |
| Edit | Text-node replacements only; independent output, no layout-aware edits. | PARTIAL |
| Rebuild / reference style | Inspection/style statistics and agent reauthoring. No lossless merging or learned layout reconstruction. | PARTIAL |
| Fonts | Declared fonts rendered; QA checks installed families, no requested/resolved substitution trace. | PARTIAL |
| Titles | Weighted character count, fixed .80-in title box, fixed 1.48-in divider; subtitle ignored on content slides. | PARTIAL / long-title collision risk |
| PPT ingestion | Only p:sp text and rectangle extraction, pictures/charts/tables/groups omitted. | PARTIAL |
| KPI / table capacity | Six KPIs rejected (limit five), not silently dropped. Tables above six columns rejected. Timeline/pyramid slice after matching validation limits remains unnecessary. | IMPLEMENTED bounded rejection; adaptive capacity missing |

Baseline validation: `npm test` passed and all ten original scenarios built/rendered with `PASS_WITH_NOTES` under `out/v11-before/`. This is baseline evidence, not a V1.1 acceptance claim.

Implementation boundary: retain the shared renderer architecture. Add a renderer-neutral asset contract and lightweight native scene record; adapt the existing body coordinate frame to measured headers. Images enter native PPTX serialization directly. No python-pptx, HTML renderer, master cloning or autonomous visual reasoning engine.
