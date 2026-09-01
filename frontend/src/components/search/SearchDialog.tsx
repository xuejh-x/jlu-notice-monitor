import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { CalendarClock, Search, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchNotices } from '../../api/notices'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import type { Notice } from '../../types'
import { cn } from '../../utils/cn'
import { shortDate } from '../../utils/format'
import { categoryLabels } from '../../utils/labels'
import { deadlinePresentation, importanceLabels, importanceLevel, sourceLabel } from '../../utils/noticeMeta'
import { ErrorState } from '../ui/Feedback'

function SearchResultRow({ notice, id, active, onActivate, onSelect }: { notice: Notice; id: string; active: boolean; onActivate: () => void; onSelect: () => void }) {
  const importance = importanceLevel(notice.importance_score)
  const deadline = deadlinePresentation(notice)
  return <button id={id} type="button" role="option" aria-selected={active} onMouseEnter={onActivate} onFocus={onActivate} onClick={onSelect} className={cn('flex min-h-16 w-full items-start gap-3 rounded-large p-3 text-left hover:bg-surface-muted', active && 'bg-surface-muted')}>
    <span className={`mt-2 h-2 w-2 shrink-0 rounded-full ${notice.is_read ? 'bg-border' : 'bg-unread'}`} aria-hidden="true" />
    <span className="sr-only">{notice.is_read ? '已读' : '未读'}</span>
    <span className="min-w-0 flex-1">
      <span className="block text-sm font-medium leading-5 text-text-primary">{notice.title}</span>
      {(importance !== 'normal' || notice.registration_deadline) && <span className="mt-1 flex flex-wrap items-center gap-2 text-metadata">
        {importance !== 'normal' && <span className="font-medium text-important">{importanceLabels[importance]}</span>}
        {notice.registration_deadline && <span className={deadline.tone === 'danger' ? 'inline-flex items-center gap-1 text-danger' : 'text-text-secondary'}>{deadline.tone === 'danger' && <CalendarClock className="h-3 w-3" aria-hidden="true" />}{deadline.text}</span>}
      </span>}
      <span className="mt-1 block text-metadata text-text-muted">{sourceLabel(notice)} · {categoryLabels[notice.category ?? ''] ?? '其他'} · {shortDate(notice.publish_date)}</span>
    </span>
  </button>
}

function SearchResults({ listboxId, keyword, waiting, pending, error, notices, total, activeIndex, onActivate, onSelect, onRetry }: { listboxId: string; keyword: string; waiting: boolean; pending: boolean; error: Error | null; notices: Notice[]; total: number; activeIndex: number; onActivate: (index: number) => void; onSelect: (notice: Notice) => void; onRetry: () => void }) {
  if (waiting || pending) return <div className="grid h-36 place-items-center text-sm text-text-muted" aria-live="polite">正在搜索……</div>
  if (error) return <ErrorState error={error} retry={onRetry} compact />
  if (!notices.length) return <div className="grid h-36 place-items-center px-4 text-center"><div><p className="font-medium text-text-primary">没有匹配“{keyword}”的通知</p><p className="mt-1 text-sm text-text-secondary">可以尝试更短的关键词或检查输入。</p></div></div>
  return <div id={listboxId} role="listbox" aria-label={`搜索结果，共 ${total} 条`} className="p-2">{notices.map((notice, index) => <SearchResultRow key={notice.id} id={`${listboxId}-option-${notice.id}`} notice={notice} active={activeIndex === index} onActivate={() => onActivate(index)} onSelect={() => onSelect(notice)} />)}</div>
}

