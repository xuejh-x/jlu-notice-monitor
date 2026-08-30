import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiRequest } from './client'

const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('apiRequest', () => {
  it('returns parsed data for a successful request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest<{ ok: boolean }>('/api/health')).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/health', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('classifies a 404 response as NOT_FOUND', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: '通知不存在' }, 404)))

    await expect(apiRequest('/api/notices/404')).rejects.toMatchObject({ kind: 'NOT_FOUND', status: 404, endpoint: '/api/notices/404' })
  })

  it('classifies other HTTP failures as HTTP_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: '服务异常' }, 500)))

    await expect(apiRequest('/api/dashboard')).rejects.toMatchObject({ kind: 'HTTP_ERROR', status: 500, endpoint: '/api/dashboard' })
  })

  it('classifies a rejected fetch as NETWORK_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(apiRequest('/api/dashboard')).rejects.toMatchObject({ kind: 'NETWORK_ERROR' })
  })

  it('classifies a timed-out request as TIMEOUT', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_input: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))

    const request = expect(apiRequest('/api/slow', undefined, { timeoutMs: 10 })).rejects.toMatchObject({ kind: 'TIMEOUT' })
    await vi.advanceTimersByTimeAsync(10)
    await request
  })

  it('classifies an external cancellation as ABORTED', async () => {
    vi.stubGlobal('fetch', vi.fn((_input: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))
    const controller = new AbortController()
    const request = apiRequest('/api/notices', undefined, { signal: controller.signal })

    controller.abort()
    await expect(request).rejects.toMatchObject({ kind: 'ABORTED' })
  })

  it('cleans up its timer and external abort listener after completion', async () => {
    const controller = new AbortController()
    const removeListener = vi.spyOn(controller.signal, 'removeEventListener')
    const clearTimer = vi.spyOn(window, 'clearTimeout')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ ok: true })))

    await apiRequest('/api/health', undefined, { signal: controller.signal })

    expect(removeListener).toHaveBeenCalledWith('abort', expect.any(Function))
    expect(clearTimer).toHaveBeenCalled()
  })
})
