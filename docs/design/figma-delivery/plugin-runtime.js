/* Standalone Figma Desktop plugin. All design output is editable native nodes. */
figma.showUI(`<html lang="zh-CN"><meta charset="utf-8"><style>body{font:13px/1.7 system-ui,sans-serif;margin:24px;color:#263044}h2{font-size:18px}button{width:100%;padding:11px;border:0;border-radius:6px;background:#4e50b6;color:white;font-weight:600;cursor:pointer}small{color:#6b7280}#status{white-space:pre-wrap;margin-top:14px}</style><h2>Notice Hub · Desktop UI</h2><p>创建可编辑的深浅色界面、组件变体、Auto Layout 与交付规范。所有图形、文字均为原生节点。</p><p><small>写入当前页面的独立区域，保留已有内容。无网络访问。首次生成需要约 1–2 分钟。</small></p><button id="build" onclick="this.disabled=true;parent.postMessage({pluginMessage:{type:'build'}},'*')">创建可编辑设计</button><div id="status"></div><script>onmessage=e=>{const m=e.data.pluginMessage;if(m){document.getElementById('status').textContent=m.text;if(m.error)document.getElementById('build').disabled=false}}</script></html>`,{width:380,height:360});
let running=false;
figma.ui.onmessage=async msg=>{
 if(msg.type!=='build'||running)return;running=true;
 try{await generate();}catch(e){figma.ui.postMessage({text:'生成中断：'+e.message+'\n此前已生成的节点保留在独立区域。请保存文件并反馈错误信息。',error:true});running=false;}
};
async function generate(){
 const page=figma.currentPage;
 const prefix='Notice Hub · v1';
 if(page.children.some(n=>n.name===prefix+' / Desktop · Dark'))throw new Error('本页已存在这套设计。请在新空白页面运行，避免重复。');
 const progress=text=>figma.ui.postMessage({text});
 progress('1 / 5  准备字体和语义变量…');
 const fontList=await figma.listAvailableFontsAsync();
 const candidates=['Noto Sans SC','Noto Sans CJK SC','Microsoft YaHei UI','PingFang SC'];
 const fontFamily=candidates.find(f=>fontList.some(x=>x.fontName.family===f));
 if(!fontFamily)throw new Error('请安装 Noto Sans SC 字体后重试，以保证中文排版。');
 const weights={};
 for(const role of ['Regular','Medium']){
  const available=fontList.filter(x=>x.fontName.family===fontFamily).map(x=>x.fontName.style);
  weights[role]=available.includes(role)?role:available.includes('Regular')?'Regular':available[0];
 }
 await Promise.all([...new Set(Object.values(weights))].map(style=>figma.loadFontAsync({family:fontFamily,style})));
 const made=[];const allCollections=await figma.variables.getLocalVariableCollectionsAsync();
 const allVars=await figma.variables.getLocalVariablesAsync();
 const makeCollection=name=>{let c=allCollections.find(c=>c.name===prefix+' / '+name);if(!c){c=figma.variables.createVariableCollection(prefix+' / '+name);c.renameMode(c.defaultModeId,'Value');allCollections.push(c);}return c;};
 const primitiveCollection=makeCollection('Primitives'),dimensions=makeCollection('Dimensions');
 const colors={Dark:{},Light:{}};const colorCollections={Dark:makeCollection('Color · Dark'),Light:makeCollection('Color · Light')};
 const rgb=hex=>({r:parseInt(hex.slice(1,3),16)/255,g:parseInt(hex.slice(3,5),16)/255,b:parseInt(hex.slice(5,7),16)/255});
 const variable=(name,c,type,value,scopes,css)=>{let v=allVars.find(v=>v.name===name&&v.variableCollectionId===c.id);if(!v){v=figma.variables.createVariable(name,c,type);v.setValueForMode(c.defaultModeId,value);v.scopes=scopes;v.setVariableCodeSyntax('WEB','var(--'+css+')');allVars.push(v);}return v;};
 const raw={};for(const hex of [...new Set(Object.values(DESIGN.themes).flatMap(c=>Object.values(c)))])raw[hex]=variable('palette/'+hex.slice(1),primitiveCollection,'COLOR',rgb(hex),[],'nh-palette-'+hex.slice(1));
 for(const theme of ['Dark','Light'])for(const [name,hex] of Object.entries(DESIGN.themes[theme])){
  const scopes=/text|fg$/.test(name)?['TEXT_FILL','STROKE_COLOR']:name.startsWith('border')?['STROKE_COLOR']:['FRAME_FILL','SHAPE_FILL','STROKE_COLOR'];
  colors[theme][name]=variable(name,colorCollections[theme],'COLOR',{type:'VARIABLE_ALIAS',id:raw[hex].id},scopes,name);
 }
 const gaps={},radii={};for(const value of DESIGN.spaces)gaps[value]=variable('space/'+value,dimensions,'FLOAT',value,['GAP'],'nh-space-'+value);
 for(const value of DESIGN.radii)radii[value]=variable('radius/'+value,dimensions,'FLOAT',value,['CORNER_RADIUS'],'nh-radius-'+value);
 const types={};const existingStyles=await figma.getLocalTextStylesAsync();
 for(const [name,[size,lineHeight,weight]] of Object.entries(DESIGN.types)){
  let st=existingStyles.find(s=>s.name===prefix+' / Type/'+name);
  if(!st){st=figma.createTextStyle();st.name=prefix+' / Type/'+name;st.fontName={family:fontFamily,style:weights[weight]};st.fontSize=Number(size);st.lineHeight={unit:'PIXELS',value:Number(lineHeight)};}
  types[name]=st;
 }
 const effects=await figma.getLocalEffectStylesAsync();let shadow=effects.find(s=>s.name===prefix+' / Elevation/Popover');
 if(!shadow){shadow=figma.createEffectStyle();shadow.name=prefix+' / Elevation/Popover';shadow.effects=[{type:'DROP_SHADOW',color:{r:0,g:0,b:0,a:.24},offset:{x:0,y:8},radius:24,spread:0,visible:true,blendMode:'NORMAL'}];}
 const paint=(name,theme)=>figma.variables.setBoundVariableForPaint({type:'SOLID',color:rgb(DESIGN.themes[theme][name])},'color',colors[theme][name]);
 const colorNode=(node,name,theme)=>{for(const x of [node,...('findAll'in node?node.findAll(()=>true):[])])for(const field of ['fills','strokes'])if(field in x&&Array.isArray(x[field])&&x[field].length)x[field]=x[field].map(p=>p.type==='SOLID'?paint(name,theme):p);};
 const padding=v=>Array.isArray(v)?v.length===2?[v[0],v[1],v[0],v[1]]:v:[v||0,v||0,v||0,v||0];
 function style(node,n,theme,parent){
  node.name=n.name;
  if('fills'in node)node.fills=n.fill?[paint(n.fill,theme)]:[];
  if(n.border||n.borderLeft){node.strokes=[paint(n.border||n.borderLeft,theme)];node.strokeWeight=n.borderWidth||1;node.strokeAlign='INSIDE';if(n.borderLeft){node.strokeTopWeight=0;node.strokeRightWeight=0;node.strokeBottomWeight=0;node.strokeLeftWeight=1;}}
  if(n.radius!==undefined&&'cornerRadius'in node)node.setBoundVariable('cornerRadius',radii[n.radius]);
  if(n.opacity!==undefined)node.opacity=n.opacity;
  if(n.visible!==undefined)node.visible=n.visible;
  if('clipsContent'in node)node.clipsContent=!!n.clip;
  if(n.width||n.height)node.resize(n.width||node.width,n.height||node.height);
  if(parent){parent.appendChild(node);sizeChild(node,n,parent);}
 }
 function sizeChild(node,n,parent){
  if(parent.layoutMode==='VERTICAL'){
   if(n.grow)node.layoutSizingVertical='FILL';
   if(n.fillWidth||!n.width)node.layoutSizingHorizontal='FILL';
  }else if(parent.layoutMode==='HORIZONTAL'){
   if(n.grow||n.fillWidth)node.layoutSizingHorizontal='FILL';
  }
 }
 const baseX=Math.max(0,...page.children.map(n=>n.x+n.width))+160,baseY=80;
 const iconRoot=figma.createFrame();iconRoot.name=prefix+' / Icon masters';page.appendChild(iconRoot);iconRoot.x=baseX;iconRoot.y=baseY+4040;iconRoot.resize(1440,180);iconRoot.fills=[paint('detail-surface','Dark')];made.push(iconRoot);
 const iconComponents={};
 let iconIndex=0;
 for(const [name,svg] of Object.entries(DESIGN.icons)){
  const node=figma.createNodeFromSvg(svg);node.name='Vector';node.resize(24,24);colorNode(node,'text-muted','Dark');
  const c=figma.createComponent();c.name='Icon/'+name;c.resize(24,24);c.fills=[];c.appendChild(node);node.x=0;node.y=0;node.constraints={horizontal:'SCALE',vertical:'SCALE'};
  iconRoot.appendChild(c);c.x=24+(iconIndex%22)*62;c.y=24+Math.floor(iconIndex/22)*66;c.description='Lucide outline icon · 24px grid · 1.65 stroke · ISC / Feather MIT licenses included';iconComponents[name]=c;iconIndex++;
 }
 const library={};const propertyMaps={};const propertyDefaults={};
 async function render(n,parent,theme,meta){
  if(n.kind==='instance'){
   const component=library[n.component]?.[theme]?.[n.variant];if(!component)throw new Error('缺少组件 '+n.component+' / '+n.variant);
   const node=component.createInstance();node.name=n.name;parent.appendChild(node);
   const propMap=propertyMaps[n.component],props={};
   for(const [key,val] of Object.entries({...propertyDefaults[n.component][theme][n.variant],...(n.props||{})}))if(propMap[key])props[propMap[key]]=key.toLowerCase().includes('icon')&&iconComponents[val]?iconComponents[val].id:val;
   for(const [key,val] of Object.entries(n.overrides||{}))if(typeof val==='boolean'&&propMap[key])props[propMap[key]]=val;
   if(Object.keys(props).length)node.setProperties(props);
   for(const [key,o] of Object.entries(n.overrides||{}))if(typeof o==='object'){
    const nested=node.findAll(x=>x.type==='INSTANCE'&&x.name===key);
    for(const x of nested){if(o.variant)x.swapComponent(library[key][theme][o.variant]);const p={};for(const [a,b]of Object.entries({...propertyDefaults[key][theme][o.variant],...(o.props||{})}))p[propertyMaps[key][a]]=b;if(Object.keys(p).length)x.setProperties(p);if(o.visible!==undefined)x.visible=o.visible;}
   }
   if(n.width||n.height)node.resize(n.width||node.width,n.height||node.height);
   sizeChild(node,n,parent);if(n.boolProp)meta.push({node,key:n.boolProp,type:'BOOLEAN',value:node.visible,field:'visible'});
   return node;
  }
  if(n.kind==='text'){
   const node=figma.createText();node.fontName={family:fontFamily,style:weights[DESIGN.types[n.role][2]]};node.characters=n.text;node.name=n.name;
   await node.setTextStyleIdAsync(types[n.role].id);node.fills=[paint(n.color,theme)];node.textAutoResize='WIDTH_AND_HEIGHT';parent.appendChild(node);
   if(parent.layoutMode==='VERTICAL'||n.grow){node.textAutoResize='HEIGHT';node.layoutSizingHorizontal='FILL';}
   if(n.width){node.resize(n.width,node.height);node.textAutoResize='HEIGHT';}
   if(n.lines){node.textTruncation='ENDING';node.maxLines=n.lines;}
   if(n.textAlign)node.textAlignHorizontal=n.textAlign;
   if(n.prop)meta.push({node,key:n.prop,type:'TEXT',value:n.text,field:'characters'});
   return node;
  }
  if(n.kind==='icon'){
   const node=iconComponents[n.icon].createInstance();node.name=n.icon;node.rescale(n.width/24);parent.appendChild(node);colorNode(node,n.color,theme);
   if(n.prop)meta.push({node,key:n.prop,type:'INSTANCE_SWAP',value:iconComponents[n.icon].id,field:'mainComponent'});
   if(n.boolProp)meta.push({node,key:n.boolProp,type:'BOOLEAN',value:true,field:'visible'});
   return node;
  }
  const node=figma.createFrame();node.layoutMode=n.dir==='H'?'HORIZONTAL':'VERTICAL';node.primaryAxisSizingMode='AUTO';node.counterAxisSizingMode='AUTO';
  node.primaryAxisAlignItems=n.justify||'MIN';node.counterAxisAlignItems=n.align||'MIN';
  node.setBoundVariable('itemSpacing',gaps[n.gap||0]);
  const pd=padding(n.pad);node.setBoundVariable('paddingTop',gaps[pd[0]]);node.setBoundVariable('paddingRight',gaps[pd[1]]);node.setBoundVariable('paddingBottom',gaps[pd[2]]);node.setBoundVariable('paddingLeft',gaps[pd[3]]);
  style(node,n,theme,parent);
  if(n.width&&!n.fillWidth)node.layoutSizingHorizontal='FIXED';if(n.height)node.layoutSizingVertical='FIXED';
  if(parent)sizeChild(node,n,parent);
  for(const child of n.children)await render(child,node,theme,meta);
  if(n.scroll){node.overflowDirection='VERTICAL';node.clipsContent=true;}
  if(n.boolProp)meta.push({node,key:n.boolProp,type:'BOOLEAN',value:true,field:'visible'});
  return node;
 }
 async function text(parent,name,value,role='Body',theme='Dark'){return render({kind:'text',name,text:value,role,color:role==='Metadata'?'text-muted':'text-primary'},parent,theme,[]);}
 const frame=(name,width,gap=16,pad=32,fill='detail-surface')=>({kind:'frame',name,width,dir:'V',gap,pad,fill,children:[]});
 const start=await render(frame(prefix+' / Getting started',1440,12,32),page,'Dark',[]);start.x=baseX;start.y=baseY-300;
 await text(start,'Title','Notice Hub / 校园通知','Title');
 await text(start,'Intro','每天打开，快速浏览，安心处理。面向高校学生的桌面通知阅读应用。');
 await text(start,'Guide','01 深浅色主界面   →   02 窄屏适配与状态   →   03 设计系统与组件库','Metadata');
 await text(start,'Version','v1.0 · 1440 × 900 · 示例数据 · Noto Sans SC · 每个组件支持 Theme / State 变体','Metadata');
 made.push(start);
 progress('2 / 5  创建组件与变体…');
 let cy=baseY+4400;
 for(const [idx,def]of DESIGN.components.entries()){
  progress('2 / 5  '+(idx+1)+' / '+DESIGN.components.length+'  '+def.name);
  const doc=await render(frame(prefix+' / '+def.name+' documentation',1440,12,32),page,'Dark',[]);doc.x=baseX;doc.y=cy;
  await text(doc,'Component title',def.name,'Title');await text(doc,'Usage',def.notes,'Body');
  const metas=[],variants=[];library[def.name]={Dark:{},Light:{}};propertyDefaults[def.name]={Dark:{},Light:{}};
  const stateNames=Object.keys(def.variants);
  for(const theme of ['Dark','Light'])for(const state of stateNames){
   const local=[];const root=await render(def.variants[state],page,theme,local);
   const c=figma.createComponentFromNode(root);c.name='Theme='+theme+', State='+state;c.description=def.notes;variants.push(c);library[def.name][theme][state]=c;propertyDefaults[def.name][theme][state]=Object.fromEntries(local.map(m=>[m.key,m.value]));
   for(const m of local){if(m.node.id===root.id)m.node=c;metas.push(m);}
  }
  const set=figma.combineAsVariants(variants,page);set.name=def.name;set.description=def.notes;set.fills=[paint('app-canvas','Dark')];set.strokes=[];
  const props={};for(const m of metas){if(!props[m.key])props[m.key]=set.addComponentProperty(m.key,m.type,m.value);m.node.componentPropertyReferences={...(m.node.componentPropertyReferences||{}),[m.field]:props[m.key]};}propertyMaps[def.name]=props;
  const maxW=Math.max(...variants.map(v=>v.width)),maxH=Math.max(...variants.map(v=>v.height));
  const columns=maxW>620?1:2;variants.forEach((c,k)=>{c.x=24+(k%columns)*(maxW+32);c.y=24+Math.floor(k/columns)*(maxH+24);});
  set.resize(48+columns*maxW+(columns-1)*32,48+Math.ceil(variants.length/columns)*(maxH+24)-24);set.x=baseX;set.y=cy+doc.height+20;
  cy=set.y+set.height+64;made.push(doc,set);
 }
 progress('3 / 5  组装主界面与适配稿…');
 const screenFrames=[];
 const positions=[[0,0],[1560,0],[0,1080],[900,1080],[1330,1080]];
 for(const [idx,s]of DESIGN.screens.entries()){
  const root=await render(s.node,page,s.theme,[]);root.name=prefix+' / '+s.name;root.x=baseX+positions[idx][0];root.y=baseY+positions[idx][1];root.clipsContent=true;screenFrames.push(root);made.push(root);
 }
 // Prototype navigation for theme preview and compact reader/back.
 const navigate=async(node,destination)=>node.setReactionsAsync([{trigger:{type:'ON_CLICK'},actions:[{type:'NODE',destinationId:destination.id,navigation:'NAVIGATE',transition:{type:'DISSOLVE',duration:.15,easing:{type:'EASE_OUT'}},preserveScrollPosition:false}]}]);
 for(let k=0;k<2;k++){
  const sun=screenFrames[k].findOne(n=>n.type==='INSTANCE'&&n.name==='Sun');if(sun)await navigate(sun,screenFrames[1-k]);
 }
 const mobileRows=screenFrames[3].findAll(n=>n.type==='INSTANCE'&&n.name==='Notification Row');for(const n of mobileRows)await navigate(n,screenFrames[4]);
 const back=screenFrames[4].findOne(n=>n.type==='INSTANCE'&&n.name==='Button');if(back)await navigate(back,screenFrames[3]);
 // Feedback patterns use actual component instances in a documented panel.
 const feedback=await render(frame(prefix+' / Reader states',1440,24,32),page,'Dark',[]);feedback.x=baseX+2080;feedback.y=baseY+1080;
 await text(feedback,'Heading','阅读与结果状态','Title');
 for(const [c,v]of [['Empty State','NoSelection'],['Empty State','NoResults'],['Loading State','Reader'],['Error State','Network'],['Error State','NotFound']]){
  await text(feedback,c+' '+v,c+' / '+v,'Metadata');await render({kind:'instance',name:c,component:c,variant:v,props:{}},feedback,'Dark',[]);
 }made.push(feedback);
 progress('4 / 5  创建设计规范与色板…');
 const foundations=await render(frame(prefix+' / Foundations',1440,24,32),page,'Dark',[]);foundations.x=baseX;foundations.y=baseY+2160;
 await text(foundations,'Title','Foundations / 设计系统','Title');
 await text(foundations,'Token architecture','基础色 → 语义色引用。Dark / Light 使用独立单模式集合；组件 Theme 变体切换。圆角、间距均绑定变量。','Body');
 for(const theme of ['Dark','Light']){
  await text(foundations,'Theme',theme+' / 语义颜色','Section');
  const names=Object.keys(DESIGN.themes[theme]).filter(n=>!['transparent','progress-surface','background','surface-raised'].includes(n));
  for(let a=0;a<names.length;a+=6){
   const row=await render({kind:'frame',name:'Swatch row',dir:'H',gap:16,pad:0,children:[]},foundations,'Dark',[]);
   for(const name of names.slice(a,a+6)){
    const cell=await render(frame(name,208,6,0),row,'Dark',[]);cell.fills=[];
    await render({kind:'frame',name:'Color',width:208,height:32,dir:'H',gap:0,pad:0,radius:4,fill:name,children:[]},cell,theme,[]);
    await text(cell,'Token',name,'Label');await text(cell,'Hex',DESIGN.themes[theme][name],'Label');
   }
  }
 }
 await text(foundations,'Typography','Typography / Noto Sans SC','Section');
 for(const [role,[size,lh,weight]]of Object.entries(DESIGN.types))await text(foundations,'Type '+role,role+' '+size+'/'+lh+' '+weight+' · 校园通知，集中有序。',role);
 await text(foundations,'Spacing','Spacing / '+DESIGN.spaces.join(' · ')+' px','Body');
 await text(foundations,'Radius','Radius / 4 标签 · 6 控件 · 7 列表与附件 · 8 图标容器 · 10 应用窗口 · 12 浮层','Body');
 await text(foundations,'Shadows','Elevation / 仅 Popover 使用 0 8 24 / 24% 黑色投影；行与阅读区不使用阴影。','Body');
 made.push(foundations);
 // Place all foundations before icon/component library, allowing the documentation to hug content.
 const libraryShift=Math.max(0,foundations.y+foundations.height+64-iconRoot.y);
 if(libraryShift>0){iconRoot.y+=libraryShift;for(const n of made)if(n!==foundations&&n!==iconRoot&&n.y>=baseY+4400)n.y+=libraryShift;}
 const handoff=await render(frame(prefix+' / Developer handoff',1440,16,32),page,'Dark',[]);handoff.x=baseX+1560;handoff.y=baseY+2160;
 await text(handoff,'Title','Developer handoff / 开发交付','Title');
 const notes=[
  '布局：1440×900，Sidebar 282 / List 574 / Reader 584。Global Toolbar 56px；列表行 86px；阅读工具栏 44px；阅读内容左右内边距 32px。列表与正文各自滚动，工具栏固定。',
  '响应式：≥1280 三栏；768–1279 列表与可返回详情，侧栏缩为72px；390 单栏，打开通知进入详情。保持 14–15px 正文，触控控件扩大到至少44px。',
  '组件 API：每个组件集提供 Theme=Dark/Light、State 以及适用的 TEXT / BOOLEAN / INSTANCE_SWAP 属性。替换图标使用组件属性；不 Detach 实例。',
  '全部=/notices；未读=read=0；收藏=favorite=1；重要=min_score=70；来源=source=<id>。保留 q/category/source/min_score/date_from/deadline_status/read/favorite/page/page_size；筛选变更重置页码。',
  '选中通知只改变阅读上下文；详情成功加载后按 notice id 去重自动已读。收藏操作不打开通知；失败时回滚视觉状态并显示可重试反馈。',
  'Search：Ctrl K 聚焦；300ms debounce；Escape 清空或关闭；AbortController、外部 signal、15s timeout 和 cleanup 不变。后台刷新保留缓存和滚动位置。',
  '截止时间：按 Asia/Shanghai 比较；相对标签提示完整时间。过期为中性；无 deadline 不显示。不把时间状态和重要评分混为一谈。',
  '附件：filename / url / type；无文件大小则省略。文件名保持原名；长名可截断但有完整提示。不安全 URL 不可下载。',
  '错误：NETWORK_ERROR、TIMEOUT、HTTP_ERROR、NOT_FOUND 使用独立文案。ABORTED 静默。404=通知不存在 + 返回列表，不能显示为服务离线。',
  '可访问性：文本与背景目标4.5:1；焦点2px；图标按钮有可访问名称；未读点伴随语义状态；选中项使用aria-current，异步反馈aria-live。↑↓ 浏览通知，Enter 打开。',
  '此设计为独立提案，未修改产品行为或路由。预览数据为排版示例。应在真实内容与字体环境中完成最终 Figma / 实现验收。'
 ];for(const [k,n]of notes.entries())await text(handoff,'Rule '+(k+1),String(k+1).padStart(2,'0')+'  '+n,'Body');made.push(handoff);
 progress('5 / 5  检查结构与组件引用…');
 const broken=[];for(const n of made)if(!Number.isFinite(n.width)||!Number.isFinite(n.height))broken.push(n.id);
 if(broken.length)throw new Error('检测到无效尺寸：'+broken.join(','));
 const count=Object.values(library).reduce((n,themes)=>n+Object.values(themes).reduce((a,states)=>a+Object.keys(states).length,0),0);
 figma.currentPage.selection=[screenFrames[0]];figma.viewport.scrollAndZoomIntoView([screenFrames[0]]);
 figma.ui.postMessage({text:'已完成：5 个界面、'+DESIGN.components.length+' 个组件集 / '+count+' 个变体、深浅色变量、设计规范与状态页。\n\n可关闭本窗口开始编辑。请在 Figma 中检查文字换行与滚动效果。'});
}
