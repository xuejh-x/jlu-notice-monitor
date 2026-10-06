import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const backendUrl = 'http://127.0.0.1:8010'

async function setState(request: APIRequestContext, id: number, state: 'read' | 'unread' | 'favorite' | 'unfavorite') {
  const response = await request.post(`${backendUrl}/api/notices/${id}/${state}`)
  expect(response.ok()).toBeTruthy()
}

async function resetFixture(request: APIRequestContext) {
  await setState(request, 101, 'unread')
  await setState(request, 101, 'unfavorite')
  await setState(request, 102, 'read')
  await setState(request, 102, 'unfavorite')
  await setState(request, 103, 'read')
  await setState(request, 103, 'favorite')
  await setState(request, 104, 'unread')
  await setState(request, 104, 'unfavorite')
  await setState(request, 105, 'read')
  await setState(request, 105, 'unfavorite')
  await setState(request, 106, 'read')
  await setState(request, 106, 'favorite')
  const preferences = await request.patch(`${backendUrl}/api/notifications/preferences`, { data: {
    enabled: true, new_notice_enabled: true, important_notice_enabled: true, deadline_enabled: true,
    source_health_enabled: true, daily_summary_enabled: true, minimum_importance: 70,
    deadline_lead_days: [7, 3, 1], quiet_start: '23:00', quiet_end: '08:00',
  } })
  expect(preferences.ok()).toBeTruthy()
}

const officialSource = {
  id: 1, code: 'e2e-main', name: 'E2E 教务通知', base_url: 'https://example.test/main', ownership: 'OFFICIAL_CLOUD',
  source_type: 'official_adapter', parser: 'auto', parser_config: {}, subscribed: true, enabled: true,
  auth_type: 'none', username: null, password_saved: false, login_url: null, allow_private_network: false,
  health_state: 'healthy', last_error_code: null, last_error: null, last_checked_at: null, last_success_at: null,
  requires_reauthentication: false, source_identity: 'a'.repeat(64), cloud_source_id: 'e2e-main',
  source_scope: 'official', execution: 'cloud', execution_policy: 'cloud_preferred', cloud_policy: 'auto', crawl_interval_seconds: null,
  validation_status: 'passed', validated_at: '2026-09-02T00:00:00',
}

const localSource = {
  ...officialSource, id: 3, code: 'e2e-local-fixture', name: 'MOCK / FIXTURE 公开来源',
  base_url: 'https://fixture.example.test/notices', ownership: 'CUSTOM_LOCAL_PUBLIC', source_type: 'public_html',
  source_identity: 'c'.repeat(64), cloud_source_id: null, source_scope: 'personal', execution: 'local', execution_policy: 'local_only',
}

async function installCloudPromotionFixture(page: Page, options: { existing?: boolean; startCloud?: boolean } = {}) {
  let source = options.startCloud ? {
    ...localSource, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud', execution_policy: 'cloud_only',
    cloud_source_id: 'shared-e2e-fixture', cloud_policy: 'force_enabled',
  } : { ...localSource }
  await page.route('**/api/source-config**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === 'GET' && path.endsWith('/api/source-config')) {
      await route.fulfill({ json: [officialSource, source] }); return
    }
    if (request.method() === 'POST' && path.endsWith('/preview')) {
      await route.fulfill({ json: { status: 'success', detected_type: 'generic_html', found: 1, items: [{ title: 'MOCK / FIXTURE preview', url: 'https://fixture.example.test/1', publish_date: null, content_preview: 'fixture' }], preview_token: 'mock-fixture-preview' } }); return
    }
    if (request.method() === 'POST' && path.endsWith('/cloud-sources')) {
      source = { ...source, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud', execution_policy: 'cloud_only', cloud_source_id: 'shared-e2e-fixture', cloud_policy: 'force_enabled', promotion_reused: Boolean(options.existing) }
      await route.fulfill({ status: 201, json: source }); return
    }
    if (request.method() === 'PATCH' && path.endsWith('/3')) {
      await route.fulfill({ json: source }); return
    }
    if (request.method() === 'POST' && path.endsWith('/promote')) {
      source = { ...source, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud', execution_policy: 'cloud_only', cloud_source_id: 'shared-e2e-fixture', cloud_policy: 'force_enabled', promotion_reused: Boolean(options.existing) }
      await route.fulfill({ json: source }); return
    }
    await route.fallback()
  })
}

