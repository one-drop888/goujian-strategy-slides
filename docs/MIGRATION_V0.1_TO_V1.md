# Migration from V0.1 to V1.0

V1 preserves V0.1's ten original slide types while introducing semantic archetypes, composition routing, a larger profile library and stronger QA.

## Existing specs

Within the validated V1 payload and capacity contract, existing `cover`, `section`, `statement`, `kpi`, `comparison`, `process`, `timeline`, `chart`, `table` and `action` slides continue to build.

## Recommended V1 migration

- Add `storyline` at deck level when known.
- Prefer semantic types such as `executive-summary`, `trend`, `root-cause`, `roadmap`, `risk` or `decision` instead of generic renderer labels.
- Add `source`, `unit` and `period` to decision-relevant charts.
- Use a built-in Profile rather than deck-specific hard-coded colors.
- Run `quality_gate.py` after PPTX generation.

## Breaking philosophy change

V0.1 treated slide types close to renderer types. V1 treats a slide type as **semantic intent**. The Composition layer resolves that intent to a reusable renderer.

V1 now rejects malformed or over-capacity input and unsupported specialized chart semantics. Older specs that depended on silent truncation or false chart aliases must be corrected. See [the spec contract](SPEC_CONTRACT.md).
