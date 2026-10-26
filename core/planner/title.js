const {execFileSync}=require('child_process');
const path=require('path');
const cache=new Map(),glyphs=new Map();
function measure(text,font,size,bold=true) {
  const key=JSON.stringify([text,font,size,bold]);
  if(cache.has(key))return cache.get(key);
  let result;
  try {
    const fontKey=JSON.stringify([font,size,bold]), known=glyphs.get(fontKey)||{};
    const missing=[...new Set([...text].filter(c=>known[c]===undefined))].join('');
    if(missing)Object.assign(known,JSON.parse(execFileSync('python3',[path.join(__dirname,'../style/measure_text.py')],{input:JSON.stringify({text:missing,font,size,bold}),encoding:'utf8',stdio:['pipe','pipe','ignore'],timeout:5000})).advances);
    glyphs.set(fontKey,known);result={width:[...text].reduce((sum,c)=>sum+known[c],0),method:'pillow-glyph-advances-with-4pct-safety'};
  }
  catch {
    // shortcut: conservative glyph classes when font measurement is unavailable; require render review.
    const width=[...text].reduce((sum,c)=>sum+(/\s/.test(c)?.34:/[ilI.,:;'!|]/.test(c)?.3:/[MW@#]/.test(c)?.95:/[^\x00-\xff]/.test(c)?1.05:.62),0)*size/72;
    result={width,method:'conservative-approximation'};
  }
  cache.set(key,result);return result;
}
function titleTokens(text) {
  return text.match(/\d{4}[-/]\d{2}(?:[-/]\d{2})?(?!\d)|[+-]?\d+(?:[.,]\d+)*(?:\s?(?:%|％|pp|万元|亿元|万|亿|元|单|天|人|个|次|小时|分钟))?|[A-Za-z0-9]+(?:[-'.][A-Za-z0-9]+)*|[^A-Za-z0-9]/gu)||[];
}
function wrap(text,font,size,width) {
  text=String(text??'');
  if(text.includes('\n'))return text.split('\n').flatMap(p=>wrap(p,font,size,width));
  const lines=[];let current=[];
  for(const token of titleTokens(text)) {
    if(current.length&&measure(current.join('')+token,font,size).width>width) {
      if(token.length===1&&'，。；：！？、）】》”’.,;:!?%％)]/'.includes(token)) {
        const tail=current.pop();if(current.length)lines.push(current.join('').trim());current=[tail,token];
      } else {lines.push(current.join('').trim());current=[token.trimStart()];}
    } else current.push(token);
  }
  if(current.length)lines.push(current.join('').trim());return lines.length?lines:[''];
}
function balancedWrap(text,font,size,width) {
  text=String(text??'');
  if(text.includes('\n'))return text.split('\n').flatMap(p=>balancedWrap(p,font,size,width));
  const lines=wrap(text,font,size,width);if(lines.length<2)return lines;
  let low=width/lines.length,high=width,best=lines;
  for(let i=0;i<16;i++){
    const mid=(low+high)/2,candidate=wrap(text,font,size,mid);
    if(candidate.length<=lines.length){best=candidate;high=mid;}else low=mid;
  }
  return best;
}
function resolveTitle(s,font,width) {
  const original=s.title||'',title=(s.title_short||original).replace(/\s*\n\s*/g,' ');
  const subtitle=s.subtitle||(s.title_short?original:'');
  const base=font.titleSize;
  const floor=Math.min(base,Math.max(base>=36?28:22,font.titleMinSize||0));
  const subtitleSize=Math.min(font.bodySize,17);
  const subtitleLines=subtitle?wrap(subtitle,font.cjk,subtitleSize,width):[];
  if(subtitleLines.length>3)throw Error('Subtitle exceeds three readable lines; move context into the body');
  if(subtitleLines.some(t=>measure(t,font.cjk,subtitleSize).width>width+.001))throw Error('An unbreakable subtitle token exceeds the available width');
  const subtitleH=subtitleLines.length?subtitleLines.length*subtitleSize/72*1.3+.04:0;
  const candidates=[];
  const candidate=(size,lines)=>{
    const widths=lines.map(t=>measure(t,font.cjk,size).width);
    const h=lines.length*size/72*1.28+.06,gap=Math.max(.15,size/72*.42);
    const titleY=.55,subtitleY=titleY+h+.13,dividerY=(subtitleH?subtitleY+subtitleH:titleY+h)+gap;
    const bodyTop=Math.max(1.65,dividerY+gap);
    return {size,lines,line_widths:widths,h,gap,titleY,subtitleY,dividerY,bodyTop,
      body_height:6.45-bodyTop,feasible:lines.length<=2&&widths.every(w=>w<=width+.001)};
  };
  const sizes=[];
  for(let size=base;size>=floor;size-=1)sizes.push(size);
  if(sizes.at(-1)!==floor)sizes.push(floor);
  let chosen;
  for(const size of sizes) {
    const option=candidate(size,[title]);candidates.push(option);
    if(option.feasible){chosen=option;break;}
  }
  if(!chosen) {
    for(const size of sizes) {
      const option=candidate(size,balancedWrap(title,font.cjk,size,width));candidates.push(option);
      if(option.feasible){chosen=option;break;}
    }
  }
  if(!chosen)throw Error('Title cannot fit safely at the readable floor; use title_short + subtitle or split the slide (unbreakable token or excess content)');
  const strategy=(s.title_short?'author-rewrite':'original')+(chosen.size<base?'-safe-font-adjustment':'');
  return {original,title,subtitle,...chosen,subtitleLines,subtitleH,strategy,minimum_size:floor,
    layout_strategy:chosen.lines.length===1?'measured-one-line':'balanced-two-line',
    candidates:candidates.map(c=>({size:c.size,lines:c.lines.length,max_width:Math.max(...c.line_widths),body_height:c.body_height,feasible:c.feasible})),
    decision:chosen.lines.length===1?'Largest readable one-line candidate that preserves the text':'No readable single-line candidate fits; balanced two-line fallback',
    measurement:measure(title,font.cjk,chosen.size).method};
}
module.exports={resolveTitle,measure,wrap,balancedWrap,titleTokens};
