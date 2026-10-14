# Quality Gate

A deck is `READY` only when **content, evidence, engineering and rendered visual review** are acceptable.

## Content gate
- Audience, decision and storyline are explicit or inferable.
- Every content page has one dominant message.
- Action titles are used where evidence supports them.
- Storyline progresses rather than repeats.
- Management conclusion is separated from raw evidence.

## Evidence gate
- No invented facts, quotes or sources.
- Decision-relevant charts include unit, period and source when available.
- Assumptions are labeled as assumptions.
- VOC quotes are not presented as prevalence without quantitative support.
- Sample/method limitations are visible for research claims.

## Visual gate
- No unintended overflow or peer overlap.
- Body text remains readable in presentation mode.
- Alignment, spacing and hierarchy are consistent.
- Visual type matches information intent.
- Repetition is intentional, not template laziness.
- Charts can be interpreted without oral explanation.

## Engineering gate
- PPTX opens successfully.
- Text and major chart/shape elements remain editable.
- Fonts are available or substitution is explicitly reported.
- Render → montage → visual inspection has been run for final delivery when the environment supports rendering.

## Status
- `PASS`: automated checks passed; no blocking issue found.
- `PASS_WITH_NOTES`: usable, with explicit limitations/warnings.
- `FAIL`: evidence, layout or file-integrity issue blocks delivery.
