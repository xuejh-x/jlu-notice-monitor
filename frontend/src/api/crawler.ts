import type { CrawlerStatus } from '../types'
import { apiRequest, type ApiRequestOptions } from './client'
// routes.py returns {"status": "started"} for a successful start.
export const runCrawler = () => apiRequest<{ status: string }>('/api/crawler/run', { method: 'POST' })
export const getCrawlerStatus = (options?: ApiRequestOptions) => apiRequest<CrawlerStatus>('/api/crawler/status', undefined, options)
