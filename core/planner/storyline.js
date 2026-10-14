const fs = require('fs');
const path = require('path');
function load(repoRoot) {
  return JSON.parse(fs.readFileSync(path.join(repoRoot,'skill','storylines','registry.json'),'utf8')).storylines;
}
function chooseStoryline(text='', repoRoot=path.resolve(__dirname,'../..')) {
  const q=String(text).toLowerCase();
  let best={id:'executive-business-review',score:0};
  for(const s of load(repoRoot)){
    const score=(s.triggers||[]).reduce((n,t)=>n+(q.includes(String(t).toLowerCase())?1:0),0);
    if(score>best.score) best={id:s.id,score};
  }
  return best.id;
}
module.exports={chooseStoryline};
