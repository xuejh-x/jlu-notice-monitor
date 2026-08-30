import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SearchDialog } from './SearchDialog'

const notice = {
  id: 7, title: '算法竞赛报名通知', url: 'https://example.test/7', publish_date: '2026-08-30', publisher: '计算机学院',
  category: 'algorithm_competition', importance_score: 92, registration_start: null, registration_deadline: '2026-09-01',
  event_start: null, event_end: null, deadline_status: 'urgent', days_until_deadline: 2, status: 'new',
  first_seen_at: '2026-08-30T00:00:00Z', last_seen_at: '2026-08-30T00:00:00Z', updated_at: '2026-08-30T00:00:00Z',
  is_read: false, is_archived: false, is_favorite: false, sources: [{ code: 'ccst', name: '计算机学院' }],
}

function renderDialog() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><SearchDialog/></MemoryRouter></QueryClientProvider>)
}

async function searchFor(keyword: string) {
  fireEvent.click(screen.getByRole('button', { name: /搜索通知、学院或关键词/ }))
  const input = await screen.findByRole('textbox', { name: '搜索通知' })
  fireEvent.change(input, { target: { value: keyword } })
}

describe('SearchDialog', () => {
  beforeEach(() => vi.unstubAllGlobals())
  afterEach(() => vi.unstubAllGlobals())

  it('renders compact results with notice decision signals', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [notice], total: 1, page: 1, page_size: 20, total_pages: 1 }), { status: 200 })))
    renderDialog()
    await searchFor('算法')
    expect(await screen.findByRole('button', { name: /算法竞赛报名通知/ }, { timeout: 1200 })).toBeInTheDocument()
    expect(screen.getByText('高相关')).toBeInTheDocument()
    expect(screen.getByText('剩余 2 天')).toBeInTheDocument()
  })

  it('keeps search empty distinct from errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }), { status: 200 })))
    renderDialog()
    await searchFor('不存在')
    expect(await screen.findByText('没有匹配“不存在”的通知', {}, { timeout: 1200 })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '暂时无法完成请求' })).not.toBeInTheDocument()
  })

  it('renders a retryable error rather than a no-result message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: '搜索服务不可用' }), { status: 500 })))
    renderDialog()
    await searchFor('失败')
    expect(await screen.findByRole('heading', { name: '暂时无法完成请求' }, { timeout: 1200 })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新连接' })).toBeInTheDocument()
    expect(screen.queryByText(/没有匹配/)).not.toBeInTheDocument()
  })
})
