import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { List, Search, SlidersHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getNotices } from '../api/notices'
import { getDashboard } from '../api/dashboard'
import { NoticeList, NoticeListSkeleton } from '../components/notice/NoticeList'
import { FilterFields } from '../components/notice/NoticeFilters'
import { Button } from '../components/ui/Button'
import { ErrorState } from '../components/ui/Feedback'
import { Pagination } from '../components/ui/Pagination'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { loadSettings } from '../stores/settings'
import { cn } from '../utils/cn'
import { countActiveFilters, parseNoticesSearchParams, serializeNoticesSearchParams, type NoticesUrlState } from '../utils/noticeSearchParams'

const readTabs: Array<{ label: string; value: NoticesUrlState['read'] }> = [
  { label: '全部', value: '' },
  { label: '未读', value: 'unread' },
  { label: '已读', value: 'read' },
]

export function NoticesPage({ selectedId = null }: { selectedId?: number | null }) {
  const savedPageSize = loadSettings().pageSize
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const state = parseNoticesSearchParams(searchParams, savedPageSize)
  const debouncedKeyword = useDebouncedValue(state.q.trim())
  const [sheetOpen, setSheetOpen] = useState(false)
  const [draft, setDraft] = useState<NoticesUrlState>(state)

  const updateState = (changes: Partial<NoticesUrlState>, { replace = false, resetPage = false } = {}) => {
    const next = { ...state, ...changes }
    if (resetPage) next.page = 1
    setSearchParams(serializeNoticesSearchParams(next, savedPageSize), { replace })
  }
  const requestFilters = {
    q: debouncedKeyword || undefined,
    category: state.category || undefined,
    source: state.source || undefined,
    min_score: state.minScore ? Number(state.minScore) : undefined,
    deadline_status: state.deadlineStatus || undefined,
    date_from: state.dateFrom || undefined,
    read: state.read ? state.read === 'read' : undefined,
    favorite: state.favorite ? state.favorite === 'favorite' : undefined,
    page: state.page,
    page_size: state.pageSize,
  }

  const query = useQuery({
    queryKey: ['notices', 'all', requestFilters],
    queryFn: ({ signal }) => getNotices(requestFilters, { signal }),
    placeholderData: previous => previous,
  })
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: ({ signal }) => getDashboard({ signal }) })

  const activeCount = countActiveFilters(state)
  const nonReadFilterCount = activeCount - (state.read ? 1 : 0)
  const hasSearch = state.q.trim().length > 0
  const clearFilters = () => updateState({ category: '', source: '', minScore: '', dateFrom: '', deadlineStatus: '', read: '', favorite: '' }, { resetPage: true })
  const clearSearch = () => updateState({ q: '' }, { resetPage: true })
  const openSheet = () => { setDraft(state); setSheetOpen(true) }
  const selectNotice = (id: number) => navigate({ pathname: `/notices/${id}`, search: searchParams.toString() ? `?${searchParams.toString()}` : '' })
  const applySheet = () => {
    updateState({ q: draft.q, category: draft.category, source: draft.source, minScore: draft.minScore, dateFrom: draft.dateFrom, deadlineStatus: draft.deadlineStatus, read: draft.read, favorite: draft.favorite }, { resetPage: true })
    setSheetOpen(false)
  }
  const resetSheet = () => setDraft({ ...draft, q: '', category: '', source: '', minScore: '', dateFrom: '', deadlineStatus: '', read: '', favorite: '' })

  const empty = hasSearch
    ? { title: `没有匹配 “${state.q.trim()}” 的通知`, description: '可以尝试其他关键词。', action: <Button variant="secondary" onClick={clearSearch}>清空搜索</Button> }
    : activeCount > 0
      ? { title: '没有找到相关通知', description: '可以尝试调整筛选条件。', action: <Button variant="secondary" onClick={clearFilters}>清除筛选</Button> }
      : { title: '暂无通知', description: '尝试调整筛选条件或检查新通知。' }

  return (
    <div className="flex min-h-[calc(100vh-var(--spacing-header-height)-2.5rem)] flex-col md:h-full md:min-h-0 md:bg-list-surface">
      <label className="mb-3 flex h-9 items-center gap-2 rounded-medium border border-border bg-surface-muted px-3 text-sm text-text-muted focus-within:border-border-strong focus-within:ring-2 focus-within:ring-focus/20 md:hidden">
          <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
          <input aria-label="搜索通知" placeholder="搜索通知、来源或关键词" value={state.q} onChange={event => updateState({ q: event.target.value }, { replace: true, resetPage: true })} className="min-w-0 flex-1 bg-transparent text-text-primary outline-none placeholder:text-text-muted" />
          <kbd className="rounded-small border border-border bg-surface px-1.5 text-label text-text-muted">Ctrl K</kbd>
      </label>
      <header className="flex h-list-header-height shrink-0 items-center justify-between gap-2 border-b border-border/70 bg-header-surface px-3">
          <div className="flex min-w-0" role="tablist" aria-label="阅读状态">
            {readTabs.map(tab => {
              const selected = state.read === tab.value
              const count = tab.value === '' ? query.data?.total : tab.value === 'unread' ? dashboard.data?.unread : undefined
              return <button key={tab.label} type="button" role="tab" aria-label={tab.label} aria-selected={selected} onClick={() => updateState({ read: tab.value }, { resetPage: true })} className={cn('h-[26px] shrink-0 rounded-small px-2 text-xs transition-colors', selected ? 'border border-accent/20 bg-accent-soft font-medium text-accent-soft-text' : 'text-text-muted hover:text-text-primary')}>{tab.label}{count !== undefined && <span aria-hidden="true"> {count}</span>}</button>
            })}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button type="button" disabled title="排序将在后续阶段接入" className="hidden h-8 items-center px-2 text-xs text-text-muted disabled:opacity-80 sm:inline-flex" aria-label="按截止时间排序">按截止时间 ↑</button>
            <button type="button" disabled className="grid h-8 w-8 place-items-center rounded-medium text-text-muted" aria-label="列表视图"><List className="h-3.5 w-3.5" /></button>
            <button id="notice-filter-trigger" type="button" onClick={openSheet} aria-haspopup="dialog" aria-expanded={sheetOpen} aria-controls="notice-filter-dialog" className="relative grid h-8 w-6 place-items-center rounded-medium text-text-muted/60 hover:bg-surface-muted hover:text-text-muted active:translate-y-px" aria-label={`筛选${nonReadFilterCount > 0 ? ` ${nonReadFilterCount}` : ''}`}><SlidersHorizontal className="h-3 w-3" />{nonReadFilterCount > 0 && <span className="absolute right-0 top-1 h-1.5 w-1.5 rounded-full bg-accent" />}</button>
          </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {query.isPending ? <NoticeListSkeleton compact /> : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()} compact /> : (
          <>
            <div className="flex items-center justify-between px-4 py-2 text-metadata text-text-muted md:hidden"><span>找到 {query.data.total} 条通知</span><span>第 {state.page} 页</span></div>
            <NoticeList notices={query.data.items} selectedId={selectedId} onSelect={selectNotice} emptyTitle={empty.title} emptyDescription={empty.description} emptyAction={empty.action} compact />
            <div className="mt-auto border-t border-border px-3 py-3"><Pagination page={state.page} totalPages={query.data.total_pages} onPageChange={page => updateState({ page })} /></div>
          </>
        )}
      </div>

      <Dialog.Root open={sheetOpen} onOpenChange={setSheetOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-overlay" />
          <Dialog.Content id="notice-filter-dialog" aria-describedby={undefined} onCloseAutoFocus={event => { event.preventDefault(); document.getElementById('notice-filter-trigger')?.focus() }} className="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xlarge border border-border-strong bg-surface-raised p-4 shadow-2xl">
            <Dialog.Title className="flex items-center justify-between font-semibold">筛选通知<Dialog.Close className="grid h-9 w-9 place-items-center rounded-medium hover:bg-surface-muted" aria-label="关闭筛选"><X className="h-5 w-5" /></Dialog.Close></Dialog.Title>
            <div className="mt-4 grid gap-3">
              <label className="grid gap-1 text-xs font-medium text-text-secondary">关键词<input aria-label="搜索通知" placeholder="搜索标题、正文或来源" value={draft.q} onChange={event => setDraft(current => ({ ...current, q: event.target.value }))} className="h-9 rounded-medium border border-border bg-surface px-3 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-border-strong" /></label>
              <FilterFields state={draft} onPatch={changes => setDraft(current => ({ ...current, ...changes }))} />
            </div>
            <div className="mt-5 flex gap-3"><Button variant="secondary" className="flex-1" onClick={resetSheet}>重置</Button><Button variant="primary" className="flex-1" onClick={applySheet}>应用{countActiveFilters(draft) > 0 ? ` (${countActiveFilters(draft)})` : ''}</Button></div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
