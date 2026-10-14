---
name: goujian-strategy-slides
metadata:
  version: "1.0.0"
description: Plan, build and review editable PPTX presentations for business reviews, strategy, research and technical decisions. Use for new semantic decks, agent-assisted rebuilding and reference-informed restyling; existing PPTX editing is limited to text within individual runs.
license: Apache-2.0
---

# Goujian Strategy Slides｜构见·战略演示

**Think clearly. Structure strategically. Present decisively.**

Think → Structure → Visualize → Build → Validate

Build a structured argument using **Question → Evidence → Judgment → Action**.
High information density ≠ high text density. Preserve the user's decision, evidence and uncertainty.

## Runtime and paths

Install the **entire repository**, including `core/`, `skill/`, `package.json` and the lockfile. Run commands from that repository root, even when this entrypoint is opened from `skill/`. Run `npm install` once. Core QA also requires Python 3.9+. Optional rendering needs LibreOffice, Poppler and Pillow; use [installation instructions](README.en.md#installation).

`SKILL.md` at the repository root is canonical; `skill/SKILL.md` is a distribution mirror, not a standalone runtime. Resolve relative links against the repository root.

## Route and plan

- **NEW:** identify audience, decision, evidence and meeting context; create a semantic JSON spec.
- **EDIT:** read [existing PPTX workflow](docs/EXISTING_PPTX_WORKFLOW.md). Only text replacements inside a single DrawingML text node are implemented; always write a separate output and rerender.
- **REBUILD / RESTYLE / REFERENCE:** inspect the PPTX and extract style. The agent reconstructs the argument and spec. Layout/master cloning, lossless round trips and automatic evidence extraction are not implemented.

Read the relevant [storyline](skill/storylines/registry.json), [template recipe](skill/templates/registry.json) and [archetype](skill/archetypes/registry.json). Recipes choose a storyline/profile; they are not imported PowerPoint masters. The planner in `core/planner/` is a keyword heuristic, not a source-to-deck reasoning model. The agent must choose and justify the story.

For operating reviews, consider Result → Structure → Gap → Cause → Action → Owner / timing.
For research, consider Question → Method / sample → Quantitative evidence → Qualitative evidence → Segment differences → Interpretation → Recommendation.

## Compose the argument

Read [content planning](skill/references/content-planning.md), [visualization rules](skill/references/visualization-rules.md) and [anti-AI-PPT guidance](skill/references/anti-ai-ppt.md) as needed.

Use conclusion-bearing action titles when evidence supports them. Cover, methodology and exploratory pages may use descriptive titles. Distinguish observation, interpretation and hypothesis. Do not invent evidence or infer causality from frequency alone.

Choose archetypes by semantic purpose, then reuse the [composition registry](skill/compositions/registry.json). Check each archetype's `status` and `limitation` before authoring:

- `IMPLEMENTED`: a V1 composition is available; the supplied content still needs review.
- `PARTIAL`: an explicit simplified representation; disclose its limitation.
- `DESIGNED`: no faithful renderer. The build rejects it; choose an implemented alternative explicitly.

Waterfall/bridge, combo, scatter/bubble, heatmap and image-insight are designed only in V1. Do not relabel a generic chart as one of these. Abstract maps, relationships and Sankey-like component groups do not encode geographic positions or flow quantities.

See [spec contract](docs/SPEC_CONTRACT.md) for fields, capacity limits and a minimal example. Keep chart series in the same unit or normalize with a disclosed calculation. Matrix coordinates must come from the author, not arbitrary placement. Funnel values must share a denominator. Split over-capacity pages; the builder will not silently discard content.

## Apply a Profile

Use an explicit user/reference choice first, then a suitable built-in profile, otherwise `executive-clean`. [Profile guide](docs/CUSTOM_PROFILE_GUIDE.md) documents typography, density, margins, chart grids, table styling, metrics and title/cover treatment. The default fonts are Noto Sans and Noto Sans CJK SC; install them on the rendering and recipient machines or provide an installed custom font.

## Build, inspect and repair

```bash
python3 skill/scripts/validate_spec.py deck.json out/spec-qa.json
node skill/scripts/build_deck.js deck.json out/deck.pptx
python3 skill/scripts/quality_gate.py out/deck.pptx --spec deck.json --out out/quality-report.json --render-dir out/render
```

The builder validates schema and composition payloads before writing. Output uses native editable shapes, text, tables and supported charts; the renderer supports a 16:9 wide canvas only.

Inspect **both** the montage for page rhythm and individual pages for titles, small labels, evidence, text fit, Chinese glyphs and relationships. Fix the source spec or shared renderer and rebuild. Render success is not visual approval. Geometry checks do not measure text overflow or understand intended overlaps.

After actual inspection, record the current PPTX SHA256, reviewer, reviewed slide numbers and concrete findings as described in [QA documentation](docs/QUALITY_AND_VALIDATION.md). Use `--visual-review review.json` to attach that review. A prior review cannot approve a rebuilt file with a different hash.

Deliver the PPTX, spec and QA result. State any `PARTIAL`, `UNAVAILABLE` or `NOT_RUN` checks. Human/agent repair remains an iterative workflow; V1 has no autonomous deterministic visual repair engine.

## Source and distribution boundaries

Keep source files intact and derivatives separate. Preserve provenance, evidence limitations, font/asset licenses and user confidentiality. Adapters reuse the same library and do not imply permission to publish user content or contact others.