async function openSearch(page: Page) {
  const search = page.getByRole('combobox', { name: '搜索通知' })
  await search.focus()
  return search
}

test.beforeEach(async ({ request }) => {
  await resetFixture(request)
})

test('Startup sync completion refreshes cached dashboard data', async ({ page }) => {
  let statusCalls = 0
  let dashboardCalls = 0
  await page.route('**/api/crawler/status', async route => {
    statusCalls += 1
    const running = statusCalls === 1
    await route.fulfill({ json: {
      running, status: running ? 'running' : 'success', trigger_source: 'startup',
      current_started_at: running ? '2026-09-10T08:00:00' : null,
      last_run: running ? null : '2026-09-10T08:00:03', last_duration: running ? null : 3,
      new_count: running ? 0 : 8, updated_count: 0, unchanged_count: 20, source_results: [],
      startup_sync: { triggered: true, started_at: '2026-09-10T08:00:00', completed_at: running ? null : '2026-09-10T08:00:03', outcome: running ? 'started' : 'success', skipped_reason: null },
    } })
  })
  await page.route('**/api/dashboard', async route => {
    dashboardCalls += 1
    await route.fulfill({ json: {
      total_count: 7,
      new_today: dashboardCalls === 1 ? 1 : 9, urgent: 0, important: 0,
      upcoming_deadlines: 0, unread: 0, source_status: [], recent_notices: [],
    } })
  })
  await page.goto('/notices')
  await expect(page.getByText('检查完成')).toBeVisible()
  await expect.poll(() => statusCalls).toBeGreaterThanOrEqual(2)
  await expect.poll(() => dashboardCalls).toBeGreaterThanOrEqual(2)
})

test('OA 校内通知 is an official public subscription with no login UI', async ({ page }) => {
  const oa = {
    ...officialSource, id: 6, code: 'oa', name: '吉林大学 OA 校内通知', base_url: 'https://oa.jlu.edu.cn',
    ownership: 'OFFICIAL_CLOUD', source_type: 'official', parser: 'oa_public', auth_type: 'none',
    enabled: true, health_state: 'healthy', last_error_code: null, requires_reauthentication: false,
    authentication_status: 'not_required', login_url: null, source_scope: 'official', execution: 'cloud', execution_policy: 'cloud_preferred',
    cloud_source_id: 'oa', cloud_policy: 'force_enabled', validation_status: 'passed',
  }
  await page.route('**/api/source-config**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === 'GET' && path.endsWith('/api/source-config')) {
      await route.fulfill({ json: [officialSource, oa] })
      return
    }
    await route.fallback()
  })
  await page.goto('/sources')
  const oaRow = page.getByRole('heading', { name: '吉林大学 OA 校内通知' }).locator('xpath=ancestor::article')
  await expect(oaRow).toBeVisible()
  await expect(page.getByRole('button', { name: /首次登录|重新登录|检测登录状态/ })).toHaveCount(0)
  await expect(oaRow.getByText(/认证：|Cookie/)).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: '吉林大学 OA 校内通知' })).toBeVisible()
  const bodyWidth = await page.locator('body').evaluate(element => element.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(390)
})

