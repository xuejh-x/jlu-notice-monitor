import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isTauri } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import { Pencil, Plus, RefreshCw, Rss, ShieldAlert, Trash2, TriangleAlert, X } from 'lucide-react'
import { useState } from 'react'
import {
  checkSource, createCloudSource, createSource, deleteSource, editSource,
  getSourceConfiguration, previewSource, promoteSource, reauthenticateSource,
  setCloudPolicy, setSourceEnabled, setSourceSubscription,
} from '../api/sources'
import { getCrawlerStatus } from '../api/crawler'
import { ApiError } from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { SourceIcon } from '../components/notice/SourceIcon'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { Input, Select, Toggle } from '../components/ui/Form'
import { useToast } from '../stores/toast'
import type { CloudSourceDraft, CrawlerSourceResult, SourceConfiguration, SourceDraft, SourceExecutionPolicy, SourceHealthState, SourceParser } from '../types'
import { relativeTime } from '../utils/format'
import { captureCrawlerCompletionBaseline, useCrawlerCompletionRefresh } from '../hooks/useCrawlerCompletionRefresh'

const healthLabels: Record<SourceHealthState, string> = {
  healthy: '运行正常', syncing: '正在同步', disabled: '已停用', needs_reauth: '需要重新登录',
  auth_error: '认证失败', parse_error: '解析失败', network_error: '网络异常', source_error: '来源异常',
  unsupported: '暂不支持', unconfigured: '等待首次检查', cloud_unconfigured: '云端尚未配置', authenticated: '已登录',
}

const executionPolicyLabels: Record<SourceExecutionPolicy, string> = {
  cloud_preferred: '云端优先',
  cloud_only: '仅云端',
  local_only: '仅本地',
}

function healthVariant(state: SourceHealthState): BadgeVariant {
  if (state === 'healthy' || state === 'authenticated') return 'success'
  if (state === 'needs_reauth' || state === 'unconfigured' || state === 'syncing') return 'warning'
  if (state === 'disabled' || state === 'cloud_unconfigured') return 'neutral'
  return 'danger'
}

const emptyDraft = (kind: 'public' | 'private'): SourceDraft => ({
  name: '', list_url: '', kind, parser: 'auto', parser_config: { pagination_limit: 1 },
  auth_type: kind === 'private' ? 'browser_session' : 'none', remember_credentials: false,
  allow_private_network: false,
})

