# Goujian Strategy Slides

[English](PRODUCT_OVERVIEW.md) | [简体中文](PRODUCT_OVERVIEW.zh-CN.md) | [Repository root](../README.en.md) · [Installation](../README.en.md#installation) · [Benchmarks A–J](BENCHMARKS_V1_2.md) · [Feasibility review](FEASIBILITY_REVIEW.md)

## Presentation Intelligence for AI Agents

Goujian Strategy Slides is an open-source presentation skill designed to help AI agents turn complex information into clear, structured and decision-useful presentations.

**Think clearly. Structure strategically. Present decisively.**

It models the reasoning behind a strong professional presentation:

**Think → Structure → Visualize → Build → Validate**

It combines management storytelling, storylines, action titles, semantic archetypes, composition grammar, data visualization, profile-driven design, native editable PPTX generation and quality gates into one workflow. The agent supplies judgment; deterministic code validates, builds and exposes boundaries.

> Great presentations are not collections of beautiful slides. They are structured arguments designed to help people understand complex information and act.

Its management reasoning model is **Question → Evidence → Judgment → Action**. High information density ≠ high text density: charts, comparisons, frameworks and tables should carry the argument, with text reserved for interpretation and action.

## Who it serves

- Management teams reviewing results, diagnosing gaps and assigning owned actions.
- Research teams connecting sample design, quantitative signals, quotations and qualified interpretation.
- Product and technology teams explaining choices, risks, operating models and staged implementation.
- AI agents that need a reusable presentation workflow instead of ad hoc slide-generation scripts.

## How V1.2 works

The agent establishes the decision, evidence, constraints and content dispositions, then authors a Reasoning Plan. Deterministic validation checks structure, arithmetic, referential closure, coverage, numeric bindings and theme selection. Compilation produces an exported spec and a native editable PPTX. A hash-bound scene and reasoning sidecar support structural QA and actual rendering for semantic/visual review.

The Reasoning Plan is an **agent-authored** input; this project has no independent general reasoning model. Validation supports `sum`, `difference`, `ratio` and `percent_change`, including unit, time-window, metric and denominator checks. There is no arbitrary formula engine, significance test or causal inference. Structured JSON sources can be compared with source bytes through JSON Pointers. Numeric ledgers extracted from images, PDFs, text or native PPTX remain reviewer-required. A citation is not proof of source truth.

The library contains 28 storylines, 86 semantic entries, 27 composition recipes, 15 profiles and 15 starting recipes. **74 semantic entries are implemented, 6 are partial, and 6 are designed only.** The last group cannot be built. Counts describe vocabulary, not a promise of 86 independently designed layouts.

## Theme and visual system

Theme precedence is reference profile > brand profile > explicit user profile > automatic intent matching > default. An explicit dark request can override automatic light selection, but dark versus printable and related conflicts are recorded rather than hidden. The selected profile drives typography, spacing, tables, metrics, chart grids and colors.

V1.2 showcases three theme variants and eight dark native chart types. Titles use glyph measurement and conservative estimation, with short-title/subtitle support, a dynamic divider and body flow. Measurement is not proof of exact PowerPoint shaping; structural QA cannot prove the absence of rendered text collisions. The final frame requires inspection.

Images, native charts, tables and interpretation share one pipeline with source, pixel-text, crop and scene relationships. Asset classification, semantic rewriting and visual repair remain agent-assisted. There is no automatic OCR, arbitrary lossless PPTX editor, autonomous visual repair or cross-renderer layout engine.

## V1.2 delivery and review

Eight showcase cases cover an executive review, Q4 actions, multisource consolidation, three theme variants, eight dark charts and a long-title regression. Each case preserves reference inputs, exported spec, PPTX, reasoning sidecar, QA, actual LibreOffice render, montage and hash manifest. The install ZIP is a separate lightweight runtime; the showcase ZIP is an optional review artifact.

Independent final visual acceptance was completed after writing stopped: Codex reviewed all 58 pages across the 8 showcase cases on Linux LibreOffice with synthetic fixtures, with `PASS_WITH_KNOWN_LIMITATIONS` bound to exact PPTX and page hashes. This is not publication approval. The 15 legacy benchmark scenarios remain visual `NOT_RUN`, and all 15 profiles were not fully visually tested. Native PowerPoint on macOS/Windows/ARM64 was not executed; Agensi/company-hosted runtime is not verified.

The Community core, including doctor, QA and defect fixes, remains free under Apache-2.0. Supporter and Pro are future candidates only: no account, payment or listing exists in this repository. Pro adds business workflow packs, not a second rendering engine. See [Commercial readiness](COMMERCIAL_READINESS.md).

For exact limits, read the [feasibility review](FEASIBILITY_REVIEW.md), [quality and validation](QUALITY_AND_VALIDATION.md), [Benchmarks A–J](BENCHMARKS_V1_2.md) and [root README](../README.en.md). V1.1 and earlier release documents remain historical records and are not retroactively rewritten.
