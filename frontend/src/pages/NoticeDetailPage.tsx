import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getNotice, setNoticeFavorite, setNoticeRead } from '../api/notices'
import { NoticeContent } from '../components/notice/NoticeContent'
import { AttachmentRow } from '../components/notice/AttachmentRow'
import { DeadlineBadge } from '../components/notice/DeadlineBadge'
import { DetailToolbar } from '../components/notice/DetailToolbar'
import { SourceIcon } from '../components/notice/SourceIcon'
import { Badge } from '../components/ui/Badge'
import { ErrorState } from '../components/ui/Feedback'
import { ExternalAnchor } from '../components/ui/ExternalAnchor'
import { useToast } from '../stores/toast'
import type { NoticeDetail } from '../types'
import { fullDate } from '../utils/format'
import { categoryLabels } from '../utils/labels'
import { invalidateNoticeState } from '../utils/noticeCache'
import { deadlineDetail, importanceLabels, importanceLevel, sourceLabel } from '../utils/noticeMeta'
import { isSafeExternalUrl } from '../utils/url'

function DetailSkeleton() {
  return (
    <div className="mx-auto w-full max-w-reader animate-pulse px-4 pb-6 pt-4 sm:px-5 md:px-[30px] md:pt-[18px]" role="status" aria-label="正在加载">
      <h1 className="sr-only">通知详情</h1>
      <div className="flex gap-2 border-b border-border pb-3"><div className="h-8 w-20 rounded bg-surface-muted" /><div className="h-8 w-24 rounded bg-surface-muted" /></div>
      <div className="mt-5 h-7 w-3/4 rounded bg-surface-muted" />
      <div className="mt-3 h-4 w-1/3 rounded bg-surface-muted" />
      <div className="mt-6 max-w-3xl space-y-4 border-t border-border pt-5">
        {[1, 2, 3, 4, 5, 6].map((i) => <div key={i} className="h-4 rounded bg-surface-muted" style={{ width: i % 3 === 0 ? '60%' : '100%' }} />)}
      </div>
    </div>
  )
}

function detailCategoryVariant(category: string | null): 'accent' | 'success' | 'warning' | 'neutral' {
  if (category === 'research' || category === 'innovation_competition') return 'success'
  if (category === 'training' || category === 'internship') return 'warning'
  if (category && category !== 'other') return 'accent'
  return 'neutral'
}

function KeyRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-metadata text-text-muted">{label}</dt>
      <dd className="mt-0.5 text-body text-text-primary">{value}</dd>
    </div>
  )
}

function StructuredInfo({ notice }: { notice: NoticeDetail }) {
  const eventPeriod = notice.event_start
    ? `${fullDate(notice.event_start)}${notice.event_end ? ` 至 ${fullDate(notice.event_end)}` : ''}`
    : null
  const supplemental = [
    notice.target_students ? { label: '面向对象', value: notice.target_students } : null,
    notice.registration_method ? { label: '报名方式', value: notice.registration_method } : null,
    notice.competition_level ? { label: '竞赛级别', value: notice.competition_level } : null,
    eventPeriod ? { label: '活动时间', value: eventPeriod } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item))
  if (!supplemental.length) return null
  return (
    <section className="max-w-reader border-y border-border py-4" aria-labelledby="info-heading">
      <h2 id="info-heading" className="text-section-heading">通知信息</h2>
      <dl className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {supplemental.map(item => <KeyRow key={item.label} label={item.label} value={item.value} />)}
      </dl>
    </section>
  )
}

function SourcePanel({ notice }: { notice: NoticeDetail }) {
  const sources = notice.sources.length
    ? notice.sources
    : notice.url
      ? [{ code: 'original', name: notice.publisher ?? '原始来源', url: notice.url }]
      : []
  return (
    <section className="max-w-reader border-t border-border pt-4" aria-labelledby="source-heading">
      <h2 id="source-heading" className="text-section-heading">来源</h2>
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
      {notice.publisher && <p className="mt-3 text-metadata text-text-muted">发布单位：{notice.publisher}</p>}
    </section>
  )
}

