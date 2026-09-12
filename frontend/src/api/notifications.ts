import { apiRequest, type ApiRequestOptions } from './client'
import type { NotificationDeliveryClaim, NotificationEvent, NotificationPreferences } from '../types'

export function getNotificationPreferences(options?: ApiRequestOptions) {
  return apiRequest<NotificationPreferences>('/api/notifications/preferences', undefined, options)
}

export function updateNotificationPreferences(value: NotificationPreferences) {
  return apiRequest<NotificationPreferences>('/api/notifications/preferences', { method: 'PATCH', body: JSON.stringify(value) })
}

export function getNotificationEvents(options?: ApiRequestOptions) {
  return apiRequest<{ items: NotificationEvent[]; unread: number }>('/api/notifications?limit=8', undefined, options)
}

export function markNotificationRead(eventId: number) {
  return apiRequest<{ event_id: number; read_at: string }>(`/api/notifications/${eventId}/read`, { method: 'POST' })
}

export function claimNotificationDelivery() {
  return apiRequest<{ delivery: NotificationDeliveryClaim | null }>('/api/notifications/claim', { method: 'POST' })
}

export function acknowledgeNotificationDelivery(
  deliveryId: number,
  claimToken: string,
  status: 'DELIVERED' | 'FAILED',
  error?: string,
) {
  return apiRequest<{ delivery_id: number; status: string; attempt_count: number }>(`/api/notifications/deliveries/${deliveryId}/ack`, {
    method: 'POST',
    body: JSON.stringify({ claim_token: claimToken, status, error }),
  })
}
