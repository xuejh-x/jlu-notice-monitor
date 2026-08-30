import { useState, type ReactNode } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import { Card } from '../components/ui/Card'
import { Select, Toggle } from '../components/ui/Form'
import { loadSettings, saveSettings } from '../stores/settings'
import { useTheme, type ThemeMode } from '../stores/theme'
import { useToast } from '../stores/toast'

function SettingsSection({ id, title, description, children }: { id: string; title: string; description: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id}>
      <div className="mb-3">
        <h2 id={id} className="text-section-heading text-text-primary">{title}</h2>
        <p className="mt-1 text-sm text-text-secondary">{description}</p>
      </div>
      <Card className="divide-y divide-border px-4 sm:px-5">{children}</Card>
    </section>
  )
}
function SettingRow({ id, title, description, children }: { id: string; title: string; description: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
      <div className="min-w-0">
        <h3 id={`${id}-label`} className="text-sm font-medium text-text-primary">{title}</h3>
        <p id={`${id}-description`} className="mt-1 max-w-xl text-sm leading-5 text-text-secondary">{description}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

export function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const [settings, setSettings] = useState(loadSettings)
  const toast = useToast()
  const update = <K extends keyof typeof settings>(key: K, value: (typeof settings)[K]) => {
    const next = { ...settings, [key]: value }
    setSettings(next)
    saveSettings(next)
    toast('设置已保存')
  }

  return (
    <>
      <PageHeader title="设置" description="调整外观、通知偏好和列表阅读方式。"/>
      <div className="max-w-3xl space-y-8">
        <SettingsSection id="appearance-settings" title="外观" description="选择适合当前环境的显示主题。">
          <SettingRow id="theme" title="外观主题" description="可选择浅色、深色或跟随系统。">
            <Select aria-labelledby="theme-label" aria-describedby="theme-description" value={theme} onChange={event => setTheme(event.target.value as ThemeMode)} className="w-full sm:w-40">
              <option value="light">浅色</option><option value="dark">深色</option><option value="system">跟随系统</option>
            </Select>
          </SettingRow>
        </SettingsSection>

        <SettingsSection id="notice-preferences" title="通知偏好" description="定义首页优先集合，不改变通知自身的“一般 / 重要 / 高相关”标签。">
          <SettingRow id="priority-threshold" title="优先关注阈值" description="评分达到该值的通知会进入首页“优先关注”集合。">
            <Select aria-labelledby="priority-threshold-label" aria-describedby="priority-threshold-description" value={settings.priorityThreshold} onChange={event => update('priorityThreshold', Number(event.target.value))} className="w-full sm:w-40">
              <option value="60">评分 60 以上</option><option value="70">评分 70 以上</option><option value="80">评分 80 以上</option>
            </Select>
          </SettingRow>
          <SettingRow id="hide-low-priority" title="精简优先列表" description="减少首页优先关注区域显示的条目数，不会隐藏或删除通知。">
            <Toggle checked={settings.hideLowPriority} aria-labelledby="hide-low-priority-label" aria-describedby="hide-low-priority-description" onClick={() => update('hideLowPriority', !settings.hideLowPriority)}/>
          </SettingRow>
        </SettingsSection>

        <SettingsSection id="reading-settings" title="阅读与显示" description="调整通知列表密度和应用启动入口。">
          <SettingRow id="page-size" title="每页数量" description="通知列表页面每次显示的条目数。">
            <Select aria-labelledby="page-size-label" aria-describedby="page-size-description" value={settings.pageSize} onChange={event => update('pageSize', Number(event.target.value))} className="w-full sm:w-40">
              <option value="10">10 条</option><option value="20">20 条</option><option value="50">50 条</option>
            </Select>
          </SettingRow>
          <SettingRow id="default-home" title="默认首页" description="应用启动后优先进入的现有页面。">
            <Select aria-labelledby="default-home-label" aria-describedby="default-home-description" value={settings.defaultHome} onChange={event => update('defaultHome', event.target.value)} className="w-full sm:w-40">
              <option value="/">首页</option><option value="/today">今日</option><option value="/deadlines">即将截止</option>
            </Select>
          </SettingRow>
        </SettingsSection>

        <p className="px-1 text-metadata leading-5 text-text-muted">设置保存在当前设备。当前仅提供中文界面。</p>
      </div>
    </>
  )
}
