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
}

const officialSource = {
  id: 1, code: 'e2e-main', name: 'E2E 教务通知', base_url: 'https://example.test/main', ownership: 'OFFICIAL_CLOUD',
  source_type: 'official_adapter', parser: 'auto', parser_config: {}, subscribed: true, enabled: true,
  auth_type: 'none', username: null, password_saved: false, login_url: null, allow_private_network: false,
  health_state: 'healthy', last_error_code: null, last_error: null, last_checked_at: null, last_success_at: null,
  requires_reauthentication: false, source_identity: 'a'.repeat(64), cloud_source_id: 'e2e-main',
  source_scope: 'official', execution: 'cloud', cloud_policy: 'auto', crawl_interval_seconds: null,
  validation_status: 'passed', validated_at: '2026-09-02T00:00:00',
}

const localSource = {
  ...officialSource, id: 3, code: 'e2e-local-fixture', name: 'MOCK / FIXTURE 公开来源',
  base_url: 'https://fixture.example.test/notices', ownership: 'CUSTOM_LOCAL_PUBLIC', source_type: 'public_html',
  source_identity: 'c'.repeat(64), cloud_source_id: null, source_scope: 'personal', execution: 'local',
}

async function installCloudPromotionFixture(page: Page, options: { existing?: boolean; startCloud?: boolean } = {}) {
  let source = options.startCloud ? {
    ...localSource, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud',
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
    if (request.method() === 'PATCH' && path.endsWith('/3')) {
      await route.fulfill({ json: source }); return
    }
    if (request.method() === 'POST' && path.endsWith('/promote')) {
      source = { ...source, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud', cloud_source_id: 'shared-e2e-fixture', cloud_policy: 'force_enabled', promotion_reused: Boolean(options.existing) }
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

  const bell = page.getByRole('button', { name: '通知摘要' })
  await bell.focus()
  await bell.press('Enter')
  const summary = page.getByRole('dialog', { name: '通知摘要' })
  await expect(summary).toBeVisible()
  await expect(summary.getByText('今日新增')).toBeVisible()
  await expect(summary.getByText('未读通知')).toBeVisible()
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

test('Settings persist after reload', async ({ page }) => {
  await page.goto('/settings')
  const theme = page.getByLabel('外观主题')
  await theme.selectOption('light')
  await expect(page.locator('html')).not.toHaveClass(/dark/)
  await page.reload()
  await expect(page.getByLabel('外观主题')).toHaveValue('light')
  await expect(page.locator('html')).not.toHaveClass(/dark/)
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
