import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCheck, ExternalLink, Star } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getNotice, setNoticeFavorite, setNoticeRead } from '../api/notices'
import { NoticeContent } from '../components/notice/NoticeContent'
import { AttachmentRow } from '../components/notice/AttachmentRow'
import { DeadlineBadge } from '../components/notice/DeadlineBadge'
import { DetailToolbar } from '../components/notice/DetailToolbar'
import { SourceIcon } from '../components/notice/SourceIcon'
import { NoticeCategoryTag } from '../components/notice/NoticeCategoryTag'
import { Badge } from '../components/ui/Badge'
import { ErrorState } from '../components/ui/Feedback'
import { ExternalAnchor } from '../components/ui/ExternalAnchor'
import { useToast } from '../stores/toast'
import type { NoticeDetail } from '../types'
import { fullDate } from '../utils/format'
import { invalidateNoticeState, preserveNoticeAfterAutoRead, updateNoticeReadState } from '../utils/noticeCache'
import { deadlineDetail, importanceLabels, importanceLevel, sourceLabel } from '../utils/noticeMeta'
import { isSafeExternalUrl } from '../utils/url'

function DetailSkeleton() {
  return (
    <div className="detail-content-frame animate-pulse pb-6 pt-4 motion-reduce:animate-none" role="status" aria-label="正在加载">
      <h1 className="sr-only">通知详情</h1>
      <div className="flex h-detail-toolbar-height gap-2 border-b border-border"><div className="h-8 w-20 rounded bg-surface-muted" /><div className="h-8 w-24 rounded bg-surface-muted" /></div>
      <div className="mt-5 h-7 w-3/4 rounded bg-surface-muted" />
      <div className="mt-3 h-4 w-1/3 rounded bg-surface-muted" />
      <div className="mt-6 max-w-3xl space-y-4 border-t border-border pt-5">
        {[1, 2, 3, 4, 5, 6].map((i) => <div key={i} className="h-4 rounded bg-surface-muted" style={{ width: i % 3 === 0 ? '60%' : '100%' }} />)}
      </div>
    </div>
  )
}

function KeyRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 [overflow-wrap:anywhere]">
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
    <section className="min-w-0 border-t border-border pt-3" aria-labelledby="info-heading">
      <h2 id="info-heading" className="text-body font-medium">通知信息</h2>
      <dl className="mt-2 grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {supplemental.map(item => <KeyRow key={item.label} label={item.label} value={item.value} />)}
      </dl>
    </section>
  )
}

