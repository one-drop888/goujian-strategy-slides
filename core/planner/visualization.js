const RULES = [
  [/trend|趋势|time series|同比|环比/i,'trend'],
  [/funnel|转化|漏斗|conversion/i,'funnel'],
  [/before|after|前后|变化前|变化后/i,'before-after'],
  [/driver|cause|原因|驱动|why/i,'driver-tree'],
  [/priority|优先级|impact.*effort|重要.*紧急/i,'priority'],
  [/timeline|里程碑|时间线|chronology/i,'timeline'],
  [/roadmap|路径|规划|phase|阶段/i,'roadmap'],
  [/benchmark|对标|竞品|compare|比较/i,'benchmark'],
  [/risk|风险/i,'risk'],
  [/process|流程|步骤/i,'process'],
  [/architecture|架构|system/i,'architecture'],
  [/exact|明细|table|清单/i,'table'],
];
function recommendArchetype(intent='') {
  for (const [re,id] of RULES) if(re.test(intent)) return id;
  return 'key-message';
}
module.exports={recommendArchetype};
