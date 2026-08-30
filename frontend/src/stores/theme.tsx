/* oxlint-disable react/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
const THEMES: readonly ThemeMode[] = ['light', 'dark', 'system']
const ThemeContext = createContext<{ theme: ThemeMode; setTheme: (value: ThemeMode) => void } | null>(null)

/** Read persisted theme with validation; unknown/legacy values fall back to `system`. */
function readTheme(): ThemeMode {
  const value = localStorage.getItem('jlu-theme')
  return value !== null && THEMES.includes(value as ThemeMode) ? (value as ThemeMode) : 'system'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(readTheme)
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => document.documentElement.classList.toggle('dark', theme === 'dark' || (theme === 'system' && media.matches))
    apply(); media.addEventListener('change', apply); return () => media.removeEventListener('change', apply)
  }, [theme])
  const setTheme = (value: ThemeMode) => { localStorage.setItem('jlu-theme', value); setThemeState(value) }
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
}
export function useTheme() { const value = useContext(ThemeContext); if (!value) throw new Error('ThemeProvider 缺失'); return value }
