/** True when `value` is an http(s) URL safe to open as an external link.
 *
 *  External URLs (original source, attachments) are treated as untrusted
 *  input: `javascript:`, `data:`, `mailto:` and malformed strings must never
 *  reach an anchor `href`. This helper is the single gate for that decision.
 */
export function isSafeExternalUrl(value: string | null | undefined): value is string {
  if (!value) return false
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}
