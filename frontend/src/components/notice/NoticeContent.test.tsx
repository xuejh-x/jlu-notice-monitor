import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { NoticeContent } from './NoticeContent'

describe('NoticeContent', () => {
  it('renders null content as a fallback message', () => {
    render(<NoticeContent content={null} />)
    expect(screen.getByText('尚未抓取到正文，请查看原网页。')).toBeInTheDocument()
  })

  it('renders plain text as escaped text nodes (no HTML execution)', () => {
    const dangerous = '<script>alert("xss")</script><img src=x onerror=alert(1)>普通正文'
    const { container } = render(<NoticeContent content={dangerous} />)
    // The literal markup string is present as text, never as a live element.
    expect(screen.getByText(/普通正文$/)).toBeInTheDocument()
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
  })

  it('splits on newlines into paragraphs and applies break-words for long tokens', () => {
    const { container } = render(<NoticeContent content={'第一段\n\n第二段'} />)
    const paragraphs = container.querySelectorAll('p')
    expect(paragraphs).toHaveLength(2)
    expect(paragraphs[0]).toHaveTextContent('第一段')
    expect(paragraphs[1]).toHaveClass('break-words')
  })
})
