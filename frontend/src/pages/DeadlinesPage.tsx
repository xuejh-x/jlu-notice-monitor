import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getDeadlineNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList, NoticeListSkeleton } from '../components/notice/NoticeList'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { cn } from '../utils/cn'
import { fullDate } from '../utils/format'

const ranges = [{ label: '今天', days: 0 }, { label: '3 天内', days: 3 }, { label: '7 天内', days: 7 }, { label: '30 天内', days: 30 }]

export function DeadlinesPage() {
  const [days, setDays] = useState(30)
  const query = useQuery({ queryKey: ['notices', 'deadlines', days], queryFn: ({ signal }) => getDeadlineNotices(days, { signal }) })
  const grouped = query.data?.reduce<Record<string, typeof query.data>>((all, notice) => {
    const key = fullDate(notice.registration_deadline)
    ;(all[key] ??= []).push(notice)
    return all
  }, {}) ?? {}
  const rangeLabel = days === 365 ? '未来一年' : ranges.find(range => range.days === days)?.label ?? '当前范围'

  const controls = (
    <div className="flex max-w-full overflow-x-auto rounded-medium border border-border bg-surface p-1" aria-label="截止范围">
      <button type="button" aria-pressed={days === 365} onClick={() => setDays(365)} className={cn('min-h-11 whitespace-nowrap rounded-small px-3 text-xs md:min-h-9', days === 365 ? 'bg-accent-soft font-medium text-accent-soft-text' : 'text-text-muted hover:bg-surface-muted')}>全部</button>
      {ranges.map(range => <button key={range.days} type="button" aria-pressed={days === range.days} onClick={() => setDays(range.days)} className={cn('min-h-11 whitespace-nowrap rounded-small px-3 text-xs md:min-h-9', days === range.days ? 'bg-accent-soft font-medium text-accent-soft-text' : 'text-text-muted hover:bg-surface-muted')}>{range.label}</button>)}
    </div>
  )

  return (
    <>
      <PageHeader title="即将截止" description={query.isSuccess ? `${rangeLabel}共有 ${query.data.length} 项截止事项。` : '按截止日期安排你的下一步行动。'} actions={controls}/>
      {query.isPending ? <NoticeListSkeleton/> : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()}/> : query.data.length ? (
        <div className="space-y-7">
          {Object.entries(grouped).map(([date, notices]) => (
            <section key={date} aria-labelledby={`deadline-${date}`}>
              <h2 id={`deadline-${date}`} className="mb-2 text-section-heading text-text-primary">{date}</h2>
              <NoticeList notices={notices}/>
            </section>
          ))}
        </div>
      ) : <EmptyState title="当前范围内暂无截止事项" description="没有即将在所选时间范围内截止的通知。"/>}
    </>
  )
}
