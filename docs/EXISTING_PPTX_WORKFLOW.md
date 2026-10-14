# Existing PPTX: Edit, Rebuild and Restyle

V1 distinguishes three operations because they have different reliability levels.

## 1. Basic text edit

Use `edit_pptx_text.py` for controlled text replacement while preserving run styling:

```bash
python3 skill/scripts/edit_pptx_text.py input.pptx replacements.json output.pptx
```

This is appropriate for corrections, terminology changes and small updates. It does **not** promise intelligent reflow when replacement text becomes much longer.

## 2. Rebuild

For structural improvement, inspect the source deck:

```bash
python3 skill/scripts/inspect_pptx.py input.pptx out/inspection.json
```

The Agent should then recover the argument/evidence, create a V1 semantic deck spec and rebuild with the normal pipeline. Rebuild is intentionally not a lossless clone; its goal is better structure and presentation quality.

## 3. Reference-based restyle

```bash
python3 skill/scripts/extract_style.py reference.pptx out/style-report.json
python3 skill/scripts/profile_from_reference.py out/style-report.json out/reference-profile.json reference-derived
node skill/scripts/build_deck.js deck.json out/restyled.pptx --profile out/reference-profile.json
```

The extracted profile is a starting point. Visual inspection remains required because arbitrary PPTX design contains details that cannot be fully reconstructed from theme tokens alone.
