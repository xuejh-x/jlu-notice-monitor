import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createSource, getSourceConfiguration, previewSource, promoteSource, reauthenticateSource, setCloudPolicy, setSourceEnabled } from '../api/sources'
import { ToastProvider } from '../stores/toast'
import type { SourceConfiguration } from '../types'
import { SourcesPage } from './SourcesPage'

vi.mock('../api/sources', () => ({
  getSourceConfiguration: vi.fn(), previewSource: vi.fn(), createSource: vi.fn(), editSource: vi.fn(),
  setSourceSubscription: vi.fn(), setSourceEnabled: vi.fn(), checkSource: vi.fn(),
  reauthenticateSource: vi.fn(), deleteSource: vi.fn(), promoteSource: vi.fn(), setCloudPolicy: vi.fn(),
}))

const official: SourceConfiguration = {
  id: 1, code: 'cse', name: '网络安全学院', base_url: 'https://example.test', ownership: 'OFFICIAL_CLOUD',
  source_type: 'official_adapter', parser: 'auto', parser_config: {}, subscribed: true, enabled: true,
  auth_type: 'none', username: null, password_saved: false, login_url: null, allow_private_network: false,
  health_state: 'healthy', last_error_code: null, last_error: null, last_checked_at: null,
  last_success_at: '2026-09-01T10:00:00', requires_reauthentication: false,
  source_identity: 'a'.repeat(64), cloud_source_id: 'cse', source_scope: 'official', execution: 'cloud',
  cloud_policy: 'auto', crawl_interval_seconds: null, validation_status: 'passed', validated_at: '2026-09-01T09:00:00',
}
const privateSource: SourceConfiguration = {
  ...official, id: 2, code: 'local-oa', name: '吉林大学 OA', ownership: 'CUSTOM_LOCAL_PRIVATE',
  source_type: 'private_browser', auth_type: 'browser_session', enabled: false, health_state: 'needs_reauth',
  requires_reauthentication: true, login_url: 'https://oa.example.test/login',
}
const publicSource: SourceConfiguration = {
  ...official, id: 3, code: 'local-fixture', name: 'MOCK / FIXTURE 公开来源',
  ownership: 'CUSTOM_LOCAL_PUBLIC', source_scope: 'personal', execution: 'local', cloud_source_id: null,
}
const sharedSource: SourceConfiguration = {
  ...publicSource, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud',
  cloud_source_id: 'shared-fixture', cloud_policy: 'force_enabled',
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><ToastProvider><MemoryRouter><SourcesPage/></MemoryRouter></ToastProvider></QueryClientProvider>)
}

