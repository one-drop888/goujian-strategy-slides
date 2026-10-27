# Contributing

The project optimizes for **decision-useful presentations**, not template count.

## Before adding anything

Ask which layer is actually missing:

- new business scenario → add or improve a Storyline;
- new semantic intent → add an Archetype;
- materially new information structure → add a Composition;
- visual language → add a Profile;
- correctness/reliability → add QA;
- platform integration only → add a thin Adapter.

Do not create a renderer for every new business label.

## Acceptance criteria

A contribution should:
1. preserve documented V1 payload behavior, and document intentional validation changes;
2. include a sanitized example or test when behavior changes;
3. keep native editability where practical;
4. avoid confidential/unlicensed assets;
5. pass `npm test`;
6. render representative examples when changing layout code.

## Release security gate

Packaging, scanner, review and release changes must follow the
[release security gate](https://github.com/one-drop888/goujian-strategy-slides/blob/main/docs/RELEASE_SECURITY_GATE.md).
Run `npm test` (which includes the gate unit tests) before opening a change. The
gate is fail-closed: unreviewed HIGH/CRITICAL findings keep CI and release red
until an independent reviewer records an exact, content-bound review. Do not
broaden allowlists, hide keywords, or bypass the scanner to obtain a green run.

## License

By contributing, you agree that your contribution is licensed under Apache-2.0. Do not submit code or visual assets you do not have the right to redistribute.
