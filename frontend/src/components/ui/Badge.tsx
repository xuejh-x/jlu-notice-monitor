import type { HTMLAttributes } from 'react'
import { cn } from '../../utils/cn'

export type BadgeVariant = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'important'
const variants: Record<BadgeVariant, string> = {
  neutral: 'border-border bg-surface-muted text-text-secondary',
  accent: 'border-transparent bg-accent-soft text-accent-soft-text',
  success: 'border-transparent bg-success/10 text-success',
  warning: 'border-transparent bg-warning/10 text-warning',
  danger: 'border-transparent bg-danger/10 text-danger',
  important: 'border-transparent bg-important/10 text-important',
}

export function Badge({ variant = 'neutral', className, ...props }: HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) { return <span className={cn('inline-flex items-center rounded-small border px-2 py-0.5 text-label', variants[variant], className)} {...props} /> }
