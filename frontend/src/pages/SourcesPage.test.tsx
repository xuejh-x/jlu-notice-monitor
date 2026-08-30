import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getSources } from '../api/sources'
import { SourcesPage } from './SourcesPage'

vi.mock('../api/sources', () => ({ getSources: vi.fn() }))
vi.mock('../components/ui/ExternalAnchor', () => ({
  ExternalAnchor: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a>,
}))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><SourcesPage/></MemoryRouter></QueryClientProvider>)
}

describe('SourcesPage', () => {
  beforeEach(() => vi.mocked(getSources).mockReset())

  it('distinguishes healthy and disabled sources and only links safe URLs', async () => {
    vi.mocked(getSources).mockResolvedValue([
      { id: 1, code: 'cse', name: '网络安全学院', base_url: 'https://example.test', enabled: true, last_checked_at: null, last_success_at: null, last_error: null, consecutive_errors: 0, status: 'healthy', message: null, notice_count: 12 },
      { id: 2, code: 'oa', name: 'OA', base_url: 'javascript:alert(1)', enabled: false, last_checked_at: null, last_success_at: null, last_error: '历史错误', consecutive_errors: 1, status: 'disabled', message: '尚未完成首次登录配置', notice_count: 0 },
    ])
    renderPage()

    expect(await screen.findByText('运行正常')).toBeInTheDocument()
    expect(screen.getByText('已停用')).toBeInTheDocument()
    expect(screen.getByText('尚未完成首次登录配置')).toBeInTheDocument()
    expect(screen.queryByText('历史错误')).not.toBeInTheDocument()
    const links = screen.getAllByRole('link', { name: /访问来源网站/ })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', 'https://example.test')
    expect(screen.getByText('来源网站地址不可用')).toBeInTheDocument()
  })

  it('renders a true empty state', async () => {
    vi.mocked(getSources).mockResolvedValue([])
    renderPage()
    expect(await screen.findByRole('heading', { name: '当前没有配置的数据源' })).toBeInTheDocument()
  })
})

