const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
export const DEFAULT_REQUEST_TIMEOUT_MS = 15_000

export type ApiErrorKind = 'NETWORK_ERROR' | 'TIMEOUT' | 'ABORTED' | 'HTTP_ERROR' | 'NOT_FOUND'
export interface ApiRequestOptions { signal?: AbortSignal; timeoutMs?: number }
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number
  readonly endpoint: string
  constructor({ kind, message, endpoint, status }: { kind: ApiErrorKind; message: string; endpoint: string; status?: number }) {
    super(message); this.name = 'ApiError'; this.kind = kind; this.status = status; this.endpoint = endpoint
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit, options: ApiRequestOptions = {}): Promise<T> {
  const controller = new AbortController()
  const timeoutMs = options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS
  let timedOut = false
  const onExternalAbort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  else options.signal?.addEventListener('abort', onExternalAbort, { once: true })
  const timer = window.setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal, headers: { 'Content-Type': 'application/json', ...init?.headers } })
    if (response.ok) return response.json() as Promise<T>
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError({ kind: response.status === 404 ? 'NOT_FOUND' : 'HTTP_ERROR', message: body?.detail ?? `请求失败（${response.status}）`, endpoint: path, status: response.status })
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (timedOut) throw new ApiError({ kind: 'TIMEOUT', message: '请求超时，请稍后重试。', endpoint: path })
    if (options.signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw new ApiError({ kind: 'ABORTED', message: '请求已取消。', endpoint: path })
    throw new ApiError({ kind: 'NETWORK_ERROR', message: '无法连接后端服务，请确认后端已启动。', endpoint: path })
  } finally {
    window.clearTimeout(timer)
    options.signal?.removeEventListener('abort', onExternalAbort)
  }
}
