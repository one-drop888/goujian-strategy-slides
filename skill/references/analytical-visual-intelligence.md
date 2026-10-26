# Analytical and visual intelligence (V1.3)

The agent owns business interpretation, narrative and design choices. Deterministic code owns arithmetic, typed constraints, formatting, native output and readback. A registry entry or JSON declaration is not proof of semantic reasoning or visual quality.

## From the question to a visual encoding

1. State the decision question, population, period and comparison. Separate measured facts, calculations, interpretations, hypotheses and recommendations. Do not infer causality from correlation, especially optional test-drive behavior and sales outcomes.
2. Reconcile source identities, denominators, dates, grouping, deduplication and cohort maturity. Preserve missing data and material uncertainty. Use the existing Reasoning Plan for source-byte checks, calculation operands and content dispositions.
3. Declare metrics when scale or reuse matters. Select a chart for a relationship: magnitude → bar/column; time → line; composition → carefully labeled bar, pie or doughnut; exact lookup → table; explicit equal-width frequency bins → histogram. Use the simpler faithful choice. Scatter, bubble, waterfall, dual-axis/combo and arbitrary statistical inference are not implemented; do not relabel a column chart as these types.
4. Write a Visual Encoding Plan using `visual_encoding` on a chart. Give stable `series[].id` values across pages; name an emphasis explicitly. Category colors are separate from brand accent. Actual, target and history roles have stable color/dash/marker treatments. Color differences, background contrast and non-color cues are separate checks.
5. Build a declared narrative graph for a complex multi-source report. Preserve material source evidence; an executive summary followed by expanded detail is valid. Duplicate candidates are review prompts, never automatic deletion.
6. Build, run the Quality Gate with the original spec, render, inspect montage and full-size pages, repair and repeat. Numeric mistakes block delivery. Reviewers must check the business claim and visual legibility, not only structural flags.

## Numeric Semantic Contract

The optional root `metrics` array uses `core/schema/metric.schema.json`. Example:

```json
{
  "metrics": [
    {"id":"conversion", "name":"成交率", "raw_value":0.092,
     "type":"percent", "storage_scale":"fraction", "display_unit":"%",
     "precision":1, "time_window":"2026-09 mature 30-day acquisition cohort",
     "denominator":1000, "aggregation":"none", "comparison_basis":"part_of_whole",
     "provenance":{"source_id":"synthetic-sales", "pointer":"/conversion"}},
    {"id":"revenue", "raw_value":12500000, "type":"currency",
     "storage_scale":"unit", "currency":"CNY", "precision":1,
     "display_scale":{"factor":10000,"unit":"万"}, "time_window":"2026 Q3"}
  ]
}
```

`fraction` percent .092 displays 9.2%; `percent` 9.2 also displays 9.2%. `pp` is a difference in percentage points, not a relative change: 8%→10% = +2.0pp and +25% relative growth. Declare the comparison basis; do not use suffix guessing. Currency requires an ISO code. `display_scale` is an explicit divisor and suffix; 万=10000 and 亿=100000000. Never infer business favorability from a sign.

Supported types: absolute, count, currency, ratio, percent, pp, yoy, mom, growth, achievement, mean, median, rank, index, duration and difference. These label a supplied fact; they do not calculate means, medians or infer its denominator. The Reasoning Plan validates supported calculations against declared operands. Unknown, contradictory or nonfinite values fail. Counts/ranks require safe integers. Tiny values that would round to zero require more precision or explicit scientific notation. Null requires `missing_policy` (gap/null); zero remains zero.

`formatMetric` uses fixed declared precision and standard decimal rounding. `formatDelta` requires explicit fraction/percent input storage when it differs from the default percent scale. A positive relative baseline is required. Never repurpose a rounded display string as a raw source value.

## Bind the same fact across components

Use `{{metric:conversion}}` in allowed slide title/text/KPI/table fields. Use `series[].metric_ids` to derive a native series from metric IDs without duplicating values:

```json
{"type":"chart", "chartType":"column", "title":"成交率为 {{metric:conversion}}",
 "labels":["本期"], "series":[{"id":"conversion","name":"成交率","metric_ids":["conversion"]}]}
```

If `values` are also supplied with metric IDs, they must match **canonical effective values** (9.2 for a percent metric, not raw .092). Prefer omitting duplicate values. Without metric references, explicit `series.storage_scale` converts its raw series once. Do not combine these conventions accidentally. `metric_bindings` validates an allowed JSON Pointer against the metric; it does not turn arbitrary text into verified evidence.

All points on a chart must share compatible unit/format/window semantics. Mixed units require separate charts, not a hidden second axis. Derived formats apply to native axes and labels. Native Excel scaling supports thousands/millions/billions; explicit non-Excel scales such as 万 normalize chart/workbook values, retain the original metric and record the factor and transformation. The display caption includes the base unit and scale. This is disclosed normalization, never an edit to the raw fact.

**Keep the original spec as the rebuildable input.** `buildDeck` returns `effective_spec` only for internal native verification. It has already substituted/scaled values and must not be used as a new source spec. The compiler exports the original portable spec; source and plan hashes remain enforced.

## Encoding and capacity

`visual_encoding` declares intent/relation, label strategy and series IDs/roles/emphasis. Supported series roles include actual, target and history; categorical series use a distinct auxiliary palette. Explicit user colors remain authoritative and are checked, not silently changed. Native lines carry markers and dash patterns. Dense lines can use end labels, preserving all underlying workbook/cache values. Use a table, facets or another page when all numbers cannot be labeled legibly.

Native chart families: bar, column, line, area, pie, doughnut. Stacking is supported for bar/column with every series explicitly stacked. Pie/doughnut require one nonnegative series with a positive total and no missing values. Histogram requires explicit contiguous equal-width numeric bins and counts. Bounded modern series/category palettes reject unsupported density with split guidance; legacy category charts preserve values and disclose fallback styling. A numerical color heuristic is not a color-vision or WCAG certification.

## Review responsibilities

- Numeric: raw/effective/display scale, %, pp, units, time windows, denominators, chart/workbook/table reconciliation and missing vs zero.
- Perceptual: series identification, legend association, label collisions, readable title/body, grayscale cues and real projection context.
- Narrative: question→claim→evidence→decision, coverage and duplication; preserve a useful summary/detail pair.
- Provenance: authentic source, authority to publish, license and uncertainty. A pointer/hash proves presence or identity, not source truth.
- Platform: one root SKILL entry and package preflight support distribution checks. Company platform and Agensi approval require actual separate uploads; local/CI PASS cannot substitute.
