import type { QueryClient } from '@tanstack/react-query'

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
 */
export function invalidateNoticeState(client: QueryClient, noticeId: number): void {
  client.invalidateQueries({ queryKey: ['notice', noticeId] })
  client.invalidateQueries({ queryKey: ['notices'] })
  client.invalidateQueries({ queryKey: ['dashboard'] })
}
