import type { Notice, NoticeDetail, NoticeFilters, PaginatedNotices } from '../types'
import { apiRequest } from './client'

function queryString(filters: NoticeFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) })
  const value = params.toString()
  return value ? `?${value}` : ''
}

export const getNotices = (filters?: NoticeFilters) => apiRequest<PaginatedNotices>(`/api/notices${queryString(filters)}`)
export const getTodayNotices = () => apiRequest<Notice[]>('/api/notices/today')
export const getDeadlineNotices = (days = 30) => apiRequest<Notice[]>(`/api/notices/deadlines?days=${days}`)
export const getNotice = (id: number) => apiRequest<NoticeDetail>(`/api/notices/${id}`)
export const searchNotices = (keyword: string) => apiRequest<PaginatedNotices>(`/api/search?keyword=${encodeURIComponent(keyword)}&page_size=20`)
export const setNoticeRead = (id: number, read: boolean) => apiRequest<Notice>(`/api/notices/${id}/${read ? 'read' : 'unread'}`, { method: 'POST' })
export const setNoticeFavorite = (id: number, favorite: boolean) => apiRequest<Notice>(`/api/notices/${id}/${favorite ? 'favorite' : 'unfavorite'}`, { method: 'POST' })
