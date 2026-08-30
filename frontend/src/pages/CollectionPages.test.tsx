import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getNotices, getTodayNotices } from '../api/notices'
import { ToastProvider } from '../stores/toast'
import { FeedPage } from './FeedPage'
import { TodayPage } from './TodayPage'

vi.mock('../api/notices', () => ({ getNotices: vi.fn(), getTodayNotices: vi.fn() }))

function renderPage(page: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><ToastProvider><MemoryRouter>{page}</MemoryRouter></ToastProvider></QueryClientProvider>)
}

describe('remaining collection pages', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(getNotices).mockReset()
    vi.mocked(getTodayNotices).mockReset()
  })

  it('uses the real Today query and a contextual empty state', async () => {
    vi.mocked(getTodayNotices).mockResolvedValue([])
    renderPage(<TodayPage/>)
    expect(await screen.findByRole('heading', { level: 1, name: '今日新通知' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '今天暂无新通知' })).toBeInTheDocument()
  })

  it('renders a shared preset feed title, result count and contextual empty state', async () => {
    vi.mocked(getNotices).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
    renderPage(<FeedPage title="网络安全" description="安全竞赛、活动与相关通知。" categories={['cybersecurity_competition']}/>)
    expect(await screen.findByRole('heading', { level: 1, name: '网络安全' })).toBeInTheDocument()
    expect(await screen.findByText('安全竞赛、活动与相关通知。 共 0 条。')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '暂无网络安全相关通知' })).toBeInTheDocument()
    expect(getNotices).toHaveBeenCalledWith(expect.objectContaining({ category: 'cybersecurity_competition' }), expect.any(Object))
  })
})
