import { CalendarDays, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Notice } from '../../types'
import { categoryLabels } from '../../utils/labels'

export function NoticeRow({ notice }: { notice: Notice }) {
  const date = notice.publish_date?.slice(0, 10) ?? '日期待定'
  return <Link to={`/notices/${notice.id}`} className="group flex min-w-0 items-center gap-3 border-b border-zinc-100 px-1 py-4 last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/50">
    <span className={`h-2 w-2 shrink-0 rounded-full ${notice.is_read ? 'bg-zinc-200 dark:bg-zinc-700' : 'bg-indigo-500'}`} />
    <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-zinc-900 group-hover:text-indigo-700 dark:text-zinc-100 dark:group-hover:text-indigo-300">{notice.title}</div>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500"><span>{notice.publisher ?? notice.sources[0]?.name ?? '来源待定'}</span><span>{categoryLabels[notice.category ?? ''] ?? '其他'}</span><span className="inline-flex items-center gap-1"><CalendarDays className="h-3 w-3" />{date}</span></div>
    </div><ChevronRight className="h-4 w-4 shrink-0 text-zinc-300 group-hover:text-indigo-500" />
  </Link>
}
