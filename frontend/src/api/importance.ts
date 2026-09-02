import type { ImportanceRule } from '../types'
import { apiRequest, type ApiRequestOptions } from './client'

const json = (method: string, value?: unknown): RequestInit => ({ method, body: value === undefined ? undefined : JSON.stringify(value) })
export const getImportanceRules = (options?: ApiRequestOptions) => apiRequest<ImportanceRule[]>('/api/importance/rules', undefined, options)
export const createImportanceRule = (keyword: string, weight: number) => apiRequest<ImportanceRule>('/api/importance/rules', json('POST', { keyword, weight, enabled: true }))
export const updateImportanceRule = (id: number, values: Partial<Pick<ImportanceRule, 'keyword' | 'weight' | 'enabled'>>) => apiRequest<ImportanceRule>(`/api/importance/rules/${id}`, json('PATCH', values))
export const deleteImportanceRule = (id: number) => apiRequest<{ rescored: number }>(`/api/importance/rules/${id}`, json('DELETE'))
export const restoreImportanceDefaults = () => apiRequest<{ rescored: number }>('/api/importance/restore-defaults', json('POST'))
