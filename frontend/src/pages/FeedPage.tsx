import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { getNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList, NoticeListSkeleton } from '../components/notice/NoticeList'
import { ErrorState } from '../components/ui/Feedback'
import { Pagination } from '../components/ui/Pagination'
import { loadSettings } from '../stores/settings'

export function FeedPage({ title, description, categories, keyword, controls }: { title: string; description: string; categories?: string[]; keyword?: string; controls?: ReactNode }) {
  const [page, setPage] = useState(1)
  const pageSize = loadSettings().pageSize
  const category = categories?.join(',')
  const query = useQuery({
    queryKey: ['notices', 'feed', category, keyword, page, pageSize],
    queryFn: ({ signal }) => getNotices({ category, q: keyword, page, page_size: pageSize }, { signal }),
    placeholderData: previous => previous,
  })
  return (
    <>
      <PageHeader title={title} description={query.isSuccess ? `${description} 共 ${query.data.total} 条。` : description}/>
      {controls}
      {query.isPending ? <NoticeListSkeleton/> : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()}/> : <>
        <NoticeList notices={query.data.items} emptyTitle={`暂无${title}相关通知`} emptyDescription="当前分类下还没有可供阅读的通知。"/>
        <Pagination page={query.data.page} totalPages={query.data.total_pages} onPageChange={setPage}/>
      </>}
    </>
  )
}
