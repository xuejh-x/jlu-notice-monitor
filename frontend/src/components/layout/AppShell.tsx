import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { Bell, Check, Menu, Moon, PanelLeftClose, PanelLeftOpen, Settings, Sun, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState, type RefObject } from 'react'
import { Link, NavLink, Outlet, matchPath, useLocation } from 'react-router-dom'
import { getCrawlerStatus } from '../../api/crawler'
import { getDashboard } from '../../api/dashboard'
import { NoticeDetailPage } from '../../pages/NoticeDetailPage'
import { NoticesPage } from '../../pages/NoticesPage'
import { useTheme } from '../../stores/theme'
import { cn } from '../../utils/cn'
import { relativeTime } from '../../utils/format'
import { SearchDialog } from '../search/SearchDialog'
import { CrawlerButton } from './CrawlerButton'
import { getRouteTitle, desktopNavGroups, mobileNavItems, navGroups } from './navigation'
import type { CrawlerStatus, DashboardData } from '../../types'

type Counts = Record<string, number | undefined>

function NavItems({ collapsed = false, ariaLabel, onSelect, groups = navGroups, counts = {} }: { collapsed?: boolean; ariaLabel: string; onSelect?: () => void; groups?: typeof navGroups; counts?: Counts }) {
  const location = useLocation()
  const [weekStart] = useState(() => new Date(Date.now() - 6 * 86_400_000).toISOString().slice(0, 10))
  return <nav className="space-y-4" aria-label={ariaLabel}>{groups.map(group => <div key={group.label} className={cn(group.label === '快捷视图' && 'border-t border-border/70 pt-4')}>
    <div className={cn('mb-1 flex items-center justify-between px-3 text-label tracking-wider text-text-muted', group.label === '主导航' && 'sr-only', collapsed && group.label !== '主导航' && 'hidden xl:flex')}>
      <span>{group.label}</span>
    </div>
    <div className="space-y-1">{group.items.map(({ to, label, icon: Icon }) => {
      const destination = to === '/notices?date_from=week' ? `/notices?date_from=${weekStart}` : to
      const [targetPath, targetSearch = ''] = destination.split('?')
      const detailSelected = targetPath === '/notices' && !targetSearch && /^\/notices\/\d+$/.test(location.pathname)
      const selected = detailSelected || (location.pathname === targetPath && (targetSearch ? location.search === `?${targetSearch}` : !location.search))
      const count = counts[label]
      return <Link key={to} to={destination} onClick={onSelect} title={label} aria-current={selected ? 'page' : undefined} className={cn(
        'flex h-9 items-center rounded-design border border-transparent px-3 text-[13px] font-normal transition-colors',
        collapsed ? 'justify-center xl:justify-start xl:gap-2.5' : 'gap-2.5',
        selected ? 'border-accent/30 bg-accent-soft font-medium text-accent-soft-text' : 'text-text-secondary hover:bg-surface-muted hover:text-text-primary',
      )}>
        <Icon className="h-4 w-4 shrink-0" />
        <span className={cn('min-w-0 flex-1 truncate', collapsed && 'hidden xl:inline')}>{label}</span>
        {count !== undefined && <span className={cn('min-w-5 rounded-full px-1.5 py-0.5 text-center text-label tabular-nums', selected ? 'bg-accent/80 text-text-inverse' : 'bg-surface-muted text-text-muted', collapsed && 'hidden xl:inline')}>{count}</span>}
      </Link>
    })}</div>
  </div>)}</nav>
}

function Sidebar({ collapsed, onToggle, online, lastRun, counts }: { collapsed: boolean; onToggle: () => void; online: boolean; lastRun?: string | null; counts: Counts }) {
  return <aside className="relative z-30 hidden min-h-0 border-r border-border/70 bg-sidebar-surface px-[18px] py-[17px] md:flex md:flex-col">
    <div className="mb-8 flex h-7 items-center gap-2.5">
      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-design bg-accent text-sm font-semibold text-text-inverse shadow-sm">N</div>
      <div className={cn('min-w-0', collapsed && 'hidden xl:block')}><div className="truncate text-[13px] font-semibold tracking-tight text-text-primary">Notice Hub</div><div className="text-label font-normal text-text-muted">吉大通知助手</div></div>
    </div>
    <div className="min-h-0 flex-1 overflow-y-auto"><NavItems collapsed={collapsed} ariaLabel="主导航" groups={desktopNavGroups} counts={counts} /></div>
    <div className={cn('mt-4', collapsed && 'hidden xl:block')}>
      <div className="h-[98px] rounded-[9px] border border-border bg-progress-surface p-3" title={lastRun ? `上次同步 ${relativeTime(lastRun)}` : '尚无同步记录'}>
        <div className="flex items-start justify-between gap-2"><div><div className="text-metadata text-text-secondary">今日概览</div><div className="mt-1 text-lg font-semibold tabular-nums text-text-primary">{counts['今日新增'] ?? 0} 条新增</div></div>
          <div className="grid h-10 w-10 place-items-center rounded-full border-[4px] border-border-strong text-accent-soft-text">{online ? <Check className="h-4 w-4" aria-hidden="true" /> : <X className="h-4 w-4 text-danger" aria-hidden="true" />}</div>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 text-label text-text-muted"><span>{counts['未读'] ?? 0} 条未读待处理</span><CrawlerButton compact /></div>
      </div>
    </div>
    <button onClick={onToggle} className="mt-2 hidden h-8 items-center rounded-medium px-2 text-xs text-text-muted hover:bg-surface-muted md:flex xl:hidden" aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}>{collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <><PanelLeftClose className="mr-2 h-4 w-4" />折叠侧边栏</>}</button>
  </aside>
}

