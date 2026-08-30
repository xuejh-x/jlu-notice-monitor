import type { ReactNode } from 'react'
export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="min-w-0">
        <h1 className="text-page-title text-text-primary sm:text-3xl">{title}</h1>
        {description && <p className="mt-1.5 max-w-3xl text-body text-text-secondary">{description}</p>}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </header>
  )
}
