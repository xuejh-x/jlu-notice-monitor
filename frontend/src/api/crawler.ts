import type { CrawlerStatus } from '../types'
import { apiRequest } from './client'
export const runCrawler = () => apiRequest<{ message?: string }>('/api/crawler/run', { method: 'POST' })
export const getCrawlerStatus = () => apiRequest<CrawlerStatus>('/api/crawler/status')
