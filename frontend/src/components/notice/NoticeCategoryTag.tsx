import { categoryLabels } from '../../utils/labels'
import { cn } from '../../utils/cn'
import { Badge } from '../ui/Badge'

/** Presentation mapping shared by list and reader; no new categories or filters. */
export function NoticeCategoryTag({ category, className }: { category: string | null; className?: string }) {
  const tone = category === 'research' || category === 'innovation_competition'
    ? 'border-source-green-fg/20 bg-source-green-bg text-source-green-fg'
    : category === 'training' || category === 'internship'
      ? 'border-deadline-warning-fg/20 bg-deadline-warning-bg text-deadline-warning-fg'
      : category && category !== 'other'
        ? 'border-source-blue-fg/20 bg-source-blue-bg text-source-blue-fg'
        : 'border-border bg-deadline-neutral-bg text-deadline-neutral-fg'
  return <Badge className={cn('block h-5 min-w-0 truncate rounded-compact px-1.5 py-0', tone, className)}>{categoryLabels[category ?? ''] ?? '其他'}</Badge>
}
