import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const dir=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(dir,'../../../frontend/package.json'));
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const lucide=require('lucide-react');
const css=fs.readFileSync(path.resolve(dir,'../../../frontend/src/index.css'),'utf8');
const parse=s=>Object.fromEntries([...s.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6});/gi)].map(m=>[m[1],m[2]]));
const light=parse(css.split('.dark {')[0]),dark=parse(css.split('.dark {')[1].split('/* Map')[0]);
// Intentional design additions: readable label colors, transparent graphic state and stronger focus outline.
for(const [theme,c] of Object.entries({light,dark})) {
 c['surface-hover']=theme==='dark'?'#172131':'#f0f2f6';
 c['transparent']=theme==='dark'?'#0f1721':'#fafbfc';
 c['deadline-warning-fg']=theme==='dark'?'#d8af76':'#7c5727';
 c['deadline-neutral-fg']=theme==='dark'?'#a0adbd':'#536176';
 c['text-muted']=theme==='dark'?'#9ba7b8':'#626976';
 c['focus']=theme==='dark'?'#aab5f9':'#4f46e5';
}
const types={Title:[24,34,'Medium'],Section:[16,24,'Medium'],Notice:[15,22,'Medium'],Body:[14,22,'Regular'],Reader:[15,28,'Regular'],Metadata:[12,18,'Regular'],Label:[11,16,'Medium']};
const spaces=[0,2,4,6,8,10,12,14,16,18,20,22,24,28,30,32,36,40,48,56,64];
const radii=[0,4,6,7,8,10,12,999];
const iconNames=['Inbox','Mail','Bookmark','Star','CalendarClock','Building2','GraduationCap','Users','Search','SlidersHorizontal','ChevronDown','ChevronRight','ChevronLeft','ArrowUpDown','ExternalLink','CheckCheck','MoreHorizontal','Download','FileText','FileSpreadsheet','Settings','RefreshCw','Check','X','CircleAlert','WifiOff','Clock3','Menu','PanelLeftClose','Sun','Moon','Circle','ArrowLeft','Plus','Link','Keyboard'];
const icons=Object.fromEntries(iconNames.map(n=>[n,renderToStaticMarkup(React.createElement(lucide[n],{size:24,strokeWidth:1.65,color:'#000000'}))]));
const f=(name,o={},children=[])=>({kind:'frame',name,dir:'V',gap:0,pad:0,...o,children:children.filter(Boolean)});
const t=(name,text,role='Body',color='text-primary',o={})=>({kind:'text',name,text,role,color,...o});
const i=(icon,color='text-muted',size=18,o={})=>({kind:'icon',name:icon,icon,color,width:size,height:size,...o});
const inst=(component,variant,props={},o={})=>({kind:'instance',name:component,component,variant,props,...o});
const line=()=>f('Divider',{height:1,fill:'border',fillWidth:true});
const spacer=()=>f('Flexible space',{grow:1,height:1});
const components=[];
const add=(name,notes,variants)=>components.push({name,notes,variants});
const button=(label,icon,kind='Default',o={})=>inst('Button',kind,{Label:label,Icon:icon},o);
const badge=(state,label)=>inst('Deadline Badge',state,{Label:label});
const tag=(label,tone='Neutral')=>inst('Tag',tone,{Label:label});
add('Button','32px 控件 · Tab 可聚焦，Enter/Space 执行；禁用态不可交互；图标 16px。Primary 只用于主要操作。',
 Object.fromEntries(['Default','Hover','Focus','Pressed','Disabled','Primary'].map(state=>[state,f('Button',{dir:'H',height:32,gap:6,pad:[0,10],radius:6,align:'CENTER',justify:'CENTER',fill:state==='Primary'?'cta-surface':['Hover','Pressed'].includes(state)?'surface-hover':undefined,border:state==='Focus'?'focus':undefined,borderWidth:2,opacity:state==='Disabled'?.45:1},[i('RefreshCw',state==='Primary'?'text-inverse':'text-muted',16,{prop:'Icon'}),t('Label','重新加载','Metadata',state==='Primary'?'text-inverse':'text-secondary',{prop:'Label'})])])));