export function SearchDialog() {
  const [desktopOpen, setDesktopOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [activeIndex, setActiveIndex] = useState(-1)
  const desktopInputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const listboxId = useId()
  const normalizedKeyword = keyword.trim()
  const debouncedKeyword = useDebouncedValue(normalizedKeyword)
  const query = useQuery({ queryKey: ['search', debouncedKeyword], queryFn: ({ signal }) => searchNotices(debouncedKeyword, { signal }), enabled: debouncedKeyword.length > 0 })
  const notices = query.data?.items ?? []
  const waitingForDebounce = normalizedKeyword.length > 0 && normalizedKeyword !== debouncedKeyword
  const shortcut = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K'

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'k') return
      const target = event.target
      const editingElsewhere = target instanceof HTMLElement && target !== desktopInputRef.current && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
      if (editingElsewhere) return
      event.preventDefault()
      if (window.matchMedia?.('(min-width: 768px)').matches ?? true) {
        setDesktopOpen(Boolean(keyword.trim()))
        requestAnimationFrame(() => { desktopInputRef.current?.focus(); desktopInputRef.current?.select() })
      } else setMobileOpen(true)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [keyword])

  const openNotice = (notice: Notice) => { setDesktopOpen(false); setMobileOpen(false); navigate(`/notices/${notice.id}`) }
  const handleKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>, close: () => void) => {
    if (event.key === 'Escape') { event.preventDefault(); close(); return }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!notices.length) return
      setDesktopOpen(true)
      setActiveIndex(current => event.key === 'ArrowDown' ? (current + 1 + notices.length) % notices.length : (current - 1 + notices.length) % notices.length)
      return
    }
    if (event.key === 'Enter' && activeIndex >= 0 && notices[activeIndex]) { event.preventDefault(); openNotice(notices[activeIndex]) }
  }
  const updateKeyword = (value: string) => { setKeyword(value); setActiveIndex(-1); setDesktopOpen(Boolean(value.trim())) }
  const clearKeyword = () => { setKeyword(''); setDesktopOpen(false); setActiveIndex(-1); desktopInputRef.current?.focus() }
  const results = (id: string) => <SearchResults listboxId={id} keyword={debouncedKeyword} waiting={waitingForDebounce} pending={query.isPending} error={query.isError ? query.error : null} notices={notices} total={query.data?.total ?? 0} activeIndex={activeIndex} onActivate={setActiveIndex} onSelect={openNotice} onRetry={() => { void query.refetch() }} />

  return <>
    <div className="relative hidden w-[438px] shrink-0 md:block" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setDesktopOpen(false) }}>
      <div className="flex h-[34px] items-center gap-2 rounded-design border border-border/70 bg-surface-muted px-3 text-sm text-text-muted focus-within:border-accent/50 focus-within:ring-2 focus-within:ring-focus/20">
        <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
        <input ref={desktopInputRef} role="combobox" aria-label="搜索通知" aria-autocomplete="list" aria-controls={listboxId} aria-expanded={desktopOpen && Boolean(normalizedKeyword)} aria-activedescendant={activeIndex >= 0 && notices[activeIndex] ? `${listboxId}-option-${notices[activeIndex].id}` : undefined} value={keyword} onChange={event => updateKeyword(event.target.value)} onFocus={() => setDesktopOpen(Boolean(normalizedKeyword))} onKeyDown={event => handleKeyDown(event, () => setDesktopOpen(false))} placeholder="搜索通知、学院或关键词" className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted" />
        {keyword ? <button type="button" onClick={clearKeyword} className="grid h-7 w-7 shrink-0 place-items-center rounded-small text-text-muted hover:bg-surface hover:text-text-primary" aria-label="清空搜索"><X className="h-3.5 w-3.5" aria-hidden="true" /></button> : <kbd className="shrink-0 rounded-[5px] border border-border bg-header-surface px-1.5 py-0.5 text-[10px] text-text-muted">{shortcut}</kbd>}
      </div>
      {desktopOpen && normalizedKeyword && <div className="absolute left-0 top-[calc(100%+6px)] z-50 max-h-[min(60vh,32rem)] w-full overflow-y-auto rounded-xlarge border border-border-strong bg-surface-raised shadow-2xl">{results(listboxId)}</div>}
    </div>
    <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
      <Dialog.Trigger asChild><button type="button" className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-design border border-border/70 bg-surface-muted px-3 text-left text-sm text-text-muted md:hidden"><Search className="h-4 w-4" aria-hidden="true" /><span className="truncate">搜索通知、学院或关键词</span></button></Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-overlay backdrop-blur-[2px]" />
        <Dialog.Content aria-describedby={undefined} className="fixed inset-x-4 top-4 z-50 max-h-[calc(100vh-2rem)] overflow-hidden rounded-xlarge border border-border-strong bg-surface-raised shadow-2xl">
          <Dialog.Title className="sr-only">搜索通知</Dialog.Title>
          <div className="flex items-center gap-3 border-b border-border px-3"><Search className="h-5 w-5 shrink-0 text-text-muted" aria-hidden="true" /><input autoFocus role="combobox" aria-label="搜索通知" aria-autocomplete="list" aria-controls={`${listboxId}-mobile`} aria-expanded={Boolean(normalizedKeyword)} value={keyword} onChange={event => { setKeyword(event.target.value); setActiveIndex(-1) }} onKeyDown={event => handleKeyDown(event, () => setMobileOpen(false))} placeholder="输入蓝桥杯、CTF、推免、实验室……" className="h-14 min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted" />{keyword && <button type="button" onClick={() => { setKeyword(''); setActiveIndex(-1) }} className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted hover:text-text-primary" aria-label="清空搜索"><X className="h-4 w-4" /></button>}<Dialog.Close className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted hover:text-text-primary" aria-label="关闭搜索"><X className="h-4 w-4" /></Dialog.Close></div>
          <div className="max-h-[min(60vh,32rem)] min-h-48 overflow-y-auto">{normalizedKeyword ? results(`${listboxId}-mobile`) : <div className="grid h-44 place-items-center px-4 text-center text-sm text-text-muted">输入关键词开始搜索</div>}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </>
}
