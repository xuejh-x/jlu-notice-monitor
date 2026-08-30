import { ChevronDown } from 'lucide-react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes } from 'react'
import { cn } from '../../utils/cn'
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) { return <input className={cn('h-11 w-full rounded-medium border border-border bg-surface px-3 text-sm text-text-primary placeholder:text-text-muted disabled:cursor-not-allowed disabled:opacity-50 md:h-9', className)} {...props} /> }
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) { return <div className="relative"><select className={cn('h-11 w-full appearance-none rounded-medium border border-border bg-surface px-3 pr-8 text-sm text-text-primary disabled:cursor-not-allowed disabled:opacity-50 md:h-9', className)} {...props}>{children}</select><ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" /></div> }

export function Toggle({ checked, className, ...props }: Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'role'> & { checked: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={cn('relative h-11 w-14 shrink-0 rounded-medium', className)}
      {...props}
    >
      <span aria-hidden="true" className={cn('absolute left-1.5 top-2.5 h-6 w-11 rounded-full transition-colors', checked ? 'bg-accent' : 'bg-border-strong')}>
        <span className={cn('absolute left-1 top-1 h-4 w-4 rounded-full bg-text-inverse transition-transform', checked && 'translate-x-5')} />
      </span>
    </button>
  )
}
