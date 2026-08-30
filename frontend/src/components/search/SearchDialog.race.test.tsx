import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Notice } from '../../types'
import { SearchDialog } from './SearchDialog'

// Deterministic concurrency tests: every fetch returns a manually-controlled
// deferred promise, so request completion order is fully scripted — no real
// network and no timing flakiness. The only real wait is the fixed 300ms
// debounce, which is deterministic.
type Deferred = { resolve: (response: Response) => void; reject: (error: unknown) => void }

function installDeferredFetch() {
  const pending = new Map<string, Deferred>()
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const keyword = decodeURIComponent(String(input).match(/keyword=([^&]+)/)?.[1] ?? '')
    return new Promise<Response>((resolve, reject) => { pending.set(keyword, { resolve, reject }) })
  }))
  return { pending }
}

function noticeFor(keyword: string): Notice {
  return {
    id: keyword.length + 100, title: `${keyword}结果通知`, url: `https://example.test/${keyword}`, publish_date: '2026-08-30', publisher: '计算机学院',
    category: 'other', importance_score: 50, registration_start: null, registration_deadline: null,
    event_start: null, event_end: null, deadline_status: 'unknown', days_until_deadline: null, status: 'new',
    first_seen_at: '2026-08-30T00:00:00Z', last_seen_at: '2026-08-30T00:00:00Z', updated_at: '2026-08-30T00:00:00Z',
    is_read: true, is_archived: false, is_favorite: false, sources: [{ code: 'ccst', name: '计算机学院' }],
  }
}

const ok = (items: Notice[], total = items.length) => new Response(JSON.stringify({ items, total, page: 1, page_size: 20, total_pages: total ? 1 : 0 }), { status: 200 })

const flushPromises = () => new Promise<void>(resolve => { setTimeout(resolve, 0) })

function renderDialog() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><SearchDialog /></MemoryRouter></QueryClientProvider>)
}

async function openDialog() {
  fireEvent.click(screen.getByRole('button', { name: /搜索通知、学院或关键词/ }))
  return screen.findByRole('textbox', { name: '搜索通知' })
}

async function type(input: HTMLElement, keyword: string) {
  fireEvent.change(input, { target: { value: keyword } })
}

