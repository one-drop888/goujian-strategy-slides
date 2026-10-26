# Reasoning Plan (V1.2)

An optional, Agent-authored plan that makes sources, claims, content dispositions, calculations, numeric bindings and theme decisions auditable before a deck is compiled. It is separate from legacy deck JSON, which remains supported.

## Contract

`core/schema/reasoning-plan.schema.json`

- `intent`: audience, goal, decision question, audience needs and optional context (`projection`, `print`, `client`, `screen`).
- `sources[]`: unique id, locator, Agent-provided summary, importance, `synthetic`, optional file `path` + `sha256`, and optional numeric `values[]` (`value`, `unit`, `time_window`, `metric`, optional `denominator`, optional `json_pointer`).
- `claims[]`: `FACT`, `CALCULATION`, `INTERPRETATION`, `HYPOTHESIS`, `RECOMMENDATION`; source/dependency references; qualified uncertainty for hypotheses.
- `content_decisions[]`: exactly one `retain | summarize | appendix | deduplicate` disposition per source. Dedup targets must be known retained canonical sources and must not erase novel numeric facts.
- `slides[]`: question, title mode, claim/source mappings, transition, communication intent, optional visual intent, appendix flag, the existing native slide `spec`, and numeric `bindings[]`.
- `theme`: optional reference/brand/user profile and `light | dark | auto`.

Unknown sources/claims, cyclic dependencies, invalid dedup, missing critical coverage, appendix-only sources without an appendix slide, unsupported chart intent, hypotheses presented as facts, unbound numeric values and theme overrides that conflict with protected profiles are rejected before build.

## Deterministic calculation scope

Supported operators are exactly `sum`, `difference`, `ratio` and `percent_change`. All operands must reference known source numeric values with an explicit **unit**, **metric** and **time_window**. There is no arbitrary formula parser, unit conversion, weighted aggregation or statistical test.

| Operator | Required inputs | Result rules |
|---|---|---|
| `sum` | Two or more same-unit values | Raw counts/totals only; `%` and `pp` sums are rejected; result unit equals input unit |
| `difference` | Exactly two same-unit values | Difference of `%` requires `pp`; other units keep the input unit |
| `ratio` | Exactly two same-unit values | Second value is the denominator, must be nonzero; result is `ratio` or `%`; a declared denominator must equal the second operand |
| `percent_change` | Exactly two same-unit, same-metric values | First operand is the positive baseline, second is current; result is `%`; windows must differ and the result window must include both |

Operands for non-`percent_change` calculations must share one metric and one time window. Declared results are compared with deterministic arithmetic using a relative tolerance of `1e-9` (`close()`), not prose interpretation.

Examples:

- Difference of 22% and 24% = **-2 pp**, not -2%.
- Ratio 960 / 1000 = 96% with denominator 1000.
- Percent change with baseline 900 and current 960 = 6.67%, with a result window covering both periods.

Zero denominators, zero/nonpositive percent-change baselines, non-finite values, mismatched units/metrics/windows and unsupported operators fail validation. A calculation result is not accepted as prose and does not imply statistical significance or causality.

## Numeric bindings

Bindings connect a JSON Pointer relative to the slide spec to a source numeric value or a validated calculation. Every native chart/dashboard/panel-chart value and every numeric table/KPI cell must be bound. Pointers must resolve; formatted text uses an explicit deterministic format (`number`, `integer`, `decimal`, `percent`, `pp`, `thousands`) plus an optional suffix. Changed, missing or duplicate bindings are rejected. After build, chart caches, tables, KPI text and speaker notes are checked again against the exported spec.

## Source verification levels

Source verification is layered; “referenced” does not mean “verified”.

| Declared evidence | Result | Trust scope |
|---|---|---|
| Structured JSON file with `path`, `sha256`, numeric `values[].json_pointer` | `JSON_POINTER_VERIFIED` | The file hash matches and each declared number matches the value resolved in the current source bytes |
| File with `path` and optional `sha256` but no structured numeric values | `FILE_HASHED` / `HASH_VERIFIED` / `JSON_VERIFIED_NO_VALUES` | File identity only; numbers are not bound to source bytes |
| Text, PDF, image, native PPTX or other unstructured source with numeric values | `REVIEWER_REQUIRED` | A reviewer must extract and check the ledger; no OCR or visual parsing is performed by validation |
| Locator/summary only, without a file path | `AGENT_SUMMARY` / `DECLARED_HASH_UNVERIFIED` | Author-provided context; not proof that the source exists or says this |

