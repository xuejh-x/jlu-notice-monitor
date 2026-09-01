import { describe, expect, it } from 'vitest'
import { getRouteTitle, mobileNavItems, navGroups } from './navigation'

describe('navigation config', () => {
  it('maps every real destination to a group', () => {
    const routes = navGroups.flatMap(g => g.items.map(i => i.to))
    expect(routes).toEqual([
      '/', '/today', '/deadlines',
      '/competitions', '/competitions/algorithm', '/cybersecurity', '/training', '/research', '/postgraduate',
      '/favorites', '/notices', '/sources', '/settings',
    ])
  })

  it('exposes the four mobile bottom-nav destinations', () => {
    expect(mobileNavItems.map(i => i.to)).toEqual(['/', '/today', '/deadlines', '/favorites'])
  })

  it('returns the page context title for static and dynamic routes', () => {
    expect(getRouteTitle('/')).toBe('收件箱')
    expect(getRouteTitle('/dashboard')).toBe('首页')
    expect(getRouteTitle('/notices')).toBe('全部通知')
    expect(getRouteTitle('/notices/42')).toBe('通知详情')
    expect(getRouteTitle('/competitions/algorithm')).toBe('算法竞赛')
  })

  it('falls back to the app name for unknown routes', () => {
    expect(getRouteTitle('/nope')).toBe('吉大通知助手')
  })
})
