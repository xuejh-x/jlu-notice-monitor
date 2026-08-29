import { format, formatDistanceToNowStrict, parseISO } from 'date-fns'
import { zhCN } from 'date-fns/locale'

export function shortDate(value?: string | null) { return value ? format(parseISO(value), 'MM-dd') : '待定' }
export function fullDate(value?: string | null) { return value ? format(parseISO(value), 'yyyy-MM-dd') : '通知中未说明' }
export function relativeTime(value?: string | null) {
  if (!value) return '尚无记录'
  return formatDistanceToNowStrict(parseISO(value.replace(' ', 'T')), { addSuffix: true, locale: zhCN })
}
