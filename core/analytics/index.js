const crypto=require('crypto');
const Ajv=require('ajv/dist/2020');
const {formatMetric,formatCodeForMetric}=require('../semantics/numeric');
const {close,compensatedSum}=require('../reasoning/calculations');
const validate=new Ajv({allErrors:true,strict:false}).compile(require('../schema/analytics.schema.json'));
const DAY=86400000;
const finite=x=>{if(x!=null&&!Number.isFinite(x))throw Error('Computed numeric overflow');return x;};
const sum=xs=>xs.some(x=>x==null)?null:finite(compensatedSum(xs));
const ratio=(a,b)=>a==null||b==null||b===0?null:finite(a/b);
const difference=(a,b)=>a==null||b==null?null:finite(a-b);
const change=(a,b)=>ratio(difference(a,b),b);
const product=(a,b)=>a==null||b==null?null:finite(a*b);
function displayMetric(x,unit='') {
 const type=unit==='%'?'percent':unit==='pp'?'pp':'absolute';
 return {id:'analytics-value',type,storage_scale:type==='absolute'?'unit':'percent',raw_value:x,
  display_unit:unit,precision:Number.isInteger(x)?0:2,comparison_basis:type==='absolute'?undefined:'declared_recipe',
  display_notation:x!==0&&(Math.abs(x)<.005||Math.abs(x)>=1e15)?'scientific':'plain'};
}
function fmt(x,unit=''){return x==null?'缺失 / N/A':formatMetric(displayMetric(x,unit)).text;}

