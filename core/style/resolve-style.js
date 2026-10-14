function resolveStyle(profile, spec = {}) {
  const colors = { ...profile.colors, ...spec.colors };
  const font = { ...profile.font, ...spec.font };
  const tokens = { ...profile.style, ...spec.style };
  const dense = ['high', 'medium-high'].includes(tokens.density);
  return {
    profileId: profile.id,
    canvas: profile.canvas || 'wide',
    background: spec.background || profile.background || 'FFFFFF',
    font: {
      latin: font.latin || 'Noto Sans', cjk: font.cjk || 'Noto Sans CJK SC',
      titleSize: Number(font.title_size || 27), bodySize: Number(font.body_size || 18),
      tableSize: Number(tokens.table_size || (dense ? 14 : 16)),
      chartSize: Number(tokens.chart_size || (dense ? 12 : 14)),
    },
    colors: {
      text: colors.text || '172B3A', muted: colors.muted || '526373',
      accent: colors.accent || '176B87', accentSoft: colors.accent_soft || 'EAF3F7',
      panel: colors.panel || 'F5F7F9', line: colors.line || 'D9E1E7',
    },
    style: {
      title_rule: 'line', table_header: 'soft', table_banding: false,
      metric_style: 'open', chart_grid: 'light', cover_treatment: 'editorial',
      ...tokens,
    },
    layout: {
      marginX: Number(tokens.margin_x || (dense ? .65 : .78)),
      titleY: .55, dividerY: 1.48, contentTop: 1.85,
      bodySize: Number(font.body_size || 18),
    },
  };
}
module.exports = { resolveStyle };
