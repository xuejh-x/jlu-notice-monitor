import { CircleCheck, Ellipsis, ExternalLink, Star } from 'lucide-react'
import { cn } from '../../utils/cn'
import { ExternalAnchor } from '../ui/ExternalAnchor'

const actionClass = 'inline-flex h-detail-toolbar-height items-center gap-2 px-2 text-xs font-medium text-text-secondary transition-colors hover:text-text-primary disabled:pointer-events-none disabled:opacity-50'

export function DetailToolbar({ favorite, read, originalUrl, busyFavorite, busyRead, onFavorite, onRead }: { favorite: boolean; read: boolean; originalUrl: string | null; busyFavorite: boolean; busyRead: boolean; onFavorite: () => void; onRead: () => void }) {
  return <div className="flex h-detail-toolbar-height items-center justify-start gap-1 border-b border-border/70 px-3" role="toolbar" aria-label="通知操作">
    <button type="button" className={actionClass} onClick={onFavorite} disabled={busyFavorite} aria-label={favorite ? '取消收藏' : '收藏通知'}><Star className={cn('h-4 w-4 text-accent-soft-text', favorite && 'fill-accent-soft-text')} aria-hidden="true" /><span>{favorite ? '取消收藏' : '收藏'}</span></button>
    <button type="button" className={actionClass} onClick={onRead} disabled={busyRead} aria-label={read ? '标记为未读' : '标记为已读'}><CircleCheck className="h-4 w-4 text-accent-soft-text" aria-hidden="true" /><span>{read ? '标记未读' : '标记已读'}</span></button>
    {originalUrl && <ExternalAnchor href={originalUrl} className={actionClass}><ExternalLink className="h-4 w-4" aria-hidden="true" />打开原文</ExternalAnchor>}
    <button type="button" disabled title="更多操作将在后续阶段接入" className="grid h-9 w-8 place-items-center text-text-muted disabled:opacity-60" aria-label="更多操作"><Ellipsis className="h-4 w-4" aria-hidden="true" /></button>
  </div>
}