add('Status Badge','状态不只依赖颜色：图标 + 文本。未读与已读是服务器状态，选中是界面状态；打开详情成功后按 id 自动已读。',{
 Unread:f('Unread',{dir:'H',gap:6,align:'CENTER'},[f('Unread dot',{width:6,height:6,radius:999,fill:'unread'}),t('Label','未读','Label','accent-soft-text',{prop:'Label'})]),
 Read:f('Read',{dir:'H',gap:4,align:'CENTER'},[i('CheckCheck','text-muted',12),t('Label','已读','Label','text-muted',{prop:'Label'})]),
 Important:f('Important',{dir:'H',gap:4,align:'CENTER'},[i('Star','important',12),t('Label','重要','Label','important',{prop:'Label'})])
});
add('Deadline Badge','紧凑 20px。今天 / 3 天内 / 未来 / 已截止；无截止时间不展示。相对文案应可查看完整年月日、时间和时区。',Object.fromEntries(
 [['Today','今天 23:59 截止','danger'],['Soon','2 天后截止','warning'],['Future','9 月 18 日截止','neutral'],['Expired','已截止','neutral']].map(([state,label,tone])=>[state,f(state,{dir:'H',height:20,pad:[0,6],gap:4,radius:4,fill:`deadline-${tone}-bg`,align:'CENTER'},[i('Clock3',`deadline-${tone}-fg`,12),t('Label',label,'Label',`deadline-${tone}-fg`,{prop:'Label'})])])));
add('Tag','非交互分类标签。20px 高，6px 水平内边距；分类不自动新增路由。',Object.fromEntries(['Neutral','Academic','Organization'].map((state,k)=>[state,f(state,{dir:'H',height:20,pad:[0,6],radius:4,fill:k===1?'source-blue-bg':k===2?'source-green-bg':'deadline-neutral-bg',align:'CENTER'},[t('Label',['校园事务','教学','活动'][k],'Label',k===1?'source-blue-fg':k===2?'source-green-fg':'deadline-neutral-fg',{prop:'Label'})])])));
add('Source Item','来源是一等实体。学院 / 部门 / 组织采用相同 32px 行结构；数字表示当前来源未读数。长名称截断，完整名称通过提示显示。',Object.fromEntries(
 ['Default','Hover','Selected'].map(state=>[state,f(state,{dir:'H',width:246,height:34,pad:[0,10],gap:10,radius:6,fill:state==='Selected'?'selected-surface':state==='Hover'?'surface-hover':undefined,align:'CENTER'},[i('Building2',state==='Selected'?'accent-soft-text':'text-muted',16,{prop:'Icon'}),t('Label','教务处','Body',state==='Selected'?'accent-soft-text':'text-secondary',{grow:1,lines:1,prop:'Label'}),t('Count','4','Metadata','text-muted',{prop:'Count'})])])));
add('Navigation Item','36px 行。只对当前入口显示选中背景；未读/收藏/重要视图映射现有 URL filters。',Object.fromEntries(['Default','Active','Focus'].map(state=>[state,f(state,{dir:'H',width:246,height:36,pad:[0,10],gap:10,radius:7,fill:state==='Active'?'selected-surface':undefined,border:state==='Focus'?'focus':undefined,borderWidth:2,align:'CENTER'},[i('Inbox',state==='Active'?'accent-soft-text':'text-muted',18,{prop:'Icon'}),t('Label','全部通知','Body',state==='Active'?'text-primary':'text-secondary',{grow:1,prop:'Label'}),t('Count','128','Metadata',state==='Active'?'accent-soft-text':'text-muted',{prop:'Count'})])])));
add('Search Bar','搜索标题、来源与正文。默认 / 聚焦 / 输入 / 加载。Ctrl K 聚焦，Esc 清空或关闭，300ms debounce；请求取消静默。',Object.fromEntries(['Default','Focus','Filled','Loading'].map(state=>[state,f(state,{dir:'H',width:438,height:34,pad:[0,10],gap:8,radius:7,fill:'attachment-surface',border:state==='Focus'?'focus':'border',borderWidth:state==='Focus'?2:1,align:'CENTER'},[i(state==='Loading'?'RefreshCw':'Search','text-muted',16),t('Query',state==='Filled'?'奖学金':'搜索通知、来源或关键词','Metadata',state==='Filled'?'text-primary':'text-muted',{grow:1,lines:1,prop:'Query'}),t('Shortcut',state==='Filled'?'Esc':'Ctrl K','Label','text-muted')])])));
add('Notification Row','86px 紧凑行；标题单行截断，右侧对齐日期与截止时间。Enter 打开，↑↓ 切换；收藏按钮独立，操作不触发打开。状态可用 TEXT / BOOLEAN 属性覆盖。',Object.fromEntries(
 ['Unread','Read','Selected','Hover','Focus'].map(state=>[state,f(state,{dir:'V',width:574,height:86,pad:[10,18],gap:2,fill:state==='Selected'?'selected-surface':state==='Hover'?'surface-hover':'list-surface',border:state==='Focus'?'focus':undefined,borderWidth:2},[
 f('Source and time',{dir:'H',height:18,gap:6,align:'CENTER'},[i('GraduationCap','source-blue-fg',14,{prop:'Source icon'}),t('Source','教务处','Metadata','text-muted',{grow:1,lines:1,prop:'Source'}),t('Published','09:40','Metadata','text-muted',{prop:'Published'})]),
 f('Title and unread',{dir:'H',height:24,gap:8,align:'CENTER'},[f('Unread dot',{width:6,height:6,radius:999,fill:state==='Read'||state==='Selected'?'border-strong':'unread',boolProp:'Show unread'}),t('Title','关于开展 2026 年本科生国家奖学金评选的通知','Notice',state==='Read'?'text-secondary':'text-primary',{grow:1,lines:1,prop:'Title'})]),
 f('Metadata',{dir:'H',height:20,gap:8,align:'CENTER'},[t('Category','奖助学金','Label','text-muted',{prop:'Category'}),t('Read status',['Read','Selected'].includes(state)?'已读':'未读','Label','text-muted'),inst('Status Badge','Important',{}, {boolProp:'Show important'}),spacer(),badge('Today','今天 23:59 截止'),i('Bookmark',state==='Selected'?'accent-soft-text':'text-muted',14,{boolProp:'Show bookmark'})])
 ])])));
