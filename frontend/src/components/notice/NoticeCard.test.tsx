import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getNotice } from '../../api/notices'
import { ToastProvider } from '../../stores/toast'
import type { Notice } from '../../types'
import { NoticeCard } from './NoticeCard'

const base: Notice = {
  id: 7, title: '测试通知标题', url: 'https://example.test/n', publish_date: '2026-08-30', publisher: '计算机学院',
  category: 'research', importance_score: 80, registration_start: null, registration_deadline: '2026-09-05',
  event_start: null, event_end: null, deadline_status: 'urgent', days_until_deadline: 6,
  status: 'new', first_seen_at: '2026-08-30T00:00:00Z', last_seen_at: '2026-08-30T00:00:00Z', updated_at: '2026-08-30T00:00:00Z',
  is_read: false, is_archived: false, is_favorite: false, sources: [{ code: 'cse', name: '网络安全学院', url: 'u' }],
}

function renderCard(notice: Notice) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter><NoticeCard notice={notice} /></MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('NoticeCard', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ notice_id: 7, is_favorite: true }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
  })

  it('renders the title as a link with the correct href', () => {
    renderCard(base)
    expect(screen.getByRole('link', { name: '测试通知标题' })).toHaveAttribute('href', '/notices/7')
  })

  it('shows the importance semantic label instead of a raw score', () => {
    renderCard({ ...base, importance_score: 80 })
    expect(screen.getByText('重要')).toBeInTheDocument()
    expect(screen.queryByText(/优先级/)).not.toBeInTheDocument()
  })

  it('shows the deadline semantics text', () => {
    renderCard({ ...base, registration_deadline: '2026-09-05', deadline_status: 'urgent', days_until_deadline: 2 })
    expect(screen.getByText('剩余 2 天')).toBeInTheDocument()
  })

  it('announces read/unread state for screen readers', () => {
    renderCard(base)
    expect(screen.getByText('未读')).toBeInTheDocument()
  })

  it('keeps the favorite action as a separate button, not inside the title link', async () => {
    renderCard(base)
    const link = screen.getByRole('link', { name: '测试通知标题' })
    const favorite = screen.getByRole('button', { name: '收藏通知' })
    expect(link).not.toContainElement(favorite)
    fireEvent.click(favorite)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  })

  it('invalidates the notice detail cache after favoriting so reopening shows the new state', async () => {
    function DetailProbe() {
      const { data } = useQuery({ queryKey: ['notice', 7], queryFn: ({ signal }) => getNotice(7, { signal }) })
      return <span data-testid="detail-probe">{data?.is_favorite ? 'favorited' : 'not-favorited'}</span>
    }
    const controlled = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({ notice_id: 7, is_favorite: true }), { status: 200 }))
      return Promise.resolve(new Response(JSON.stringify({ ...base, id: 7, is_favorite: false }), { status: 200 }))
    })
    vi.stubGlobal('fetch', controlled)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter>
            <NoticeCard notice={base} />
            <DetailProbe />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    )

    await screen.findByTestId('detail-probe')
    const detailGets = () => controlled.mock.calls.filter(([input, init]) => !init?.method && String(input).includes('/notices/7')).length
    expect(detailGets()).toBe(1)

    fireEvent.click(screen.getByRole('button', { name: '收藏通知' }))
    await waitFor(() => expect(detailGets()).toBe(2))
  })
})
