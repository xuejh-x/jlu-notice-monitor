import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getCrawlerStatus, runCrawler } from '../../api/crawler'
import { useToast } from '../../stores/toast'
import { Button } from '../ui/Button'
import { crawlerStatusLabel, isCrawlerJobRunning } from './crawlerStatus'

export function CrawlerButton({ compact = false }: { compact?: boolean }) {
  const toast = useToast()
  const client = useQueryClient()
  const [tracking, setTracking] = useState(false)
  const hasRun = useRef(false)
  const baselineLastRun = useRef<string | null>(null)
  const handledStartupCompletion = useRef<string | null>(null)
  const status = useQuery({
    queryKey: ['crawler'],
    queryFn: ({ signal }) => getCrawlerStatus({ signal }),
    refetchInterval: query => {
      const value = query.state.data
      const startupPending = Boolean(value?.startup_sync?.triggered && !value.startup_sync.completed_at)
      return tracking || isCrawlerJobRunning(value) || startupPending ? 1500 : false
    },
  })
  const running = isCrawlerJobRunning(status.data)

  useEffect(() => {
    const startupPending = Boolean(
      status.data?.startup_sync?.triggered && !status.data.startup_sync.completed_at,
    )
    if ((!startupPending && !running) || tracking) return
    baselineLastRun.current = status.data?.last_run ?? null
    const timer = window.setTimeout(() => setTracking(true), 0)
    return () => window.clearTimeout(timer)
  }, [running, status.data, tracking])

  useEffect(() => {
    if (running) {
      hasRun.current = true
      return
    }
    if (!tracking || !status.data) return
    const runCompleted = hasRun.current || status.data.last_run !== baselineLastRun.current
    const startupCompleted = Boolean(status.data.startup_sync?.completed_at)
    if (!runCompleted && !startupCompleted) return
    const result = status.data
    if (result.startup_sync?.completed_at) {
      handledStartupCompletion.current = result.startup_sync.completed_at
    }
    const timer = window.setTimeout(() => {
      setTracking(false)
      hasRun.current = false
      const failed = result.source_results.filter(
        item => item.status === 'failure' || item.status === 'partial_failure',
      ).length
      toast(
        result.status === 'failure'
          ? `检查失败：${failed || result.source_results.length} 个来源异常`
          : result.status === 'partial_failure' || failed
          ? `检查完成：${failed} 个来源异常，新增 ${result.new_count} 条，更新 ${result.updated_count} 条`
          : `检查完成：新增 ${result.new_count} 条，更新 ${result.updated_count} 条`,
        result.status === 'failure' || result.status === 'partial_failure' || failed ? 'error' : undefined,
      )
      for (const key of [['dashboard'], ['notices'], ['search'], ['sources'], ['source-config']]) {
        void client.invalidateQueries({ queryKey: key })
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [client, running, status.data, toast, tracking])

  useEffect(() => {
    const completedAt = status.data?.startup_sync?.completed_at
    if (!completedAt || handledStartupCompletion.current === completedAt) return
    handledStartupCompletion.current = completedAt
    for (const key of [['dashboard'], ['notices'], ['search'], ['sources'], ['source-config']]) {
      void client.invalidateQueries({ queryKey: key })
    }
  }, [client, status.data?.startup_sync?.completed_at])

  useEffect(() => {
    if (!tracking || hasRun.current) return
    const timer = window.setTimeout(() => setTracking(false), 15_000)
    return () => window.clearTimeout(timer)
  }, [tracking])

  const run = useMutation({
    mutationFn: runCrawler,
    onSuccess: () => {
      toast('已开始检查新通知')
      baselineLastRun.current = status.data?.last_run ?? null
      hasRun.current = false
      setTracking(true)
      window.setTimeout(() => status.refetch(), 600)
    },
    onError: () => toast('启动检查失败，请稍后重试', 'error'),
  })
  const busy = run.isPending || tracking || running
  return (
    <Button
      variant={compact ? 'ghost' : 'primary'}
      size={compact ? 'sm' : 'md'}
      className={compact ? 'h-5 w-auto justify-start px-1 text-label text-text-muted' : ''}
      onClick={() => run.mutate()}
      disabled={busy}
      aria-label="检查新通知"
    >
      <RefreshCw className={`h-3 w-3 ${running ? 'animate-spin' : ''}`}/>
      <span>{run.isPending && !running ? '正在启动…' : crawlerStatusLabel(status.data)}</span>
    </Button>
  )
}
