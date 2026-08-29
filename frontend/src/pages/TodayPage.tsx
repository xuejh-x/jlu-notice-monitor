import { useQuery } from '@tanstack/react-query'
import { getTodayNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList } from '../components/notice/NoticeList'
import { ErrorState, PageSkeleton } from '../components/ui/Feedback'
export function TodayPage() { const q=useQuery({queryKey:['notices','today'],queryFn:getTodayNotices}); if(q.isPending)return <PageSkeleton/>; if(q.isError)return <ErrorState message={q.error.message} retry={()=>q.refetch()}/>; return <><PageHeader title="今日新通知" description={`今天共发现 ${q.data.length} 条新通知。`}/><NoticeList notices={q.data} emptyTitle="今天没有新的通知" emptyDescription="所有启用的数据源均已检查。"/></> }
