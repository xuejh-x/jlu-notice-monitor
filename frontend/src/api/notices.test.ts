import { afterEach, describe, expect, it, vi } from 'vitest'
import { setNoticeFavorite, setNoticeRead } from './notices'

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
