import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bookmark, CalendarClock, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { setNoticeFavorite } from '../../api/notices'
import type { Notice } from '../../types'
import { useToast } from '../../stores/toast'
import { cn } from '../../utils/cn'
import { relativeTime } from '../../utils/format'
import { categoryLabels } from '../../utils/labels'
import { invalidateNoticeState } from '../../utils/noticeCache'
import { deadlinePresentation, importanceLabels, importanceLevel, isExpired, sourceLabel } from '../../utils/noticeMeta'
import { Badge } from '../ui/Badge'
import { DeadlineBadge } from './DeadlineBadge'
import { SourceIcon } from './SourceIcon'

function categoryVariant(category: string | null): 'accent' | 'success' | 'warning' | 'neutral' {
  if (category === 'research' || category === 'innovation_competition') return 'success'
  if (category === 'training' || category === 'internship') return 'warning'
  if (category && category !== 'other') return 'accent'
  return 'neutral'
}

export function NoticeCard({ notice, selected = false, onSelect, compact = false }: { notice: Notice; selected?: boolean; onSelect?: (id: number) => void; compact?: boolean }) {
  const queryClient = useQueryClient(); const toast = useToast()
  const favorite = useMutation({ mutationFn: () => setNoticeFavorite(notice.id, !notice.is_favorite), onSuccess: () => { invalidateNoticeState(queryClient, notice.id); toast(notice.is_favorite ? '已取消收藏' : '收藏成功') }, onError: () => toast('收藏操作失败，请稍后重试', 'error') })
  const level = importanceLevel(notice.importance_score)
  const deadline = deadlinePresentation(notice)
  const expired = isExpired(notice)

  if (compact) {
    const source = sourceLabel(notice)
    return (
      <article className={cn('group relative mx-3 my-0.5 box-border h-notice-row-height border-b border-border/20 px-2.5 py-1.5 transition-colors hover:bg-surface-muted/40', selected && 'z-10 rounded-design border border-accent/45 bg-selected-surface hover:bg-selected-surface')}>
        <Link
          to={`/notices/${notice.id}`}
          onClick={event => {
            if (!onSelect) return
            event.preventDefault()
            onSelect(notice.id)
          }}
          aria-label={`打开${notice.title}`}
          aria-current={selected ? 'page' : undefined}
          className="absolute inset-0 focus-visible:rounded-design focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        />
        <div className="flex items-center gap-2 text-metadata text-text-muted">
          <SourceIcon name={source} />
          <span className="min-w-0 flex-1 truncate text-text-secondary">{source}</span>
          <time className="shrink-0 tabular-nums">{relativeTime(notice.publish_date)}</time>
        </div>
        <div className="mt-0.5 flex items-start gap-2">
          <span className={cn('mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full', notice.is_read ? 'bg-border-strong' : 'bg-unread')} aria-hidden="true" />
          <span className="sr-only">{notice.is_read ? '已读' : '未读'}</span>
          <h2 className={cn('min-w-0 flex-1 truncate text-left text-notice-title leading-5 group-hover:text-text-primary', expired && 'text-text-secondary', notice.is_read ? 'font-normal text-text-secondary' : 'font-medium text-text-primary', selected && 'text-text-primary')}>{notice.title}</h2>
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-1.5 pl-3.5">
          <Badge variant={categoryVariant(notice.category)} className="h-6 max-w-32 truncate px-2 py-0">{categoryLabels[notice.category ?? ''] ?? '其他'}</Badge>
          {level !== 'normal' && <span className="shrink-0 text-label font-medium text-important">{importanceLabels[level]}</span>}
          <span className="flex-1" />
          <DeadlineBadge notice={notice} />
          <button type="button" onClick={() => favorite.mutate()} disabled={favorite.isPending} aria-label={notice.is_favorite ? '取消收藏' : '收藏通知'} className="relative z-10 -mr-1 grid h-6 w-6 shrink-0 place-items-center rounded-small text-text-muted hover:bg-surface-raised hover:text-important">
            <Bookmark className={cn('h-4 w-4', notice.is_favorite && 'fill-accent-soft-text text-accent-soft-text')} />
          </button>
        </div>
      </article>
    )
  }

  const deadlineTone = deadline.tone === 'danger' ? 'font-medium text-danger' : deadline.tone === 'secondary' ? 'text-text-secondary' : 'text-text-muted'
  return (
    <article className="group flex gap-3 border-b border-border px-1 py-4 last:border-0">
      <span className={cn('mt-2 h-2 w-2 shrink-0 rounded-full', notice.is_read ? 'bg-border' : 'bg-unread')} aria-hidden="true" />
      <span className="sr-only">{notice.is_read ? '已读' : '未读'}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-3">
          <Link to={`/notices/${notice.id}`} className={cn('block min-w-0 flex-1 text-notice-title text-text-primary hover:text-accent-soft-text', expired && 'text-text-secondary', notice.is_read ? 'font-normal' : 'font-medium')}>{notice.title}</Link>
          <button type="button" onClick={() => favorite.mutate()} disabled={favorite.isPending} aria-label={notice.is_favorite ? '取消收藏' : '收藏通知'} className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted hover:text-important md:h-9 md:w-9"><Star className={cn('h-4 w-4', notice.is_favorite && 'fill-important text-important')} /></button>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {level !== 'normal' && <span className={cn('font-medium text-important', level === 'high' && 'font-semibold')}>{importanceLabels[level]}</span>}
          <span className={cn('inline-flex items-center gap-1', deadlineTone)}>{deadline.tone === 'danger' && <CalendarClock className="h-3.5 w-3.5" />}{deadline.text}</span>
          {notice.status === 'updated' && <span className="text-text-muted">已更新</span>}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-text-muted"><span>{sourceLabel(notice)}</span><span aria-hidden="true">·</span><span>{categoryLabels[notice.category ?? ''] ?? '其他'}</span><span aria-hidden="true">·</span><span>{relativeTime(notice.publish_date)}</span></div>
      </div>
    </article>
  )
}
