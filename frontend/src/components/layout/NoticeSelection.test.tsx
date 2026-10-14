import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NoticeDetail } from '../../types'
import { ThemeProvider } from '../../stores/theme'
import { AppShell } from './AppShell'

const makeNotice = (id: number): NoticeDetail => ({
  id, title: `通知 ${id}`, url: `https://example.test/${id}`, publish_date: '2026-09-01', publisher: '来源',
  category: 'other', importance_score: 20, registration_start: null, registration_deadline: null,
  event_start: null, event_end: null, deadline_status: 'unknown', days_until_deadline: null, status: 'new',
  first_seen_at: '2026-09-01', last_seen_at: '2026-09-01', updated_at: '2026-09-01',
  is_read: true, is_archived: false, is_favorite: false, sources: [{ code: 'ccst', name: '计算机学院' }],
  content: `正文 ${id}`, target_students: null, registration_method: null, competition_level: null, attachments: [], updates: [],
})
const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })
const pageOf = (items: NoticeDetail[], page = 1) => ({ items, total: 60, total_count: 60, unread_count: 3, all_count: 100, page, page_size: 20, total_pages: 3 })

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}{location.search}</output>
}
function renderWorkspace(entry = '/notices') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } })
  render(<QueryClientProvider client={client}><ThemeProvider><MemoryRouter initialEntries={[entry]}>
    <LocationProbe />
    <Routes><Route element={<AppShell />}><Route path="notices" element={<div />} /><Route path="notices/:id" element={<div />} /><Route path="settings" element={<div>设置内容</div>} /></Route></Routes>
  </MemoryRouter></ThemeProvider></QueryClientProvider>)
  return client
}
const list = () => screen.getByRole('region', { name: '通知工作区' })
const reader = () => screen.getByRole('complementary', { name: '通知详情工作区' })
async function chooseSearch(id: number) {
  const input = screen.getByRole('combobox', { name: '搜索通知' })
  fireEvent.focus(input)
  fireEvent.change(input, { target: { value: '通知' } })
  fireEvent.click(await screen.findByRole('option', { name: new RegExp(`通知 ${id}`) }))
}
async function expectSelection(id: number) {
  await within(reader()).findByRole('heading', { level: 1, name: `通知 ${id}` })
  await waitFor(() => expect(within(list()).getByRole('link', { name: `打开通知 ${id}` })).toHaveAttribute('aria-current', 'page'))
  expect(list().querySelectorAll('[aria-current="page"]')).toHaveLength(1)
}

