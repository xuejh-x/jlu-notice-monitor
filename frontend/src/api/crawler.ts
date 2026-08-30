import type { CrawlerStatus } from '../types'
import { apiRequest, type ApiRequestOptions } from './client'
export const runCrawler = () => apiRequest<{ message?: string }>('/api/crawler/run', { method: 'POST' })
export const getCrawlerStatus = (options?: ApiRequestOptions) => apiRequest<CrawlerStatus>('/api/crawler/status', undefined, options)
