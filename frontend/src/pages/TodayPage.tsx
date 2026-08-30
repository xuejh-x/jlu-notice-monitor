import { useQuery } from '@tanstack/react-query'
import { getTodayNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList, NoticeListSkeleton } from '../components/notice/NoticeList'
import { ErrorState } from '../components/ui/Feedback'

export function TodayPage() {
  const query = useQuery({ queryKey: ['notices', 'today'], queryFn: ({ signal }) => getTodayNotices({ signal }) })
  return (
    <>
      <PageHeader title="今日新通知" description={query.isSuccess ? `今天共发现 ${query.data.length} 条新通知。` : '查看今天新增或首次发现的通知。'}/>
      {query.isPending ? <NoticeListSkeleton/> : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()}/> : <NoticeList notices={query.data} emptyTitle="今天暂无新通知" emptyDescription="当前没有今天新增或首次发现的通知。"/>}
    </>
  )
}
