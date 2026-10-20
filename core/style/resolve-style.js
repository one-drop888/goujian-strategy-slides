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
  const target=relativeLuminance(background)<.45?'FFFFFF':'000000';
  let low=0,high=1,best=target;
  for(let i=0;i<24;i++) {
    const mid=(low+high)/2,candidate=mix(foreground,target,mid);
    if(contrastRatio(candidate,background)>=minimum){best=candidate;high=mid;} else low=mid;
  }
  return best;
}
function rgbToHsl(value) {
  const {r,g,b}=hexToRgb(value),rn=r/255,gn=g/255,bn=b/255;
  const max=Math.max(rn,gn,bn),min=Math.min(rn,gn,bn),l=(max+min)/2;
  if(max===min) return [0,0,l];
  const d=max-min,s=l>.5?d/(2-max-min):d/(max+min);
  let h=max===rn?(gn-bn)/d+(gn<bn?6:0):max===gn?(bn-rn)/d+2:(rn-gn)/d+4;
  return [h/6,s,l];
}
function hslToHex(h,s,l) {
  function hue(p,q,t){if(t<0)t+=1;if(t>1)t-=1;if(t<1/6)return p+(q-p)*6*t;if(t<1/2)return q;if(t<2/3)return p+(q-p)*(2/3-t)*6;return p;}
  if(s===0) return rgbToHex({r:l*255,g:l*255,b:l*255});
  const q=l<.5?l*(1+s):l+s-l*s,p=2*l-q;
  return rgbToHex({r:hue(p,q,h+1/3)*255,g:hue(p,q,h)*255,b:hue(p,q,h-1/3)*255});
}
function rotateHue(value,degrees) {
  const [h,s,l]=rgbToHsl(value);
  return hslToHex((h+degrees/360)%1,s,l);
}
function uniquePalette(seeds,background,text) {
  const dark=relativeLuminance(background)<.45,palette=[];
  for(const seed of seeds) {
    let color=ensureContrast(seed,background,3),attempt=0;
    while(palette.includes(color)) {
      color=ensureContrast(mix(color,dark?'FFFFFF':'000000',.1+attempt*.06),background,3);
      attempt++;
    }
    palette.push(color);
  }
  if(palette.length<4) palette.push(ensureContrast(mix(text,background,.45),background,3));
  return palette;
}

function deriveTokens(colors,background,styleTokens={}) {
  const dark=relativeLuminance(background)<.45;
  const text=ensureContrast(colors.text||'000000',background,4.5);
  const muted=ensureContrast(colors.muted||text,background,4.5);
  const accent=ensureContrast(colors.accent||text,background,3);
  const accentSoft=colors.accent_soft||colors.accentSoft||colors.panel||background;
  const surface=colors.panel||mix(background,text,.06);
  const divider=colors.line||mix(background,text,.2);
  const secondarySeed=colors.secondary_accent||colors.secondaryAccent||rotateHue(accent,180);
  const secondaryAccent=ensureContrast(secondarySeed,background,3);
  const neutral=ensureContrast(mix(text,background,.45),background,3);
  const palette=uniquePalette([
    accent,
    secondaryAccent,
    mix(accent,text,.45),
    mix(secondaryAccent,text,.45),
  ],background,text);
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
      palette,
      labels:ensureContrast(muted,background,4.5),
      title:ensureContrast(text,background,4.5),
      dataLabel:ensureContrast(text,background,4.5),
      grid:ensureContrast(divider,background,1.2),
      highlight:palette[0],
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
module.exports = { resolveStyle, deriveTokens, contrastRatio, relativeLuminance };