test('Sources page shows an active local fallback for a cloud-preferred source', async ({ page }) => {
  const fallbackSource = {
    ...officialSource,
    id: 6,
    code: 'oa',
    name: '吉林大学 OA 校内通知',
    base_url: 'https://oa.jlu.edu.cn',
    parser: 'oa_public',
    cloud_source_id: 'oa',
  }
  await page.route('**/api/source-config**', async route => {
    const request = route.request()
    if (request.method() === 'GET' && new URL(request.url()).pathname.endsWith('/api/source-config')) {
      await route.fulfill({ json: [officialSource, fallbackSource] })
      return
    }
    await route.fallback()
  })
  await page.route('**/api/crawler/status', route => route.fulfill({ json: {
    running: false, status: 'success', current_started_at: null,
    last_run: '2026-09-12T08:00:00', last_duration: 2,
    new_count: 0, updated_count: 0, unchanged_count: 1,
    source_results: [{
      source: 'oa', status: 'success', execution_policy: 'cloud_preferred',
      effective_execution: 'local', fallback_used: true,
      fallback_reason: 'PUBLIC_FEED_TIMEOUT', fetched: 1,
      new_count: 0, updated_count: 0, unchanged_count: 1, errors: [],
      attempts: [
        { execution: 'cloud', status: 'failure', error: 'PUBLIC_FEED_TIMEOUT' },
        { execution: 'local', status: 'success', error: null },
      ],
    }],
  } }))

  await page.goto('/sources')
  const row = page.getByRole('heading', { name: '吉林大学 OA 校内通知' }).locator('xpath=ancestor::article')
  await expect(row.getByText('云端优先')).toBeVisible()
  await expect(row.getByText('本地回退生效')).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(row.getByText('本地回退生效')).toBeVisible()
  expect(await page.locator('body').evaluate(element => element.scrollWidth)).toBeLessThanOrEqual(390)
})

test('Cloud HTML auto-detect failure can be recovered with advanced selectors', async ({ page }) => {
  let previewCalls = 0
  let previewBody: Record<string, unknown> | null = null
  await page.route('**/api/source-config**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === 'GET' && path.endsWith('/api/source-config')) {
      await route.fulfill({ json: [officialSource] }); return
    }
    if (request.method() === 'POST' && path.endsWith('/preview')) {
      previewCalls += 1
      previewBody = request.postDataJSON()
      if (previewCalls === 1) {
        await route.fulfill({ status: 422, json: { detail: 'Source preview failed: This page is unsupported or needs advanced selector configuration' } }); return
      }
      await route.fulfill({ json: { status: 'success', detected_type: 'generic_html', found: 1, items: [{ title: 'Selector 通知', url: 'https://dynamic.example.test/1', publish_date: null, content_preview: '' }], preview_token: 'selector-preview' } }); return
    }
    await route.fallback()
  })
  await page.goto('/sources')
  await page.getByRole('button', { name: '添加云端共享来源' }).click()
  await page.getByLabel('名称').fill('动态页面通知')
  await page.getByLabel('URL').fill('https://dynamic.example.test/notices')
  await page.getByRole('button', { name: 'Test Fetch / Preview' }).click()
  await expect(page.getByLabel('列表元素 Selector')).toBeVisible()
  await page.getByLabel('列表元素 Selector').fill('.notice-item')
  await page.getByLabel('标题 Selector').fill('.title')
  await page.getByLabel('URL Selector').fill('a[href]')
  await page.getByLabel('时间 Selector').fill('.time')
  await page.getByRole('button', { name: 'Test Fetch / Preview' }).click()
  await expect(page.getByText('Preview Result · 找到 1 条通知')).toBeVisible()
  expect(previewBody).toMatchObject({ parser: 'generic_html', parser_config: { type: 'html_selector', item_selector: '.notice-item', title_selector: '.title', url_selector: 'a[href]', time_selector: '.time' } })
})

test('Dashboard → Notice Detail', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.getByRole('main').getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('heading', { name: '最近通知' })).toBeVisible()
  await page.getByRole('link', { name: /E2E 未读奖学金申请通知/ }).first().click()
  await expect(page).toHaveURL(/\/notices\/101$/)
  await expect(page.getByRole('heading', { name: 'E2E 未读奖学金申请通知', level: 1 })).toBeVisible()
})

