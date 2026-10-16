const {execFileSync}=require('child_process');
let inventory;
function resolveFonts(font) {
  if(inventory===undefined) {
    try {inventory=new Set(execFileSync('fc-list',[':','family'],{encoding:'utf8',timeout:5000}).split(/[\n,]/).map(s=>s.trim().toLowerCase()));}
    catch {inventory=null;}
  }
  const report=[]; const resolved={...font};
  for(const script of ['latin','cjk']) {
    const requested=font.preferred?.[script]||font[script];
    const candidates=[requested,...(font[`fallback_${script}`]||[]),...(script==='cjk'?['Noto Sans CJK SC','Microsoft YaHei','PingFang SC']:['Noto Sans','Aptos','Arial','DejaVu Sans'])];
    let found=inventory?candidates.find(f=>inventory.has(f.toLowerCase())):null;
    if(inventory&&!found) {
      try {
        const fallback=execFileSync('fc-match',['-f','%{family}',script==='cjk'?'sans-serif:lang=zh-cn':'sans-serif:lang=en'],{encoding:'utf8',timeout:3000}).split(',')[0].trim();
        if(inventory.has(fallback.toLowerCase()))found=fallback;
      } catch {}
    }
    resolved[script]=found||requested;
    report.push({script,requested,resolved:resolved[script],substituted:!!found&&found!==requested,status:found?'PROVEN':'UNAVAILABLE'});
  }
  return {font:resolved,report};
}
module.exports={resolveFonts};