describe('SourcesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, privateSource])
  })

  it('renders official, public and private sections with persistent re-login state', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: '官方来源' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '我的公开来源' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '我的私有来源' })).toBeInTheDocument()
    expect(screen.getAllByText('需要重新登录').length).toBeGreaterThan(0)
    expect(screen.getByText('1 个来源需要重新登录')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重新登录/ })).toBeInTheDocument()
  })

  it('requires explicit authentication warning acknowledgement before enabling a private source', async () => {
    vi.mocked(setSourceEnabled).mockResolvedValue({ ...privateSource, enabled: true })
    renderPage()
    await screen.findByText('吉林大学 OA')
    fireEvent.click(screen.getByRole('button', { name: '启用' }))
    expect(screen.getByText('此来源需要登录后才能自动抓取。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '继续并登录' }))
    await waitFor(() => expect(setSourceEnabled).toHaveBeenCalledWith(2, true, true))
  })

  it('tests and previews a custom public source before confirmation', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official])
    vi.mocked(previewSource).mockResolvedValue({ status: 'success', detected_type: 'rss', found: 20, items: [{ title: '第一条通知', url: 'https://lab.test/1', publish_date: null, content_preview: '正文' }], preview_token: 'preview-token' })
    vi.mocked(createSource).mockResolvedValue({ ...official, id: 3, code: 'local-3', name: '实验室通知', ownership: 'CUSTOM_LOCAL_PUBLIC' })
    renderPage(); await screen.findByText('网络安全学院')
    fireEvent.click(screen.getByRole('button', { name: /添加公开来源/ }))
    fireEvent.change(screen.getByLabelText('名称'), { target: { value: '实验室通知' } })
    fireEvent.change(screen.getByLabelText('通知列表 URL'), { target: { value: 'https://lab.test/notices' } })
    expect(screen.getByRole('button', { name: '确认添加' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '测试并预览' }))
    expect(await screen.findByText('找到 20 条通知')).toBeInTheDocument()
    expect(screen.getByText('第一条通知')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认添加' }))
    await waitFor(() => expect(createSource).toHaveBeenCalledWith(expect.objectContaining({ name: '实验室通知' }), 'preview-token'))
  })

  it('keeps confirmation disabled when preview fails', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official])
    vi.mocked(previewSource).mockRejectedValue(new Error('unsupported structure'))
    renderPage(); await screen.findByText('网络安全学院')
    fireEvent.click(screen.getByRole('button', { name: /添加公开来源/ }))
    fireEvent.change(screen.getByLabelText('名称'), { target: { value: '不支持页面' } })
    fireEvent.change(screen.getByLabelText('通知列表 URL'), { target: { value: 'https://unsupported.test/notices' } })
    fireEvent.click(screen.getByRole('button', { name: '测试并预览' }))
    await waitFor(() => expect(previewSource).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('button', { name: '确认添加' })).toBeDisabled()
    expect(createSource).not.toHaveBeenCalled()
  })

  it('starts the explicit re-login action for a source that needs reauthentication', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    vi.mocked(reauthenticateSource).mockResolvedValue({
      status: 'manual_login_required', login_url: 'https://oa.example.test/login', message: 'manual login',
    })
    renderPage(); await screen.findByText('吉林大学 OA')
    fireEvent.click(screen.getByRole('button', { name: /重新登录/ }))
    await waitFor(() => expect(reauthenticateSource).toHaveBeenCalledWith(2))
    expect(open).toHaveBeenCalledWith('https://oa.example.test/login', '_blank', 'noopener,noreferrer')
    open.mockRestore()
  })

  it('requires a successful test and opens a non-persistent admin-key dialog for promotion', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, { ...publicSource, validation_status: 'untested', validated_at: null }])
    renderPage(); await screen.findByText('MOCK / FIXTURE 公开来源')
    expect(screen.getByRole('button', { name: '上云' })).toBeDisabled()
  })

  it('clears a wrong admin key and reports the cloud error', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, publicSource])
    vi.mocked(promoteSource).mockRejectedValue(new Error('管理员授权失败'))
    renderPage(); await screen.findByText('MOCK / FIXTURE 公开来源')
    fireEvent.click(screen.getByRole('button', { name: '上云' }))
    const key = screen.getByLabelText('管理员密钥')
    expect(key).toHaveAttribute('type', 'password')
    fireEvent.change(key, { target: { value: 'wrong-key' } })
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('管理员授权失败')
    expect(key).toHaveValue('')
    expect(promoteSource).toHaveBeenCalledWith(3, 'wrong-key')
  })

  it('maps an already-existing cloud source and clears the admin-key dialog', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, publicSource])
    vi.mocked(promoteSource).mockResolvedValue({
      ...publicSource, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud',
      cloud_source_id: 'shared-fixture', cloud_policy: 'force_enabled', promotion_reused: true,
    })
    renderPage(); await screen.findByText('MOCK / FIXTURE 公开来源')
    fireEvent.click(screen.getByRole('button', { name: '上云' }))
    fireEvent.change(screen.getByLabelText('管理员密钥'), { target: { value: 'MOCK-FIXTURE-ADMIN' } })
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => expect(promoteSource).toHaveBeenCalledWith(3, 'MOCK-FIXTURE-ADMIN'))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('云端已有该来源，已完成本地关联')).toBeInTheDocument()
  })

  it('shows forced-cloud state and requires the admin key for a safe policy change', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, sharedSource])
    vi.mocked(setCloudPolicy).mockResolvedValue({ ...sharedSource, cloud_policy: 'force_disabled' })
    renderPage(); await screen.findByText('管理员强制上云')
    fireEvent.click(screen.getByRole('button', { name: '移出云端' }))
    fireEvent.change(screen.getByLabelText('管理员密钥'), { target: { value: 'MOCK-FIXTURE-ADMIN' } })
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => expect(setCloudPolicy).toHaveBeenCalledWith(3, 'force_disabled', 'MOCK-FIXTURE-ADMIN'))
  })

  it('renders a true empty state', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([])
    renderPage()
    expect(await screen.findByRole('heading', { name: '当前没有配置的数据源' })).toBeInTheDocument()
  })
})
