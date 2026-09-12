import { CircleCheck, ExternalLink, Mail, Star } from 'lucide-react'
import { cn } from '../../utils/cn'
import { ExternalAnchor } from '../ui/ExternalAnchor'

const actionClass = 'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-small px-2 ring-1 ring-inset ring-transparent text-metadata text-text-secondary transition-colors hover:ring-border-strong hover:bg-surface-hover hover:text-text-primary active:bg-selected-surface aria-pressed:ring-accent-soft-text/30 aria-pressed:bg-selected-surface aria-pressed:text-accent-soft-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:pointer-events-none disabled:opacity-50'

export function DetailToolbar({ favorite, read, originalUrl, busyFavorite, busyRead, onFavorite, onRead }: { favorite: boolean; read: boolean; originalUrl: string | null; busyFavorite: boolean; busyRead: boolean; onFavorite: () => void; onRead: () => void }) {
  return <div className="sticky top-11 z-10 border-b border-border bg-detail-surface md:top-0" role="toolbar" aria-label="通知操作">
    <div className="detail-content-frame">
    <div className="-mx-2 flex h-detail-toolbar-height items-center gap-1.5">
    <button type="button" className={actionClass} onClick={onFavorite} disabled={busyFavorite} aria-pressed={favorite} aria-label={favorite ? '取消收藏' : '收藏通知'}><Star className={cn('h-3.5 w-3.5 text-text-muted', favorite && 'fill-accent-soft-text text-accent-soft-text')} aria-hidden="true" /><span className="text-metadata">{favorite ? '已收藏' : '收藏'}</span></button>
    <button type="button" className={actionClass} onClick={onRead} disabled={busyRead} aria-label={read ? '标记为未读' : '标记为已读'}>{read ? <Mail className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" /> : <CircleCheck className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" />}<span className="text-metadata">{read ? '标记未读' : '标记已读'}</span></button>
    {originalUrl && <ExternalAnchor href={originalUrl} className={cn(actionClass, 'ml-auto')}><ExternalLink className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" />打开原文</ExternalAnchor>}
    </div>
    </div>
  </div>
}
