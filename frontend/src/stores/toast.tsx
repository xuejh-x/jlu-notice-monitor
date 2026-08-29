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
  return <ToastContext.Provider value={show}>{children}<div className="fixed bottom-20 right-4 z-[100] space-y-2 md:bottom-5" aria-live="polite">{items.map(item => <div key={item.id} className="flex min-w-64 items-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm shadow-xl dark:border-zinc-700 dark:bg-zinc-900">{item.tone === 'success' ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <CircleAlert className="h-4 w-4 text-rose-500" />}<span className="flex-1">{item.message}</span><button onClick={() => setItems(v => v.filter(i => i.id !== item.id))} aria-label="关闭提示"><X className="h-4 w-4 text-zinc-400" /></button></div>)}</div></ToastContext.Provider>
}
export const useToast = () => useContext(ToastContext)
