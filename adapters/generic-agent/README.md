# Generic Agent Adapter

This repository is already the runtime package. A generic agent should:

1. load `SKILL.md`;
2. read only the referenced Storyline / Archetype / Profile rules needed for the current task;
3. generate a semantic deck JSON;
4. validate it with `skill/scripts/validate_spec.py`;
5. build with `skill/scripts/build_deck.js`;
6. run `skill/scripts/quality_gate.py`;
7. inspect the rendered montage before claiming Visual QA PASS.

Platform-specific manifests may live in an adapter, but adapters must not fork the Presentation Library.
