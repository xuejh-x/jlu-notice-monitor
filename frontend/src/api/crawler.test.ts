import { afterEach, describe, expect, it, vi } from 'vitest'
import { runCrawler } from './crawler'

describe('runCrawler mutation contract', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('POSTs and resolves the backend started payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'started' }), { status: 202, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await runCrawler()

    expect(result).toEqual({ status: 'started' })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/crawler/run', expect.objectContaining({ method: 'POST' }))
  })
})
