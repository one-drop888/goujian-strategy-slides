# Hermes Adapter

Hermes should treat `SKILL.md` as the presentation capability entrypoint and reuse the same V1 Presentation Library as every other runtime.

Recommended execution contract:

```text
Input/context → semantic JSON → validate → build → quality gate → inspect montage → deliver
```

Hermes-specific wrapper code may handle tool invocation or file paths. It must not duplicate Storylines, Archetypes, Profiles or renderers.
