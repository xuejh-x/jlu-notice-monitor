/* oxlint-disable react/only-export-components */
import { CheckCircle2, CircleAlert, X } from 'lucide-react'
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

type Toast = { id: number; message: string; tone: 'success' | 'error' }
const ToastContext = createContext<(message: string, tone?: Toast['tone']) => void>(() => undefined)
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const show = useCallback((message: string, tone: Toast['tone'] = 'success') => {
    const id = Date.now(); setItems(v => [...v, { id, message, tone }]); window.setTimeout(() => setItems(v => v.filter(i => i.id !== id)), 3200)
  }, [])
  return <ToastContext.Provider value={show}>{children}<div className="fixed bottom-20 right-4 z-[100] space-y-2 md:bottom-5" aria-live="polite">{items.map(item => <div key={item.id} className="flex min-w-64 items-center gap-3 rounded-large border border-border bg-surface-raised px-4 py-3 text-sm shadow-xl">{item.tone === 'success' ? <CheckCircle2 className="h-4 w-4 text-success" /> : <CircleAlert className="h-4 w-4 text-danger" />}<span className="flex-1">{item.message}</span><button className="grid h-11 w-11 shrink-0 place-items-center rounded-medium hover:bg-surface-muted md:h-9 md:w-9" onClick={() => setItems(v => v.filter(i => i.id !== item.id))} aria-label="关闭提示"><X className="h-4 w-4 text-text-muted" /></button></div>)}</div></ToastContext.Provider>
}
export const useToast = () => useContext(ToastContext)
