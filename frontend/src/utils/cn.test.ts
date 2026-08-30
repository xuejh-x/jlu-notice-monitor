import { describe, expect, it } from 'vitest'
import { cn } from './cn'

describe('cn (tailwind-merge with Gate 3B typography tokens)', () => {
  it('keeps a custom font-size token together with a text color', () => {
    const result = cn('text-label', 'text-indigo-700')
    expect(result).toContain('text-label')
    expect(result).toContain('text-indigo-700')
  })

  it('keeps text-metadata together with a semantic text color', () => {
    expect(cn('text-metadata tabular-nums text-text-muted')).toBe('text-metadata tabular-nums text-text-muted')
  })

  it('still resolves real class conflicts with last-wins', () => {
    expect(cn('bg-white', 'bg-zinc-50')).toBe('bg-zinc-50')
    expect(cn('text-zinc-900', 'text-zinc-100')).toBe('text-zinc-100')
  })
})
