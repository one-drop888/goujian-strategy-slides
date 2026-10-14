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
| KPI | 1–5 `items`: `label`, `value`, `delta`/`note`, optional `highlight` |
| Scorecard | 1–7 `items`: `label`, `value`/`actual`, `target`, `variance`/`delta`, `status`; research-method uses `label`, `value`, `note` |
| Comparison | 1–4 `columns`: `heading`, `points` (max 6), optional `value`, `highlight`; `compare-2` requires exactly two |
| Process / timeline | 1–6 process or 1–7 timeline `items`: `title`, `note`, `time`/`period` |
| Funnel | 1–6 `items`: `title`, positive decreasing `value` counts or percentages of one shared base; commas accepted |
| Roadmap | 1–5 `lanes`: `title`, 1–5 `phases` with `title`; ordinal phase lanes, not a date-scaled Gantt |
| Matrix | Up to 14 `items`: `title`, author-supplied `x`,`y` in [0,1]; `xLabel`, `yLabel`, optional `quadrants`, `insight`; close labels may collide |
| Hierarchy | `root`, 1–5 `items`: `title`, up to 3 `children`; two levels only |
| Chart | 1–4 `series`: `name`, `labels`, numeric `values`; at most 24 categories with identical labels across series. `chartType`: bar, column, line, area, pie, doughnut. Optional `highlightIndex`, `numberFormat`, `axisMin`, `unit`, `period`, `insight`. Bar/area baselines include zero; line baselines may differ if explicit. |
| Table | `headers`, rectangular `rows`, max 6 columns × 8 rows; optional `columnWidths` fractions summing to 1, zero-based `highlightRows` |
| Action / risk | Up to 6 `items`; action: `title`, `note`, `owner`, `time`, `status`; risk: `title`, `likelihood`, `impact`, `mitigation`, `owner` |
| Evidence | `quote`/`evidenceText`/`body`, `attribution`, `insight`, optional `note` |
| Architecture | 1–5 `layers`: `title`, 1–5 `items` with `title`, optional `highlight`; component groups, not executable graph edges |
| Portfolio | Up to 4 `items`: `title`, `value`/`status`, `note`, `highlight` |
| Pyramid | Up to 5 `items`/`levels` with `title` |

Capacity is an upper bound, not a fit guarantee. Long text needs editing, a larger layout, or another slide. Tables remain editable native tables; dense cell text can exceed intended height and must be checked after rendering. Evidence objects are retained in speaker notes; they do not verify truth. Per-slide `source` appears visibly.

Native chart data includes editable workbook values. Colors emphasize the selected first category by default; use `highlightIndex` deliberately. Synthetic examples illustrate structure and must not be presented as real research.

The `renderer` override is not public. Unknown compositions, malformed series, unsupported advanced chart archetypes, missing coordinates and excess item counts fail before output is written. Custom profile paths and inheritance are supported. V1 accepts only `canvas: "wide"`; standard/4:3 is not implemented.