test('Notices filter keeps URL, UI, and results aligned', async ({ page }) => {
  await page.goto('/notices')
  await page.getByRole('button', { name: '筛选' }).click()
  const dialog = page.getByRole('dialog')
  const filter = dialog.getByRole('textbox', { name: '搜索通知' })
  await filter.fill('量子计算')
  await dialog.getByRole('button', { name: /^应用/ }).click()
  await expect(page).toHaveURL(/q=%E9%87%8F%E5%AD%90%E8%AE%A1%E7%AE%97/)
  await expect(page.getByRole('link', { name: /E2E 量子计算讲座报名/ })).toBeVisible()
  await expect(page.getByText('E2E 普通校园活动')).toHaveCount(0)
  await page.getByRole('button', { name: '筛选' }).click()
  const clearDialog = page.getByRole('dialog')
  const clearFilter = clearDialog.getByRole('textbox', { name: '搜索通知' })
  await clearFilter.clear()
  await clearDialog.getByRole('button', { name: /^应用/ }).click()
  await expect(page).not.toHaveURL(/q=/)
  await expect(page.getByRole('link', { name: /E2E 普通校园活动/ })).toBeVisible()
})

test('Notices date filter changes the real API result', async ({ page, request }) => {
  const seeded = await (await request.get(`${backendUrl}/api/notices/101`)).json()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/notices')
  await expect(page.getByText('当前结果 15 条 · 未读 3 条')).toBeVisible()
  await page.getByRole('button', { name: '筛选' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('起始日期').fill(seeded.publish_date)
  await dialog.getByRole('button', { name: /^应用/ }).click()

  await expect(dialog).toHaveCount(0)
  await expect(page).toHaveURL(new RegExp(`date_from=${seeded.publish_date}`))
  await expect(page.getByText('当前结果 2 条 · 未读 2 条')).toBeVisible()
  await expect(page.getByText('E2E 已收藏实验室招募')).toHaveCount(0)
})

test('Notices source filter changes the real API result', async ({ page }) => {
  await page.goto('/notices')
  await page.getByRole('button', { name: '筛选' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('来源').selectOption('ccst')
  await dialog.getByRole('button', { name: /^应用/ }).click()

  await expect(page).toHaveURL(/source=ccst/)
  await expect(page.getByText('当前结果 2 条 · 未读 0 条')).toBeVisible()
  await expect(page.getByRole('link', { name: /E2E 已收藏实验室招募/ })).toBeVisible()
  await expect(page.getByText('E2E 蓝桥杯竞赛通知')).toHaveCount(0)
})

test('Notices read-state filter changes the real API result', async ({ page }) => {
  await page.goto('/notices')
  await page.getByRole('button', { name: '筛选' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('阅读状态').selectOption('unread')
  await dialog.getByRole('button', { name: /^应用/ }).click()

  await expect(page).toHaveURL(/read=0/)
  await expect(page.getByText('当前结果 3 条 · 未读 3 条')).toBeVisible()
  await expect(page.getByRole('link', { name: /E2E 未读奖学金申请通知/ })).toBeVisible()
  await expect(page.getByText('E2E 量子计算讲座报名')).toHaveCount(0)
})

test('Notices pagination uses the current filtered total_count', async ({ page }) => {
  await page.goto('/notices?source=cse&page_size=10')

  await expect(page.getByText('当前结果 11 条 · 未读 3 条')).toBeVisible()
  await expect(page.getByText('1–10 / 11 条')).toBeVisible()
  await expect(page.getByText('第 1 / 2 页')).toBeVisible()
  await page.getByRole('button', { name: '下一页' }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.getByText('11–11 / 11 条')).toBeVisible()
})

test('Clearing Notices filters restores the complete list', async ({ page }) => {
  await page.goto('/notices?source=ccst')
  await expect(page.getByText('当前结果 2 条 · 未读 0 条')).toBeVisible()
  await page.getByRole('button', { name: '筛选 1' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: '重置' }).click()
  await dialog.getByRole('button', { name: '应用' }).click()

  await expect(page).toHaveURL(/\/notices$/)
  await expect(page.getByText('当前结果 15 条 · 未读 3 条')).toBeVisible()
  await expect(page.getByRole('link', { name: /E2E 蓝桥杯竞赛通知/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /E2E 已收藏实验室招募/ })).toBeVisible()
})

test('Favorite → Favorites → unfavorite updates membership', async ({ page }) => {
  await page.goto('/notices/102')
  const detailToolbar = page.getByRole('toolbar', { name: '通知操作' })
  await detailToolbar.getByRole('button', { name: '收藏通知' }).click()
  await expect(detailToolbar.getByRole('button', { name: '取消收藏' })).toBeVisible()
  await page.goto('/favorites')
  await page.getByRole('link', { name: /E2E 量子计算讲座报名/ }).click()
  await expect(page).toHaveURL(/\/notices\/102$/)
  await expect(page.getByRole('heading', { name: 'E2E 量子计算讲座报名', level: 1 })).toBeVisible()
  await detailToolbar.getByRole('button', { name: '取消收藏' }).click()
  await expect(detailToolbar.getByRole('button', { name: '收藏通知' })).toBeVisible()
  await page.goto('/favorites')
  await expect(page.getByText('E2E 量子计算讲座报名')).toHaveCount(0)
})

test('Inline search opens the correct detail without a modal', async ({ page }) => {
  await page.goto('/')
  const search = await openSearch(page)
  await search.fill('量子计算')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  const result = page.getByRole('listbox').getByRole('option', { name: /E2E 量子计算讲座报名/ })
  await expect(result).toBeVisible()
  await result.click()
  await expect(page).toHaveURL(/\/notices\/102$/)
  await expect(page.getByRole('heading', { name: 'E2E 量子计算讲座报名', level: 1 })).toBeVisible()
})

test('Header bell and avatar expose real keyboard-accessible popovers', async ({ page }) => {
  await page.goto('/notices/102')

  const bell = page.getByRole('button', { name: /提醒中心/ })
  await bell.focus()
  await bell.press('Enter')
  const summary = page.getByRole('dialog', { name: '提醒中心' })
  await expect(summary).toBeVisible()
  await expect(summary.getByText('最近提醒')).toBeVisible()
  await expect(summary.getByText(/条未读提醒/)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(summary).toHaveCount(0)
  await expect(bell).toBeFocused()

  const avatar = page.getByRole('button', { name: '应用菜单' })
  await avatar.focus()
  await avatar.press('Space')
  const menu = page.getByRole('menu', { name: '应用菜单' })
  await expect(menu).toBeVisible()
  await expect(menu.getByRole('menuitem', { name: '设置' })).toBeFocused()
  await menu.getByRole('menuitem', { name: '设置' }).click()
  await expect(page).toHaveURL(/\/settings$/)
})

test('Auto-read removes an unread notice from the unread view', async ({ page }) => {
  const readResponse = page.waitForResponse(response => response.url().endsWith('/api/notices/101/read') && response.request().method() === 'POST')
  await page.goto('/notices/101')
  await readResponse
  await page.goto('/notices?read=0')
  await expect(page.getByText('E2E 未读奖学金申请通知')).toHaveCount(0)
  await expect(page.getByRole('link', { name: /E2E 蓝桥杯竞赛通知/ })).toBeVisible()
})

test('Mark unread applies once and remains unread after cache reconciliation', async ({ page, request }) => {
  await page.goto('/notices/102')
  const toolbar = page.getByRole('toolbar', { name: '通知操作' })
  const response = page.waitForResponse(item => item.url().endsWith('/api/notices/102/unread') && item.request().method() === 'POST')
  await toolbar.getByRole('button', { name: '标记为未读' }).click()
  await response
  await expect(toolbar.getByRole('button', { name: '标记为已读' })).toBeVisible()
  const detailResponse = await request.get(`${backendUrl}/api/notices/102`)
  expect((await detailResponse.json()).is_read).toBeFalsy()
})

test('A manually unread notice becomes read when its detail is entered again', async ({ page, request }) => {
  await setState(request, 102, 'favorite')
  await page.goto('/notices/102')
  const toolbar = page.getByRole('toolbar', { name: '通知操作' })
  await expect(toolbar.getByRole('button', { name: '取消收藏' })).toBeVisible()

  const unreadResponse = page.waitForResponse(item => item.url().endsWith('/api/notices/102/unread') && item.request().method() === 'POST')
  await toolbar.getByRole('button', { name: '标记为未读' }).click()
  await unreadResponse
  await expect(toolbar.getByRole('button', { name: '标记为已读' })).toBeVisible()

  await page.goto('/notices/103')
  await expect(page.getByRole('heading', { name: 'E2E 已收藏实验室招募', level: 1 })).toBeVisible()
  const rereadResponse = page.waitForResponse(item => item.url().endsWith('/api/notices/102/read') && item.request().method() === 'POST')
  await page.goto('/notices/102')
  await rereadResponse

  await expect(page.getByRole('toolbar', { name: '通知操作' }).getByRole('button', { name: '标记为未读' })).toBeVisible()
  await expect(page.getByRole('toolbar', { name: '通知操作' }).getByRole('button', { name: '取消收藏' })).toBeVisible()
  const detailResponse = await request.get(`${backendUrl}/api/notices/102`)
  const reopened = await detailResponse.json()
  expect(reopened.is_read).toBeTruthy()
  expect(reopened.is_favorite).toBeTruthy()
})

test('Unread filtering keeps the independent all-notice count', async ({ page, request }) => {
  const dashboard = await (await request.get(`${backendUrl}/api/dashboard`)).json()
  await page.goto('/notices')
  const sidebar = page.getByRole('navigation', { name: '主导航' })
  await expect(sidebar.getByRole('link', { name: '全部通知' })).toContainText(String(dashboard.total_count))
  await page.getByRole('tab', { name: '未读' }).click()
  await expect(page).toHaveURL(/read=0/)
  await expect(sidebar.getByRole('link', { name: '全部通知' })).toContainText(String(dashboard.total_count))
})

test('Cloud Shared Source can be previewed, authenticated, created and viewed at desktop/mobile sizes', async ({ page }) => {
  await installCloudPromotionFixture(page)
  await page.goto('/sources')
  await page.getByRole('button', { name: '添加云端共享来源' }).click()
  await page.getByLabel('名称').fill('MOCK / FIXTURE 云端共享')
  await page.getByLabel('URL').fill('https://fixture.example.test/notices')
  await page.getByRole('button', { name: 'Test Fetch / Preview' }).click()
  await expect(page.getByText('Preview Result · 找到 1 条通知')).toBeVisible()
  await page.getByLabel('管理员密钥').fill('MOCK-FIXTURE-ADMIN')
  await page.getByRole('button', { name: '创建 Cloud Registry 记录' }).click()
  await expect(page.getByText('云端共享', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: '云端共享来源' })).toBeVisible()
  expect(await page.locator('body').evaluate(element => element.scrollWidth)).toBeLessThanOrEqual(390)
})

test('Settings persist after reload', async ({ page }) => {
  await page.goto('/settings')
  const theme = page.getByLabel('外观主题')
  await theme.selectOption('light')
  await expect(page.locator('html')).not.toHaveClass(/dark/)
  await page.reload()
  await expect(page.getByLabel('外观主题')).toHaveValue('light')
  await expect(page.locator('html')).not.toHaveClass(/dark/)
})

test('Storage management confirms manual cleanup and refreshes its statistics', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByText('可清理通知')).toBeVisible()
  await expect(page.getByText('1 条', { exact: true })).toBeVisible()
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.getByRole('button', { name: '清理旧通知' }).click()
    const preview = page.getByRole('dialog', { name: '清理旧通知' })
    await expect(preview).toContainText('包括未读、已收藏和高重要度通知')
    await expect(preview).toContainText('发布日期不明确的通知会保留')
    expect(await page.locator('body').evaluate(element => element.scrollWidth)).toBeLessThanOrEqual(width)
    await preview.getByRole('button', { name: '取消' }).click()
    await expect(page.getByText('1 条', { exact: true })).toBeVisible()
  }
  await page.getByRole('button', { name: '清理旧通知' }).click()
  const dialog = page.getByRole('dialog', { name: '清理旧通知' })
  await expect(dialog).toContainText('1 条超过 365 天的通知')
  const cleaned = page.waitForResponse(response => response.url().endsWith('/api/storage/cleanup') && response.request().method() === 'POST')
  await dialog.getByRole('button', { name: '确认清理' }).click()
  await cleaned
  await expect(page.getByText('0 条', { exact: true })).toBeVisible()
  await page.goto('/notices')
  await expect(page.getByText('E2E 可清理旧通知')).toHaveCount(0)
})

test('Unknown notice renders the dedicated 404 state', async ({ page }) => {
  await page.goto('/notices/999999')
  await expect(page.getByRole('heading', { name: '通知不存在', level: 1 })).toBeVisible()
  await expect(page.getByRole('link', { name: '返回通知列表' })).toBeVisible()
})

test('390px mobile smoke reaches Today through bottom navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('navigation', { name: '底部导航' }).getByRole('link', { name: '今日' }).click()
  await expect(page).toHaveURL(/\/today$/)
  await expect(page.getByRole('heading', { name: '今日新通知', level: 1 })).toBeVisible()
})

test('MOCK / FIXTURE local source promotes to cloud after admin-key confirmation', async ({ page }) => {
  await installCloudPromotionFixture(page)
  await page.goto('/sources')
  await expect(page.getByText('MOCK / FIXTURE 公开来源')).toBeVisible()
  await page.getByRole('button', { name: '编辑' }).click()
  await page.getByRole('button', { name: '测试并预览' }).click()
  await expect(page.getByText('找到 1 条通知')).toBeVisible()
  await page.getByRole('button', { name: '确认更新' }).click()
  await page.getByRole('button', { name: '上云' }).click()
  await page.getByLabel('管理员密钥').fill('MOCK-FIXTURE-ADMIN')
  await page.getByRole('button', { name: '确认' }).click()
  await expect(page.getByRole('heading', { name: '云端共享来源' })).toBeVisible()
  await expect(page.getByText('管理员强制上云')).toBeVisible()
})

test('MOCK / FIXTURE duplicate promotion links the existing cloud identity', async ({ page }) => {
  await installCloudPromotionFixture(page, { existing: true })
  await page.goto('/sources')
  await page.getByRole('button', { name: '上云' }).click()
  await page.getByLabel('管理员密钥').fill('MOCK-FIXTURE-ADMIN')
  await page.getByRole('button', { name: '确认' }).click()
  await expect(page.getByText('云端已有该来源，已完成本地关联')).toBeVisible()
  await expect(page.getByText('云端共享', { exact: true })).toBeVisible()
})

test('MOCK / FIXTURE cloud mapping survives page restart without local actions', async ({ page }) => {
  await installCloudPromotionFixture(page, { startCloud: true })
  await page.goto('/sources')
  await page.reload()
  await expect(page.getByText('云端共享', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '编辑' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '移出云端' })).toBeVisible()
})

test('MOCK / FIXTURE favorite and read state survive source promotion', async ({ page, request }) => {
  await installCloudPromotionFixture(page)
  await page.goto('/sources')
  await page.getByRole('button', { name: '上云' }).click()
  await page.getByLabel('管理员密钥').fill('MOCK-FIXTURE-ADMIN')
  await page.getByRole('button', { name: '确认' }).click()
  const notice = await request.get(`${backendUrl}/api/notices/106`)
  expect(notice.ok()).toBeTruthy()
  expect((await notice.json()).is_read).toBe(true)
  const favorite = await request.get(`${backendUrl}/api/notices?favorite=true&q=promotion%20state`)
  expect(favorite.ok()).toBeTruthy()
  expect((await favorite.json()).total).toBe(1)
})

test('new notification event opens its notice detail from the Bell', async ({ page }) => {
  await page.goto('/notices')
  await page.getByRole('button', { name: /提醒中心/ }).click()
  const reminder = page.getByRole('dialog', { name: '提醒中心' }).getByRole('button', { name: /收到新通知.*E2E 普通校园活动/ })
  await expect(reminder).toBeVisible()
  await reminder.click()
  await expect(page).toHaveURL(/\/notices\/105$/)
  await expect(page.getByRole('heading', { level: 1, name: 'E2E 普通校园活动' })).toBeVisible()
})

test('restart-style regeneration does not duplicate a daily notification', async ({ page, request }) => {
  const before = await (await request.get(`${backendUrl}/api/notifications?limit=50`)).json()
  const countBefore = before.items.filter((item: { type: string }) => item.type === 'DAILY_SUMMARY').length
  expect((await request.post(`${backendUrl}/api/notifications/generate`)).ok()).toBeTruthy()
  await page.goto('/notices')
  await page.reload()
  expect((await request.post(`${backendUrl}/api/notifications/generate`)).ok()).toBeTruthy()
  const after = await (await request.get(`${backendUrl}/api/notifications?limit=50`)).json()
  expect(after.items.filter((item: { type: string }) => item.type === 'DAILY_SUMMARY')).toHaveLength(countBefore)
})

test('deadline reminder is generated once for the configured lead day', async ({ request }) => {
  await request.post(`${backendUrl}/api/notifications/generate`)
  await request.post(`${backendUrl}/api/notifications/generate`)
  const events = await (await request.get(`${backendUrl}/api/notifications?limit=50`)).json()
  const reminders = events.items.filter((item: { type: string; notice_id: number }) => item.type === 'DEADLINE_APPROACHING' && item.notice_id === 107)
  expect(reminders).toHaveLength(1)
  expect(reminders[0].body).toContain('还有 3 天截止')
})

test('daily summary contains local aggregate counts', async ({ request }) => {
  const events = await (await request.get(`${backendUrl}/api/notifications?limit=50`)).json()
  const summary = events.items.find((item: { type: string }) => item.type === 'DAILY_SUMMARY')
  expect(summary).toBeTruthy()
  expect(summary.title).toBe('Notice Hub 今日摘要')
  expect(summary.body).toMatch(/新增 \d+ · 重要 \d+ · 即将截止 \d+ · 未读 \d+/)
})

test('desktop reminder preference persists and denied permission shows actionable guidance', async ({ page }) => {
  await page.goto('/settings')
  const master = page.getByRole('switch', { name: '桌面提醒' })
  await expect(master).toHaveAttribute('aria-checked', 'true')
  await master.click()
  await expect(master).toHaveAttribute('aria-checked', 'false')
  await page.reload()
  await expect(page.getByRole('switch', { name: '桌面提醒' })).toHaveAttribute('aria-checked', 'false')

  await page.getByRole('switch', { name: '桌面提醒' }).click()
  const dialog = page.getByRole('dialog', { name: '开启桌面提醒' })
  await expect(dialog).toContainText('Windows 设置 → 系统 → 通知')
  await dialog.getByRole('button', { name: '取消' }).click()
  await expect(page.getByRole('switch', { name: '桌面提醒' })).toHaveAttribute('aria-checked', 'false')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('switch', { name: '桌面提醒' }).click()
  await expect(dialog.getByRole('button', { name: '打开 Windows 通知设置' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await dialog.getByRole('button', { name: '打开 Windows 通知设置' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('switch', { name: '桌面提醒' })).toHaveAttribute('aria-checked', 'false')
})
