import type { CrawlerStatus } from '../../types'

export function isCrawlerJobRunning(value?: CrawlerStatus): boolean {
  return value?.running === true && value.status === 'running'
}

export function crawlerStatusLabel(value?: CrawlerStatus): string {
  if (isCrawlerJobRunning(value)) {
    return value?.trigger_source === 'startup' ? '正在检查最新通知…' : '检查中…'
  }
  if (value?.status === 'partial_failure') return '部分失败'
  if (value?.status === 'failure') return '检查失败'
  if (value?.status === 'success') return '检查完成'
  return '检查'
}
