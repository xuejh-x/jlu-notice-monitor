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
      return Promise.resolve(new Response(JSON.stringify({ running: false, current_started_at: null, last_run: null, last_duration: null, new_count: 0, updated_count: 0, source_results: [] }), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><ToastProvider><CrawlerButton compact /></ToastProvider></QueryClientProvider>)

    fireEvent.click(await screen.findByRole('button', { name: '检查新通知' }))

    await waitFor(() => expect(fetchMock.mock.calls.some(([input, init]) => init?.method === 'POST' && String(input).endsWith('/api/crawler/run'))).toBe(true))
    expect(await screen.findByText('已开始检查新通知')).toBeInTheDocument()
  })
})