function SourcePanel({ notice, originalUrl }: { notice: NoticeDetail; originalUrl: string | null }) {
  const sources = notice.sources.length
    ? notice.sources
    : notice.url
      ? [{ code: 'original', name: notice.publisher ?? '原始来源', url: notice.url }]
      : []
  return (
    <section className="min-w-0 border-t border-border pt-3" aria-labelledby="source-heading">
      <h2 id="source-heading" className="sr-only">来源</h2>
      <div className="flex min-w-0 flex-wrap items-start gap-x-4 gap-y-1">
      {originalUrl && <ExternalAnchor href={originalUrl} className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-small text-metadata text-text-secondary hover:text-text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"><ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />打开原文链接</ExternalAnchor>}
      {sources.length ? (
        <ul className="space-y-1">
          {sources.map((source, index) => {
            const href = source.url ?? notice.url
            const safe = isSafeExternalUrl(href)
            return (
              <li key={`${source.code}-${index}`} className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 [overflow-wrap:anywhere]">
                <span className="text-metadata text-text-muted">{source.name}</span>
                {safe && (
                  <ExternalAnchor href={href} className="inline-flex min-h-8 items-center gap-1 text-metadata text-text-secondary hover:text-text-primary hover:underline">
                    查看原通知
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  </ExternalAnchor>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="text-metadata text-text-muted">未提供原始来源。</p>
      )}
      </div>
      {notice.publisher && <p className="mt-1 text-metadata text-text-muted [overflow-wrap:anywhere]">发布单位：{notice.publisher}</p>}
    </section>
  )
}

function AttachmentsSection({ notice }: { notice: NoticeDetail }) {
  if (!notice.attachments.length) return null
  return (
    <section className="min-w-0" aria-labelledby="attachments-heading">
      <h2 id="attachments-heading" className="text-body font-medium">附件 <span className="ml-1 text-label font-normal text-text-muted">{notice.attachments.length}</span></h2>
      <ul className="mt-2 space-y-2">
        {notice.attachments.map((attachment, index) => {
          return <li key={`${attachment.url}-${index}`}><AttachmentRow attachment={attachment} fallbackName={`附件 ${index + 1}`} /></li>
        })}
      </ul>
    </section>
  )
}

export function NoticeDetailPage({ embeddedId }: { embeddedId?: number }) {
  const { search } = useLocation()
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
    onMutate: async (value: boolean) => {
      // A deliberate "mark unread" must not be consumed by the automatic
      // read effect on the very next render.
      if (!value) markedIds.current.add(id)
      await Promise.all([
        client.cancelQueries({ queryKey: ['notice', id] }),
        client.cancelQueries({ queryKey: ['notices'] }),
        client.cancelQueries({ queryKey: ['dashboard'] }),
        client.cancelQueries({ queryKey: ['search'] }),
      ])
      const previousRead = client.getQueryData<NoticeDetail>(['notice', id])?.is_read
      updateNoticeReadState(client, id, value, previousRead)
      return { previousRead }
    },
    onSuccess: (_result, value) => {
      toast(value ? '已标记为已读' : '已标记为未读')
    },
    onError: (_error, _value, context) => {
      if (context?.previousRead !== undefined) {
        updateNoticeReadState(client, id, context.previousRead, !context.previousRead)
      }
      toast('阅读状态操作失败', 'error')
    },
    onSettled: () => {
      invalidateNoticeState(client, id)
      client.invalidateQueries({ queryKey: ['search'] })
    },
  })

  useEffect(() => {
    if (query.data && query.data.id === id && !query.data.is_read && !markedIds.current.has(id)) {
      markedIds.current.add(id)
      setNoticeRead(id, true)
        .then(() => {
          updateNoticeReadState(client, id, true, false)
          preserveNoticeAfterAutoRead(client, id)
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
              to={{ pathname: '/notices', search }}
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
    <div className="min-h-full min-w-0 bg-detail-surface">
      <Link to={{ pathname: '/notices', search }} className="sticky top-0 z-20 flex h-11 items-center gap-2 border-b border-border bg-detail-surface px-shell-gutter text-body text-text-secondary hover:text-text-primary md:hidden"><ArrowLeft className="h-4 w-4" aria-hidden="true" />返回通知列表</Link>
      <DetailToolbar favorite={notice.is_favorite} read={notice.is_read} originalUrl={originalUrl} busyFavorite={favorite.isPending} busyRead={readState.isPending} onFavorite={() => favorite.mutate(!notice.is_favorite)} onRead={() => readState.mutate(!notice.is_read)} />
      <div className="detail-content-frame pb-5 pt-4">
        <article className="min-w-0 [overflow-wrap:anywhere]">
        <header className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <NoticeCategoryTag category={notice.category} />
            {level !== 'normal' && <Badge variant="important" className="gap-1 border-0 bg-transparent p-0"><Star className="h-3 w-3" aria-hidden="true" />{importanceLabels[level]}</Badge>}
            {notice.status === 'updated' && <Badge className="h-5 px-1.5 py-0">已更新</Badge>}
            <span className="ml-auto inline-flex items-center gap-1 text-label text-text-muted">{notice.is_read ? <CheckCheck className="h-3 w-3" aria-hidden="true" /> : <span className="h-1.5 w-1.5 rounded-full bg-unread" aria-hidden="true" />}{notice.is_read ? '已读' : '未读'}</span>
          </div>
          <h1 className="text-page-title text-text-primary">{notice.title}</h1>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1">
          <div className="flex min-w-0 items-start gap-2 text-metadata text-text-secondary">
            <SourceIcon name={sourceLabel(notice)} metadata className="text-source-blue-fg" />
            <span className="min-w-0">{sourceLabel(notice)}</span>
          </div>
            {notice.publish_date && <time dateTime={notice.publish_date} className="text-metadata text-text-muted">发布时间：{fullDate(notice.publish_date)}</time>}
          </div>
          {deadline && <div className="flex min-w-0 items-center gap-2 pt-1"><span className="shrink-0 text-metadata text-text-muted">截止时间</span><DeadlineBadge notice={notice} detail list text={deadline.text} className="h-auto min-h-5 max-w-full py-0.5" /></div>}
        </header>

        <div className="mt-4 border-t border-border pt-4">
          <div className="min-w-0 space-y-5">
            <section aria-labelledby="body-heading">
              <h2 id="body-heading" className="sr-only">通知正文</h2>
              <div>
                <NoticeContent content={notice.content} />
              </div>
            </section>

            <StructuredInfo notice={notice} />

            <AttachmentsSection notice={notice} />

            <SourcePanel notice={notice} originalUrl={originalUrl} />
          </div>
        </div>
        </article>
      </div>
    </div>
  )
}
