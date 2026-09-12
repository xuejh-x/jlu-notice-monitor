import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getCrawlerStatus } from '../api/crawler'
import { createCloudSource, createSource, getSourceConfiguration, previewSource, promoteSource, reauthenticateSource, setCloudPolicy, setSourceEnabled } from '../api/sources'
import { ToastProvider } from '../stores/toast'
import type { SourceConfiguration } from '../types'
import { SourcesPage } from './SourcesPage'

vi.mock('../api/sources', () => ({
  getSourceConfiguration: vi.fn(), previewSource: vi.fn(), createSource: vi.fn(), createCloudSource: vi.fn(), editSource: vi.fn(),
  setSourceSubscription: vi.fn(), setSourceEnabled: vi.fn(), checkSource: vi.fn(),
  reauthenticateSource: vi.fn(), deleteSource: vi.fn(), promoteSource: vi.fn(), setCloudPolicy: vi.fn(),
}))

vi.mock('../api/crawler', () => ({ getCrawlerStatus: vi.fn() }))

const official: SourceConfiguration = {
  id: 1, code: 'cse', name: '网络安全学院', base_url: 'https://example.test', ownership: 'OFFICIAL_CLOUD',
  source_type: 'official_adapter', parser: 'auto', parser_config: {}, subscribed: true, enabled: true,
  auth_type: 'none', username: null, password_saved: false, login_url: null, allow_private_network: false,
  health_state: 'healthy', last_error_code: null, last_error: null, last_checked_at: null,
  last_success_at: '2026-09-01T10:00:00', requires_reauthentication: false,
  source_identity: 'a'.repeat(64), cloud_source_id: 'cse', source_scope: 'official', execution: 'cloud',
  execution_policy: 'cloud_preferred',
  cloud_policy: 'auto', crawl_interval_seconds: null, validation_status: 'passed', validated_at: '2026-09-01T09:00:00',
}
const privateSource: SourceConfiguration = {
  ...official, id: 2, code: 'private-portal', name: '校内认证来源', ownership: 'CUSTOM_LOCAL_PRIVATE',
  source_type: 'private_browser', auth_type: 'browser_session', enabled: false, health_state: 'needs_reauth',
  execution_policy: 'local_only', execution: 'local', cloud_source_id: null, source_scope: 'private',
  requires_reauthentication: true, login_url: 'https://private.example.test/login',
}
const oaOfficial: SourceConfiguration = {
  ...official, id: 6, code: 'oa', name: '吉林大学 OA 校内通知', base_url: 'https://oa.jlu.edu.cn',
  source_type: 'official', parser: 'oa_public' as SourceConfiguration['parser'], auth_type: 'none',
  cloud_source_id: 'oa', cloud_policy: 'force_enabled', authentication_status: 'not_required', login_url: null,
}
const publicSource: SourceConfiguration = {
  ...official, id: 3, code: 'local-fixture', name: 'MOCK / FIXTURE 公开来源',
  ownership: 'CUSTOM_LOCAL_PUBLIC', source_scope: 'personal', execution: 'local', execution_policy: 'local_only', cloud_source_id: null,
}
const sharedSource: SourceConfiguration = {
  ...publicSource, ownership: 'SHARED_CLOUD', source_scope: 'shared', execution: 'cloud',
  execution_policy: 'cloud_only', cloud_source_id: 'shared-fixture', cloud_policy: 'force_enabled',
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><ToastProvider><MemoryRouter><SourcesPage/></MemoryRouter></ToastProvider></QueryClientProvider>)
}

