export type Category = 'competition' | 'algorithm' | 'cybersecurity' | 'training' | 'research' | 'postgraduate' | 'other'
export type DeadlineStatus = 'unknown' | 'expired' | 'today' | 'urgent' | 'normal'
export type SourceHealth = 'disabled' | 'unconfigured' | 'login_required' | 'login_expired' | 'unavailable' | 'healthy'

export interface NoticeSource { code: string; name: string; url?: string }
export interface Notice {
  id: number; title: string; url: string; publish_date: string | null; publisher: string | null
  category: Category | string | null; importance_score: number
  registration_start: string | null; registration_deadline: string | null
  event_start: string | null; event_end: string | null
  deadline_status: DeadlineStatus | string | null; days_until_deadline: number | null
  status: string; first_seen_at: string; last_seen_at: string; updated_at: string
  is_read: boolean; is_archived: boolean; is_favorite: boolean; sources: NoticeSource[]
}
export interface Attachment { filename: string | null; url: string; type: string | null }
export interface NoticeDetail extends Notice {
  content: string | null; target_students: string | null; registration_method: string | null
  competition_level: string | null; attachments: Attachment[]; updates: Array<Record<string, unknown>>
}
export interface PaginatedNotices { items: Notice[]; total: number; page: number; page_size: number; total_pages: number }
export interface Source {
  id: number; code: string; name: string; base_url: string; enabled: boolean
  last_checked_at: string | null; last_success_at: string | null; last_error: string | null
  consecutive_errors: number; status: SourceHealth | string; message: string | null
  notice_count: number
}
export interface CrawlerSourceResult { source: string; fetched: number; new_count: number; updated_count: number; unchanged_count: number; errors: string[] }
export interface CrawlerStatus {
  running: boolean; current_started_at: string | null; last_run: string | null; last_duration: number | null
  new_count: number; updated_count: number; source_results: CrawlerSourceResult[]
}
export interface NoticeFilters {
  category?: string; source?: string; min_score?: number; date_from?: string; date_to?: string
  status?: string; deadline_status?: string; favorite?: boolean; read?: boolean; q?: string
  keyword?: string; sort?: 'newest' | 'priority' | 'deadline'; page?: number; page_size?: number
}
export interface SourceStatus {
  code: string; name: string; enabled: boolean; status: SourceHealth | string; message: string | null
  last_success_at?: string | null; last_error_at?: string | null
}
export interface DashboardData {
  new_today: number; urgent: number; important: number; upcoming_deadlines: number; unread: number
  source_status: SourceStatus[]; recent_notices: Notice[]
}
