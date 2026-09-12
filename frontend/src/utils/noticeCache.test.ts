import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { invalidateNoticeState, preserveNoticeAfterAutoRead, updateNoticeReadState } from './noticeCache'

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

describe('preserveNoticeAfterAutoRead', () => {
  it('marks cached list rows read and makes the query stale without refetching it', () => {
    const client = new QueryClient()
    const notice = { id: 42, is_read: false }
    client.setQueryData(['notices', 'all', { read: false }], { items: [notice], total: 1, total_count: 1, unread_count: 1, all_count: 1, page: 1, page_size: 20, total_pages: 1 })
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    preserveNoticeAfterAutoRead(client, 42)

    expect(client.getQueryData<{ items: Array<{ id: number; is_read: boolean }> }>(['notices', 'all', { read: false }])?.items).toEqual([{ id: 42, is_read: true }])
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['notices'], refetchType: 'none' })
  })
})

describe('updateNoticeReadState', () => {
  it('updates detail/list/dashboard immediately without changing independent totals', () => {
    const client = new QueryClient()
    const notice = { id: 42, is_read: true }
    client.setQueryData(['notice', 42], notice)
    client.setQueryData(['notices', 'all'], { items: [notice], total: 1, total_count: 1, unread_count: 1, all_count: 1, page: 1, page_size: 20, total_pages: 1 })
    client.setQueryData(['dashboard'], { total_count: 9, unread: 2, important: 3, upcoming_deadlines: 4, recent_notices: [notice] })

    updateNoticeReadState(client, 42, false, true)

    expect(client.getQueryData<{ is_read: boolean }>(['notice', 42])?.is_read).toBe(false)
    expect(client.getQueryData<{ items: Array<{ is_read: boolean }> }>(['notices', 'all'])?.items[0].is_read).toBe(false)
    expect(client.getQueryData<{ total_count: number; unread: number; important: number; upcoming_deadlines: number }>(['dashboard'])).toMatchObject({ total_count: 9, unread: 3, important: 3, upcoming_deadlines: 4 })
  })
})
