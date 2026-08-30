import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode, useState } from 'react'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getDashboard } from '../api/dashboard'
import { searchNotices } from '../api/notices'
import { ToastProvider } from '../stores/toast'
import { NoticeDetailPage } from './NoticeDetailPage'

vi.mock('../components/ui/ExternalAnchor', () => ({
  ExternalAnchor: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a>,
}))

const detail = {
  id: 42,
  title: '测试通知',
  url: 'https://example.test/notice',
  publish_date: '2026-08-30',
  publisher: '测试单位',
  category: 'other',
  importance_score: 80,
  registration_start: null,
  registration_deadline: null,
  event_start: null,
  event_end: null,
  deadline_status: 'unknown',
  days_until_deadline: null,
  status: 'new',
  first_seen_at: '2026-08-30T00:00:00Z',
  last_seen_at: '2026-08-30T00:00:00Z',
  updated_at: '2026-08-30T00:00:00Z',
  is_read: true,
  is_archived: false,
  is_favorite: false,
  sources: [],
  content: null,
  target_students: null,
  registration_method: null,
  competition_level: null,
  attachments: [{ filename: '真实附件.pdf', url: 'https://example.test/file.pdf', type: 'pdf' }],
  updates: [],
}

function DetailHarness() {
  const [renderCount, setRenderCount] = useState(0)
  return <>
    <Link to="/notices/2">打开通知 B</Link>
    <button onClick={() => setRenderCount(value => value + 1)}>普通重渲染</button>
    <span data-testid="render-count">{renderCount}</span>
    <Routes><Route path="/notices/:id" element={<NoticeDetailPage />}/></Routes>
  </>
}