function HeaderActions({ crawler, crawlerError, dashboard }: { crawler?: CrawlerStatus; crawlerError: boolean; dashboard?: DashboardData }) {
  const { theme, setTheme } = useTheme()
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

  const statusText = crawlerError ? '检查服务连接异常' : crawler?.running ? '正在检查新通知' : '检查服务正常'
  const statusTone = crawlerError ? 'bg-danger' : crawler?.running ? 'bg-warning' : 'bg-success'
  const toggle = (name: 'alerts' | 'account') => setActive(current => current === name ? null : name)

  return <div className="relative ml-auto hidden items-center gap-2 md:flex">
    <button ref={bellRef} type="button" onClick={() => toggle('alerts')} aria-label="通知摘要" aria-haspopup="dialog" aria-expanded={active === 'alerts'} aria-controls="header-alerts-popover" className="grid h-8 w-8 place-items-center rounded-medium text-text-muted transition-colors hover:bg-surface-muted hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30"><Bell className="h-3.5 w-3.5" aria-hidden="true" /></button>
    <button ref={avatarRef} type="button" onClick={() => toggle('account')} aria-label="应用菜单" aria-haspopup="menu" aria-expanded={active === 'account'} aria-controls="header-account-menu" className="grid h-[26px] w-[26px] place-items-center rounded-full bg-border-strong text-text-primary transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/30"><UserRound className="h-3.5 w-3.5" aria-hidden="true" /></button>

    {active === 'alerts' && <div ref={panelRef} id="header-alerts-popover" role="dialog" aria-label="通知摘要" className="absolute right-9 top-[calc(100%+8px)] z-50 w-72 rounded-large border border-border-strong bg-surface-raised p-3 shadow-xl">
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-text-primary">通知摘要</h2><span className="inline-flex items-center gap-1.5 text-label text-text-muted"><span className={`h-1.5 w-1.5 rounded-full ${statusTone}`} aria-hidden="true" />{statusText}</span></div>
      <dl className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-medium bg-surface-muted px-2.5 py-2"><dt className="text-label text-text-muted">今日新增</dt><dd className="mt-0.5 text-sm font-semibold tabular-nums text-text-primary">{dashboard?.new_today ?? 0}</dd></div>
        <div className="rounded-medium bg-surface-muted px-2.5 py-2"><dt className="text-label text-text-muted">未读通知</dt><dd className="mt-0.5 text-sm font-semibold tabular-nums text-text-primary">{dashboard?.unread ?? 0}</dd></div>
      </dl>
      <div className="mt-3 border-t border-border/70 pt-2 text-metadata text-text-muted"><p>最近检查：{crawler?.last_run ? relativeTime(crawler.last_run) : '尚无检查记录'}</p>{crawler?.last_run && <p className="mt-1">上次新增 {crawler.new_count} 条，更新 {crawler.updated_count} 条</p>}</div>
      <div className="mt-3 flex gap-2"><Link data-popup-focus to="/notices?read=0" onClick={() => setActive(null)} className="flex h-8 flex-1 items-center justify-center rounded-medium border border-border text-xs text-text-secondary hover:bg-surface-muted hover:text-text-primary">查看未读</Link><Link to="/deadlines" onClick={() => setActive(null)} className="flex h-8 flex-1 items-center justify-center rounded-medium border border-border text-xs text-text-secondary hover:bg-surface-muted hover:text-text-primary">即将截止</Link></div>
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
  return <header className="relative z-20 flex h-header-height items-center gap-2 border-b border-border/70 bg-header-surface px-4 sm:gap-3 md:px-[18px]">
    <div className="min-w-0 md:hidden"><span data-testid="route-context" className="block truncate text-sm font-semibold">{title}</span></div>
    <SearchDialog />
    <HeaderActions crawler={crawler} crawlerError={crawlerError} dashboard={dashboard} />
    <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted md:hidden" aria-label={theme === 'dark' ? '切换浅色主题' : '切换深色主题'}>{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
  </header>
}

function BottomNav({ moreOpen, onMore, triggerRef }: { moreOpen: boolean; onMore: () => void; triggerRef: RefObject<HTMLButtonElement | null> }) {
  return <nav className="fixed inset-x-0 bottom-0 z-40 flex h-mobile-nav-height items-center justify-around border-t border-border bg-surface md:hidden" aria-label="底部导航">
    {mobileNavItems.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end className={({ isActive }) => cn('flex h-full min-w-14 flex-col items-center justify-center gap-1 text-label', isActive ? 'font-medium text-accent-soft-text' : 'text-text-muted')}><Icon className="h-5 w-5" />{label}</NavLink>)}
    <button ref={triggerRef} onClick={onMore} className="flex h-full min-w-14 flex-col items-center justify-center gap-1 text-label text-text-muted" aria-label="更多导航" aria-haspopup="dialog" aria-expanded={moreOpen} aria-controls="mobile-navigation-dialog"><Menu className="h-5 w-5" />更多</button>
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
  const { pathname } = useLocation()
  const detailMatch = matchPath('/notices/:id', pathname)
  const detailId = detailMatch?.params.id
  const noticeWorkspaceRoute = pathname === '/notices' || Boolean(detailId)
  const crawler = useQuery({ queryKey: ['crawler'], queryFn: ({ signal }) => getCrawlerStatus({ signal }), refetchInterval: 60_000 })
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: ({ signal }) => getDashboard({ signal }) })
  const toggleCollapse = () => { const next = !collapsed; setCollapsed(next); localStorage.setItem('jlu-sidebar', next ? 'collapsed' : 'expanded') }
  const counts: Counts = { 收件箱: dashboard.data?.unread, 重要: dashboard.data?.important, 即将截止: dashboard.data?.upcoming_deadlines, 未读: dashboard.data?.unread, 今日新增: dashboard.data?.new_today }

  return <div className="min-h-screen bg-app-canvas text-text-primary transition-colors md:pb-[6px] md:pl-[12px] md:pt-[6px]">
    <div className={cn('min-h-screen bg-app-frame md:grid md:h-[calc(100vh-12px)] md:min-h-0 md:overflow-hidden md:rounded-app md:ring-1 md:ring-inset md:ring-border md:grid-cols-[var(--spacing-sidebar-expanded)_minmax(0,1fr)]', collapsed && 'md:grid-cols-[var(--spacing-sidebar-collapsed)_minmax(0,1fr)] xl:grid-cols-[var(--spacing-sidebar-expanded)_minmax(0,1fr)]')}>
      <Sidebar collapsed={collapsed} onToggle={toggleCollapse} online={!crawler.isError} lastRun={crawler.data?.last_run} counts={counts} />
      <div className="min-w-0 md:grid md:min-h-0 md:grid-rows-[var(--spacing-header-height)_minmax(0,1fr)]">
        <Header title={getRouteTitle(pathname)} crawler={crawler.data} crawlerError={crawler.isError} dashboard={dashboard.data} />
        {noticeWorkspaceRoute ? <div className="min-w-0 md:grid md:min-h-0 md:grid-cols-[minmax(0,calc(50%+1px))_minmax(0,calc(50%-1px))]">
          <section className={cn('min-w-0 border-r border-border/60 bg-list-surface md:min-h-0 md:overflow-hidden', detailId && 'hidden md:block')} aria-label="通知工作区"><main className="h-full p-4 sm:p-5 md:p-0"><NoticesPage selectedId={detailId ? Number(detailId) : null} /></main></section>
          <aside className={cn('min-w-0 bg-detail-surface md:min-h-0 md:overflow-y-auto', detailId ? 'block' : 'hidden md:grid md:place-items-center')} aria-label="通知详情工作区">{detailId ? <NoticeDetailPage embeddedId={Number(detailId)} /> : <div className="max-w-sm px-8 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-large bg-accent-soft text-accent-soft-text"><Bell className="h-5 w-5" /></div><h2 className="mt-4 text-section-heading">请选择一条通知</h2><p className="mt-2 text-body text-text-muted">通知详情将在这里显示。</p></div>}</aside>
        </div> : <main className="min-h-0 overflow-y-auto bg-bg p-4 sm:p-5 lg:p-6"><Outlet /></main>}
      </div>
    </div>
    <BottomNav moreOpen={moreOpen} onMore={() => setMoreOpen(true)} triggerRef={moreTriggerRef} />
    <MorePanel open={moreOpen} onOpenChange={setMoreOpen} triggerRef={moreTriggerRef} />
  </div>
}