describe('notice workspace selection', () => {
  let items: NoticeDetail[]
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>
  beforeEach(() => {
    localStorage.clear()
    items = [makeNotice(1), makeNotice(2)]
    fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input))
      if (url.pathname === '/api/notices') return Promise.resolve(ok(pageOf(items, Number(url.searchParams.get('page') ?? 1))))
      if (url.pathname === '/api/search') return Promise.resolve(ok(pageOf([makeNotice(1), makeNotice(7), makeNotice(8)])))
      const detail = url.pathname.match(/^\/api\/notices\/(\d+)$/)
      if (detail) return Promise.resolve(ok(makeNotice(Number(detail[1]))))
      if (url.pathname.endsWith('/read')) return Promise.resolve(ok({ notice_id: 7, is_read: true }))
      if (url.pathname === '/api/dashboard') return Promise.resolve(ok({ total_count: 100, unread: 3, recent_notices: [], source_status: [] }))
      if (url.pathname === '/api/notifications') return Promise.resolve(ok({ unread: 0, items: [] }))
      return Promise.resolve(ok({ running: false, source_results: [] }))
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('uses the route for ordinary list selection without duplicating the row', async () => {
    renderWorkspace('/notices?source=ccst&page=2')
    fireEvent.click(await screen.findByRole('link', { name: '打开通知 1' }))
    await expectSelection(1)
    expect(screen.getByTestId('location')).toHaveTextContent('/notices/1?source=ccst&page=2')
    expect(screen.queryByRole('region', { name: '当前打开的通知' })).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([input]) => new URL(String(input)).pathname === '/api/notices/1')).toHaveLength(1)
  })

  it('highlights an existing search target and clears the old selection', async () => {
    renderWorkspace('/notices/2')
    await expectSelection(2)
    await chooseSearch(1)
    await expectSelection(1)
    expect(within(list()).getByRole('link', { name: '打开通知 2' })).not.toHaveAttribute('aria-current')
    expect(screen.queryByRole('region', { name: '当前打开的通知' })).not.toBeInTheDocument()
  })

  it.each([
    '?page=3',
    '?q=原关键词&category=research&source=cse&date_from=2026-10-01&read=0&favorite=1&min_score=80&deadline_status=urgent&page=2',
  ])('temporarily shows a search target outside the current page/filters while preserving %s', async search => {
    renderWorkspace(`/notices${search}`)
    await screen.findByRole('link', { name: '打开通知 1' })
    await chooseSearch(7)
    await expectSelection(7)
    expect(screen.getByTestId('location')).toHaveTextContent(`/notices/7${search}`)
    expect(within(screen.getByRole('region', { name: '当前打开的通知' })).getByRole('link', { name: '打开通知 7' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('当前结果 60 条 · 未读 3 条')).toBeInTheDocument()
    expect(screen.getByText(`第 ${search.includes('page=3') ? 3 : 2} / 3 页`)).toBeInTheDocument()
  })

  it('ignores an earlier detail response arriving after the last search selection', async () => {
    let resolveFirst!: (response: Response) => void
    let firstSignal: AbortSignal | undefined
    const normal = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (new URL(String(input)).pathname === '/api/notices/7') {
        firstSignal = init?.signal as AbortSignal
        return new Promise<Response>(resolve => { resolveFirst = resolve })
      }
      return normal(input)
    })
    renderWorkspace()
    await chooseSearch(7)
    await waitFor(() => expect(resolveFirst).toBeDefined())
    await chooseSearch(8)
    await expectSelection(8)
    expect(firstSignal?.aborted).toBe(true)
    await act(async () => resolveFirst(ok(makeNotice(7))))
    await expectSelection(8)
    expect(within(list()).queryByRole('link', { name: '打开通知 7' })).not.toBeInTheDocument()
    expect(within(reader()).queryByText('正文 7')).not.toBeInTheDocument()
  })

  it('clearing or closing search preserves selection; closing detail removes the temporary row', async () => {
    renderWorkspace('/notices?source=cse&page=2')
    await chooseSearch(7)
    await expectSelection(7)
    fireEvent.click(screen.getByRole('button', { name: '清空搜索' }))
    await expectSelection(7)
    fireEvent.click(within(reader()).getAllByRole('link', { name: '返回通知列表' })[0])
    await waitFor(() => expect(screen.queryByRole('region', { name: '当前打开的通知' })).not.toBeInTheDocument())
    expect(list().querySelector('[aria-current="page"]')).toBeNull()
    expect(screen.getByTestId('location')).toHaveTextContent('/notices?source=cse&page=2')
  })

  it('retains the temporary row after auto-read, refetch, and a change of page', async () => {
    renderWorkspace('/notices?read=0')
    const normal = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input: RequestInfo | URL) => new URL(String(input)).pathname === '/api/notices/7'
      ? Promise.resolve(ok({ ...makeNotice(7), is_read: false })) : normal(input))
    await chooseSearch(7)
    await expectSelection(7)
    await waitFor(() => expect(within(screen.getByRole('region', { name: '当前打开的通知' })).getByText('已读')).toBeInTheDocument())
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/api/notices/7/read'))).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /下一页/ }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('page=2'))
    await expectSelection(7)
  })

  it('deduplicates a temporary row when a new page contains it, and restores it when the row disappears', async () => {
    const client = renderWorkspace('/notices/7')
    await expectSelection(7)
    items = [makeNotice(7), makeNotice(2)]
    await act(async () => { await client.invalidateQueries({ queryKey: ['notices'] }) })
    await waitFor(() => expect(screen.queryByRole('region', { name: '当前打开的通知' })).not.toBeInTheDocument())
    await expectSelection(7)
    items = []
    await act(async () => { await client.invalidateQueries({ queryKey: ['notices'] }) })
    await expectSelection(7)
    await screen.findByRole('region', { name: '当前打开的通知' })
  })

  it('keeps manual unread and read-all in sync with the selected temporary row', async () => {
    let read = true
    const normal = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const path = new URL(String(input)).pathname
      if (path === '/api/notices/7') return Promise.resolve(ok({ ...makeNotice(7), is_read: read }))
      if (path === '/api/notices/7/unread') { read = false; return Promise.resolve(ok({ notice_id: 7, is_read: false })) }
      if (path === '/api/notices/read-all') { read = true; return Promise.resolve(ok({ updated: 3 })) }
      return normal(input)
    })
    renderWorkspace('/notices/7?read=0')
    await expectSelection(7)
    fireEvent.click(within(reader()).getByRole('button', { name: '标记为未读' }))
    await waitFor(() => expect(within(screen.getByRole('region', { name: '当前打开的通知' })).getByText('未读')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '全部已读' }))
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '确定' }))
    await waitFor(() => expect(within(screen.getByRole('region', { name: '当前打开的通知' })).getByText('已读')).toBeInTheDocument())
    await expectSelection(7)
    expect(within(reader()).getByRole('button', { name: '标记为未读' })).toBeInTheDocument()
  })

  it('still shows the selected notice when loading the filtered page fails', async () => {
    const normal = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input: RequestInfo | URL) => new URL(String(input)).pathname === '/api/notices'
      ? Promise.resolve(new Response('{}', { status: 500 })) : normal(input))
    renderWorkspace('/notices/7?source=cse')
    await expectSelection(7)
    expect(await within(list()).findByRole('heading', { name: '暂时无法完成请求' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '当前打开的通知' })).toBeInTheDocument()
  })

  it('restores selection from a fresh detail URL without search history or loaded list data', async () => {
    renderWorkspace('/notices/8?source=cse&page=3')
    await expectSelection(8)
    expect(screen.getByRole('region', { name: '当前打开的通知' })).toBeInTheDocument()
  })

  it('does not apply settings query parameters to a search destination', async () => {
    renderWorkspace('/settings?source=cse&page=3')
    await chooseSearch(7)
    await expectSelection(7)
    expect(screen.getByTestId('location').textContent).toBe('/notices/7')
  })

  it('does not render a stale selected row when the detail is missing', async () => {
    const client = renderWorkspace('/notices/7')
    await expectSelection(7)
    await act(async () => {
      const normal = fetchMock.getMockImplementation()!
      fetchMock.mockImplementation((input: RequestInfo | URL) => String(input).endsWith('/api/notices/7')
        ? Promise.resolve(new Response('{}', { status: 404 })) : normal(input))
      await client.invalidateQueries({ queryKey: ['notice', 7] })
    })
    expect(await within(reader()).findByRole('heading', { name: '通知不存在' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '当前打开的通知' })).not.toBeInTheDocument()
  })
})
