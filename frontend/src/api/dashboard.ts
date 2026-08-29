import type { DashboardData, Notice } from '../types'
import { apiRequest } from './client'

export const getDashboard = () => apiRequest<DashboardData>('/api/dashboard')
export const getImportantNotices = (minScore = 70) => apiRequest<Notice[]>(`/api/notices/important?min_score=${minScore}`)
