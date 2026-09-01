import type { ReactNode } from 'react'
import type { Notice } from '../../types'
import { NoticeCard } from './NoticeCard'
import { EmptyState } from '../ui/Feedback'
import { Card } from '../ui/Card'

interface NoticeListProps {
  notices: Notice[]
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  selectedId?: number | null
  onSelect?: (id: number) => void
  compact?: boolean
}

export function NoticeList({ notices, emptyTitle = '没有找到相关通知', emptyDescription = '可以尝试调整筛选条件。', emptyAction, selectedId, onSelect, compact = false }: NoticeListProps) {
  if (!notices.length) return <div className={compact ? 'p-3' : undefined}><EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} compact={compact} /></div>
  if (compact) return <div className="bg-list-surface pt-1.5">{notices.map(notice => <NoticeCard key={notice.id} notice={notice} selected={selectedId === notice.id} onSelect={onSelect} compact />)}</div>
  return <Card className="px-4 sm:px-5">{notices.map(notice => <NoticeCard key={notice.id} notice={notice} />)}</Card>
}

export function NoticeListSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? 'bg-list-surface px-3' : 'rounded-large border border-border bg-surface px-4 sm:px-5'} role="status" aria-label="正在加载">
      {[1, 2, 3, 4, 5].map(i => (
        <div key={i} className={compact ? 'flex h-notice-row-height gap-3 border-b border-border/20 py-3 last:border-0' : 'flex gap-3 border-b border-border py-4 last:border-0'}>
          <span className="mt-2 h-2 w-2 shrink-0 animate-pulse rounded-full bg-surface-muted" />
          <div className="min-w-0 flex-1 space-y-2 animate-pulse"><div className="h-4 w-2/3 rounded bg-surface-muted" /><div className="h-3 w-1/2 rounded bg-surface-muted" /><div className="h-3 w-1/3 rounded bg-surface-muted" /></div>
        </div>
      ))}
    </div>
  )
}
