import type { Notice } from '../../types'
import { NoticeCard } from './NoticeCard'
import { EmptyState } from '../ui/Feedback'
import { Card } from '../ui/Card'

export function NoticeList({ notices, emptyTitle = '没有找到相关通知', emptyDescription = '可以尝试调整筛选条件。' }: { notices: Notice[]; emptyTitle?: string; emptyDescription?: string }) {
  if (!notices.length) return <EmptyState title={emptyTitle} description={emptyDescription} />
  return <Card className="px-4 sm:px-5">{notices.map(notice => <NoticeCard key={notice.id} notice={notice} />)}</Card>
}
