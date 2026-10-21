function buildRoadmapDag(tasks,dependencies) {
  if(!Array.isArray(tasks)||tasks.length<1||tasks.length>9) throw new Error('dependency roadmap requires 1–9 tasks');
  const ids=new Set();
  for(const [index,task] of tasks.entries()) {
    if(!task||typeof task!=='object') throw new Error(`tasks[${index}] must be an object`);
    const id=typeof task.id==='string'?task.id.trim():'';
    if(!id) throw new Error(`tasks[${index}] requires a nonempty id`);
    if(ids.has(id)) throw new Error(`duplicate task id ${id}`);
    if(!(typeof task.title==='string'&&task.title.trim())&&!(typeof task.label==='string'&&task.label.trim())) throw new Error(`task ${id} requires a title`);
    if(!Number.isInteger(task.lane)||task.lane<0||task.lane>2) throw new Error(`task ${id} requires an explicit lane 0–2`);
    ids.add(id);
  }
  if(dependencies!=null&&!Array.isArray(dependencies)) throw new Error('dependencies must be an array');
  const edges=dependencies||[];
  const seen=new Set(),preds=new Map(tasks.map(task=>[task.id,[]])),succs=new Map(tasks.map(task=>[task.id,[]]));
  for(const [index,edge] of edges.entries()) {
    if(!edge||typeof edge.from!=='string'||typeof edge.to!=='string') throw new Error(`dependencies[${index}] requires from and to`);
    if(!ids.has(edge.from)||!ids.has(edge.to)) throw new Error(`dependency ${edge.from} → ${edge.to} references an unknown task`);
    if(edge.from===edge.to) throw new Error(`dependency ${edge.from} → ${edge.to} is a self-loop`);
    const key=edge.from+'\u0000'+edge.to;
    if(seen.has(key)) throw new Error(`duplicate dependency ${edge.from} → ${edge.to}`);
    seen.add(key);preds.get(edge.to).push(edge.from);succs.get(edge.from).push(edge.to);
  }
  const stage=new Map(tasks.map(task=>[task.id,0])),indegree=new Map(tasks.map(task=>[task.id,preds.get(task.id).length]));
  const queue=tasks.filter(task=>indegree.get(task.id)===0).map(task=>task.id);
  let visited=0;
  for(let index=0;index<queue.length;index++) {
    const id=queue[index];visited++;
    for(const next of succs.get(id)) {
      stage.set(next,Math.max(stage.get(next),stage.get(id)+1));
      indegree.set(next,indegree.get(next)-1);
      if(indegree.get(next)===0)queue.push(next);
    }
  }
  if(visited!==tasks.length) throw new Error('dependencies must form an acyclic graph (cycle detected)');
  const stageCount=Math.max(...stage.values())+1;
  if(stageCount>3) throw new Error('dependency depth exceeds 3 stages; split the roadmap');
  const positions=new Map();
  for(const task of tasks) {
    const key=stage.get(task.id)+'\u0000'+task.lane;
    if(positions.has(key)) throw new Error(`tasks ${positions.get(key)} and ${task.id} occupy the same stage/lane position; adjust lane`);
    positions.set(key,task.id);
  }
  const nodes=tasks.map(task=>({...task,stage:stage.get(task.id),title:(task.title||task.label).trim()}));
  return {nodes,stages:stageCount,edges:edges.map(edge=>({from:edge.from,to:edge.to})),byId:new Map(nodes.map(node=>[node.id,node]))};
}
module.exports={buildRoadmapDag};
