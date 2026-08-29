import { useQuery } from '@tanstack/react-query'
import { SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { getNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList } from '../components/notice/NoticeList'
import { ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { Input, Select } from '../components/ui/Form'
import { Pagination } from '../components/ui/Pagination'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { loadSettings } from '../stores/settings'

export function NoticesPage() {
  const pageSize = loadSettings().pageSize
  const [keyword, setKeyword] = useState('')
  const [category, setCategory] = useState('')
  const [source, setSource] = useState('')
  const [minScore, setMinScore] = useState('')
  const [deadlineStatus, setDeadlineStatus] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [read, setRead] = useState('')
  const [favorite, setFavorite] = useState('')
  const [page, setPage] = useState(1)
  const debouncedKeyword = useDebouncedValue(keyword.trim())

  const query = useQuery({
    queryKey: ['notices', 'all', debouncedKeyword, category, source, minScore, deadlineStatus, dateFrom, read, favorite, page, pageSize],
    queryFn: () => getNotices({
      q: debouncedKeyword || undefined,
      category: category || undefined,
      source: source || undefined,
      min_score: minScore ? Number(minScore) : undefined,
      deadline_status: deadlineStatus || undefined,
      date_from: dateFrom || undefined,
      read: read ? read === 'read' : undefined,
      favorite: favorite ? favorite === 'favorite' : undefined,
      page,
      page_size: pageSize,
    }),
    placeholderData: previous => previous,
  })
  const resetPage = () => setPage(1)

  return <><PageHeader title="全部通知" description="筛选和浏览已收录的所有通知。"/>
    <section className="mb-4 grid gap-2 rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900 sm:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-8">
      <Input aria-label="搜索通知" placeholder="搜索标题或正文" value={keyword} onChange={event => { setKeyword(event.target.value); resetPage() }}/>
      <Select aria-label="分类" value={category} onChange={event => { setCategory(event.target.value); resetPage() }}><option value="">全部分类</option><option value="algorithm_competition">算法竞赛</option><option value="cybersecurity_competition">网络安全</option><option value="innovation_competition">创新创业</option><option value="training">实训</option><option value="internship">实习</option><option value="research">科研</option><option value="postgraduate_recommendation">推免</option><option value="academic">教学</option></Select>
      <Select aria-label="来源" value={source} onChange={event => { setSource(event.target.value); resetPage() }}><option value="">全部来源</option><option value="cse">网络安全学院</option><option value="ccst">计算机学院</option><option value="csw">软件学院</option><option value="jwc">本科生院</option><option value="innovation">创新创业教育学院</option><option value="oa">吉林大学 OA</option></Select>
      <Select aria-label="最低优先级" value={minScore} onChange={event => { setMinScore(event.target.value); resetPage() }}><option value="">不限优先级</option><option value="70">70 以上</option><option value="80">80 以上</option><option value="90">90 以上</option></Select>
      <Input aria-label="起始日期" type="date" value={dateFrom} onChange={event => { setDateFrom(event.target.value); resetPage() }}/>
      <Select aria-label="截止状态" value={deadlineStatus} onChange={event => { setDeadlineStatus(event.target.value); resetPage() }}><option value="">全部截止状态</option><option value="today">今天截止</option><option value="urgent">3 天内截止</option><option value="normal">稍后截止</option><option value="expired">已截止</option><option value="unknown">时间待定</option></Select>
      <Select aria-label="阅读状态" value={read} onChange={event => { setRead(event.target.value); resetPage() }}><option value="">全部阅读状态</option><option value="unread">未读</option><option value="read">已读</option></Select>
      <Select aria-label="收藏状态" value={favorite} onChange={event => { setFavorite(event.target.value); resetPage() }}><option value="">全部收藏状态</option><option value="favorite">已收藏</option><option value="normal">未收藏</option></Select>
    </section>
    {query.isPending ? <PageSkeleton/> : query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()}/> : <>
      <div className="mb-3 flex items-center justify-between text-xs text-zinc-500"><span>找到 {query.data.total} 条通知</span><span className="inline-flex items-center gap-1"><SlidersHorizontal className="h-3.5 w-3.5"/>服务端筛选 · 第 {query.data.page} 页</span></div>
      <NoticeList notices={query.data.items}/>
      <Pagination page={query.data.page} totalPages={query.data.total_pages} onPageChange={setPage}/>
    </>}
  </>
}