const pct=x=>x==null?'N/A':fmt(x*100,'%');
function date(s){const d=new Date(s+'T00:00:00Z');if(!Number.isFinite(+d)||d.toISOString().slice(0,10)!==s)throw Error('Invalid calendar date: '+s);return +d;}
function unique(xs,key){if(new Set(xs.map(key)).size!==xs.length)throw Error('Duplicate identity: '+key.toString());}
function analyze(input){
 if(!validate(input))throw Error('Analytical input schema: '+JSON.stringify(validate.errors));
 const d=JSON.parse(JSON.stringify(input)),start=date(d.period.start),end=date(d.period.end);
 if(start>end)throw Error('Period start must precede end');
 const warnings=[],slides=[],metrics={};
 const source=`${d.synthetic?'合成数据 · ':''}${d.source}`;
 const add=(type,title,fields={})=>slides.push({type,title,source,...fields});
 const table=(title,headers,rows,fields={})=>{
  for(let offset=0;offset<rows.length;offset+=8)add('table',title+(rows.length>8?`（${offset/8+1}）`:''),{headers,rows:rows.slice(offset,offset+8),...fields});
 };
 const chart=(title,labels,series,unit,insight,fields={})=>{
  const ids=labels.map((_,i)=>i),hasMissing=series.some(s=>s.values.some(v=>v===null));
  if(hasMissing)warnings.push(title+': missing observations retained as native chart gaps and N/A in table');
  const values=series.flatMap(s=>s.values).filter(v=>v!=null);
  const representative=values.find(v=>v!==0&&(Math.abs(v)<.005||Math.abs(v)>=1e15))??values.find(v=>!Number.isInteger(v))??values[0]??0;
  const numberFormat=formatCodeForMetric(displayMetric(representative,unit));
  for(let offset=0;offset<ids.length;offset+=10){const chunk=ids.slice(offset,offset+10);add('chart',title+(ids.length>10?`（${offset/10+1}）`:''),{labels:chunk.map(i=>labels[i]),series:series.map(s=>({...s,values:chunk.map(i=>s.values[i])})),unit,period:`${d.period.start} 至 ${d.period.end}`,insight,chartType:'bar',numberFormat,...(hasMissing?{missing_policy:'gap'}:{}),...fields});}
 };
 const score=(title,items)=>{for(let i=0;i<items.length;i+=6)add('kpi-dashboard',title,{items:items.slice(i,i+6)});};
 const summary=(title,items)=>{for(let i=0;i<items.length;i+=5)add('executive-summary',title,{items:items.slice(i,i+5)});};
 add('cover',d.title,{subtitle:`${d.period.start} 至 ${d.period.end} · ${d.synthetic?'合成数据示例':'用户提供数据'}`});
 if(d.recipe==='business-performance'){
  unique(d.metrics,x=>x.id);const p=d.metrics.find(x=>x.id===d.primary_metric);if(!p)throw Error('primary_metric must identify a metric');
  unique(d.trend,x=>x.month);unique(d.contributions,x=>x.label);
  const months=d.trend.map(x=>x.month);months.forEach(m=>date(m+'-01'));
  if(months.some((m,i)=>i&&m<=months[i-1])||months.at(-1)!==d.period.end.slice(0,7))throw Error('Trend must be ordered and end in the reporting month');
  if(d.period.start!==d.period.end.slice(0,7)+'-01'||date(d.period.end)+DAY!==date(new Date(date(d.period.end)+DAY).toISOString().slice(0,7)+'-01'))throw Error('Business performance requires a full calendar month');
  if(d.trend.at(-1).actual!==p.actual)throw Error('Latest trend observation must equal primary actual');
  const priorYearMonth=`${Number(d.period.end.slice(0,4))-1}${d.period.end.slice(4,7)}`;
  const bases=[[d.trend.at(-2),p.previous_month,'previous_month'],[d.trend.find(x=>x.month===priorYearMonth),p.previous_year,'previous_year']];
  for(const [point,baseline,label] of bases)if(point?.actual!=null&&baseline!=null&&point.actual!==baseline)throw Error('Trend observation conflicts with '+label+' baseline');
  if(months.some((m,i)=>i&&date(m+'-01')!==date(new Date(Date.UTC(Number(months[i-1].slice(0,4)),Number(months[i-1].slice(5)),1)).toISOString().slice(0,10))))throw Error('Trend months must be consecutive; supply explicit null for missing months');
  const total=sum(d.contributions.map(x=>x.actual));if(total!=null&&p.actual!=null&&!close(total,p.actual))throw Error('Contributions must reconcile to primary actual');
  const previous=sum(d.contributions.map(x=>x.previous));if(previous!=null&&p.previous_month!=null&&!close(previous,p.previous_month))throw Error('Previous contributions must reconcile to previous_month');
  metrics.kpis=d.metrics.map(x=>({...x,variance:difference(x.actual,x.target),variance_unit:x.unit==='%'?'pp':x.unit,attainment:ratio(x.actual,x.target),mom:change(x.actual,x.previous_month),yoy:change(x.actual,x.previous_year)}));
  metrics.contributions=d.contributions.map(x=>({...x,share:ratio(x.actual,p.actual),delta:difference(x.actual,x.previous)}));
  metrics.reconciliation={actual:total,previous};
  score(`${p.label}达成 ${pct(ratio(p.actual,p.target))}，目标差异 ${fmt(difference(p.actual,p.target),p.unit==='%'?'pp':p.unit)}`,metrics.kpis.map(x=>({label:x.label,value:fmt(x.actual,x.unit),delta:`目标 ${fmt(x.target,x.unit)} · 同比 ${pct(x.yoy)}`,highlight:x.id===p.id})));
  if(d.metrics.length>=3&&d.metrics.length<=6&&d.trend.length<=12&&d.trend.every(x=>x.actual!=null))slides.at(-1).dashboard={unit:`${p.unit} · 月度实际`,labels:months,series:[{name:p.label,values:d.trend.map(x=>x.actual)}]};
  chart(`${p.label}实际 ${fmt(p.actual,p.unit)}，目标 ${fmt(p.target,p.unit)}`,[p.label],[{name:'实际',role:'actual',values:[p.actual]},{name:'目标',role:'target',values:[p.target]}],p.unit,'同一指标、同一月份，避免混合单位比较');
  chart(`${p.label}环比 ${pct(change(p.actual,p.previous_month))}`,months,d.trend.length?[{name:p.label,values:d.trend.map(x=>x.actual)}]:[],p.unit,'月度实际值；同比与环比均使用显式提供的基期',{chartType:'line'});
  table('目标差异按指标逐项核对',['指标','单位','实际','目标','差异','达成','环比','同比'],metrics.kpis.map(x=>[x.label,x.unit,fmt(x.actual),fmt(x.target),fmt(x.variance,x.variance_unit),pct(x.attainment),pct(x.mom),pct(x.yoy)]),{subtitle:'百分比指标差异用百分点（pp）；同比、环比均为相对变化'});
  table('趋势保留每个月份及缺失状态',['月份',p.unit],d.trend.map(x=>[x.month,fmt(x.actual)]));
  chart('贡献分析使用同一总量和基期',d.contributions.map(x=>x.label),[{name:'本月',role:'actual',values:d.contributions.map(x=>x.actual)},{name:'上月',role:'history',values:d.contributions.map(x=>x.previous)}],p.unit,'分项合计与总量校验；贡献与增长贡献分开解释');
  table('贡献份额与增量分开呈现',['分项','本月','上月','份额','增量'],metrics.contributions.map(x=>[x.label,fmt(x.actual),fmt(x.previous),pct(x.share),fmt(x.delta)]));
  summary('管理摘要只陈述可计算差异',metrics.kpis.map(x=>({title:x.label,note:`实际 ${fmt(x.actual,x.unit)}，差异 ${fmt(x.variance,x.variance_unit)}，同比 ${pct(x.yoy)}；原因与行动由管理者验证。`})));
 } else if(d.recipe==='sales-conversion'){
  const asof=date(d.as_of);if(asof<end)throw Error('as_of must cover cohort acquisition period');
  unique(d.stages,x=>x.id);unique(d.edges,x=>x.from+'>'+x.to);
  const leadRows=new Map();let duplicateLeadRows=0;for(const l of d.leads){if(leadRows.has(l.lead_id)){if(JSON.stringify(l)!==JSON.stringify(leadRows.get(l.lead_id)))throw Error('Conflicting duplicate lead_id');duplicateLeadRows++;}else leadRows.set(l.lead_id,l);}d.leads=[...leadRows.values()];
  const stages=new Map(d.stages.map(x=>[x.id,x.label]));if(stages.has('lead')||!stages.has(d.outcome_stage))throw Error('Stages exclude reserved lead and include outcome_stage');
  for(const e of d.edges)if(e.from===e.to||(!stages.has(e.from)&&e.from!=='lead')||!stages.has(e.to))throw Error('Edge must reference distinct configured stages');
  const customers=new Map();
  for(const l of d.leads){date(l.acquired);if(date(l.acquired)>asof)throw Error('Lead occurs after as_of');const prev=customers.get(l.customer_id);if(prev&&prev.acquired===l.acquired&&(prev.channel!==l.channel||prev.region!==l.region))throw Error('Ambiguous first-touch attribution for '+l.customer_id);if(!prev||l.acquired<prev.acquired)customers.set(l.customer_id,l);}
  const events=new Map();let repeated=0;
  for(const e of d.events){if(!customers.has(e.customer_id)||!stages.has(e.stage))throw Error('Event has unresolved customer/stage');const when=date(e.date),acq=date(customers.get(e.customer_id).acquired);if(when<acq||when>asof)throw Error('Event outside acquired/as_of observation bounds');const key=e.customer_id+'\0'+e.stage;if(events.has(key)){repeated++;if(when>=events.get(key))continue;}events.set(key,when);}
  const inPeriod=[...customers.values()].filter(l=>date(l.acquired)>=start&&date(l.acquired)<=end);
  const mature=inPeriod.filter(l=>date(l.acquired)+d.horizon_days*DAY<=asof);
  const reached=(l,stage)=>stage==='lead'?date(l.acquired):((events.get(l.customer_id+'\0'+stage)??Infinity)<=date(l.acquired)+d.horizon_days*DAY?events.get(l.customer_id+'\0'+stage):null);
  const won=l=>reached(l,d.outcome_stage)!=null;
  const groups=key=>[...new Set(mature.map(key))].sort().map(k=>{const rows=mature.filter(l=>key(l)===k),wins=rows.filter(won).length;return {label:k,customers:rows.length,wins,rate:ratio(wins,rows.length)};});
  metrics.cohort={acquired:inPeriod.length,mature:mature.length,immature:inPeriod.length-mature.length,wins:mature.filter(won).length,rate:ratio(mature.filter(won).length,mature.length)};
  metrics.dedup={duplicate_lead_rows:duplicateLeadRows,extra_leads:d.leads.length-customers.size,repeated_stage_events:repeated};
  metrics.stages=[{id:'lead',label:'获客',count:mature.length},...d.stages.map(s=>({id:s.id,label:s.label,count:mature.filter(l=>reached(l,s.id)!=null).length}))];
  metrics.edges=d.edges.map(e=>{const from=mature.filter(l=>reached(l,e.from)!=null),to=from.filter(l=>reached(l,e.to)!=null&&reached(l,e.to)>=reached(l,e.from));return {...e,denominator:from.length,converted:to.length,not_observed:from.length-to.length,rate:ratio(to.length,from.length)};});
  metrics.regions=groups(l=>l.region);metrics.channels=groups(l=>l.channel);metrics.cohorts=groups(l=>l.acquired.slice(0,7));
  metrics.branches=d.stages.filter(s=>s.id!==d.outcome_stage).map(s=>{const yes=mature.filter(l=>reached(l,s.id)!=null),no=mature.filter(l=>reached(l,s.id)==null);return {stage:s.label,yes:yes.length,yes_wins:yes.filter(won).length,no:no.length,no_wins:no.filter(won).length};});
  warnings.push('Rates use mature acquisition cohorts and first observed stage within horizon; branches are optional; attribution is earliest lead. Association is not causation.');
  score('获客与成交按成熟客户队列计算',[{label:'获客客户',value:fmt(metrics.cohort.acquired)},{label:'成熟分母',value:fmt(mature.length)},{label:'未成熟排除',value:fmt(metrics.cohort.immature)},{label:'成交客户',value:fmt(metrics.cohort.wins)},{label:'成交率',value:pct(metrics.cohort.rate),highlight:true},{label:'观察窗',value:fmt(d.horizon_days,' 天')}]);
  if(metrics.cohort.wins>0)add('sales-funnel','获客到成交仅使用必然嵌套的客户集合',{items:[{title:'成熟获客客户',value:mature.length},{title:'窗口内成交客户',value:metrics.cohort.wins}]});
  else add('key-message','当前成熟队列没有观察到成交',{statement:`成熟客户 ${mature.length} 人，成交 0 人。`,note:'零分母的成交率保持 N/A，不伪造漏斗数量。'});
  chart('到店、试驾与成交分别统计，分支不是必经阶段',metrics.stages.map(x=>x.label),[{name:'成熟客户数',values:metrics.stages.map(x=>x.count)}],'客户','阶段覆盖允许分支；不强制画成逐级收窄漏斗');
  table('阶段流失指观察窗内未见后续事件',['观察路径','分母','后续客户','未见后续','转化率'],metrics.edges.map(x=>[`${stages.get(x.from)||'获客'} → ${stages.get(x.to)}`,x.denominator,x.converted,x.not_observed,pct(x.rate)]));
  table('队列转化保持相同观察窗',['获客月份','成熟客户','成交','转化率'],metrics.cohorts.map(x=>[x.label,x.customers,x.wins,pct(x.rate)]));
  chart('区域对比展示客户量与成交量',metrics.regions.map(x=>x.label),[{name:'成熟客户',values:metrics.regions.map(x=>x.customers)},{name:'成交',values:metrics.regions.map(x=>x.wins)}],'客户','区域属于首次获客归属；不按最新门店重新分配');
  table('渠道归因固定首次获客口径',['渠道','成熟客户','成交','转化率'],metrics.channels.map(x=>[x.label,x.customers,x.wins,pct(x.rate)]));
  table('行为分组只提示关联，不能证明增量因果',['行为','参与客户','成交','成交率','未参与','成交','成交率'],metrics.branches.map(x=>[x.stage,x.yes,x.yes_wins,pct(ratio(x.yes_wins,x.yes)),x.no,x.no_wins,pct(ratio(x.no_wins,x.no))]));
  summary('诊断需先核对口径，再设计验证',[{title:'客户去重',note:`额外线索 ${metrics.dedup.extra_leads} 条；重复阶段事件 ${repeated} 条，均不重复计客户。`},{title:'跨期与成熟度',note:`截至 ${d.as_of}，固定 ${d.horizon_days} 天观察窗；未成熟 ${metrics.cohort.immature} 人排除。`},{title:'结论边界',note:'行为选择、客群与渠道差异均可能影响转化；试驾相关性不能自动解释为因果。'}]);
 } else {
  const asof=date(d.as_of);if(asof<end)throw Error('as_of must cover reporting period');unique(d.projects,x=>x.id);unique(d.milestones,x=>x.id);
  const projects=new Set(d.projects.map(x=>x.id));
  warnings.push('Project quantities and costs are cumulative as of as_of; all currency is CNY. Full-budget variance is not earned-value performance or savings.');
  metrics.projects=d.projects.map(p=>{const cost=sum([product(p.actual_days,p.day_rate),p.external_cost]);return {...p,cost,unit_variance:difference(p.actual_units,p.planned_units),cost_variance:difference(cost,p.budget),budget_usage:ratio(cost,p.budget),value_cost:ratio(p.realized_value,cost)};});
  metrics.milestones=d.milestones.map(m=>{if(!projects.has(m.project_id))throw Error('Milestone references unknown project');const planned=date(m.planned),actual=m.actual==null?null:date(m.actual);if(actual!=null&&actual>asof)throw Error('Milestone actual occurs after as_of');return {...m,status:actual==null?(planned<asof?'逾期未完':'待完成'):actual<=planned?'按期完成':'延期完成',delay_days:actual==null?null:(actual-planned)/DAY};});
  metrics.total={planned_units:sum(d.projects.map(x=>x.planned_units)),actual_units:sum(d.projects.map(x=>x.actual_units)),planned_days:sum(d.projects.map(x=>x.planned_days)),actual_days:sum(d.projects.map(x=>x.actual_days)),budget:sum(d.projects.map(x=>x.budget)),cost:sum(metrics.projects.map(x=>x.cost)),realized_value:sum(d.projects.map(x=>x.realized_value))};
  metrics.total.cost_variance=difference(metrics.total.cost,metrics.total.budget);metrics.total.value_cost=ratio(metrics.total.realized_value,metrics.total.cost);
  const t=metrics.total;
  score('项目总览同时核对交付、人天与成本',[{label:'交付量',value:fmt(t.actual_units,d.unit),delta:`计划 ${fmt(t.planned_units,d.unit)}`},{label:'投入人天',value:fmt(t.actual_days),delta:`计划 ${fmt(t.planned_days)}`},{label:'实际成本',value:fmt(t.cost,' 元'),delta:`预算 ${fmt(t.budget,' 元')}`,highlight:true},{label:'成本差异',value:fmt(t.cost_variance,' 元')},{label:'已实现价值',value:fmt(t.realized_value,' 元')},{label:'价值 / 成本',value:fmt(t.value_cost,' 倍')}]);
  chart('交付计划与实际按项目同尺度比较',d.projects.map(x=>x.name),[{name:'计划',role:'target',values:d.projects.map(x=>x.planned_units)},{name:'实际',role:'actual',values:d.projects.map(x=>x.actual_units)}],d.unit,'交付量不代表质量或业务价值；须结合验收状态');
  table('里程碑以截至日判断逾期，未完成不伪造成零天延误',['项目','里程碑','计划','实际','状态','偏差天数'],metrics.milestones.map(x=>[d.projects.find(p=>p.id===x.project_id).name,x.name,x.planned,x.actual||'未完成',x.status,fmt(x.delay_days)]));
  chart('资源投入按计划与实际人天比较',d.projects.map(x=>x.name),[{name:'计划人天',values:d.projects.map(x=>x.planned_days)},{name:'实际人天',values:d.projects.map(x=>x.actual_days)}],'人天','成本 = 实际人天 × 日费率 + 外部费用');
  table('预算与成本逐项保留，超支不等同于亏损',['项目','预算 / 元','成本 / 元','差异 / 元','使用率','已实现价值 / 元','价值成本比'],metrics.projects.map(x=>[x.name,fmt(x.budget),fmt(x.cost),fmt(x.cost_variance),pct(x.budget_usage),fmt(x.realized_value),fmt(x.value_cost)]));
  table('风险与交付量并列，缺失值保持可见',['项目','风险','计划交付','实际交付','差异'],metrics.projects.map(x=>[x.name,x.risk,fmt(x.planned_units),fmt(x.actual_units),fmt(x.unit_variance)]));
  summary('管理摘要聚焦偏差与待确认项',[{title:'交付',note:`实际 ${fmt(t.actual_units,d.unit)} / 计划 ${fmt(t.planned_units,d.unit)}；不合并不同计量单位。`},{title:'预算',note:`实际成本 ${fmt(t.cost,' 元')}，预算差异 ${fmt(t.cost_variance,' 元')}。`},{title:'投入产出',note:`价值成本比 ${fmt(t.value_cost,' 倍')}；仅使用用户声明的已实现价值，不推算未来收益。`}]);
 }
 function missing(x,p='input'){if(x===null)warnings.push(p+': missing; N/A retained');else if(Array.isArray(x))x.forEach((v,i)=>missing(v,`${p}[${i}]`));else if(typeof x==='object')Object.entries(x).forEach(([k,v])=>missing(v,p+'.'+k));}missing(d);
 const hash=crypto.createHash('sha256').update(JSON.stringify(input)).digest('hex');
 const audit={recipe:d.recipe,input_sha256:hash,source:d.source,synthetic:d.synthetic,period:d.period,metrics,warnings};
 const spec={title:d.title,profile:d.profile||'executive-dense',lang:'zh-CN',storyline:d.recipe==='sales-conversion'?'sales-funnel':d.recipe==='project-analytics'?'project-update':'quarterly-review',footer:source,slides};
 return {spec,audit};
}
module.exports={analyze,fmt,ratio,sum};
