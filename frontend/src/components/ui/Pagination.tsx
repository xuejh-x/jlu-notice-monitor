import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './Button'

export function Pagination({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange: (page: number) => void }) {
  if (totalPages <= 1) return null
  return <nav className="mt-4 flex items-center justify-center gap-3" aria-label="通知分页">
    <Button disabled={page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft className="h-4 w-4"/>上一页</Button>
    <span className="min-w-20 text-center text-xs tabular-nums text-zinc-500">第 {page} / {totalPages} 页</span>
    <Button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>下一页<ChevronRight className="h-4 w-4"/></Button>
  </nav>
}
