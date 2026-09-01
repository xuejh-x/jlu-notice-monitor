import { Download, File, FileSpreadsheet, FileText } from 'lucide-react'
import type { Attachment } from '../../types'
import { isSafeExternalUrl } from '../../utils/url'
import { ExternalAnchor } from '../ui/ExternalAnchor'

function attachmentIdentity(attachment: Attachment) {
  const value = `${attachment.type ?? ''} ${attachment.filename ?? ''}`.toLowerCase()
  if (value.includes('xlsx') || value.includes('xls') || value.includes('spreadsheet')) return { icon: FileSpreadsheet, tone: 'bg-source-green-bg text-source-green-fg' }
  if (value.includes('pdf')) return { icon: FileText, tone: 'bg-deadline-danger-bg text-deadline-danger-fg' }
  return { icon: File, tone: 'bg-source-blue-bg text-source-blue-fg' }
}

export function AttachmentRow({ attachment, fallbackName }: { attachment: Attachment; fallbackName: string }) {
  const name = attachment.filename ?? fallbackName
  const safe = isSafeExternalUrl(attachment.url)
  const { icon: Icon, tone } = attachmentIdentity(attachment)
  const content = <>
    <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-[5px] ${tone}`}><Icon className="h-4 w-4" aria-hidden="true" /></span>
    <span className="min-w-0 flex-1 truncate text-body text-text-primary">{name}</span>
    {attachment.type && <span className="shrink-0 text-metadata uppercase text-text-muted">{attachment.type}</span>}
    {safe && <span className="grid h-7 w-7 shrink-0 place-items-center text-text-muted"><Download className="h-4 w-4" aria-hidden="true" /></span>}
  </>
  const className = 'flex h-attachment-height min-w-0 items-center gap-3 rounded-design border border-border bg-attachment-surface px-3 transition-colors hover:border-border-strong'
  return safe ? <ExternalAnchor href={attachment.url} className={className}>{content}</ExternalAnchor> : <span className={className}>{content}</span>
}
