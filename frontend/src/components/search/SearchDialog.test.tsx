import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
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
  function LocationProbe() { const location = useLocation(); return <output data-testid="location">{location.pathname}</output> }
  return render(<QueryClientProvider client={client}><MemoryRouter><SearchDialog/><textarea aria-label="其他输入"/><LocationProbe/></MemoryRouter></QueryClientProvider>)
}

async function searchFor(keyword: string) {
  const input = screen.getByRole('combobox', { name: '搜索通知' })
  fireEvent.change(input, { target: { value: keyword } })
  return input
}

describe('SearchDialog', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders compact results with notice decision signals', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [notice], total: 1, page: 1, page_size: 20, total_pages: 1 }), { status: 200 })))
    renderDialog()
    await searchFor('算法')
    expect(await screen.findByRole('option', { name: /算法竞赛报名通知/ }, { timeout: 1200 })).toBeInTheDocument()
    expect(screen.getByText('高相关')).toBeInTheDocument()
    expect(screen.getByText('2 天后截止')).toBeInTheDocument()
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

  it('focuses and selects the inline field with Ctrl+K without opening a dialog', async () => {
    vi.stubGlobal('fetch', vi.fn())
    renderDialog()
    const input = screen.getByRole('combobox', { name: '搜索通知' })
    fireEvent.change(input, { target: { value: '已有关键词' } })
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    await waitFor(() => expect(input).toHaveFocus())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    const otherInput = screen.getByRole('textbox', { name: '其他输入' })
    otherInput.focus()
    fireEvent.keyDown(otherInput, { key: 'k', ctrlKey: true })
    expect(otherInput).toHaveFocus()
  })

  it('supports Escape, clear, arrow navigation, and Enter selection', async () => {
    const second = { ...notice, id: 8, title: '第二条算法通知' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [notice, second], total: 2, page: 1, page_size: 20, total_pages: 1 }), { status: 200 })))
    renderDialog()
    const input = await searchFor('算法')
    await screen.findByRole('option', { name: /第二条算法通知/ }, { timeout: 1200 })
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(input).toHaveAttribute('aria-expanded', 'false')
    fireEvent.focus(input)
    expect(input).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(screen.getByRole('button', { name: '清空搜索' }))
    expect(input).toHaveValue('')

    fireEvent.change(input, { target: { value: '算法' } })
    await screen.findByRole('option', { name: /第二条算法通知/ }, { timeout: 1200 })
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    await waitFor(() => expect(input.getAttribute('aria-activedescendant')).toContain('option-7'))
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    await waitFor(() => expect(input.getAttribute('aria-activedescendant')).toContain('option-8'))
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.getByTestId('location')).toHaveTextContent('/notices/8')
  })
})