function SourceEditor({ kind, initial, onClose }: { kind: 'public' | 'private'; initial?: SourceConfiguration; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [draft, setDraft] = useState<SourceDraft>(() => initial ? {
    name: initial.name, list_url: initial.base_url, kind, parser: initial.parser,
    parser_config: initial.parser_config, auth_type: initial.auth_type, login_url: initial.login_url ?? undefined,
    username: initial.username ?? undefined, remember_credentials: initial.password_saved,
    allow_private_network: initial.allow_private_network,
  } : emptyDraft(kind))
  const [advanced, setAdvanced] = useState(Boolean(initial && Object.keys(initial.parser_config).length > 1))
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof previewSource>> | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const update = <K extends keyof SourceDraft>(key: K, value: SourceDraft[K]) => {
    setDraft(current => ({ ...current, [key]: value })); setPreview(null); setMessage(null)
  }
  const updateSelector = (key: keyof SourceDraft['parser_config'], value: string | number) => {
    setDraft(current => ({ ...current, parser_config: { ...current.parser_config, [key]: value } })); setPreview(null)
  }
  const test = useMutation({
    mutationFn: () => previewSource(draft),
    onSuccess: result => { setPreview(result); setMessage(null) },
    onError: error => { setPreview(null); setMessage(error instanceof Error ? error.message : '测试失败') },
  })
  const save = useMutation({
    mutationFn: () => initial ? editSource(initial.id, draft, preview!.preview_token) : createSource(draft, preview!.preview_token),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['source-config'] }); toast(initial ? '来源已更新' : '来源已添加'); onClose() },
    onError: error => setMessage(error instanceof Error ? error.message : '保存失败'),
  })
  const privateSource = kind === 'private'
  return (
    <section aria-label={initial ? `编辑${initial.name}` : privateSource ? '添加私有来源' : '添加公开来源'} className="rounded-large border border-border bg-surface p-4 sm:p-5">
      <div className="flex items-center justify-between gap-4"><h3 className="text-section-heading text-text-primary">{initial ? '编辑来源' : privateSource ? '添加私有来源' : '添加公开来源'}</h3><Button size="icon" variant="ghost" onClick={onClose} aria-label="关闭来源编辑"><X className="h-4 w-4"/></Button></div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="text-sm text-text-secondary">名称<Input className="mt-1.5" value={draft.name} onChange={event => update('name', event.target.value)} /></label>
        <label className="text-sm text-text-secondary">通知列表 URL<Input className="mt-1.5" type="url" value={draft.list_url} onChange={event => update('list_url', event.target.value)} placeholder="https://example.edu/notice/" /></label>
        <label className="text-sm text-text-secondary">来源格式<Select className="mt-1.5" value={draft.parser} onChange={event => update('parser', event.target.value as SourceDraft['parser'])}><option value="auto">自动检测</option><option value="generic_html">HTML</option><option value="rss">RSS</option><option value="atom">Atom</option><option value="api">API (JSON)</option></Select></label>
        {privateSource && <label className="text-sm text-text-secondary">认证方式<Select className="mt-1.5" value={draft.auth_type} onChange={event => update('auth_type', event.target.value as SourceDraft['auth_type'])}><option value="browser_session">浏览器会话</option><option value="username_password">账号密码 / 手动登录</option><option value="basic">Basic Auth</option><option value="bearer">Bearer / API Token</option><option value="cookie">Cookie / Session</option><option value="custom_adapter">自定义适配器</option></Select></label>}
        {privateSource && <label className="text-sm text-text-secondary">登录 URL<Input className="mt-1.5" type="url" value={draft.login_url ?? ''} onChange={event => update('login_url', event.target.value)} /></label>}
        {privateSource && <label className="text-sm text-text-secondary">账号<Input className="mt-1.5" value={draft.username ?? ''} autoComplete="username" onChange={event => update('username', event.target.value)} /></label>}
        {privateSource && <label className="text-sm text-text-secondary">密码 / Token<Input className="mt-1.5" type="password" value={draft.password ?? ''} autoComplete="current-password" onChange={event => update('password', event.target.value)} /></label>}
      </div>
      {privateSource && <div className="mt-4 space-y-2 rounded-medium bg-surface-muted p-3 text-sm text-text-secondary"><label className="flex items-center justify-between gap-4"><span>记住账号密码（使用 Windows 本机安全存储）</span><Toggle checked={Boolean(draft.remember_credentials)} onClick={() => update('remember_credentials', !draft.remember_credentials)} /></label><label className="flex items-center justify-between gap-4"><span>允许访问本机所在的私有网络地址</span><Toggle checked={Boolean(draft.allow_private_network)} onClick={() => update('allow_private_network', !draft.allow_private_network)} /></label></div>}
      <button type="button" className="mt-4 text-sm font-medium text-accent-soft-text hover:underline" onClick={() => setAdvanced(value => !value)}>{advanced ? '收起高级解析配置' : '高级解析配置'}</button>
      {advanced && <div className="mt-3 grid gap-3 rounded-medium bg-surface-muted p-3 sm:grid-cols-2">{[
        ['item_selector', '通知项选择器'], ['title_selector', '标题选择器'], ['link_selector', '链接选择器'],
        ['date_selector', '发布日期选择器'], ['content_selector', '详情正文选择器'], ['attachment_selector', '附件选择器'], ['next_page_selector', '下一页选择器'],
      ].map(([key, label]) => <label key={key} className="text-sm text-text-secondary">{label}<Input className="mt-1.5" value={String(draft.parser_config[key as keyof SourceDraft['parser_config']] ?? '')} onChange={event => updateSelector(key as keyof SourceDraft['parser_config'], event.target.value)} /></label>)}</div>}
      <div className="mt-4 flex flex-wrap gap-2"><Button onClick={() => test.mutate()} disabled={!draft.name || !draft.list_url || test.isPending}>{test.isPending ? '正在测试…' : '测试并预览'}</Button><Button variant="primary" onClick={() => save.mutate()} disabled={!preview || save.isPending}>{initial ? '确认更新' : '确认添加'}</Button><Button variant="ghost" onClick={onClose}>取消</Button></div>
      {message && <p role="alert" className="mt-3 text-sm text-danger">{message}</p>}
      {preview && <div className="mt-4 rounded-medium border border-border bg-surface-muted p-3"><p className="text-sm font-medium text-text-primary">{preview.status === 'success' ? `找到 ${preview.found} 条通知` : '配置已验证，登录后继续测试解析'}</p>{preview.message && <p className="mt-1 text-sm text-text-secondary">{preview.message}</p>}<ol className="mt-2 space-y-1 text-sm text-text-secondary">{preview.items.map(item => <li key={item.url} className="truncate">{item.title}</li>)}</ol></div>}
    </section>
  )
}

