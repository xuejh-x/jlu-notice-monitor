import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/client'
import { ErrorState, PageSkeleton } from './Feedback'

describe('ErrorState', () => {
  it('keeps aborted requests silent', () => {
    const retry = vi.fn()
    const { container } = render(<ErrorState error={new ApiError({ kind: 'ABORTED', message: '请求已取消', endpoint: '/api/test' })} retry={retry}/>)
    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByText('请求已取消')).not.toBeInTheDocument()
  })

  it('announces asynchronous loading and error states', () => {
    const { rerender } = render(<PageSkeleton/>)
    expect(screen.getByRole('status', { name: '正在加载' })).toBeInTheDocument()

    rerender(<ErrorState error={new ApiError({ kind: 'TIMEOUT', message: '请求超时', endpoint: '/api/test' })}/>)
    expect(screen.getByRole('alert')).toHaveTextContent('请求超时')
  })
})
