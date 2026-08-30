import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Badge, type BadgeVariant } from './Badge'

describe('Badge', () => {
  it('renders its label', () => {
    render(<Badge>算法竞赛</Badge>)
    expect(screen.getByText('算法竞赛')).toBeInTheDocument()
  })

  it('renders every semantic variant without crashing', () => {
    const variants: BadgeVariant[] = ['neutral', 'accent', 'success', 'warning', 'danger', 'important']
    for (const variant of variants) {
      const { unmount } = render(<Badge variant={variant}>标签</Badge>)
      expect(screen.getByText('标签')).toBeInTheDocument()
      unmount()
    }
  })
})
