import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isTauri } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import { Pencil, Plus, RefreshCw, Rss, ShieldAlert, Trash2, TriangleAlert, X } from 'lucide-react'
import { useState } from 'react'
import {
  checkSource, createSource, deleteSource, editSource, getSourceConfiguration, previewSource,
  promoteSource, reauthenticateSource, setCloudPolicy, setSourceEnabled, setSourceSubscription,
} from '../api/sources'
import { PageHeader } from '../components/layout/PageHeader'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { Input, Select, Toggle } from '../components/ui/Form'
import { useToast } from '../stores/toast'
import type { SourceConfiguration, SourceDraft, SourceHealthState } from '../types'
import { relativeTime } from '../utils/format'

const healthLabels: Record<SourceHealthState, string> = {
  healthy: '运行正常', syncing: '正在同步', disabled: '已停用', needs_reauth: '需要重新登录',
  auth_error: '认证失败', parse_error: '解析失败', network_error: '网络异常', source_error: '来源异常',
  unsupported: '暂不支持', unconfigured: '等待首次检查', authenticated: '已登录',
}

function healthVariant(state: SourceHealthState): BadgeVariant {
  if (state === 'healthy' || state === 'authenticated') return 'success'
  if (state === 'needs_reauth' || state === 'unconfigured' || state === 'syncing') return 'warning'
  if (state === 'disabled') return 'neutral'
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
        <label className="text-sm text-text-secondary">来源格式<Select className="mt-1.5" value={draft.parser} onChange={event => update('parser', event.target.value as SourceDraft['parser'])}><option value="auto">自动检测</option><option value="generic_html">网页列表</option><option value="rss">RSS / Atom</option></Select></label>
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

function SourceRow({ source, onEdit }: { source: SourceConfiguration; onEdit: () => void }) {
  const queryClient = useQueryClient(); const toast = useToast()
  const [warning, setWarning] = useState(false); const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [adminAction, setAdminAction] = useState<'promote' | 'auto' | 'force_enabled' | 'force_disabled' | null>(null)
  const [adminKey, setAdminKey] = useState(''); const [adminError, setAdminError] = useState<string | null>(null)
  const refresh = async () => { await queryClient.invalidateQueries({ queryKey: ['source-config'] }); await queryClient.invalidateQueries({ queryKey: ['sources'] }) }
  const subscription = useMutation({ mutationFn: (value: boolean) => setSourceSubscription(source.id, value), onSuccess: refresh })
  const enabled = useMutation({ mutationFn: ({ value, acknowledged }: { value: boolean; acknowledged?: boolean }) => setSourceEnabled(source.id, value, acknowledged), onSuccess: async () => { setWarning(false); await refresh() } })
  const check = useMutation({ mutationFn: () => checkSource(source.id), onSuccess: () => toast('已开始检查该来源') })
  const reauth = useMutation({ mutationFn: () => reauthenticateSource(source.id), onSuccess: async result => { toast('请在本机完成登录验证'); if (isTauri()) await openUrl(result.login_url); else window.open(result.login_url, '_blank', 'noopener,noreferrer') } })
  const remove = useMutation({ mutationFn: (clear: boolean) => deleteSource(source.id, clear), onSuccess: async () => { await refresh(); toast('来源已删除') } })
  const admin = useMutation({ mutationFn: () => adminAction === 'promote' ? promoteSource(source.id, adminKey) : setCloudPolicy(source.id, adminAction!, adminKey), onSuccess: async result => { setAdminKey(''); setAdminError(null); setAdminAction(null); await refresh(); toast(result.promotion_reused ? '云端已有该来源，已完成本地关联' : '云端来源设置已更新') }, onError: error => { setAdminKey(''); setAdminError(error instanceof Error ? error.message : '管理员操作失败') } })
  const official = source.ownership === 'OFFICIAL_CLOUD'; const shared = source.ownership === 'SHARED_CLOUD'; const cloud = official || shared; const privateSource = source.ownership === 'CUSTOM_LOCAL_PRIVATE'
  return (
    <article className="border-b border-border px-4 py-4 last:border-0 sm:px-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-medium text-text-primary">{source.name}</h3>{shared && <Badge variant="neutral">云端共享</Badge>}<Badge variant={healthVariant(source.health_state)}>{healthLabels[source.health_state] ?? source.health_state}</Badge>{shared && <Badge variant={source.cloud_policy === 'force_enabled' ? 'success' : 'neutral'}>{source.cloud_policy === 'force_enabled' ? '管理员强制上云' : source.cloud_policy === 'force_disabled' ? '管理员禁止云抓取' : '自动策略'}</Badge>}</div><p className="mt-1 text-metadata text-text-muted">最近成功：{relativeTime(source.last_success_at)}{source.last_error_code ? ` · ${source.last_error_code}` : ''}</p></div>
        <div className="flex flex-wrap items-center gap-2">{cloud ? <><label className="flex items-center gap-2 text-sm text-text-secondary"><span>{source.subscribed ? '已订阅' : '未订阅'}</span><Toggle checked={source.subscribed} onClick={() => subscription.mutate(!source.subscribed)} /></label>{shared && source.cloud_policy === 'force_enabled' && <Button size="sm" variant="ghost" onClick={() => { setAdminError(null); setAdminAction('force_disabled') }}>移出云端</Button>}{shared && source.cloud_policy !== 'force_enabled' && <Button size="sm" variant="ghost" onClick={() => { setAdminError(null); setAdminAction('force_enabled') }}>上云</Button>}{shared && source.cloud_policy !== 'auto' && <Button size="sm" variant="ghost" onClick={() => { setAdminError(null); setAdminAction('auto') }}>恢复自动</Button>}</> : <><Button size="sm" variant="ghost" onClick={onEdit}><Pencil className="h-3.5 w-3.5"/>编辑</Button><Button size="sm" variant="ghost" disabled={check.isPending || source.requires_reauthentication || !source.enabled} onClick={() => check.mutate()}><RefreshCw className="h-3.5 w-3.5"/>检查</Button>{!privateSource && <Button size="sm" variant="ghost" disabled={source.validation_status !== 'passed'} onClick={() => { setAdminError(null); setAdminAction('promote') }}>上云</Button>}{privateSource && source.requires_reauthentication && <Button size="sm" onClick={() => reauth.mutate()}><ShieldAlert className="h-3.5 w-3.5"/>重新登录</Button>}<Button size="sm" variant="ghost" onClick={() => source.enabled ? enabled.mutate({ value: false }) : privateSource ? setWarning(true) : enabled.mutate({ value: true })}>{source.enabled ? '停用' : '启用'}</Button><Button size="icon" variant="ghost" aria-label={`删除${source.name}`} onClick={() => setDeleteConfirm(true)}><Trash2 className="h-4 w-4"/></Button></>}</div>
      </div>
      {source.requires_reauthentication && <p className="mt-3 flex items-center gap-2 text-sm text-warning"><TriangleAlert className="h-4 w-4"/>此来源已暂停自动抓取，完成重新登录后才会恢复。</p>}
      {source.last_error && !source.requires_reauthentication && <p className="mt-3 text-sm text-danger">{source.last_error}</p>}
      {warning && <div role="alert" className="mt-3 rounded-medium border border-border bg-surface-muted p-3 text-sm text-text-secondary"><p className="font-medium text-text-primary">此来源需要登录后才能自动抓取。</p><p className="mt-1">登录信息和状态仅保存在本机。验证码、短信、二维码或 MFA 需要你手动完成；状态失效后会暂停来源并提醒重新登录。</p><div className="mt-3 flex gap-2"><Button size="sm" variant="primary" onClick={() => enabled.mutate({ value: true, acknowledged: true })}>继续并登录</Button><Button size="sm" variant="ghost" onClick={() => setWarning(false)}>取消</Button></div></div>}
      {deleteConfirm && <div role="alert" className="mt-3 rounded-medium border border-border bg-surface-muted p-3 text-sm text-text-secondary"><p>删除来源不会因一次抓取失败而自动清除登录信息。请选择：</p><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant="danger" onClick={() => remove.mutate(false)}>仅删除来源</Button>{privateSource && <Button size="sm" variant="danger" onClick={() => remove.mutate(true)}>删除并清除本地登录信息</Button>}<Button size="sm" variant="ghost" onClick={() => setDeleteConfirm(false)}>取消</Button></div></div>}
      <Dialog.Root open={adminAction !== null} onOpenChange={open => { if (!open) { setAdminAction(null); setAdminKey(''); setAdminError(null) } }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-overlay"/><Dialog.Content aria-describedby="cloud-admin-description" className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-xlarge border border-border-strong bg-surface-raised p-5 shadow-2xl"><Dialog.Title className="text-section-heading text-text-primary">{adminAction === 'promote' || adminAction === 'force_enabled' ? '将此来源加入云端共享抓取' : adminAction === 'force_disabled' ? '停止此来源的云端抓取' : '恢复云端自动策略'}</Dialog.Title><Dialog.Description id="cloud-admin-description" className="mt-2 text-sm text-text-secondary">此操作仅用于 Cloud Source Management。密钥只发送一次，不会保存在本机。</Dialog.Description><label className="mt-4 block text-sm text-text-secondary">管理员密钥<Input autoFocus className="mt-1.5" type="password" autoComplete="off" value={adminKey} onChange={event => setAdminKey(event.target.value)} /></label>{adminError && <p role="alert" className="mt-3 text-sm text-danger">{adminError}</p>}<div className="mt-5 flex justify-end gap-2"><Dialog.Close asChild><Button variant="ghost">取消</Button></Dialog.Close><Button variant="primary" disabled={!adminKey || admin.isPending} onClick={() => admin.mutate()}>{admin.isPending ? '正在提交…' : '确认'}</Button></div></Dialog.Content></Dialog.Portal></Dialog.Root>
    </article>
  )
}

function SourceSection({ title, description, sources, onEdit }: { title: string; description: string; sources: SourceConfiguration[]; onEdit: (source: SourceConfiguration) => void }) {
  return <section><div className="mb-3"><h2 className="text-section-heading text-text-primary">{title}</h2><p className="mt-1 text-sm text-text-secondary">{description}</p></div><div className="rounded-large border border-border bg-surface">{sources.length ? sources.map(source => <SourceRow key={source.id} source={source} onEdit={() => onEdit(source)}/>) : <div className="p-5 text-sm text-text-muted">尚未添加</div>}</div></section>
}

export function SourcesPage() {
  const sources = useQuery({ queryKey: ['source-config'], queryFn: ({ signal }) => getSourceConfiguration({ signal }) })
  const [editor, setEditor] = useState<{ kind: 'public' | 'private'; source?: SourceConfiguration } | null>(null)
  const official = sources.data?.filter(source => source.ownership === 'OFFICIAL_CLOUD') ?? []
  const shared = sources.data?.filter(source => source.ownership === 'SHARED_CLOUD') ?? []
  const publicLocal = sources.data?.filter(source => source.ownership === 'CUSTOM_LOCAL_PUBLIC') ?? []
  const privateLocal = sources.data?.filter(source => source.ownership === 'CUSTOM_LOCAL_PRIVATE') ?? []
  const needsReauth = privateLocal.filter(source => source.requires_reauthentication).length
  return (
    <>
      <PageHeader title="数据源" description="官方通知由 Notice Hub 公共源同步；自定义和登录来源仅在当前设备处理。"/>
      {needsReauth > 0 && <div role="status" className="mb-5 flex items-center gap-2 rounded-medium border border-border bg-surface-muted px-4 py-3 text-sm text-warning"><ShieldAlert className="h-4 w-4"/>{needsReauth} 个来源需要重新登录</div>}
      {sources.isPending ? <PageSkeleton/> : sources.isError ? <ErrorState error={sources.error} retry={() => sources.refetch()}/> : sources.data.length ? <div className="max-w-5xl space-y-7">
        <SourceSection title="官方来源" description="开关只影响当前设备的显示和同步偏好，不会停用云端公共抓取。" sources={official} onEdit={() => undefined}/>
        <SourceSection title="云端共享来源" description="云端统一抓取；每台设备仍独立决定是否订阅，阅读与收藏状态只保存在本机。" sources={shared} onEdit={() => undefined}/>
        <SourceSection title="我的公开来源" description="支持自动识别 RSS / Atom 与常见静态通知网页；复杂页面可使用高级选择器。" sources={publicLocal} onEdit={source => setEditor({ kind: 'public', source })}/>
        {editor?.kind === 'public' ? <SourceEditor kind="public" initial={editor.source} onClose={() => setEditor(null)}/> : <Button onClick={() => setEditor({ kind: 'public' })}><Plus className="h-4 w-4"/>添加公开来源</Button>}
        <SourceSection title="我的私有来源" description="凭据、Cookie 和浏览器会话不会上传到 Notice Hub 云端。" sources={privateLocal} onEdit={source => setEditor({ kind: 'private', source })}/>
        {editor?.kind === 'private' ? <SourceEditor kind="private" initial={editor.source} onClose={() => setEditor(null)}/> : <Button onClick={() => setEditor({ kind: 'private' })}><Plus className="h-4 w-4"/>添加私有来源</Button>}
        <p className="flex items-start gap-2 text-metadata leading-5 text-text-muted"><Rss className="mt-0.5 h-3.5 w-3.5 shrink-0"/>自动检测不能保证支持任意网站。解析不安全或结构不明确时，测试步骤会明确失败，不会静默保存。</p>
      </div> : <EmptyState title="当前没有配置的数据源" description="后端尚未返回任何来源配置。"/>}
    </>
  )
}
