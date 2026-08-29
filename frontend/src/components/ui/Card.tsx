import type { HTMLAttributes } from 'react'
import { cn } from '../../utils/cn'
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn('rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900', className)} {...props} /> }