const cloudEmptyDraft: CloudSourceDraft = {
  name: '', list_url: '', parser: 'auto', parser_config: { pagination_limit: 1 },
  category: 'other', crawl_interval_seconds: 3600, public_shared: true,
}

function CloudSourceEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [draft, setDraft] = useState<CloudSourceDraft>(cloudEmptyDraft)
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof previewSource>> | null>(null)
  const [advanced, setAdvanced] = useState(false)
  const [adminKey, setAdminKey] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const previewDraft: SourceDraft = {
    name: draft.name, list_url: draft.list_url, kind: 'public', parser: draft.parser,
    parser_config: { ...draft.parser_config, default_category: draft.category }, auth_type: 'none',
    remember_credentials: false, allow_private_network: false,
  }
  const update = <K extends keyof CloudSourceDraft>(key: K, value: CloudSourceDraft[K]) => {
    setDraft(current => ({ ...current, [key]: value })); setPreview(null); setMessage(null)
  }
  const updateSelector = (key: 'item_selector' | 'title_selector' | 'url_selector' | 'time_selector', value: string) => {
    setDraft(current => ({
      ...current,
      parser: 'generic_html',
      parser_config: { ...current.parser_config, type: 'html_selector', [key]: value },
    }))
    setPreview(null)
    setMessage(null)
  }
  const test = useMutation({
    mutationFn: () => previewSource(previewDraft),
    onSuccess: result => { setPreview(result); setMessage(null) },
    onError: error => { setPreview(null); setAdvanced(true); setMessage(error instanceof Error ? error.message : '测试失败') },
  })
  const create = useMutation({
    mutationFn: () => createCloudSource({ ...draft, parser_config: previewDraft.parser_config }, preview!.preview_token, adminKey),
    onSuccess: async result => {
      setAdminKey('')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['source-config'] }),
        queryClient.invalidateQueries({ queryKey: ['sources'] }),
      ])
      toast(result.promotion_reused ? '云端已有该来源，已完成桌面同步' : '云端共享来源已创建')
      onClose()
    },
    onError: error => { setAdminKey(''); setMessage(error instanceof Error ? error.message : '创建失败') },
  })
  return <section aria-label="添加云端共享来源" className="rounded-large border border-border bg-surface p-4 sm:p-5">
    <div className="flex items-center justify-between gap-4"><h3 className="text-section-heading text-text-primary">添加云端共享来源</h3><Button size="icon" variant="ghost" onClick={onClose} aria-label="关闭云端来源编辑"><X className="h-4 w-4"/></Button></div>
    <p className="mt-2 text-sm text-text-secondary">先测试抓取并确认预览，再使用一次性管理员密钥写入 Cloud Registry。</p>
    <div className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm text-text-secondary">名称<Input className="mt-1.5" value={draft.name} onChange={event => update('name', event.target.value)} /></label>
      <label className="text-sm text-text-secondary">URL<Input className="mt-1.5" type="url" value={draft.list_url} onChange={event => update('list_url', event.target.value)} placeholder="https://example.edu/notices" /></label>
      <label className="text-sm text-text-secondary">来源类型<Select className="mt-1.5" value={draft.parser} onChange={event => update('parser', event.target.value as SourceParser)}><option value="auto">自动检测</option><option value="generic_html">HTML</option><option value="rss">RSS</option><option value="atom">Atom</option><option value="api">API (JSON)</option></Select></label>
      <label className="text-sm text-text-secondary">分类<Select className="mt-1.5" value={draft.category} onChange={event => update('category', event.target.value)}><option value="other">其他</option><option value="algorithm_competition">算法竞赛</option><option value="cybersecurity_competition">网络安全竞赛</option><option value="innovation_competition">创新创业</option><option value="training">实训</option><option value="internship">实习</option><option value="research">科研</option><option value="postgraduate_recommendation">推免</option><option value="academic">教学</option></Select></label>
      <label className="text-sm text-text-secondary">抓取策略<Select className="mt-1.5" value={draft.crawl_interval_seconds} onChange={event => update('crawl_interval_seconds', Number(event.target.value))}><option value={900}>每 15 分钟</option><option value={1800}>每 30 分钟</option><option value={3600}>每小时</option><option value={21600}>每 6 小时</option><option value={86400}>每天</option></Select></label>
      <label className="flex items-center justify-between gap-4 rounded-medium bg-surface-muted px-3 py-2 text-sm text-text-secondary"><span>公开共享</span><Toggle checked={draft.public_shared} onClick={() => update('public_shared', !draft.public_shared)} /></label>
    </div>
    <button type="button" className="mt-4 text-sm font-medium text-accent-soft-text hover:underline" onClick={() => setAdvanced(value => !value)}>{advanced ? '收起高级 HTML 配置' : '高级 HTML 配置'}</button>
    {advanced && <div className="mt-3 rounded-medium border border-border bg-surface-muted p-3">
      <p className="text-sm text-text-secondary">自动检测失败时，可按网页 DOM 结构填写 CSS Selector；重新预览成功后即可创建。</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">{[
        ['item_selector', '列表元素 Selector', '.notice-item'],
        ['title_selector', '标题 Selector', '.title'],
        ['url_selector', 'URL Selector', 'a[href]'],
        ['time_selector', '时间 Selector', '.time'],
      ].map(([key, label, placeholder]) => <label key={key} className="text-sm text-text-secondary">{label}<Input className="mt-1.5" value={String(draft.parser_config[key as keyof typeof draft.parser_config] ?? '')} placeholder={placeholder} onChange={event => updateSelector(key as 'item_selector' | 'title_selector' | 'url_selector' | 'time_selector', event.target.value)} /></label>)}</div>
    </div>}
    <div className="mt-4 flex flex-wrap gap-2"><Button onClick={() => test.mutate()} disabled={!draft.name || !draft.list_url || !draft.public_shared || test.isPending}>{test.isPending ? '正在测试…' : 'Test Fetch / Preview'}</Button><Button variant="primary" onClick={() => create.mutate()} disabled={!preview || !adminKey || create.isPending}>{create.isPending ? '正在创建…' : '创建 Cloud Registry 记录'}</Button><Button variant="ghost" onClick={onClose}>取消</Button></div>
    {!draft.public_shared && <p className="mt-3 text-sm text-warning">私有来源必须保留在本机；云端共享来源需要开启公开共享。</p>}
    {preview && <div className="mt-4 rounded-medium border border-border bg-surface-muted p-3"><p className="text-sm font-medium text-text-primary">Preview Result · 找到 {preview.found} 条通知</p><ol className="mt-2 space-y-1 text-sm text-text-secondary">{preview.items.map(item => <li key={item.url} className="truncate">{item.title}</li>)}</ol></div>}
    {preview && <label className="mt-4 block text-sm text-text-secondary">管理员密钥<Input className="mt-1.5" type="password" autoComplete="off" value={adminKey} onChange={event => setAdminKey(event.target.value)} /></label>}
    {message && <p role="alert" className="mt-3 text-sm text-danger">{message}</p>}
  </section>
}