describe('SourcesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, privateSource])
    vi.mocked(getCrawlerStatus).mockResolvedValue({
      running: false, status: 'success', current_started_at: null, last_run: null,
      last_duration: null, new_count: 0, updated_count: 0, source_results: [],
    })
  })

  it('renders subscriptions, cloud shared, and local sections with persistent re-login state', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: '我的订阅' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '云端共享来源' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '本地来源' })).toBeInTheDocument()
    expect(screen.getAllByText('需要重新登录').length).toBeGreaterThan(0)
    expect(screen.getByText('1 个来源需要重新登录')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重新登录/ })).toBeInTheDocument()
  })

  it('shows execution policies as read-only source metadata', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, sharedSource, publicSource])
    renderPage()
    expect(await screen.findByText('云端优先')).toBeInTheDocument()
    expect(screen.getByText('仅云端')).toBeInTheDocument()
    expect(screen.getByText('仅本地')).toBeInTheDocument()
  })

  it('shows cloud running and local fallback status from the latest source run', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, oaOfficial])
    vi.mocked(getCrawlerStatus).mockResolvedValue({
      running: false, status: 'success', current_started_at: null,
      last_run: '2026-09-12T08:00:00', last_duration: 2,
      new_count: 0, updated_count: 0, source_results: [
        {
          source: 'cse', status: 'success', execution_policy: 'cloud_preferred',
          effective_execution: 'cloud', fallback_used: false, fallback_reason: null,
          fetched: 0, new_count: 0, updated_count: 0, unchanged_count: 0, errors: [],
        },
        {
          source: 'oa', status: 'success', execution_policy: 'cloud_preferred',
          effective_execution: 'local', fallback_used: true,
          fallback_reason: 'PUBLIC_FEED_TIMEOUT', fetched: 1,
          new_count: 0, updated_count: 0, unchanged_count: 1, errors: [],
        },
      ],
    })
    renderPage()
    expect(await screen.findByText('云端运行')).toBeInTheDocument()
    expect(screen.getByText('本地回退生效')).toBeInTheDocument()
  })

  it('requires explicit authentication warning acknowledgement before enabling a private source', async () => {
    vi.mocked(setSourceEnabled).mockResolvedValue({ ...privateSource, enabled: true })
    renderPage()
    await screen.findByText('校内认证来源')
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

  it('tests, authenticates, and creates a Cloud Shared Source', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official])
    vi.mocked(previewSource).mockResolvedValue({ status: 'success', detected_type: 'api', found: 2, items: [{ title: 'API 通知', url: 'https://api.test/notices/1', publish_date: null, content_preview: '正文' }], preview_token: 'cloud-preview-token' })
    vi.mocked(createCloudSource).mockResolvedValue({ ...sharedSource, parser: 'api', name: '共享 API' })
    renderPage(); await screen.findByText('网络安全学院')
    fireEvent.click(screen.getByRole('button', { name: '添加云端共享来源' }))
    fireEvent.change(screen.getByLabelText('名称'), { target: { value: '共享 API' } })
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'https://api.test/notices' } })
    fireEvent.change(screen.getByLabelText('来源类型'), { target: { value: 'api' } })
    fireEvent.click(screen.getByRole('button', { name: 'Test Fetch / Preview' }))
    expect(await screen.findByText('Preview Result · 找到 2 条通知')).toBeInTheDocument()
    const key = screen.getByLabelText('管理员密钥')
    fireEvent.change(key, { target: { value: 'MOCK-FIXTURE-ADMIN' } })
    fireEvent.click(screen.getByRole('button', { name: '创建 Cloud Registry 记录' }))
    await waitFor(() => expect(createCloudSource).toHaveBeenCalledWith(
      expect.objectContaining({ name: '共享 API', parser: 'api', public_shared: true }),
      'cloud-preview-token',
      'MOCK-FIXTURE-ADMIN',
    ))
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

  it('opens advanced HTML selector mode after cloud auto-detect fails and retries with parser_config', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official])
    vi.mocked(previewSource)
      .mockRejectedValueOnce(new Error('This page is unsupported or needs advanced selector configuration'))
      .mockResolvedValueOnce({ status: 'success', detected_type: 'generic_html', found: 1, items: [{ title: 'Selector 通知', url: 'https://dynamic.test/1', publish_date: null, content_preview: '' }], preview_token: 'selector-preview' })
    renderPage(); await screen.findByText('网络安全学院')
    fireEvent.click(screen.getByRole('button', { name: '添加云端共享来源' }))
    fireEvent.change(screen.getByLabelText('名称'), { target: { value: '动态通知' } })
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'https://dynamic.test/notices' } })
    fireEvent.click(screen.getByRole('button', { name: 'Test Fetch / Preview' }))
    expect(await screen.findByLabelText('列表元素 Selector')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('列表元素 Selector'), { target: { value: '.notice-item' } })
    fireEvent.change(screen.getByLabelText('标题 Selector'), { target: { value: '.title' } })
    fireEvent.change(screen.getByLabelText('URL Selector'), { target: { value: 'a[href]' } })
    fireEvent.change(screen.getByLabelText('时间 Selector'), { target: { value: '.time' } })
    fireEvent.click(screen.getByRole('button', { name: 'Test Fetch / Preview' }))
    await waitFor(() => expect(previewSource).toHaveBeenLastCalledWith(expect.objectContaining({
      parser: 'generic_html',
      parser_config: expect.objectContaining({ type: 'html_selector', item_selector: '.notice-item', url_selector: 'a[href]', time_selector: '.time' }),
    })))
    expect(await screen.findByText('Preview Result · 找到 1 条通知')).toBeInTheDocument()
  })

  it('starts the explicit re-login action for a source that needs reauthentication', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    vi.mocked(reauthenticateSource).mockResolvedValue({
      status: 'manual_login_required', login_url: 'https://private.example.test/login', message: 'manual login',
    })
    renderPage(); await screen.findByText('校内认证来源')
    fireEvent.click(screen.getByRole('button', { name: /重新登录/ }))
    await waitFor(() => expect(reauthenticateSource).toHaveBeenCalledWith(2))
    expect(open).toHaveBeenCalledWith('https://private.example.test/login', '_blank', 'noopener,noreferrer')
    open.mockRestore()
  })

  it('renders OA 校内通知 as an official public source without authentication controls', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([official, oaOfficial])
    renderPage()
    const heading = await screen.findByRole('heading', { name: '吉林大学 OA 校内通知' })
    const row = heading.closest('article')
    expect(row).not.toBeNull()
    expect(screen.queryByRole('button', { name: /首次登录|重新登录|检测登录状态/ })).not.toBeInTheDocument()
    expect(row).not.toHaveTextContent('Cookie')
    expect(row).not.toHaveTextContent('认证：')
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
      execution_policy: 'cloud_only', cloud_source_id: 'shared-fixture', cloud_policy: 'force_enabled', promotion_reused: true,
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

  it('shows an unconfigured public feed as a neutral Cloud state without leaking the internal code', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([{
      ...official,
      health_state: 'source_error',
      last_error_code: 'SOURCE_ERROR',
      last_error: 'SourceError: PUBLIC_FEED_NOT_CONFIGURED',
      last_success_at: null,
    }])
    renderPage()
    expect(await screen.findByText('云端尚未配置')).toBeInTheDocument()
    expect(screen.getByText('等待 Notice Hub 公共源启用')).toBeInTheDocument()
    expect(screen.queryByText('来源异常')).not.toBeInTheDocument()
    expect(screen.queryByText(/PUBLIC_FEED_NOT_CONFIGURED/)).not.toBeInTheDocument()
    expect(screen.queryByText('SOURCE_ERROR')).not.toBeInTheDocument()
  })

  it('keeps a genuine source error in the danger state', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([{
      ...official,
      health_state: 'source_error',
      last_error_code: 'SOURCE_ERROR',
      last_error: 'SourceError: upstream returned malformed content',
    }])
    renderPage()
    expect(await screen.findByText('来源异常')).toBeInTheDocument()
    expect(screen.getByText('SourceError: upstream returned malformed content')).toBeInTheDocument()
    expect(screen.getByText(/SOURCE_ERROR/)).toBeInTheDocument()
    expect(screen.queryByText('云端尚未配置')).not.toBeInTheDocument()
  })

  it('keeps all creation entry points available when no sources exist', async () => {
    vi.mocked(getSourceConfiguration).mockResolvedValue([])
    renderPage()
    expect(await screen.findByRole('button', { name: '添加云端共享来源' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '添加公开来源' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '添加私有来源' })).toBeEnabled()
  })
})
