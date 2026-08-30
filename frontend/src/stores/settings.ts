export interface Settings { pageSize: number; hideLowPriority: boolean; priorityThreshold: number; defaultHome: string }

export const DEFAULTS: Settings = { pageSize: 20, hideLowPriority: false, priorityThreshold: 70, defaultHome: '/' }

const PAGE_SIZES = new Set([10, 20, 50])
const PRIORITY_THRESHOLDS = new Set([60, 70, 80])
const DEFAULT_HOMES = new Set(['/', '/today', '/deadlines'])

/** Normalize any persisted/partial value into the canonical `Settings` shape.
 *
 *  This is the single validation boundary for the `jlu-settings` persistence:
 *  unknown keys are dropped, invalid/out-of-range fields fall back to
 *  `DEFAULTS`, and numeric fields accept numeric strings (legacy/edited
 *  storage). It keeps every consumer (`loadSettings`) deterministic.
 */
export function parseSettings(raw: unknown): Settings {
  if (raw === null || typeof raw !== 'object') return { ...DEFAULTS }
  const value = raw as Record<string, unknown>
  const pageSize = Number(value.pageSize)
  const priorityThreshold = Number(value.priorityThreshold)
  return {
    pageSize: PAGE_SIZES.has(pageSize) ? pageSize : DEFAULTS.pageSize,
    hideLowPriority: value.hideLowPriority === true,
    priorityThreshold: PRIORITY_THRESHOLDS.has(priorityThreshold) ? priorityThreshold : DEFAULTS.priorityThreshold,
    defaultHome: typeof value.defaultHome === 'string' && DEFAULT_HOMES.has(value.defaultHome) ? value.defaultHome : DEFAULTS.defaultHome,
  }
}

export function loadSettings(): Settings {
  try {
    return parseSettings(JSON.parse(localStorage.getItem('jlu-settings') ?? '{}'))
  } catch {
    return { ...DEFAULTS }
  }
}

export function saveSettings(value: Settings): void {
  localStorage.setItem('jlu-settings', JSON.stringify(value))
}
