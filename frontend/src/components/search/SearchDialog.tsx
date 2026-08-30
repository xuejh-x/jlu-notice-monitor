import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { CalendarClock, Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchNotices } from '../../api/notices'
import { ErrorState } from '../ui/Feedback'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import type { Notice } from '../../types'
import { shortDate } from '../../utils/format'
import { categoryLabels } from '../../utils/labels'
import { deadlinePresentation, importanceLabels, importanceLevel, sourceLabel } from '../../utils/noticeMeta'

function SearchResultRow({ notice, onSelect }: { notice: Notice; onSelect: () => void }) {
  const importance = importanceLevel(notice.importance_score)
  const deadline = deadlinePresentation(notice)
  return (
    <button type="button" onClick={onSelect} className="flex min-h-16 w-full items-start gap-3 rounded-large p-3 text-left hover:bg-surface-muted">
      <span className={`mt-2 h-2 w-2 shrink-0 rounded-full ${notice.is_read ? 'bg-border' : 'bg-unread'}`} aria-hidden="true"/>
      <span className="sr-only">{notice.is_read ? '已读' : '未读'}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium leading-5 text-text-primary">{notice.title}</span>
        {(importance !== 'normal' || notice.registration_deadline) && <span className="mt-1 flex flex-wrap items-center gap-2 text-metadata">
          {importance !== 'normal' && <span className="font-medium text-important">{importanceLabels[importance]}</span>}
          {notice.registration_deadline && <span className={deadline.tone === 'danger' ? 'inline-flex items-center gap-1 text-danger' : 'text-text-secondary'}>{deadline.tone === 'danger' && <CalendarClock className="h-3 w-3" aria-hidden="true"/>}{deadline.text}</span>}
        </span>}
        <span className="mt-1 block text-metadata text-text-muted">{sourceLabel(notice)} · {categoryLabels[notice.category ?? ''] ?? '其他'} · {shortDate(notice.publish_date)}</span>
      </span>
    </button>
  )
}
export function SearchDialog() {
  const [open, setOpen] = useState(false)
  const [keyword, setKeyword] = useState('')
  const navigate = useNavigate()
  const normalizedKeyword = keyword.trim()
  const debouncedKeyword = useDebouncedValue(normalizedKeyword)

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const query = useQuery({
    queryKey: ['search', debouncedKeyword],
    queryFn: ({ signal }) => searchNotices(debouncedKeyword, { signal }),
    enabled: debouncedKeyword.length > 0,
  })
  const waitingForDebounce = normalizedKeyword.length > 0 && normalizedKeyword !== debouncedKeyword

  const openNotice = (id: number) => {
    setOpen(false)
    navigate(`/notices/${id}`)
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button type="button" className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-medium border border-border bg-surface-muted px-3 text-left text-sm text-text-muted hover:border-border-strong sm:max-w-md md:h-9">
          <Search className="h-4 w-4" aria-hidden="true"/>
          <span className="truncate">搜索通知、学院或关键词</span>
          <kbd className="ml-auto hidden rounded-small border border-border bg-surface px-1.5 py-0.5 text-[10px] text-text-muted sm:block">Ctrl K</kbd>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-overlay backdrop-blur-[2px]"/>
        <Dialog.Content aria-describedby={undefined} className="fixed inset-x-4 top-4 z-50 max-h-[calc(100vh-2rem)] overflow-hidden rounded-xlarge border border-border-strong bg-surface-raised shadow-2xl sm:left-1/2 sm:right-auto sm:top-[12vh] sm:w-[calc(100%-2rem)] sm:max-w-2xl sm:-translate-x-1/2">
          <Dialog.Title className="sr-only">搜索通知</Dialog.Title>
          <div className="flex items-center gap-3 border-b border-border px-3 sm:px-4">
            <Search className="h-5 w-5 shrink-0 text-text-muted" aria-hidden="true"/>
            <input autoFocus aria-label="搜索通知" value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="输入蓝桥杯、CTF、推免、实验室……" className="h-14 min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"/>
            <Dialog.Close className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted hover:text-text-primary" aria-label="关闭搜索"><X className="h-4 w-4"/></Dialog.Close>
          </div>
          <div className="max-h-[min(60vh,32rem)] min-h-48 overflow-y-auto p-2">
            {!normalizedKeyword ? <div className="grid h-44 place-items-center px-4 text-center text-sm text-text-muted">输入关键词开始搜索</div>
              : waitingForDebounce || query.isPending ? <div className="grid h-44 place-items-center text-sm text-text-muted" aria-live="polite">正在搜索……</div>
                : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()}/>
                  : query.data.items.length ? <div aria-label={`搜索结果，共 ${query.data.total} 条`}>{query.data.items.map(notice => <SearchResultRow key={notice.id} notice={notice} onSelect={() => openNotice(notice.id)}/>)}</div>
                    : <div className="grid h-44 place-items-center px-4 text-center"><div><p className="font-medium text-text-primary">没有匹配“{debouncedKeyword}”的通知</p><p className="mt-1 text-sm text-text-secondary">可以尝试更短的关键词或检查输入。</p></div></div>}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
