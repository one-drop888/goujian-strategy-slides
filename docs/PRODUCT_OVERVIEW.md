# Goujian Strategy Slides

[English](PRODUCT_OVERVIEW.md) | [简体中文](PRODUCT_OVERVIEW.zh-CN.md)

## Presentation Intelligence for AI Agents

Goujian Strategy Slides is an open-source, production-oriented presentation skill designed to help AI agents turn complex information into clear, structured and decision-useful presentations.

**Think clearly. Structure strategically. Present decisively.**

Instead of treating presentation creation as a simple text-to-slide task, Goujian models the reasoning process behind strong professional presentations:

**Think → Structure → Visualize → Build → Validate**

It combines management storytelling, storyline planning, semantic slide archetypes, reusable composition grammar, visualization logic, profile-driven design, native editable PPTX generation and quality validation into one presentation workflow.

> Great presentations are not collections of beautiful slides. They are structured arguments designed to make complex information understandable and actionable.

Its management reasoning model is **Question → Evidence → Judgment → Action**. High information density ≠ high text density: the chart, comparison, framework or table should carry the argument, with text reserved for interpretation and action.

## Who it serves

- Management teams reviewing results, diagnosing gaps and assigning owned actions.
- Research teams connecting sample design, quantitative signals, quotations and qualified interpretations.
- Product and technology teams explaining choices, risks, operating models and staged implementation.
- AI agents that need a reusable presentation workflow instead of ad hoc slide-generation scripts.

## How the product works

The agent first establishes the decision, evidence and constraints. It chooses a storyline and semantic slide purpose, then creates a JSON presentation spec. Reusable compositions and an explicit visual profile drive the PPTX backend. Executable validation rejects malformed or over-capacity payloads. Rendering and visual inspection close the loop.

The library contains 28 storylines, 78 semantic entries, 23 composition recipes, 15 profiles and 15 starting recipes. **65 semantic entries are implemented, 6 are partial, and 7 are designed only.** The last group cannot be built. Counts describe a vocabulary, not a promise of 78 independently designed or equally expressive layouts.

## V1 scope

V1 focuses on PowerPoint/PPTX. Native text, shapes, tables and supported chart data remain editable. Basic text edits, agent-led reconstruction and style statistics support existing-deck workflows, within explicit limits.

The planner is a small heuristic helper, not an autonomous analyst. Evidence selection, causal judgment, template interpretation and visual repair remain agent/human responsibilities. The full [capability matrix](../README.md#capability-boundaries) and [feasibility review](FEASIBILITY_REVIEW.md) state those limits.

The Presentation Intelligence layer is independent of PptxGenJS. It leaves a path to HTML and web-based renderers, while the reusable cross-renderer geometry engine is future work. V1 does not implement HTML output, animations, arbitrary lossless PPTX editing or deterministic visual repair.

There is one product and one Presentation Library. Platform adapters provide thin execution guidance, not different public/company/personal editions.
