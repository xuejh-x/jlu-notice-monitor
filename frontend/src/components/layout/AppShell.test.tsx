import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeProvider } from '../../stores/theme'
import { ToastProvider } from '../../stores/toast'
import { AppShell } from './AppShell'

const crawlerStatus = { running: false, current_started_at: null, last_run: '2026-08-30T08:00:00Z', last_duration: 12, new_count: 1, updated_count: 0, source_results: [] }
const dashboard = { total_count: 18, new_today: 5, urgent: 1, important: 2, upcoming_deadlines: 3, unread: 4, source_status: [], recent_notices: [] }
const reminders = { unread: 1, items: [{ id: 41, type: 'DEADLINE_APPROACHING', notice_id: 42, source_id: 1, severity: 'warning', title: '报名即将截止', body: '还有 3 天截止，点击查看详情。', route: '/notices/42', local_date: '2026-09-03', read_at: null, created_at: '2026-09-03T08:00:00' }] }
const notice = { id: 42, title: 'MOCK / FIXTURE reminder target', url: 'https://example.test/42', publish_date: '2026-09-03', publisher: 'MOCK', category: 'other', importance_score: 70, registration_start: null, registration_deadline: '2026-09-06', event_start: null, event_end: null, deadline_status: 'urgent', days_until_deadline: 3, status: 'active', first_seen_at: '2026-09-03T00:00:00', last_seen_at: '2026-09-03T00:00:00', updated_at: '2026-09-03T00:00:00', is_read: false, is_archived: false, is_favorite: false, sources: [{ code: 'fixture', name: 'MOCK' }], content: 'fixture body', target_students: null, registration_method: null, competition_level: null, attachments: [], updates: [] }

