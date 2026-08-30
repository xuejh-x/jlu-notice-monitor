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
    expect(screen.getByLabelText('来源')).toHaveValue('cse')
    expect(screen.getByLabelText('阅读状态')).toHaveValue('unread')
    expect(await screen.findByText('第 2 / 5 页')).toBeInTheDocument()
    expect(requestUrls(fetchMock).some(url => url.includes('q=test') && url.includes('source=cse') && url.includes('read=false') && url.includes('page=2') && url.includes('page_size=50'))).toBe(true)
  })

  it('writes an explicit filter to the URL and resets page', async () => {
    renderNotices('/notices?page=3')
    await screen.findByText('第 3 / 5 页')

    fireEvent.change(screen.getByLabelText('分类'), { target: { value: 'research' } })

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('?category=research'))
    expect(screen.getByTestId('location')).not.toHaveTextContent('page=')
  })

  it('writes search input with replace semantics and debounces the request', async () => {
    renderNotices()
    await screen.findByText('找到 0 条通知')
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

    expect(screen.getByLabelText('分类')).toHaveValue('')
    expect(screen.getByLabelText('阅读状态')).toHaveValue('')
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

  it('shows a filter-empty state with a clear action', async () => {
    renderNotices('/notices?category=research')
    expect(await screen.findByRole('heading', { name: '没有找到相关通知' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '清除筛选' })).toBeInTheDocument()
  })

  it('shows a true-empty state when there are no notices and no filters', async () => {
    renderNotices('/notices')
    expect(await screen.findByRole('heading', { name: '暂无通知' })).toBeInTheDocument()
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
    await screen.findByText('找到 0 条通知')

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
    await screen.findByText('找到 0 条通知')
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
