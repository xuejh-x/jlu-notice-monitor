import { CircleAlert, Download, File, FileSpreadsheet, FileText } from 'lucide-react'
import type { Attachment } from '../../types'
import { isSafeExternalUrl } from '../../utils/url'
import { ExternalAnchor } from '../ui/ExternalAnchor'

function attachmentIdentity(attachment: Attachment) {
  const value = `${attachment.type ?? ''} ${attachment.filename ?? ''}`.toLowerCase()
  if (value.includes('xlsx') || value.includes('xls') || value.includes('spreadsheet')) return { icon: FileSpreadsheet, tone: 'bg-source-green-bg text-source-green-fg' }
  if (value.includes('pdf')) return { icon: FileText, tone: 'bg-deadline-danger-bg text-deadline-danger-fg' }
  if (value.includes('doc') || value.includes('word')) return { icon: FileText, tone: 'bg-source-blue-bg text-source-blue-fg' }
  return { icon: File, tone: 'bg-source-blue-bg text-source-blue-fg' }
}

export function AttachmentRow({ attachment, fallbackName }: { attachment: Attachment; fallbackName: string }) {
  const name = attachment.filename ?? fallbackName
  const safe = isSafeExternalUrl(attachment.url)
  const { icon: Icon, tone } = attachmentIdentity(attachment)
  const longName = name.length > 28
  const content = <>
    <span className={`grid h-7 w-6.5 shrink-0 place-items-center rounded-compact border border-current/20 ${tone}`}><Icon className="h-4 w-4" aria-hidden="true" /></span>
    <span className="flex min-w-0 flex-1 text-body text-text-secondary group-hover:text-text-primary" aria-label={name}>
      {longName ? <><span className="truncate" aria-hidden="true">{name.slice(0, -10)}</span><span className="shrink-0" aria-hidden="true">{name.slice(-10)}</span></> : <span className="truncate">{name}</span>}
    </span>
    {attachment.type && <span title={attachment.type} className="max-w-12 shrink-0 truncate text-label uppercase text-text-muted">{attachment.type}</span>}
    {safe && <span className="grid h-6 w-4 shrink-0 place-items-center text-text-muted group-hover:text-accent-soft-text"><Download className="h-4 w-4" aria-hidden="true" /></span>}
    {!safe && <><CircleAlert className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" /><span className="sr-only">链接不可用</span></>}
  </>
  const className = 'group flex h-attachment-height min-w-0 items-center gap-2.5 rounded-design border border-border bg-attachment-surface px-3'
  return safe ? <ExternalAnchor href={attachment.url} title={name} aria-label={`${name}${attachment.type ? ` ${attachment.type}` : ''}`} className={`${className} transition-colors hover:border-border-strong hover:bg-surface-hover active:bg-selected-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus`}>{content}</ExternalAnchor> : <span title={`${name} · 链接不可用`} aria-disabled="true" className={className}>{content}</span>
}
