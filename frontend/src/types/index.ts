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
/** Backend response of /notices/{id}/read|unread|favorite|unfavorite|archive|unarchive
 *  (routes.py `_set_state`): the mutated field is a dynamic key, e.g.
 *  {"notice_id": 34, "is_favorite": true}. */
export type NoticeStateResult =
  | { notice_id: number; is_favorite: boolean }
  | { notice_id: number; is_read: boolean }
  | { notice_id: number; is_archived: boolean }
export interface Source {
  id: number; code: string; name: string; base_url: string; enabled: boolean
  last_checked_at: string | null; last_success_at: string | null; last_error: string | null
  consecutive_errors: number; status: SourceHealth | string; message: string | null
  notice_count: number
  ownership?: SourceOwnership; subscribed?: boolean; source_type?: string; auth_type?: string; health_state?: SourceHealthState
}
export type SourceOwnership = 'OFFICIAL_CLOUD' | 'SHARED_CLOUD' | 'CUSTOM_LOCAL_PUBLIC' | 'CUSTOM_LOCAL_PRIVATE'
export type SourceHealthState = 'healthy' | 'syncing' | 'disabled' | 'needs_reauth' | 'auth_error' | 'parse_error' | 'network_error' | 'source_error' | 'unsupported' | 'unconfigured' | 'cloud_unconfigured' | 'authenticated'
export type SourceParser = 'auto' | 'generic_html' | 'rss' | 'atom'
export type SourceAuthType = 'none' | 'username_password' | 'browser_session' | 'cookie' | 'basic' | 'bearer' | 'api_token' | 'custom_adapter'
export interface ParserConfiguration {
  item_selector?: string; title_selector?: string; link_selector?: string; date_selector?: string
  content_selector?: string; attachment_selector?: string; next_page_selector?: string; pagination_limit?: number
}
export interface SourceDraft {
  name: string; list_url: string; kind: 'public' | 'private'; parser: SourceParser
  parser_config: ParserConfiguration; auth_type: SourceAuthType; login_url?: string
  username?: string; password?: string; remember_credentials?: boolean; allow_private_network?: boolean
}
export interface SourceConfiguration {
  id: number; code: string; name: string; base_url: string; ownership: SourceOwnership
  source_type: string; parser: SourceParser; parser_config: ParserConfiguration; subscribed: boolean; enabled: boolean
  auth_type: SourceAuthType; username: string | null; password_saved: boolean; login_url: string | null
  allow_private_network: boolean; health_state: SourceHealthState; last_error_code: string | null
  last_error: string | null; last_checked_at: string | null; last_success_at: string | null; requires_reauthentication: boolean
  authentication_status?: 'not_required' | 'not_configured' | 'required' | 'authenticated'
  source_identity: string | null; cloud_source_id: string | null
  source_scope: 'official' | 'shared' | 'personal' | 'private'; execution: 'cloud' | 'local'
  cloud_policy: 'auto' | 'force_enabled' | 'force_disabled'; crawl_interval_seconds: number | null
  validation_status: 'untested' | 'passed' | 'failed'; validated_at: string | null
  promotion_reused?: boolean
}
export interface SourcePreview {
  status: 'success' | 'authentication_required'; detected_type: SourceParser; found: number
  items: Array<{ title: string; url: string; publish_date: string | null; content_preview: string }>
  message?: string; preview_token: string
}
export interface ImportanceRule { id: number; keyword: string; weight: number; enabled: boolean; is_system_default: boolean }
export interface CrawlerSourceResult {
  source: string; status?: 'pending' | 'running' | 'success' | 'partial_failure' | 'failure' | 'skipped' | string
  fetched: number; detail_fetched?: number; detail_skipped?: number
  new_count: number; updated_count: number; unchanged_count: number; errors: string[]
  list_duration_seconds?: number; detail_duration_seconds?: number; parse_db_duration_seconds?: number
}
export interface CrawlerStatus {
  running: boolean; status?: 'idle' | 'running' | 'success' | 'partial_failure' | 'failure' | string
  current_started_at: string | null; current_source?: string | null; current_sources?: string[]
  completed_sources?: number; total_sources?: number
  last_run: string | null; last_duration: number | null
  trigger_source?: 'manual' | 'scheduled' | string | null
  scheduler?: {
    enabled: boolean; running: boolean; interval_minutes: number
    last_scheduled_run: string | null; next_scheduled_run: string | null
    last_scheduled_outcome: string | null; last_error: string | null
  }
  new_count: number; updated_count: number; unchanged_count?: number; source_results: CrawlerSourceResult[]
  startup_sync?: {
    triggered: boolean; started_at: string | null; completed_at: string | null
    outcome: 'started' | 'success' | 'partial_failure' | 'failure' | 'skipped_running' | 'cancelled' | string | null
    skipped_reason: string | null
  }
}
export interface NoticeFilters {
  category?: string; source?: string; min_score?: number; date_from?: string; date_to?: string
  status?: string; deadline_status?: string; favorite?: boolean; read?: boolean; q?: string
  keyword?: string; sort?: 'newest' | 'priority' | 'deadline'; page?: number; page_size?: number
}
export interface SourceStatus {
  code: string; name: string; enabled: boolean; status: SourceHealth | string; message: string | null
  // Dashboard embeds the /api/sources serialization (routes.py sources()),
  // whose fields are last_checked_at / last_success_at / last_error.
  last_checked_at?: string | null; last_success_at?: string | null; last_error?: string | null
}
export interface DashboardData {
  new_today: number; urgent: number; important: number; upcoming_deadlines: number; unread: number
  source_status: SourceStatus[]; recent_notices: Notice[]
}

export type NotificationEventType = 'NEW_NOTICE' | 'IMPORTANT_NOTICE' | 'DEADLINE_APPROACHING' | 'DEADLINE_CHANGED' | 'SOURCE_AUTH_REQUIRED' | 'SOURCE_ERROR' | 'DAILY_SUMMARY'
export interface NotificationEvent {
  id: number; type: NotificationEventType; notice_id: number | null; source_id: number | null
  severity: 'info' | 'warning' | 'error'; title: string; body: string; route: string | null
  local_date: string | null; read_at: string | null; created_at: string
}
export interface NotificationPreferences {
  enabled: boolean; new_notice_enabled: boolean; important_notice_enabled: boolean
  deadline_enabled: boolean; source_health_enabled: boolean; daily_summary_enabled: boolean
  minimum_importance: number; deadline_lead_days: number[]; quiet_start: string; quiet_end: string
}
export interface NotificationDeliveryClaim {
  delivery_id: number; claim_token: string; event: NotificationEvent
}
