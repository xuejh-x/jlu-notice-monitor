import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CalendarClock, ExternalLink, FileText, Star } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getNotice, setNoticeFavorite, setNoticeRead } from '../api/notices'
import { NoticeContent } from '../components/notice/NoticeContent'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ErrorState } from '../components/ui/Feedback'
import { ExternalAnchor } from '../components/ui/ExternalAnchor'
import { useToast } from '../stores/toast'
import type { NoticeDetail } from '../types'
import { cn } from '../utils/cn'
import { fullDate } from '../utils/format'
import { categoryLabels } from '../utils/labels'
import { invalidateNoticeState } from '../utils/noticeCache'
import { deadlineDetail, deadlinePresentation, importanceLabels, importanceLevel } from '../utils/noticeMeta'
import { isSafeExternalUrl } from '../utils/url'

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-detail-max animate-pulse" role="status" aria-label="正在加载">
      <h1 className="sr-only">通知详情</h1>
      <div className="h-4 w-24 rounded bg-surface-muted" />
      <div className="mt-6 h-9 w-3/4 rounded bg-surface-muted" />
      <div className="mt-4 h-5 w-1/3 rounded bg-surface-muted" />
      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-4 rounded bg-surface-muted" style={{ width: i % 3 === 0 ? '60%' : '100%' }} />
          ))}
        </div>
        <div className="hidden h-72 rounded-large border border-border bg-surface lg:block" />
      </div>
    </div>
  )
}

function DecisionRow({ notice }: { notice: NoticeDetail }) {
  const level = importanceLevel(notice.importance_score)
  const deadline = deadlinePresentation(notice)
  const deadlineTone = deadline.tone === 'danger' ? 'font-medium text-danger' : deadline.tone === 'secondary' ? 'text-text-secondary' : 'text-text-muted'
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
      {level !== 'normal' && (
        <Badge variant="important" className={level === 'high' ? 'font-semibold' : undefined}>
          {importanceLabels[level]}
        </Badge>
      )}
      <span className={cn('inline-flex items-center gap-1.5 text-body', deadlineTone)}>
        {deadline.tone === 'danger' && <CalendarClock className="h-4 w-4" aria-hidden="true" />}
        {deadline.text}
      </span>
    </div>
  )
}

function KeyRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-metadata text-text-muted">{label}</dt>
      <dd className="mt-0.5 text-body text-text-primary">{value}</dd>
    </div>
  )
}

function KeyInfoPanel({ notice }: { notice: NoticeDetail }) {
  const deadline = deadlineDetail(notice)
  const deadlineTone = deadline.tone === 'danger' ? 'text-danger' : deadline.tone === 'secondary' ? 'text-text-secondary' : 'text-text-muted'
  const eventPeriod = notice.event_start
    ? `${fullDate(notice.event_start)}${notice.event_end ? ` 至 ${fullDate(notice.event_end)}` : ''}`
    : null
  const primarySource = notice.sources[0]?.name ?? notice.publisher ?? null
  return (
    <Card className="p-5">
      <h2 className="text-section-heading">关键信息</h2>
      <dl className="mt-4 space-y-4">
        <div className="flex items-start gap-2.5">
          <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
          <div>
            <dt className="text-metadata text-text-muted">报名截止</dt>
            <dd className={cn('mt-0.5 text-body font-medium', deadlineTone)}>{deadline.text}</dd>
          </div>
        </div>
        {notice.target_students && <KeyRow label="面向对象" value={notice.target_students} />}
        {notice.registration_method && <KeyRow label="报名方式" value={notice.registration_method} />}
        {notice.competition_level && <KeyRow label="竞赛级别" value={notice.competition_level} />}
        {eventPeriod && <KeyRow label="比赛时间" value={eventPeriod} />}
        {notice.publish_date && <KeyRow label="发布时间" value={fullDate(notice.publish_date)} />}
        {primarySource && <KeyRow label="来源" value={primarySource} />}
      </dl>
    </Card>
  )
}

