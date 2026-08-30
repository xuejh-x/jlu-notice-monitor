import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CalendarClock, Inbox, MailOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getDashboard, getImportantNotices } from '../api/dashboard'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList, NoticeListSkeleton } from '../components/notice/NoticeList'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { loadSettings } from '../stores/settings'

function DashboardSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="正在加载">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[1, 2, 3, 4].map(item => <div key={item} className="h-28 animate-pulse rounded-large border border-border bg-surface" />)}
      </div>
      <div className="grid gap-6 xl:grid-cols-2"><NoticeListSkeleton/><NoticeListSkeleton/></div>
    </div>
  )
}

export function DashboardPage() {
  const settings = loadSettings()
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: ({ signal }) => getDashboard({ signal }) })
  const important = useQuery({
    queryKey: ['notices', 'important', settings.priorityThreshold],
    queryFn: ({ signal }) => getImportantNotices(settings.priorityThreshold, { signal }),
  })

  const hour = new Date().getHours()
  const greeting = hour < 6 ? '夜深了' : hour < 12 ? '上午好' : hour < 18 ? '下午好' : '晚上好'

  if (dashboard.isPending) return <><PageHeader title={greeting} description="正在整理最新通知与截止事项。"/><DashboardSkeleton/></>
  if (dashboard.isError) return <><PageHeader title={greeting} description="查看今天值得处理的通知。"/><ErrorState error={dashboard.error} retry={() => dashboard.refetch()}/></>

  const data = dashboard.data
  const trueEmpty = data.recent_notices.length === 0 && data.new_today === 0 && data.unread === 0 && data.urgent === 0 && data.upcoming_deadlines === 0 && important.isSuccess && important.data.length === 0
  if (trueEmpty) {
    return <><PageHeader title={greeting} description="通知概览"/><EmptyState title="尚无通知" description="当前还没有可供阅读的通知，可以先确认数据源状态。" action={<Link to="/sources" className="text-sm font-medium text-accent-soft-text hover:underline">查看数据源</Link>}/></>
  }

  const stats = [
    { label: '今日新增', value: data.new_today, icon: Inbox, tone: 'text-accent-soft-text bg-accent-soft' },
    { label: '未读通知', value: data.unread, icon: MailOpen, tone: 'text-accent-soft-text bg-accent-soft' },
    { label: '3 天内截止', value: data.urgent, icon: AlertTriangle, tone: 'text-danger bg-danger/10' },
    { label: '待办截止', value: data.upcoming_deadlines, icon: CalendarClock, tone: 'text-warning bg-warning/10' },
  ]
  const healthySources = data.source_status.filter(source => source.status === 'healthy').length
  const pausedSources = data.source_status.filter(source => source.status === 'disabled' || source.status === 'unconfigured').length
  const attentionSources = Math.max(0, data.source_status.length - healthySources - pausedSources)

  return (
    <div className="space-y-8">
      <PageHeader
        title={greeting}
        description={data.new_today ? `今天发现 ${data.new_today} 条新通知，先处理未读和临近截止事项。` : '今天暂无新增，仍可继续处理未读与临近截止事项。'}
      />

      <section aria-labelledby="dashboard-summary-heading">
        <h2 id="dashboard-summary-heading" className="sr-only">核心摘要</h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {stats.map(({ label, value, icon: Icon, tone }) => (
            <div key={label} className="rounded-large border border-border bg-surface p-4 sm:p-5">
              <div className={`mb-4 grid h-9 w-9 place-items-center rounded-medium ${tone}`}><Icon className="h-4 w-4" aria-hidden="true"/></div>
              <div className="text-2xl font-semibold tabular-nums text-text-primary">{value}</div>
              <div className="mt-1 text-metadata text-text-muted">{label}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="grid min-w-0 gap-8 xl:grid-cols-2">
        <section className="min-w-0" aria-labelledby="priority-heading">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div><h2 id="priority-heading" className="text-section-heading">优先关注</h2><p className="mt-1 text-metadata text-text-muted">达到你的优先阈值（{settings.priorityThreshold}）</p></div>
            <Link to={`/notices?min_score=${settings.priorityThreshold}`} className="inline-flex min-h-11 items-center text-sm font-medium text-accent-soft-text hover:underline md:min-h-0">查看优先通知</Link>
          </div>
          {important.isPending ? <NoticeListSkeleton/> : important.isError ? <ErrorState error={important.error} retry={() => important.refetch()}/> : <NoticeList notices={important.data.slice(0, settings.hideLowPriority ? 5 : 8)} emptyTitle="暂无优先通知" emptyDescription="当前没有达到你的优先阈值的通知。"/>}
        </section>

        <section className="min-w-0" aria-labelledby="recent-heading">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div><h2 id="recent-heading" className="text-section-heading">最近通知</h2><p className="mt-1 text-metadata text-text-muted">共 {data.unread} 条未读</p></div>
            <Link to="/notices" className="inline-flex min-h-11 items-center text-sm font-medium text-accent-soft-text hover:underline md:min-h-0">查看全部</Link>
          </div>
          <NoticeList notices={data.recent_notices.slice(0, 8)} emptyTitle="暂无最近通知" emptyDescription="数据源尚未返回最近通知。"/>
        </section>
      </div>

      <section className="flex flex-col gap-3 border-t border-border pt-5 text-sm sm:flex-row sm:items-center sm:justify-between" aria-labelledby="source-overview-heading">
        <div>
          <h2 id="source-overview-heading" className="text-section-heading">来源状态</h2>
          <p className="mt-1 text-text-secondary">
            {data.source_status.length ? `${healthySources} 个正常${pausedSources ? ` · ${pausedSources} 个暂停` : ''}${attentionSources ? ` · ${attentionSources} 个需关注` : ''}` : '当前没有配置的数据源'}
          </p>
        </div>
        <Link to="/sources" className="inline-flex min-h-11 items-center font-medium text-accent-soft-text hover:underline md:min-h-0">查看数据源</Link>
      </section>
    </div>
  )
}
