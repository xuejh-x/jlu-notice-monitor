import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeList } from '../components/notice/NoticeList'
import { ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { Pagination } from '../components/ui/Pagination'
import { loadSettings } from '../stores/settings'

export function FeedPage({ title, description, categories, keyword }: { title: string; description: string; categories?: string[]; keyword?: string }) {
  const [page, setPage] = useState(1)
  const pageSize = loadSettings().pageSize
  const category = categories?.join(',')
  const query = useQuery({
    queryKey: ['notices', 'feed', category, keyword, page, pageSize],
    queryFn: () => getNotices({ category, q: keyword, page, page_size: pageSize }),
    placeholderData: previous => previous,
  })
  if (query.isPending) return <PageSkeleton/>
  if (query.isError) return <ErrorState message={query.error.message} retry={() => query.refetch()}/>
  return <><PageHeader title={title} description={description}/><NoticeList notices={query.data.items}/><Pagination page={query.data.page} totalPages={query.data.total_pages} onPageChange={setPage}/></>
}
