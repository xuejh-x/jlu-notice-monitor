import { isTauri } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import type { AnchorHTMLAttributes, MouseEvent } from 'react'

type ExternalAnchorProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> & {
  href: string
}

export function ExternalAnchor({ href, onClick, ...props }: ExternalAnchorProps) {
  async function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event)
    if (event.defaultPrevented || !isTauri()) return

    event.preventDefault()
    try {
      await openUrl(href)
    } catch (error) {
      console.error('无法使用系统默认应用打开外部链接', error)
      window.alert('无法打开外部链接，请稍后重试。')
    }
  }

  return (
    <a
      {...props}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(event) => void handleClick(event)}
    />
  )
}
