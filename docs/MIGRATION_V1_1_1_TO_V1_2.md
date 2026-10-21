# Migrate from V1.1.1 to V1.2.0

V1.2.0 is additive for existing users. The legacy deck JSON contract, profiles, analytics inputs and public CLI entry points remain supported. The new Reasoning Plan is optional.

## Compatibility summary

| Area | V1.1.1 | V1.2.0 |
|---|---|---|
| Legacy deck JSON | Supported | Supported; unchanged routing for valid accepted specs |
| Reasoning Plan | Not available | Optional Agent-authored plan with deterministic validation and sidecars |
| Native PPTX output | Supported | Supported; same editable object model |
| Node / Python minimum | Node 18+, Python 3.9+ | Unchanged |
| Dependencies | PptxGenJS 4.0.0 / Ajv 8.20.0 / JSZip 3.10.2 | Unchanged versions; JSZip remains an explicit dependency under MIT or GPL-3.0-or-later (MIT selected in notices) |
| Installer | v1.1.1 ZIP | `goujian-strategy-slides-v1.2.0.zip`; one root `SKILL.md`, no PPTX |
| Showcase | Not part of the installer | Separate optional `goujian-strategy-slides-v1.2.0-showcase.zip` |
| Desktop rendering | LibreOffice/Poppler/fonts optional | Unchanged; missing render tools remain `UNAVAILABLE`, not a visual pass |

There are no database migrations, account migrations or remote services. The installer contains no user content.

## Upgrade steps

1. Back up any custom specs, plans, profiles, source assets and generated decks outside the installed folder.
2. Remove or rename the old installed folder. Do not merge the new ZIP over an old directory; stale files may violate the single-SKILL and cache rules.
3. Extract `goujian-strategy-slides-v1.2.0.zip` to a path of your choice. It extracts to one `goujian-strategy-slides/` folder with one root `SKILL.md`.
4. From that folder, run:

```bash
npm run bootstrap
. .venv/bin/activate
npm run doctor -- --json
npm test
```

5. Rebuild existing outputs with the same spec inputs. If a deck was built from the V1.1 Q4 or multimodal fixtures, regenerate it: those fixtures received bounded copy fixes in V1.2.
6. Inspect the actual render. Do not reuse a visual review from a prior build; the record is bound to the PPTX hash.

## Choosing the plan workflow

- Existing semantic deck JSON: continue with `validate_spec.py` and `build_deck.js`; no plan is required.
- Auditable sources/calculations: add a Reasoning Plan and use `validate_plan.js` / `compile_plan.js`.
- A plan never overwrites an existing output without `--force`; use a new output name or replace only the intended artifact.
- The plan is agent-authored. Validation does not verify source truth or visual quality.

```bash
node skill/scripts/validate_plan.js plan.json --json
node skill/scripts/compile_plan.js plan.json --out out/deck.pptx --spec-out out/deck.spec.json
```

## Recovery

- `npm run doctor -- --json` reports missing/broken required tools and recovery hints. It does not prove commands executed.
- If `npm ci` fails, verify Node/npm versions, remove a partial `node_modules/`, and rerun `npm run bootstrap`.
- If the isolated environment is interrupted, rerun `npm run bootstrap`; it repairs a partial `.venv` without using global pip.
- If rendering is unavailable, install LibreOffice, Poppler and Noto fonts. Build/schema/inspection still work, but visual review remains unavailable.
- If a source path was relative to a copied example, run from the canonical fixture directory or edit the plan copy deliberately. Do not treat a copied reference input as the executable source.

## Rollback

Keep the old installer ZIP or source tag. To roll back, remove the V1.2 folder and reinstall the previous release. Plans and sidecars produced by V1.2 are not required by V1.1.1; keep them as records. Do not downgrade the lockfile in place if you need V1.2 behavior.

## Known limits carried forward

- 16:9 canvas only; no HTML renderer; waterfall/bridge, combo, scatter/bubble and heatmap remain designed only.
- No automatic OCR, arbitrary lossless PPTX editing, autonomous visual repair or font embedding.
- macOS/Windows/ARM64 native PowerPoint and Agensi-hosted runtime were not verified in this phase.
- Font measurement is an estimate; inspect final rendering.
