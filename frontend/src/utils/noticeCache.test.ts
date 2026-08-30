import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { invalidateNoticeState } from './noticeCache'

describe('invalidateNoticeState', () => {
  it('invalidates the detail, list, and dashboard entries with the authoritative key set', () => {
    const client = new QueryClient()
    const spy = vi.spyOn(client, 'invalidateQueries').mockImplementation((() => Promise.resolve()) as typeof client.invalidateQueries)

    invalidateNoticeState(client, 42)

    expect(spy).toHaveBeenCalledTimes(3)
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notice', 42] })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notices'] })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
  })
})
