import { describe, expect, it } from 'vitest'
import type { Notice } from '../types'
import { deadlineDetail, deadlinePresentation, importanceLabels, importanceLevel, isExpired, sourceLabel } from './noticeMeta'

const base: Notice = {
  id: 1, title: '测试通知', url: 'https://example.test', publish_date: '2026-08-30', publisher: '计算机学院',
  category: 'other', importance_score: 50, registration_start: null, registration_deadline: null,
  event_start: null, event_end: null, deadline_status: 'unknown', days_until_deadline: null,
  status: 'new', first_seen_at: '2026-08-30T00:00:00Z', last_seen_at: '2026-08-30T00:00:00Z', updated_at: '2026-08-30T00:00:00Z',
  is_read: true, is_archived: false, is_favorite: false, sources: [],
}

describe('importanceLevel', () => {
  it('maps the fixed semantic bands independent of any threshold', () => {
    expect(importanceLevel(50)).toBe('normal')
    expect(importanceLevel(70)).toBe('important')
    expect(importanceLevel(89)).toBe('important')
    expect(importanceLevel(90)).toBe('high')
    expect(importanceLabels.important).toBe('重要')
    expect(importanceLabels.high).toBe('高相关')
  })
})

describe('deadlinePresentation', () => {
  it('returns 时间待定 for no deadline', () => {
    expect(deadlinePresentation({ ...base, registration_deadline: null, deadline_status: 'unknown', days_until_deadline: null })).toEqual({ text: '时间待定', tone: 'muted' })
  })
  it('returns 今天截止 for today', () => {
    expect(deadlinePresentation({ ...base, registration_deadline: '2026-08-30', deadline_status: 'today', days_until_deadline: 0 })).toEqual({ text: '今天截止', tone: 'danger' })
  })
  it('returns a danger tone for a soon deadline', () => {
    expect(deadlinePresentation({ ...base, registration_deadline: '2026-09-01', deadline_status: 'urgent', days_until_deadline: 2 })).toEqual({ text: '2 天后截止', tone: 'danger' })
  })
  it('returns a secondary tone for a normal deadline', () => {
    const result = deadlinePresentation({ ...base, registration_deadline: '2026-09-10', deadline_status: 'normal', days_until_deadline: 11 })
    expect(result.tone).toBe('secondary')
    expect(result.text).toBe('11 天后截止')
  })
  it('returns 已截止 muted for expired', () => {
    expect(deadlinePresentation({ ...base, registration_deadline: '2026-01-01', deadline_status: 'expired', days_until_deadline: -200 })).toEqual({ text: '已截止', tone: 'muted' })
  })
})

describe('deadlineDetail', () => {
  it('returns 时间待定 for no deadline', () => {
    expect(deadlineDetail({ ...base, registration_deadline: null, deadline_status: 'unknown', days_until_deadline: null })).toEqual({ text: '时间待定', tone: 'muted' })
  })
  it('returns 已截止 with date for expired', () => {
    expect(deadlineDetail({ ...base, registration_deadline: '2026-01-01', deadline_status: 'expired', days_until_deadline: -200 })).toEqual({ text: '已截止 · 2026-01-01', tone: 'muted' })
  })
  it('returns 今天截止 with date for today', () => {
    expect(deadlineDetail({ ...base, registration_deadline: '2026-08-30', deadline_status: 'today', days_until_deadline: 0 })).toEqual({ text: '今天截止 · 2026-08-30', tone: 'danger' })
  })
  it('returns date + remaining days for soon and normal deadlines', () => {
    expect(deadlineDetail({ ...base, registration_deadline: '2026-09-01', deadline_status: 'urgent', days_until_deadline: 2 })).toEqual({ text: '2026-09-01 · 剩余 2 天', tone: 'danger' })
    expect(deadlineDetail({ ...base, registration_deadline: '2026-09-10', deadline_status: 'normal', days_until_deadline: 11 })).toEqual({ text: '2026-09-10 · 剩余 11 天', tone: 'secondary' })
  })
})

describe('sourceLabel', () => {
  it('falls back to publisher when there is no source', () => {
    expect(sourceLabel({ ...base, sources: [] })).toBe('计算机学院')
  })
  it('returns primary source +N for multiple sources', () => {
    const sources = [{ code: 'cse', name: '网络安全学院', url: 'u1' }, { code: 'jwc', name: '本科生院', url: 'u2' }]
    expect(sourceLabel({ ...base, sources })).toBe('网络安全学院 +1')
  })
})

describe('isExpired', () => {
  it('detects expired status or negative days', () => {
    expect(isExpired({ ...base, deadline_status: 'expired', days_until_deadline: null })).toBe(true)
    expect(isExpired({ ...base, deadline_status: 'normal', days_until_deadline: -1 })).toBe(true)
    expect(isExpired({ ...base, deadline_status: 'normal', days_until_deadline: 5 })).toBe(false)
  })
})
