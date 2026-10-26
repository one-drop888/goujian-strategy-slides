const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('fs'),path=require('path'),os=require('os'),JSZip=require('jszip');
const {validateDeck}=require('../core/schema/validate');
const {buildTimeline,TIMELINE_AXIS}=require('../core/composition/timeline');
const {buildRoadmapDag}=require('../core/composition/roadmap-dag');
const {buildDeck}=require('../core/renderer');
const {datedTimelineSlide,closeDateTimelineSlide,branchSwimlaneSlide,legacyRoadmapSlide,deck}=require('./relationship-fixtures');
const root=path.resolve(__dirname,'..');
const near=(a,b,epsilon=1e-9)=>Math.abs(a-b)<=epsilon;

function tmpdir() {return fs.mkdtempSync(path.join(os.tmpdir(),'gj-relationship-'));}
function sceneFor(file) {return JSON.parse(fs.readFileSync(file+'.scene.json','utf8'));}
async function nativeTexts(file) {
  const zip=await JSZip.loadAsync(fs.readFileSync(file));
  let xml='';
  for(const name of Object.keys(zip.files)) if(/^ppt\/slides\/slide\d+\.xml$/.test(name)) xml+=await zip.file(name).async('string');
  return [...xml.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)].map(match=>match[1]).join('\n');
}
function nodes(slide,role) {return slide.nodes.filter(node=>node.semantic_role===role);}

test('ISO timeline positions use true elapsed distance and optional duration',()=>{
  const model=buildTimeline(datedTimelineSlide.items);
  assert.equal(model.mode,'date');
  assert.equal(model.span_days,112);
  const byId=new Map(model.nodes.map(node=>[node.id,node]));
  assert(near(byId.get('pilot').start_ratio,28/112));
  assert(near(byId.get('review').start_ratio,56/112));
  assert(near(byId.get('readout').start_ratio,1));
  assert.equal(byId.get('pilot').duration_days,18);
  assert(near(byId.get('rollout').end_ratio,102/112));
  assert(near(byId.get('kickoff').start_ratio,0));
  assert.equal(model.axis.width,TIMELINE_AXIS.w);
});

test('ordinal timelines keep their legacy equal-distance model',()=>{
  const model=buildTimeline([{title:'A'},{title:'B'},{title:'C'}]);
  assert.equal(model.mode,'ordinal');
  assert(!model.nodes.some(node=>'start_ratio' in node));
});

test('September 1, September 2 and October 31 keep unequal true spacing in two label lanes',()=>{
  const model=buildTimeline(closeDateTimelineSlide.items);
  const byId=new Map(model.nodes.map(node=>[node.id,node]));
  assert(near(byId.get('sep1').start_ratio,0));
  assert(near(byId.get('sep2').start_ratio,1/60));
  assert(near(byId.get('oct31').start_ratio,1));
  assert.equal(byId.get('sep2').label_lane,1);
  assert.equal(byId.get('sep1').label_lane,0);
  assert.equal(model.label_lanes,2);
  assert.equal(model.reflowed,true);
});

test('ISO timeline rejects duplicate dates, reversed durations and illegible density with split guidance',()=>{
  const item=(id,date,end_date)=>({id,title:id,date,...(end_date?{end_date}:{})});
  assert.throws(()=>buildTimeline([item('A','2026-01-01'),item('B','2026-01-01')]),/duplicate timeline date/);
  assert.throws(()=>buildTimeline([item('A','2026-02-01','2026-01-01')]),/must not precede/);
  assert.throws(()=>buildTimeline([item('A','2026-02-30')]),/not a real calendar date/);
  assert.throws(()=>buildTimeline([{id:'A',title:'A',date:'2026-01-01'},{id:'B',title:'B'}]),/cannot mix dated and undated/);
  assert.throws(()=>buildTimeline([item('W','2026-01-01'),item('X','2026-01-02'),item('Y','2026-01-03'),item('Z','2026-02-01')]),/cluster within[\s\S]*two label lanes[\s\S]*split the chronological detail/);
  assert.throws(()=>buildTimeline([item('A','2026-01-01'),item('A','2026-02-01')]),/duplicate timeline node id/);
  assert.throws(()=>buildTimeline(Array.from({length:8},(_,i)=>item(`T${i}`,`2026-0${i+1}-01`))),/exceed layout capacity/);
});

