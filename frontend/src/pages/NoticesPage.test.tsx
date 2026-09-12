import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { parseNoticesSearchParams, serializeNoticesSearchParams } from '../utils/noticeSearchParams'
import { NoticesPage } from './NoticesPage'

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.search}</output>
}

function renderNotices(initialEntry = '/notices') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <LocationProbe/>
        <Routes><Route path="/notices" element={<NoticesPage/>}/></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const requestUrls = (fetchMock: ReturnType<typeof vi.fn>) => fetchMock.mock.calls.map(([input]) => String(input))

describe('NoticesPage URL state', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    localStorage.clear()
    fetchMock = vi.fn((input: RequestInfo | URL) => {
      const page = Number(new URL(String(input)).searchParams.get('page') ?? 1)
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0, page, page_size: 20, total_pages: 5 }), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('restores search, page, page size and API parameters from the initial URL', async () => {
    renderNotices('/notices?q=test&source=cse&read=0&page=2&page_size=50')

    expect(screen.getByLabelText('搜索通知')).toHaveValue('test')
    expect(screen.getByRole('tab', { name: '未读' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('button', { name: '筛选 1' }))
    expect(within(await screen.findByRole('dialog')).getByLabelText('来源')).toHaveValue('cse')
    expect(await screen.findByText('第 2 / 5 页')).toBeInTheDocument()
    expect(requestUrls(fetchMock).some(url => url.includes('q=test') && url.includes('source=cse') && url.includes('read=false') && url.includes('page=2') && url.includes('page_size=50'))).toBe(true)
  })

  it('writes an explicit filter to the URL and resets page', async () => {
    renderNotices('/notices?page=3')
    await screen.findByText('第 3 / 5 页')

    fireEvent.click(screen.getByRole('button', { name: '筛选' }))
    fireEvent.change(within(await screen.findByRole('dialog')).getByLabelText('分类'), { target: { value: 'research' } })
    fireEvent.click(screen.getByRole('button', { name: /应用/ }))

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('?category=research'))
    expect(screen.getByTestId('location')).not.toHaveTextContent('page=')
  })

  it('writes search input with replace semantics and debounces the request', async () => {
    renderNotices()
    await screen.findByText('当前结果 0 条 · 未读 0 条')
    fetchMock.mockClear()

    fireEvent.change(screen.getByLabelText('搜索通知'), { target: { value: '奖学金' } })

    expect(screen.getByTestId('location')).toHaveTextContent(`?q=${encodeURIComponent('奖学金')}`)
    expect(requestUrls(fetchMock).some(url => url.includes(encodeURIComponent('奖学金')))).toBe(false)
    await waitFor(() => expect(requestUrls(fetchMock).some(url => url.includes(`q=${encodeURIComponent('奖学金')}`))).toBe(true), { timeout: 1000 })
  })

  it('writes pagination to the URL without changing active filters', async () => {
    renderNotices('/notices?source=ccst&page=2')
    await screen.findByText('第 2 / 5 页')

    fireEvent.click(screen.getByRole('button', { name: /下一页/ }))

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('?source=ccst&page=3'))
  })

  it('falls back safely for invalid parameters', async () => {
    renderNotices('/notices?page=abc&page_size=999&category=invalid&read=maybe')

    fireEvent.click(screen.getByRole('button', { name: '筛选' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('分类')).toHaveValue('')
    expect(screen.getByRole('tab', { name: '全部', hidden: true })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText('第 1 / 5 页')).toBeInTheDocument()
    expect(requestUrls(fetchMock).some(url => url.includes('page=1') && url.includes('page_size=20') && !url.includes('category=invalid'))).toBe(true)
  })

  it('round-trips every supported URL schema field', () => {
    const params = new URLSearchParams('q=奖学金&category=research&source=csw&min_score=80&date_from=2026-08-30&deadline_status=urgent&read=0&favorite=1&page=2&page_size=50')

    const state = parseNoticesSearchParams(params, 20)

    expect(state).toMatchObject({ q: '奖学金', category: 'research', source: 'csw', minScore: '80', dateFrom: '2026-08-30', deadlineStatus: 'urgent', read: 'unread', favorite: 'favorite', page: 2, pageSize: 50 })
    expect(serializeNoticesSearchParams(state, 20).toString()).toBe(params.toString())
  })
})

describe('NoticesPage states and filters', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    localStorage.clear()
    fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 1 }), { status: 200 })))
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('shows a distinct search-empty state for a non-matching query', async () => {
    renderNotices('/notices?q=不存在关键词')
    expect(await screen.findByRole('heading', { name: '没有匹配 “不存在关键词” 的通知' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '清空搜索' })).toBeInTheDocument()
  })

  it('distinguishes the global total from filtered and unread result counts', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      const filtered = url.includes('read=false') ? 3 : 7
      const body = { items: [], total: filtered, total_count: filtered, unread_count: 3, all_count: 7, page: 1, page_size: 20, total_pages: 1 }
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    })
    renderNotices('/notices')
    expect(await screen.findByText('全库 7 条')).toBeInTheDocument()
    expect(screen.getByText('当前结果 7 条 · 未读 3 条')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '未读' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('read=0'))
    expect(await screen.findByText('当前结果 3 条 · 未读 3 条')).toBeInTheDocument()
    expect(screen.getByText('全库 7 条')).toBeInTheDocument()
  })

  it('shows a filter-empty state with a clear action', async () => {
    renderNotices('/notices?category=research')
    expect(await screen.findByRole('heading', { name: '没有找到相关通知' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '清除筛选' })).toBeInTheDocument()
  })

  it('shows a true-empty state when there are no notices and no filters', async () => {
    renderNotices('/notices')
    expect(await screen.findByRole('heading', { name: '暂无通知' })).toBeInTheDocument()
  })

  it('keeps sort and view as static indicators while filter remains functional', async () => {
    renderNotices('/notices')
    await screen.findByRole('heading', { name: '暂无通知' })
    expect(screen.getByTitle('当前按截止时间升序')).toBeInTheDocument()
    expect(screen.getByTitle('当前为列表视图')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '按截止时间排序' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '列表视图' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '筛选' })).toBeEnabled()
  })

  it('clears filters from the URL via the empty-state action', async () => {
    renderNotices('/notices?category=research&source=cse')
    await screen.findByRole('heading', { name: '没有找到相关通知' })
    fireEvent.click(screen.getByRole('button', { name: '清除筛选' }))
    await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('category='))
    expect(screen.getByTestId('location')).not.toHaveTextContent('source=')
  })

  it('opens the mobile filter sheet, applies draft changes to the URL, then resets', async () => {
    renderNotices('/notices')
    await screen.findByText('当前结果 0 条 · 未读 0 条')

    fireEvent.click(screen.getByRole('button', { name: '筛选' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('分类'), { target: { value: 'research' } })
    fireEvent.click(within(dialog).getByRole('button', { name: /应用/ }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('category=research'))

    fireEvent.click(screen.getByRole('button', { name: '筛选 1' }))
    const dialog2 = await screen.findByRole('dialog')
    fireEvent.click(within(dialog2).getByRole('button', { name: '重置' }))
    fireEvent.click(within(dialog2).getByRole('button', { name: /应用/ }))
    await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('category='))
  })

  it('exposes filter sheet state and restores focus when it closes', async () => {
    renderNotices('/notices')
    await screen.findByText('当前结果 0 条 · 未读 0 条')
    const trigger = screen.getByRole('button', { name: '筛选' })

    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')

    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: '关闭筛选' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveFocus()
  })
})

