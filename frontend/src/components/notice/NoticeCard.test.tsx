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

function renderCard(notice: Notice, props: { compact?: boolean; selected?: boolean; onSelect?: (id: number) => void } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter><NoticeCard notice={notice} {...props} /></MemoryRouter>
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

  it.each([true, false])('labels a single-page timestamp as detection time (compact=%s)', compact => {
    renderCard({ ...base, publish_date: null, sources: [{ code: 'lqb', name: '蓝桥杯赛事信息（吉林大学）', url: 'https://lus-jlu.github.io/lqb.html' }] }, { compact })
    expect(screen.getByText(/首次检测：/)).toBeVisible()
    expect(screen.queryByText('尚无记录')).not.toBeInTheDocument()
    if (compact) expect(screen.getByText(/首次检测：/)).toHaveAttribute('datetime', base.first_seen_at)
  })

  it('keeps selected, unread, important, updated and favorite states independent in the compact row', () => {
    renderCard({ ...base, is_favorite: true, status: 'updated' }, { compact: true, selected: true })
    expect(screen.getByRole('link', { name: `打开${base.title}` })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('未读')).toBeVisible()
    expect(screen.getByText('重要')).toBeVisible()
    expect(screen.getByText('已更新')).toBeVisible()
    expect(screen.getByText('科研/实验室')).toBeVisible()
    expect(screen.getByRole('button', { name: '取消收藏' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('opens a compact row through the existing selection callback without coupling the favorite action', async () => {
    const onSelect = vi.fn()
    renderCard(base, { compact: true, onSelect })
    const link = screen.getByRole('link', { name: `打开${base.title}` })
    const button = screen.getByRole('button', { name: '收藏通知' })
    expect(link).not.toContainElement(button)
    fireEvent.click(button)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(onSelect).not.toHaveBeenCalled()
    fireEvent.click(link)
    expect(onSelect).toHaveBeenCalledExactlyOnceWith(base.id)
  })

  it.each([
    ['today', 0, '今天截止', 'bg-deadline-danger-bg'],
    ['urgent', 3, '3 天后截止', 'bg-deadline-warning-bg'],
    ['upcoming', 12, '12 天后截止', 'bg-deadline-neutral-bg'],
    ['expired', -1, '已截止', 'bg-deadline-neutral-bg'],
  ] as const)('renders compact deadline %s without changing its calculated label', (deadline_status, days_until_deadline, label, tone) => {
    renderCard({ ...base, deadline_status, days_until_deadline, is_read: true, importance_score: 20 }, { compact: true })
    expect(screen.getByText(label)).toHaveClass(tone)
    expect(screen.getByText('已读')).toBeVisible()
    expect(screen.queryByText('重要')).not.toBeInTheDocument()
  })

  it('omits an absent compact deadline and preserves the complete accessible long title', () => {
    const title = '关于开展本科生科研训练计划项目申报与材料提交工作的通知'.repeat(8)
    renderCard({ ...base, title, registration_deadline: null, deadline_status: 'none', days_until_deadline: null }, { compact: true })
    expect(screen.getByRole('link', { name: `打开${title}` })).toHaveAttribute('title', title)
    expect(screen.queryByText(/截止|时间待定/)).not.toBeInTheDocument()
  })

  it('shows the importance semantic label instead of a raw score', () => {
    renderCard({ ...base, importance_score: 80 })
    expect(screen.getByText('重要')).toBeInTheDocument()
    expect(screen.queryByText(/优先级/)).not.toBeInTheDocument()
  })

  it('shows the deadline semantics text', () => {
    renderCard({ ...base, registration_deadline: '2026-09-05', deadline_status: 'urgent', days_until_deadline: 2 })
    expect(screen.getByText('2 天后截止')).toBeInTheDocument()
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