function renderDetail(id = '42') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/notices/${id}`]}>
            <DetailHarness/>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
}

const readCalls = (fetchMock: ReturnType<typeof vi.fn>) => fetchMock.mock.calls
  .filter(([input, init]) => init?.method === 'POST' && String(input).endsWith('/read'))
  .map(([input]) => String(input))

describe('NoticeDetailPage', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('renders the backend attachment filename', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(detail), { status: 200 }))))

    renderDetail()
    expect(await screen.findByText('真实附件.pdf')).toBeInTheDocument()
  })

  it('renders a dedicated 404 state with a return link', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ detail: '通知不存在' }), { status: 404 }))))

    renderDetail('404')
    expect(await screen.findByRole('heading', { level: 1, name: '通知不存在' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回通知列表' })).toHaveAttribute('href', '/notices')
    expect(screen.queryByRole('heading', { name: '无法连接本地服务' })).not.toBeInTheDocument()
  })

  it('auto-reads unread notice A and B exactly once in the same component instance', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({ notice_id: Number(url.match(/notices\/(\d+)/)?.[1]), is_read: true }), { status: 200 }))
      const id = Number(url.match(/notices\/(\d+)/)?.[1])
      return Promise.resolve(new Response(JSON.stringify({ ...detail, id, title: id === 1 ? '通知 A' : '通知 B', is_read: false }), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderDetail('1')
    expect(await screen.findByRole('heading', { name: '通知 A' })).toBeInTheDocument()
    await waitFor(() => expect(readCalls(fetchMock).filter(url => url.endsWith('/notices/1/read'))).toHaveLength(1))

    fireEvent.click(screen.getByRole('link', { name: '打开通知 B' }))
    expect(await screen.findByRole('heading', { name: '通知 B' })).toBeInTheDocument()
    await waitFor(() => {
      expect(readCalls(fetchMock).filter(url => url.endsWith('/notices/1/read'))).toHaveLength(1)
      expect(readCalls(fetchMock).filter(url => url.endsWith('/notices/2/read'))).toHaveLength(1)
    })
  })

  it('does not auto-read the same unread notice again after an ordinary rerender', async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({ notice_id: 42, is_read: true }), { status: 200 }))
      return Promise.resolve(new Response(JSON.stringify({ ...detail, is_read: false }), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderDetail()
    await waitFor(() => expect(readCalls(fetchMock)).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: '普通重渲染' }))
    expect(screen.getByTestId('render-count')).toHaveTextContent('1')
    expect(readCalls(fetchMock)).toHaveLength(1)
  })

  it('does not auto-read a notice that is already read', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(detail), { status: 200 })))
    vi.stubGlobal('fetch', fetchMock)

    renderDetail()
    expect(await screen.findByRole('heading', { name: '测试通知' })).toBeInTheDocument()
    expect(readCalls(fetchMock)).toHaveLength(0)
  })

  it('renders a favorite action with an accessible name and toggles via the existing mutation', async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({ notice_id: 42, field: 'is_favorite' }), { status: 200 }))
      return Promise.resolve(new Response(JSON.stringify(detail), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderDetail()
    const button = await screen.findByRole('button', { name: '收藏通知' })
    fireEvent.click(button)
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input, init]) => init?.method === 'POST' && String(input).endsWith('/notices/42/favorite'))).toBe(true)
    })
  })

  it('renders the original source link from the notice url', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(detail), { status: 200 }))))

    renderDetail()
    const links = await screen.findAllByRole('link', { name: '查看原通知' })
    expect(links.length).toBeGreaterThan(0)
    expect(links[0]).toHaveAttribute('href', 'https://example.test/notice')
  })

  it('keeps network errors separate from the dedicated 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderDetail()
    expect(await screen.findByRole('heading', { name: '无法连接本地服务' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新连接' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '返回通知列表' })).not.toBeInTheDocument()
  })

  it('renders the full deadline detail from real fields', async () => {
    const withDeadline = { ...detail, registration_deadline: '2026-09-10', deadline_status: 'normal', days_until_deadline: 11 }
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(withDeadline), { status: 200 }))))

    renderDetail()
    const values = await screen.findAllByText('2026-09-10 · 剩余 11 天')
    expect(values.length).toBeGreaterThan(0)
  })

  it('invalidates the dashboard cache after favoriting in detail', async () => {
    function DashboardProbe() {
      const { data } = useQuery({ queryKey: ['dashboard'], queryFn: ({ signal }) => getDashboard({ signal }) })
      return <span data-testid="dashboard-probe">{data ? 'loaded' : 'pending'}</span>
    }
    const controlled = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({ notice_id: 42, is_favorite: true }), { status: 200 }))
      if (url.includes('/dashboard')) return Promise.resolve(new Response(JSON.stringify({ unread: 0 }), { status: 200 }))
      return Promise.resolve(new Response(JSON.stringify(detail), { status: 200 }))
    })
    vi.stubGlobal('fetch', controlled)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/notices/42']}>
            <DashboardProbe />
            <Routes><Route path="/notices/:id" element={<NoticeDetailPage />} /></Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    )

    await screen.findByTestId('dashboard-probe')
    const dashboardGets = () => controlled.mock.calls.filter(([input, init]) => !init?.method && String(input).includes('/dashboard')).length
    expect(dashboardGets()).toBe(1)

    fireEvent.click(await screen.findByRole('button', { name: '收藏通知' }))
    await waitFor(() => expect(dashboardGets()).toBe(2))
  })

  it('auto-read invalidates the search cache so reopened results show fresh read state', async () => {
    function SearchProbe() {
      const { data } = useQuery({ queryKey: ['search', 'kw'], queryFn: ({ signal }) => searchNotices('kw', { signal }) })
      return <span data-testid="search-probe">{data ? 'loaded' : 'pending'}</span>
    }
    const unreadDetail = { ...detail, is_read: false }
    const controlled = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({ notice_id: 42, is_read: true }), { status: 200 }))
      if (url.includes('/api/search')) return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }), { status: 200 }))
      return Promise.resolve(new Response(JSON.stringify(unreadDetail), { status: 200 }))
    })
    vi.stubGlobal('fetch', controlled)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/notices/42']}>
            <SearchProbe />
            <Routes><Route path="/notices/:id" element={<NoticeDetailPage />} /></Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    )

    await screen.findByTestId('search-probe')
    const searchGets = () => controlled.mock.calls.filter(([input, init]) => !init?.method && String(input).includes('/api/search')).length
    await waitFor(() => {
      expect(controlled.mock.calls.some(([input, init]) => init?.method === 'POST' && String(input).endsWith('/notices/42/read'))).toBe(true)
    })

    // The read mutation invalidates ['search'], so the observed search query
    // refetches: exactly one initial GET plus one invalidation-driven GET.
    await waitFor(() => expect(searchGets()).toBe(2))
  })
})
