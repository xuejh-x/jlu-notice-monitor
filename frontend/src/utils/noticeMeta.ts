import type { Notice } from '../types'
import { fullDate, shortDate } from './format'

export type ImportanceLevel = 'normal' | 'important' | 'high'

/** Fixed semantic band (design.md §15): independent of user priorityThreshold. */
export function importanceLevel(score: number): ImportanceLevel {
  if (score >= 90) return 'high'
  if (score >= 70) return 'important'
  return 'normal'
}

export const importanceLabels = { important: '重要', high: '高相关' } as const

export type DeadlineTone = 'muted' | 'secondary' | 'danger'

export interface DeadlinePresentation { text: string; tone: DeadlineTone }

/** Deadline semantics (design.md §14), reusing existing semantic tokens. */
export function deadlinePresentation(notice: Notice): DeadlinePresentation {
  const days = notice.days_until_deadline
  if (isExpired(notice)) return { text: '已截止', tone: 'muted' }
  if (!notice.registration_deadline) return { text: '时间待定', tone: 'muted' }
  if (notice.deadline_status === 'today') return { text: '今天截止', tone: 'danger' }
  if (days !== null && days <= 3) return { text: `${Math.max(0, days)} 天后截止`, tone: 'danger' }
  return { text: days !== null ? `${days} 天后截止` : `截止 ${shortDate(notice.registration_deadline)}`, tone: 'secondary' }
}

/** Full-deadline presentation for the detail page: concrete date + days left,
 *  reusing the same deadline semantics and tokens as `deadlinePresentation`. */
export function deadlineDetail(notice: Notice): DeadlinePresentation {
  if (!notice.registration_deadline) return { text: '时间待定', tone: 'muted' }
  const date = fullDate(notice.registration_deadline)
  if (isExpired(notice)) return { text: `已截止 · ${date}`, tone: 'muted' }
  if (notice.deadline_status === 'today') return { text: `今天截止 · ${date}`, tone: 'danger' }
  const days = notice.days_until_deadline
  if (days === null) return { text: date, tone: 'secondary' }
  if (days <= 3) return { text: `${date} · 剩余 ${Math.max(0, days)} 天`, tone: 'danger' }
  return { text: `${date} · 剩余 ${days} 天`, tone: 'secondary' }
}

export function isExpired(notice: Notice): boolean {
  return notice.deadline_status === 'expired' || (notice.days_until_deadline !== null && notice.days_until_deadline < 0)
}

/** Primary source + "+N" when a notice has multiple sources. */
export function sourceLabel(notice: Notice): string {
  const primary = notice.sources[0]?.name ?? notice.publisher ?? '来源待定'
  return notice.sources.length > 1 ? `${primary} +${notice.sources.length - 1}` : primary
}
