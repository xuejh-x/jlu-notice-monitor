# 吉林大学网站适配修复 B7 报告

验收时间：2026-10-15T23:05:05.940624+08:00。完整 B7 有界交付；保留所有外部阻塞及未验证能力。

本轮复核全部 112 个原 P3 入口，并从已保存官方页面补发现 4 个‘人才招聘’入口，共 116 个。59 个发现缺口（15 个原受阻、44 个原未发现栏目）与 308 条原始无官网行另建台账，范围重叠，不相加计算覆盖率。没有正式启用来源、触碰正式 SQLite、部署 Cloud、推送 GitHub、发布或安装客户端。OA 按用户要求零请求。

## 1. 实际数量与能力边界

| 指标 | 数量 |
| --- | ---: |
| 原 P3 入口 / 新发现入口 | 112 / 4 |
| 样本通过，仍有能力限制 | 80 |
| 样本仍待修复或缺少可靠元信息 | 10 |
| 访问受阻 / 栏目权限受限 | 3 / 2 |
| 列表模板仍不支持 | 1 |
| 有零记录证据的当前空栏目 | 2 |
| 单篇文章 / 静态招聘说明 / 外部平台引用 | 11 / 3 / 1 |
| 混合首页，范围待确认 | 3 |
| 完全通过全部运行环境 / 正式准入 | 0 / 0 |
| 独立禁用候选配置 | 101 |
| 列表页记录 / 按栏目去重的列表通知记录 | 153 / 1773 |
| 详情样本 / 四项独立对照通过 | 253 / 236 |
| 两轮隔离稳定性回放通过 | 90 |
| HTTP 发起尝试 / 逻辑缓存条目 / HTML 哈希检查 | 676 / 675 / 544 |
| 新增有官方依据站点 / 合并库存 URL / 库存主机 | 2 / 182 / 166 |

每栏目最多两页、三篇详情；不足三篇全检。部分正文只是附件或图片引用，端点下载、OCR、全历史均未验证。‘样本通过’需要列表独立召回对照、标题、日期、正文、附件 DOM 对照、分页边界及隔离重放，HTTP 200 或非空不能单独通过。隔离重放使用已经解析的样本，生产策略与真正 Cloud/feed、已安装 Desktop fallback 并未实跑。

所有 116 个入口均有范围/访问/预览结论；15 个引用对象无需作为独立列表适配，3 个混合首页没有确定监控范围。剩余适配对象中没有因为未取到样本而伪报通过。59 个发现入口全部完成限定深度检查，但未发现栏目不等于没有通知。

## 2. 本批实际修复

- VSB 文章标题、发布日期：修复已观察的 content-bt、ti/author、readtitle、item_biaoti、biaoti、#Title、表格 pubtime_publisher、匿名居中元信息及 view-title/view-info。只在文章范围、正文之前读取；正文事件日期与缺少的发布日期不补造。nav01 只为有明确文章标题/时间结构且无菜单链接的模板读取元信息，普通导航仍被排除。
- 表格与定义列表复用现有高级选择器：附属中学、边疆考古、哲学基础理论、高教所均有独立候选，未为各站新增专用爬虫。哲学列表显示日期与静态属性可能不一致，详情日期未出现仍保留未确认。
- WordPress 复用规则：只读取 article.type-post 的正文、文章头标题与 ISO datetime；只提取同一文章中带‘相关附件:N’标题的附件列表，不混入网站页脚、分类或标签。附件仅引用，不下载。
- WordPress 有界分页：支持同源同栏目 /page/正整数，保留稳定查询参数校验；跨栏目、跨站、认证信息、HTTP 降级、伪数字与路径逃逸继续拦截。审计拒绝把 NEXT_PAGE_OUTSIDE_COLUMN 等安全停止误算分页通过；第二页已真实补证。
- 招生通知误合并：复试名单与拟录取名单、普通公示与显式第二批分别保留；URL/public_id 优先级、14 天窗口、0.92 阈值、来源关系和用户状态不变。两组真实样本回放由 2 条恢复为 3 条独立记录，第二轮没有重复新增。没有批量修正正式旧数据。
- 栏目发现：修复‘人才招聘’标签遗漏。缓存内发现并检查人才办、经济学院、交通学院、出版社四个明确入口；经济学院样本通过，其余三个是长期招聘/联系说明页。静态说明不标为已支持列表。
- 审计对照纠正：资产处侧栏新闻不再计入当前栏目召回；原 11 个单篇文章引用独立分类，其中 8 个旧 JSP 引用当前权限受限仍保留限制。3 个首页不按混合新闻强行准入。

可复用代码差异见 [application-changes.diff](jlu-fix-b7/application-changes.diff)，实际四个应用文件有变化；source preview、安全校验、执行策略、数据库模型和 UI 未变更。

## 3. 发现缺口与机构官网补证

四个官方目录、学校主页本轮重新取得快照；59 个指定入口各首页加至多三个明确相关一级入口，遗漏的更深入口逐条保存。8 次定向检索只接受官方原页补证；外部转载、百科、企业聚合与冒用学校内容的博彩站未纳入、未抓取。

