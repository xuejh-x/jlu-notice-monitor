import { apiRequest, type ApiRequestOptions } from './client'
import type { StorageCleanupResult, StorageStatus } from '../types'

export function getStorageStatus(options?: ApiRequestOptions) {
  return apiRequest<StorageStatus>('/api/storage/status', undefined, options)
}

export function cleanOldNotifications() {
  return apiRequest<StorageCleanupResult>('/api/storage/cleanup', { method: 'POST' })
}
