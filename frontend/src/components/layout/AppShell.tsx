import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { Bell, Menu, Moon, PanelLeftClose, PanelLeftOpen, Sun, X } from 'lucide-react'
import { useRef, useState, type RefObject } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { getCrawlerStatus } from '../../api/crawler'
import { useTheme } from '../../stores/theme'
import { cn } from '../../utils/cn'
import { relativeTime } from '../../utils/format'
import { SearchDialog } from '../search/SearchDialog'
import { CrawlerButton } from './CrawlerButton'
import { getRouteTitle, mobileNavItems, navGroups } from './navigation'

function NavItems({ collapsed = false, ariaLabel, onSelect }: { collapsed?: boolean; ariaLabel: string; onSelect?: () => void }) {
  return (
    <nav className="space-y-5" aria-label={ariaLabel}>
      {navGroups.map(group => (
        <div key={group.label}>
          {!collapsed && <div className="mb-1 px-3 text-label font-semibold tracking-wider text-text-muted">{group.label}</div>}
          <div className="space-y-0.5">
            {group.items.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end
                onClick={onSelect}
                title={collapsed ? label : undefined}
                className={({ isActive }) => cn(
                  'flex h-11 items-center rounded-medium text-sm transition-colors md:h-9',
                  collapsed ? 'justify-center px-2' : 'gap-3 px-3',
                  isActive
                    ? 'bg-accent-soft font-medium text-accent-soft-text'
                    : 'text-text-secondary hover:bg-surface-muted hover:text-text-primary',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && label}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  )
}

function Sidebar({ collapsed, onToggle, online, lastRun }: { collapsed: boolean; onToggle: () => void; online: boolean; lastRun?: string | null }) {
  return (
    <aside className={cn('fixed inset-y-0 left-0 z-30 hidden border-r border-border bg-surface px-3 py-4 transition-[width] md:flex md:flex-col', collapsed ? 'w-sidebar-collapsed' : 'w-sidebar-expanded')}>
      <div className={cn('mb-5 flex h-10 items-center', collapsed ? 'justify-center' : 'gap-3 px-2')}>
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-large bg-accent text-text-inverse"><Bell className="h-5 w-5" /></div>
        {!collapsed && <div className="min-w-0"><div className="truncate font-semibold tracking-tight">吉大通知助手</div><div className="text-xs text-text-muted">个人通知情报中心</div></div>}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto"><NavItems collapsed={collapsed} ariaLabel="主导航" /></div>
      <div className="mt-3 border-t border-border pt-3">
        {!collapsed && (
          <div className="mb-2 rounded-medium bg-surface-muted p-3 text-xs">
            <div className="flex items-center gap-2 font-medium"><span className={cn('h-2 w-2 rounded-full', online ? 'bg-success' : 'bg-danger')} />{online ? '后端在线' : '后端离线'}</div>
            <div className="mt-1.5 text-text-muted">上次同步 {relativeTime(lastRun)}</div>
          </div>
        )}
        <button onClick={onToggle} className={cn('flex h-9 w-full items-center rounded-medium text-xs text-text-muted hover:bg-surface-muted', collapsed ? 'justify-center' : 'gap-2 px-3')} aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}>{collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <><PanelLeftClose className="h-4 w-4" />折叠侧边栏</>}</button>
      </div>
    </aside>
  )
}

function Header({ title }: { title: string }) {
  const { theme, setTheme } = useTheme()
  return (
    <header className="sticky top-0 z-20 flex h-header-height items-center gap-2 border-b border-border bg-surface/90 px-4 backdrop-blur sm:gap-3 sm:px-6 lg:px-8">
      <div className="min-w-0 md:hidden"><span data-testid="route-context" className="block truncate text-sm font-semibold">{title}</span></div>
      <SearchDialog />
      <div className="hidden md:block"><CrawlerButton /></div>
      <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted md:h-9 md:w-9" aria-label={theme === 'dark' ? '切换浅色主题' : '切换深色主题'}>{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
    </header>
  )
}

function BottomNav({ moreOpen, onMore, triggerRef }: { moreOpen: boolean; onMore: () => void; triggerRef: RefObject<HTMLButtonElement | null> }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex h-mobile-nav-height items-center justify-around border-t border-border bg-surface md:hidden" aria-label="底部导航">
      {mobileNavItems.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end className={({ isActive }) => cn('flex h-full min-w-14 flex-col items-center justify-center gap-1 text-label', isActive ? 'font-medium text-accent-soft-text' : 'text-text-muted')}><Icon className="h-5 w-5" />{label}</NavLink>
      ))}
      <button ref={triggerRef} onClick={onMore} className="flex h-full min-w-14 flex-col items-center justify-center gap-1 text-label text-text-muted" aria-label="更多导航" aria-haspopup="dialog" aria-expanded={moreOpen} aria-controls="mobile-navigation-dialog"><Menu className="h-5 w-5" />更多</button>
    </nav>
  )
}

function MorePanel({ open, onOpenChange, triggerRef }: { open: boolean; onOpenChange: (open: boolean) => void; triggerRef: RefObject<HTMLButtonElement | null> }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-overlay" />
        <Dialog.Content id="mobile-navigation-dialog" aria-describedby={undefined} onCloseAutoFocus={event => { event.preventDefault(); triggerRef.current?.focus() }} className="fixed inset-y-0 right-0 z-50 w-[min(86vw,340px)] overflow-y-auto border-l border-border-strong bg-surface p-4 shadow-2xl">
          <Dialog.Title className="flex items-center justify-between font-semibold">全部功能<Dialog.Close className="grid h-11 w-11 place-items-center rounded-medium hover:bg-surface-muted" aria-label="关闭菜单"><X className="h-5 w-5" /></Dialog.Close></Dialog.Title>
          <div className="mt-5"><NavItems ariaLabel="完整导航" onSelect={() => onOpenChange(false)} /></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('jlu-sidebar') === 'collapsed')
  const [moreOpen, setMoreOpen] = useState(false)
  const moreTriggerRef = useRef<HTMLButtonElement>(null)
  const { pathname } = useLocation()
  const crawler = useQuery({ queryKey: ['crawler'], queryFn: ({ signal }) => getCrawlerStatus({ signal }), refetchInterval: 60_000 })
  const toggleCollapse = () => { const next = !collapsed; setCollapsed(next); localStorage.setItem('jlu-sidebar', next ? 'collapsed' : 'expanded') }

  return (
    <div className="min-h-screen bg-bg text-text-primary transition-colors">
      <Sidebar collapsed={collapsed} onToggle={toggleCollapse} online={!crawler.isError} lastRun={crawler.data?.last_run} />
      <div className={cn('transition-[padding]', collapsed ? 'md:pl-sidebar-collapsed' : 'md:pl-sidebar-expanded')}>
        <Header title={getRouteTitle(pathname)} />
        <main className="mx-auto max-w-content-max p-4 sm:p-6 lg:p-8"><Outlet /></main>
      </div>
      <BottomNav moreOpen={moreOpen} onMore={() => setMoreOpen(true)} triggerRef={moreTriggerRef} />
      <MorePanel open={moreOpen} onOpenChange={setMoreOpen} triggerRef={moreTriggerRef} />
    </div>
  )
}
