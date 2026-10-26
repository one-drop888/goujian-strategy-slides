const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('fs'),path=require('path'),os=require('os'),{spawnSync}=require('child_process');
const {assertDistinctOutputs}=require('../core/safety/paths');
const root=path.resolve(__dirname,'..'),bytes=fs.readFileSync(path.join(root,'skill/analytics/business-performance.json'));
for(const kind of ['symlink','hardlink']) for(const suffix of ['','.spec.json','.data.json','.scene.json']) {
  test(`analysis rejects ${kind} input alias at ${suffix||'PPTX'} before writing`,t=>{
    const dir=fs.mkdtempSync(path.join(os.tmpdir(),'构见 input safety '));
    try {
      const input=path.join(dir,'source.json'),out=path.join(dir,'deck.pptx'),alias=out+suffix;
      fs.writeFileSync(input,bytes);
      if(kind==='symlink') {
        try {fs.symlinkSync(input,alias);} catch(error) {
          if(process.platform==='win32'&&['EPERM','EACCES'].includes(error.code)) {t.skip('Windows symlink privilege unavailable');return;}
          throw error;
        }
      } else fs.linkSync(input,alias);
      const before=fs.readdirSync(dir).sort();
      const result=spawnSync(process.execPath,[path.join(root,'scripts/analyze.js'),input,out],{encoding:'utf8'});
      assert.notEqual(result.status,0);assert.match(result.stderr,/must not overwrite input/);
      assert.deepEqual(fs.readFileSync(input),bytes);assert.deepEqual(fs.readdirSync(dir).sort(),before);
    } finally {fs.rmSync(dir,{recursive:true,force:true});}
  });
}
test('shared output guard rejects existing output hardlinks',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gj-output-links-'));
  try {
    const a=path.join(dir,'a'),b=path.join(dir,'b');fs.writeFileSync(a,'preserve');fs.linkSync(a,b);
    assert.throws(()=>assertDistinctOutputs([{path:a,label:'a'},{path:b,label:'b'}]),/must be different/);
    assert.equal(fs.readFileSync(a,'utf8'),'preserve');
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
test('analysis rejects aliases between sidecar outputs without changing existing files',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gj-sidecar-links-'));
  try {
    const input=path.join(dir,'source.json'),out=path.join(dir,'deck.pptx');fs.writeFileSync(input,bytes);
    fs.writeFileSync(out+'.spec.json','preserve');fs.linkSync(out+'.spec.json',out+'.data.json');
    const result=spawnSync(process.execPath,[path.join(root,'scripts/analyze.js'),input,out],{encoding:'utf8'});
    assert.notEqual(result.status,0);assert.match(result.stderr,/must be different/);
    assert.deepEqual(fs.readFileSync(input),bytes);assert.equal(fs.readFileSync(out+'.spec.json','utf8'),'preserve');
    assert(!fs.existsSync(out));
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
