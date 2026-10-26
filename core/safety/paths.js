const fs=require('fs');
const path=require('path');

function canonicalPath(target) {
  const resolved=path.resolve(target),suffix=[];
  let current=resolved;
  while(true) {
    try {
      const real=fs.realpathSync.native(current);
      return path.join(real,...suffix.reverse());
    } catch {
      const parent=path.dirname(current);
      if(parent===current) return resolved;
      suffix.push(path.basename(current));
      current=parent;
    }
  }
}

function sameFile(left,right) {
  if(canonicalPath(left)===canonicalPath(right)) return true;
  try {
    const a=fs.statSync(left),b=fs.statSync(right);
    return a.dev===b.dev&&a.ino===b.ino;
  } catch { return false; }
}

function assertNotInput(target,label,inputs) {
  for(const input of inputs||[]) {
    if(input&&sameFile(target,input)) throw new Error(`${label} must not overwrite input ${input}`);
  }
  return path.resolve(target);
}

function assertDistinctOutputs(outputs) {
  const entries=outputs.filter(Boolean).map(({path:target,label})=>({label,target,canonical:canonicalPath(target)}));
  for(let i=0;i<entries.length;i++) for(let j=i+1;j<entries.length;j++) {
    if(entries[i].canonical===entries[j].canonical||sameFile(entries[i].target,entries[j].target)) {
      throw new Error(`${entries[i].label} and ${entries[j].label} must be different paths`);
    }
  }
  return entries;
}

module.exports={canonicalPath,sameFile,assertNotInput,assertDistinctOutputs};
