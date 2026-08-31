import { invoke, isTauri } from '@tauri-apps/api/core'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Button } from '../ui/Button'
import { ErrorState } from '../ui/Feedback'

type BackendStatus = {
  phase: 'idle' | 'starting' | 'ready' | 'failed' | 'stopping'
  ready: boolean
  owned: boolean
  pid: number | null
  error: string | null
}

const startingStatus: BackendStatus = {
  phase: 'starting',
  ready: false,
  owned: false,
  pid: null,
  error: null,
}

const failedStatus = (message: string): BackendStatus => ({
  phase: 'failed',
  ready: false,
  owned: false,
  pid: null,
  error: message,
})

export function DesktopBackendBoundary({ children }: { children: ReactNode }) {
  const desktop = isTauri()
  const [status, setStatus] = useState<BackendStatus>(startingStatus)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    if (!desktop) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const poll = async () => {
      try {
        const next = await invoke<BackendStatus>('backend_status')
        if (cancelled) return
        setStatus(next)
        if (!next.ready && next.phase !== 'failed') {
          timer = setTimeout(poll, 200)
        }
      } catch {
        if (!cancelled) {
          setStatus(failedStatus('无法读取本地通知服务状态。请重新启动应用。'))
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [desktop])

  const retry = useCallback(async () => {
    setRetrying(true)
    setStatus(startingStatus)
    try {
      setStatus(await invoke<BackendStatus>('retry_backend'))
    } catch {
      setStatus(failedStatus('无法重新启动本地通知服务。请重新启动应用。'))
    } finally {
      setRetrying(false)
    }
  }, [])

  if (!desktop || status.ready) return children

  if (status.phase === 'failed') {
    return (
      <main className="fixed inset-0 grid place-items-center bg-bg p-6">
        <div className="w-full max-w-lg">
          <ErrorState
            headingLevel={1}
            title="本地通知服务启动失败"
            message={status.error ?? '本地通知服务无法启动。'}
            action={<Button variant="primary" onClick={retry} disabled={retrying}>{retrying ? '正在重试…' : '重新启动服务'}</Button>}
          />
        </div>
      </main>
    )
  }

  return (
    <main className="fixed inset-0 grid place-items-center bg-bg p-6">
      <div className="text-center" role="status" aria-live="polite">
        <h1 className="text-page-title text-text-primary">吉大通知助手</h1>
        <p className="mt-2 text-sm text-text-secondary">正在启动本地通知服务…</p>
      </div>
    </main>
  )
}
