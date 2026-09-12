import { Clock3 } from 'lucide-react'
import type { Notice } from '../../types'
import { cn } from '../../utils/cn'
import { deadlinePresentation, isExpired } from '../../utils/noticeMeta'

export function DeadlineBadge({ notice, detail = false, list = false, text, className }: { notice: Notice; detail?: boolean; list?: boolean; text?: string; className?: string }) {
  if (!notice.registration_deadline && !isExpired(notice)) return null
  const deadline = deadlinePresentation(notice)
  const tone = isExpired(notice) || deadline.tone === 'secondary'
    ? 'bg-deadline-neutral-bg text-deadline-neutral-fg'
    : deadline.tone === 'danger'
      ? list && notice.deadline_status !== 'today' ? 'bg-deadline-warning-bg text-deadline-warning-fg' : 'bg-deadline-danger-bg text-deadline-danger-fg'
      : 'bg-deadline-warning-bg text-deadline-warning-fg'
  return <span title={list ? notice.registration_deadline ?? undefined : undefined} className={cn('inline-flex h-6 shrink-0 items-center rounded-compact border border-current/20 px-2 text-label tabular-nums', tone, detail && 'min-w-24 justify-center', list && 'h-5 gap-1 px-1.5', className)}>{list && <Clock3 className="h-3 w-3" aria-hidden="true" />}{text ?? deadline.text}</span>
}
