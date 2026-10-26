const HEX=/^[0-9A-Fa-f]{6}$/;

function hexToRgb(value) {
  const hex=String(value||'').replace(/^#/,'');
  if(!HEX.test(hex)) throw new Error(`Invalid hex color: ${value}`);
  return {r:parseInt(hex.slice(0,2),16),g:parseInt(hex.slice(2,4),16),b:parseInt(hex.slice(4,6),16)};
}
function rgbToHex(value) {
  const {r,g,b}=typeof value==='string'?hexToRgb(value):value;
  return [r,g,b].map(v=>Math.max(0,Math.min(255,Math.round(v))).toString(16).padStart(2,'0')).join('').toUpperCase();
}
function linear(channel) {
  const c=channel/255;
  return c<=.03928?c/12.92:((c+.055)/1.055)**2.4;
}
function relativeLuminance(value) {
  const {r,g,b}=hexToRgb(value);
  return .2126*linear(r)+.7152*linear(g)+.0722*linear(b);
}
function contrastRatio(a,b) {
  const la=relativeLuminance(a),lb=relativeLuminance(b);
  return (Math.max(la,lb)+.05)/(Math.min(la,lb)+.05);
}
function mix(a,b,amount) {
  const x=hexToRgb(a),y=hexToRgb(b);
  return rgbToHex({r:x.r+(y.r-x.r)*amount,g:x.g+(y.g-x.g)*amount,b:x.b+(y.b-x.b)*amount});
}
function ensureContrast(foreground,background,minimum) {
  if(contrastRatio(foreground,background)>=minimum) return rgbToHex(foreground);
  const black=contrastRatio('000000',background),white=contrastRatio('FFFFFF',background);
  const target=black>=white?'000000':'FFFFFF';
  let low=0,high=1,best=target;
  for(let i=0;i<24;i++) {
    const mid=(low+high)/2,candidate=mix(foreground,target,mid);
    if(contrastRatio(candidate,background)>=minimum){best=candidate;high=mid;} else low=mid;
  }
  return contrastRatio(best,background)>=minimum?best:target;
}
// Bounded, deterministic palette: related tones of the accent plus one neutral.
function chartPalette(accent,secondary,background,text) {
  const seeds=[accent,secondary,mix(accent,background,.5),mix(text,background,.45)];
  const palette=[];
  for(const seed of seeds) {
    let color=ensureContrast(seed,background,3);
    for(let attempt=1;palette.includes(color)&&attempt<=4;attempt++) {
      const toward=attempt%2?'FFFFFF':'000000';
      color=ensureContrast(mix(color,toward,.15*Math.ceil(attempt/2)),background,3);
    }
    palette.push(color);
  }
  return palette;
}

function labOf(value) {
  const {r,g,b}=hexToRgb(value);
  const x=(linear(r)*.4124+linear(g)*.3576+linear(b)*.1805)/.95047;
  const y=(linear(r)*.2126+linear(g)*.7152+linear(b)*.0722);
  const z=(linear(r)*.0193+linear(g)*.1192+linear(b)*.9505)/1.08883;
  const f=t=>t>.008856?Math.cbrt(t):7.787*t+16/116;
  return {L:116*f(y)-16,a:500*(f(x)-f(y)),b:200*(f(y)-f(z))};
}
function deltaE76(a,b) { const x=labOf(a),y=labOf(b); return Math.hypot(x.L-y.L,x.a-y.a,x.b-y.b); }
// Purpose-built categorical seeds (Okabe-Ito inspired) are separated from the brand accent.
function categoricalPalette(background) {
  const seeds=['0072B2','E69F00','009E73','CC79A7','D55E00','56B4E9','F0E442','7F7F7F'];
  const fallback=['000000','FFFFFF','FFFF00','00FFFF','FFE0B2','B2EBF2','C8E6C9','F8BBD0'];
  const chosen=[];
  for(const seed of [...seeds,...fallback]) {
    for(let attempt=0;attempt<28;attempt++) {
      const toward=attempt%2?'000000':'FFFFFF';
      const candidate=ensureContrast(attempt===0?seed:mix(seed,toward,.07*(1+Math.floor(attempt/2))),background,3);
      if(chosen.includes(candidate)) continue;
      const separated=chosen.every(other=>deltaE76(candidate,other)>=18||Math.abs(relativeLuminance(candidate)-relativeLuminance(other))*100>=10);
      if(separated) {chosen.push(candidate);break;}
    }
    if(chosen.length>=8) break;
  }
  if(chosen.length<4) throw new Error('Unable to construct four distinguishable categorical chart colors for this background');
  return chosen;
}

function deriveTokens(colors,background,styleTokens={}) {
  const dark=relativeLuminance(background)<.45;
  const text=ensureContrast(colors.text||'000000',background,4.5);
  const muted=ensureContrast(colors.muted||text,background,4.5);
  const accent=ensureContrast(colors.accent||text,background,3);
  const accentSoft=colors.accent_soft||colors.accentSoft||colors.panel||background;
  const surface=colors.panel||mix(background,text,.06);
  const divider=colors.line||mix(background,text,.2);
  const secondarySeed=colors.secondary_accent||colors.secondaryAccent||mix(accent,text,.55);
  const secondaryAccent=ensureContrast(secondarySeed,background,3);
  const neutral=ensureContrast(mix(text,background,.45),background,3);
  const accentPalette=chartPalette(accent,secondaryAccent,background,text);
  const categorical=categoricalPalette(background);
  const solidHeader=styleTokens.table_header==='solid';
  const headerFill=solidHeader?text:accentSoft;
  return {
    mode:dark?'dark':'light',
    background:rgbToHex(background),
    surface:rgbToHex(surface),
    text,
    muted,
    accent,
    accentSoft:rgbToHex(accentSoft),
    secondaryAccent,
    divider:rgbToHex(divider),
    chart:{
      background:rgbToHex(background),
      palette:categorical.slice(0,4),
      categorical,
      sequential:[ensureContrast(mix(background,text,.08),background,3),ensureContrast(accent,background,3)],
      diverging:[ensureContrast(dark?'56B4E9':'0072B2',background,3),ensureContrast(divider,background,3),ensureContrast(dark?'F87171':'D55E00',background,3)],
      labels:ensureContrast(muted,background,4.5),
      title:ensureContrast(text,background,4.5),
      dataLabel:ensureContrast(text,background,4.5),
      grid:ensureContrast(divider,background,1.2),
      highlight:accentPalette[0],
      accent:ensureContrast(accent,background,3),
      neutral,
    },
    table:{
      headerFill:rgbToHex(headerFill),
      headerText:ensureContrast(solidHeader?background:text,headerFill,4.5),
      bodyFill:rgbToHex(background),
      bodyText:ensureContrast(text,background,4.5),
      bandFill:rgbToHex(surface),
      border:rgbToHex(divider),
    },
    status:{
      positive:ensureContrast(dark?'34D399':'047857',background,4.5),
      negative:ensureContrast(dark?'F87171':'B91C1C',background,4.5),
      warning:ensureContrast(dark?'FBBF24':'B45309',background,4.5),
      neutral:muted,
    },
    image:{
      overlay:dark?'000000':'FFFFFF',
      text:ensureContrast(dark?'FFFFFF':'111827',dark?'000000':'FFFFFF',4.5),
    },
  };
}

function resolveStyle(profile, spec = {}) {
  const colors = { ...profile.colors, ...spec.colors };
  const font = { ...profile.font, ...spec.font };
  const tokens = { ...profile.style, ...spec.style };
  const dense = ['high', 'medium-high'].includes(tokens.density);
  const background = spec.background || profile.background || 'FFFFFF';
  const styleTokens = {
    title_rule: 'line', table_header: 'soft', table_banding: false,
    metric_style: 'open', chart_grid: 'light', cover_treatment: 'editorial',
    ...tokens,
  };
  return {
    profileId: profile.id,
    canvas: profile.canvas || 'wide',
    background,
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
    style: styleTokens,
    tokens: deriveTokens(colors,background,styleTokens),
    layout: {
      marginX: Number(tokens.margin_x || (dense ? .65 : .78)),
      titleY: .55, dividerY: 1.48, contentTop: 1.85,
      bodySize: Number(font.body_size || 18),
    },
  };
}
module.exports = { resolveStyle, deriveTokens, contrastRatio, relativeLuminance, hexToRgb, rgbToHex, mix, ensureContrast, categoricalPalette, deltaE76 };
