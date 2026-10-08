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
import { deadlinePresentation, importanceLabels, importanceLevel, isExpired, sourceLabel, usesDetectionTime } from '../../utils/noticeMeta'
import { Badge } from '../ui/Badge'
import { DeadlineBadge } from './DeadlineBadge'
import { SourceIcon } from './SourceIcon'
import { NoticeCategoryTag } from './NoticeCategoryTag'

export function NoticeCard({ notice, selected = false, onSelect, compact = false }: { notice: Notice; selected?: boolean; onSelect?: (id: number) => void; compact?: boolean }) {
  const queryClient = useQueryClient(); const toast = useToast()
  const favorite = useMutation({ mutationFn: () => setNoticeFavorite(notice.id, !notice.is_favorite), onSuccess: () => { invalidateNoticeState(queryClient, notice.id); toast(notice.is_favorite ? '已取消收藏' : '收藏成功') }, onError: () => toast('收藏操作失败，请稍后重试', 'error') })
  const level = importanceLevel(notice.importance_score)
  const deadline = deadlinePresentation(notice)
  const expired = isExpired(notice)
  const detected = usesDetectionTime(notice)
  const timestamp = detected ? notice.first_seen_at : notice.publish_date

  if (compact) {
    const source = sourceLabel(notice)
    return (
      <article className={cn('group relative box-border flex h-notice-row-height min-w-0 flex-col gap-0.5 px-shell-gutter py-2.5 transition-colors hover:bg-surface-hover active:bg-selected-surface', selected && 'bg-selected-surface hover:bg-selected-surface')}>
        <Link
          to={`/notices/${notice.id}`}
          onClick={event => {
            if (!onSelect) return
            event.preventDefault()
            onSelect(notice.id)
          }}
          aria-label={`打开${notice.title}`}
          aria-current={selected ? 'page' : undefined}
          title={notice.title}
          className="absolute inset-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
        />
        <div className="pointer-events-none flex h-4.5 shrink-0 items-center gap-1.5 text-metadata text-text-muted">
          <SourceIcon name={source} inline />
          <span className="min-w-0 flex-1 truncate text-text-secondary">{source}</span>
          <time dateTime={timestamp ?? undefined} className="shrink-0 tabular-nums">{detected ? '首次检测：' : ''}{relativeTime(timestamp)}</time>
        </div>
        <div className="pointer-events-none flex h-6 shrink-0 items-center gap-2">
          {!notice.is_read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-unread" aria-hidden="true" />}
          <h2 className={cn('min-w-0 flex-1 truncate text-left text-notice-title font-medium', notice.is_read || expired ? 'text-text-secondary' : 'text-text-primary', selected && 'text-text-primary')}>{notice.title}</h2>
        </div>
        <div className="flex h-5 min-w-0 shrink-0 items-center gap-2 text-label text-text-muted">
          <div className="pointer-events-none flex min-w-0 flex-1 items-center gap-2">
            <NoticeCategoryTag category={notice.category} />
            <span className={cn('shrink-0', !notice.is_read && 'text-accent-soft-text')}>{notice.is_read ? '已读' : '未读'}</span>
            {level !== 'normal' && <Badge variant="important" className="shrink-0 gap-1 border-0 bg-transparent p-0"><Star className="h-3 w-3" aria-hidden="true" />{importanceLabels[level]}</Badge>}
            {notice.status === 'updated' && <Badge className="min-w-0 truncate rounded-compact border-source-green-fg/20 bg-source-green-bg px-1.5 py-0 text-source-green-fg">已更新</Badge>}
          </div>
          <DeadlineBadge notice={notice} list />
          <button type="button" onClick={() => favorite.mutate()} disabled={favorite.isPending} aria-label={notice.is_favorite ? '取消收藏' : '收藏通知'} aria-pressed={notice.is_favorite} className="relative z-10 grid h-5 w-5 shrink-0 place-items-center rounded-small text-text-muted hover:bg-surface-raised hover:text-accent-soft-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50">
            <Bookmark className={cn('h-3.5 w-3.5', notice.is_favorite && 'fill-accent-soft-text text-accent-soft-text')} aria-hidden="true" />
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
        <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-text-muted"><span>{sourceLabel(notice)}</span><span aria-hidden="true">·</span><span>{categoryLabels[notice.category ?? ''] ?? '其他'}</span><span aria-hidden="true">·</span><span>{detected ? '首次检测：' : ''}{relativeTime(timestamp)}</span></div>
      </div>
    </article>
  )
}
