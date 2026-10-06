import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createImportanceRule, getImportanceRules, restoreImportanceDefaults, updateImportanceRule } from '../api/importance'
import { getNotificationPreferences, updateNotificationPreferences } from '../api/notifications'
import { cleanOldNotifications, getStorageStatus } from '../api/storage'
import { checkDesktopNotificationPermission, openWindowsNotificationSettings, requestDesktopNotificationPermission, sendDesktopNotificationTest } from '../services/desktopNotifications'
import { ThemeProvider } from '../stores/theme'
import { ToastProvider } from '../stores/toast'
import { SettingsPage } from './SettingsPage'

vi.mock('../api/importance', () => ({
  getImportanceRules: vi.fn(), createImportanceRule: vi.fn(), updateImportanceRule: vi.fn(),
  deleteImportanceRule: vi.fn(), restoreImportanceDefaults: vi.fn(),
}))
vi.mock('../api/notifications', () => ({ getNotificationPreferences: vi.fn(), updateNotificationPreferences: vi.fn() }))
vi.mock('../api/storage', () => ({ getStorageStatus: vi.fn(), cleanOldNotifications: vi.fn() }))
vi.mock('../services/desktopNotifications', () => ({
  checkDesktopNotificationPermission: vi.fn(() => Promise.resolve(true)),
  openWindowsNotificationSettings: vi.fn(() => Promise.resolve()),
  requestDesktopNotificationPermission: vi.fn(() => Promise.resolve(true)),
  sendDesktopNotificationTest: vi.fn(() => Promise.resolve()),
}))

const notificationPreferences = { enabled: false, new_notice_enabled: true, important_notice_enabled: true, deadline_enabled: true, source_health_enabled: true, daily_summary_enabled: true, minimum_importance: 70, deadline_lead_days: [7, 3, 1], quiet_start: '23:00', quiet_end: '08:00' }
const storageStatus = { database_size: '1.0 MB', database_size_bytes: 1048576, total_notifications: 12, cleanup_candidates: 2, last_cleanup_at: null, retention_days: 365, preserves_local_exceptions: false }

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><ThemeProvider><ToastProvider><SettingsPage/></ToastProvider></ThemeProvider></QueryClientProvider>)
}

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.clear(); vi.clearAllMocks()
    vi.mocked(getImportanceRules).mockResolvedValue([{ id: 1, keyword: 'PWN', weight: 8, enabled: true, is_system_default: true }])
    vi.mocked(getNotificationPreferences).mockResolvedValue(notificationPreferences)
    vi.mocked(updateNotificationPreferences).mockImplementation(async value => value)
    vi.mocked(checkDesktopNotificationPermission).mockResolvedValue(true)
    vi.mocked(requestDesktopNotificationPermission).mockResolvedValue(true)
    vi.mocked(openWindowsNotificationSettings).mockResolvedValue(undefined)
    vi.mocked(sendDesktopNotificationTest).mockResolvedValue(undefined)
    vi.mocked(getStorageStatus).mockResolvedValue(storageStatus)
    vi.mocked(cleanOldNotifications).mockResolvedValue({ ...storageStatus, total_notifications: 10, cleanup_candidates: 0, last_cleanup_at: '2026-09-13T12:00:00+00:00', deleted_count: 2 })
  })

  it('organizes existing controls and the personal importance editor', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: '设置' })).toBeInTheDocument()
    for (const section of ['外观', '通知偏好', '桌面提醒', '个人重要度', '存储管理', '阅读与显示']) expect(screen.getByRole('heading', { level: 2, name: section })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '外观主题' })).toBeInTheDocument()
    expect(await screen.findByDisplayValue('PWN')).toBeInTheDocument()
  })

  it('enables desktop notifications and sends a test notification when permission is granted', async () => {
    renderPage()
    const master = await screen.findByRole('switch', { name: '桌面提醒' })
    expect(await screen.findByText('🟢 Windows 通知已开启')).toBeInTheDocument()
    fireEvent.click(master)
    await waitFor(() => expect(updateNotificationPreferences).toHaveBeenCalledWith(expect.objectContaining({ enabled: true }), expect.anything()))
    await waitFor(() => expect(sendDesktopNotificationTest).toHaveBeenCalledTimes(1))
    expect(requestDesktopNotificationPermission).toHaveBeenCalledTimes(1)
    expect(vi.mocked(updateNotificationPreferences).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(sendDesktopNotificationTest).mock.invocationCallOrder[0])
    expect(await screen.findByRole('combobox', { name: '截止提前' })).toHaveValue('7,3,1')
    expect(screen.getByLabelText('静默开始')).toHaveValue('23:00')
  })

  it('keeps the preference off and shows permission guidance when permission is denied', async () => {
    vi.mocked(checkDesktopNotificationPermission).mockResolvedValue(false)
    vi.mocked(requestDesktopNotificationPermission).mockResolvedValue(false)
    renderPage()
    const master = await screen.findByRole('switch', { name: '桌面提醒' })
    expect(await screen.findByText('⚠️ 需要 Windows 通知权限')).toBeInTheDocument()
    fireEvent.click(master)
    expect(await screen.findByRole('dialog', { name: '开启桌面提醒' })).toHaveTextContent('Windows 设置 → 系统 → 通知')
    expect(master).toHaveAttribute('aria-checked', 'false')
    expect(updateNotificationPreferences).not.toHaveBeenCalled()
    expect(sendDesktopNotificationTest).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '开启桌面提醒' })).not.toBeInTheDocument())
    expect(master).toHaveAttribute('aria-checked', 'false')
  })

  it('opens Windows notification settings from the permission dialog', async () => {
    vi.mocked(checkDesktopNotificationPermission).mockResolvedValue(false)
    vi.mocked(requestDesktopNotificationPermission).mockResolvedValue(false)
    renderPage()
    fireEvent.click(await screen.findByRole('switch', { name: '桌面提醒' }))
    fireEvent.click(await screen.findByRole('button', { name: '打开 Windows 通知设置' }))
    await waitFor(() => expect(openWindowsNotificationSettings).toHaveBeenCalledTimes(1))
    expect(updateNotificationPreferences).not.toHaveBeenCalled()
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

  it('shows storage status and only runs cleanup after confirmation', async () => {
    renderPage()
    expect(await screen.findByText('1.0 MB')).toBeInTheDocument()
    expect(screen.getByText('2 条', { exact: true })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '清理旧通知' }))
    expect(cleanOldNotifications).not.toHaveBeenCalled()
    const dialog = screen.getByRole('dialog', { name: '清理旧通知' })
    expect(dialog).toHaveTextContent('2 条超过 365 天的通知')
    expect(dialog).toHaveTextContent('包括未读、已收藏和高重要度通知')
    expect(dialog).toHaveTextContent('发布日期不明确的通知会保留')
    fireEvent.click(screen.getByRole('button', { name: '确认清理' }))
    await waitFor(() => expect(cleanOldNotifications).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.getByText('0 条', { exact: true })).toBeInTheDocument())
  })
})
