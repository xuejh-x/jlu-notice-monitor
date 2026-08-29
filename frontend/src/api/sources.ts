import type { Source } from '../types'
import { apiRequest } from './client'
export const getSources = () => apiRequest<Source[]>('/api/sources')
