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
}

async function openSearch(page: Page) {
  await page.getByRole('button', { name: /搜索/ }).first().click()
  return page.getByRole('dialog').getByRole('textbox', { name: '搜索通知' })
}

test.beforeEach(async ({ request }) => {
  await resetFixture(request)
})

test('Dashboard → Notice Detail', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('main').getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('heading', { name: '最近通知' })).toBeVisible()
  await page.getByRole('link', { name: /E2E 未读奖学金申请通知/ }).first().click()
  await expect(page).toHaveURL(/\/notices\/101$/)
  await expect(page.getByRole('heading', { name: 'E2E 未读奖学金申请通知', level: 1 })).toBeVisible()
})

test('Notices filter keeps URL, UI, and results aligned', async ({ page }) => {
  await page.goto('/notices')
  const filter = page.getByRole('textbox', { name: '搜索通知' })
  await filter.fill('量子计算')
  await expect(page).toHaveURL(/q=%E9%87%8F%E5%AD%90%E8%AE%A1%E7%AE%97/)
  await expect(page.getByRole('link', { name: /E2E 量子计算讲座报名/ })).toBeVisible()
  await expect(page.getByText('E2E 普通校园活动')).toHaveCount(0)
  await filter.clear()
  await expect(page).not.toHaveURL(/q=/)
  await expect(page.getByRole('link', { name: /E2E 普通校园活动/ })).toBeVisible()
})

test('Favorite → Favorites → unfavorite updates membership', async ({ page }) => {
  await page.goto('/notices/102')
  await page.getByRole('button', { name: '收藏通知' }).click()
  await expect(page.getByRole('button', { name: '取消收藏' })).toBeVisible()
  await page.goto('/favorites')
  await page.getByRole('link', { name: /E2E 量子计算讲座报名/ }).click()
  await expect(page).toHaveURL(/\/notices\/102$/)
  await expect(page.getByRole('heading', { name: 'E2E 量子计算讲座报名', level: 1 })).toBeVisible()
  await page.getByRole('button', { name: '取消收藏' }).click()
  await expect(page.getByRole('button', { name: '收藏通知' })).toBeVisible()
  await page.goto('/favorites')
  await expect(page.getByText('E2E 量子计算讲座报名')).toHaveCount(0)
})

test('Search dialog opens the correct detail', async ({ page }) => {
  await page.goto('/')
  const search = await openSearch(page)
  await search.fill('量子计算')
  const result = page.getByRole('dialog').getByRole('button', { name: /E2E 量子计算讲座报名/ })
  await expect(result).toBeVisible()
  await result.click()
  await expect(page).toHaveURL(/\/notices\/102$/)
  await expect(page.getByRole('heading', { name: 'E2E 量子计算讲座报名', level: 1 })).toBeVisible()
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
