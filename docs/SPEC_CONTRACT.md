# V1 presentation specification

The JSON Schema is executed by Ajv 2020 in both build and spec QA. Composition payload validation adds size, shape and semantic constraints. Unknown fields remain allowed for annotations and future compatibility; they are not automatically rendered.

```json
{
  "title": "Pilot decision",
  "lang": "en-US",
  "profile": "executive-clean",
  "slides": [{
    "type": "decision",
    "title": "Approve a measured pilot before expanding coverage",
    "statement": "Fund two teams for six weeks; review quality and cost before rollout.",
    "source": "Illustrative example"
  }]
}
```

| Composition payload | Fields and bounded capacity |
|---|---|
| Cover / section | `title`, optional `subtitle`, `kicker`, `footer`, `number` |
| Message | `statement` or `body`; optional `note` |
| Summary | 1–5 `items`: `title`, `note` or `implication` |
| KPI | 1–6 `items`: `label`, `value`, `delta`/`note`, optional `highlight` |
| Scorecard | 1–7 `items`: `label`, `value`/`actual`, `target`, `variance`/`delta`, `status`; research-method uses `label`, `value`, `note` |
| Comparison | 1–4 `columns`: `heading`, `points` (max 6), optional `value`, `highlight`; `compare-2` requires exactly two |
| Process / timeline | 1–6 process or 1–7 timeline `items`: `title`, `note`, `time`/`period` |
| Funnel | 1–6 `items`: `title`, positive decreasing `value` counts or percentages of one shared base; commas accepted |
| Roadmap | 1–5 `lanes`: `title`, 1–5 `phases` with `title`; ordinal phase lanes, not a date-scaled Gantt |
| Matrix | Up to 14 `items`: `title`, author-supplied `x`,`y` in [0,1]; `xLabel`, `yLabel`, optional `quadrants`, `insight`; close labels may collide |
| Hierarchy | `root`, 1–5 `items`: `title`, up to 3 `children`; two levels only |
| Chart | 1–4 `series`: `name`, `labels`, numeric `values`; at most 24 categories with identical labels across series. `chartType`: bar, column, line, area, pie, doughnut. Optional `highlightIndex`, `numberFormat`, `axisMin`, `unit`, `period`, `insight`. Bar/area baselines include zero; line baselines may differ if explicit. |
| Table | `headers`, rectangular `rows`, max 9 columns × 8 rows; optional `columnWidths` fractions summing to 1, zero-based `highlightRows` |
| Action / risk | Up to 6 `items`; action: `title`, `note`, `owner`, `time`, `status`; risk: `title`, `likelihood`, `impact`, `mitigation`, `owner` |
| Evidence | `quote`/`evidenceText`/`body`, `attribution`, `insight`, optional `note` |
| Architecture | 1–5 `layers`: `title`, 1–5 `items` with `title`, optional `highlight`; component groups, not executable graph edges |
| Portfolio | Up to 4 `items`: `title`, `value`/`status`, `note`, `highlight` |
| Pyramid | Up to 5 `items`/`levels` with `title` |

Capacity is an upper bound, not a fit guarantee. Long text needs editing, a larger layout, or another slide. Tables remain editable native tables; dense cell text can exceed intended height and must be checked after rendering. Evidence objects are retained in speaker notes; they do not verify truth. Per-slide `source` appears visibly.

Native chart data includes editable workbook values. Colors emphasize the selected first category by default; use `highlightIndex` deliberately. Synthetic examples illustrate structure and must not be presented as real research.

The `renderer` override is not public. Unknown compositions, malformed series, unsupported advanced chart archetypes, missing coordinates and excess item counts fail before output is written. Custom profile paths and inheritance are supported. V1 accepts only `canvas: "wide"`; standard/4:3 is not implemented.

## V1.1 assets and measured headers

See [Multimodal Contract](MULTIMODAL_CONTRACT.md) for deck assets, panels, provenance, relationships, title_short/subtitle, analytical_series, local profile search and spatial QA. Six KPIs use 3 × 2. Tables over six columns use compact type (minimum 12pt); split content when it is too dense. No renderer silently drops items or columns.


## V1.3 optional semantic contracts

Existing V1.2.1 specs remain accepted. Root `metrics` adds explicit raw/storage/display semantics and source metadata; root `narrative` adds a declared argument/evidence ledger. `series.metric_id`/`metric_ids` can supply values without duplicating them; schema validation prepares an immutable effective copy before layout checks. Explicit slide/dashboard/panel category labels take precedence over metric time-window fallback labels.

Use `{{metric:id}}` in supported title/KPI/table text and `metric_bindings` for allowed numeric pointers. Fraction percent .092 becomes canonical9.2%; a pp difference is a distinct type. Currency requires an ISO code and explicit scaling. Non-Excel display scales such as万 normalize chart/workbook values with a recorded factor; preserve the original source spec for rebuilding. The internal `effective_spec` is not a new raw input. JSON numbers use IEEE754, not an arbitrary-precision accounting representation; do not claim precision absent from the input.

Null chart values require `missing_policy: gap/null`, stay native blanks and are never changed into zero. Modern encoding uses bounded distinct palettes; explicit nominal categories beyond available distinguishable colors must be split/faceted. The legacy category capacity above does not promise24 unique colors. Histograms use explicit contiguous equal-width numeric bins and a uniform frequency paint. Incomplete observation windows must be disclosed.

`visual_encoding` records relation, palette type, series IDs/roles/emphasis and labels. Categorical series remain distinct from brand accent. Value-based sequential/diverging/semantic encoding is bounded to bar/column; the semantic palette requires explicit business direction. Stable series IDs/registry retain series identity; maintain category order across comparable pages. Explicit user styles are preserved and checked. Non-color cues and actual render review remain necessary.

No axis may hide a declared point. Bar/column/area axes include zero. Positive truncated line minima require an explicit visible `axis_note`; disclosure is not permission to clip data. Pie/doughnut require one nonnegative complete series; typed percentage parts must declare a complete part-of-whole total, not independent conversion rates. Changes/pp/attainment are not valid pie parts. A pie share is a fraction computed by Office and uses a different number format from a stored percent-point value.

Date timelines use item `date`/optional `end_date` in ISO form and preserve elapsed positions. Without dates, legacy spacing remains ordinal. Bounded roadmap tasks/dependencies retain branches, lanes, labels, owner/date/status; cyclic business flows are not accepted as an acyclic dependency graph. See [numeric/visual details](../skill/references/analytical-visual-intelligence.md), [narrative graph](../skill/references/narrative-graph.md) and [migration](MIGRATION_V1_3.md).
