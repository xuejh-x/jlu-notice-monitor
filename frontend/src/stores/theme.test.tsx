import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ThemeProvider, useTheme } from './theme'

function Probe() {
  const { theme, setTheme } = useTheme()
  return <button onClick={() => setTheme('dark')}>{theme}</button>
}

function renderTheme() {
  return render(<ThemeProvider><Probe /></ThemeProvider>)
}

describe('theme persistence contract', () => {
  beforeEach(() => localStorage.clear())

  it('defaults to system when nothing is persisted', () => {
    renderTheme()
    expect(screen.getByRole('button')).toHaveTextContent('system')
  })

  it('falls back to system for an invalid persisted value', () => {
    localStorage.setItem('jlu-theme', 'banana')
    renderTheme()
    expect(screen.getByRole('button')).toHaveTextContent('system')
  })

  it('restores a valid persisted value', () => {
    localStorage.setItem('jlu-theme', 'dark')
    renderTheme()
    expect(screen.getByRole('button')).toHaveTextContent('dark')
  })

  it('persists theme changes to localStorage', () => {
    renderTheme()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByRole('button')).toHaveTextContent('dark')
    expect(localStorage.getItem('jlu-theme')).toBe('dark')
  })
})
