import { invoke, isTauri } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'
import {
  isPermissionGranted,
  requestPermission,
} from '@tauri-apps/plugin-notification'
import { acknowledgeNotificationDelivery, claimNotificationDelivery } from '../api/notifications'

const INTERNAL_ROUTE = /^\/(?:notices\/[1-9]\d*|notices|deadlines|sources)$/

export function validNotificationRoute(value: unknown): value is string {
  return typeof value === 'string' && INTERNAL_ROUTE.test(value)
}

export async function requestDesktopNotificationPermission(): Promise<boolean> {
  if (!isTauri()) return false
  if (await isPermissionGranted()) return true
  return (await requestPermission()) === 'granted'
}

export async function sendWindowsNotification(title: string, body: string, route: string): Promise<void> {
  if (!validNotificationRoute(route)) throw new Error('Notification route is not allowed')
  await invoke('show_windows_notification', { title, body, route })
}

export async function deliverNextDesktopNotification(): Promise<boolean> {
  if (!isTauri() || !(await isPermissionGranted())) return false
  const { delivery } = await claimNotificationDelivery()
  if (!delivery) return false
  try {
    await sendWindowsNotification(
      delivery.event.title,
      delivery.event.body,
      validNotificationRoute(delivery.event.route) ? delivery.event.route : '/notices',
    )
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Native notification request failed'
    try {
      await acknowledgeNotificationDelivery(delivery.delivery_id, delivery.claim_token, 'FAILED', message.slice(0, 500))
    } catch {
      // A lost acknowledgement intentionally leaves SENDING persisted. The backend
      // converts it to UNCERTAIN instead of retrying a possibly displayed toast.
    }
    return false
  }
  try {
    await acknowledgeNotificationDelivery(delivery.delivery_id, delivery.claim_token, 'DELIVERED')
    return true
  } catch {
    // Windows accepted the toast, so never downgrade this ambiguous SENDING
    // claim to FAILED: doing so could retry and display a duplicate.
    return false
  }
}

export async function startDesktopNotificationBridge(onNavigate: (route: string) => void): Promise<() => void> {
  if (!isTauri()) return () => undefined
  const unlisten = await listen<string>('notification-route', async event => {
    const route = event.payload
    if (!validNotificationRoute(route)) return
    const window = getCurrentWindow()
    await window.unminimize()
    await window.show()
    await window.setFocus()
    onNavigate(route)
  })
  let running = false
  const deliver = async () => {
    if (running) return
    running = true
    try {
      // Drain a small bounded batch. Further events wait for the next tick.
      for (let index = 0; index < 5 && await deliverNextDesktopNotification(); index += 1) { /* bounded drain */ }
    } catch {
      // Backend/permission availability is retried on the next bounded poll.
    } finally {
      running = false
    }
  }
  void deliver()
  const interval = window.setInterval(() => void deliver(), 15_000)
  return () => {
    window.clearInterval(interval)
    unlisten()
  }
}
