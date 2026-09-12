import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bell, Check, Inbox, Menu, Moon, PanelLeftClose, PanelLeftOpen, Settings, Sun, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState, type RefObject } from 'react'
import { Link, NavLink, Outlet, matchPath, useLocation, useNavigate } from 'react-router-dom'
import { getCrawlerStatus } from '../../api/crawler'
import { getDashboard } from '../../api/dashboard'
import { getNotificationEvents, markNotificationRead } from '../../api/notifications'
import { NoticeDetailPage } from '../../pages/NoticeDetailPage'
import { NoticesPage } from '../../pages/NoticesPage'
import { useTheme } from '../../stores/theme'
import { startDesktopNotificationBridge, validNotificationRoute } from '../../services/desktopNotifications'
import { cn } from '../../utils/cn'
import { relativeTime } from '../../utils/format'
import { SearchDialog } from '../search/SearchDialog'
import { CrawlerButton } from './CrawlerButton'
import { isCrawlerJobRunning } from './crawlerStatus'
import { getRouteTitle, desktopNavGroups, desktopSourceGroups, desktopUtilityGroups, mobileNavItems, navGroups } from './navigation'
import type { CrawlerStatus, DashboardData } from '../../types'

type Counts = Record<string, number | undefined>

function NavItems({ collapsed = false, ariaLabel, onSelect, groups = navGroups, counts = {} }: { collapsed?: boolean; ariaLabel: string; onSelect?: () => void; groups?: typeof navGroups; counts?: Counts }) {
  const location = useLocation()
  const [weekStart] = useState(() => new Date(Date.now() - 6 * 86_400_000).toISOString().slice(0, 10))
  return <nav className="space-y-4" aria-label={ariaLabel}>{groups.map(group => <div key={group.label} className={cn(group.label === '快捷视图' && 'border-t border-border/70 pt-4')}>
    <div className={cn('sidebar-label mb-2 flex items-center justify-between px-2.5 text-label text-text-muted', ['主导航', '管理', '快捷视图'].includes(group.label) && 'sr-only', collapsed && 'hidden')}>
      <span>{group.label}</span>
    </div>
    <div className="space-y-1">{group.items.map(({ to, label, icon: Icon }) => {
      const destination = to === '/notices?date_from=week' ? `/notices?date_from=${weekStart}` : to
      const [targetPath, targetSearch = ''] = destination.split('?')
      const inNoticeWorkspace = /^\/notices(?:\/\d+)?$/.test(location.pathname)
      const currentParams = new URLSearchParams(location.search)
      const targetParams = new URLSearchParams(targetSearch)
      const selected = targetPath === '/notices'
        ? inNoticeWorkspace && (targetSearch
          ? [...targetParams].every(([key, value]) => currentParams.get(key) === value)
          : !['read', 'favorite', 'min_score', 'source'].some(key => currentParams.has(key)))
        : location.pathname === targetPath
      const count = counts[label]
      return <Link key={to} to={destination} onClick={onSelect} title={label} aria-label={label} aria-current={selected ? 'page' : undefined} className={cn(
        'sidebar-link flex h-9 items-center gap-2.5 rounded-design px-2.5 text-body font-normal transition-colors',
        collapsed && 'justify-center',
        selected ? 'bg-selected-surface text-text-primary' : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
      )}>
        <Icon className={cn('h-4.5 w-4.5 shrink-0', selected ? 'text-accent-soft-text' : 'text-text-muted')} aria-hidden="true" />
        <span className={cn('sidebar-label min-w-0 flex-1 truncate', collapsed && 'hidden')}>{label}</span>
        {count !== undefined && <span aria-hidden="true" className={cn('sidebar-label text-metadata tabular-nums', selected ? 'text-accent-soft-text' : 'text-text-muted', collapsed && 'hidden')}>{count}</span>}
      </Link>
    })}</div>
  </div>)}</nav>
}

