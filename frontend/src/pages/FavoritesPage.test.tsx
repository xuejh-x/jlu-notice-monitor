import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../stores/toast'
import type { Notice } from '../types'
import { invalidateNoticeState } from '../utils/noticeCache'
import { FavoritesPage } from './FavoritesPage'

const base: Notice = {
  id: 1, title: '收藏通知A', url: 'https://example.test/1', publish_date: '2026-08-30', publisher: '计算机学院',
  category: 'other', importance_score: 50, registration_start: null, registration_deadline: null,
  event_start: null, event_end: null, deadline_status: 'unknown', days_until_deadline: null, status: 'new',
  first_seen_at: '2026-08-30T00:00:00Z', last_seen_at: '2026-08-30T00:00:00Z', updated_at: '2026-08-30T00:00:00Z',
  is_read: true, is_archived: false, is_favorite: true, sources: [{ code: 'cse', name: '网络安全学院' }],
}

describe('FavoritesPage membership contract', () => {
  beforeEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

  it('refetches the favorites list when notice state is invalidated (notices prefix covers filtered lists)', async () => {
    const page = { items: [base], total: 1, page: 1, page_size: 20, total_pages: 1 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <ToastProvider>
          <MemoryRouter><FavoritesPage /></MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('收藏通知A')).toBeInTheDocument()
    const gets = () => fetchMock.mock.calls.filter(([input, init]) => !init?.method && String(input).includes('/api/notices')).length
    expect(gets()).toBe(1)

    // Unfavorite elsewhere → invalidateNoticeState(['notices']) → the active
    // favorites query (['notices','favorites',page,pageSize]) must refetch.
    invalidateNoticeState(client, 1)
    await waitFor(() => expect(gets()).toBe(2))
  })
})
