import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList, NoticeListSkeleton } from '../components/notice/NoticeList'
import { ErrorState } from '../components/ui/Feedback'
import { Pagination } from '../components/ui/Pagination'
import { loadSettings } from '../stores/settings'

export function FavoritesPage() {
  const [page, setPage] = useState(1)
  const pageSize = loadSettings().pageSize
  const query = useQuery({
    queryKey: ['notices', 'favorites', page, pageSize],
    queryFn: ({ signal }) => getNotices({ favorite: true, page, page_size: pageSize }, { signal }),
    placeholderData: previous => previous,
  })
  return (
    <>
      <PageHeader title="我的收藏" description={query.isSuccess ? `共收藏 ${query.data.total} 条通知，集中处理稍后需要回看的内容。` : '集中查看稍后需要处理的通知。'}/>
      {query.isPending ? <NoticeListSkeleton/> : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()}/> : <>
        <NoticeList
          notices={query.data.items}
          emptyTitle="还没有收藏通知"
          emptyDescription="看到值得之后处理的内容时，可以点击星标。"
          emptyAction={<Link to="/notices" className="text-sm font-medium text-accent-soft-text hover:underline">前往全部通知</Link>}
        />
        <Pagination page={query.data.page} totalPages={query.data.total_pages} onPageChange={setPage}/>
      </>}
    </>
  )
}
