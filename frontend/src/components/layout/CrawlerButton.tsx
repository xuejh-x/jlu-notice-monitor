import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getCrawlerStatus, runCrawler } from '../../api/crawler'
import { useToast } from '../../stores/toast'
import { Button } from '../ui/Button'

export function CrawlerButton({ compact = false }: { compact?: boolean }) {
  const toast = useToast()
  const client = useQueryClient()
  const [tracking, setTracking] = useState(false)
  const hasRun = useRef(false)
  const status = useQuery({
    queryKey: ['crawler'],
    queryFn: ({ signal }) => getCrawlerStatus({ signal }),
    refetchInterval: tracking ? 1500 : false,
  })
  const startupRunning = Boolean(status.data?.running && status.data.trigger_source === 'startup')

  useEffect(() => {
    if (!startupRunning || tracking) return
    const timer = window.setTimeout(() => setTracking(true), 0)
    return () => window.clearTimeout(timer)
  }, [startupRunning, tracking])

  useEffect(() => {
    if (status.data?.running) {
      hasRun.current = true
      return
    }
    if (!tracking || !hasRun.current || !status.data) return
    const result = status.data
    const timer = window.setTimeout(() => {
      setTracking(false)
      hasRun.current = false
      const failed = result.source_results.filter(item => item.status === 'failure' || item.status === 'partial_failure').length
      toast(
        failed
          ? `检查完成：${failed} 个来源异常，新增 ${result.new_count} 条，更新 ${result.updated_count} 条`
          : `检查完成：新增 ${result.new_count} 条，更新 ${result.updated_count} 条`,
        failed ? 'error' : undefined,
      )
      for (const key of [['dashboard'], ['notices'], ['search'], ['sources'], ['source-config']]) {
        void client.invalidateQueries({ queryKey: key })
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [status.data, tracking, toast, client])

  const run = useMutation({
    mutationFn: runCrawler,
    onSuccess: () => {
      toast('已开始检查新通知')
      setTracking(true)
      window.setTimeout(() => status.refetch(), 600)
    },
    onError: () => toast('启动检查失败，请稍后重试', 'error'),
  })
  const running = run.isPending || tracking || status.data?.running
  return (
    <Button
      variant={compact ? 'ghost' : 'primary'}
      size={compact ? 'sm' : 'md'}
      className={compact ? 'h-5 w-auto justify-start px-1 text-label text-text-muted' : ''}
      onClick={() => run.mutate()}
      disabled={running}
      aria-label="检查新通知"
    >
      <RefreshCw className={`h-3 w-3 ${running ? 'animate-spin' : ''}`}/>
      <span>{startupRunning ? '正在检查最新通知…' : running ? '检查中…' : '检查'}</span>
    </Button>
  )
}