describe('SearchDialog concurrency contract', () => {
  beforeEach(() => vi.unstubAllGlobals())
  afterEach(() => vi.unstubAllGlobals())

  it('stale success: an earlier request resolving last cannot overwrite the latest results', async () => {
    const { pending } = installDeferredFetch()
    renderDialog()
    const input = await openDialog()

    await type(input, '奖')
    await waitFor(() => expect(pending.has('奖')).toBe(true))
    await type(input, '竞赛')
    await waitFor(() => expect(pending.has('竞赛')).toBe(true))

    // B resolves first
    pending.get('竞赛')!.resolve(ok([noticeFor('竞赛')]))
    expect(await screen.findByRole('button', { name: /竞赛结果通知/ })).toBeInTheDocument()

    // A resolves last — UI must stay on B
    pending.get('奖')!.resolve(ok([noticeFor('奖')]))
    await act(async () => { await flushPromises() })
    expect(screen.getByRole('button', { name: /竞赛结果通知/ })).toBeInTheDocument()
    expect(screen.queryByText(/奖结果通知/)).not.toBeInTheDocument()
  })

  it('stale error: an earlier request failing last keeps results and shows no error', async () => {
    const { pending } = installDeferredFetch()
    renderDialog()
    const input = await openDialog()

    await type(input, '奖')
    await waitFor(() => expect(pending.has('奖')).toBe(true))
    await type(input, '竞赛')
    await waitFor(() => expect(pending.has('竞赛')).toBe(true))

    pending.get('竞赛')!.resolve(ok([noticeFor('竞赛')]))
    await screen.findByRole('button', { name: /竞赛结果通知/ })

    pending.get('奖')!.reject(new TypeError('Failed to fetch'))
    await act(async () => { await flushPromises() })
    expect(screen.queryByRole('heading', { name: '无法连接本地服务' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重新连接' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /竞赛结果通知/ })).toBeInTheDocument()
  })

  it('stale empty: an earlier request returning empty last cannot switch the UI to empty', async () => {
    const { pending } = installDeferredFetch()
    renderDialog()
    const input = await openDialog()

    await type(input, '奖')
    await waitFor(() => expect(pending.has('奖')).toBe(true))
    await type(input, '竞赛')
    await waitFor(() => expect(pending.has('竞赛')).toBe(true))

    pending.get('竞赛')!.resolve(ok([noticeFor('竞赛')]))
    await screen.findByRole('button', { name: /竞赛结果通知/ })

    pending.get('奖')!.resolve(ok([]))
    await act(async () => { await flushPromises() })
    expect(screen.queryByText(/没有匹配/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /竞赛结果通知/ })).toBeInTheDocument()
  })

  it('clear while pending: a late response cannot repopulate results after the query is cleared', async () => {
    const { pending } = installDeferredFetch()
    renderDialog()
    const input = await openDialog()

    await type(input, '奖')
    await waitFor(() => expect(pending.has('奖')).toBe(true))

    await type(input, '')
    expect(await screen.findByText('输入关键词开始搜索')).toBeInTheDocument()

    pending.get('奖')!.resolve(ok([noticeFor('奖')]))
    await act(async () => { await flushPromises() })
    expect(screen.getByText('输入关键词开始搜索')).toBeInTheDocument()
    expect(screen.queryByText(/奖结果通知/)).not.toBeInTheDocument()
  })

  it('rapid A→B→C: only the latest query owns results, loading, and errors', async () => {
    const { pending } = installDeferredFetch()
    renderDialog()
    const input = await openDialog()

    await type(input, '奖')
    await waitFor(() => expect(pending.has('奖')).toBe(true))
    await type(input, '竞赛')
    await waitFor(() => expect(pending.has('竞赛')).toBe(true))
    await type(input, '蓝桥')
    await waitFor(() => expect(pending.has('蓝桥')).toBe(true))

    // While C is pending, earlier completions must not clear loading or surface anything
    expect(screen.getByText('正在搜索……')).toBeInTheDocument()
    pending.get('奖')!.resolve(ok([noticeFor('奖')]))
    await act(async () => { await flushPromises() })
    expect(screen.getByText('正在搜索……')).toBeInTheDocument()
    expect(screen.queryByText(/奖结果通知/)).not.toBeInTheDocument()

    pending.get('竞赛')!.reject(new TypeError('Failed to fetch'))
    await act(async () => { await flushPromises() })
    expect(screen.getByText('正在搜索……')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '无法连接本地服务' })).not.toBeInTheDocument()

    // C completes — it alone controls the final UI
    pending.get('蓝桥')!.resolve(ok([noticeFor('蓝桥')]))
    expect(await screen.findByRole('button', { name: /蓝桥结果通知/ })).toBeInTheDocument()
    expect(screen.queryByText('正在搜索……')).not.toBeInTheDocument()
    expect(screen.queryByText(/奖结果通知/)).not.toBeInTheDocument()
    expect(screen.queryByText(/竞赛结果通知/)).not.toBeInTheDocument()
  })

  it('close while pending: no visible stale error, and reopen shows the current query state', async () => {
    const { pending } = installDeferredFetch()
    renderDialog()
    const input = await openDialog()

    await type(input, '奖')
    await waitFor(() => expect(pending.has('奖')).toBe(true))

    fireEvent.click(screen.getByRole('button', { name: '关闭搜索' }))
    await waitFor(() => expect(screen.queryByRole('textbox', { name: '搜索通知' })).not.toBeInTheDocument())

    // Fails while the dialog is closed — nothing user-visible may appear
    pending.get('奖')!.reject(new TypeError('Failed to fetch'))
    await act(async () => { await flushPromises() })
    expect(screen.queryByRole('heading', { name: '无法连接本地服务' })).not.toBeInTheDocument()

    // Reopen: consistent, retryable state for the current keyword (not stale pollution)
    fireEvent.click(screen.getByRole('button', { name: /搜索通知、学院或关键词/ }))
    expect(await screen.findByRole('heading', { name: '无法连接本地服务' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新连接' })).toBeInTheDocument()
  })
})
