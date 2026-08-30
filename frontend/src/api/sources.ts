import type { Source } from '../types'
import { apiRequest, type ApiRequestOptions } from './client'
export const getSources = (options?: ApiRequestOptions) => apiRequest<Source[]>('/api/sources', undefined, options)