add('Attachment Card','46px 行：文件类型、原始文件名、格式、下载。仅有 filename / url / type 的数据契约；不虚构文件大小。长文件名中间省略；不安全 URL 禁用下载。',Object.fromEntries(['PDF','XLSX','Hover','Unavailable'].map(state=>[state,f(state,{dir:'H',width:520,height:46,pad:[0,12],gap:10,radius:7,fill:'attachment-surface',border:state==='Hover'?'border-strong':'border',align:'CENTER'},[f('File icon',{width:26,height:28,dir:'H',justify:'CENTER',align:'CENTER',radius:4,fill:state==='XLSX'?'source-green-bg':'deadline-danger-bg'},[i(state==='XLSX'?'FileSpreadsheet':'FileText',state==='XLSX'?'source-green-fg':'deadline-danger-fg',16)]),t('Filename',state==='XLSX'?'国家奖学金申请审批表.xlsx':'2026 年国家奖学金评审办法.pdf','Body','text-secondary',{grow:1,lines:1,prop:'Filename'}),t('Type',state==='XLSX'?'XLSX':'PDF','Label','text-muted',{prop:'Type'}),i(state==='Unavailable'?'CircleAlert':'Download','text-muted',16)])])));
add('Toolbar','固定在详情顶部；正文区域独立滚动。收藏与标记未读操作有反馈，打开原文使用外链；更多为仅图标按钮。',{
 Default:f('Toolbar',{dir:'H',width:584,height:44,pad:[0,22],gap:6,align:'CENTER',fill:'detail-surface'},[button('收藏','Star'),button('标记未读','Mail'),spacer(),button('打开原文','ExternalLink'),button('','MoreHorizontal')]),
 Saved:f('Toolbar',{dir:'H',width:584,height:44,pad:[0,22],gap:6,align:'CENTER',fill:'detail-surface'},[button('已收藏','Star'),button('标记未读','Mail'),spacer(),button('打开原文','ExternalLink'),button('','MoreHorizontal')])
});
add('Empty State','空列表与空详情分开。无搜索结果保留搜索词，提供清除筛选；收藏为空解释下一步；空详情引导选择，不显示为错误。',Object.fromEntries([
 ['NoResults','没有找到相关通知','试试其他关键词，或清除筛选条件。','Search','清除筛选'],['NoFavorites','把值得关注的通知留在这里','点击通知旁的收藏图标，方便之后查阅。','Bookmark','浏览全部通知'],['NoSelection','选择一条通知开始阅读','使用 ↑ ↓ 浏览列表，按 Enter 打开通知。','Inbox',''],['CaughtUp','暂时没有未读通知','新通知同步后会显示在这里。','CheckCheck','查看全部通知']
 ].map(([state,title,body,icon,action])=>[state,f(state,{width:520,height:280,align:'CENTER',justify:'CENTER',gap:12,pad:32},[f('Icon well',{width:44,height:44,dir:'H',align:'CENTER',justify:'CENTER',radius:10,fill:'attachment-surface'},[i(icon,'text-muted',22)]),t('Title',title,'Section'),t('Description',body,'Body','text-muted',{textAlign:'CENTER'}),action?button(action,'ChevronRight'):null])])));
