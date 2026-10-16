# Runnable analytical presentation library

V1.1 has three executable recipe families, each covering six analytical tasks. These are data transformations with tested calculations, not extra slide-template counts. [Machine-readable definitions](../skill/analytics/registry.json) specify input fields, formulas, chart choices, conclusion boundaries and semantic/composition mapping. The [strict input schema](../core/schema/analytics.schema.json) rejects missing required fields, unexpected fields and invalid types. Existing Presentation Specs remain compatible.

## Replace data and run

After the normal installation, copy an input example, replace its values and source, set `synthetic: false` for real supplied data, and keep it outside the public repository. No external service is called. Personal IDs are only local input; do not publish customer data.

```bash
npm run analyze:business
npm run analyze:sales
npm run analyze:project
node scripts/analyze.js my-input.json 'out/我的分析（Q4） & ★.pptx'
python3 skill/scripts/quality_gate.py out/analytics/business.pptx --spec out/analytics/business.pptx.spec.json --analytics-input skill/analytics/business-performance.json --out out/analytics/business-qa.json --render-dir out/analytics/business-render
```

Output: editable `.pptx`, generated `.spec.json`, recomputable `.data.json` and hash-bound `.scene.json`. Build success does not grant visual acceptance. All text, tables, chart series and chart workbooks are native/editable; supplied screenshots retain pixel text.

## Business Performance

Input: full calendar reporting month, explicitly named primary metric, metrics with their own units, ordered consecutive monthly trend, and primary-metric contributions. The last trend point must equal primary actual. Both current and previous contributions reconcile to their totals. Metrics with different units never share an axis.

- KPI Scorecard: actual, target and attainment = actual / target.
- Target vs Actual: grouped native bars for the same primary metric and unit, baseline zero.
- YoY / MoM Trend: `(actual - baseline) / baseline`; baseline values are supplied, not invented from dates. Monthly trend uses actual units, not mixed-scale measures.
- Variance Analysis: actual − target. Percentage-level differences use percentage points (`pp`); relative YoY/MoM remain percentages.
- Contribution Analysis: share = component / total; change = component − previous. Negative growth contributions are allowed although raw nonnegative amounts are required.
- Management Summary: computed facts only. The engine does not invent causes, forecasts or prescriptions.

Input example: [business-performance.json](../skill/analytics/business-performance.json). Unknown numeric values must be explicit `null`: output shows N/A, and incomplete totals remain unknown. A zero denominator yields N/A. An incomplete chart observation is excluded with a data note and retained in a table. Trend gaps need explicit null months. Revenue returns/negative raw amounts require a separately designed net-value contract; they are not accepted by this first recipe.

## Sales Conversion

Input: acquisition period, `as_of`, elapsed-day `horizon_days`, lead/customer identity, acquisition date, channel and region, configured stage definitions, directed observation edges and dated events. `lead` is reserved for acquisition. Stage labels are supplied by the user. There is no mandatory test-drive stage.

- Lead Funnel: only nested mature acquired customers → observed outcome. Optional visit/trial behavior is a separate reach chart. Zero outcomes never become an invented positive funnel count.
- Conversion Rate: distinct outcome customers in their fixed acquisition horizon / distinct mature acquired customers. An observation on the horizon endpoint is included (day zero is acquisition). Immature customers are reported separately and excluded from rate denominators.
- Stage Drop-off: denominator reached the configured source stage; numerator subsequently reached the target. The first observed event per stage is used. A missing later event means **not observed**, not necessarily a lost customer.
- Cohort Conversion: acquisition month, constant observation horizon. Cross-month outcome events are included when inside the customer window; calendar-period sales and cohort sales are different measures.
- Regional / Store Comparison: the `region` dimension may contain regions or stores, consistently for the entire input. First-touch attribution remains fixed. No latest-store reassignment.
- Sales Driver Analysis: behavior-stratified conversion and channel attribution are descriptive. Self-selection, channel mix, missing observations and confounding prevent causal attribution. Trial correlation is never converted into a claim that trials caused sales growth.

Exact repeated lead rows are deduplicated; conflicting rows sharing `lead_id` fail. Different leads for the same customer use the earliest acquisition; same-date conflicting first-touch attribution fails. Events count a customer once per stage. Unknown customer/stage, dates before acquisition or after `as_of` fail. IDs must already be canonical across systems: probabilistic identity linkage is not implemented. Missing events are not imputed; input data completeness must be checked by the owner.

Input example: [sales-conversion.json](../skill/analytics/sales-conversion.json). The synthetic case includes duplicate leads/events, cross-period outcomes, immature cohorts and completed orders without trial.

## Project Analytics

Input: explicit `measurement_basis: cumulative_as_of`, `currency: CNY`, one common delivery `unit`, project plans/actuals, human-days, day rates, external costs, full budget, supplied realized value, risk and milestone dates. These are cumulative snapshots, not summed period flows. Future forecasts and mixed-unit aggregation are outside this contract.

- Project KPI / Planned vs Actual: complete delivery and resource totals; missing component makes the total unknown.
- Milestone Performance: completed delay = actual date − planned date. Null actual stays open, overdue if its deadline is before `as_of`.
- Resource Allocation: planned and actual human-days per project.
- Budget / Cost Variance: cost = actual days × day rate + external cost. Variance = cost − full budget; usage = cost / budget. This is not earned-value analysis and an unused full budget is not automatically a saving.
- Risk and Delivery Overview: declared risk alongside delivery difference. Value/cost uses supplied realized value only; it is not a future ROI estimate or causal benefit claim.

Input example: [project-analytics.json](../skill/analytics/project-analytics.json). Unknown realized value remains N/A, including the portfolio total. Milestone/project IDs must resolve; actual completion after `as_of` fails.

## Capacity and fidelity

The planner explicitly splits all tables at eight rows, charts at ten categories, KPI groups at six and summaries at five. Every observation remains in the corresponding tables. No renderer silently discards rows or measures. Long text beyond measured capacity fails actionably instead of shrinking indefinitely.

`--analytics-input` recomputes the original input, compares the generated Spec, then checks serialized native table/KPI text and numeric chart caches. It detects changed Spec values and changed native chart values. It does not authenticate source data, prove source completeness or certify causality. Numerical regressions cover units, zero denominators, nulls, reconciliation, cross-period cohorts, optional trial, duplicate identity, chronology, overflow and pagination.

## Design references and reuse boundary

The implementation uses general, publicly described communication principles in original code:

- [IBCS](https://www.ibcs.com/ibcs-version-2-0/): consistent meaning and notation; findings before decoration. No IBCS/ISO compliance or certification claim.
- [Microsoft Power BI dashboard guidance](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips): audience, contextual metrics, comparable time periods and scales, restrained emphasis.
- [Tableau visual best practices](https://help.tableau.com/current/pro/desktop/en-us/visual_best_practices.htm): consistent typography and formatting, deliberate axes and supporting annotation.

Reviewed 2026-10-16. No commercial templates, screenshots, charts, fonts or source code from these references were copied or redistributed. All benchmark numbers and imagery are synthetic or project-authored; the showroom illustration is AI generated and visibly identified.