function SourcePanel({ notice }: { notice: NoticeDetail }) {
  const sources = notice.sources.length
    ? notice.sources
    : notice.url
      ? [{ code: 'original', name: notice.publisher ?? '原始来源', url: notice.url }]
      : []
  return (
    <Card className="p-5">
      <h2 className="text-section-heading">来源</h2>
      {sources.length ? (
        <ul className="mt-4 space-y-3">
          {sources.map((source, index) => {
            const href = source.url ?? notice.url
            const safe = isSafeExternalUrl(href)
            return (
              <li key={`${source.code}-${index}`} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-body text-text-secondary">{source.name}</span>
                {safe && (
                  <ExternalAnchor href={href} className="inline-flex min-h-11 items-center gap-1 text-body font-medium text-accent-soft-text hover:underline md:min-h-0">
                    查看原通知
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  </ExternalAnchor>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="mt-3 text-body text-text-muted">未提供原始来源。</p>
      )}
      {notice.publisher && (
        <p className="mt-4 text-metadata text-text-muted">发布单位：{notice.publisher}</p>
      )}
    </Card>
  )
}

function AttachmentsSection({ notice }: { notice: NoticeDetail }) {
  if (!notice.attachments.length) return null
  return (
    <section aria-labelledby="attachments-heading">
      <h2 id="attachments-heading" className="text-section-heading">附件</h2>
      <ul className="mt-4 space-y-2">
        {notice.attachments.map((attachment, index) => {
          const name = attachment.filename ?? `附件 ${index + 1}`
          const safe = isSafeExternalUrl(attachment.url)
          const content = (
            <>
              <FileText className="h-5 w-5 shrink-0 text-text-muted" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-body text-text-primary">{name}</span>
              {attachment.type && <span className="shrink-0 text-metadata uppercase text-text-muted">{attachment.type}</span>}
              {safe && <ExternalLink className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />}
            </>
          )
          const rowClass = 'flex min-w-0 items-center gap-3 rounded-large border border-border bg-surface p-3 text-sm shadow-sm transition-colors hover:bg-surface-muted'
          return (
            <li key={`${attachment.url}-${index}`}>
              {safe ? (
                <ExternalAnchor href={attachment.url} className={rowClass}>{content}</ExternalAnchor>
              ) : (
                <span className={rowClass}>{content}</span>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function NoticeDetailPage() {
  const id = Number(useParams().id)
  const client = useQueryClient()
  const toast = useToast()
  const markedIds = useRef(new Set<number>())

  const query = useQuery({
    queryKey: ['notice', id],
    queryFn: ({ signal }) => getNotice(id, { signal }),
    enabled: Number.isFinite(id),
  })

  const favorite = useMutation({
    mutationFn: (value: boolean) => setNoticeFavorite(id, value),
    onSuccess: () => {
      invalidateNoticeState(client, id)
      toast(query.data?.is_favorite ? '已取消收藏' : '收藏成功')
    },
    onError: () => toast('收藏操作失败', 'error'),
  })

  useEffect(() => {
    if (query.data && query.data.id === id && !query.data.is_read && !markedIds.current.has(id)) {
      markedIds.current.add(id)
      setNoticeRead(id, true)
        .then(() => {
          client.invalidateQueries({ queryKey: ['notices'] })
          client.invalidateQueries({ queryKey: ['dashboard'] })
          // Search result rows display the unread dot, so cached search
          // entries must not serve a stale 未读 after auto-read.
          client.invalidateQueries({ queryKey: ['search'] })
        })
        .catch(() => undefined)
    }
  }, [query.data, id, client])

  if (query.isPending) return <DetailSkeleton />

  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.kind === 'NOT_FOUND'
    return (
      <ErrorState
        error={query.error}
        headingLevel={1}
        retry={notFound ? undefined : () => query.refetch()}
        action={
          notFound ? (
            <Link
              to="/notices"
              className="mt-4 inline-flex h-11 items-center justify-center gap-2 rounded-medium border border-transparent bg-accent px-3.5 text-sm font-medium text-text-inverse transition-colors hover:bg-accent-hover md:h-9"
            >
              返回通知列表
            </Link>
          ) : undefined
        }
      />
    )
  }

  const notice = query.data

  return (
    <div className="mx-auto max-w-detail-max">
      <Link
        to="/notices"
        className="mb-5 inline-flex min-h-11 items-center gap-2 text-body text-text-muted transition-colors hover:text-text-primary md:min-h-0"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        返回通知列表
      </Link>

      <article>
        <header>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="accent">{categoryLabels[notice.category ?? ''] ?? '其他'}</Badge>
            {notice.status === 'updated' && <Badge>已更新</Badge>}
          </div>

          <div className="mt-3 flex items-start gap-3">
            <h1 className="min-w-0 flex-1 text-page-title">{notice.title}</h1>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => favorite.mutate(!notice.is_favorite)}
              disabled={favorite.isPending}
              aria-label={notice.is_favorite ? '取消收藏' : '收藏通知'}
              className="h-11 w-11 shrink-0"
            >
              <Star className={cn('h-5 w-5', notice.is_favorite ? 'fill-amber-400 text-amber-500' : 'text-text-muted')} aria-hidden="true" />
            </Button>
          </div>

          <DecisionRow notice={notice} />
        </header>

        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start">
          <div className="min-w-0 space-y-8">
            <div className="lg:hidden">
              <KeyInfoPanel notice={notice} />
            </div>

            <section aria-labelledby="body-heading">
              <h2 id="body-heading" className="text-section-heading">通知正文</h2>
              <div className="mt-4">
                <NoticeContent content={notice.content} />
              </div>
            </section>

            <AttachmentsSection notice={notice} />

            <div className="lg:hidden">
              <SourcePanel notice={notice} />
            </div>
          </div>

          <aside className="hidden space-y-6 lg:block">
            <KeyInfoPanel notice={notice} />
            <SourcePanel notice={notice} />
          </aside>
        </div>
      </article>
    </div>
  )
}
