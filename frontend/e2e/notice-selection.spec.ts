import { expect, test } from '@playwright/test'

const backendUrl = 'http://127.0.0.1:8010'

for (const width of [1440, 768, 390]) {
  for (const inPage of [true, false]) {
    test(`search selection ${inPage ? 'in page' : 'outside filters/page'} at ${width}px`, async ({ page, request }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      const response = await request.get(`${backendUrl}/api/notices/102`)
      expect(response.ok()).toBeTruthy()
      const target = await response.json()
      // A full, scrollable page. The detail and global search use the real API.
      const rows = Array.from({ length: 20 }, (_, index) => ({ ...target, id: 200 + index, title: `MOCK / FIXTURE 通知 ${index}` }))
      if (inPage) rows[19] = target
      await page.route('**/api/notices?**', route => route.fulfill({ json: {
        items: rows, total: 60, total_count: 60, unread_count: 0, all_count: 100, page: 2, page_size: 20, total_pages: 3,
      } }))
      const search = inPage ? '?page=2' : '?source=ccst&category=research&read=0&date_from=2099-01-01&page=2'
      await page.goto(`/notices${search}`)
      const list = page.getByRole('region', { name: '通知工作区', includeHidden: true })
      const reader = page.getByRole('complementary', { name: '通知详情工作区' })
      await expect(list.getByRole('link', { name: '打开MOCK / FIXTURE 通知 0' })).toBeVisible()
      const pane = list.locator('.overflow-y-auto')
      if (!inPage) await pane.evaluate(element => { element.scrollTop = element.scrollHeight })
      if (width < 768) await page.getByRole('button', { name: '搜索通知、学院或关键词' }).click()
      await page.getByRole('combobox', { name: '搜索通知', exact: true }).fill('量子计算')
      await page.getByRole('option', { name: /E2E 量子计算讲座报名/ }).click()
      await expect(page).toHaveURL(`/notices/102${search}`)
      await expect(reader.getByRole('heading', { level: 1, name: target.title })).toBeVisible()
      const selected = list.getByRole('link', { name: `打开${target.title}`, includeHidden: true })
      await expect(selected).toHaveAttribute('aria-current', 'page')
      await expect(list.locator('[aria-current="page"]')).toHaveCount(1)
      await expect(list.getByRole('region', { name: '当前打开的通知', includeHidden: true })).toHaveCount(inPage ? 0 : 1)

      if (width >= 1280) {
        await expect(selected).toBeInViewport()
        const bounds = await selected.boundingBox()
        const paneBounds = await pane.boundingBox()
        expect(bounds!.y).toBeGreaterThanOrEqual(paneBounds!.y)
        expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(paneBounds!.y + paneBounds!.height)
        const scrollTop = await pane.evaluate(element => element.scrollTop)
        if (inPage) expect(scrollTop).toBeGreaterThan(0)
        else expect(scrollTop).toBe(0)
        if (!inPage) {
          await page.reload()
          await expect(list.getByRole('link', { name: `打开${target.title}` })).toHaveAttribute('aria-current', 'page')
        }
      } else {
        await expect(list).toBeHidden()
        await page.setViewportSize({ width: 1440, height: 900 })
        await expect(selected).toBeInViewport()
        await page.setViewportSize({ width, height: 900 })
        await expect(list).toBeHidden()
      }
      await page.screenshot({ path: testInfo.outputPath('selected.png') })
      expect(await page.locator('body').evaluate(element => element.scrollWidth)).toBeLessThanOrEqual(width)
      expect(await page.evaluate(() => document.scrollingElement?.scrollTop)).toBe(0)
      if (width < 1280) {
        await reader.getByRole('link', { name: '返回通知列表' }).click()
        await expect(page).toHaveURL(`/notices${search}`)
        await expect(list).toBeVisible()
        await expect(list.locator('[aria-current="page"]')).toHaveCount(0)
        await expect(list.getByRole('region', { name: '当前打开的通知' })).toHaveCount(0)
        await page.screenshot({ path: testInfo.outputPath('returned-list.png') })
        expect(await page.locator('body').evaluate(element => element.scrollWidth)).toBeLessThanOrEqual(width)
      }
    })
  }
}
