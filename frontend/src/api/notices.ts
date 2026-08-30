import type { Notice, NoticeDetail, NoticeFilters, NoticeStateResult, PaginatedNotices } from '../types'
import { apiRequest, type ApiRequestOptions } from './client'

function queryString(filters: NoticeFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) })
  const value = params.toString()
  return value ? `?${value}` : ''
}

export const getNotices = (filters?: NoticeFilters, options?: ApiRequestOptions) => apiRequest<PaginatedNotices>(`/api/notices${queryString(filters)}`, undefined, options)
export const getTodayNotices = (options?: ApiRequestOptions) => apiRequest<Notice[]>('/api/notices/today', undefined, options)
export const getDeadlineNotices = (days = 30, options?: ApiRequestOptions) => apiRequest<Notice[]>(`/api/notices/deadlines?days=${days}`, undefined, options)
export const getNotice = (id: number, options?: ApiRequestOptions) => apiRequest<NoticeDetail>(`/api/notices/${id}`, undefined, options)
export const searchNotices = (keyword: string, options?: ApiRequestOptions) => apiRequest<PaginatedNotices>(`/api/search?keyword=${encodeURIComponent(keyword)}&page_size=20`, undefined, options)
export const setNoticeRead = (id: number, read: boolean) => apiRequest<Extract<NoticeStateResult, { is_read: boolean }>>(`/api/notices/${id}/${read ? 'read' : 'unread'}`, { method: 'POST' })
export const setNoticeFavorite = (id: number, favorite: boolean) => apiRequest<Extract<NoticeStateResult, { is_favorite: boolean }>>(`/api/notices/${id}/${favorite ? 'favorite' : 'unfavorite'}`, { method: 'POST' })
