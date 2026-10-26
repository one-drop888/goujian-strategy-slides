# V1.3 synthetic source inputs

These files are project-authored synthetic fixtures for reproducible rendering and QA benchmarks. They are byte-identical copies of `skill/analytics/*.json` at the V1.3 fixture freeze. They contain no company data, customer records, personal data, or third-party assets.

| Source ID | File | Format | Synthetic | Rights | Review |
| --- | --- | --- | --- | --- | --- |
| synthetic-business-performance | `business-performance.json` | JSON | yes | Project-authored / Apache-2.0 | NOT_RUN |
| synthetic-sales-conversion | `sales-conversion.json` | JSON | yes | Project-authored / Apache-2.0 | NOT_RUN |
| synthetic-project-analytics | `project-analytics.json` | JSON | yes | Project-authored / Apache-2.0 | NOT_RUN |

`source-ledger.json` records the SHA-256 of each input, the declared period, the measurement basis, and the review status. The declared period mirrors the raw reporting window; earlier history appears only in explicitly dated trend or previous_month/previous_year fields (for example the business trend from 2026-04 to 2026-09 alongside the 2026-09 snapshot). The ledger is an inventory, not proof of source authenticity. Rights and access review remain with the release owner.

The same raw bytes are used for the V1.2.1 baseline and the current V1.3 comparison. Do not edit these files when reproducing a comparison; the benchmark records their hashes.
