import { afterEach, describe, expect, it, vi } from 'vitest'
import { getNotices, setNoticeFavorite, setNoticeRead } from './notices'

// routes.py `_set_state` serializes the mutated field as a dynamic key.
const stateResponse = (noticeId: number, field: 'is_favorite' | 'is_read', value: boolean) =>
  new Response(JSON.stringify({ notice_id: noticeId, [field]: value }), { status: 200, headers: { 'Content-Type': 'application/json' } })

describe('notice mutation contract', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('POSTs favorite and resolves the backend state payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(stateResponse(7, 'is_favorite', true))
    vi.stubGlobal('fetch', fetchMock)

    const result = await setNoticeFavorite(7, true)

    expect(result).toEqual({ notice_id: 7, is_favorite: true })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/notices/7/favorite', expect.objectContaining({ method: 'POST' }))
  })

  it('POSTs unfavorite with the opposite endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(stateResponse(7, 'is_favorite', false))
    vi.stubGlobal('fetch', fetchMock)

    const result = await setNoticeFavorite(7, false)

    expect(result).toEqual({ notice_id: 7, is_favorite: false })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/notices/7/unfavorite', expect.objectContaining({ method: 'POST' }))
  })

  it('POSTs read and resolves the backend state payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(stateResponse(7, 'is_read', true))
    vi.stubGlobal('fetch', fetchMock)

    const result = await setNoticeRead(7, true)

    expect(result).toEqual({ notice_id: 7, is_read: true })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/notices/7/read', expect.objectContaining({ method: 'POST' }))
  })
})

describe('notice query contract', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('serializes every supported list filter and keeps explicit count semantics', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [], total: 2, total_count: 2, unread_count: 1, all_count: 12,
      page: 1, page_size: 10, total_pages: 1,
    }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await getNotices({
      category: 'research', source: 'ccst', min_score: 80, date_from: '2026-09-10',
      deadline_status: 'urgent', read: false, favorite: true, page: 1, page_size: 10,
    })

    const requested = new URL(String(fetchMock.mock.calls[0][0]))
    expect(Object.fromEntries(requested.searchParams)).toMatchObject({
      category: 'research', source: 'ccst', min_score: '80', date_from: '2026-09-10',
      deadline_status: 'urgent', read: 'false', favorite: 'true', page: '1', page_size: '10',
    })
    expect(result).toMatchObject({ total_count: 2, unread_count: 1, all_count: 12, total_pages: 1 })
  })
})
