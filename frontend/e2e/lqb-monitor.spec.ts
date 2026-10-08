import { expect, test } from '@playwright/test'

const url = 'https://lus-jlu.github.io/lqb.html'
const name = '蓝桥杯赛事信息（吉林大学）'

for (const width of [1440, 390]) {
  test(`FIXTURE Lanqiao detection, reading and local source controls (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    let read = false
    let readCalls = 0
    const detected = new Date().toISOString()
    const notice = {
      id: 901, title: '第18届蓝桥杯信息更新：参赛日程', url, publish_date: null, publisher: name,
      category: 'algorithm_competition', importance_score: 65, status: 'new',
      first_seen_at: detected, last_seen_at: detected, updated_at: detected,
      registration_start: null, registration_deadline: null, event_start: null, event_end: null,
      deadline_status: 'unknown', days_until_deadline: null, is_archived: false, is_favorite: false,
      sources: [{ code: 'lqb', name, url }],
      content: '【参赛日程】\n变更前：报名截止12月18日\n变更后：报名截止12月19日',
      attachments: [], updates: [], target_students: null, registration_method: null, competition_level: null,
    }
    await page.route('**/api/notices**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path.endsWith('/901/read')) {
        read = true; readCalls++
        await route.fulfill({ json: { notice_id: 901, is_read: true } }); return
      }
      if (path.endsWith('/901')) {
        await route.fulfill({ json: { ...notice, is_read: read } }); return
      }
      if (path.endsWith('/notices')) {
        const params = new URL(route.request().url()).searchParams
        const items = params.get('read') === 'false' && read ? [] : [{ ...notice, is_read: read }]
        await route.fulfill({ json: { items, total: items.length, total_count: items.length,
          unread_count: read ? 0 : 1, all_count: 1, page: 1, page_size: 20, total_pages: items.length ? 1 : 0 } }); return
      }
      await route.fallback()
    })
    await page.goto('/notices?source=lqb&read=0')
    await expect(page.getByRole('link', { name: `打开${notice.title}` })).toBeVisible()
    await expect(page.getByText(/首次检测：/)).toBeVisible()
    await page.getByRole('button', { name: '筛选 1' }).click()
    await expect(page.getByRole('dialog').getByLabel('来源')).toHaveValue('lqb')
    await page.getByRole('button', { name: '关闭筛选' }).click()
    await page.getByRole('link', { name: `打开${notice.title}` }).click()
    await expect(page.getByRole('heading', { level: 1, name: notice.title })).toBeVisible()
    await expect(page.getByText(/首次检测：/).last()).toBeVisible()
    await expect(page.getByText(/变更后：报名截止12月19日/)).toBeVisible()
    await expect(page.getByText(/发布时间：/)).toHaveCount(0)
    await expect(page.locator(`a[href="${url}"]`).first()).toBeVisible()
    await expect.poll(() => readCalls).toBe(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    await page.screenshot({ path: `test-results/lqb-detail-${width}.png`, fullPage: true })
    // Explicit refresh may remove a read row; merely opening it must not.
    if (width >= 768) await expect(page.getByRole('link', { name: `打开${notice.title}` })).toBeVisible()
    await page.goto('/notices?source=lqb&read=0')
    await expect(page.getByRole('link', { name: `打开${notice.title}` })).toHaveCount(0)
    await expect(page.getByText('当前结果 0 条 · 未读 0 条')).toBeVisible()

    let failed = false
    let completed: string | null = null
    let checks = 0
    await page.route('**/api/crawler/status', async route => route.fulfill({ json: {
      running: false, status: failed ? 'failure' : 'success', last_run: completed,
      current_started_at: null, last_duration: 0.1, new_count: 0, updated_count: 0, source_results: [],
    } }))
    await page.route('**/api/source-config/9/check', async route => {
      checks++
      if (checks === 3) {
        await route.fulfill({ status: 409, json: { detail: '已有检查正在运行（测试）' } }); return
      }
      failed = checks === 1
      completed = new Date(Date.now() + checks * 1000).toISOString()
      await route.fulfill({ status: 202, json: { status: 'started', source: 'lqb' } })
    })
    await page.route('**/api/source-config', async route => route.fulfill({ json: [{
      id: 9, code: 'lqb', name, base_url: url, ownership: 'CUSTOM_LOCAL_PUBLIC',
      source_type: 'single_page_monitor', parser: 'lqb', parser_config: {}, subscribed: true, enabled: true,
      auth_type: 'none', health_state: failed ? 'parse_error' : 'healthy', source_scope: 'personal', execution: 'local',
      execution_policy: 'local_only', cloud_source_id: null, cloud_policy: 'auto', validation_status: 'passed',
      requires_reauthentication: false,
      last_error: failed ? 'LQB_PARSER_FAILED: required sections missing (FIXTURE)' : null,
      last_error_code: failed ? 'PARSE_ERROR' : null,
      last_checked_at: detected, last_success_at: detected,
    }] }))
    await page.goto('/sources')
    await expect(page.getByRole('heading', { name })).toBeVisible()
    await expect(page.getByRole('button', { name: '编辑' })).toBeDisabled()
    await expect(page.getByRole('button', { name: '上云', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '检查', exact: true })).toBeEnabled()
    await expect(page.getByText(/首次检查只建立基线/)).toBeVisible()
    await expect(page.getByText(/完全退出桌面客户端或系统休眠期间不会检查页面/)).toBeVisible()
    const check = page.getByRole('button', { name: '检查', exact: true })
    await check.click()
    await expect(page.getByText('解析失败', { exact: true })).toBeVisible()
    await expect(page.getByText(/LQB_PARSER_FAILED: required sections missing/)).toBeVisible()
    await expect(check).toBeEnabled()
    await check.click()
    await expect(page.getByText('运行正常', { exact: true })).toBeVisible()
    await expect(page.getByText('解析失败', { exact: true })).toHaveCount(0)
    await expect(check).toBeEnabled()
    await check.click()
    await expect(page.getByText('已有检查正在运行（测试）', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    await page.screenshot({ path: `test-results/lqb-source-${width}.png`, fullPage: true })
  })
}
