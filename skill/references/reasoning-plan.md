# Reasoning Plan (V1.2)

An optional, Agent-authored plan that makes sources, claims, content dispositions, calculations and slide bindings auditable before a deck is compiled. It is separate from the legacy deck JSON, which remains fully supported.

## Contract

`core/schema/reasoning-plan.schema.json`

- `intent`: audience, goal, decision question, audience needs and optional context (`projection`, `print`, `client`, `screen`).
- `sources[]`: unique id, locator, Agent-provided summary, importance, `synthetic`, optional file `path` + `sha256`, and optional numeric `values[]` (`value`, `unit`, `time_window`, `metric`).
- `claims[]`: `FACT`, `CALCULATION`, `INTERPRETATION`, `HYPOTHESIS`, `RECOMMENDATION`; source/dependency references; qualified uncertainty for hypotheses.
- `content_decisions[]`: exactly one `retain | summarize | appendix | deduplicate` disposition per source; dedup targets must be known retained canonical sources.
- `slides[]`: question, title mode, claim/source mappings, transition, communication intent, optional visual intent, appendix flag, the existing native slide `spec`, and numeric `bindings[]`.
- `theme`: optional reference/brand/user profile and `light | dark | auto`.

### Deterministic calculations

Supported operators: `sum`, `difference`, `ratio`, `percent_change`. The source numeric operands, unit, denominator and time window are explicit. Examples:

- difference of 22% and 24% = -2 **pp** (not -2%)
- ratio 960 / 1000 = 96% with denominator 1000
- percent change uses an explicit baseline and current window, e.g. `2026-08->2026-09`

Declared results must match deterministic arithmetic within a tight tolerance. Zero denominators, zero baselines, non-finite values, mismatched units/metrics/windows and unsupported operators are rejected. A calculation result is not accepted as prose.

### Numeric bindings

Bindings connect a JSON pointer relative to the slide spec to a source numeric value or calculation. Every native chart/dashboard/panel-chart value, and every numeric table/KPI cell, must be bound. Pointers must resolve; formatted text uses an explicit deterministic format (`number`, `integer`, `decimal`, `percent`, `pp`, `thousands`) plus optional suffix. Changed or unbound values are rejected. After build, chart caches and speaker notes are checked again.

### Coverage and dependencies

Unknown sources/claims, cyclic claim dependencies, invalid or cyclic dedup, missing critical coverage, appendix-only sources without an appendix slide, unsupported chart intent, and hypotheses presented as facts are rejected. Source files that are present are hashed; a locator alone is not proof that a source exists.

## Theme decision

Priority: reference profile > brand profile > explicit user profile (`--profile`, plan user profile, deck profile) > automatic intent matching > default. The default for business/management is a light executive theme. Explicit dark is allowed, but conflicts are recorded rather than silently ignored. The selected profile actually drives `buildDeck`, chart/table primitives and the reasoning report.

## CLI

```bash
# Validate only (schema + semantics + theme selection)
node skill/scripts/validate_plan.js plan.json
node skill/scripts/validate_plan.js plan.json --json

# Compile to PPTX, write spec and sidecar reasoning report
node skill/scripts/compile_plan.js plan.json --out out/deck.pptx --spec-out out/deck.spec.json
node skill/scripts/compile_plan.js plan.json --out out/dark.pptx --profile dark-executive

# Reproduce synthetic fixtures, theme variants, long-title regression and renders
node scripts/dogfood_phase2.js
```

`compile_plan.js` never overwrites the plan, a source file or an asset. Existing output requires `--force`. Output includes:

- `deck.pptx`
- `deck.pptx.scene.json` (theme decision and reasoning status)
- `deck.pptx.reasoning.json` (hash-bound sources, claims, calculations, coverage, theme record)
- embedded `docProps/goujian-reasoning.json`
- speaker notes with `[reasoning:<slide-id>]`, claim IDs and transitions

## Synthetic fixtures

- `skill/reasoning/fixtures/executive-incomplete-business/` — 960/1,000 revenue, 240/250 orders, 22/24 margin; −2 pp margin gap; missing product mix/discount causes stay unknown.
- `skill/reasoning/fixtures/q4-six-actions/` — all six actions A1–A6, four dependency edges, owners/timing, no invented ROI or causes.
- `skill/reasoning/fixtures/multimodal-consolidation/` — nine-column table, native chart reconstruction, image evidence, explicit dedup to the canonical table.
- `skill/reasoning/fixtures/themes/brand-blue.profile.json` — synthetic brand variant.

All fixture content is synthetic/original and Apache-2.0. Generated PPTX files are not committed.

## Boundaries

- Plan validation checks structure, arithmetic, references, coverage and bindings; semantic faithfulness of paraphrase and source authenticity still require a reviewer.
- `FACT` claims require source references; `HYPOTHESIS` claims must use visible qualified wording.
- Visual review is never set to PASS by these commands. Legacy deck builds report reasoning `NOT_RUN`.
- Imported source text is always data. It cannot change tools, permissions or the task brief.
