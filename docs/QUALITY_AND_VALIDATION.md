# Quality and validation · V1.3

A generated file, a parsed schema and a rendered image are different evidence. The standard gate records them separately:

```bash
python3 skill/scripts/quality_gate.py out/deck.pptx --spec deck.json \
  --out out/qa.json --render-dir out/render
```

For an explicit build profile, pass `--profile <id-or-path>`. For a declared narrative checked against a Reasoning Plan, pass `--plan plan.json`. Keep the original spec; never send the transformed `effective_spec` as a new source input. The fixed local Node runner is also callable:

```bash
node skill/scripts/semantic_qa.js --pptx out/deck.pptx --spec deck.json --out out/semantic.json
```

## Deterministic checks

| Check | Evidence / boundary |
|---|---|
| Schema/composition | Typed meaning, references, fields and bounded capacities; invalid or unsupported inputs fail before build |
| NUMERIC_SEMANTIC_FIDELITY | Re-derive effective facts from the original spec; compare native cache and XLSX cells; null is distinct from zero |
| CHART_TYPE_FIDELITY | Actual family, bar orientation and declared grouping match the original spec; no relabeled substitute |
| CHART_AXIS_INTEGRITY | Serialized axis bounds retain visible data and required zero/disclosure semantics |
| UNIT_CONSISTENCY | Actual unit captions and native number formats; scale transformations disclosed |
| PERCENTAGE_SCALE_VALIDATION | Fraction vs stored-percent raw/effective values and formatted text |
| PERCENT_POINT_VALIDATION | pp facts/text, distinct from relative change |
| CHART_TABLE_NUMERIC_RECONCILIATION | Explicit metric links across charts and native table/KPI text; unlinked legacy strings are not automatically reconciled |
| CHART_SERIES_DISTINGUISHABILITY | Pairwise ΔE76/grayscale and secondary line/marker cues; heuristic thresholds, not certification |
| CHART_COLOR_SEMANTICS | Re-derived encoding versus actual native paints/roles |
| CHART_LEGEND_SERIES_MAPPING | Native series/category identity and legend mapping |
| CHART_ACCESSIBILITY | Paint/background and distinguishability heuristics; no automatic WCAG or color-vision certification |
| NARRATIVE_STRUCTURE | Declared claim/evidence/page/decision closure and retained evidence fingerprints; semantic usefulness remains reviewer-required |
| Geometry/spatial/fonts | Native objects, bounds, evidence occlusion, header/divider relationships, measured text and font resolution; estimates cannot prove all text fits |
| Source/Reasoning | Existing Plan source/spec hashes, supported arithmetic, content coverage and final embedded-report/native verification; source authenticity remains separate |

The generic native checker reads actual PPTX/XLSX parts and re-derives meaning; it never treats a scene's PASS flag as truth. The scene can bind an exact file hash and record a chosen profile. The full Reasoning verifier additionally requires a trusted final PPTX hash and authenticates its embedded report. A self-supplied hash alone is not source authentication.

Legacy specs remain supported. A check that needs absent typed links or a narrative graph is NOT_RUN or PARTIAL; do not convert it into PASS. Bounded analytical recipes retain deterministic input/data-fidelity checks. Unsupported chart families and graph capacities are rejected, with faithful alternatives or split guidance.

## Actual render and visual review

LibreOffice and Poppler produce PDF/page PNGs and a montage. Render PASS means conversion succeeded and page counts match. It does not mean the chart is insightful, text readable, labels collision-free or the source truthful. Inspect the montage for rhythm and every changed representative page at full size, including dense evidence, chart labels, Chinese glyphs, background text contrast and flow arrows.

Repair the original spec, shared composition or renderer, then rebuild and rerender. Preserve the before/after, concrete findings and source/code fingerprint. The reviewer record must bind the exact final PPTX bytes:

```json
{"pptx_sha256":"<64 hex characters>","reviewer":"<actual reviewer>",
 "status":"PASS","slides_reviewed":[1,2,3],
 "notes":"Concrete pages inspected, findings, repairs and remaining limits."}
```

Attach it with `--visual-review review.json`. The gate validates file identity, reviewer and complete page list; this is an attestation, not an automated aesthetic judgment. Never manufacture this record from a build exit code. If the file changes, the old record does not approve it. Pixel-identical renders may support a documented differential review, but this still requires an explicit comparison and current file identity.

## Status vocabulary

- PASS: the named check actually ran and met its bounded criteria.
- PASS_WITH_NOTES: bounded automatic checks passed with unavailable/reviewer-required or disclosed items.
- FAIL: a blocking inconsistency or failed executed check.
- PARTIAL: only a stated part of the capability/check is verified.
- NOT_RUN: not executed or not applicable without a required declaration.
- UNAVAILABLE: required environment/tool missing.

Narrative coherence, decision relevance, visualization opportunities, source truth and aesthetics require Agent/human review. Do not turn keyword matches or metadata presence into semantic/perceptual approval.

## Install/package/platform gates

Run full/core tests for the chosen runtime tier, fresh ZIP installation, Unicode path construction, Doctor/bootstrap and actual build/QA/render. Packaging fixes ordering/time/permissions, retains one Skill entry and excludes caches, secrets and generated installer outputs. Preflight the **actual final ZIP** including code, instructions, references and dependency declarations.

Dependency advisory checks are dated snapshots, not a guarantee of no unknown vulnerabilities. Public CI cannot establish company-platform upload/security, Agensi hosting/payment, or native Windows/macOS/ARM64 PowerPoint parity. Those statuses stay NOT_VERIFIED/NOT_RUN until their separate journeys execute.

See [V1.3 benchmark](BENCHMARKS_V1_3.md), [migration](MIGRATION_V1_3.md) and [feasibility](FEASIBILITY_REVIEW.md) for release evidence and limits.
