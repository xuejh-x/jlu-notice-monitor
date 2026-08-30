import { CircleAlert, Inbox } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '../../api/client'
import { Button } from './Button'

export function PageSkeleton() { return <div className="space-y-4" role="status" aria-label="正在加载">{[1,2,3,4,5].map(i => <div key={i} className="h-24 animate-pulse rounded-large border border-border bg-surface" />)}</div> }
export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) { return <div className="grid min-h-64 place-items-center rounded-large border border-dashed border-border bg-surface px-6 text-center"><div><Inbox className="mx-auto h-8 w-8 text-text-muted" /><h2 className="mt-3 font-semibold">{title}</h2><p className="mt-1 max-w-sm text-sm text-text-secondary">{description}</p>{action && <div className="mt-4">{action}</div>}</div></div> }
export function ErrorState({ error, message, retry, action, headingLevel = 2 }: { error?: unknown; message?: string; retry?: () => void; action?: ReactNode; headingLevel?: 1 | 2 }) {
  const apiError = error instanceof ApiError ? error : null
  if (apiError?.kind === 'ABORTED') return null
  const Heading = headingLevel === 1 ? 'h1' : 'h2'
  const copy = apiError?.kind === 'NOT_FOUND' ? { title: '通知不存在', description: '该通知可能已被删除或链接无效。' }
    : apiError?.kind === 'TIMEOUT' ? { title: '请求超时', description: apiError.message }
      : apiError?.kind === 'HTTP_ERROR' ? { title: '暂时无法完成请求', description: apiError.message }
        : { title: '无法连接本地服务', description: message ?? apiError?.message ?? '无法连接后端服务，请确认后端已启动。' }
  return <div className="grid min-h-64 place-items-center rounded-large border border-border bg-surface px-6 text-center" role="alert"><div><CircleAlert className="mx-auto h-8 w-8 text-danger" /><Heading className="mt-3 font-semibold">{copy.title}</Heading><p className="mt-1 text-sm text-text-secondary">{copy.description}</p>{action ?? (retry && <Button onClick={retry} className="mt-4">重新连接</Button>)}</div></div>
}
