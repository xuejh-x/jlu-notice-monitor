import type { Notice, NoticeDetail, NoticeFilters, NoticeStateResult, PaginatedNotices } from '../types'
import { apiRequest, type ApiRequestOptions } from './client'

function queryString(filters: NoticeFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) })
  const value = params.toString()
  return value ? `?${value}` : ''
}

type NoticesWireResponse = Omit<PaginatedNotices, 'total_count' | 'unread_count' | 'all_count' | 'total'> & {
  total_count?: number
  unread_count?: number
  all_count?: number
  total?: number
}

function normalizePage(page: NoticesWireResponse): PaginatedNotices {
  const totalCount = page.total_count ?? page.total ?? 0
  return {
    ...page,
    total_count: totalCount,
    unread_count: page.unread_count ?? page.items.filter(notice => !notice.is_read).length,
    all_count: page.all_count ?? totalCount,
    total: page.total ?? totalCount,
  }
}

export const getNotices = (filters?: NoticeFilters, options?: ApiRequestOptions) => apiRequest<NoticesWireResponse>(`/api/notices${queryString(filters)}`, undefined, options).then(normalizePage)
export const getTodayNotices = (options?: ApiRequestOptions) => apiRequest<Notice[]>('/api/notices/today', undefined, options)
export const getDeadlineNotices = (days = 30, options?: ApiRequestOptions) => apiRequest<Notice[]>(`/api/notices/deadlines?days=${days}`, undefined, options)
export const getNotice = (id: number, options?: ApiRequestOptions) => apiRequest<NoticeDetail>(`/api/notices/${id}`, undefined, options)
export const searchNotices = (keyword: string, options?: ApiRequestOptions) => apiRequest<NoticesWireResponse>(`/api/search?keyword=${encodeURIComponent(keyword)}&page_size=20`, undefined, options).then(normalizePage)
export const setNoticeRead = (id: number, read: boolean) => apiRequest<Extract<NoticeStateResult, { is_read: boolean }>>(`/api/notices/${id}/${read ? 'read' : 'unread'}`, { method: 'POST' })
export const setAllNoticesRead = () => apiRequest<{ updated: number }>('/api/notices/read-all', { method: 'POST' })
export const setNoticeFavorite = (id: number, favorite: boolean) => apiRequest<Extract<NoticeStateResult, { is_favorite: boolean }>>(`/api/notices/${id}/${favorite ? 'favorite' : 'unfavorite'}`, { method: 'POST' })
