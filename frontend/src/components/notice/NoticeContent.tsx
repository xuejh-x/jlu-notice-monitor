/** Renders the scraped notice body.
 *
 *  Security boundary: `content` is plain text produced server-side by
 *  `parse_detail_html` (`get_text` + whitespace normalization), not HTML.
 *  React renders it as escaped text nodes, so there is no
 *  `dangerouslySetInnerHTML`, no sanitizer requirement, and no way for
 *  script/style/event-handler content to execute. This component only owns
 *  reading typography and overflow containment.
 */
export function NoticeContent({ content }: { content: string | null }) {
  if (!content) {
    return <p className="text-body text-text-muted">尚未抓取到正文，请查看原网页。</p>
  }

  // Server-side extraction collapses whitespace to single spaces, so most
  // notices are one paragraph; the split is kept for any future newline data.
  const paragraphs = content.split(/\n+/).filter(Boolean)

  return (
    <div className="space-y-4">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="text-detail-body break-words text-text-primary">
          {paragraph}
        </p>
      ))}
    </div>
  )
}
