const TOPIC_ONLY=/^(背景|现状|分析|总结|问题|方案|规划|计划|进展|数据|结果|策略|营销|销售|项目|渠道|用户|竞品|风险|结论|background|overview|analysis|strategy|plan|update|results?|sales|marketing|risk)$/i;
function looksLikeTopicTitle(title='') {
  const t=String(title).trim().replace(/[：:。.]$/,'');
  return TOPIC_ONLY.test(t) || t.length <= 4;
}
function actionTitleScore(title='') {
  const t=String(title).trim();
  let score=0;
  if(t.length>=10) score++;
  if(/[，,:：；;]/.test(t)) score++;
  if(/增长|下降|高于|低于|转向|应|需要|导致|驱动|集中|改善|差距|风险|机会|优先|increase|decline|should|driv|gap|risk|opportun|shift/i.test(t)) score+=2;
  if(looksLikeTopicTitle(t)) score-=2;
  return score;
}
module.exports={looksLikeTopicTitle,actionTitleScore};
