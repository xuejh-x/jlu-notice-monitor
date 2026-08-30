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
