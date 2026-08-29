import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../utils/cn'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' | 'icon' }
export function Button({ variant = 'secondary', size = 'md', className, ...props }: Props) {
  const variants = { primary: 'bg-indigo-600 text-white hover:bg-indigo-700 border-indigo-600', secondary: 'bg-white text-zinc-700 hover:bg-zinc-50 border-zinc-200 dark:bg-zinc-900 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800', ghost: 'border-transparent bg-transparent text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800', danger: 'bg-rose-600 text-white hover:bg-rose-700 border-rose-600' }
  const sizes = { sm: 'h-8 px-3 text-xs', md: 'h-9 px-3.5 text-sm', icon: 'h-9 w-9' }
  return <button className={cn('inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border font-medium transition-colors disabled:pointer-events-none disabled:opacity-50', variants[variant], sizes[size], className)} {...props} />
}
