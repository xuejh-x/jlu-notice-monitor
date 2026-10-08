import { type QueryClient, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import type { CrawlerStatus } from '../types'
import { isCrawlerJobRunning } from '../components/layout/crawlerStatus'

// The shell button and Sources page observe the same query. Refresh only once
// per completion/client, including runs that finish between two status polls.
const refreshed = new WeakMap<QueryClient, string | null>()

export function captureCrawlerCompletionBaseline(client: QueryClient, status = client.getQueryData<CrawlerStatus>(['crawler'])) {
  if (!refreshed.has(client)) refreshed.set(client, status?.last_run ?? null)
}

export function useCrawlerCompletionRefresh(status?: CrawlerStatus) {
  const client = useQueryClient()
  useEffect(() => {
    if (!status) return
    const initial = !refreshed.has(client)
    captureCrawlerCompletionBaseline(client, status)
    if (isCrawlerJobRunning(status)) return
    const completed = status.last_run ?? status.startup_sync?.completed_at
    // An old persisted result at mount is a baseline, not a newly finished
    // crawl. Refreshing it can evict the user's preserved unread page.
    if (initial && !status.startup_sync?.completed_at) {
      // Health may have changed while the first status request was in flight.
      // Reconcile sources only; never evict an existing unread page for an old
      // saved result. Subsequent completions refresh all affected queries.
      if (completed) {
        for (const key of [['sources'], ['source-config']]) {
          void client.invalidateQueries({ queryKey: key })
        }
      }
      return
    }
    if (!completed || (!initial && refreshed.get(client) === completed)) return
    refreshed.set(client, completed)
    for (const key of [['dashboard'], ['notices'], ['search'], ['sources'], ['source-config']]) {
      void client.invalidateQueries({ queryKey: key })
    }
  }, [client, status])
}