const filterNotices = Array.from({ length: 12 }, (_, index) => ({
  id: index + 1,
  title: `筛选测试通知 ${index + 1}`,
  url: `https://example.test/${index + 1}`,
  publish_date: `2026-09-${String(12 - index).padStart(2, '0')}`,
  publisher: index === 11 ? '计算机学院' : '网络安全学院',
  category: index < 6 ? 'research' : 'academic',
  importance_score: 95 - index,
  registration_start: null,
  registration_deadline: null,
  event_start: null,
  event_end: null,
  deadline_status: 'unknown',
  days_until_deadline: null,
  status: 'active',
  first_seen_at: '2026-09-12T00:00:00',
  last_seen_at: '2026-09-12T00:00:00',
  updated_at: '2026-09-12T00:00:00',
  is_read: index >= 4,
  is_archived: false,
  is_favorite: false,
  sources: [{ code: index === 11 ? 'ccst' : 'cse', name: index === 11 ? '计算机学院' : '网络安全学院' }],
}))

describe('NoticesPage server-backed filtering', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    localStorage.clear()
    fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input))
      let items = [...filterNotices]
      const dateFrom = url.searchParams.get('date_from')
      const source = url.searchParams.get('source')
      const read = url.searchParams.get('read')
      if (dateFrom) items = items.filter(notice => notice.publish_date >= dateFrom)
      if (source) items = items.filter(notice => notice.sources.some(item => item.code === source))
      if (read !== null) items = items.filter(notice => notice.is_read === (read === 'true'))
      const totalCount = items.length
      const page = Number(url.searchParams.get('page') ?? 1)
      const pageSize = Number(url.searchParams.get('page_size') ?? 20)
      const pageItems = items.slice((page - 1) * pageSize, page * pageSize)
      return Promise.resolve(new Response(JSON.stringify({
        items: pageItems,
        total: totalCount,
        total_count: totalCount,
        unread_count: items.filter(notice => !notice.is_read).length,
        all_count: filterNotices.length,
        page,
        page_size: pageSize,
        total_pages: totalCount ? Math.ceil(totalCount / pageSize) : 0,
      }), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('date filter changes the visible list and closes the dialog after Apply', async () => {
    renderNotices()
    expect(await screen.findByText('当前结果 12 条 · 未读 4 条')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '筛选' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('起始日期'), { target: { value: '2026-09-10' } })
    fireEvent.click(within(dialog).getByRole('button', { name: '应用 (1)' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('当前结果 3 条 · 未读 3 条')).toBeInTheDocument()
    expect(screen.getByText('筛选测试通知 1')).toBeInTheDocument()
    expect(screen.queryByText('筛选测试通知 4')).not.toBeInTheDocument()
    expect(requestUrls(fetchMock).some(url => url.includes('date_from=2026-09-10'))).toBe(true)
  })

  it('source filter changes the visible list', async () => {
    renderNotices()
    await screen.findByText('当前结果 12 条 · 未读 4 条')
    fireEvent.click(screen.getByRole('button', { name: '筛选' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('来源'), { target: { value: 'ccst' } })
    fireEvent.click(within(dialog).getByRole('button', { name: '应用 (1)' }))

    expect(await screen.findByText('当前结果 1 条 · 未读 0 条')).toBeInTheDocument()
    expect(screen.getByText('筛选测试通知 12')).toBeInTheDocument()
    expect(screen.queryByText('筛选测试通知 1')).not.toBeInTheDocument()
    expect(requestUrls(fetchMock).some(url => url.includes('source=ccst'))).toBe(true)
  })

  it('read-state filter changes the visible list', async () => {
    renderNotices()
    await screen.findByText('当前结果 12 条 · 未读 4 条')
    fireEvent.click(screen.getByRole('button', { name: '筛选' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('阅读状态'), { target: { value: 'unread' } })
    fireEvent.click(within(dialog).getByRole('button', { name: '应用 (1)' }))

    expect(await screen.findByText('当前结果 4 条 · 未读 4 条')).toBeInTheDocument()
    expect(screen.getByText('筛选测试通知 4')).toBeInTheDocument()
    expect(screen.queryByText('筛选测试通知 5')).not.toBeInTheDocument()
    expect(requestUrls(fetchMock).some(url => url.includes('read=false'))).toBe(true)
  })

  it('builds pagination from the filtered total_count', async () => {
    renderNotices('/notices?source=cse&page_size=10')

    expect(await screen.findByText('1–10 / 11 条')).toBeInTheDocument()
    expect(screen.getByText('第 1 / 2 页')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    expect(await screen.findByText('11–11 / 11 条')).toBeInTheDocument()
    expect(screen.getByText('筛选测试通知 11')).toBeInTheDocument()
    expect(requestUrls(fetchMock).some(url => url.includes('source=cse') && url.includes('page=2') && url.includes('page_size=10'))).toBe(true)
  })

  it('clearing the filter restores the complete list', async () => {
    renderNotices('/notices?source=ccst')
    expect(await screen.findByText('当前结果 1 条 · 未读 0 条')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '筛选 1' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: '重置' }))
    fireEvent.click(within(dialog).getByRole('button', { name: '应用' }))

    expect(await screen.findByText('当前结果 12 条 · 未读 4 条')).toBeInTheDocument()
    expect(screen.getByText('筛选测试通知 1')).toBeInTheDocument()
    expect(screen.getByText('筛选测试通知 12')).toBeInTheDocument()
    expect(screen.getByTestId('location')).not.toHaveTextContent('source=')
  })
})
