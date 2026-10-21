# V1.2 visual previews

Every image in this directory is composed from **actual PNG renders** produced by LibreOfficeDev 26.8.0.0 alpha0 from the V1.2 native PPTX files. No slide was redrawn, mocked up or generated as an image by a model. The surrounding labels, borders and footers are documentation composition only; all slide content inside each card is the untouched render.

Source decks are the synthetic fixtures in the optional showcase (`out/v1.2-showcase`, built by `npm run showcase`). They are not included in the installer ZIP and are not committed to git. All content is synthetic or project-authored; no real company, customer or financial data appears.

| Preview | Size | Source renders |
|---|---|---|
| `hero.png` | 1600×900 | executive cover; Q4 page 2; multimodal page 3 |
| `q4-before-after.png` | 1920×720 | pre-fix round-3 dark render; current dark theme page 2 |
| `multimodal-before-after.png` | 1920×720 | pre-fix round-3 chart page; current chart page 3 |
| `theme-variants.png` | 1920×640 | light, brand-blue and dark page 2 of the same Q4 plan |
| `scenario-previews.png` | 1920×960 | six representative pages across five cases |
| `social-preview-1280x640.png` | 1280×640 | dark theme page 2 plus repository identity |

## Source render hashes

SHA-256 of the exact PNGs used for composition:

| Render | SHA-256 |
|---|---|
| `out/v1.2-showcase/decks/executive-incomplete-business-render/slide-1.png` | `a2951391c9c6d447f453972268fe8e0e11cb612debca7524c753de42aee51d8c` |
| `out/v1.2-showcase/decks/q4-six-actions-render/slide-2.png` | `c24aaa63a2d3502e4f1a7090210f259fbb5d3adfd16a9a7227e09c00fe690887` |
| `out/v1.2-showcase/decks/multimodal-consolidation-render/slide-3.png` | `a0c911dca95ce46db9ccfe8949a1ec16f4c390f7f2e6deb8937d2dd64f8040ad` |
| `out/v1.2-showcase/before/q4-summary-theme-dark-before.png` | `dbd785b78c5a6ee0b298d1a8afbacffe3eb17dfdc871753d94c384c4fc73f3c9` |
| `out/v1.2-showcase/theme-variants/theme-dark/slide-2.png` | `470d51248c8844f74048e07358a0a84409730ecef25eae285136956f41662ffa` |
| `out/v1.2-showcase/before/multimodal-chart-page3-before.png` | `85a3a687885b120b98d122a9e7d5a598fe96d61e72344e7a12fbf909b4bfc578` |
| `out/v1.2-showcase/theme-variants/theme-light/slide-2.png` | `c24aaa63a2d3502e4f1a7090210f259fbb5d3adfd16a9a7227e09c00fe690887` |
| `out/v1.2-showcase/theme-variants/theme-brand-blue/slide-2.png` | `3cc9fb9e7bdcb0695d3fc33d2eef1fa1ff72d462d95cb29587a7ece58b024035` |
| `out/v1.2-showcase/decks/executive-incomplete-business-render/slide-3.png` | `9db61f79ca5a19a2fdea7798c988e51ad671316f011ad5f59dd62fec54aeb3a4` |
| `out/v1.2-showcase/decks/q4-six-actions-render/slide-3.png` | `94a32a422d6c8449f0acc1eb3a35f138379349221565a63e96998540f309b0bb` |
| `out/v1.2-showcase/decks/multimodal-consolidation-render/slide-6.png` | `a7366bcec644b5a4918828b77f9394bacff722cb06e2d99092ae3afdeb0c1b18` |
| `out/v1.2-showcase/dark-chart-types/render/slide-5.png` | `dd942c33e093fb41b536450af5a20335939155bcfa6dbc7a9d495ef1110c24c3` |
| `out/v1.2-showcase/long-title/render/slide-2.png` | `a23e27bbdb5fac2d0bbf47731fd1541680490d1f771d08217e10110832eaa600` |

If any fixture or engine source changes, these previews must be rebuilt from the new renders. They are illustrations of the built bytes, not a visual approval of every page.

## Status

Final independent full-size visual QA by Codex is **pending** and occurs after the writer stops. These previews do not claim that review. The previews show actual pixels; they are not editable and carry no source provenance beyond the render and input hashes recorded in the showcase manifests.
