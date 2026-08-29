import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { setNoticeFavorite } from '../../api/notices'
import type { Notice } from '../../types'
import { categoryLabels } from '../../utils/labels'
import { shortDate } from '../../utils/format'
import { useToast } from '../../stores/toast'
import { Badge } from '../ui/Badge'
import { cn } from '../../utils/cn'

export function NoticeCard({ notice }: { notice: Notice }) {
  const queryClient = useQueryClient(); const toast = useToast()
  const favorite = useMutation({ mutationFn: () => setNoticeFavorite(notice.id, !notice.is_favorite), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['notices'] }); queryClient.invalidateQueries({ queryKey: ['dashboard'] }); toast(notice.is_favorite ? '已取消收藏' : '收藏成功') }, onError: () => toast('收藏操作失败，请稍后重试', 'error') })
  const urgent = notice.days_until_deadline !== null && notice.days_until_deadline >= 0 && notice.days_until_deadline <= 3
  return <article className={cn('group relative border-b border-zinc-100 px-1 py-4 last:border-0 dark:border-zinc-800', notice.deadline_status === 'expired' && 'opacity-60')}>
    <div className="flex gap-3"><span className={cn('mt-2 h-2 w-2 shrink-0 rounded-full', notice.is_read ? 'bg-zinc-200 dark:bg-zinc-700' : 'bg-indigo-500')} />
      <div className="min-w-0 flex-1 pr-10"><div className="mb-1.5 flex flex-wrap items-center gap-1.5"><Badge className="border-transparent bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">{categoryLabels[notice.category ?? ''] ?? '其他'}</Badge>{urgent && <Badge className="border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">紧急</Badge>}{notice.status === 'updated' && <Badge>已更新</Badge>}</div>
        <Link to={`/notices/${notice.id}`} className="block text-[15px] font-medium leading-6 text-zinc-900 hover:text-indigo-700 dark:text-zinc-100 dark:hover:text-indigo-300">{notice.title}</Link>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500"><span>{notice.sources[0]?.name ?? notice.publisher ?? '来源待定'}</span><span>发布 {shortDate(notice.publish_date)}</span>{notice.registration_deadline && <span className={cn('inline-flex items-center gap-1', urgent && 'font-medium text-rose-600 dark:text-rose-400')}><CalendarClock className="h-3.5 w-3.5" />截止 {shortDate(notice.registration_deadline)}{notice.days_until_deadline !== null && ` · 剩余 ${Math.max(0, notice.days_until_deadline)} 天`}</span>}<span>优先级 {notice.importance_score}</span></div>
      </div><button type="button" onClick={() => favorite.mutate()} disabled={favorite.isPending} aria-label={notice.is_favorite ? '取消收藏' : '收藏通知'} className="absolute right-1 top-4 grid h-9 w-9 place-items-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-amber-500 dark:hover:bg-zinc-800"><Star className={cn('h-4 w-4', notice.is_favorite && 'fill-amber-400 text-amber-500')} /></button>
    </div>
  </article>
}
