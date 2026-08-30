import { CalendarDays, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Notice } from '../../types'
import { categoryLabels } from '../../utils/labels'
import { sourceLabel } from '../../utils/noticeMeta'

export function NoticeRow({ notice }: { notice: Notice }) {
  const date = notice.publish_date?.slice(0, 10) ?? '日期待定'
  return <Link to={`/notices/${notice.id}`} className="group flex min-w-0 items-center gap-3 border-b border-border px-1 py-4 last:border-0 hover:bg-surface-muted">
    <span className={`h-2 w-2 shrink-0 rounded-full ${notice.is_read ? 'bg-border' : 'bg-unread'}`} aria-hidden="true" />
    <span className="sr-only">{notice.is_read ? '已读' : '未读'}</span>
    <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-text-primary group-hover:text-accent-soft-text">{notice.title}</div>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-metadata text-text-muted"><span>{sourceLabel(notice)}</span><span>{categoryLabels[notice.category ?? ''] ?? '其他'}</span><span className="inline-flex items-center gap-1"><CalendarDays className="h-3 w-3" aria-hidden="true" />{date}</span></div>
    </div><ChevronRight className="h-4 w-4 shrink-0 text-text-muted group-hover:text-accent-soft-text" aria-hidden="true" />
  </Link>
}
