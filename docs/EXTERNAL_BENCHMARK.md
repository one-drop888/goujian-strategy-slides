# External reference benchmark

Reviewed 2026-10-14. This is a qualitative review of public primary documentation, not a timed competitive benchmark or a claim that competitor tools were executed. No code, templates or visual assets were copied.

| Reference | Observed emphasis | Implication for Goujian |
|---|---|---|
| [Anthropic PPTX skill](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md) | Native authoring, existing-package editing, thumbnail review and detailed Office-file validation workflows | Goujian's management vocabulary is more explicit; its arbitrary-file editing and OOXML validation are narrower. The reference identifies proprietary licensing; no implementation was copied. |
| [PptxGenJS chart documentation](https://gitbrent.github.io/PptxGenJS/docs/api-charts/) | Native chart controls, axes, legends and series options | The candidate underused available styling. Goujian now sets orientation, fonts, baselines, muted grids and selective emphasis explicitly. |
| [Slidev guide](https://sli.dev/guide/) | Developer-oriented slides with a web-native authoring/rendering model | Goujian has a stronger management-spec orientation for its target use, but no comparable HTML/interactivity implementation. |
| [Duarte data storytelling](https://www.duarte.com/services/data-storytelling-services/) | Connecting analysis and visual communication to decisions | Use evidence and its implication as the organizing unit, not a visually busy slide count. This was a conceptual reference, not a template source. |

## Three defensible strengths

1. An explicit management argument model, with reusable storyline questions and semantic roles, guides the agent before layout.
2. A small native editable PPTX backend reuses compositions across that semantic vocabulary, with profiles and a testable JSON contract.
3. Evidence/source visibility, declared partial capabilities, negative tests and hash-bound visual records make limits inspectable.

These are strengths of product fit and workflow design, not evidence of universal superiority over other tools.

## Three gaps

1. **Editing and package fidelity:** text-node edits and agent-led rebuilding are much narrower than comprehensive template/master manipulation. Deferred to later versions.
2. **Layout and visual intelligence:** fixed bounded geometry does not measure all text or optimize labels. This round improved typography, charts, tables and diagrams, but an automatic layout solver/repair loop remains future work.
3. **Authoring reach and onboarding:** the initial candidate lacked convincing examples, transparent capability boundaries and reproducible installation evidence. Bilingual docs, actual render previews, a lockfile and a repeatable benchmark runner address the low-risk portion. Native Windows/macOS validation and HTML output remain gaps.
