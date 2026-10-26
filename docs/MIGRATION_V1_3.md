# Migrating from V1.2.1 to V1.3

V1.2.1 deck specs and Reasoning Plans remain accepted. Apache-2.0 and the single root `SKILL.md` entry are unchanged. Use the complete runtime archive; copying only `skill/` omits the shared core.

## Optional contracts

You can retain legacy strings/numeric series. Add root `metrics`, explicit placeholders and typed series when scale, units or cross-component consistency matter. Add root `narrative` for declared argument/evidence review. See [numeric and visual contract](../skill/references/analytical-visual-intelligence.md) and [narrative graph](../skill/references/narrative-graph.md). The original spec is the saved/rebuildable input; `effective_spec` is a build-internal representation, not an exported replacement source.

V1.3 rejects misleading typed unit/format/scale combinations, ambiguous percentage storage, hidden gaps, unsupported pie negatives and impossible encoding density. Repair the input, split a chart or select a faithful alternative. Do not strip units, convert null to zero or relabel an unsupported chart type. Legacy ordinal timeline semantics are preserved; a date-scaled timeline must declare its dates explicitly. Native output remains 16:9.

Measured titles may choose a readable smaller single line before a balanced two-line fallback. The minimum normal title is 22pt, unless an explicit profile starts smaller. The original text is retained. Use `title_short`/`subtitle` only after the agent has preserved the claim and moved context intentionally. This is bounded measurement, not automatic semantic rewriting or a generic layout optimizer.

## Secure runtime tiers

Node.js 18+ and Python 3.9+ remain the core baseline. Secure image processing, pixel text measurement and full rendering need **Python 3.11+ and Pillow 13.0.0**. Python 3.9/3.10 can run the core tier without Pillow; image-dependent checks report their limitations. There is no older vulnerable Pillow fallback. `npm run bootstrap -- --python /path/to/python3.11` explicitly selects the interpreter and installs dependencies only into the local `.venv` plus the project npm tree. Bootstrap does not install system fonts, LibreOffice or Poppler; follow the platform installation instructions and run Doctor.

The lockfile targets fast-uri3.1.9 for published security fixes without unrelated dependency upgrades. Python requirements use an environment marker, so old Python does not install the secure image tier. Activate `.venv` before running tests/QA. On Linux/macOS: `. .venv/bin/activate`; PowerShell: `.\.venv\Scripts\Activate.ps1`. Use `npm run test:core` for the Pillow-free core tier, `npm test` for the full image/render tier.

## Review and distribution

Keep PPTX, original spec, scene, provenance and QA together. A changed PPTX invalidates the earlier hash-bound visual review; rerender and inspect the changed pages. The standard Quality Gate distinguishes deterministic checks, rendering and reviewer attestation.

Run `npm run package`, then `npm run preflight -- dist/goujian-strategy-slides-v1.3.0.zip --json out/package-preflight.json`. Package preflight examines the actual archive, not only source files. It does not certify the company platform or Agensi. Those require their own real upload and approval. Native Windows/macOS PowerPoint consistency is not established by a Linux LibreOffice render.