原受阻 15 个入口：10 个 TLS EOF 提前关闭（不同于证书有效期失败）、第一医院服务器断连、理论法学站超时、附中实验学校证书验证失败、图书馆动态空壳、OA 暂缓，各保留完整错误链。robots 获取受阻时没有继续正文请求；确定性证书问题未关闭验证。

图书馆历史 robots 的 Disallow:/ 原文保留。本轮 HTTPS robots 为 404，按当前可观察规则只获取一次首页；页面是动态空壳，未执行脚本或猜测 API、未绕过访问控制，仍没有已验证通知栏目。不能沿用旧 robots 结论假装从未复核，也不能据首页 200 宣称支持。

补证两个官网：吉林大学出版社 https://press.jlu.edu.cn/index.htm（联系页、简介和‘吉林大学出版社有限责任公司’页脚自证）；国家地球物理探测仪器工程技术研究中心 https://nercgei.jlu.edu.cn/index.htm（中心简介明确依托吉林大学）。后者原官方目录链接回研究机构目录，本次记录正确站点作为替代发现依据，不把两站 URL 当作协议别名强合并。

原始 units.json 确有 308 条 site_url 为空、298 个不同名称，其中附中、附小、附中实验学校 3 条在补充记录已有 URL。因此旧摘要 305 与原始空行口径不同，本轮同时保存两者，不覆盖历史。298 个名称也不等于 298 个独立单位，重复‘综合办公室’等不凭名称合并。

机构行处理结果：{'OFFICIAL_SITE_UNCONFIRMED': 303, 'SHARED_OFFICIAL_UNIT_PAGE_CONFIRMED': 1, 'PREVIOUS_SUPPLEMENT_ALREADY_IDENTIFIED_URL': 3, 'OFFICIAL_WEBSITE_SELF_IDENTITY_CONFIRMED': 1}。出版社官网已自证；行政服务中心确认是校长办公室共享页面，未推断独立站点。附中实验学校仅 URL 已知、证书受阻；东荣/莱姆顿/应用技术学院和两家校管企业的补充官方新闻/公开信息没有证明独立官网。其他条目均保留各自目录 URL、时间与未找到官方链接的限定原因，未执行 308 次独立全网查询。

逐行记录见 [unknown-unit-ledger.csv](jlu-fix-b7/unknown-unit-ledger.csv)、[discovery-gap-ledger.csv](jlu-fix-b7/discovery-gap-ledger.csv)、[新增库存](jlu-b7-site-inventory.csv)。原 44 个缺口中学工、创新创业通知现可从首页发现，但属于已有候选，不重复计为新栏目。

## 4. 仍未解决的原因与优先级

- P0：本批完整后端回归通过；OA 按用户要求暂缓，截图‘部分失败’与系统网络问题不在本批恢复。真实 Cloud/feed、已安装客户端状态仍另行验收。
- P1：服务器/TLS/robots 前置条件受阻的管理服务入口等待可访问环境或站点修复；缺少发布日期与重复发布语义不得通过猜测时间或放宽去重消除。正式来源准入仍需独立范围。
- P2：附属中学、高教所等特殊列表已恢复；新发现经济学院人才招聘样本通过。交通学院长期招聘说明没有按通知列表启用。各批学院剩余限制继续保留 B6 报告。
- P3：哲学中心、廉政、集成光电子三栏、汽车底盘实验室缺少可靠发布日期或仅有上传时间；医院/理论化学旧镜像包含乱码，医院附件是带损坏文本的 Teleport JavaScript 入口，不执行脚本恢复文件。
- P3：东北振兴页面错误闭合使通知列表落在 header 祖先内；现有导航保护正确拒绝。需站点修复 DOM 或另行实现带可审查安全边界的专门规则，不能全局放行 header。智能仪器四条通知全指向微信，未抓外部平台。
- P3：数量经济旧 list.php?SID=1 仍 404；同一官方首页明确链接的新 /xgxw1/zxtz.htm 已独立验证，旧地址不重试、不假称重定向已修好。后勤集团、测试中心旧列表明确权限受限，不登录。
- 重复候选：医院传染病两条同标题/日期/正文，可能为原站重复发布；人兽共患病 2017 招聘同名但正文版本不同，需人工确定转载/修订身份。保留 URL、正文哈希和关系，不在正式库合并或拆分。

B7 栏目间同 URL 组 33，不同 URL 同标题/日期候选组 29；与 B6 快照共有 URL 组 0。这是跨栏目引用/转载候选，不能当成数据库重复通知数量。

## 5. 逐栏结论（含全部旧失败）

