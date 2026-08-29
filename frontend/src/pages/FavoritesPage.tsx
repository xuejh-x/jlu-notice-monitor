import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList } from '../components/notice/NoticeList'
import { ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { Pagination } from '../components/ui/Pagination'
import { loadSettings } from '../stores/settings'

export function FavoritesPage() {
  const [page, setPage] = useState(1)
  const pageSize = loadSettings().pageSize
  const query = useQuery({
    queryKey: ['notices', 'favorites', page, pageSize],
    queryFn: () => getNotices({ favorite: true, page, page_size: pageSize }),
    placeholderData: previous => previous,
  })
  if (query.isPending) return <PageSkeleton/>
  if (query.isError) return <ErrorState message={query.error.message} retry={() => query.refetch()}/>
  return <><PageHeader title="我的收藏" description="集中查看稍后需要处理的通知。"/><NoticeList notices={query.data.items} emptyTitle="还没有收藏通知" emptyDescription="看到值得之后处理的内容时，可以点击星标。"/><Pagination page={query.data.page} totalPages={query.data.total_pages} onPageChange={setPage}/></>
}
