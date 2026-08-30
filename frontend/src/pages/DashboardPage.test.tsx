import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { getDashboard, getImportantNotices } from '../api/dashboard'
import { ToastProvider } from '../stores/toast'
import { DashboardPage } from './DashboardPage'

vi.mock('../api/dashboard', () => ({ getDashboard: vi.fn(), getImportantNotices: vi.fn() }))

const notice = {
  id: 1, title: '重要测试通知', url: 'https://example.test/1', publish_date: '2026-08-30', publisher: '测试来源',
  category: 'research', importance_score: 80, registration_start: null, registration_deadline: null,
  event_start: null, event_end: null, deadline_status: 'unknown', days_until_deadline: null, status: 'new',
  first_seen_at: '2026-08-30T00:00:00Z', last_seen_at: '2026-08-30T00:00:00Z', updated_at: '2026-08-30T00:00:00Z',
  is_read: false, is_archived: false, is_favorite: false, sources: [],
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><ToastProvider><MemoryRouter><DashboardPage/></MemoryRouter></ToastProvider></QueryClientProvider>)
}

describe('DashboardPage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(getDashboard).mockReset()
    vi.mocked(getImportantNotices).mockReset()
  })

  it('renders decision metrics, priority notices, recent notices and source status', async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      new_today: 2, urgent: 1, important: 3, upcoming_deadlines: 4, unread: 5,
      source_status: [
        { code: 'cse', name: '网络安全学院', enabled: true, status: 'healthy', message: null },
        { code: 'oa', name: 'OA', enabled: false, status: 'disabled', message: null },
      ],
      recent_notices: [notice],
    })
    vi.mocked(getImportantNotices).mockResolvedValue([notice])

    renderPage()
    expect(await screen.findByText('今日新增')).toBeInTheDocument()
    expect(screen.getByText('未读通知')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: '重要测试通知' })).toHaveLength(2)
    expect(screen.getByText('1 个正常 · 1 个暂停')).toBeInTheDocument()
  })

  it('shows a dedicated error instead of an empty dashboard', async () => {
    vi.mocked(getDashboard).mockRejectedValue(new ApiError({ kind: 'HTTP_ERROR', message: '服务暂不可用', endpoint: '/api/dashboard', status: 500 }))
    vi.mocked(getImportantNotices).mockResolvedValue([])

    renderPage()
    expect(await screen.findByRole('heading', { name: '暂时无法完成请求' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '尚无通知' })).not.toBeInTheDocument()
  })

  it('shows a true-empty state with a source action', async () => {
    vi.mocked(getDashboard).mockResolvedValue({ new_today: 0, urgent: 0, important: 0, upcoming_deadlines: 0, unread: 0, source_status: [], recent_notices: [] })
    vi.mocked(getImportantNotices).mockResolvedValue([])

    renderPage()
    expect(await screen.findByRole('heading', { name: '尚无通知' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看数据源' })).toHaveAttribute('href', '/sources')
  })
})