function Sidebar({ collapsed, onToggle, onMore, crawler, crawlerError, counts }: { collapsed: boolean; onToggle: () => void; onMore: (trigger: HTMLButtonElement) => void; crawler?: CrawlerStatus; crawlerError: boolean; counts: Counts }) {
  const syncing = isCrawlerJobRunning(crawler)
  const syncText = crawlerError ? '连接异常' : !crawler ? '正在连接…' : syncing ? '正在同步…' : crawler.status === 'failure' ? '同步失败' : crawler.status === 'partial_failure' ? '部分来源异常' : crawler.last_run ? `已同步 · ${relativeTime(crawler.last_run)}` : '尚未同步'
  return <aside aria-label="侧边栏" className="app-sidebar relative z-30 hidden min-h-0 flex-col bg-sidebar-surface py-6 md:flex">
    <div className="mb-4 flex h-10 shrink-0 items-center gap-3 px-2.5">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-medium bg-cta-surface text-section-heading text-text-inverse">N</div>
      <div className={cn('sidebar-label min-w-0', collapsed && 'hidden')}><div className="truncate text-section-heading text-text-primary">Notice Hub</div><div className="text-label text-text-muted">校园通知，集中有序</div></div>
    </div>
    <div className="min-h-0 flex-1 space-y-6 overflow-y-auto">
      <NavItems collapsed={collapsed} ariaLabel="主导航" groups={desktopNavGroups} counts={counts} />
      <NavItems collapsed={collapsed} ariaLabel="通知来源" groups={desktopSourceGroups} />
    </div>
    <div className="mt-4 shrink-0 border-t border-border pt-2">
      <NavItems collapsed={collapsed} ariaLabel="应用管理" groups={desktopUtilityGroups} />
      <div className={cn('flex items-center justify-between gap-1', collapsed && 'flex-col')}>
        <button onClick={event => onMore(event.currentTarget)} className="sidebar-link flex h-9 min-w-0 items-center gap-2.5 rounded-design px-2.5 text-body text-text-muted hover:bg-surface-hover" title="全部功能" aria-label="全部功能" aria-haspopup="dialog"><Menu className="h-4.5 w-4.5 shrink-0" /><span className={cn('sidebar-label', collapsed && 'hidden')}>全部功能</span></button>
        <button onClick={onToggle} className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-medium text-text-muted hover:bg-surface-hover xl:flex" title={collapsed ? '展开侧边栏' : '折叠侧边栏'} aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}>{collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}</button>
      </div>
      <div className="sidebar-sync mt-2 flex min-w-0 items-center gap-1 px-2.5" title={syncText}>
        <span className={cn('sidebar-label min-w-0 flex-1 truncate text-label text-text-muted', collapsed && 'hidden')}>{crawler?.last_run && !crawlerError && !syncing && !['failure', 'partial_failure'].includes(crawler.status ?? '') && <Check className="mr-1 inline h-3 w-3 text-source-green-fg" aria-hidden="true" />}{syncText}</span>
        <CrawlerButton compact />
      </div>
    </div>
  </aside>
}

