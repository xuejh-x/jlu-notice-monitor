import { Bell, CalendarClock, CalendarDays, CircleStar, FlaskConical, GraduationCap, House, List, Settings, ShieldCheck, Trophy, Waypoints } from 'lucide-react'
import type { ComponentType } from 'react'
import { matchPath } from 'react-router-dom'

export interface NavItem { to: string; label: string; icon: ComponentType<{ className?: string }> }
export interface NavGroup { label: string; items: NavItem[] }

/** Desktop Sidebar + Mobile "More" panel navigation (real routes only). */
export const navGroups: NavGroup[] = [
  {
    label: '总览',
    items: [
      { to: '/', label: '首页', icon: House },
      { to: '/today', label: '今日', icon: CalendarDays },
      { to: '/deadlines', label: '即将截止', icon: CalendarClock },
    ],
  },
  {
    label: '分类',
    items: [
      { to: '/competitions', label: '全部竞赛', icon: Trophy },
      { to: '/competitions/algorithm', label: '算法竞赛', icon: Waypoints },
      { to: '/cybersecurity', label: '网络安全', icon: ShieldCheck },
      { to: '/training', label: '实训 / 实习', icon: GraduationCap },
      { to: '/research', label: '科研 / 实验室', icon: FlaskConical },
      { to: '/postgraduate', label: '推免', icon: GraduationCap },
    ],
  },
  {
    label: '管理',
    items: [
      { to: '/favorites', label: '收藏', icon: CircleStar },
      { to: '/notices', label: '全部通知', icon: List },
      { to: '/sources', label: '数据源', icon: Bell },
      { to: '/settings', label: '设置', icon: Settings },
    ],
  },
]

/** Mobile bottom navigation destinations. */
export const mobileNavItems: NavItem[] = [
  { to: '/', label: '首页', icon: House },
  { to: '/today', label: '今日', icon: CalendarDays },
  { to: '/deadlines', label: '截止', icon: CalendarClock },
  { to: '/favorites', label: '收藏', icon: CircleStar },
]

/** route pattern → short context title for the mobile top bar. */
const routeTitles: Array<[string, string]> = [
  ['/', '首页'],
  ['/today', '今日'],
  ['/deadlines', '即将截止'],
  ['/competitions', '全部竞赛'],
  ['/competitions/algorithm', '算法竞赛'],
  ['/cybersecurity', '网络安全'],
  ['/training', '实训 / 实习'],
  ['/research', '科研 / 实验室'],
  ['/postgraduate', '推免'],
  ['/favorites', '收藏'],
  ['/notices', '全部通知'],
  ['/notices/:id', '通知详情'],
  ['/sources', '数据源'],
  ['/settings', '设置'],
]

export function getRouteTitle(pathname: string): string {
  for (const [pattern, title] of routeTitles) {
    if (matchPath(pattern, pathname)) return title
  }
  return '吉大通知助手'
}
