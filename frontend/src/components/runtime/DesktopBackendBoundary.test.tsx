import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DesktopBackendBoundary } from './DesktopBackendBoundary'

const tauri = vi.hoisted(() => ({
  invoke: vi.fn(),
  isTauri: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => tauri)

describe('DesktopBackendBoundary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not gate the normal browser application', () => {
    tauri.isTauri.mockReturnValue(false)
    render(<DesktopBackendBoundary><div>应用内容</div></DesktopBackendBoundary>)
    expect(screen.getByText('应用内容')).toBeInTheDocument()
    expect(tauri.invoke).not.toHaveBeenCalled()
  })

  it('waits for desktop backend readiness before rendering the application', async () => {
    tauri.isTauri.mockReturnValue(true)
    tauri.invoke
      .mockResolvedValueOnce({ phase: 'starting', ready: false, owned: true, pid: 42, error: null })
      .mockResolvedValueOnce({ phase: 'ready', ready: true, owned: true, pid: 42, error: null })

    render(<DesktopBackendBoundary><div>应用内容</div></DesktopBackendBoundary>)
    expect(screen.getByRole('status')).toHaveTextContent('正在启动本地通知服务')
    await waitFor(() => expect(screen.getByText('应用内容')).toBeInTheDocument())
  })

  it('shows a safe failure state and retries through the Tauri command', async () => {
    tauri.isTauri.mockReturnValue(true)
    tauri.invoke.mockImplementation((command: string) => {
      if (command === 'backend_status') {
        return Promise.resolve({ phase: 'failed', ready: false, owned: false, pid: null, error: '端口 8000 已被其他程序占用。' })
      }
      return Promise.resolve({ phase: 'ready', ready: true, owned: true, pid: 43, error: null })
    })

    render(<DesktopBackendBoundary><div>应用内容</div></DesktopBackendBoundary>)
    expect(await screen.findByRole('heading', { level: 1, name: '本地通知服务启动失败' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('端口 8000 已被其他程序占用')

    fireEvent.click(screen.getByRole('button', { name: '重新启动服务' }))
    await waitFor(() => expect(screen.getByText('应用内容')).toBeInTheDocument())
    expect(tauri.invoke).toHaveBeenCalledWith('retry_backend')
  })
})