| 机构 / 栏目 | 原状态 | 当前结论 | 原因或剩余问题 | 证据 |
| --- | --- | --- | --- | --- |
| 党委巡视工作办公室 / [通知公告](https://dwxcb.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-f80d3ae13dc4](jlu-fix-b7/results/p3-f80d3ae13dc4.json) |
| 党委宣传部 / [通知公告](https://xcb.jlu.edu.cn/whjs/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-63ff349131e1](jlu-fix-b7/results/p3-63ff349131e1.json) |
| 党委宣传部 / [通知公告](https://xcb.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-2d092f512c10](jlu-fix-b7/results/p3-2d092f512c10.json) |
| 发展规划处 / [通知 公告](https://dev.jlu.edu.cn/ggdt/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-d7ea2bd5b29a](jlu-fix-b7/results/p3-d7ea2bd5b29a.json) |
| 地质调查项目管理办公室（地质调查研究院、矿产资源研究院） / [通知快讯](https://ddy.jlu.edu.cn/tzkx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-df49160ba131](jlu-fix-b7/results/p3-df49160ba131.json) |
| 地质调查项目管理办公室（地质调查研究院、矿产资源研究院） / [通知公告](https://ddy.jlu.edu.cn/tzkx/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-3e3193ebc99c](jlu-fix-b7/results/p3-3e3193ebc99c.json) |
| 人力资源处 / [通知 动态](https://rsgl.jlu.edu.cn/tzdt.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-58b5da329790](jlu-fix-b7/results/p3-58b5da329790.json) |
| 人力资源处 / [招聘信息](https://rsgl.jlu.edu.cn/zpxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-b4bf49021cd7](jlu-fix-b7/results/p3-b4bf49021cd7.json) |
| 人力资源处 / [公告公示](https://rsgl.jlu.edu.cn/gggs.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-a12c9fdf5402](jlu-fix-b7/results/p3-a12c9fdf5402.json) |
| 博士后工作办公室 / [招聘信息](https://bsh.jlu.edu.cn/zpxx.htm) | 失败 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-064a4d605439](jlu-fix-b7/results/p3-064a4d605439.json) |
| 国际合作与交流处 / [相关公示](https://oic.jlu.edu.cn/hzbx2/xggs.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-79dae7a36e30](jlu-fix-b7/results/p3-79dae7a36e30.json) |
| 国际合作与交流处 / [通知公告](https://oic.jlu.edu.cn/zytg1/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-be94a971ce81](jlu-fix-b7/results/p3-be94a971ce81.json) |
| 资产管理处 / [通知公告](https://zcgl.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-81ced94833ac](jlu-fix-b7/results/p3-81ced94833ac.json) |
| 资产管理处 / [自行采购项目公告](https://zcgl.jlu.edu.cn/zxcgxmgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-f973305063fd](jlu-fix-b7/results/p3-f973305063fd.json) |
| 后勤处 / [通知公告](https://hqc.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-26ed334f996e](jlu-fix-b7/results/p3-26ed334f996e.json) |
| 后勤处 / [采购公示与采购结果公告](https://hqc.jlu.edu.cn/cggsycgjggg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-717cb1dd0cc9](jlu-fix-b7/results/p3-717cb1dd0cc9.json) |
| 保卫处、党委保卫部 / [通知公告 /NOTICES](https://bwc.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-611033d52dce](jlu-fix-b7/results/p3-611033d52dce.json) |
| 离退休工作处 / [教学信息](https://ltxc.jlu.edu.cn/lndx/jxxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-ec56189cf7e4](jlu-fix-b7/results/p3-ec56189cf7e4.json) |
| 离退休工作处 / [通知公告](https://ltxc.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-222ec72508f6](jlu-fix-b7/results/p3-222ec72508f6.json) |
| 政策与法规办公室 / [通知公告](https://zcyfg.jlu.edu.cn/sylm/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-598e7296ed82](jlu-fix-b7/results/p3-598e7296ed82.json) |
| 基础设施建设办公室 / [通知公告](https://jjb.jlu.edu.cn/bmxw/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-fabc7ba49bf1](jlu-fix-b7/results/p3-fabc7ba49bf1.json) |
| 经营性资产改革和管理办公室 / [通知](https://jgb.jlu.edu.cn/dwgz/tz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-b5a06a58053e](jlu-fix-b7/results/p3-b5a06a58053e.json) |
| 经营性资产改革和管理办公室 / [有关通知](https://jgb.jlu.edu.cn/ygtz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-92fc799ee238](jlu-fix-b7/results/p3-92fc799ee238.json) |
| 附属学校管理办公室 / [通知中心 NOTICE](https://pjb.jlu.edu.cn/tzzx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-5d7be7001eb1](jlu-fix-b7/results/p3-5d7be7001eb1.json) |
| 附属学校管理办公室 / [工作通知](https://pjb.jlu.edu.cn/tzzx/gztz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-45f6501a5554](jlu-fix-b7/results/p3-45f6501a5554.json) |
| 附属学校管理办公室 / [通知公告](https://pjb.jlu.edu.cn/fsxxdw/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-aa40d6abd751](jlu-fix-b7/results/p3-aa40d6abd751.json) |
| 学生心理健康指导中心 / [通知公告](https://psy.jlu.edu.cn/xwzx/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-1046fa015dad](jlu-fix-b7/results/p3-1046fa015dad.json) |
| 大数据和网络管理中心 / [通知公告](https://nic.jlu.edu.cn/tzkx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-2dd321c9e62c](jlu-fix-b7/results/p3-2dd321c9e62c.json) |
| 档案馆 / [通知公告](https://dag.jlu.edu.cn/index/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-07989e4e3e51](jlu-fix-b7/results/p3-07989e4e3e51.json) |
| 继续教育管理办公室 / [项目公示](https://jjglb.jlu.edu.cn/fxljy/xmgs.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-6081a6077fa8](jlu-fix-b7/results/p3-6081a6077fa8.json) |
| 继续教育管理办公室 / [通知公告](https://jjglb.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-fe70747cb90d](jlu-fix-b7/results/p3-fe70747cb90d.json) |
| 教师教学发展中心 / [通知公告](https://ctld.jlu.edu.cn/index/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-f504e1e18da8](jlu-fix-b7/results/p3-f504e1e18da8.json) |
| 妇委会 / [公告信息](https://fwh.jlu.edu.cn/ggxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-a1dc0cd69bc7](jlu-fix-b7/results/p3-a1dc0cd69bc7.json) |
| 白求恩医学部 / [通知公告](https://jdyxb.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-552953476abb](jlu-fix-b7/results/p3-552953476abb.json) |
| 医院管理处 / [通知公告](https://ywc.jlu.edu.cn/ylfwgl1/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-99066c319e6f](jlu-fix-b7/results/p3-99066c319e6f.json) |
| 医院管理处 / [通知公告](https://ywc.jlu.edu.cn/ylxzgl1/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-625011e2029d](jlu-fix-b7/results/p3-625011e2029d.json) |
| 医院管理处 / [通知公告](https://ywc.jlu.edu.cn/jxyxjy1/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-b944229a171b](jlu-fix-b7/results/p3-b944229a171b.json) |
| 医院管理处 / [通知公告](https://ywc.jlu.edu.cn/byhyxjy1/tzgg.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | ATTACHMENTS_NOT_INDEPENDENTLY_VERIFIED; ENCODING_REPLACEMENT_IN_SOURCE | [p3-43c4bdb1d4ae](jlu-fix-b7/results/p3-43c4bdb1d4ae.json) |
| 医院管理处 / [通知公告](https://ywc.jlu.edu.cn/xyggwsgl1/tzgg.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | SAME_TITLE_PUBLICATIONS_REQUIRE_IDENTITY_REVIEW | [p3-fa535e3ee14b](jlu-fix-b7/results/p3-fa535e3ee14b.json) |
| 东区事务办公室 / [通知公告](https://dqswb.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-cd417b7e833f](jlu-fix-b7/results/p3-cd417b7e833f.json) |
| 西区事务办公室 / [通知公告](https://hp.jlu.edu.cn/tztg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-36ce682535f5](jlu-fix-b7/results/p3-36ce682535f5.json) |
| 后勤服务集团 / [通知公告](https://hqserver.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1023) | 失败 | PERMISSION_RESTRICTED | COLUMN_PERMISSION_REQUIRED | [p3-918d011e17e4](jlu-fix-b7/results/p3-918d011e17e4.json) |
| 后勤服务集团 / [后勤服务集团关于召开科级干部竞聘考评会的通知](https://hqserver.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=11922&wbtreeid=1023) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-18762e4fb6bd](jlu-fix-b7/results/p3-18762e4fb6bd.json) |
| 后勤服务集团 / [关于饮食服务中心管理员（餐厅主任）岗位聘用的通知](https://hqserver.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=11909&wbtreeid=1023) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-bc6d4e3522a1](jlu-fix-b7/results/p3-bc6d4e3522a1.json) |
| 后勤服务集团 / [关于饮食服务中心管理员（餐厅主任）岗位聘用人选的公示](https://hqserver.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=11902&wbtreeid=1023) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-21df4a457282](jlu-fix-b7/results/p3-21df4a457282.json) |
| 考古与艺术博物馆 / [通知](https://aamuseum.jlu.edu.cn/tzkx/tz.htm) | 部分通过 | ACCESS_BLOCKED | TLS_EOF_CONNECTION_CLOSED | [p3-13f5df19e0b1](jlu-fix-b7/results/p3-13f5df19e0b1.json) |
| 综合极端条件高压科学中心 / [通知公告](https://lvpecf.jlu.edu.cn/index/tzgg.htm) | 部分通过 | ACCESS_BLOCKED | TLS_EOF_CONNECTION_CLOSED | [p3-b77c23b62583](jlu-fix-b7/results/p3-b77c23b62583.json) |
| 测试科学实验中心 / [通知通告](https://cszx.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1008) | 失败 | PERMISSION_RESTRICTED | COLUMN_PERMISSION_REQUIRED | [p3-9cfc1755cb34](jlu-fix-b7/results/p3-9cfc1755cb34.json) |
| 测试科学实验中心 / [关于测试科学实验中心推荐业务副主任考察人选的通知](https://cszx.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=1166&wbtreeid=1008) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-92d95ca9b5e9](jlu-fix-b7/results/p3-92d95ca9b5e9.json) |
| 测试科学实验中心 / [【转发-校内通知】关于张伟职务聘任的通知](https://cszx.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=1093&wbtreeid=1008) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-a6c4eb02b91d](jlu-fix-b7/results/p3-a6c4eb02b91d.json) |
| 测试科学实验中心 / [关于测试科学实验中心主任考察人选的通知](https://cszx.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=1179&wbtreeid=1008) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-5e75b78d19d0](jlu-fix-b7/results/p3-5e75b78d19d0.json) |
| 测试科学实验中心 / [关于电子显微镜中心寒假期间运行通知](https://cszx.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=1197&wbtreeid=1008) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-9031f1a975a2](jlu-fix-b7/results/p3-9031f1a975a2.json) |
| 测试科学实验中心 / [关于拟将张尊昊同志转为中共预备党员的公示](https://cszx.jlu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=1101&wbtreeid=1008) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-2472c2f95b44](jlu-fix-b7/results/p3-2472c2f95b44.json) |
| 长白山实验室 / [通知公告](https://cbslab.jlu.edu.cn/xwzx/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-fc6bb7747414](jlu-fix-b7/results/p3-fc6bb7747414.json) |
| 国家教材建设重点研究基地（高等学校理学教材研究） / [新闻通知](https://nrcem.jlu.edu.cn/xwtz/xwdt.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-c1ad0a7cdcf9](jlu-fix-b7/results/p3-c1ad0a7cdcf9.json) |
| 国家教材建设重点研究基地（高等学校理学教材研究） / [通知公告](https://nrcem.jlu.edu.cn/xwtz/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-6057733eb6f0](jlu-fix-b7/results/p3-6057733eb6f0.json) |
| 国家教材建设重点研究基地（高等学校理学教材研究） / [会议通知](https://nrcem.jlu.edu.cn/xzzq/hytz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-a93aafad1fe0](jlu-fix-b7/results/p3-a93aafad1fe0.json) |
| 东北与东北亚研究院 / [通知公告](https://ncnas.jlu.edu.cn/xwdt/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-3d34c2ae440c](jlu-fix-b7/results/p3-3d34c2ae440c.json) |
| 东北民族研究中心 / [通知公告](https://dbmz.jlu.edu.cn/tzgg.htm) | 完全通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-1f12d3363e10](jlu-fix-b7/results/p3-1f12d3363e10.json) |
| 无机合成与制备化学全国重点实验室 / [通知](https://synlab.jlu.edu.cn/information/events) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-0669ddf88689](jlu-fix-b7/results/p3-0669ddf88689.json) |
| 无机合成与制备化学全国重点实验室 / [通知](https://synlab.jlu.edu.cn/archive/information/events) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-2a947afc9f1e](jlu-fix-b7/results/p3-2a947afc9f1e.json) |
| 无机合成与制备化学全国重点实验室 / [仪器公告](https://synlab.jlu.edu.cn/archive/information/events/instrument-announcement) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-b2b4060ce6db](jlu-fix-b7/results/p3-b2b4060ce6db.json) |
| 无机合成与制备化学全国重点实验室 / [实验室2025年度公开招聘专业技术人员 拟聘人选公示](https://synlab.jlu.edu.cn/2025/09/5203.html) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-9e34816e096b](jlu-fix-b7/results/p3-9e34816e096b.json) |
| 无机合成与制备化学全国重点实验室 / [2025年申请重点实验室开放课题基金的通知](https://synlab.jlu.edu.cn/2025/09/5172.html) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-9315876bd6fa](jlu-fix-b7/results/p3-9315876bd6fa.json) |
| 无机合成与制备化学全国重点实验室 / [2024年申请重点实验室开放课题基金的通知](https://synlab.jlu.edu.cn/2024/06/5016.html) | 无需适配 | SINGLE_ARTICLE_REFERENCE | Observed article route and saved page identify one article, not an independent notice list; not marked supported | [p3-9cc6eba0da5b](jlu-fix-b7/results/p3-9cc6eba0da5b.json) |
| 智能仪器与测控技术研究所 / [通知公告](https://iiimct.jlu.edu.cn/xwzx/tzgg.htm) | 失败 | EXTERNAL_PLATFORM_REFERENCES | All four observed entries link to WeChat; no same-site details. Platform fetch/auth/download not attempted; not marked supported | [p3-d631ccd9f522](jlu-fix-b7/results/p3-d631ccd9f522.json) |
| 吉林大学附属中学 / [通知公告](https://fszx.jlu.edu.cn/xwzx/tzgg.htm) | 失败 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-aec68cedee88](jlu-fix-b7/results/p3-aec68cedee88.json) |
| 吉林大学附属小学 / [通知公告](https://jdfx.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-91835e5c30a1](jlu-fix-b7/results/p3-91835e5c30a1.json) |
| 党委教师工作部 / [通知公告](http://jsgzb.jlu.edu.cn/tzgg.htm) | 完全通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-057482fcf4d1](jlu-fix-b7/results/p3-057482fcf4d1.json) |
| 白求恩医学部 / [研究生院通知](http://jdyxb.jlu.edu.cn/bqeyjsbgs/yjsjy/yjsytz.htm) | 失败 | VERIFIED_EMPTY_COLUMN | Explicit server-rendered zero-record/pager evidence, no fabricated notices | [p3-f0c724975201](jlu-fix-b7/results/p3-f0c724975201.json) |
| 西区事务办公室 / [教学信息](http://jwc.jlu.edu.cn/index.htm) | 部分通过 | HOMEPAGE_SCOPE_REVIEW | Original homepage mixes several sections; notice columns are validated separately, no automatic homepage admission | [p3-50b513692338](jlu-fix-b7/results/p3-50b513692338.json) |
| 未来科学国际合作联合实验室 / [新闻通知](http://icfs.jlu.edu.cn/xwtz/xw.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-acb2a085dfc4](jlu-fix-b7/results/p3-acb2a085dfc4.json) |
| 未来科学国际合作联合实验室 / [通知](http://icfs.jlu.edu.cn/xwtz/tz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-d26c079d5778](jlu-fix-b7/results/p3-d26c079d5778.json) |
| 未来科学国际合作联合实验室 / [通知公告](http://icfs.jlu.edu.cn/rcpy/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-e4a31bb7b4d2](jlu-fix-b7/results/p3-e4a31bb7b4d2.json) |
| 未来科学国际合作联合实验室 / [招聘信息](http://icfs.jlu.edu.cn/jrwm/zpxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-96349c12f2d5](jlu-fix-b7/results/p3-96349c12f2d5.json) |
| 未来科学国际合作联合实验室 / [首页 / 人才培养 / 通知公告](http://icfs.jlu.edu.cn/index.htm) | 部分通过 | HOMEPAGE_SCOPE_REVIEW | Original homepage mixes several sections; notice columns are validated separately, no automatic homepage admission | [p3-0f85aaa162f5](jlu-fix-b7/results/p3-0f85aaa162f5.json) |
| 边疆考古研究中心 / [通知公告](http://bjkg.jlu.edu.cn/tzgg.htm) | 失败 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-dbe97ad67104](jlu-fix-b7/results/p3-dbe97ad67104.json) |
| 数量经济研究中心 / [中心通知](http://jlucqe.jlu.edu.cn/list.php?SID=1) | 失败 | ACCESS_BLOCKED | HTTP_404 | [p3-86da28c02411](jlu-fix-b7/results/p3-86da28c02411.json) |
| 数量经济研究中心 / [中心通知](http://jlucqe.jlu.edu.cn/xgxw1/zxtz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-517983231abb](jlu-fix-b7/results/p3-517983231abb.json) |
| 中国国有经济研究中心 / [通知公告](http://ccpser.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-145fbc0028ac](jlu-fix-b7/results/p3-145fbc0028ac.json) |
| 哲学基础理论研究中心 / [中心通知](http://pftheory.jlu.edu.cn/zxxw1/zxtz.htm) | 失败 | SAMPLE_REVIEW_REQUIRED | DATE_NOT_INDEPENDENTLY_VERIFIED | [p3-dccdc07e027f](jlu-fix-b7/results/p3-dccdc07e027f.json) |
| 廉政研究院 / [通知公告](http://acre.jlu.edu.cn/xwdt/tzgg1.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | DATE_NOT_INDEPENDENTLY_VERIFIED | [p3-a137b207198f](jlu-fix-b7/results/p3-a137b207198f.json) |
| 协商治理研究院 / [通知公告](http://cppcc.jlu.edu.cn/zxdt/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-85735f6aeafc](jlu-fix-b7/results/p3-85735f6aeafc.json) |
| 集成光电子全国重点实验室 / [招生信息](http://sklio.jlu.edu.cn/rcpy/zsxx.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | DATE_NOT_INDEPENDENTLY_VERIFIED | [p3-531d956cfe39](jlu-fix-b7/results/p3-531d956cfe39.json) |
| 集成光电子全国重点实验室 / [招聘信息](http://sklio.jlu.edu.cn/zxns/zpxx.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | DATE_NOT_INDEPENDENTLY_VERIFIED | [p3-dc59edeed902](jlu-fix-b7/results/p3-dc59edeed902.json) |
| 集成光电子全国重点实验室 / [通知公告](http://sklio.jlu.edu.cn/index/tzgg.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | DATE_NOT_INDEPENDENTLY_VERIFIED | [p3-f24c497b7c18](jlu-fix-b7/results/p3-f24c497b7c18.json) |
| 高压与超硬材料全国重点实验室 / [招生信息](http://nlshm-lab.jlu.edu.cn/yjsjy/zsxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-3a9be451148b](jlu-fix-b7/results/p3-3a9be451148b.json) |
| 高压与超硬材料全国重点实验室 / [通知公告](http://nlshm-lab.jlu.edu.cn/yjsjy/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-bda802ae708b](jlu-fix-b7/results/p3-bda802ae708b.json) |
| 高压与超硬材料全国重点实验室 / [招聘信息](http://nlshm-lab.jlu.edu.cn/rczp/zpxx.htm) | 完全通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-8d31d6a0c1fb](jlu-fix-b7/results/p3-8d31d6a0c1fb.json) |
| 高压与超硬材料全国重点实验室 / [通知公告 Notice](http://nlshm-lab.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-d46a55c006bd](jlu-fix-b7/results/p3-d46a55c006bd.json) |
| 汽车底盘集成与仿生全国重点实验室 / [信息公告 >>](http://acib.jlu.edu.cn/xxgg.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | DATE_NOT_INDEPENDENTLY_VERIFIED; UPLOAD_TIME_PUBLICATION_UNCONFIRMED | [p3-a79bb2d1ffdf](jlu-fix-b7/results/p3-a79bb2d1ffdf.json) |
| 符号计算与知识工程教育部重点实验室 / [通知公告](http://scke.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-559bea095695](jlu-fix-b7/results/p3-559bea095695.json) |
| 分子酶学工程教育部重点实验室 / [室内通知/ Indoor notification](http://www.mee.jlu.edu.cn/index/sntz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-9279a878c7d7](jlu-fix-b7/results/p3-9279a878c7d7.json) |
| 病理生物学教育部重点实验室 / [公告通知](http://pathobiology.jlu.edu.cn/ggtz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-0768ea65e573](jlu-fix-b7/results/p3-0768ea65e573.json) |
| 人兽共患病研究教育部重点实验室 / [招聘信息](http://ghb.jlu.edu.cn/rczp/zpxx.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | SAME_TITLE_PUBLICATIONS_REQUIRE_IDENTITY_REVIEW | [p3-075bd0471b07](jlu-fix-b7/results/p3-075bd0471b07.json) |
| 人兽共患病研究教育部重点实验室 / [通知公告 notice](http://ghb.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-b9081fc300d9](jlu-fix-b7/results/p3-b9081fc300d9.json) |
| 地下水资源与环境教育部重点实验室 / [通知公告](http://klgre.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-43985ce4fe1b](jlu-fix-b7/results/p3-43985ce4fe1b.json) |
| 器官再造与移植教育部重点实验室（筹） / [通知公告](http://ort.jlu.edu.cn/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-be255c9b528c](jlu-fix-b7/results/p3-be255c9b528c.json) |
| 特种工程塑料教育部工程中心 / [通知](http://jusep.jlu.edu.cn/xwzx/tz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-8c83f402e628](jlu-fix-b7/results/p3-8c83f402e628.json) |
| 高等教育研究所 / [招生信息](http://gjs.jlu.edu.cn/zsjy/zsxx.htm) | 失败 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-0a00088dd271](jlu-fix-b7/results/p3-0a00088dd271.json) |
| 东北振兴发展研究院 / [通知公告](http://dbzx.jlu.edu.cn/xwdt/yjydt.htm) | 部分通过 | LIST_OR_PAGINATION_UNSUPPORTED | MALFORMED_HEADER_ANCESTOR_CONTAINS_NOTICE_LIST | [p3-5c626cbfdf19](jlu-fix-b7/results/p3-5c626cbfdf19.json) |
| 吉林大学国家发展与安全研究院 / [通知公告](http://indss.jlu.edu.cn/rcpy/tzgg.htm) | 失败 | VERIFIED_EMPTY_COLUMN | Explicit server-rendered zero-record/pager evidence, no fabricated notices | [p3-8a5615f2d971](jlu-fix-b7/results/p3-8a5615f2d971.json) |
| 吉林大学国家发展与安全研究院 / [首页 / 人才培养 / 通知公告](http://indss.jlu.edu.cn/index.htm) | 部分通过 | HOMEPAGE_SCOPE_REVIEW | Original homepage mixes several sections; notice columns are validated separately, no automatic homepage admission | [p3-8c4d7b0730cc](jlu-fix-b7/results/p3-8c4d7b0730cc.json) |
| 吉林大学国家发展与安全研究院 / [通知](http://indss.jlu.edu.cn/xwtz/tz.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-e088fc12870c](jlu-fix-b7/results/p3-e088fc12870c.json) |
| 理论化学研究所 / [招生信息](http://itc.jlu.edu.cn/yjspy/zsxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-06d121ac0e9b](jlu-fix-b7/results/p3-06d121ac0e9b.json) |
| 理论化学研究所 / [通知公告](http://itc.jlu.edu.cn/dtxx/tzgg.htm) | 部分通过 | SAMPLE_REVIEW_REQUIRED | ENCODING_REPLACEMENT_IN_SOURCE | [p3-b6c8c6e200cd](jlu-fix-b7/results/p3-b6c8c6e200cd.json) |
| 原子与分子物理研究所 / [招生信息](http://iamp.jlu.edu.cn/rcpy/zsxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-276d57c8bed1](jlu-fix-b7/results/p3-276d57c8bed1.json) |
| 原子与分子物理研究所 / [教学信息](http://iamp.jlu.edu.cn/rcpy/jxxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-208e2a8cdba2](jlu-fix-b7/results/p3-208e2a8cdba2.json) |
| 原子与分子物理研究所 / [通知公告](http://iamp.jlu.edu.cn/dtxx/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-4a6ebc9fd5fc](jlu-fix-b7/results/p3-4a6ebc9fd5fc.json) |
| 原子与分子物理研究所 / [招聘信息](http://iamp.jlu.edu.cn/rczp/zpxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-6396551e0634](jlu-fix-b7/results/p3-6396551e0634.json) |
| 人兽共患病研究所 / [招聘信息](http://iz.jlu.edu.cn/rczp/zpxx.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-4f22b55d0c72](jlu-fix-b7/results/p3-4f22b55d0c72.json) |
| 人兽共患病研究所 / [通知公告](http://iz.jlu.edu.cn/index/tzgg.htm) | 部分通过 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [p3-3230ff7620b1](jlu-fix-b7/results/p3-3230ff7620b1.json) |
| 人才工作办公室、党委人才工作办公室 / [人才招聘](https://talent.jlu.edu.cn/rczp.htm) | 新发现未验证 | STATIC_RECRUITMENT_INFORMATION_PAGE | Captured page is ongoing recruitment/contact information with no chronological article list or publication metadata; no list adaptation admission | [recruitment-6d1c1bd9f0d1](jlu-fix-b7/results/recruitment-6d1c1bd9f0d1.json) |
| 经济学院 / [人才招聘](https://jjxy.jlu.edu.cn/szdw/rczp.htm) | 新发现未验证 | BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified | [recruitment-71ef1c4ae467](jlu-fix-b7/results/recruitment-71ef1c4ae467.json) |
| 交通学院 / [人才招聘](https://jt.jlu.edu.cn/szdw/rczp.htm) | 新发现未验证 | STATIC_RECRUITMENT_INFORMATION_PAGE | Captured page is ongoing recruitment/contact information with no chronological article list or publication metadata; no list adaptation admission | [recruitment-1121e0479a35](jlu-fix-b7/results/recruitment-1121e0479a35.json) |
| 吉林大学出版社有限责任公司 / [人才招聘](https://press.jlu.edu.cn/lxwm/rczp.htm) | 新发现未验证 | STATIC_RECRUITMENT_INFORMATION_PAGE | Captured page is ongoing recruitment/contact information with no chronological article list or publication metadata; no list adaptation admission | [recruitment-9beec40c661d](jlu-fix-b7/results/recruitment-9beec40c661d.json) |

## 6. 复现、回归与保留证明

最终逐栏 CSV：[jlu-b7-compatibility-report.csv](jlu-b7-compatibility-report.csv)；每行 JSON 包含请求 URL、实际时间、最终 URL、错误链、样本、正文/附件对照、分页、两轮内存库结果和代码清单。缓存为解码后的 HTML 证据，原始响应字节与完整文件未保存。

离线复现（零网络）：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/review_jlu_b7.py --input docs/jlu-fix-b7/recruitment-20261015 --output docs/jlu-fix-b7/reproduce-new-directory
```

该命令只读本批快照，缺少 URL 立即失败；改变代码需新输出目录，不能覆盖既有验收。线上采集脚本有逐条 checkpoint 和代码指纹，断点继续使用原缓存而不重试已确定限制。

| 检查 | 真实结果 |
| --- | --- |
| baseline | 533 passed, 1 skipped |
| regression-before | 5 failed, 399 passed |
| regression-before-wordpress-identity | 5 failed, 406 passed |
| targeted | 424 passed |
| final | 567 passed, 1 skipped |

最终完整后端 567 通过、1 跳过；跳过为未配置的外部 PostgreSQL 集成验证，没有连接外部数据库。针对性 424 通过，最后四项栏目发现/元信息位置边界测试由完整回归覆盖；完整回归已包含全部 34 个新增测试。前端未变更，因此未重复前端 test/lint/build。

原 1449 份受保护证据、7165 份 B6 文件及 9 份既有报告 SHA 均未变化；正式 sources.yaml SHA 为 `d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d`。程序全局数据库连接被拒绝，样本回放与 pytest 仅使用隔离数据。候选全部 disabled，Cloud/Desktop 策略与用户 ID、已读、收藏、来源关系保持。

测试生成器曾遇到 Windows 换行再生成校验误报，已改用既存 fixture/source SHA 保护；保留 collection 日志及 tooling-iterations.json。这些不是学校站点失败。原始首轮及各次离线结果均保留，未把中间缺少缓存的结果纳入最终失败统计。

B6 与 B7 两个大板块已分别交付；下一阶段应按需要选择正式来源准入、Cloud/feed 实机验收或外部站点条件恢复后复核。本轮停在 B7，不自动部署、补全历史、修改系统网络或更新客户端。
