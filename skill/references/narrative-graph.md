# Declared narrative graph

The optional root `narrative` field adds a reviewable argument ledger to an existing deck spec. It is backward compatible: legacy decks without it still build and report narrative review NOT_RUN. `core/semantics/narrative.js` checks declared structure and evidence presence; it is not an autonomous storyline model.

Declare an `objective`; claims with IDs/text/kind/evidence_ids; evidence with source_id and actual slide/JSON Pointer bindings; one node per slide; forward edges with a named relation and explanation; optional decisions. Content nodes need a question and claim; later nodes need a transition. Roles: cover, transition, summary, detail, comparison, decision, appendix. Relations: introduces, supports, expands, contrasts, leads_to, recaps.

```json
{"objective":"确认收入差距及下一步验证",
 "claims":[{"id":"gap","text":"收入距目标40万元","kind":"FACT","evidence_ids":["sales"]}],
 "evidence":[{"id":"sales","source_id":"synthetic-sales","bindings":[{"slide":1,"pointer":"/rows/0"}]}],
 "nodes":[{"slide":1,"role":"detail","question":"实际与目标差多少？","claim_ids":["gap"],"evidence_ids":["sales"],"decision_ids":["review"]}],
 "edges":[],
 "decisions":[{"id":"review","question":"是否安排口径与原因验证？","claim_ids":["gap"]}]}
```

The example accompanies a table slide with a retained row of actual/target data. Bindings are restricted to supported content fields and fingerprint actual retained content plus unit/period. Required claims/evidence must be covered. An appendix disposition preserves evidence and stays traceable. If a Reasoning Plan is supplied, claim IDs/text/kind must agree with the plan and source IDs must be known. Source authenticity still needs a source ledger and review.

Exact repeated titles and repeated claim/evidence combinations produce redundancy candidates. A summary followed by detail may explicitly declare `expansion_note` to describe the added value. This is a reviewer assertion, not an algorithmic proof that similar wording is useful. Never delete a page or numerical evidence solely because words match. Unspecified owner/timing remains unknown; no dates, benefits or responsibility are invented.

The report distinguishes structural checks from `review_required: true`. `VISUALIZATION_OPPORTUNITY_REVIEW` requires the agent to judge whether a comparison/trend would communicate more clearly than plain numbers. The automatic checker does not simulate this judgment with keywords. Builds put the graph in the scene and page-level narrative context in editable speaker notes. Full semantic and aesthetic review remains a separate gate.