function HeaderActions({ crawler, crawlerError, dashboard }: { crawler?: CrawlerStatus; crawlerError: boolean; dashboard?: DashboardData }) {
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const notifications = useQuery({ queryKey: ['notification-events'], queryFn: ({ signal }) => getNotificationEvents({ signal }), refetchInterval: 30_000 })
  const markRead = useMutation({ mutationFn: markNotificationRead, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notification-events'] }) })
  const [active, setActive] = useState<'alerts' | 'account' | null>(null)
  const bellRef = useRef<HTMLButtonElement>(null)
  const avatarRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!active) return
    const trigger = active === 'alerts' ? bellRef.current : avatarRef.current
    const focusFrame = requestAnimationFrame(() => panelRef.current?.querySelector<HTMLElement>('[data-popup-focus]')?.focus())
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node
      if (!panelRef.current?.contains(target) && !trigger?.contains(target)) setActive(null)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setActive(null)
      requestAnimationFrame(() => trigger?.focus())
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      cancelAnimationFrame(focusFrame)
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [active])

  const crawlRunning = isCrawlerJobRunning(crawler)
  const statusText = crawlerError ? '检查服务连接异常' : crawlRunning ? '正在检查新通知' : crawler?.status === 'partial_failure' ? '最近检查部分失败' : crawler?.status === 'failure' ? '最近检查失败' : crawler?.status === 'success' ? '最近检查完成' : '检查服务空闲'
  const statusTone = crawlerError || crawler?.status === 'failure' ? 'bg-danger' : crawlRunning || crawler?.status === 'partial_failure' ? 'bg-warning' : 'bg-success'
  const toggle = (name: 'alerts' | 'account') => setActive(current => current === name ? null : name)
  const reauthCount = dashboard?.source_status?.filter(source => source.status === 'needs_reauth' || source.status === 'login_expired').length ?? 0
  const notificationItems = Array.isArray(notifications.data?.items) ? notifications.data.items : []
  const reminderUnread = typeof notifications.data?.unread === 'number' ? notifications.data.unread : 0
  const openReminder = (eventId: number, route: string | null) => {
    markRead.mutate(eventId)
    setActive(null)
    navigate(validNotificationRoute(route) ? route : '/notices')
  }

  return <div className="relative hidden shrink-0 items-center gap-2 md:flex">
    <button ref={bellRef} type="button" onClick={() => toggle('alerts')} aria-label={reminderUnread ? `提醒中心，${reminderUnread} 条未读提醒` : '提醒中心'} aria-haspopup="dialog" aria-expanded={active === 'alerts'} aria-controls="header-alerts-popover" className="relative grid h-8 w-8 place-items-center rounded-medium text-text-muted transition-colors hover:bg-surface-muted hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30"><Bell className="h-3.5 w-3.5" aria-hidden="true" />{(reminderUnread > 0 || reauthCount > 0) && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true"/>}</button>
    <button ref={avatarRef} type="button" onClick={() => toggle('account')} aria-label="应用菜单" aria-haspopup="menu" aria-expanded={active === 'account'} aria-controls="header-account-menu" className="grid h-[26px] w-[26px] place-items-center rounded-full bg-border-strong text-text-primary transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30"><UserRound className="h-3.5 w-3.5" aria-hidden="true" /></button>

    {active === 'alerts' && <div ref={panelRef} id="header-alerts-popover" role="dialog" aria-label="提醒中心" className="absolute right-9 top-[calc(100%+8px)] z-50 w-80 rounded-large border border-border-strong bg-surface-raised p-3 shadow-xl">
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-text-primary">最近提醒</h2><span className="inline-flex items-center gap-1.5 text-label text-text-muted"><span className={`h-1.5 w-1.5 rounded-full ${statusTone}`} aria-hidden="true" />{statusText}</span></div>
      <div className="mt-3 max-h-80 space-y-1 overflow-y-auto">
        {notifications.isPending && <p className="px-2 py-4 text-center text-xs text-text-muted">正在读取提醒…</p>}
        {!notifications.isPending && notificationItems.length === 0 && <p className="px-2 py-4 text-center text-xs text-text-muted">暂无提醒</p>}
        {notificationItems.map((item, index) => <button key={item.id} data-popup-focus={index === 0 ? true : undefined} type="button" onClick={() => openReminder(item.id, item.route)} className="flex w-full gap-2.5 rounded-medium px-2 py-2 text-left hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30">
          <span className={cn('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full', item.read_at ? 'bg-border-strong' : item.severity === 'error' ? 'bg-danger' : item.severity === 'warning' ? 'bg-warning' : 'bg-accent')} aria-hidden="true"/>
          <span className="min-w-0"><span className="block truncate text-xs font-medium text-text-primary">{item.title}</span><span className="mt-0.5 block line-clamp-2 text-metadata leading-4 text-text-muted">{item.body}</span></span>
        </button>)}
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-2 text-metadata text-text-muted"><span>{reminderUnread} 条未读提醒</span><span>最近检查：{crawler?.last_run ? relativeTime(crawler.last_run) : '尚无记录'}</span></div>
      {reauthCount > 0 && <Link to="/sources" onClick={() => setActive(null)} className="mt-2 flex items-center justify-between rounded-medium bg-surface-muted px-2.5 py-2 text-xs text-warning"><span>{reauthCount} 个来源需要重新登录</span><span>处理</span></Link>}
      <div className="mt-2 flex gap-2"><Link to="/settings" onClick={() => setActive(null)} className="flex h-8 flex-1 items-center justify-center rounded-medium border border-border text-xs text-text-secondary hover:bg-surface-muted hover:text-text-primary">提醒设置</Link><Link to="/deadlines" onClick={() => setActive(null)} className="flex h-8 flex-1 items-center justify-center rounded-medium border border-border text-xs text-text-secondary hover:bg-surface-muted hover:text-text-primary">即将截止</Link></div>
    </div>}

    {active === 'account' && <div ref={panelRef} id="header-account-menu" role="menu" aria-label="应用菜单" className="absolute right-0 top-[calc(100%+8px)] z-50 w-52 rounded-large border border-border-strong bg-surface-raised p-2 shadow-xl">
      <div className="px-2 py-2"><p className="text-sm font-semibold text-text-primary">Notice Hub</p><p className="mt-0.5 text-label text-text-muted">本地通知聚合助手</p></div>
      <div className="border-t border-border/70 pt-1">
        <Link data-popup-focus role="menuitem" to="/settings" onClick={() => setActive(null)} className="flex h-9 items-center gap-2 rounded-medium px-2 text-xs text-text-secondary hover:bg-surface-muted hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30"><Settings className="h-3.5 w-3.5" aria-hidden="true" />设置</Link>
        <button role="menuitem" type="button" onClick={() => { setTheme(theme === 'dark' ? 'light' : 'dark'); setActive(null) }} className="flex h-9 w-full items-center gap-2 rounded-medium px-2 text-left text-xs text-text-secondary hover:bg-surface-muted hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30">{theme === 'dark' ? <Sun className="h-3.5 w-3.5" aria-hidden="true" /> : <Moon className="h-3.5 w-3.5" aria-hidden="true" />}{theme === 'dark' ? '切换浅色主题' : '切换深色主题'}</button>
      </div>
    </div>}
  </div>
}

function Header({ title, crawler, crawlerError, dashboard }: { title: string; crawler?: CrawlerStatus; crawlerError: boolean; dashboard?: DashboardData }) {
  const { theme, setTheme } = useTheme()
  return <header className="app-header relative z-20 flex h-header-height items-center gap-2 bg-header-surface px-4 sm:gap-3 md:px-shell-gutter">
    <div className="min-w-0 md:hidden"><span data-testid="route-context" className="block truncate text-sm font-semibold">{title}</span></div>
    <SearchDialog />
    <div className="hidden min-w-0 flex-1 md:block" />
    <time className="hidden shrink-0 text-metadata text-text-muted xl:block" dateTime={new Date().toLocaleDateString('en-CA')}>{new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' }).format(new Date())}</time>
    <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="hidden h-8 w-8 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-hover md:grid" aria-label={theme === 'dark' ? '切换浅色主题' : '切换深色主题'}>{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
    <HeaderActions crawler={crawler} crawlerError={crawlerError} dashboard={dashboard} />
    <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted md:hidden" aria-label={theme === 'dark' ? '切换浅色主题' : '切换深色主题'}>{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
  </header>
}

function BottomNav({ moreOpen, onMore }: { moreOpen: boolean; onMore: (trigger: HTMLButtonElement) => void }) {
  return <nav className="fixed inset-x-0 bottom-0 z-40 flex h-mobile-nav-height items-center justify-around border-t border-border bg-surface md:hidden" aria-label="底部导航">
    {mobileNavItems.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end className={({ isActive }) => cn('flex h-full min-w-14 flex-col items-center justify-center gap-1 text-label', isActive ? 'font-medium text-accent-soft-text' : 'text-text-muted')}><Icon className="h-5 w-5" />{label}</NavLink>)}
    <button onClick={event => onMore(event.currentTarget)} className="flex h-full min-w-14 flex-col items-center justify-center gap-1 text-label text-text-muted" aria-label="更多导航" aria-haspopup="dialog" aria-expanded={moreOpen} aria-controls="mobile-navigation-dialog"><Menu className="h-5 w-5" />更多</button>
  </nav>
}

function MorePanel({ open, onOpenChange, triggerRef }: { open: boolean; onOpenChange: (open: boolean) => void; triggerRef: RefObject<HTMLButtonElement | null> }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-overlay" /><Dialog.Content id="mobile-navigation-dialog" aria-describedby={undefined} onCloseAutoFocus={event => { event.preventDefault(); triggerRef.current?.focus() }} className="fixed inset-y-0 right-0 z-50 w-[min(86vw,340px)] overflow-y-auto border-l border-border-strong bg-surface p-4 shadow-2xl">
    <Dialog.Title className="flex items-center justify-between font-semibold">全部功能<Dialog.Close className="grid h-11 w-11 place-items-center rounded-medium hover:bg-surface-muted" aria-label="关闭菜单"><X className="h-5 w-5" /></Dialog.Close></Dialog.Title>
    <div className="mt-5"><NavItems ariaLabel="完整导航" onSelect={() => onOpenChange(false)} /></div>
  </Dialog.Content></Dialog.Portal></Dialog.Root>
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('jlu-sidebar') === 'collapsed')
  const [moreOpen, setMoreOpen] = useState(false)
  const moreTriggerRef = useRef<HTMLButtonElement>(null)
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const detailMatch = matchPath('/notices/:id', pathname)
  const detailId = detailMatch?.params.id
  const noticeWorkspaceRoute = pathname === '/notices' || Boolean(detailId)
  const crawler = useQuery({ queryKey: ['crawler'], queryFn: ({ signal }) => getCrawlerStatus({ signal }), refetchInterval: 60_000 })
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: ({ signal }) => getDashboard({ signal }) })
  const toggleCollapse = () => { const next = !collapsed; setCollapsed(next); localStorage.setItem('jlu-sidebar', next ? 'collapsed' : 'expanded') }
  const counts: Counts = { 全部通知: dashboard.data?.total_count, 未读通知: dashboard.data?.unread, 重要通知: dashboard.data?.important, 即将截止: dashboard.data?.upcoming_deadlines }
  const openMore = (trigger: HTMLButtonElement) => { moreTriggerRef.current = trigger; setMoreOpen(true) }

  useEffect(() => {
    let disposed = false
    let stop: (() => void) | undefined
    void startDesktopNotificationBridge(route => navigate(route)).then(cleanup => {
      if (disposed) cleanup()
      else stop = cleanup
    })
    return () => { disposed = true; stop?.() }
  }, [navigate])

  return <div className="h-dvh min-h-0 overflow-hidden bg-app-canvas text-text-primary transition-colors">
    <div className="app-shell grid h-full min-h-0 overflow-hidden bg-app-frame" data-sidebar-collapsed={collapsed}>
      <Sidebar collapsed={collapsed} onToggle={toggleCollapse} onMore={openMore} crawler={crawler.data} crawlerError={crawler.isError} counts={counts} />
      <div className="grid min-h-0 min-w-0 grid-rows-[var(--spacing-header-height)_minmax(0,1fr)]">
        <Header title={getRouteTitle(pathname)} crawler={crawler.data} crawlerError={crawler.isError} dashboard={dashboard.data} />
        {noticeWorkspaceRoute ? <div className="notice-workspace grid min-h-0 min-w-0 overflow-hidden">
          <section className={cn('min-h-0 min-w-0 overflow-hidden bg-list-surface pb-mobile-nav-height md:pb-0', detailId && 'hidden xl:block')} aria-label="通知工作区"><main className="h-full min-h-0 overflow-hidden"><NoticesPage selectedId={detailId ? Number(detailId) : null} /></main></section>
          <aside className={cn('min-h-0 min-w-0 overflow-y-auto bg-detail-surface pb-mobile-nav-height md:pb-0 xl:border-l xl:border-border', detailId ? 'block' : 'hidden xl:grid xl:place-items-center')} aria-label="通知详情工作区">{detailId ? <><Link to={{ pathname: '/notices', search }} className="hidden min-h-11 items-center gap-2 px-shell-gutter text-body text-text-secondary hover:text-text-primary md:flex xl:hidden"><ArrowLeft className="h-4 w-4" />返回通知列表</Link><NoticeDetailPage embeddedId={Number(detailId)} /></> : <div className="max-w-sm px-8 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-app bg-attachment-surface text-text-muted"><Inbox className="h-5 w-5" /></div><h2 className="mt-4 text-section-heading">选择一条通知开始阅读</h2><p className="mt-2 text-body text-text-muted">通知详情将在这里显示。</p></div>}</aside>
        </div> : <main className="min-h-0 overflow-y-auto bg-bg p-4 sm:p-5 lg:p-6"><Outlet /></main>}
      </div>
    </div>
    <BottomNav moreOpen={moreOpen} onMore={openMore} />
    <MorePanel open={moreOpen} onOpenChange={setMoreOpen} triggerRef={moreTriggerRef} />
  </div>
}
