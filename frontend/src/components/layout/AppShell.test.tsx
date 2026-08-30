import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeProvider } from '../../stores/theme'
import { ToastProvider } from '../../stores/toast'
import { AppShell } from './AppShell'

const crawlerStatus = { running: false, current_started_at: null, last_run: '2026-08-30T08:00:00Z', last_duration: 12, new_count: 1, updated_count: 0, source_results: [] }

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
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(crawlerStatus), { status: 200 })))
  })

  it('renders the sidebar with all grouped destinations', async () => {
    renderShell('/')
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    for (const label of ['首页', '今日', '即将截止', '全部竞赛', '收藏', '全部通知', '数据源', '设置']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    }
  })

  it('marks the current route active with aria-current', async () => {
    renderShell('/favorites')
    const nav = await screen.findByRole('navigation', { name: '主导航' })
    expect(within(nav).getByRole('link', { name: '收藏' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: '首页' })).not.toHaveAttribute('aria-current')
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