const skeleton=(width,height=12)=>f('Skeleton',{width,height,radius:4,fill:'border'});
add('Loading State','保留框架，延迟约 200ms 再显示骨架。禁用随机闪烁；reduced-motion 下静态显示。已有缓存的后台刷新不清空内容。',{
 List:f('Loading list',{width:574,gap:0},Array.from({length:4},(_,k)=>f('Skeleton row '+k,{height:86,pad:[14,18],gap:10},[f('Source skeleton',{dir:'H',gap:12},[skeleton(96,10),spacer(),skeleton(42,10)]),skeleton(420),skeleton(170,10)]))),
 Reader:f('Loading reader',{width:520,pad:24,gap:20},[skeleton(400,24),skeleton(280),line(),...Array.from({length:5},(_,k)=>skeleton(k===4?220:472))])
});
add('Error State','NETWORK_ERROR / TIMEOUT / HTTP_ERROR / NOT_FOUND 必须区别。ABORTED 静默。重试保留查询与已选通知；失败不得显示成空结果。',Object.fromEntries([
 ['Network','暂时无法连接通知服务','请检查网络或本地服务，已有通知仍可阅读。','WifiOff','重新连接'],['Timeout','加载时间比预期更长','请求已超时，请稍后重试。','Clock3','重试'],['Server','通知加载失败','服务暂时不可用，请稍后再试。','CircleAlert','重试'],['NotFound','通知不存在','这条通知可能已移除，返回列表查看其他通知。','FileText','返回列表']
 ].map(([state,title,body,icon,action])=>[state,f(state,{width:520,height:280,align:'CENTER',justify:'CENTER',gap:12,pad:32},[i(icon,'deadline-warning-fg',28),t('Title',title,'Section'),t('Description',body,'Body','text-muted',{textAlign:'CENTER'}),button(action,state==='NotFound'?'ArrowLeft':'RefreshCw')])])));

