# Feasibility review · V1.3

[English](FEASIBILITY_REVIEW.md) | [简体中文](FEASIBILITY_REVIEW.zh-CN.md)

2026-10-26. **V1.3 RELEASE READY WITH KNOWN LIMITATIONS.** This is the bounded engineering/product verdict. Publication additionally requires green CI, review of its actual Ubuntu renders, approved-commit packaging and remote verification; this document does not itself claim a published Release.

| Dimension | Status | Evidence and boundary |
|---|---|---|
| Architecture feasibility | PROVEN | Existing schemas, reasoning, compositions/profiles and one native PPTX engine extended; legacy examples retained |
| Product feasibility | PROVEN | Three recomputable analytical recipes and explicit semantic/narrative contracts; the agent supplies interpretation/design |
| Visual/aesthetic quality | PROVEN | Actual montage and representative full-size inspection; see hash-bound review and its limited scope |
| Installation feasibility | PROVEN | Unicode/spaced ZIP extraction, project npm/venv bootstrap, Doctor and example build/QA/render; final archive rechecked at release |
| Maintainability | PARTIAL | Shared calculations/formatting/readback; pinned native XML patches and the large benchmark/QA scripts need focused regression |
| Extensibility | PARTIAL | Semantic contracts are reusable; layout and native readback remain PPTX-specific |
| Multi-renderer readiness | PARTIAL | HTML renderer and renderer-neutral layout IR are not implemented |
| Open-source readiness | PROVEN | Apache-2.0, one Skill, complete-ZIP preflight, source-parity and immutable release workflow |
| Documentation accuracy | PROVEN | Bilingual product/installation/migration/quality docs distinguish implemented checks from Agent judgment and unsupported platforms |
| QA reliability | PROVEN | Native values/workbooks/units/series, source aliases, family/axis/paint corruption and metadata negatives are exercised; universal aesthetic/semantic correctness is not certified |

## Executed evidence

Frozen engine SHA256: `e183c3c162801781a1c69cc480dd53b49f805c2e571be5a9a0245cff5b45d854`. Full regression: 188 discovered, 187 passed, 1 opt-in integration skip, 0 failures (122 Node + 66 Python). Core tier: 172 discovered, 171 passed, 1 skip, 0 failures. The real clean-install/bootstrap journey is executed separately, rather than counting the skipped test as a pass. Legacy benchmark: 15 scenarios / 104 slides, all rendered, PASS_WITH_NOTES.

V1.3 chart matrix: 96 cases, 72 actual accepted renders and 24 expected rejections. Six native families, light/dark and eight edge-case categories are covered, with stacked/histogram supplements. Three same-input v1.2.1 comparisons use identical raw JSON; three 12-page theme galleries, a 5-page source ledger and 8 native relationship examples are generated. [Benchmark and actual comparison](BENCHMARKS_V1_3.md) · [independent visual record](evidence/v1.3/visual-review.json).

The source baseline is v1.2.1 commit `fb55b1cc92e52923027c2a5ad405d3ee92b42f25`; both versions use the same current locked host runtime. This is controlled source comparison, not historical Office replay. Original recipe layouts largely remain; curated gallery compositions are separate Agent-authored examples. A changed color is not evidence of automatic narrative reconstruction.

## Audit, repair and visual iteration

Independent review found and repaired output aliases that could overwrite a source; tiny/large numeric comparison and long-sum roundoff errors; currency/share-label mistakes; missing-line bridges; overwritten category labels; long-title context and relationship-copy errors. Native family/axis/paint corruption originally escaped generic QA; all three original mutation probes now correctly FAIL. Source-ledger periods and derivative hashes are reconciled against original bytes.

Full-size render inspection also found false zero-area gaps, empty single-point areas and negative labels overlapping categories. Unsupported area inputs now fail with explicit line/KPI/table alternatives. Magnitude-aware negative-axis padding preserves tiny real values; category labels stay outside negative bars. Actual rerenders were inspected. No source value was silently imputed, removed or changed to make a picture pass.

The final local visual verdict is PASS_WITH_NOTES: complete montages/contact sheets plus named full-size pages, not every page at full size. Dense tables suit read-ahead/appendix; close true-date markers can touch while alternating labels remain readable; overlapping areas are less useful than lines for exact comparison. The automated manifests retain VISUAL_QA=NOT_RUN; the separate Codex record supplies the actual reviewer judgment.

## Boundaries

Typed metrics validate declared meaning and formatting; explicit bindings share facts across text/KPI/table/chart. They are not a general source-extraction, causal-inference or statistical-significance engine. Narrative graphs flag declared coverage/exact redundancy; Agent review retains useful summary/detail and assesses decision relevance. JSON/IEEE754 is not arbitrary-precision accounting.

Six native chart families, stacking and explicit equal-bin histograms have bounded implementations. Missing/single-point areas and unsupported scatter/bubble/waterfall/combination charts are rejected. Dated timeline and bounded acyclic branch/swimlane/DAG use editable objects; cyclic flows and generic scheduling remain unsupported. Existing PPTX replacement is limited; lossless editing, HTML output and autonomous visual repair are not implemented.

The secure optional tier requires Python 3.11+ / Pillow 13; Python 3.9+ retains a Pillow-free core tier. Dependency advisories are a [dated snapshot](evidence/v1.3/dependency-security.json), not a promise of no unknown vulnerabilities. Complete ZIP preflight preserves the V1.2.1 static Doctor fix and checks code, instructions, metadata, paths, permissions and dependency declarations. It is not private-platform approval.

Local execution used Node 24.18, Python 3.14.4 / Pillow 13, LibreOfficeDev 26.8 alpha and Poppler 26.05 on Linux x86_64. CI supplies a separate Ubuntu render that is reviewed before release. Native Windows/macOS/ARM64 PowerPoint is NOT_RUN; company/Agensi upload/security is NOT_VERIFIED. GitHub Social Preview material is generated; applying the repository setting remains manual because the browser session was unavailable, despite verified CLI admin access.

Pro is a separate design deliverable outside public Core. Paid delivery, measured differentiation and marketplace execution are not established; $29 remains a pricing hypothesis. Final release commit, archive checksums and public verification are recorded in external Release evidence, avoiding circular self-hashes inside the installer.
