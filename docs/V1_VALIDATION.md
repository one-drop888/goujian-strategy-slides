# V1 validation record

Executed locally on 2026-10-14. Environment: Linux, Node 24.18.0, npm 11.19.1, Python 3.14.4, LibreOffice 26.2.6.3, Poppler 26.05.0, Pillow 12.1.1, installed Noto Sans and Noto Sans CJK SC. Optional system dependencies were already installed; this is a clean source/dependency installation, not a fresh operating-system image.

| Check | Result | Scope |
|---|---|---|
| `npm install` from clean extracted runtime | PASS | New directory and new node_modules; committed lockfile |
| `npm test` | PASS | Architecture smoke tests, ten example specs, schema/profile/planner contract tests, six QA regressions, native 23-recipe gallery |
| `npm run validate:example` | PASS | Business review spec |
| `npm run build:example` | PASS | Editable 8-slide PPTX |
| `npm run qa:example` | PASS_WITH_NOTES | Geometry/font/render pass; no automatic visual approval |
| Ten benchmark builds | PASS | 60 pages; each scenario executed |
| Ten benchmark spec checks | PASS_WITH_NOTES | Nine pass; training explicitly warns about partial case-study semantics |
| Geometry QA | PASS | All ten decks; bounded checks, not text-fit proof |
| Font QA | PASS | Explicit families available on this host, including chart text |
| Render / montage | PASS | All ten decks, 60 pages |
| Visual review | PASS, vision-agent scope | All benchmark montages plus representative full-size pages; hash-bound records |
| Profile coverage | PASS | 15 profiles × 3 common probe pages; final dark-theme correction rerendered |
| Composition coverage | PASS | 23 recipes built, geometry checked and rendered; montage inspected |
| Existing PPTX workflow | PASS within bounds | Inspection, one-node text replacement, edited-deck render, style extraction and profile-derived build |
| Core without optional Python packages | PASS | Standard-library QA works; rendering reports unavailable when Pillow cannot be imported |
| Native Microsoft PowerPoint editing/rendering | NOT_RUN | Native XML/workbook checks do not replace Office UI verification |
| Native Windows/macOS installation | NOT_RUN | Linux verified; WSL/macOS guidance is not a tested-platform claim |

[Benchmark evidence](evidence/benchmark-summary.json) contains exact local PPTX hashes and per-scenario results. [Visual review](VISUAL_REVIEW.md) includes before/after images. Rebuilds need fresh reviews; hashes are not reproducible-build assertions.

All examples are illustrative synthetic content, not private company evidence. No benchmark competitor execution, user-adoption study or independent human aesthetic approval is claimed.

GitHub CI covers Node 18/Python 3.9 and Node 24/Python 3.11. Its presence in source is not proof of a passed run. The release workflow separately verifies a fresh clone after publication; see its actual run result and the final release report for remote evidence.
