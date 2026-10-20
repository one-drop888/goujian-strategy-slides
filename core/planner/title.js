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
function wrap(text,font,size,width) {
  text=String(text??'');
  if(text.includes('\n'))return text.split('\n').flatMap(p=>wrap(p,font,size,width));
  const lines=[];let current='';
  for(const token of text.match(/[A-Za-z0-9]+(?:[-'.][A-Za-z0-9]+)*|[^A-Za-z0-9]/gu)||[]) {
    if(current&&measure(current+token,font,size).width>width) {
      const tail=current.match(/^(.*?)([A-Za-z0-9]+|.)$/u);
      if(/^[，。；：！？、）】》”’.,;:!?)]$/.test(token)&&tail&&tail[1]){lines.push(tail[1].trim());current=tail[2]+token;}
      else {lines.push(current.trim());current=token.trimStart();}
    }
    else current+=token;
  }
  if(current)lines.push(current.trim());return lines.length?lines:[''];
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
  const original=s.title||'';
  let title=(s.title_short||original).replace(/\s*\n\s*/g,' '),subtitle=s.subtitle||'';
  let strategy=s.title_short?'author-rewrite':'original';
  const base=font.titleSize,minimum=base*.92;
  if(s.title_short&&!subtitle)subtitle=original;
  let size=base;
  if(measure(title,font.cjk,size).width>width && measure(title,font.cjk,minimum).width<=width){size=minimum;strategy+='-safe-font-adjustment';}
  let lines=wrap(title,font.cjk,size,width);
  if(lines.length===2) {
    // Balance by measured width, preserving every character and word.
    const tokens=title.match(/[A-Za-z0-9]+|[^A-Za-z0-9]/gu)||[];let best=null;
    for(let i=1;i<tokens.length;i++){
      const a=tokens.slice(0,i).join('').trim(),b=tokens.slice(i).join('').trim();
      const wa=measure(a,font.cjk,size).width,wb=measure(b,font.cjk,size).width;
      if(wa<=width&&wb<=width&&(!best||Math.abs(wa-wb)<best.score))best={lines:[a,b],score:Math.abs(wa-wb)};
    }
    if(best)lines=best.lines;
  }
  if(lines.length>2)throw Error('Title needs an explicit title_short + subtitle; it cannot fit safely in two lines');
  if(lines.some(t=>measure(t,font.cjk,size).width>width+.001))throw Error('An unbreakable title token exceeds the available width; supply a shorter title_short');
  const subtitleLines=subtitle?wrap(subtitle,font.cjk,Math.min(font.bodySize,17),width):[];
  if(subtitleLines.length>3)throw Error('Subtitle exceeds three readable lines; move context into the body');
  if(subtitleLines.some(t=>measure(t,font.cjk,Math.min(font.bodySize,17)).width>width+.001))throw Error('An unbreakable subtitle token exceeds the available width');
  const h=lines.length*size/72*1.28+.06;
  const subtitleH=subtitleLines.length?subtitleLines.length*Math.min(font.bodySize,17)/72*1.3+.04:0;
  const gap=Math.max(.15,size/72*.42);
  const titleY=.55,subtitleY=titleY+h+.13,dividerY=(subtitleH?subtitleY+subtitleH:titleY+h)+gap;
  return {original,title,subtitle,lines,line_widths:lines.map(t=>measure(t,font.cjk,size).width),subtitleLines,size,h,subtitleH,titleY,subtitleY,dividerY,bodyTop:Math.max(1.65,dividerY+gap),gap,strategy,measurement:measure(title,font.cjk,size).method};
}
module.exports={resolveTitle,measure,wrap,balancedWrap};
