import type { HTMLAttributes } from 'react'
import { cn } from '../../utils/cn'
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn('rounded-large border border-border bg-surface shadow-sm', className)} {...props} /> }
