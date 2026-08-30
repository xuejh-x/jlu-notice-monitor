import type { DashboardData, Notice } from '../types'
import { apiRequest, type ApiRequestOptions } from './client'

export const getDashboard = (options?: ApiRequestOptions) => apiRequest<DashboardData>('/api/dashboard', undefined, options)
export const getImportantNotices = (minScore = 70, options?: ApiRequestOptions) => apiRequest<Notice[]>(`/api/notices/important?min_score=${minScore}`, undefined, options)
