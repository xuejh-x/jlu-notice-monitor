import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createImportanceRule, getImportanceRules, restoreImportanceDefaults, updateImportanceRule } from '../api/importance'
import { ThemeProvider } from '../stores/theme'
import { ToastProvider } from '../stores/toast'
import { SettingsPage } from './SettingsPage'

vi.mock('../api/importance', () => ({
  getImportanceRules: vi.fn(), createImportanceRule: vi.fn(), updateImportanceRule: vi.fn(),
  deleteImportanceRule: vi.fn(), restoreImportanceDefaults: vi.fn(),
}))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><ThemeProvider><ToastProvider><SettingsPage/></ToastProvider></ThemeProvider></QueryClientProvider>)
}

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.clear(); vi.clearAllMocks()
    vi.mocked(getImportanceRules).mockResolvedValue([{ id: 1, keyword: 'PWN', weight: 8, enabled: true, is_system_default: true }])
  })

  it('organizes existing controls and the personal importance editor', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: '设置' })).toBeInTheDocument()
    for (const section of ['外观', '通知偏好', '个人重要度', '阅读与显示']) expect(screen.getByRole('heading', { level: 2, name: section })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '外观主题' })).toBeInTheDocument()
    expect(await screen.findByDisplayValue('PWN')).toBeInTheDocument()
  })

  it('keeps the existing local settings persistence behavior', () => {
    renderPage()
    fireEvent.change(screen.getByRole('combobox', { name: '优先关注阈值' }), { target: { value: '80' } })
    expect(JSON.parse(localStorage.getItem('jlu-settings') ?? '{}')).toMatchObject({ priorityThreshold: 80 })
  })

  it('shows score guidance on mouse hover and keyboard focus', async () => {
    renderPage(); await screen.findByDisplayValue('PWN')
    const help = screen.getByRole('button', { name: '查看分值参考' })
    fireEvent.mouseEnter(help.parentElement!)
    expect(screen.getByRole('tooltip')).toHaveTextContent('+25 ~ +35')
    fireEvent.mouseLeave(help.parentElement!); expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.focus(help); expect(screen.getByRole('tooltip')).toHaveTextContent('最终重要度还会综合分类')
  })

  it('validates weights, adds keywords and saves a changed rule', async () => {
    vi.mocked(createImportanceRule).mockResolvedValue({ id: 2, keyword: 'Linux', weight: 10, enabled: true, is_system_default: false })
    vi.mocked(updateImportanceRule).mockResolvedValue({ id: 1, keyword: 'PWN', weight: 35, enabled: true, is_system_default: false })
    renderPage(); await screen.findByDisplayValue('PWN')
    const newKeyword = screen.getByRole('textbox', { name: '新关键词' }); const newWeight = screen.getByRole('spinbutton', { name: '新关键词分值' })
    fireEvent.change(newKeyword, { target: { value: 'Linux' } }); fireEvent.change(newWeight, { target: { value: '60' } })
    expect(screen.getByRole('button', { name: /添加关键词/ })).toBeDisabled()
    fireEvent.change(newWeight, { target: { value: '10' } }); fireEvent.click(screen.getByRole('button', { name: /添加关键词/ }))
    await waitFor(() => expect(createImportanceRule).toHaveBeenCalledWith('Linux', 10))
    fireEvent.change(screen.getByRole('spinbutton', { name: 'PWN 分值' }), { target: { value: '35' } })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(updateImportanceRule).toHaveBeenCalledWith(1, { keyword: 'PWN', weight: 35 }))
  })

  it('requires confirmation before restoring defaults', async () => {
    vi.mocked(restoreImportanceDefaults).mockResolvedValue({ rescored: 12 })
    renderPage(); await screen.findByDisplayValue('PWN')
    fireEvent.click(screen.getByRole('button', { name: '恢复系统默认' }))
    expect(restoreImportanceDefaults).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '确认恢复' }))
    await waitFor(() => expect(restoreImportanceDefaults).toHaveBeenCalledTimes(1))
  })
})
