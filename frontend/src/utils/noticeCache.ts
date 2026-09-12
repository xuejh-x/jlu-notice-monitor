import type { QueryClient } from '@tanstack/react-query'
import type { DashboardData, Notice, NoticeDetail, PaginatedNotices } from '../types'

/** The single authoritative cache-invalidation set for notice read/favorite
 *  state mutations: every query entry that can display a notice's user state.
 *  - `['notice', id]`  — detail page (star, read state)
 *  - `['notices']`     — all list entries (notices/all, favorites, feeds,
 *                        competitions, deadlines, today, important)
 *  - `['dashboard']`   — dashboard metrics (unread count) and recent_notices
 *                        (rendered via NoticeCard)
 *  Both mutation sites (NoticeCard, NoticeDetailPage) must go through here so
 *  the chain 收藏 → backend → cache → Notices/Favorites/Dashboard/Detail
 *  stays consistent instead of each site invalidating its own subset.
 *
 *  Note: `['search', keyword]` result rows display the unread dot (read state
 *  only, no favorite star). Search entries are therefore invalidated by the
 *  read path (NoticeDetailPage auto-read), not by this favorite/read-common
 *  set — favorite mutations do not change anything search renders.
 */
export function invalidateNoticeState(client: QueryClient, noticeId: number): void {
  client.invalidateQueries({ queryKey: ['notice', noticeId] })
  client.invalidateQueries({ queryKey: ['notices'] })
  client.invalidateQueries({ queryKey: ['dashboard'] })
}

function markRead(notice: Notice, noticeId: number): Notice {
  return notice.id === noticeId ? { ...notice, is_read: true } : notice
}

function setRead(notice: Notice, noticeId: number, read: boolean): Notice {
  return notice.id === noticeId ? { ...notice, is_read: read } : notice
}

function isPaginatedNotices(value: unknown): value is PaginatedNotices {
  return Boolean(value && typeof value === 'object' && Array.isArray((value as PaginatedNotices).items))
}

/** Keep the list the user is reading stable after automatic read.
 *
 * Cached rows update immediately, including the selected row in an unread
 * view. The queries become stale without refetching active observers, so the
 * backend's real filtered result is applied on the next filter/view entry or
 * explicit refresh instead of removing the row under the reader's pointer.
 */
export function preserveNoticeAfterAutoRead(client: QueryClient, noticeId: number): void {
  client.setQueriesData<unknown>({ queryKey: ['notices'] }, (current: unknown) => {
    if (Array.isArray(current)) return current.map(notice => markRead(notice as Notice, noticeId))
    if (isPaginatedNotices(current)) return { ...current, items: current.items.map(notice => markRead(notice, noticeId)) }
    return current
  })
  void client.invalidateQueries({ queryKey: ['notices'], refetchType: 'none' })
}


/** Optimistically project one read-state transition into every mounted surface.
 * Global counters come from the independent dashboard query and are adjusted
 * only for a real false <-> true transition; total/important/deadline values
 * are deliberately left unchanged.
 */
export function updateNoticeReadState(
  client: QueryClient,
  noticeId: number,
  read: boolean,
  previousRead?: boolean,
): void {
  client.setQueryData<NoticeDetail>(['notice', noticeId], current => current ? { ...current, is_read: read } : current)
  for (const key of [['notices'], ['search']] as const) {
    client.setQueriesData<unknown>({ queryKey: key }, (current: unknown) => {
      if (Array.isArray(current)) return current.map(notice => setRead(notice as Notice, noticeId, read))
      if (isPaginatedNotices(current)) return { ...current, items: current.items.map(notice => setRead(notice, noticeId, read)) }
      return current
    })
  }
  client.setQueryData<DashboardData>(['dashboard'], current => {
    if (!current) return current
    const delta = previousRead === undefined || previousRead === read ? 0 : read ? -1 : 1
    return {
      ...current,
      unread: Math.max(0, current.unread + delta),
      recent_notices: current.recent_notices.map(notice => setRead(notice, noticeId, read)),
    }
  })
}
