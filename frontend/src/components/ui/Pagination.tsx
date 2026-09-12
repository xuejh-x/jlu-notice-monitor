import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './Button'
import { cn } from '../../utils/cn'

export function Pagination({ page, totalPages, onPageChange, compact = false }: { page: number; totalPages: number; onPageChange: (page: number) => void; compact?: boolean }) {
  if (totalPages <= 1) return null
  return <nav className={cn('mt-4 flex items-center justify-center gap-2 sm:gap-3', compact && 'mt-0 gap-2')} aria-label="通知分页">
    <Button aria-label="上一页" variant={compact ? 'ghost' : 'secondary'} className={cn('gap-1 px-2 sm:gap-2 sm:px-3.5', compact && 'h-8 w-8 px-0 sm:px-0 md:h-8')} disabled={page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft className="h-4 w-4"/>{!compact && '上一页'}</Button>
    <span className="min-w-16 text-center text-metadata tabular-nums text-text-muted sm:min-w-20">第 {page} / {totalPages} 页</span>
    <Button aria-label="下一页" variant={compact ? 'ghost' : 'secondary'} className={cn('gap-1 px-2 sm:gap-2 sm:px-3.5', compact && 'h-8 w-8 px-0 sm:px-0 md:h-8')} disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>{!compact && '下一页'}<ChevronRight className="h-4 w-4"/></Button>
  </nav>
}
