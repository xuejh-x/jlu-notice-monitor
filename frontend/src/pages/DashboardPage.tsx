import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CalendarClock, CircleAlert, Inbox, RefreshCw } from 'lucide-react'
import { getDashboard, getImportantNotices } from '../api/dashboard'
import { NoticeRow } from '../components/notice/NoticeRow'
import { loadSettings } from '../stores/settings'

function Skeleton() { return <div className="space-y-4">{[1,2,3,4].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-zinc-200/70 dark:bg-zinc-800" />)}</div> }

export function DashboardPage() {
  const settings = loadSettings()
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const important = useQuery({ queryKey: ['notices', 'important', settings.priorityThreshold], queryFn: () => getImportantNotices(settings.priorityThreshold) })
  if (dashboard.isPending) return <Skeleton />
  if (dashboard.isError) return <section className="grid min-h-[55vh] place-items-center"><div className="max-w-md text-center"><CircleAlert className="mx-auto mb-3 h-10 w-10 text-rose-500" /><h1 className="text-xl font-semibold">暂时无法读取通知</h1><p className="mt-2 text-sm text-zinc-500">{dashboard.error.message}</p><button onClick={() => dashboard.refetch()} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"><RefreshCw className="h-4 w-4" />重新连接</button></div></section>
  const data = dashboard.data
  const stats = [{ label: '今日新增', value: data.new_today, icon: Inbox, tone: 'bg-blue-50 text-blue-700' }, { label: '紧急截止', value: data.urgent, icon: AlertTriangle, tone: 'bg-rose-50 text-rose-700' }, { label: '重要通知', value: data.important, icon: CircleAlert, tone: 'bg-amber-50 text-amber-700' }, { label: '待办截止', value: data.upcoming_deadlines, icon: CalendarClock, tone: 'bg-indigo-50 text-indigo-700' }]
  const hour = new Date().getHours(); const greeting = hour < 6 ? '夜深了' : hour < 12 ? '上午好' : hour < 18 ? '下午好' : '晚上好'
  return <div className="space-y-6"><div><h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{greeting}</h1><p className="mt-2 text-sm text-zinc-500">{data.new_today ? `今天发现 ${data.new_today} 条新通知，其中 ${data.important} 条值得优先关注。` : '今天暂时没有新的高相关通知。'}</p></div>
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">{stats.map(({ label, value, icon: Icon, tone }) => <div key={label} className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-5"><div className={`mb-4 grid h-9 w-9 place-items-center rounded-lg ${tone} dark:bg-zinc-800`}><Icon className="h-4 w-4" /></div><div className="text-2xl font-semibold tabular-nums text-zinc-950 dark:text-zinc-100">{value}</div><div className="mt-1 text-xs text-zinc-500">{label}</div></div>)}</section>
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)]"><section className="min-w-0 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-5"><div className="mb-2 flex items-center justify-between"><div><h2 className="font-semibold">最新通知</h2><p className="mt-1 text-xs text-zinc-500">共 {data.unread} 条未读</p></div><a href="/notices" className="text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400">查看全部</a></div>{data.recent_notices.length ? data.recent_notices.map((notice) => <NoticeRow key={notice.id} notice={notice} />) : <div className="py-16 text-center text-sm text-zinc-400">暂无最新通知</div>}</section>
      <section className="min-w-0 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-5"><div className="mb-2"><h2 className="font-semibold">优先关注</h2><p className="mt-1 text-xs text-zinc-500">优先级 {settings.priorityThreshold} 以上</p></div>{important.isPending ? <Skeleton /> : important.data?.length ? important.data.slice(0, settings.hideLowPriority ? 5 : 8).map((notice) => <NoticeRow key={notice.id} notice={notice} />) : <div className="py-16 text-center text-sm text-zinc-400">暂无重要通知</div>}</section></div>
  </div>
}