test('branch swimlane retains explicit decision edges and bounded DAG structure',()=>{
  assert.deepEqual(validateDeck(deck([branchSwimlaneSlide])),[]);
  const dag=buildRoadmapDag(branchSwimlaneSlide.tasks,branchSwimlaneSlide.dependencies);
  assert.equal(dag.stages,3);
  assert.equal(dag.edges.filter(edge=>edge.from==='B').length,3);
  assert.equal(dag.edges.find(edge=>edge.to==='D').label,'达到门槛');
  assert.deepEqual(branchSwimlaneSlide.dependencies.map(edge=>edge.label),['完成后评估','达到门槛','未达门槛','暂停投入']);
});

test('light and dark dated timelines render native date labels and true-distance markers',async()=>{
  const dir=tmpdir();
  try {
    const spec=deck([datedTimelineSlide]);
    for(const profile of ['executive-clean','dark-executive']) {
      const file=path.join(dir,`timeline-${profile}.pptx`);
      await buildDeck(spec,file,{profile});
      const slide=sceneFor(file).slides[0];
      const markers=nodes(slide,'timeline_marker');
      assert.equal(markers.length,5);
      const kickoff=markers.find(node=>node.node_id==='kickoff'),readout=markers.find(node=>node.node_id==='readout'),pilot=markers.find(node=>node.node_id==='pilot');
      assert(near((pilot.bbox.x-kickoff.bbox.x)/(readout.bbox.x-kickoff.bbox.x),28/112,1e-6));
      const durations=nodes(slide,'timeline_duration');
      assert.equal(durations.length,2);
      assert.equal(durations.find(node=>node.node_id==='pilot').duration_days,18);
      const dates=nodes(slide,'timeline_date').map(node=>node.text);
      assert.deepEqual(dates,['2026-01-05','2026-02-02','2026-03-02','2026-03-30','2026-04-27']);
      assert(nodes(slide,'timeline_date').every(node=>node.kind==='text'&&node.provenance.render_mode==='editable'));
      const text=await nativeTexts(file);
      for(const value of ['2026-01-05','2026-04-27','18 天','季度复盘']) assert(text.includes(value),`${profile} native text missing ${value}`);
    }
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('close ISO dates reflow with leaders while native marker spacing stays true',async()=>{
  const dir=tmpdir();
  try {
    for(const profile of ['executive-clean','dark-executive']) {
      const file=path.join(dir,`close-${profile}.pptx`);
      await buildDeck(deck([closeDateTimelineSlide]),file,{profile});
      const slide=sceneFor(file).slides[0];
      const markers=nodes(slide,'timeline_marker');
      assert.equal(markers.length,3);
      const sep1=markers.find(node=>node.node_id==='sep1'),sep2=markers.find(node=>node.node_id==='sep2'),oct31=markers.find(node=>node.node_id==='oct31');
      assert(near((sep2.bbox.x-sep1.bbox.x)/(oct31.bbox.x-sep1.bbox.x),1/60,1e-6));
      assert.equal(sep2.label_lane,1);
      const leaders=nodes(slide,'timeline_leader');
      assert.deepEqual(leaders.map(node=>node.node_id),['sep2']);
      const dates=nodes(slide,'timeline_date');
      assert.deepEqual(dates.map(node=>node.text),['2026-09-01','2026-09-02','2026-10-31']);
      assert.equal(dates.find(node=>node.text==='2026-09-02').label_lane,1);
      const text=await nativeTexts(file);
      for(const value of ['2026-09-01','2026-09-02','2026-10-31','次日补访']) assert(text.includes(value),`${profile} native text missing ${value}`);
    }
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('light and dark branch swimlanes keep branches, labels and owner/date/status native',async()=>{
  const dir=tmpdir();
  try {
    const spec=deck([branchSwimlaneSlide]);
    for(const profile of ['executive-clean','dark-executive']) {
      const file=path.join(dir,`swimlane-${profile}.pptx`);
      await buildDeck(spec,file,{profile});
      const slide=sceneFor(file).slides[0];
      assert.equal(nodes(slide,'swimlane_label').length,3);
      const tasks=nodes(slide,'task_node');
      assert.equal(tasks.length,5);
      const supplement=tasks.find(node=>node.task_id==='C');
      assert.equal(supplement.owner,'研究组');
      assert.equal(supplement.date,'2026 Q2');
      assert.equal(supplement.status,'进行中');
      const decisions=nodes(slide,'decision_edge');
      assert.deepEqual(decisions.map(node=>node.text).sort(),['暂停投入','未达门槛','达到门槛','完成后评估'].sort());
      assert(decisions.every(node=>node.kind==='text'&&node.provenance.render_mode==='editable'));
      assert.equal(decisions.length,4);
      assert(nodes(slide,'dependency').some(node=>node.from==='B'&&node.to==='D'));
      assert(nodes(slide,'dependency').some(node=>node.from==='B'&&node.to==='C'));
      const text=await nativeTexts(file);
      for(const value of ['业务','决策','研究','达到门槛','未达门槛','研究组 · 2026 Q2 · 进行中']) assert(text.includes(value),`${profile} native text missing ${value}`);
    }
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('legacy lane roadmaps still render beside the bounded graph mode',async()=>{
  assert.deepEqual(validateDeck(deck([legacyRoadmapSlide])),[]);
  const dir=tmpdir();
  try {
    const file=path.join(dir,'legacy.pptx');
    await buildDeck(deck([legacyRoadmapSlide]),file,{profile:'executive-clean'});
    const text=await nativeTexts(file);
    for(const value of ['产品','运营','研究','试点版本','稳定运营']) assert(text.includes(value),`missing ${value}`);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('cyclic or malformed graphs fail honestly instead of being linearized',async()=>{
  const base={tasks:branchSwimlaneSlide.tasks,dependencies:branchSwimlaneSlide.dependencies,stage_labels:branchSwimlaneSlide.stage_labels,lane_labels:branchSwimlaneSlide.lane_labels};
  const invalid=(over,pattern)=>assert.match(validateDeck(deck([{type:'roadmap',title:'Graph',...base,...over}])).join('\n'),pattern);
  invalid({dependencies:[...branchSwimlaneSlide.dependencies,{from:'D',to:'B'}]},/acyclic|cycle/);
  invalid({dependencies:[{from:'A',to:'Z'}]},/unknown task/);
  invalid({tasks:[...branchSwimlaneSlide.tasks,{id:'A',title:'Again',lane:0}]},/duplicate task id/);
  invalid({tasks:[{id:'A',title:'A',lane:3}],dependencies:[],lane_labels:['业务']},/lane 0–2/);
  invalid({dependencies:[{from:'A',to:'B',label:' '}]},/label must be a nonempty string/);
  invalid({dependencies:[{from:'A',to:'B',label:'x'.repeat(41)}]},/at most 40 characters/);
  invalid({tasks:[{id:'A',title:'A',lane:0,status:'x'.repeat(33)}],dependencies:[],lane_labels:['业务']},/at most 32 characters/);
  invalid({lane_labels:['业务']},/lane_labels must name each occupied swimlane/);
  invalid({lane_labels:['业务','研究','决策','多余']},/lane_labels must name up to three/);
  const grid=Array.from({length:9},(_,i)=>({id:`T${i}`,title:`T${i}`,lane:i%3}));
  const connectors=[];
  for(const from of ['T0','T1','T2']) for(const to of ['T3','T4','T5','T6','T7','T8']) if(connectors.length<13) connectors.push({from,to});
  invalid({tasks:grid,dependencies:connectors},/exceeds 12 connectors/);
  const dir=tmpdir();
  try {
    const file=path.join(dir,'cycle.pptx');
    await assert.rejects(()=>buildDeck(deck([{type:'roadmap',title:'Cycle',...base,dependencies:[...branchSwimlaneSlide.dependencies,{from:'D',to:'B'}]}]),file,{profile:'executive-clean'}),/acyclic|cycle/);
    assert(!fs.existsSync(file),'a cyclic flow must not produce a fake linear deck');
    assert.match(validateDeck(deck([{type:'process',title:'Flow',items:[{title:'A'},{title:'B'}],dependencies:[{from:'A',to:'B'}]}])).join('\n'),/cannot silently linearize/);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('DAG ISO dates cannot reverse dependency chronology or use nonexistent days',()=>{
 const tasks=[{id:'a',title:'先核对',lane:0,date:'2026-09-20'},{id:'b',title:'再审批',lane:1,date:'2026-09-10'}];assert.throws(()=>buildRoadmapDag(tasks,[{from:'a',to:'b'}]),/ISO date order/);tasks[1].date='2026-02-30';assert.throws(()=>buildRoadmapDag(tasks,[]),/real calendar date/);
});
