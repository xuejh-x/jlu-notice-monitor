import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList } from '../components/notice/NoticeList'
import { ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { Select } from '../components/ui/Form'
import { Pagination } from '../components/ui/Pagination'
import { loadSettings } from '../stores/settings'
import { cn } from '../utils/cn'

const tabs = [['全部', ''], ['算法', 'algorithm_competition'], ['网络安全', 'cybersecurity_competition'], ['创新创业', 'innovation_competition']] as const
const allCompetitions = 'algorithm_competition,cybersecurity_competition,innovation_competition'

export function CompetitionsPage() {
  const pageSize = loadSettings().pageSize
  const [category, setCategory] = useState('')
  const [source, setSource] = useState('')
  const [minScore, setMinScore] = useState('')
  const [deadlineStatus, setDeadlineStatus] = useState('')
  const [sort, setSort] = useState<'newest' | 'priority' | 'deadline'>('newest')
  const [page, setPage] = useState(1)
  const resetPage = () => setPage(1)
  const query = useQuery({
    queryKey: ['notices', 'competitions', category, source, minScore, deadlineStatus, sort, page, pageSize],
    queryFn: () => getNotices({
      category: category || allCompetitions,
      source: source || undefined,
      min_score: minScore ? Number(minScore) : undefined,
      deadline_status: deadlineStatus || undefined,
      sort,
      page,
      page_size: pageSize,
    }),
    placeholderData: previous => previous,
  })

  return <><PageHeader title="竞赛通知" description="聚合算法、网络安全与创新创业竞赛信息。"/>
    <div className="mb-4 flex gap-1 overflow-x-auto border-b border-zinc-200 dark:border-zinc-800">{tabs.map(([label, value]) => <button key={label} onClick={() => { setCategory(value); resetPage() }} className={cn('whitespace-nowrap border-b-2 px-4 py-2.5 text-sm', category === value ? 'border-indigo-600 font-medium text-indigo-700 dark:text-indigo-300' : 'border-transparent text-zinc-500')}>{label}</button>)}</div>
    <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <Select aria-label="竞赛来源" value={source} onChange={event => { setSource(event.target.value); resetPage() }}><option value="">全部来源</option><option value="cse">网络安全学院</option><option value="ccst">计算机学院</option><option value="csw">软件学院</option><option value="innovation">创新创业教育学院</option></Select>
      <Select aria-label="竞赛重要程度" value={minScore} onChange={event => { setMinScore(event.target.value); resetPage() }}><option value="">不限重要程度</option><option value="70">优先级 70 以上</option><option value="80">优先级 80 以上</option></Select>
      <Select aria-label="竞赛截止状态" value={deadlineStatus} onChange={event => { setDeadlineStatus(event.target.value); resetPage() }}><option value="">全部截止状态</option><option value="today">今天截止</option><option value="urgent">3 天内截止</option><option value="normal">稍后截止</option><option value="expired">已截止</option><option value="unknown">时间待定</option></Select>
      <Select aria-label="竞赛排序" value={sort} onChange={event => { setSort(event.target.value as typeof sort); resetPage() }}><option value="newest">最新发布</option><option value="priority">重要程度</option><option value="deadline">截止日期</option></Select>
    </div>
    {query.isPending ? <PageSkeleton/> : query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()}/> : <><NoticeList notices={query.data.items}/><Pagination page={query.data.page} totalPages={query.data.total_pages} onPageChange={setPage}/></>}
  </>
}