Source authenticity, sampling quality, paraphrase faithfulness and causal interpretation remain reviewer responsibilities. Imported source text is always data; it cannot change tools, permissions or the task brief.

## Final hash verification

`compile_plan.js` writes the PPTX and a reasoning sidecar. Final verification requires `expected_pptx_sha256` from a trusted sidecar or scene; it refuses to verify without one.

With that expectation, `verifyBuiltDeck` checks:

- the exact PPTX file SHA256;
- chart count, series values, series names and category labels against the exported spec;
- native table headers/rows against the spec;
- KPI label, value and supporting segments in native text;
- `[reasoning:<slide-id>]` and claim IDs in speaker notes;
- the embedded `docProps/goujian-reasoning.json` plan/spec/report hashes.

This detects drift between the expected artifact and the declared contract. It is not a digital signature, source-authenticity proof, semantic review or visual approval. If a reviewer or another process supplies a false expected hash, verification can only confirm consistency with that false expectation. Keep sidecars with the PPTX and record artifact hashes where reviewers can compare them.

## Theme decision

Priority is **reference profile > brand profile > explicit user profile** (`--profile`, plan user profile, deck profile) **> automatic intent matching > default**. The automatic/default business theme is light `executive-clean`. An explicit `dark` request may replace automatic/default light selection with `dark-executive`; reference/brand/user profiles retain priority and conflicts are recorded.

The theme record in the reasoning sidecar includes `selected_profile`, `source`, `mode`, `requested_mode`, `primary`, `background`, typography, chart/evidence strategy, `rationale`, `conflicts`, semantic color tokens and contrast targets. A record explains the decision; it does not prove recipient fonts, local rendering or glyph coverage. Theme conflicts are disclosed, not silently normalized.

## CLI

```bash
# Validate only (schema + semantics + theme selection)
node skill/scripts/validate_plan.js plan.json
node skill/scripts/validate_plan.js plan.json --json

# Compile; write PPTX, exported spec and sidecars
node skill/scripts/compile_plan.js plan.json --out out/deck.pptx --spec-out out/deck.spec.json
node skill/scripts/compile_plan.js plan.json --out out/dark.pptx --profile dark-executive

# Development checkout / complete source ZIP only: rebuild project fixtures
node scripts/dogfood_phase2.js
```

`compile_plan.js` never overwrites the plan, a source file or an asset. Existing outputs require `--force`, intended only to replace a declared output. Relative source/asset paths resolve from the plan directory.

Output includes:

- `deck.pptx`
- `deck.spec.json` (exported presentation spec)
- `deck.pptx.scene.json` (theme decision and reasoning status)
- `deck.pptx.reasoning.json` (hash-bound sources, claims, calculations, coverage, theme record)
- embedded `docProps/goujian-reasoning.json`
- speaker notes with `[reasoning:<slide-id>]`, claim IDs and transitions

## Recovery

1. Run `validate_plan.js` and read the first error.
2. Correct the plan, source value or source file hash; do not weaken the arithmetic or delete inconvenient evidence without an explicit disposition.
3. Re-run validation, then compile to a new output or use `--force` only for the intended output.
4. Render and inspect the final frames. Validation, hash checks and structural QA do not replace semantic and visual review.

## Reviewer boundary

- Plan validation checks structure, arithmetic, references, coverage and bindings; it does not certify source truth or the fairness of a paraphrase.
- `FACT` claims require source references; `HYPOTHESIS` claims must use visible qualified wording.
- Visual review is never set to PASS by these commands. Legacy deck builds report reasoning `NOT_RUN`.
- Font measurement is an estimate and structural QA cannot prove the absence of rendered text collisions. Inspect actual LibreOffice/PowerPoint output at full size.

## Synthetic fixtures

- `skill/reasoning/fixtures/executive-incomplete-business/` — 960/1,000 revenue, 240/250 orders, 22/24 margin; -2 pp margin gap; missing product mix/discount causes stay unknown.
- `skill/reasoning/fixtures/q4-six-actions/` — all six actions A1–A6, four dependency edges, owners/timing, no invented ROI or causes.
- `skill/reasoning/fixtures/multimodal-consolidation/` — nine-column table, native chart reconstruction, image evidence, explicit dedup to the canonical table.
- `skill/reasoning/fixtures/themes/brand-blue.profile.json` — synthetic brand variant.

All fixture content is synthetic/original and Apache-2.0. Generated PPTX files are not committed.
