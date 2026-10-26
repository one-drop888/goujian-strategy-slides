const TIMELINE_AXIS={x:1.15,w:10.9,minLabelGap:1.7,capacity:7};
const ISO_DATE=/^(\d{4})-(\d{2})-(\d{2})$/;

function parseIsoDate(value,label) {
  if(typeof value!=='string'||!ISO_DATE.test(value)) throw new Error(`${label} must be an ISO date (YYYY-MM-DD)`);
  const [,year,month,day]=value.match(ISO_DATE).map(Number);
  const ms=Date.UTC(year,month-1,day);
  const date=new Date(ms);
  if(date.getUTCFullYear()!==year||date.getUTCMonth()!==month-1||date.getUTCDate()!==day) throw new Error(`${label} ${value} is not a real calendar date`);
  return ms;
}

function buildTimeline(items,options={}) {
  const axisWidth=options.axisWidth??TIMELINE_AXIS.w;
  const minLabelGap=options.minLabelGap??TIMELINE_AXIS.minLabelGap;
  if(!Array.isArray(items)||!items.length) throw new Error('timeline requires 1–7 items');
  if(items.length>TIMELINE_AXIS.capacity) throw new Error(`timeline items exceed layout capacity ${TIMELINE_AXIS.capacity}; split the chronology`);
  const isDated=item=>item&&typeof item==='object'&&(item.date!=null||item.end_date!=null);
  const dated=items.filter(isDated);
  if(!dated.length) return {mode:'ordinal',nodes:items.map((item,index)=>({...item,index}))};
  if(dated.length!==items.length) throw new Error('timeline cannot mix dated and undated items; date every milestone or remove all dates');
  const ids=new Set(),dates=new Set();
  const nodes=items.map((item,index)=>{
    const label=`items[${index}]`;
    if(typeof item!=='object'||item===null) throw new Error(`${label} must be an object when an ISO timeline is used`);
    const id=typeof item.id==='string'&&item.id.trim()?item.id.trim():`milestone-${index+1}`;
    if(ids.has(id)) throw new Error(`duplicate timeline node id ${id}`);
    ids.add(id);
    if(!(typeof item.title==='string'&&item.title.trim())&&!(typeof item.label==='string'&&item.label.trim())) throw new Error(`timeline node ${id} requires a title`);
    const start=parseIsoDate(item.date,`timeline node ${id} date`);
    if(dates.has(item.date)) throw new Error(`duplicate timeline date ${item.date}; use one milestone per date or merge the entries`);
    dates.add(item.date);
    let end=start;
    if(item.end_date!=null) {
      end=parseIsoDate(item.end_date,`timeline node ${id} end_date`);
      if(end<start) throw new Error(`timeline node ${id} end_date ${item.end_date} must not precede date ${item.date}`);
      if(end===start) throw new Error(`timeline node ${id} end_date must differ from date; omit end_date for a milestone`);
    }
    for(const [field,value] of [['owner',item.owner],['status',item.status]]) {
      if(value!=null&&(typeof value!=='string'||!value.trim()||value.trim().length>32)) throw new Error(`timeline node ${id} ${field} must be a nonempty string of at most 32 characters`);
    }
    return {...item,id,index,start,end,duration_days:(end-start)/86400000};
  });
  const min=Math.min(...nodes.map(node=>node.start));
  const max=Math.max(...nodes.map(node=>node.end??node.start));
  if(max===min) throw new Error('ISO timeline requires at least two distinct dates; split or aggregate the milestones');
  for(const node of nodes) {
    node.start_ratio=(node.start-min)/(max-min);
    node.end_ratio=(node.end-min)/(max-min);
  }
  const ordered=[...nodes].sort((a,b)=>a.start-b.start||a.index-b.index);
  const laneEnds=[];
  for(const node of ordered) {
    let lane=laneEnds.findIndex(end=>node.start_ratio*axisWidth-end>=minLabelGap);
    if(lane===-1&&laneEnds.length<2) lane=laneEnds.length;
    if(lane===-1) {
      const close=ordered.filter(other=>other!==node&&Math.abs(other.start_ratio-node.start_ratio)*axisWidth<minLabelGap).map(other=>other.date);
      throw new Error(`timeline dates ${[node.date,...close].join(', ')} cluster within ${minLabelGap.toFixed(2)} in even after two label lanes at true elapsed scale; consolidate milestones or split the chronological detail onto a second slide (elapsed positions are never distorted)`);
    }
    node.label_lane=lane;
    laneEnds[lane]=node.start_ratio*axisWidth;
  }
  const reflowed=nodes.some(node=>node.label_lane>0);
  return {mode:'date',nodes,min,max,span_days:(max-min)/86400000,label_lanes:laneEnds.length,reflowed,
    axis:{width:axisWidth,min_label_gap:minLabelGap}};
}

module.exports={buildTimeline,parseIsoDate,TIMELINE_AXIS};
