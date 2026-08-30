import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ThemeProvider } from '../stores/theme'
import { ToastProvider } from '../stores/toast'
import { SettingsPage } from './SettingsPage'

function renderPage() {
  return render(<ThemeProvider><ToastProvider><SettingsPage/></ToastProvider></ThemeProvider>)
}

describe('SettingsPage', () => {
  beforeEach(() => localStorage.clear())

  it('organizes real controls with visible accessible labels', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: '设置' })).toBeInTheDocument()
    for (const section of ['外观', '通知偏好', '阅读与显示']) expect(screen.getByRole('heading', { level: 2, name: section })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '外观主题' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '优先关注阈值' })).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: '精简优先列表' })).toHaveAttribute('aria-checked', 'false')
  })

  it('keeps the existing local settings persistence behavior', () => {
    renderPage()
    fireEvent.change(screen.getByRole('combobox', { name: '优先关注阈值' }), { target: { value: '80' } })
    expect(JSON.parse(localStorage.getItem('jlu-settings') ?? '{}')).toMatchObject({ priorityThreshold: 80 })
    expect(screen.getByText('通知偏好').parentElement).toHaveTextContent('不改变通知自身的“一般 / 重要 / 高相关”标签')
  })
})

