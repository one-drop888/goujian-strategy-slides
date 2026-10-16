# Custom profiles

Use a built-in id, a direct JSON path, or directories in `PRESENTATION_PROFILE_DIRS` (OS path delimiter: colon on POSIX, semicolon on Windows). Relative `extends` paths resolve from the child profile; built-in ids are also accepted. Inheritance deep-merges and rejects cycles.

```json
{
  "id": "my-executive",
  "extends": "executive-clean",
  "font": { "cjk": "Noto Sans CJK SC", "body_size": 19 },
  "colors": { "accent": "2457C5", "accent_soft": "EEF3FF" },
  "style": { "margin_x": 0.8, "title_rule": "accent", "table_header": "solid" }
}
```

```bash
node skill/scripts/build_deck.js deck.json out/custom.pptx --profile my-profile.json
```

Real renderer tokens:

| Token | Values / effect |
|---|---|
| `font.latin`, `font.cjk`, `font.preferred`, `fallback_latin`, `fallback_cjk` | Requested/preferred script families and fallback arrays; installed candidates resolve when Fontconfig is available; no embedding |
| `font.title_size`, `font.body_size` | Presentation title/body size; some diagram labels use bounded explicit sizes |
| `style.density` | Default spacing category; explicit `margin_x` takes precedence |
| `style.margin_x` | Horizontal margin in inches |
| `style.title_rule` | `line`, `accent`, `none` |
| `style.table_header` | `soft`, `solid` |
| `style.table_banding` | Boolean, alternating row background |
| `style.table_size`, `style.chart_size` | Table and chart type sizes |
| `style.metric_style` | `open`, `panel` |
| `style.chart_grid` | `light`, `none` |
| `style.cover_treatment` | `editorial`, `band` |
| `style.image_gap`, `image_caption_size`, `image_border` | Image gutter (inches), caption size (pt), `line`/`none` border |
| `colors` | `text`, `muted`, `accent`, `accent_soft`, `panel`, `line`; six-digit hex |

Only `canvas: "wide"` is supported. V1.1 images use real gutter/caption/border tokens. There is no gradient engine. Built-in ids resolve first, followed by the spec directory's `profiles/` and root, configured search directories, then explicit paths. Omitted ids use the default; unknown explicit ids fail. The 15 built-ins form related design families, not 15 unrelated art directions. Test a custom profile with titles, images, tables, charts and mixed Chinese/English text before adopting it.
