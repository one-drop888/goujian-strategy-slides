# Goujian Strategy Slides

[English](PRODUCT_OVERVIEW.md) | [简体中文](PRODUCT_OVERVIEW.zh-CN.md) · [README](../README.en.md)

**Presentation Intelligence for AI Agents**

Goujian is an open-source, production-oriented presentation skill. It helps an agent turn complex information into a structured argument and native editable PowerPoint, with explicit data contracts and reviewable output.

Think clearly. Structure strategically. Present decisively.

**Think → Structure → Visualize → Build → Validate**

A useful management presentation answers a question, presents evidence, makes a supported judgment and identifies an action. Goujian uses **Question → Evidence → Judgment → Action** to organize that work. High information density does not mean high text density: a precise comparison may communicate more than several paragraphs, while a table may be better than a chart for exact lookup.

## What you get

- A reusable presentation library: storylines, semantic archetypes, compositions, profiles and recipes, backed by one native PPTX engine. These are expression choices, not hundreds of unrelated slide templates.
- Three executable analytical workflows: business performance, nonlinear sales conversion and project performance. Inputs, calculations, periods, denominators and missing facts stay inspectable.
- Optional typed metrics for fractions, percentages, percentage points, currency, scaling and display precision. A fact can drive a title, KPI, table and native chart without repeated manual conversion.
- An agent-authored Reasoning Plan for sources, claims, arithmetic and content dispositions. A declared Narrative Graph tracks questions, evidence, pages and decisions without automatically deleting similar content.
- Visual encoding for categorical comparisons, declared value scales and business roles; native text, charts, tables and shapes; measured titles and image/evidence compositions.
- Executable QA on serialized PPTX and chart workbooks, plus geometry, fonts, spatial checks, actual render and a separate visual-review record.

The working boundary is deliberate: the agent explains and chooses; code computes, constrains and records. The project does not contain an independent general business reasoning model, arbitrary statistical significance engine or causal inference system.

## One product, different agent environments

The Community runtime is Apache-2.0 and retains one root `SKILL.md`. Agent adapters reuse the same core; a platform display name does not create a new skill ID or a company-specific branch. Install the complete source/runtime ZIP, not only the `skill/` directory.

Node18+/Python3.9+ remain compatibility floors; use maintained security-patched runtimes. Secure image/full-render functionality needs Python3.11+/Pillow13 plus external render tools/fonts. See [installation](INSTALLATION.md).

## Output and limitations

Native text, shapes, tables and supported charts can be edited in PowerPoint. Pixel text in screenshots cannot. Existing PPTX text replacement is bounded to a single DrawingML text node; lossless round-trip editing, imported master cloning, automatic OCR and autonomous visual repair are not implemented.

Six native chart families are supported. Explicit equal-width histogram bins and stacked bar/column have bounded implementations; unsupported statistical or combination charts are rejected instead of relabeled. Source truth, business relevance and aesthetics still require review. The executed Linux environment does not prove native Windows/macOS/ARM64 PowerPoint parity or company/Agensi approval.

V1.3 focuses on **Semantic Accuracy → Visual Encoding → Perceptual Clarity → Management Insight**. The [benchmark](BENCHMARKS_V1_3.md) and [feasibility review](FEASIBILITY_REVIEW.md) state what was actually tested. Pro is a separate product design; it does not remove correctness or readability fixes from Community and is not a launched paid product.
