import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../../stores/toast'
import { CrawlerButton } from './CrawlerButton'

describe('CrawlerButton', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('starts the real crawler action when the overview check is clicked', async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({ status: 'started' }), { status: 200 }))
      return Promise.resolve(new Response(JSON.stringify({ running: false, status: 'idle', current_started_at: null, last_run: null, last_duration: null, new_count: 0, updated_count: 0, source_results: [] }), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><ToastProvider><CrawlerButton compact /></ToastProvider></QueryClientProvider>)

    fireEvent.click(await screen.findByRole('button', { name: '检查新通知' }))

    await waitFor(() => expect(fetchMock.mock.calls.some(([input, init]) => init?.method === 'POST' && String(input).endsWith('/api/crawler/run'))).toBe(true))
    expect(await screen.findByText('已开始检查新通知')).toBeInTheDocument()
  })

  it('shows the backend-owned startup synchronization state without starting it from React', async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(new Response(JSON.stringify({ running: true, status: 'running', trigger_source: 'startup', current_started_at: '2026-09-02T08:00:00', last_run: null, last_duration: null, new_count: 0, updated_count: 0, source_results: [], startup_sync: { triggered: true, started_at: '2026-09-02T08:00:00', completed_at: null, outcome: 'started', skipped_reason: null } }), { status: 200 })))
    vi.stubGlobal('fetch', fetchMock)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><ToastProvider><CrawlerButton compact /></ToastProvider></QueryClientProvider>)
    expect(await screen.findByText('正在检查最新通知…')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('does not equate an idle crawler or running scheduler with checking', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ running: false, status: 'idle', current_started_at: null, last_run: null, last_duration: null, new_count: 0, updated_count: 0, source_results: [], scheduler: { enabled: true, running: true, interval_minutes: 15 } }), { status: 200 }))))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><ToastProvider><CrawlerButton compact /></ToastProvider></QueryClientProvider>)
    expect(await screen.findByText('检查')).toBeInTheDocument()
    expect(screen.queryByText(/检查中|正在检查/)).not.toBeInTheDocument()
  })

  it.each([
    ['success', '检查完成'],
    ['partial_failure', '部分失败'],
    ['failure', '检查失败'],
  ])('renders the backend terminal %s state', async (state, label) => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ running: false, status: state, current_started_at: null, last_run: '2026-09-02T08:00:03', last_duration: 3, new_count: 1, updated_count: 0, source_results: [] }), { status: 200 }))))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><ToastProvider><CrawlerButton compact /></ToastProvider></QueryClientProvider>)
    expect(await screen.findByText(label)).toBeInTheDocument()
  })

  it('invalidates notice queries once startup synchronization completes', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ running: true, status: 'running', trigger_source: 'startup', current_started_at: '2026-09-02T08:00:00', last_run: null, last_duration: null, new_count: 0, updated_count: 0, source_results: [], startup_sync: { triggered: true, started_at: '2026-09-02T08:00:00', completed_at: null, outcome: 'started', skipped_reason: null } }), { status: 200 }))))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    render(<QueryClientProvider client={client}><ToastProvider><CrawlerButton compact /></ToastProvider></QueryClientProvider>)
    await screen.findByText('正在检查最新通知…')
    client.setQueryData(['crawler'], {
      running: false, status: 'success', trigger_source: 'startup', current_started_at: null,
      last_run: '2026-09-02T08:00:03', last_duration: 3, new_count: 2, updated_count: 1,
      unchanged_count: 10, source_results: [],
      startup_sync: { triggered: true, started_at: '2026-09-02T08:00:00', completed_at: '2026-09-02T08:00:03', outcome: 'success', skipped_reason: null },
    })
    expect(await screen.findByText('检查完成：新增 2 条，更新 1 条')).toBeInTheDocument()
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['notices'] }))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
    expect(invalidate.mock.calls.filter(([options]) => options?.queryKey?.[0] === 'notices')).toHaveLength(1)
    expect(screen.queryByText(/正在检查/)).not.toBeInTheDocument()
  })
})
