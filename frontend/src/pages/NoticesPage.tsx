import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { SlidersHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList, NoticeListSkeleton } from '../components/notice/NoticeList'
import { FilterFields } from '../components/notice/NoticeFilters'
import { Button } from '../components/ui/Button'
import { ErrorState } from '../components/ui/Feedback'
import { Input } from '../components/ui/Form'
import { Pagination } from '../components/ui/Pagination'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { loadSettings } from '../stores/settings'
import { countActiveFilters, parseNoticesSearchParams, serializeNoticesSearchParams, type NoticesUrlState } from '../utils/noticeSearchParams'

export function NoticesPage() {
  const savedPageSize = loadSettings().pageSize
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

  const activeCount = countActiveFilters(state)
  const hasSearch = state.q.trim().length > 0

  const clearFilters = () => updateState({ category: '', source: '', minScore: '', dateFrom: '', deadlineStatus: '', read: '', favorite: '' }, { resetPage: true })
  const clearSearch = () => updateState({ q: '' }, { resetPage: true })
  const openSheet = () => { setDraft(state); setSheetOpen(true) }
  const applySheet = () => {
    updateState({ category: draft.category, source: draft.source, minScore: draft.minScore, dateFrom: draft.dateFrom, deadlineStatus: draft.deadlineStatus, read: draft.read, favorite: draft.favorite }, { resetPage: true })
    setSheetOpen(false)
  }
  const resetSheet = () => setDraft({ ...draft, category: '', source: '', minScore: '', dateFrom: '', deadlineStatus: '', read: '', favorite: '' })

  const empty = hasSearch
    ? { title: `没有匹配 “${state.q.trim()}” 的通知`, description: '可以尝试其他关键词。', action: <Button variant="secondary" onClick={clearSearch}>清空搜索</Button> }
    : activeCount > 0
      ? { title: '没有找到相关通知', description: '可以尝试调整筛选条件。', action: <Button variant="secondary" onClick={clearFilters}>清除筛选</Button> }
      : { title: '暂无通知', description: '尚未收录任何通知。' }

  return (
    <>
      <PageHeader title="全部通知" description="筛选和浏览已收录的所有通知。" />
      <section className="mb-4 rounded-large border border-border bg-surface p-3">
        <Input aria-label="搜索通知" placeholder="搜索标题或正文" value={state.q} onChange={event => updateState({ q: event.target.value }, { replace: true, resetPage: true })} className="mb-2 md:max-w-md" />
        <div className="hidden gap-2 md:grid md:grid-cols-3 xl:grid-cols-7">
          <FilterFields state={state} onPatch={changes => updateState(changes, { resetPage: true })} />
        </div>
        <div className="flex items-center justify-between md:hidden">
          <Button id="notice-filter-trigger" variant="secondary" onClick={openSheet} aria-haspopup="dialog" aria-expanded={sheetOpen} aria-controls="notice-filter-dialog"><SlidersHorizontal className="h-4 w-4" />筛选{activeCount > 0 ? ` ${activeCount}` : ''}</Button>
          <span className="text-xs text-text-muted">{activeCount > 0 ? `已应用 ${activeCount} 项筛选` : '全部通知'}</span>
        </div>
      </section>

      {query.isPending ? <NoticeListSkeleton /> : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()} /> : (
        <>
          <div className="mb-3 flex items-center justify-between gap-3 text-xs text-text-muted">
            <span>找到 {query.data.total} 条通知</span>
            <div className="flex items-center gap-3">
              {activeCount > 0 && query.data.total > 0 && <button type="button" onClick={clearFilters} className="hidden items-center gap-1 rounded-medium px-2 py-1 text-text-secondary hover:bg-surface-muted md:inline-flex">清除筛选</button>}
              <span>第 {state.page} 页</span>
            </div>
          </div>
          <NoticeList notices={query.data.items} emptyTitle={empty.title} emptyDescription={empty.description} emptyAction={empty.action} />
          <Pagination page={state.page} totalPages={query.data.total_pages} onPageChange={page => updateState({ page })} />
        </>
      )}

      <Dialog.Root open={sheetOpen} onOpenChange={setSheetOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-overlay" />
          <Dialog.Content id="notice-filter-dialog" aria-describedby={undefined} onCloseAutoFocus={event => { event.preventDefault(); document.getElementById('notice-filter-trigger')?.focus() }} className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-large border-t border-border-strong bg-surface p-4 pb-6">
            <Dialog.Title className="flex items-center justify-between font-semibold">筛选<Dialog.Close className="grid h-11 w-11 place-items-center rounded-medium hover:bg-surface-muted" aria-label="关闭筛选"><X className="h-5 w-5" /></Dialog.Close></Dialog.Title>
            <div className="mt-4 space-y-3"><FilterFields state={draft} onPatch={changes => setDraft(current => ({ ...current, ...changes }))} /></div>
            <div className="mt-5 flex gap-3">
              <Button variant="secondary" className="flex-1" onClick={resetSheet}>重置</Button>
              <Button variant="primary" className="flex-1" onClick={applySheet}>应用{countActiveFilters(draft) > 0 ? ` (${countActiveFilters(draft)})` : ''}</Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}
