# v1.3.2 package separation: independent review

Codex checkpoint, 2026-10-28. Implementation reviewed at
`a01bc9f68cb2fc8bf1405990f91d78791e7e3496`. This is a bounded code and
finding review, not a release approval or company-platform certification.

## Observed failure and engineering change

The official v1.3.1 Runtime archive was independently hashed as
`7ee0d15488368a876ac2624546f72a13de8bdf01f322ed1055bb8c099d67b3dd`.
Its three literal `exec(` occurrences are in defensive regex source at
`scripts/security_preflight.py:90,91,714`. No corresponding Python builtin
execution was found. Three company messages cannot establish a one-to-one
mapping without the server's actual rule and location evidence.

The new Runtime removes exactly four Source-only members: the packager, the
release preflight, and the hostile-source plan/document negative fixture.
They remain in the Source distribution with their tests. Runtime operational
scripts, QA, resources and documented production commands remain; `package`
and `preflight` are explicitly Source commands. The manifest now declares 185
members, plus the mapped `package.json` (186 ZIP members).

Compared with pre-task main `2640a325f48c4a47b2a8c20ec94275e223e5e79e`,
`core/` and `skill/` implementation bytes are unchanged. The dependency lock
is identical after removing only its two version fields. This supports a
small implementation change; it does not substitute for actual-package
regression and visual acceptance.

## Exact finding adjudication

Actual candidate ZIP scans used Cisco Skill Scanner 2.3.1, the unchanged
low-noise policy and fingerprint, and the pinned isolated tool environment.
The Runtime raw report contains 4 CRITICAL and 26 LOW findings; Source contains
34 CRITICAL, 4 HIGH, 7 MEDIUM and 147 LOW. The first scans deliberately failed
closed with stale exact reviews after the root Skill version/install wording
changed. They are not recorded as successful scans.

Codex reviewed the actual 38 HIGH/CRITICAL Source locations and the Skill diff:

- 33 locations have exactly the previously reviewed file bytes. Their process
  calls remain explicit local argv calls, not shell-string execution. Runtime
  calls retain actual font measurement, image preparation, font discovery and
  capability checks. They require a trusted host, PATH and installed skill;
  this review is not an OS sandbox claim.
- Three defensive preflight regex literals moved to lines 102, 103 and 726.
  Their text is byte-identical to the old locations. All 26 executable risk
  detector AST nodes remain identical; no detector was weakened or hidden.
- Two negative-test string literals moved to lines 413 and 437. Their text
  remains byte-identical and the tests pass the samples to the analyzer; they
  do not execute those hostile samples.
- The new Source-only installed-runtime harness runs documented production
  CLIs with argv lists, retains failed artifacts, rejects a wrong baseline hash
  before opening its ZIP, and does not inject developer code into Runtime.
  It is test infrastructure, not a new runtime mechanism.

The ledger rebinds these exact locations to the reviewed file hashes and root
Skill hash. It preserves raw severity and the earlier rationale; prior
approvals remain in Git history. There are no wildcard exclusions, severity
changes, scanner setting changes or new PDF approvals. The final archive must
run the complete gate again against its own approved commit.

MEDIUM findings remain visible: Source advisory requests use public package
coordinates; inherited process environments are for local child execution,
not an observed network sink. Binary PNG signature matches do not by
themselves establish executable prompt instructions. The generic undeclared
network finding is not a declaration that installation or optional tool setup
is network-free. These are retained triage, not universal safety assurances.

## Independent checks and limits

Codex directly reran 125 focused harness/parity/preflight/workflow tests,
32 harness tests after the final caller fix, and the deterministic packager
checks. Source input overwrite protection, installed payload canonical-byte
checks, frozen v1.3.1 preflight and wrong-digest rejection are independently
covered. Full candidate Source and Unicode Runtime installation, native-object,
data, image/font and rendered-pixel equivalence are separate acceptance steps;
their actual reports must govern release, not this checkpoint.

The old company upload is **FAIL**. The new candidate company upload/security
is **NOT_VERIFIED**. JavaScript behavioral dataflow, model semantic security
analysis and native Windows/macOS PowerPoint acceptance are not established by
this review. Public CI or Cisco approval cannot substitute for company review.

## CI portability follow-up

PR #5 run `40705348100` at `fab8521` failed on Python 3.9 and 3.11 because
the new test pinned `ast.dump` serialization from Python 3.14. Those failures
remain in history; the security gate itself passed. Repair `7c0b62d` changes
only the test invariant to the exact source blocks of the same 26 AST-selected
detectors. Codex independently parsed the SHA-locked official v1.3.1 ZIP and
the current file on Python 3.10.22 and 3.14.4: all 26 blocks are byte-identical
and hash to `f75f32ee543e11f1a7cd656d921114529b16aa8951925c34e3fcadaa6493e680`.
Changed-literal and missing-node probes are rejected. No detector, production
code, runtime payload, scanner setting or PDF policy changes.

Codex reviewed the test diff and the two unchanged inert HIGH string literals,
now at lines 455 and 479, and rebound only those two ledger entries to the new
test-file hash. The other 36 exact reviews are unchanged. This is not an
approval to skip the real Python 3.9/3.11 CI rerun; all required checks must
pass at the repaired commit before merge. Historical Phase 1b test counts
remain historical, not retroactively increased.

The repaired run `40707924666` subsequently passed both older-Python tiers,
security and historical parity, then exposed a receipt-format defect: the
extracted Source ZIP's tests succeeded, but a TAP-only output assertion rejected
Node 24's Unicode spec reporter. Repair `c20a386` captures the real npm and tee
exit codes immediately, rejects either failure and binds both codes to the
existing receipt. Codex reviewed the capture and failure probes, reran 28 tests
on Python 3.10 and 3.14, and strengthened the positive receipt fixture to contain
only the actual Unicode reporter format. Raw test logs are retained in both
workflow artifacts and hashed as bytes, so their recorded digest can be
independently reproduced. Neither source-test execution nor any safety gate is
removed. Runtime bytes, the renderer and all 38 exact reviews remain unchanged;
the corrected full CI and Release rehearsal are still required.
