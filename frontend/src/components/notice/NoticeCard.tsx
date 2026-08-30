import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { setNoticeFavorite } from '../../api/notices'
import type { Notice } from '../../types'
import { useToast } from '../../stores/toast'
import { cn } from '../../utils/cn'
import { shortDate } from '../../utils/format'
import { categoryLabels } from '../../utils/labels'
import { deadlinePresentation, importanceLabels, importanceLevel, isExpired, sourceLabel } from '../../utils/noticeMeta'

export function NoticeCard({ notice }: { notice: Notice }) {
  const queryClient = useQueryClient(); const toast = useToast()
  const favorite = useMutation({ mutationFn: () => setNoticeFavorite(notice.id, !notice.is_favorite), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['notices'] }); queryClient.invalidateQueries({ queryKey: ['dashboard'] }); toast(notice.is_favorite ? '已取消收藏' : '收藏成功') }, onError: () => toast('收藏操作失败，请稍后重试', 'error') })
  const level = importanceLevel(notice.importance_score)
  const deadline = deadlinePresentation(notice)
  const deadlineTone = deadline.tone === 'danger' ? 'font-medium text-danger' : deadline.tone === 'secondary' ? 'text-text-secondary' : 'text-text-muted'
  const expired = isExpired(notice)

  return (
    <article className="group flex gap-3 border-b border-border px-1 py-4 last:border-0">
      <span className={cn('mt-2 h-2 w-2 shrink-0 rounded-full', notice.is_read ? 'bg-border' : 'bg-unread')} aria-hidden="true" />
      <span className="sr-only">{notice.is_read ? '已读' : '未读'}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-3">
          <Link to={`/notices/${notice.id}`} className={cn('block min-w-0 flex-1 text-notice-title text-text-primary hover:text-accent-soft-text', expired && 'text-text-secondary', notice.is_read ? 'font-normal' : 'font-medium')}>
            {notice.title}
          </Link>
          <button type="button" onClick={() => favorite.mutate()} disabled={favorite.isPending} aria-label={notice.is_favorite ? '取消收藏' : '收藏通知'} className="grid h-11 w-11 shrink-0 place-items-center rounded-medium text-text-muted hover:bg-surface-muted hover:text-amber-500 md:h-9 md:w-9">
            <Star className={cn('h-4 w-4', notice.is_favorite && 'fill-amber-400 text-amber-500')} />
          </button>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {level !== 'normal' && <span className={cn('font-medium text-important', level === 'high' && 'font-semibold')}>{importanceLabels[level]}</span>}
          <span className={cn('inline-flex items-center gap-1', deadlineTone)}>{deadline.tone === 'danger' && <CalendarClock className="h-3.5 w-3.5" />}{deadline.text}</span>
          {notice.status === 'updated' && <span className="text-text-muted">已更新</span>}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-text-muted">
          <span>{sourceLabel(notice)}</span>
          <span aria-hidden="true">·</span>
          <span>{categoryLabels[notice.category ?? ''] ?? '其他'}</span>
          <span aria-hidden="true">·</span>
          <span>{shortDate(notice.publish_date)}</span>
        </div>
      </div>
    </article>
  )
}
