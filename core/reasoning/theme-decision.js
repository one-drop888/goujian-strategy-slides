const path=require('path');
const {loadProfile,resolveProfileFile}=require('../style/profile-loader');
const {schemaErrors}=require('../schema/validate');
const {relativeLuminance}=require('../style/resolve-style');

const RULES=[
  [/marketing|campaign|brand|营销|品牌|传播|活动/i,'marketing'],
  [/launch|release|go-to-market|发布|上市|新品/i,'launch'],
  [/research|interview|survey|voc|调研|研究|访谈|用户研究/i,'research'],
  [/training|enablement|培训|赋能/i,'training'],
  [/sales|channel|pipeline|销售|渠道|成交/i,'sales'],
  [/product|platform|technical|engineering|产品|技术|平台/i,'product-tech'],
  [/strategy|strategic|战略/i,'strategy'],
  [/finance|business|revenue|margin|budget|management|board|executive|decision|approve|经营|财务|利润|收入|预算|管理|决策|批准/i,'executive-clean'],
];

function automaticProfile(intent={}) {
  const primary=[intent.audience,intent.context?.scenario].filter(Boolean).join(' ');
  const secondary=[intent.goal,intent.decision_question,...(intent.audience_needs||[])].filter(Boolean).join(' ');
  let best=null;
  for(const [pattern,profile] of RULES) {
    const primaryMatches=primary.match(new RegExp(pattern.source,'gi'))||[];
    const secondaryMatches=secondary.match(new RegExp(pattern.source,'gi'))||[];
    const score=primaryMatches.length*2+secondaryMatches.length;
    if(score&&(!best||score>best.score)) best={profile,score,matched:[...primaryMatches,...secondaryMatches][0]};
  }
  return best?{profile:best.profile,matched:best.matched}:{profile:null,matched:null};
}

function hex(value) { return String(value??'').replace(/^#/,'').toUpperCase(); }
function assertPriorityOverrides(plan,profile,protectedSource) {
  const deck=plan.deck||{},violations=[];
  const profileBackground=profile.background||'FFFFFF';
  if(deck.background&&hex(deck.background)!==hex(profileBackground)) {
    violations.push(`background ${deck.background} conflicts with ${profileBackground}`);
  }
  for(const [key,value] of Object.entries(deck.colors||{})) {
    const base=profile.colors?.[key]??profile.colors?.[key.replace(/_([a-z])/g,(_,letter)=>letter.toUpperCase())];
    if(base==null) violations.push(`colors.${key} is not defined by the ${protectedSource} profile`);
    else if(hex(value)!==hex(base)) violations.push(`colors.${key} ${value} conflicts with ${base}`);
  }
  const fontDefaults={latin:'Noto Sans',cjk:'Noto Sans CJK SC',title_size:27,body_size:18};
  for(const key of ['latin','cjk','title_size','body_size']) {
    if(deck.font?.[key]==null) continue;
    const base=profile.font?.[key]??fontDefaults[key];
    if(String(deck.font[key])!==String(base)) violations.push(`font.${key} ${deck.font[key]} conflicts with ${base}`);
  }
  if(violations.length) {
    throw new Error(`${protectedSource} profile has highest priority; remove these deck overrides or move them into the ${protectedSource} profile: ${violations.join('; ')}`);
  }
}
function selectTheme(plan,options={}) {
  const theme=plan.theme||{};
  const planDir=options.planDir||process.cwd();
  const repoRoot=options.repoRoot||path.resolve(__dirname,'../..');
  const conflicts=[];
  let selected,source,reason;
  if(theme.reference_profile) {
    selected=theme.reference_profile;source='reference';reason='explicit reference profile has highest priority';
  } else if(theme.brand_profile) {
    selected=theme.brand_profile;source='brand';reason='brand profile has priority over user and automatic selection';
  } else {
    const user=options.profile||theme.user_profile||plan.deck?.profile;
    if(user) { selected=user;source='explicit-user';reason=options.profile?'CLI --profile is an explicit user override':'explicit user profile in the plan'; }
    else {
      const automatic=automaticProfile(plan.intent);
      if(automatic.profile) { selected=automatic.profile;source='automatic';reason=`intent matched "${automatic.matched}"`; }
      else { selected='executive-clean';source='default';reason='business/management default is a light executive theme'; }
    }
  }
  const requested_mode=theme.mode||'auto';
  if(requested_mode==='dark'&&['automatic','default'].includes(source)&&selected!=='dark-executive') {
    selected='dark-executive';source='explicit-mode';
    reason='explicit dark request overrides automatic/default light selection';
  }
  const file=resolveProfileFile(selected,repoRoot,planDir);
  const profile=loadProfile(selected,repoRoot,new Set(),planDir);
  const errors=schemaErrors('profile',profile);
  if(errors.length) throw new Error(`Invalid selected profile ${selected}: ${errors.join('; ')}`);
  if(source==='reference'||source==='brand') assertPriorityOverrides(plan,profile,source);
  const actual_mode=relativeLuminance(profile.background||'FFFFFF')<.45?'dark':'light';
  if(requested_mode==='light'&&actual_mode==='dark') {
    conflicts.push('requested light mode but the selected profile is dark; explicit profile priority retained');
  }
  if(requested_mode==='dark'&&actual_mode==='light'&&['reference','brand','explicit-user'].includes(source)) {
    conflicts.push('requested dark mode conflicts with the explicitly selected light profile; explicit profile priority retained');
  }
  if((plan.intent?.context?.printable||plan.intent?.context?.medium==='print')&&actual_mode==='dark') {
    conflicts.push('printable context usually favors a light background; dark profile was explicitly selected');
  }
  const colors=profile.colors||{};
  return {
    selected_profile:selected,profile_path:file,source,mode:actual_mode,requested_mode,
    primary:colors.accent||colors.text||'176B87',background:profile.background||'FFFFFF',
    typography:{latin:profile.font?.latin||'Noto Sans',cjk:profile.font?.cjk||'Noto Sans CJK SC',
      title_size:profile.font?.title_size||27,body_size:profile.font?.body_size||18},
    chart_strategy:'Palette derives from the accent with a 3:1 series / 4.5:1 text contrast guard; grid and labels use semantic tokens.',
    evidence_strategy:'Editable native charts/tables; image evidence stays embedded with caption and provenance; speaker notes carry source/claim traceability.',
    rationale:reason,conflicts,
  };
}

function publicThemeDecision(decision) {
  const {profile_path,...rest}=decision||{};
  return rest;
}

module.exports={selectTheme,publicThemeDecision,automaticProfile};
