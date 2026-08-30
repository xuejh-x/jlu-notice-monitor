import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../utils/cn'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' | 'icon' }
export function Button({ variant = 'secondary', size = 'md', className, ...props }: Props) {
  const variants = {
    primary: 'border-transparent bg-accent text-text-inverse hover:bg-accent-hover',
    secondary: 'border-border bg-surface text-text-secondary hover:bg-surface-muted',
    ghost: 'border-transparent bg-transparent text-text-secondary hover:bg-surface-muted',
    danger: 'border-transparent bg-danger text-text-inverse hover:bg-danger/90',
  }
  const sizes = {
    sm: 'h-9 px-3 text-xs',
    md: 'h-11 px-3.5 text-sm md:h-9',
    icon: 'h-11 w-11 md:h-9 md:w-9',
  }
  return <button className={cn('inline-flex shrink-0 items-center justify-center gap-2 rounded-medium border font-medium transition-colors disabled:pointer-events-none disabled:opacity-50', variants[variant], sizes[size], className)} {...props} />
}
