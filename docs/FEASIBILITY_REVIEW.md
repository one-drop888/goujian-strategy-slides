# V1.0 feasibility review

[English](FEASIBILITY_REVIEW.md) | [简体中文](FEASIBILITY_REVIEW.zh-CN.md)

**Verdict: V1.0 RELEASE READY WITH KNOWN LIMITATIONS.**

Goujian Strategy Slides is feasible as a production-oriented, agent-assisted workflow for bounded editable management presentations. It is not yet an autonomous source-to-deck system or a lossless editor. Review date: 2026-10-14. The assessment covers the optimized source and executed local fixtures. Publication and remote verification are separate operations, evidenced by the release workflow and the final release report.

## Feasibility by area

`PROVEN` means executed within the stated scope; `PARTIAL` means useful implementation with material limits; `DESIGNED` means an architectural intention without working output; `BLOCKED` means execution could not proceed. These are evidence states, not maturity scores.

| Area | State | Evidence and boundary |
|---|---|---|
| Architecture feasibility | PROVEN | Executed schema → semantic resolution → profile → PPTX → QA pipeline; no PptxGenJS import in planning/composition layers |
| Product feasibility | PROVEN | 10 management scenarios, 60 pages, evidence/decision/action vocabulary; examples are synthetic and do not establish real customer adoption |
| Visual / aesthetic quality | PROVEN | Three bounded iterations; 3 before/after decks, all 10 final montages, 23-recipe gallery and 15-profile probes inspected by a vision agent; no independent human panel |
| Installation feasibility | PROVEN | Clean extracted package: install, tests, validate, build and QA; Linux environment only; optional rendering tools installed separately |
| Maintainability | PARTIAL | Shared primitives, separated data slides, lockfile and negative regression tests; structural renderer remains substantial and some geometry is explicitly sized |
| Extensibility | PROVEN | Registry resolution, profile inheritance and custom reference-derived profile build executed; new semantics still need explicit payload/render tests |
| Multi-renderer readiness | PARTIAL | Portable semantic JSON and composition routing; no shared geometry engine or HTML backend |
| Open-source readiness | PROVEN | Apache-2.0 license, dependency notices, packaged runtime, bilingual entrypoints, contribution guide and CI/release workflows; this is not an independent provenance/legal certification |
| Documentation accuracy | PROVEN | Public npm commands executed; capability claims matched to code and limitations; no planned renderer represented as current output |
| QA reliability | PARTIAL | Schema/capacity, geometry, font availability, render and hash-bound review checks execute; they cannot establish factual truth, exact text fit or universal visual quality |

## Independent layer audit

| Layer | Status | Finding |
|---|---|---|
| Schema | IMPLEMENTED | Ajv Draft 2020-12 plus composition payload/capacity guards execute before file creation |
| Planner | PARTIAL | Keyword routing and title helpers exist; agent performs source reasoning and storyline adaptation |
| Storyline | IMPLEMENTED | 28 distinct recommended sequences; related review variants are not independent reasoning engines |
| Archetype | PARTIAL | 78 entries: 65 implemented, 6 partial, 7 designed-only; unsupported specialized visuals fail rather than silently approximate |
| Composition | IMPLEMENTED | 23 routing recipes reuse 21 rendering functions; not a backend-neutral constraint solver |
| Profile | IMPLEMENTED | 15 presets drive typography, margins, tables, charts, metrics, title rules, covers and color; some diagrams retain fixed sizing |
| Renderer | IMPLEMENTED | Native text, shapes, tables and supported charts; only wide PPTX output |
| QA | PARTIAL | Executable checks plus explicit reviewer records; render and Fontconfig are optional dependencies |
| HTML / future renderer | DESIGNED | Semantic layers can be reused; backend geometry and font measurement must be implemented |

There is no blocked core feature within the declared bounded V1 scope. Native Windows/macOS/PowerPoint rendering was **not tested**; that is an evidence gap, not a pass.

## Verification and installation

See [validation record](V1_VALIDATION.md) and [machine-readable benchmark evidence](evidence/benchmark-summary.json). The package includes `core/`, `skill/`, adapters, scripts, tests, docs, schemas and lockfile; `skill/` alone is not installable. Core Python checks use the standard library. Rendering separately needs Pillow, LibreOffice, Poppler and installed fonts.

Ten scenarios were checked for storyline fit, action titles, page variety, composition, charts where present, profile behavior, PPTX generation, Chinese rendering, geometry and visual quality. Some decision/training decks appropriately have no quantitative chart. All 60 final pages rendered. Training retains an explicit partial case-study warning. Font QA passed on this host after replacing unavailable defaults with installed Noto families and declaring chart fonts.

Negative tests exercise misleading/unsupported charts, malformed values, over-capacity content, missing coordinates, graphic-frame overflow, unavailable tools, unsafe in-place edits and stale visual review hashes. The 23-recipe gallery checks native chart XML/workbooks and absence of flattened slide images. A bounded text edit was rendered, and extracted style tokens were used to build a new profile.

## Claims audit

| Claim | State | Actual scope |
|---|---|---|
| Create | PROVEN | Validated semantic spec → PPTX |
| Edit | PARTIAL | Individual text-node replacement; separate output, no intelligent reflow |
| Rebuild | PARTIAL | Agent reconstructs a spec after inspection; no lossless conversion |
| Template reuse | PARTIAL | Recipe/storyline/profile reuse, not arbitrary master/layout import |
| Style extraction | PARTIAL | Font/theme/geometry statistics and profile starting point |
| Native editable PPTX | PROVEN | Native text/shapes/tables/charts with chart workbook data in tested fixtures; UI editing in Microsoft PowerPoint not tested |
| Overflow / overlap | PARTIAL | Bounding boxes and peer candidates; grouped/rotated/text layout limits |
| Font QA | PARTIAL | Declared font-family availability; no glyph/embedding/recipient proof |
| Render / montage | PROVEN | Executed LibreOffice/Poppler/Pillow pipeline |
| Visual QA | PARTIAL | Vision-agent inspection and artifact-bound attestation |
| Repair loop | PARTIAL | Spec/code edits, rebuild and inspection performed by an agent; no automatic repair engine |

## Strengths and gaps against public references

[External benchmark](EXTERNAL_BENCHMARK.md) is a qualitative review of primary documentation, not a controlled competitor execution benchmark. Goujian's strongest combination is explicit management reasoning, a semantic-to-composition architecture, and an editable Chinese/English PPTX workflow with inspectable quality evidence.

The three largest remaining gaps are sophisticated text/layout measurement, robust import/edit fidelity for arbitrary existing decks, and mature web/multi-renderer output. This round addressed weak typography/charts, ineffective profile tokens, misleading semantic mappings, missing schema enforcement and installation/claim accuracy. It did not attempt a speculative rewrite.

## Release boundaries and roadmap

- V1.1: content-aware text fit, long/dense real-deck fixtures, advanced chart implementation with truthful semantics, and native Office comparison.
- V1.1: improve heuristic planning and profile-specific diagram sizing based on user evidence.
- V2: HTML backend, shared layout measurement and richer reconstruction; animations and deterministic automatic visual repair remain future work.

Users must still supply trustworthy evidence, review each rendered deck and split overlong content. A PASS in one environment is not a guarantee for every font, recipient, source document or business inference.
