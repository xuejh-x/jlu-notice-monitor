import { describe, expect, it } from 'vitest'
import { isSafeExternalUrl } from './url'

describe('isSafeExternalUrl', () => {
  it('accepts http and https URLs', () => {
    expect(isSafeExternalUrl('https://ccst.jlu.edu.cn/info/1056/20854.htm')).toBe(true)
    expect(isSafeExternalUrl('http://example.test/a.pdf')).toBe(true)
  })

  it('rejects javascript: and other non-http schemes', () => {
    expect(isSafeExternalUrl('javascript:alert(1)')).toBe(false)
    expect(isSafeExternalUrl('data:text/html,<script>1</script>')).toBe(false)
    expect(isSafeExternalUrl('mailto:test@example.test')).toBe(false)
  })

  it('rejects empty and malformed values without throwing', () => {
    expect(isSafeExternalUrl('')).toBe(false)
    expect(isSafeExternalUrl(null)).toBe(false)
    expect(isSafeExternalUrl(undefined)).toBe(false)
    expect(isSafeExternalUrl('not a url')).toBe(false)
  })
})