function SourceRow({ source, runResult, onEdit }: { source: SourceConfiguration; runResult?: CrawlerSourceResult; onEdit: () => void }) {
  const queryClient = useQueryClient(); const toast = useToast()
  const [warning, setWarning] = useState(false); const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [adminAction, setAdminAction] = useState<'promote' | 'auto' | 'force_enabled' | 'force_disabled' | null>(null)
  const [adminKey, setAdminKey] = useState(''); const [adminError, setAdminError] = useState<string | null>(null)
  const refresh = async () => { await queryClient.invalidateQueries({ queryKey: ['source-config'] }); await queryClient.invalidateQueries({ queryKey: ['sources'] }) }
  const subscription = useMutation({ mutationFn: (value: boolean) => setSourceSubscription(source.id, value), onSuccess: refresh })
  const enabled = useMutation({ mutationFn: ({ value, acknowledged }: { value: boolean; acknowledged?: boolean }) => setSourceEnabled(source.id, value, acknowledged), onSuccess: async () => { setWarning(false); await refresh() } })
  const check = useMutation({
    onMutate: () => captureCrawlerCompletionBaseline(queryClient),
    mutationFn: () => checkSource(source.id),
    onSuccess: async () => {
      toast('已开始检查该来源')
      await queryClient.invalidateQueries({ queryKey: ['crawler'] })
    },
    onError: error => {
      if (error instanceof ApiError && error.kind === 'ABORTED') return
      toast(error instanceof Error ? error.message : '启动来源检查失败，请稍后重试', 'error')
    },
  })
  const reauth = useMutation({
    mutationFn: () => reauthenticateSource(source.id),
    onSuccess: async result => {
      await refresh()
      toast('请在本机完成登录验证')
      if (isTauri()) await openUrl(result.login_url)
      else window.open(result.login_url, '_blank', 'noopener,noreferrer')
    },
    onError: error => toast(error instanceof Error ? error.message : '无法启动登录配置', 'error'),
  })
  const remove = useMutation({ mutationFn: (clear: boolean) => deleteSource(source.id, clear), onSuccess: async () => { await refresh(); toast('来源已删除') } })
  const admin = useMutation({ mutationFn: () => adminAction === 'promote' ? promoteSource(source.id, adminKey) : setCloudPolicy(source.id, adminAction!, adminKey), onSuccess: async result => { setAdminKey(''); setAdminError(null); setAdminAction(null); await refresh(); toast(result.promotion_reused ? '云端已有该来源，已完成本地关联' : '云端来源设置已更新') }, onError: error => { setAdminKey(''); setAdminError(error instanceof Error ? error.message : '管理员操作失败') } })
  const official = source.ownership === 'OFFICIAL_CLOUD'; const shared = source.ownership === 'SHARED_CLOUD'; const cloud = official || shared; const privateSource = source.ownership === 'CUSTOM_LOCAL_PRIVATE'
  const singlePage = source.source_type === 'single_page_monitor'
  const publicFeedMissing = cloud && (source.health_state === 'cloud_unconfigured' || source.last_error_code === 'PUBLIC_FEED_NOT_CONFIGURED' || Boolean(source.last_error?.includes('PUBLIC_FEED_NOT_CONFIGURED')))
  const displayHealth = publicFeedMissing ? 'cloud_unconfigured' : source.health_state
  const showsExecutionState = official && source.execution_policy === 'cloud_preferred'
  const localFallbackActive = Boolean(
    runResult?.fallback_used && runResult.effective_execution === 'local'
  )
  const authenticationRequired = privateSource && (
    source.requires_reauthentication
    || source.authentication_status === 'not_configured'
    || source.authentication_status === 'required'
    || (!source.authentication_status && source.health_state === 'unconfigured')
  )
  const authenticationLabel = source.authentication_status === 'authenticated' ? '已认证' : source.authentication_status === 'not_configured' ? '未配置' : source.authentication_status === 'required' ? '需要认证' : '无需认证'
  return (
    <article className="border-b border-border px-4 py-4 last:border-0 sm:px-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-start gap-3"><SourceIcon name={source.name}/><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-medium text-text-primary">{source.name}</h3>{shared && <Badge variant="neutral">云端共享</Badge>}<Badge variant={healthVariant(displayHealth)}>{healthLabels[displayHealth] ?? displayHealth}</Badge><Badge variant="neutral">{executionPolicyLabels[source.execution_policy]}</Badge>{showsExecutionState && <Badge variant={localFallbackActive ? 'warning' : 'success'}>{localFallbackActive ? '本地回退生效' : '云端运行'}</Badge>}{shared && <Badge variant={source.cloud_policy === 'force_enabled' ? 'success' : 'neutral'}>{source.cloud_policy === 'force_enabled' ? '管理员强制上云' : source.cloud_policy === 'force_disabled' ? '管理员禁止云抓取' : '自动策略'}</Badge>}</div>{shared && <p className="mt-1 break-all text-metadata text-text-secondary">{source.base_url}</p>}<p className="mt-1 text-metadata text-text-muted">{shared ? `类型：${source.parser === 'generic_html' ? 'HTML' : source.parser.toUpperCase()} · 状态：${healthLabels[displayHealth] ?? displayHealth} · 更新：${relativeTime(source.last_checked_at ?? source.last_success_at)}` : `最近成功：${relativeTime(source.last_success_at)}`}{privateSource ? ` · 认证：${authenticationLabel}` : ''}{source.last_error_code && !publicFeedMissing ? ` · ${source.last_error_code}` : ''}</p></div></div>
        <div className="flex flex-wrap items-center gap-2">{cloud ? <><label className="flex items-center gap-2 text-sm text-text-secondary"><span>{source.subscribed ? '已订阅' : '未订阅'}</span><Toggle checked={source.subscribed} onClick={() => subscription.mutate(!source.subscribed)} /></label>{shared && source.cloud_policy === 'force_enabled' && <Button size="sm" variant="ghost" onClick={() => { setAdminError(null); setAdminAction('force_disabled') }}>移出云端</Button>}{shared && source.cloud_policy !== 'force_enabled' && <Button size="sm" variant="ghost" onClick={() => { setAdminError(null); setAdminAction('force_enabled') }}>上云</Button>}{shared && source.cloud_policy !== 'auto' && <Button size="sm" variant="ghost" onClick={() => { setAdminError(null); setAdminAction('auto') }}>恢复自动</Button>}</> : <><Button size="sm" variant="ghost" disabled={singlePage} onClick={onEdit}><Pencil className="h-3.5 w-3.5"/>编辑</Button><Button size="sm" variant="ghost" disabled={check.isPending || source.requires_reauthentication || !source.enabled} onClick={() => check.mutate()}><RefreshCw className="h-3.5 w-3.5"/>检查</Button>{!privateSource && !singlePage && <Button size="sm" variant="ghost" disabled={source.validation_status !== 'passed'} onClick={() => { setAdminError(null); setAdminAction('promote') }}>上云</Button>}{authenticationRequired && <Button size="sm" onClick={() => reauth.mutate()} disabled={reauth.isPending}><ShieldAlert className="h-3.5 w-3.5"/>{source.authentication_status === 'not_configured' || source.health_state === 'unconfigured' ? '首次登录' : '重新登录'}</Button>}<Button size="sm" variant="ghost" onClick={() => source.enabled ? enabled.mutate({ value: false }) : privateSource ? setWarning(true) : enabled.mutate({ value: true })}>{source.enabled ? '停用' : '启用'}</Button><Button size="icon" variant="ghost" aria-label={`删除${source.name}`} onClick={() => setDeleteConfirm(true)}><Trash2 className="h-4 w-4"/></Button></>}</div>
      </div>
      {singlePage && <p className="mt-3 text-sm text-text-muted">按重要章节监测变化；首次检查只建立基线，不生成历史未读通知。监控依赖本地后端运行及联网；完全退出桌面客户端或系统休眠期间不会检查页面，恢复后可主动检查。离线期间出现又撤回的网页变化可能无法检测。</p>}
      {source.requires_reauthentication && <p className="mt-3 flex items-center gap-2 text-sm text-warning"><TriangleAlert className="h-4 w-4"/>此来源已暂停自动抓取，完成重新登录后才会恢复。</p>}
      {publicFeedMissing && <p className="mt-3 text-sm text-text-muted">等待 Notice Hub 公共源启用</p>}
      {source.last_error && !source.requires_reauthentication && !publicFeedMissing && <p className="mt-3 text-sm text-danger">{source.last_error}</p>}
      {warning && <div role="alert" className="mt-3 rounded-medium border border-border bg-surface-muted p-3 text-sm text-text-secondary"><p className="font-medium text-text-primary">此来源需要登录后才能自动抓取。</p><p className="mt-1">登录信息和状态仅保存在本机。验证码、短信、二维码或 MFA 需要你手动完成；状态失效后会暂停来源并提醒重新登录。</p><div className="mt-3 flex gap-2"><Button size="sm" variant="primary" onClick={() => enabled.mutate({ value: true, acknowledged: true })}>继续并登录</Button><Button size="sm" variant="ghost" onClick={() => setWarning(false)}>取消</Button></div></div>}
      {deleteConfirm && <div role="alert" className="mt-3 rounded-medium border border-border bg-surface-muted p-3 text-sm text-text-secondary"><p>删除来源不会因一次抓取失败而自动清除登录信息。请选择：</p><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant="danger" onClick={() => remove.mutate(false)}>仅删除来源</Button>{privateSource && <Button size="sm" variant="danger" onClick={() => remove.mutate(true)}>删除并清除本地登录信息</Button>}<Button size="sm" variant="ghost" onClick={() => setDeleteConfirm(false)}>取消</Button></div></div>}
      <Dialog.Root open={adminAction !== null} onOpenChange={open => { if (!open) { setAdminAction(null); setAdminKey(''); setAdminError(null) } }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-overlay"/><Dialog.Content aria-describedby="cloud-admin-description" className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-xlarge border border-border-strong bg-surface-raised p-5 shadow-2xl"><Dialog.Title className="text-section-heading text-text-primary">{adminAction === 'promote' || adminAction === 'force_enabled' ? '将此来源加入云端共享抓取' : adminAction === 'force_disabled' ? '停止此来源的云端抓取' : '恢复云端自动策略'}</Dialog.Title><Dialog.Description id="cloud-admin-description" className="mt-2 text-sm text-text-secondary">此操作仅用于 Cloud Source Management。密钥只发送一次，不会保存在本机。</Dialog.Description><label className="mt-4 block text-sm text-text-secondary">管理员密钥<Input autoFocus className="mt-1.5" type="password" autoComplete="off" value={adminKey} onChange={event => setAdminKey(event.target.value)} /></label>{adminError && <p role="alert" className="mt-3 text-sm text-danger">{adminError}</p>}<div className="mt-5 flex justify-end gap-2"><Dialog.Close asChild><Button variant="ghost">取消</Button></Dialog.Close><Button variant="primary" disabled={!adminKey || admin.isPending} onClick={() => admin.mutate()}>{admin.isPending ? '正在提交…' : '确认'}</Button></div></Dialog.Content></Dialog.Portal></Dialog.Root>
    </article>
  )
}

function SourceSection({ title, description, sources, runResults, onEdit }: { title: string; description: string; sources: SourceConfiguration[]; runResults: Map<string, CrawlerSourceResult>; onEdit: (source: SourceConfiguration) => void }) {
  return <section><div className="mb-3"><h2 className="text-section-heading text-text-primary">{title}</h2><p className="mt-1 text-sm text-text-secondary">{description}</p></div><div className="rounded-large border border-border bg-surface">{sources.length ? sources.map(source => <SourceRow key={source.id} source={source} runResult={runResults.get(source.code)} onEdit={() => onEdit(source)}/>) : <div className="p-5 text-sm text-text-muted">尚未添加</div>}</div></section>
}

export function SourcesPage() {
  const sources = useQuery({ queryKey: ['source-config'], queryFn: ({ signal }) => getSourceConfiguration({ signal }) })
  const crawler = useQuery({
    queryKey: ['crawler'],
    queryFn: ({ signal }) => getCrawlerStatus({ signal }),
    refetchInterval: query => query.state.data?.running ? 1_500 : 60_000,
  })
  useCrawlerCompletionRefresh(crawler.data)
  const [editor, setEditor] = useState<{ kind: 'public' | 'private'; source?: SourceConfiguration } | null>(null)
  const [cloudEditor, setCloudEditor] = useState(false)
  const official = sources.data?.filter(source => source.ownership === 'OFFICIAL_CLOUD') ?? []
  const shared = sources.data?.filter(source => source.ownership === 'SHARED_CLOUD') ?? []
  const publicLocal = sources.data?.filter(source => source.ownership === 'CUSTOM_LOCAL_PUBLIC') ?? []
  const privateLocal = sources.data?.filter(source => source.ownership === 'CUSTOM_LOCAL_PRIVATE') ?? []
  const needsReauth = privateLocal.filter(source => source.requires_reauthentication).length
  const runResults = new Map(
    (crawler.data?.source_results ?? []).map(result => [result.source, result])
  )
  return (
    <>
      <PageHeader title="数据源" description="官方通知由 Notice Hub 公共源同步；自定义和登录来源仅在当前设备处理。"/>
      {needsReauth > 0 && <div role="status" className="mb-5 flex items-center gap-2 rounded-medium border border-border bg-surface-muted px-4 py-3 text-sm text-warning"><ShieldAlert className="h-4 w-4"/>{needsReauth} 个来源需要重新登录</div>}
      {sources.isPending ? <PageSkeleton/> : sources.isError ? <ErrorState error={sources.error} retry={() => sources.refetch()}/> : <div className="max-w-5xl space-y-7">
        <SourceSection title="我的订阅" description="官方订阅偏好只保存在当前设备；共享来源的订阅开关在下方管理。" sources={official} runResults={runResults} onEdit={() => undefined}/>
        <SourceSection title="云端共享来源" description="云端统一抓取；每台设备仍独立决定是否订阅，阅读与收藏状态只保存在本机。" sources={shared} runResults={runResults} onEdit={() => undefined}/>
        {cloudEditor ? <CloudSourceEditor onClose={() => setCloudEditor(false)}/> : <Button onClick={() => setCloudEditor(true)}><Plus className="h-4 w-4"/>添加云端共享来源</Button>}
        <SourceSection title="本地来源" description="公开与私有来源都只在当前设备抓取；私有凭据、Cookie 和浏览器会话绝不上传。" sources={[...publicLocal, ...privateLocal]} runResults={runResults} onEdit={source => setEditor({ kind: source.ownership === 'CUSTOM_LOCAL_PRIVATE' ? 'private' : 'public', source })}/>
        {editor?.kind === 'public' ? <SourceEditor kind="public" initial={editor.source} onClose={() => setEditor(null)}/> : <Button onClick={() => setEditor({ kind: 'public' })}><Plus className="h-4 w-4"/>添加公开来源</Button>}
        {editor?.kind === 'private' ? <SourceEditor kind="private" initial={editor.source} onClose={() => setEditor(null)}/> : <Button onClick={() => setEditor({ kind: 'private' })}><Plus className="h-4 w-4"/>添加私有来源</Button>}
        <p className="flex items-start gap-2 text-metadata leading-5 text-text-muted"><Rss className="mt-0.5 h-3.5 w-3.5 shrink-0"/>自动检测不能保证支持任意网站。解析不安全或结构不明确时，测试步骤会明确失败，不会静默保存。</p>
      </div>}
    </>
  )
}
