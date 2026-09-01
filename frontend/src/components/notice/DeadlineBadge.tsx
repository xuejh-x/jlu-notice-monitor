import type { Notice } from '../../types'
import { cn } from '../../utils/cn'
import { deadlinePresentation, isExpired } from '../../utils/noticeMeta'

export function DeadlineBadge({ notice, detail = false, text, className }: { notice: Notice; detail?: boolean; text?: string; className?: string }) {
  if (!notice.registration_deadline && !isExpired(notice)) return null
  const deadline = deadlinePresentation(notice)
  const tone = isExpired(notice) || deadline.tone === 'secondary'
    ? 'bg-deadline-neutral-bg text-deadline-neutral-fg'
    : deadline.tone === 'danger'
      ? 'bg-deadline-danger-bg text-deadline-danger-fg'
      : 'bg-deadline-warning-bg text-deadline-warning-fg'
  return <span className={cn('inline-flex h-6 shrink-0 items-center rounded-small border border-current/10 px-2 text-label tabular-nums', tone, detail && 'min-w-24 justify-center', className)}>{text ?? deadline.text}</span>
}
