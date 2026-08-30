import { beforeEach, describe, expect, it } from 'vitest'
import { DEFAULTS, loadSettings, parseSettings, saveSettings } from './settings'

describe('settings persistence contract', () => {
  beforeEach(() => localStorage.clear())

  it('returns defaults when nothing is persisted', () => {
    expect(loadSettings()).toEqual(DEFAULTS)
  })

  it('restores a valid persisted value', () => {
    localStorage.setItem('jlu-settings', JSON.stringify({ pageSize: 50, priorityThreshold: 80, hideLowPriority: true, defaultHome: '/deadlines' }))
    expect(loadSettings()).toEqual({ pageSize: 50, priorityThreshold: 80, hideLowPriority: true, defaultHome: '/deadlines' })
  })

  it('merges partial persisted values over defaults', () => {
    localStorage.setItem('jlu-settings', JSON.stringify({ priorityThreshold: 80 }))
    expect(loadSettings()).toEqual({ ...DEFAULTS, priorityThreshold: 80 })
  })

  it('falls back to defaults on invalid JSON', () => {
    localStorage.setItem('jlu-settings', '{not-json')
    expect(loadSettings()).toEqual(DEFAULTS)
  })

  it('coerces invalid/out-of-range persisted values to defaults', () => {
    localStorage.setItem('jlu-settings', JSON.stringify({ pageSize: 'abc', priorityThreshold: 99, hideLowPriority: 'false', defaultHome: '/notices' }))
    expect(loadSettings()).toEqual(DEFAULTS)
  })

  it('accepts numeric strings for numeric fields', () => {
    localStorage.setItem('jlu-settings', JSON.stringify({ pageSize: '50', priorityThreshold: '80' }))
    expect(loadSettings()).toEqual({ ...DEFAULTS, pageSize: 50, priorityThreshold: 80 })
  })

  it('round-trips saveSettings -> loadSettings', () => {
    saveSettings({ ...DEFAULTS, defaultHome: '/today', pageSize: 10 })
    expect(loadSettings()).toEqual({ ...DEFAULTS, defaultHome: '/today', pageSize: 10 })
  })

  it('drops unknown keys and rejects non-object persisted values', () => {
    expect(parseSettings(null)).toEqual(DEFAULTS)
    expect(parseSettings('garbage')).toEqual(DEFAULTS)
    expect(parseSettings({ pageSize: 20, extra: 'drop-me' })).toEqual(DEFAULTS)
  })
})
