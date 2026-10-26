# Architecture · V1.3

Goujian is one product with one shared native PPTX engine. Platform adapters do not fork the analytical or rendering core.

```text
Agent + sources + user intent
  → Data semantics (optional typed metric catalogue)
  → Analytical Reasoning Plan + declared narrative graph
  → Visual encoding + composition/profile selection
  → Adaptive title/layout + PPTX renderer
  → Native readback + geometry/fonts/spatial + render + reviewer
```

## Responsibilities and actual implementation

| Layer | Implementation | Boundary |
|---|---|---|
| Data semantic contract | `core/semantics/numeric.js`, `deck.js`, metric/deck schemas | Validates supplied meaning, not source authenticity; original spec immutable |
| Analytical reasoning | Existing `core/reasoning/` source hashes, bounded arithmetic, claim/content ledger; three `core/analytics/` recipes | Business interpretation is agent-authored; no general model or arbitrary formula engine |
| Narrative graph | `core/semantics/narrative.js`, optional deck field | Declared links/coverage/fingerprints and redundancy candidates; no automatic semantic deletion |
| Visual grammar | `core/renderer/encoding.js`, style tokens | Stable series identities, roles, categorical/value encoding and bounded perceptual heuristics |
| Adaptive presentation | Existing composition resolver, profiles, measured title candidates, native slide primitives | Wide16:9, bounded capacities; no generic global layout optimizer |
| Relationship layouts | Date/ordinal timeline; native DAG branch/swimlane/roadmap | True date distances; bounded graph capacities; cycles not implemented as DAG |
| QA | Shared `native_readback.js`, `semantic.js`, existing Python gate/renderers | Serialized PPTX and XLSX checked; visual/source-truth judgments remain separate |
| Distribution | One root Skill, deterministic runtime package, complete-ZIP preflight, existing CI/release workflow | Public checks cannot certify company/marketplace import |

## Original facts and transformed output

A build validates the original deck, derives an effective copy and records substitutions/storage conversions/display normalization. Raw fractions .092 become canonical percent-point values9.2. Excel-native thousands/millions formats retain base chart values; explicit 万/亿 scales normalize chart/workbook values and record the factor, while the original metric remains unchanged. Placeholders bind formatted text to the same catalogue.

The original spec is the portable rebuild input. `effective_spec` is internal and must not be passed back as raw input. Reasoning Plan source/spec hashes remain enforced; final native verification requires the trusted final PPTX hash and authenticates the embedded report. Generic QA re-derives expected values from the original spec and reads the actual output without trusting a sidecar PASS flag.

## Reuse rather than independent slide templates

Storylines express management logic. Semantic archetypes resolve into a limited set of compositions and native primitives. Profiles supply typography, spacing, chart/table language and colors. A catalogue count is not a count of independently implemented renderers. Unsupported semantic types stay explicitly unsupported instead of silently becoming a misleading chart.

The legacy keyword planner remains a helper. Agent-authored reasoning, not fixed keyword rules, makes business and chart-selection decisions. Deterministic code rejects contradictions and unsupported capacity.

## Extension boundary

Numeric semantics, declared narrative and most source/claim contracts have no PptxGenJS imports. These can be reused by a future renderer. Composition realization, native chart format/style patches, scenes and QA are still PPTX-specific. HTML/multi-renderer readiness is PARTIAL at the contract level; there is no HTML renderer or complete renderer-independent layout IR in V1.3. A future implementation needs its own layout adapter and output/readback/visual acceptance, not a rewrite of business reasoning.

The native chart XML postprocessor targets pinned PptxGenJS4.0.0 behavior. Upgrades must repeat the native/workbook/format/legend and actual-render tests. Large QA/benchmark modules are a maintenance boundary: extend focused helpers when new families justify it, not a second rendering engine.

## Community and Pro

Apache-2.0 Community contains semantic correctness, native generation, readability and QA. Any future Pro extension consumes the same public contracts/engine from separately versioned, licensed and delivered code. No proprietary Pro module is included in this public repository. Paid delivery, marketplace runtime and commercial differentiation are separate unverified gates.
