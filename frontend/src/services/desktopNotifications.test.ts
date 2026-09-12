import { beforeEach, describe, expect, it, vi } from 'vitest'
import { acknowledgeNotificationDelivery, claimNotificationDelivery } from '../api/notifications'
import { checkDesktopNotificationPermission, deliverNextDesktopNotification, openWindowsNotificationSettings, requestDesktopNotificationPermission, sendDesktopNotificationTest, sendWindowsNotification, validNotificationRoute } from './desktopNotifications'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { isPermissionGranted, requestPermission } from '@tauri-apps/plugin-notification'
import { openUrl } from '@tauri-apps/plugin-opener'

vi.mock('@tauri-apps/api/core', () => ({ isTauri: vi.fn(() => true), invoke: vi.fn() }))
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn() }))
vi.mock('@tauri-apps/api/window', () => ({ getCurrentWindow: vi.fn() }))
vi.mock('@tauri-apps/plugin-notification', () => ({
  isPermissionGranted: vi.fn(() => Promise.resolve(true)), requestPermission: vi.fn(),
}))
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: vi.fn() }))
vi.mock('../api/notifications', () => ({ claimNotificationDelivery: vi.fn(), acknowledgeNotificationDelivery: vi.fn() }))

const event = { id: 9, type: 'NEW_NOTICE' as const, notice_id: 42, source_id: 1, severity: 'info' as const, title: '新通知', body: '简洁正文', route: '/notices/42', local_date: null, read_at: null, created_at: '2026-09-03T00:00:00' }

describe('desktop notification bridge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(isTauri).mockReturnValue(true)
    vi.mocked(isPermissionGranted).mockResolvedValue(true)
    vi.mocked(invoke).mockResolvedValue(undefined)
    vi.mocked(openUrl).mockResolvedValue(undefined)
  })

  it('reports and requests Windows notification permission', async () => {
    expect(await checkDesktopNotificationPermission()).toBe(true)
    expect(await requestDesktopNotificationPermission()).toBe(true)
    expect(requestPermission).not.toHaveBeenCalled()

    vi.mocked(isPermissionGranted).mockResolvedValue(false)
    vi.mocked(requestPermission).mockResolvedValue('denied')
    expect(await requestDesktopNotificationPermission()).toBe(false)
  })

  it('opens the scoped Windows notification settings page', async () => {
    await openWindowsNotificationSettings()
    expect(openUrl).toHaveBeenCalledWith('ms-settings:notifications')
  })

  it('sends a native test notification through the existing Windows command', async () => {
    await sendDesktopNotificationTest()
    expect(invoke).toHaveBeenCalledWith('show_windows_notification', {
      title: '桌面提醒已开启',
      body: 'JLU Notice Monitor 将在这里发送新通知提醒。',
      route: '/notices',
    })
  })

  it('only accepts allow-listed internal routes from native activation', async () => {
    expect(validNotificationRoute('/notices/42')).toBe(true)
    expect(validNotificationRoute('https://example.test')).toBe(false)
    await expect(sendWindowsNotification('x', 'y', '/notices/nope')).rejects.toThrow('not allowed')
  })

  it('sends a claimed event and acknowledges native acceptance once', async () => {
    vi.mocked(claimNotificationDelivery).mockResolvedValue({ delivery: { delivery_id: 3, claim_token: 'a'.repeat(32), event } })
    vi.mocked(acknowledgeNotificationDelivery).mockResolvedValue({ delivery_id: 3, status: 'DELIVERED', attempt_count: 1 })
    expect(await deliverNextDesktopNotification()).toBe(true)
    expect(invoke).toHaveBeenCalledWith('show_windows_notification', { title: '新通知', body: '简洁正文', route: '/notices/42' })
    expect(acknowledgeNotificationDelivery).toHaveBeenCalledWith(3, 'a'.repeat(32), 'DELIVERED')
  })

  it('persists a definite native failure for bounded retry', async () => {
    vi.mocked(claimNotificationDelivery).mockResolvedValue({ delivery: { delivery_id: 3, claim_token: 'b'.repeat(32), event } })
    vi.mocked(invoke).mockRejectedValue(new Error('fixture native rejection'))
    vi.mocked(acknowledgeNotificationDelivery).mockResolvedValue({ delivery_id: 3, status: 'FAILED', attempt_count: 1 })
    expect(await deliverNextDesktopNotification()).toBe(false)
    expect(acknowledgeNotificationDelivery).toHaveBeenCalledWith(3, 'b'.repeat(32), 'FAILED', 'fixture native rejection')
  })

  it('does not mark a Windows-accepted toast failed when its acknowledgement is lost', async () => {
    vi.mocked(claimNotificationDelivery).mockResolvedValue({ delivery: { delivery_id: 3, claim_token: 'c'.repeat(32), event } })
    vi.mocked(acknowledgeNotificationDelivery).mockRejectedValue(new Error('fixture acknowledgement loss'))
    expect(await deliverNextDesktopNotification()).toBe(false)
    expect(invoke).toHaveBeenCalledOnce()
    expect(acknowledgeNotificationDelivery).toHaveBeenCalledOnce()
    expect(acknowledgeNotificationDelivery).toHaveBeenCalledWith(3, 'c'.repeat(32), 'DELIVERED')
  })
})
