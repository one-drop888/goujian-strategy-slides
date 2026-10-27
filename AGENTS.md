# Agent instructions

This repository ships the Goujian Strategy Slides skill and its deterministic
release pipeline.

- Follow `docs/RELEASE_SECURITY_GATE.md`. It is the mandatory canonical security
  gate for packaging, scanning, evidence and release approval.
- Never bypass, weaken or remove the skill-package security scan, the exact
  review ledger, the complete receipt check set or the typed publish approval.
- Do not edit `security/review-ledger.json` to approve findings. Only an
  independent review may add exact, content-bound approvals.
- Keep exactly one `SKILL.md` in the repository and in every archive.
- Build archives only with `scripts/package_runtime.py`; never hand-edit a ZIP.
- Live advisory checks must use public coordinates and fail closed on service
  errors. Do not weaken them to make a run green.
- Keep the inert negative-control fixture generated in a private temporary
  directory via `scripts/negative_skill_fixture.py`; never check it in.