function AttachmentsSection({ notice }: { notice: NoticeDetail }) {
  if (!notice.attachments.length) return null
  return (
    <section className="max-w-reader" aria-labelledby="attachments-heading">
      <h2 id="attachments-heading" className="text-section-heading">附件（{notice.attachments.length}）</h2>
      <ul className="mt-3 space-y-1.5">
        {notice.attachments.map((attachment, index) => {
          return <li key={`${attachment.url}-${index}`}><AttachmentRow attachment={attachment} fallbackName={`附件 ${index + 1}`} /></li>
        })}
      </ul>
    </section>
  )
}

export function NoticeDetailPage({ embeddedId }: { embeddedId?: number }) {
  const routeId = Number(useParams().id)
  const id = embeddedId ?? routeId
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

  const readState = useMutation({
    mutationFn: (value: boolean) => setNoticeRead(id, value),
    onSuccess: (_result, value) => {
      client.setQueryData<NoticeDetail>(['notice', id], current => current ? { ...current, is_read: value } : current)
      client.invalidateQueries({ queryKey: ['notices'] })
      client.invalidateQueries({ queryKey: ['dashboard'] })
      client.invalidateQueries({ queryKey: ['search'] })
      toast(value ? '已标记为已读' : '已标记为未读')
    },
    onError: () => toast('阅读状态操作失败', 'error'),
  })

  useEffect(() => {
    if (query.data && query.data.id === id && !query.data.is_read && !markedIds.current.has(id)) {
      markedIds.current.add(id)
      setNoticeRead(id, true)
        .then(() => {
          client.setQueryData<NoticeDetail>(['notice', id], current => current ? { ...current, is_read: true } : current)
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
  const originalUrl = isSafeExternalUrl(notice.url) ? notice.url : null
  const level = importanceLevel(notice.importance_score)
  const deadline = notice.registration_deadline ? deadlineDetail(notice) : null

  return (
    <div className="min-h-full bg-detail-surface">
      <DetailToolbar favorite={notice.is_favorite} read={notice.is_read} originalUrl={originalUrl} busyFavorite={favorite.isPending} busyRead={readState.isPending} onFavorite={() => favorite.mutate(!notice.is_favorite)} onRead={() => readState.mutate(!notice.is_read)} />
      <div className="mx-auto w-full max-w-reader px-4 pb-6 pt-4 sm:px-5 md:px-[30px] md:pt-[18px]">
        <Link to="/notices" className="mb-4 inline-flex min-h-11 items-center gap-2 text-body text-text-muted transition-colors hover:text-text-primary md:hidden"><ArrowLeft className="h-4 w-4" aria-hidden="true" />返回通知列表</Link>
        <article>
        <header>
          <h1 className="text-page-title font-semibold leading-8 text-text-primary">{notice.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-2 text-metadata text-text-muted">
            <SourceIcon name={sourceLabel(notice)} metadata />
            <span className="font-medium text-text-secondary">{sourceLabel(notice)}</span>
            {notice.publish_date && <span>发布时间：{fullDate(notice.publish_date)}</span>}
            <span className="min-w-2 flex-1" />
            {deadline && <DeadlineBadge notice={notice} detail text={deadline.text} />}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <Badge variant={detailCategoryVariant(notice.category)} className="h-[25px] px-2.5 py-0">{categoryLabels[notice.category ?? ''] ?? '其他'}</Badge>
            {level !== 'normal' && <Badge variant="important" className={level === 'high' ? 'font-semibold' : undefined}>{importanceLabels[level]}</Badge>}
            {notice.status === 'updated' && <Badge>已更新</Badge>}
          </div>
        </header>

        <div className="mt-3.5 grid gap-5 border-t border-border/70 pt-3.5">
          <div className="min-w-0 space-y-5">
            <section aria-labelledby="body-heading">
              <h2 id="body-heading" className="text-section-heading">通知正文</h2>
              <div className="mt-3">
                <NoticeContent content={notice.content} />
              </div>
            </section>

            <StructuredInfo notice={notice} />

            <AttachmentsSection notice={notice} />

            {originalUrl && (
              <ExternalAnchor href={originalUrl} className="flex h-cta-height w-full items-center justify-center gap-2 rounded-design bg-cta-surface px-4 text-sm font-medium text-text-inverse transition-colors hover:brightness-110">
                打开原文链接
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </ExternalAnchor>
            )}

            <SourcePanel notice={notice} />
          </div>
        </div>
        </article>
      </div>
    </div>
  )
}