function renderShell(initialEntry = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[initialEntry]}>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<div>home</div>} />
                <Route path="today" element={<div>today</div>} />
                <Route path="deadlines" element={<div>deadlines</div>} />
                <Route path="competitions" element={<div>competitions</div>} />
                <Route path="competitions/algorithm" element={<div>algorithm</div>} />
                <Route path="cybersecurity" element={<div>cyber</div>} />
                <Route path="training" element={<div>training</div>} />
                <Route path="research" element={<div>research</div>} />
                <Route path="postgraduate" element={<div>postgrad</div>} />
                <Route path="favorites" element={<div>favorites</div>} />
                <Route path="notices" element={<div>notices</div>} />
                <Route path="notices/:id" element={<div>detail</div>} />
                <Route path="sources" element={<div>sources</div>} />
                <Route path="settings" element={<div>settings</div>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('AppShell navigation', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      const body = url.includes('/dashboard') ? dashboard
        : url.includes('/api/notifications?') ? reminders
        : url.includes('/api/notices/42') ? notice
        : url.includes('/api/notices?') ? { items: [notice], total: 1, page: 1, page_size: 20, total_pages: 1 }
        : crawlerStatus
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    }))
  })

  it('renders the compact desktop sidebar destinations', async () => {
    renderShell('/')
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    for (const label of ['全部通知', '重要通知', '即将截止', '未读通知', '收藏']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    }
    await waitFor(() => expect(within(nav).getByRole('link', { name: '全部通知' })).toHaveTextContent('18'))
    expect(within(nav).getByRole('link', { name: '未读通知' })).toHaveTextContent('4')
    const management = screen.getByRole('navigation', { name: '应用管理' })
    expect(within(management).getByRole('link', { name: '来源管理' })).toHaveAttribute('href', '/sources')
    expect(within(management).getByRole('link', { name: '设置与偏好' })).toHaveAttribute('href', '/settings')
    expect(screen.queryByText('今日概览')).not.toBeInTheDocument()
  })

  it('opens recent notification events and closes with Escape while restoring focus', async () => {
    renderShell('/')
    await screen.findByRole('navigation', { name: '主导航' })
    const trigger = await screen.findByRole('button', { name: '提醒中心，1 条未读提醒' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(trigger)
    const popover = await screen.findByRole('dialog', { name: '提醒中心' })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(within(popover).getByText('检查服务空闲')).toBeInTheDocument()
    expect(within(popover).getByRole('button', { name: /报名即将截止/ })).toHaveTextContent('还有 3 天截止')
    expect(within(popover).getByText('1 条未读提醒')).toBeInTheDocument()
    expect(within(popover).getByRole('link', { name: '提醒设置' })).toHaveAttribute('href', '/settings')
    await waitFor(() => expect(within(popover).getByRole('button', { name: /报名即将截止/ })).toHaveFocus())
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '通知摘要' })).not.toBeInTheDocument())
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('marks a reminder read and routes its click to the notice detail', async () => {
    renderShell('/')
    const trigger = await screen.findByRole('button', { name: '提醒中心，1 条未读提醒' })
    fireEvent.click(trigger)
    fireEvent.click(await screen.findByRole('button', { name: /报名即将截止/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'MOCK / FIXTURE reminder target' })).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/notifications/41/read'), expect.objectContaining({ method: 'POST' })))
  })

  it('opens the application menu, exposes real actions, and closes on outside click', async () => {
    renderShell('/')
    await screen.findByRole('navigation', { name: '主导航' })
    const trigger = screen.getByRole('button', { name: '应用菜单' })
    fireEvent.click(trigger)
    const menu = await screen.findByRole('menu', { name: '应用菜单' })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(within(menu).getByText('本地通知聚合助手')).toBeInTheDocument()
    expect(within(menu).getByRole('menuitem', { name: '设置' })).toHaveAttribute('href', '/settings')
    const theme = within(menu).getByRole('menuitem', { name: '切换深色主题' })
    await waitFor(() => expect(within(menu).getByRole('menuitem', { name: '设置' })).toHaveFocus())
    fireEvent.click(theme)
    expect(localStorage.getItem('jlu-theme')).toBe('dark')
    await waitFor(() => expect(screen.queryByRole('menu', { name: '应用菜单' })).not.toBeInTheDocument())

    fireEvent.click(trigger)
    await screen.findByRole('menu', { name: '应用菜单' })
    fireEvent.pointerDown(document.body)
    await waitFor(() => expect(screen.queryByRole('menu', { name: '应用菜单' })).not.toBeInTheDocument())
    expect(screen.queryByText('+')).not.toBeInTheDocument()
  })

  it('marks the current route active with aria-current', async () => {
    renderShell('/notices?favorite=1')
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    expect(within(nav).getByRole('link', { name: '收藏' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: '全部通知' })).not.toHaveAttribute('aria-current')
  })

  it('preserves the selected view on a detail URL with search and pagination', async () => {
    renderShell('/notices/42?favorite=1&q=fixture&page=2')
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    expect(within(nav).getByRole('link', { name: '收藏' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: '返回通知列表' })).toHaveAttribute('href', '/notices?favorite=1&q=fixture&page=2')
  })

  it('keeps an auto-read notice in the current unread list when returning from detail', async () => {
    let markedRead = false
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST' && url.endsWith('/api/notices/42/read')) {
        markedRead = true
        return Promise.resolve(new Response(JSON.stringify({ notice_id: 42, is_read: true }), { status: 200 }))
      }
      if (url.includes('/api/notices/42')) return Promise.resolve(new Response(JSON.stringify({ ...notice, is_read: markedRead }), { status: 200 }))
      if (url.includes('/api/notices?')) return Promise.resolve(new Response(JSON.stringify({ items: markedRead ? [] : [notice], total: markedRead ? 0 : 1, page: 1, page_size: 20, total_pages: 1 }), { status: 200 }))
      if (url.includes('/dashboard')) return Promise.resolve(new Response(JSON.stringify({ ...dashboard, unread: markedRead ? 3 : 4 }), { status: 200 }))
      if (url.includes('/api/notifications?')) return Promise.resolve(new Response(JSON.stringify(reminders), { status: 200 }))
      return Promise.resolve(new Response(JSON.stringify(crawlerStatus), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderShell('/notices?read=0')
    const listLink = await screen.findByRole('link', { name: `打开${notice.title}` })
    fireEvent.click(listLink)

    expect(await screen.findByRole('heading', { level: 1, name: notice.title })).toBeInTheDocument()
    await waitFor(() => expect(markedRead).toBe(true))
    const retainedLink = screen.getByRole('link', { name: `打开${notice.title}` })
    expect(within(retainedLink.closest('article') as HTMLElement).getByText('已读')).toBeInTheDocument()

    const listGetsBeforeReturn = fetchMock.mock.calls.filter(([input, init]) => !init?.method && String(input).includes('/api/notices?')).length
    expect(listGetsBeforeReturn).toBe(1)

    fireEvent.click(screen.getAllByRole('link', { name: '返回通知列表' })[0])
    expect(screen.getByRole('link', { name: `打开${notice.title}` })).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([input, init]) => !init?.method && String(input).includes('/api/notices?')).length).toBe(1)
  })

  it('uses the existing source codes and keeps a source active while paging', async () => {
    renderShell('/notices?source=ccst&page=2')
    const nav = await screen.findByRole('navigation', { name: '通知来源' })
    expect(within(nav).getByRole('link', { name: '计算机学院' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getAllByRole('link').map(link => link.getAttribute('href'))).toEqual([
      '/notices?source=cse', '/notices?source=ccst', '/notices?source=csw',
      '/notices?source=jwc', '/notices?source=innovation', '/notices?source=oa',
    ])
  })

  it('keeps the full navigation accessible from the desktop sidebar', async () => {
    renderShell('/')
    const trigger = screen.getByRole('button', { name: '全部功能' })
    fireEvent.click(trigger)
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('link', { name: '科研 / 实验室' })).toHaveAttribute('href', '/research')
    fireEvent.click(within(dialog).getByRole('button', { name: '关闭菜单' }))
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('collapses the sidebar and persists the preference', async () => {
    renderShell('/')
    await screen.findByRole('navigation', { name: '主导航' })
    const toggle = screen.getByRole('button', { name: '折叠侧边栏' })
    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: '展开侧边栏' })).toBeInTheDocument()
    expect(localStorage.getItem('jlu-sidebar')).toBe('collapsed')
  })

  it('renders the mobile bottom nav with four destinations plus More', async () => {
    renderShell('/')
    const nav = await screen.findByRole('navigation', { name: '底部导航' })
    for (const label of ['首页', '今日', '截止', '收藏']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    }
    expect(within(nav).getByRole('button', { name: '更多导航' })).toBeInTheDocument()
  })

  it('opens the More panel with the full navigation and closes it', async () => {
    renderShell('/')
    await screen.findByRole('navigation', { name: '主导航' })
    const trigger = screen.getByRole('button', { name: '更多导航' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('navigation', { name: '完整导航' })).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: '全部通知' })).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: '关闭菜单' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveFocus()
  })

  it('shows the mobile route context for a dynamic route', async () => {
    renderShell('/notices/42')
    await screen.findByRole('navigation', { name: '主导航' })
    expect(screen.getByTestId('route-context')).toHaveTextContent('通知详情')
  })
})