const data=[
 ['教务处','09:40','关于开展 2026 年本科生国家奖学金评选的通知','奖助学金','Today','今天 23:59 截止','Selected',true],
 ['计算机科学与技术学院','09:18','2026 秋季学期本科生选课及补退选安排','教学安排','Soon','2 天后截止','Unread',true],
 ['学生就业指导中心','08:56','2027 届毕业生秋季校园招聘双选会报名通知','实习就业','Soon','3 天后截止','Unread',false],
 ['校团委','08:30','关于招募校庆系列活动学生志愿者的通知','校园活动','Future','9 月 18 日截止','Unread',false],
 ['研究生院','昨天','关于 2027 年推荐免试研究生申请材料的说明','推免升学','Soon','3 天后截止','Unread',true],
 ['图书馆','昨天','图书馆中秋节开放时间及借阅服务安排','校园服务','Future','','Read',false],
 ['网络安全协会','昨天','校园网络安全挑战赛报名与赛前培训','竞赛','Future','9 月 21 日截止','Read',false],
 ['科学技术处','9 月 8 日','本科生科研训练计划项目结题材料提交','科研','Expired','已截止','Read',false]
];
const row=(d,selected=false)=> {
 const n=inst('Notification Row',selected?'Selected':d[6],{Source:d[0],Published:d[1],Title:d[2],Category:d[3],'Show important':d[7],'Show unread':!['Selected','Read'].includes(selected?'Selected':d[6])},{fillWidth:true});
 n.overrides={'Deadline Badge':{variant:d[4],props:{Label:d[5]},visible:!!d[5]},'Show bookmark':false};
 return n;
};
const nav=(label,icon,count,state='Default')=>inst('Navigation Item',state,{Label:label,Icon:icon,Count:count},{fillWidth:true});
const source=(label,count,icon='Building2',state='Default')=>inst('Source Item',state,{Label:label,Count:count,Icon:icon},{fillWidth:true});
const group=(label)=>f('Source group',{dir:'H',pad:[12,10,4,10],gap:6,align:'CENTER'},[i('ChevronDown','text-muted',12),t('Group title',label,'Label','text-muted')]);
const sidebar=()=>f('Sidebar',{width:282,height:900,fill:'sidebar-surface',pad:[24,18,16,18],gap:16},[
 f('Brand',{dir:'H',gap:12,align:'CENTER',height:40,pad:[0,10]},[f('App mark',{width:32,height:32,radius:8,dir:'H',align:'CENTER',justify:'CENTER',fill:'cta-surface'},[t('Monogram','N','Section','text-inverse')]),f('Brand name',{gap:0},[t('Product','Notice Hub','Section'),t('Positioning','校园通知，集中有序','Label','text-muted')])]),
 f('Inbox views',{gap:4},[nav('全部通知','Inbox','128','Active'),nav('未读通知','Mail','18'),nav('收藏','Bookmark','12'),nav('重要通知','Star','6')]),
 f('Deadline shortcut',{gap:8},[line(),nav('即将截止','CalendarClock','3')]),
 f('Sources',{gap:0},[f('Sources header',{dir:'H',pad:[8,10,0,10],align:'CENTER'},[t('Section label','通知来源','Label','text-muted',{grow:1}),i('SlidersHorizontal','text-muted',14)]),group('学院'),source('计算机科学与技术学院','5','GraduationCap'),source('软件学院','2','GraduationCap'),group('部门'),source('教务处','4'),source('学生就业指导中心','3'),source('研究生院','1'),source('图书馆','','Building2'),group('组织'),source('校团委','2','Users'),source('网络安全协会','1','Users')]),
 f('Sidebar spring',{grow:1}),
 f('Footer',{gap:8},[line(),nav('设置与偏好','Settings',''),f('Sync',{dir:'H',pad:[4,10],gap:6,align:'CENTER'},[i('Check','source-green-fg',12),t('Sync status','已同步 · 10:42','Label','text-muted',{grow:1}),i('RefreshCw','text-muted',14)])])
]);
const list=()=>f('Notice List',{width:574,height:844,fill:'list-surface'},[
 f('List title',{dir:'H',height:52,pad:[0,18],gap:8,align:'CENTER'},[t('Heading','全部通知','Section'),t('Total','128','Metadata','text-muted'),spacer(),button('最新发布','ArrowUpDown')]),
 f('List filters',{dir:'H',height:36,pad:[0,18],gap:8,align:'CENTER'},[tag('全部来源'),tag('全部时间'),spacer(),button('筛选','SlidersHorizontal')]),
 f('Date group',{dir:'H',height:28,pad:[0,18],align:'CENTER'},[t('Group','最近更新','Label','text-muted',{grow:1}),t('Unread count','18 条未读','Label','text-muted')]),
 ...data.map(d=>row(d)),
 f('List footer',{dir:'H',height:40,pad:[0,18],gap:10,align:'CENTER'},[t('Showing','1–8 / 128 条','Label','text-muted',{grow:1}),t('Page','第 1 页','Label','text-muted'),button('','ChevronLeft'),button('','ChevronRight')])
]);
const readerBody=()=>f('Reader content',{width:584,pad:[16,32,12,32],gap:12},[
 f('Notice header',{gap:8},[
 f('Type and context',{dir:'H',gap:8,align:'CENTER'},[tag('奖助学金','Academic'),inst('Status Badge','Important'),spacer(),inst('Status Badge','Read')]),
 t('Detail title','关于开展 2026 年本科生\n国家奖学金评选的通知','Title','text-primary'),
 f('Source identity',{dir:'H',gap:8,align:'CENTER'},[i('Building2','text-secondary',16),t('Source name','教务处 · 学生资助管理中心','Metadata','text-secondary')]),
 f('Publication and deadline',{dir:'H',gap:8,align:'CENTER'},[t('Publish datetime','发布于 2026 年 9 月 10 日 09:40','Metadata','text-muted',{grow:1}),badge('Today','今天 23:59 截止')]),
 f('Tags',{dir:'H',gap:6},[tag('本科生'),tag('国家奖学金'),tag('2026 学年')])
 ]),line(),
 f('Body',{gap:8},[
 t('Salutation','各学院、各位同学：','Reader','text-secondary'),
 t('Paragraph 1','2026 年本科生国家奖学金评选工作现已启动。请符合条件的同学认真阅读评审办法，在规定时间内完成申请。','Reader','text-secondary'),
 t('Section 1','一、申请对象','Body','text-primary'),
 t('Eligibility','我校全日制本科二年级及以上学生。具体申请条件、成绩要求与名额分配以附件评审办法为准。','Reader','text-secondary'),
 t('Section 2','二、材料与提交方式','Body','text-primary'),
 t('Requirements','1. 填写《国家奖学金申请审批表》。\n2. 准备成绩单及相关获奖证明材料。\n3. 将申请材料提交至所在学院学生工作办公室。','Reader','text-secondary'),
 f('Deadline note',{dir:'H',gap:10,pad:12,radius:6,fill:'deadline-warning-bg',align:'CENTER'},[i('CalendarClock','deadline-warning-fg',18),t('Deadline instruction','校级截止：9 月 10 日 23:59。\n请同时留意所在学院的材料受理时间。','Metadata','deadline-warning-fg',{grow:1})])
 ]),
 f('Attachments',{gap:8},[f('Attachment heading',{dir:'H',gap:8,align:'CENTER'},[t('Heading','附件','Body'),t('Count','2','Label','text-muted')]),inst('Attachment Card','PDF',{},{fillWidth:true}),inst('Attachment Card','XLSX',{},{fillWidth:true})]),
 f('Original',{dir:'H',gap:8,align:'CENTER'},[button('查看原文','ExternalLink'),t('Original host','教务处官方网站','Label','text-muted'),spacer(),t('Body footer','正文内容以原文为准','Label','text-muted')])
]);
const desktop=()=>f('Desktop · 全部通知',{width:1440,height:900,dir:'H',fill:'app-frame'},[
 sidebar(),f('Workspace',{width:1158,height:900},[
 f('Global Toolbar',{dir:'H',height:56,pad:[0,18],gap:16,align:'CENTER',fill:'header-surface'},[inst('Search Bar','Default'),spacer(),t('Today','9 月 10 日  周四','Metadata','text-muted'),button('','Sun'),f('User avatar',{width:28,height:28,radius:999,fill:'selected-surface',dir:'H',align:'CENTER',justify:'CENTER'},[t('Avatar text','同','Label','accent-soft-text')])]),
 f('Reading workspace',{dir:'H',width:1158,height:844},[list(),f('Detail Reader',{width:584,height:844,fill:'detail-surface',borderLeft:'border'},[inst('Toolbar','Default'),line(),f('Reader scroll area',{width:584,grow:1,clip:true,scroll:'VERTICAL'},[readerBody()])])])
 ])
]);
const mobile=()=>f('390 · 通知列表',{width:390,height:844,fill:'list-surface'},[
 f('Mobile header',{dir:'H',height:60,pad:[0,16],gap:12,align:'CENTER'},[button('','Menu','Default',{width:44,height:44}),t('Title','全部通知','Section',{},{grow:1}),button('','Search','Default',{width:44,height:44})]),
 f('Filters',{dir:'H',height:44,pad:[0,16],gap:8,align:'CENTER'},[tag('全部来源'),tag('未读 18'),spacer(),button('','SlidersHorizontal')]),
 ...data.slice(0,7).map(d=>row(d)),
 f('Mobile footer',{height:50,dir:'H',pad:[0,20],align:'CENTER',justify:'CENTER'},[t('Help','轻触通知阅读详情','Metadata','text-muted')])
]);
// Correct the optional color argument above while keeping all text on semantic tokens.
const mobileFrame=mobile();mobileFrame.children[0].children[1].color='text-primary';
const mobileDetail=f('390 · 通知详情',{width:390,height:844,fill:'detail-surface',clip:true},[f('Back bar',{dir:'H',height:52,pad:[0,12],gap:6,align:'CENTER'},[button('返回通知','ArrowLeft','Default',{height:44}),spacer(),button('','Star','Default',{width:44,height:44}),button('','ExternalLink','Default',{width:44,height:44})]),f('Reader scroll area',{width:390,grow:1,clip:true,scroll:'VERTICAL'},[{...readerBody(),width:390,pad:[16,20]}])]);
const tablet=f('768 · 列表浏览',{width:768,height:900,dir:'H',fill:'list-surface'},[
 f('Collapsed sidebar',{width:72,height:900,pad:[20,12],gap:16,align:'CENTER',fill:'sidebar-surface'},[f('Brand mark',{width:32,height:32,fill:'cta-surface',radius:8,dir:'H',align:'CENTER',justify:'CENTER'},[t('N','N','Section','text-inverse')]),...['Inbox','Mail','Bookmark','Star','CalendarClock'].map(x=>button('',x)),f('Space',{grow:1}),button('','Settings')]),
 f('Tablet list',{width:696,height:900},[f('Search header',{dir:'H',height:56,pad:[0,18],align:'CENTER'},[inst('Search Bar','Default',{},{grow:1})]),{...list(),width:696}])
]);
const screens=[{name:'Desktop · Dark',theme:'Dark',node:desktop()},{name:'Desktop · Light',theme:'Light',node:desktop()},{name:'768 · Compact',theme:'Dark',node:tablet},{name:'390 · List',theme:'Dark',node:mobileFrame},{name:'390 · Reader',theme:'Dark',node:mobileDetail}];
const spec={version:'1.0',name:'Notice Hub',themes:{Dark:dark,Light:light},types,spaces,radii,icons,components,screens};
fs.writeFileSync(path.join(dir,'design-data.json'),JSON.stringify(spec,null,2));

