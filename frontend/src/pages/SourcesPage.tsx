import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, CircleOff, ExternalLink, TriangleAlert } from 'lucide-react'
import { getSources } from '../api/sources'
import { PageHeader } from '../components/layout/PageHeader'
import { Badge, type BadgeVariant } from '../components/ui/Badge'
import { EmptyState, ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { ExternalAnchor } from '../components/ui/ExternalAnchor'
import type { Source } from '../types'
import { relativeTime } from '../utils/format'
import { sourceStatusLabels } from '../utils/labels'
import { isSafeExternalUrl } from '../utils/url'

function sourcePresentation(source: Source): { variant: BadgeVariant; icon: typeof CheckCircle2 } {
  if (source.status === 'healthy') return { variant: 'success', icon: CheckCircle2 }
  if (source.status === 'disabled' || source.status === 'unconfigured') return { variant: 'neutral', icon: CircleOff }
  return { variant: source.status === 'login_required' ? 'warning' : 'danger', icon: TriangleAlert }
}
function SourceRow({ source }: { source: Source }) {
  const presentation = sourcePresentation(source)
  const StatusIcon = presentation.icon
  const paused = source.status === 'disabled' || source.status === 'unconfigured'
  const safeUrl = isSafeExternalUrl(source.base_url)

  return (
    <article className="border-b border-border px-4 py-5 last:border-0 sm:px-5">
      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(180px,1.2fr)_minmax(260px,1fr)_auto] lg:items-start">
        <div className="min-w-0">
          <h2 className="text-section-heading text-text-primary">{source.name}</h2>
          <p className="mt-1 text-metadata text-text-muted">{source.code} · {source.enabled ? '已启用' : '未启用'}</p>
          {safeUrl ? (
            <ExternalAnchor href={source.base_url} className="mt-2 inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-accent-soft-text hover:underline md:min-h-9">
              访问来源网站
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true"/>
              <span className="sr-only">（在新窗口打开）</span>
            </ExternalAnchor>
          ) : <p className="mt-2 text-metadata text-text-muted">来源网站地址不可用</p>}
        </div>

        <dl className="grid grid-cols-2 gap-x-5 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3">
          <div><dt className="text-metadata text-text-muted">最近检查</dt><dd className="mt-1 text-text-secondary">{relativeTime(source.last_checked_at)}</dd></div>
          <div><dt className="text-metadata text-text-muted">最近成功</dt><dd className="mt-1 text-text-secondary">{relativeTime(source.last_success_at)}</dd></div>
          <div><dt className="text-metadata text-text-muted">收录通知</dt><dd className="mt-1 tabular-nums text-text-secondary">{source.notice_count}</dd></div>
        </dl>

        <Badge variant={presentation.variant} className="w-fit">
          <StatusIcon className="mr-1 h-3 w-3" aria-hidden="true"/>
          {sourceStatusLabels[source.status] ?? source.status}
        </Badge>
      </div>

      {source.message && <p className="mt-4 rounded-medium bg-surface-muted px-3 py-2 text-sm leading-5 text-text-secondary">{source.message}</p>}
      {!paused && source.last_error && source.last_error !== source.message && <p className="mt-3 flex gap-2 text-sm text-danger"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true"/><span>{source.last_error}</span></p>}
    </article>
  )
}

export function SourcesPage() {
  const sources = useQuery({ queryKey: ['sources'], queryFn: ({ signal }) => getSources({ signal }) })
  return (
    <>
      <PageHeader title="数据源" description={sources.isSuccess ? `当前监控 ${sources.data.length} 个通知来源，状态为只读概览。` : '查看当前监控来源、启用状态与最近获取情况。'}/>
      {sources.isPending ? <PageSkeleton/> : sources.isError ? <ErrorState error={sources.error} retry={() => sources.refetch()}/> : sources.data.length ? (
        <div className="rounded-large border border-border bg-surface">{sources.data.map(source => <SourceRow key={source.code} source={source}/>)}</div>
      ) : <EmptyState title="当前没有配置的数据源" description="后端尚未返回任何可供查看的通知来源。"/>}
    </>
  )
}
