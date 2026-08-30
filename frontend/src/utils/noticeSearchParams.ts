const categories = new Set([
  'algorithm_competition',
  'cybersecurity_competition',
  'innovation_competition',
  'training',
  'internship',
  'research',
  'postgraduate_recommendation',
  'academic',
])
const sources = new Set(['cse', 'ccst', 'csw', 'jwc', 'innovation', 'oa'])
const scores = new Set(['70', '80', '90'])
const deadlineStatuses = new Set(['today', 'urgent', 'normal', 'expired', 'unknown'])
const pageSizes = new Set([10, 20, 50])

export interface NoticesUrlState {
  q: string
  category: string
  source: string
  minScore: string
  dateFrom: string
  deadlineStatus: string
  read: '' | 'read' | 'unread'
  favorite: '' | 'favorite' | 'normal'
  page: number
  pageSize: number
}

const enumValue = (params: URLSearchParams, key: string, allowed: Set<string>) => {
  const value = params.get(key) ?? ''
  return allowed.has(value) ? value : ''
}

const positiveInteger = (value: string | null) => {
  if (!value || !/^[1-9]\d*$/.test(value)) return 1
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) ? parsed : 1
}

const validDate = (value: string | null) => {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return ''
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value ? value : ''
}

const validPageSize = (value: number) => pageSizes.has(value) ? value : 20

export function parseNoticesSearchParams(params: URLSearchParams, savedPageSize: number): NoticesUrlState {
  const pageSizeParam = Number(params.get('page_size'))
  const readParam = params.get('read')
  const favoriteParam = params.get('favorite')
  return {
    q: params.get('q') ?? '',
    category: enumValue(params, 'category', categories),
    source: enumValue(params, 'source', sources),
    minScore: enumValue(params, 'min_score', scores),
    dateFrom: validDate(params.get('date_from')),
    deadlineStatus: enumValue(params, 'deadline_status', deadlineStatuses),
    read: readParam === '1' ? 'read' : readParam === '0' ? 'unread' : '',
    favorite: favoriteParam === '1' ? 'favorite' : favoriteParam === '0' ? 'normal' : '',
    page: positiveInteger(params.get('page')),
    pageSize: pageSizes.has(pageSizeParam) ? pageSizeParam : validPageSize(savedPageSize),
  }
}

export function serializeNoticesSearchParams(state: NoticesUrlState, savedPageSize: number) {
  const params = new URLSearchParams()
  if (state.q.trim()) params.set('q', state.q)
  if (state.category) params.set('category', state.category)
  if (state.source) params.set('source', state.source)
  if (state.minScore) params.set('min_score', state.minScore)
  if (state.dateFrom) params.set('date_from', state.dateFrom)
  if (state.deadlineStatus) params.set('deadline_status', state.deadlineStatus)
  if (state.read) params.set('read', state.read === 'read' ? '1' : '0')
  if (state.favorite) params.set('favorite', state.favorite === 'favorite' ? '1' : '0')
  if (state.page > 1) params.set('page', String(state.page))
  if (state.pageSize !== validPageSize(savedPageSize)) params.set('page_size', String(state.pageSize))
  return params
}

/** Count non-default filters (q / page / page_size excluded). */
export function countActiveFilters(state: Pick<NoticesUrlState, 'category' | 'source' | 'minScore' | 'dateFrom' | 'deadlineStatus' | 'read' | 'favorite'>): number {
  let count = 0
  if (state.category) count++
  if (state.source) count++
  if (state.minScore) count++
  if (state.dateFrom) count++
  if (state.deadlineStatus) count++
  if (state.read) count++
  if (state.favorite) count++
  return count
}