// Shared semantic renderer: same component data powers preview and the Figma plugin.
function expand(n,theme,props={},overrides={}) {
 n=structuredClone(n);
 if(n.kind==='instance') {
   const c=components.find(c=>c.name===n.component);const override=overrides[n.component]||{};
   const root=expand(c.variants[override.variant||n.variant],theme,{...n.props,...override.props},{});
   for(const key of ['width','height','grow','fillWidth','boolProp','visible']) if(n[key]!==undefined)root[key]=n[key];
   root.name=n.name;
   if(override.visible===false)root.visible=false;
   if(n.boolProp&&props[n.boolProp]!==undefined)root.visible=props[n.boolProp];
   if(n.overrides)root.children=root.children?.map(child=>expandOverrides(child,theme,n.overrides));
   return root;
 }
 if(n.prop&&props[n.prop]!==undefined){if(n.kind==='text')n.text=String(props[n.prop]);if(n.kind==='icon')n.icon=props[n.prop];}
 if(n.boolProp&&props[n.boolProp]!==undefined)n.visible=props[n.boolProp];
 if(n.children)n.children=n.children.map(c=>expand(c,theme,props,overrides));
 return n;
}
function expandOverrides(n,theme,overrides){
 if(overrides[n.name]&&typeof overrides[n.name]==='object'){
   const o=overrides[n.name],c=components.find(c=>c.name===n.name);
   if(c){const r=expand(c.variants[o.variant],theme,o.props);r.visible=o.visible;return r;}
 }
 if(n.boolProp&&overrides[n.boolProp]!==undefined)n.visible=overrides[n.boolProp];
 if(n.children)n.children=n.children.map(c=>expandOverrides(c,theme,overrides));return n;
}
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
function html(n){
 if(n.visible===false)return '';
 const st=[];const px=v=>typeof v==='number'?v+'px':v;
 st.push('box-sizing:border-box','min-width:0','flex-shrink:0','position:relative');
 if(n.width&&!n.fillWidth)st.push('width:'+px(n.width));if(n.fillWidth)st.push('width:100%');if(n.height)st.push('height:'+px(n.height));
 if(n.grow)st.push('flex:1 1 0');
 if(n.fill)st.push('background:var(--'+n.fill+')');
 if(n.color)st.push('color:var(--'+n.color+')');
 if(n.radius)st.push('border-radius:'+px(n.radius));
 if(n.opacity!==undefined)st.push('opacity:'+n.opacity);
 if(n.border)st.push('box-shadow:inset 0 0 0 '+(n.borderWidth||1)+'px var(--'+n.border+')');
 if(n.borderLeft)st.push('border-left:1px solid var(--'+n.borderLeft+')');
 if(n.clip)st.push('overflow:hidden');if(n.scroll)st.push('overflow-y:auto;overflow-x:hidden;min-height:0');
 if(n.kind==='text'){
  const [size,lh,weight]=types[n.role];st.push(`font-size:${size}px;line-height:${lh}px;font-weight:${weight==='Medium'?500:400};white-space:pre-wrap`);
  if(n.lines===1)st.push('white-space:nowrap;overflow:hidden;text-overflow:ellipsis');
  if(n.textAlign)st.push('text-align:'+n.textAlign.toLowerCase());
  return `<div data-name="${esc(n.name)}" style="${st.join(';')}">${esc(n.text)}</div>`;
 }
 if(n.kind==='icon')return `<div data-name="${esc(n.icon)}" style="${st.join(';')};display:flex;align-items:center;justify-content:center">${icons[n.icon].replace('width="24"',`width="${n.width}"`).replace('height="24"',`height="${n.height}"`).replace('stroke="#000000"','stroke="currentColor"')}</div>`;
 st.push('display:flex','flex-direction:'+(n.dir==='H'?'row':'column'),'gap:'+(n.gap||0)+'px');
 if(n.pad){let a=Array.isArray(n.pad)?n.pad:[n.pad];st.push('padding:'+a.map(px).join(' '));}
 if(n.align)st.push('align-items:'+({CENTER:'center',MIN:'flex-start',MAX:'flex-end'}[n.align]||n.align));
 if(n.justify)st.push('justify-content:'+({CENTER:'center',MIN:'flex-start',MAX:'flex-end',SPACE_BETWEEN:'space-between'}[n.justify]||n.justify));
 return `<div data-name="${esc(n.name)}" style="${st.join(';')}">${n.children.map(html).join('')}</div>`;
}
const styles=Object.entries(spec.themes).map(([theme,colors])=>`.theme-${theme}{${Object.entries(colors).map(([k,v])=>`--${k}:${v};`).join('')}}`).join('\n');
const screenHtml=screens.map((s,k)=>`<section class="view theme-${s.theme}" id="screen-${k}" data-screen="${s.name}">${html(expand(s.node,s.theme))}</section>`).join('');
const componentHtml=components.map((c,k)=>`<section class="component theme-Dark" id="component-${k}"><h2>${esc(c.name)}</h2><p>${esc(c.notes)}</p><div class="variants">${Object.entries(c.variants).map(([v,n])=>`<div class="specimen"><h3>${esc(v)}</h3>${html(expand(n,'Dark'))}</div>`).join('')}</div></section>`).join('');
const foundationHtml=`<section class="component theme-Dark" id="foundations"><h2>Foundations · 设计基础</h2><p>Color · Dark / Light　/　Noto Sans SC　/　4px 基础间距　/　仅浮层使用阴影</p><div class="palette">${Object.keys(dark).map(n=>`<div class="swatch"><div style="background:${dark[n]}"></div><strong>${n}</strong><span>${dark[n]} / ${light[n]}</span></div>`).join('')}</div><div class="type-specs">${Object.entries(types).map(([n,[size,lh,w]])=>`<div><small>${n} · ${size}/${lh} · ${w}</small><p style="font-size:${size}px;line-height:${lh}px">校园通知，集中有序。 Notice Hub 2026</p></div>`).join('')}</div><p>Spacing: ${spaces.join(' / ')} px</p><p>Radius: ${radii.join(' / ')} px</p><p>Popover shadow: 0 8px 24px rgba(0,0,0,.24) · focus: 2px outline</p></section>`;
const preview=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Notice Hub · Design Review</title><style>
${styles}
*{box-sizing:border-box}body{margin:0;background:#070b11;color:#f4f4f5;font-family:"Noto Sans SC","Microsoft YaHei UI","Microsoft YaHei",sans-serif}.review-nav{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;height:56px;padding:0 24px;background:#0c121b;border-bottom:1px solid #202938;font-size:12px}.review-nav a{color:#bac4d1;text-decoration:none;padding:6px 10px;border:1px solid #354052;border-radius:6px}.review-nav strong{margin-right:auto}.view{margin:40px auto 80px;width:max-content;box-shadow:0 16px 48px #0004}.component{max-width:1440px;margin:80px auto;padding:40px;background:var(--detail-surface);border:1px solid var(--border);border-radius:12px}.component h2{font-size:24px;font-weight:500;margin:0 0 12px}.component p{font-size:14px;color:var(--text-muted);line-height:24px}.variants{display:flex;flex-wrap:wrap;align-items:flex-start;gap:32px 40px;padding-top:24px}.specimen{min-width:160px;max-width:100%}.specimen h3{font-size:12px;font-weight:400;color:var(--text-muted);margin:0 0 12px}.palette{display:grid;grid-template-columns:repeat(5,1fr);gap:20px}.swatch{font-size:12px;display:flex;flex-direction:column;gap:8px}.swatch div{height:48px;border-radius:6px;border:1px solid var(--border-strong)}.swatch span{color:var(--text-muted)}.type-specs{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:40px 0}.type-specs small{color:var(--text-muted)}
body.single .review-nav,body.single .view,body.single .component{display:none}body.single .shown{display:block!important;margin:0;box-shadow:none}body.single{background:transparent;width:max-content} .view>div{overflow:hidden}
</style><nav class="review-nav"><strong>Notice Hub · 设计审阅</strong><a href="#screen-0">深色主界面</a><a href="#screen-1">浅色</a><a href="#screen-2">768px</a><a href="#screen-3">390px</a><a href="#foundations">设计基础</a><a href="#component-0">组件库</a></nav>${screenHtml}${foundationHtml}${componentHtml}<script>const p=new URLSearchParams(location.search);if(p.has('view')){document.body.classList.add('single');document.getElementById(p.get('view'))?.classList.add('shown')}</script></html>`;
fs.writeFileSync(path.join(dir,'preview.html'),preview);
const runtime=fs.readFileSync(path.join(dir,'plugin-runtime.js'),'utf8');
fs.writeFileSync(path.join(dir,'code.js'),'const DESIGN = '+JSON.stringify(spec)+';\n'+runtime);
console.log(JSON.stringify({components:components.length,variants:components.reduce((n,c)=>n+Object.keys(c.variants).length,0),screens:screens.length,colorTokens:Object.keys(dark).length},null,2));
