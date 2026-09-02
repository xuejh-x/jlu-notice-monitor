import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, Plus, Trash2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { createImportanceRule, deleteImportanceRule, getImportanceRules, restoreImportanceDefaults, updateImportanceRule } from '../api/importance'
import { PageHeader } from '../components/layout/PageHeader'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { Input, Select, Toggle } from '../components/ui/Form'
import { loadSettings, saveSettings } from '../stores/settings'
import { useTheme, type ThemeMode } from '../stores/theme'
import { useToast } from '../stores/toast'
import type { ImportanceRule } from '../types'

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

function ScoreHelp() {
  const [visible, setVisible] = useState(false)
  return <span className="relative inline-flex" onMouseEnter={() => setVisible(true)} onMouseLeave={() => setVisible(false)}>
    <button type="button" aria-label="查看分值参考" aria-expanded={visible} onFocus={() => setVisible(true)} onBlur={() => setVisible(false)} className="inline-flex h-7 w-7 items-center justify-center rounded-medium text-text-muted hover:bg-surface-muted"><Info className="h-4 w-4"/></button>
    {visible && <span role="tooltip" className="absolute left-0 top-8 z-20 w-72 rounded-medium border border-border bg-surface-raised p-3 text-left text-xs leading-5 text-text-secondary shadow-sm">
      <strong className="block text-sm text-text-primary">分值参考</strong>
      <span className="mt-1 block">+25 ~ +35　非常重要：竞赛、报名、关键机会</span><span className="block">+15 ~ +24　比较重要：科研、实习、实验室</span><span className="block">+5 ~ +14　一般兴趣：技术方向、普通兴趣词</span><span className="block">0　不额外影响</span><span className="block">-10 ~ -20　降低优先级</span><span className="block">-21 ~ -35　基本不感兴趣</span><span className="mt-1 block text-text-muted">最终重要度还会综合分类、截止日期等因素。</span>
    </span>}
  </span>
}

function RuleRow({ rule, refresh }: { rule: ImportanceRule; refresh: () => Promise<void> }) {
  const toast = useToast(); const [keyword, setKeyword] = useState(rule.keyword); const [weight, setWeight] = useState(String(rule.weight)); const [error, setError] = useState<string | null>(null)
  const save = useMutation({ mutationFn: () => updateImportanceRule(rule.id, { keyword: keyword.trim(), weight: Number(weight) }), onSuccess: async () => { await refresh(); setError(null); toast('规则已保存，现有通知已重新评分') }, onError: value => setError(value instanceof Error ? value.message : '保存失败') })
  const toggle = useMutation({ mutationFn: () => updateImportanceRule(rule.id, { enabled: !rule.enabled }), onSuccess: refresh })
  const remove = useMutation({ mutationFn: () => deleteImportanceRule(rule.id), onSuccess: async () => { await refresh(); toast('规则已删除，现有通知已重新评分') } })
  const numeric = Number(weight); const valid = keyword.trim().length > 0 && Number.isInteger(numeric) && numeric >= -50 && numeric <= 50
  return <div className="py-4"><div className="grid gap-3 sm:grid-cols-[minmax(160px,1fr)_100px_auto_auto] sm:items-center"><Input aria-label={`${rule.keyword} 关键词`} value={keyword} onChange={event => setKeyword(event.target.value)}/><Input aria-label={`${rule.keyword} 分值`} type="number" min={-50} max={50} value={weight} onChange={event => setWeight(event.target.value)}/><Toggle checked={rule.enabled} aria-label={`${rule.keyword} 启用状态`} onClick={() => toggle.mutate()}/><div className="flex gap-1"><Button size="sm" disabled={!valid || save.isPending || (keyword === rule.keyword && numeric === rule.weight)} onClick={() => save.mutate()}>保存</Button><Button size="icon" variant="ghost" aria-label={`删除 ${rule.keyword}`} onClick={() => remove.mutate()}><Trash2 className="h-4 w-4"/></Button></div></div>{Math.abs(numeric) > 35 && <p className="mt-2 text-xs text-warning">单个关键词的绝对分值较高，可能主导最终重要度。</p>}{!valid && <p className="mt-2 text-xs text-danger">关键词不能为空，分值必须是 -50 到 +50 的整数。</p>}{error && <p role="alert" className="mt-2 text-xs text-danger">{error}</p>}</div>
}

function ImportanceSettings() {
  const queryClient = useQueryClient(); const toast = useToast(); const rules = useQuery({ queryKey: ['importance-rules'], queryFn: ({ signal }) => getImportanceRules({ signal }) })
  const [keyword, setKeyword] = useState(''); const [weight, setWeight] = useState('10'); const [confirmRestore, setConfirmRestore] = useState(false)
  const refresh = async () => { await Promise.all([queryClient.invalidateQueries({ queryKey: ['importance-rules'] }), queryClient.invalidateQueries({ queryKey: ['notices'] }), queryClient.invalidateQueries({ queryKey: ['dashboard'] }), queryClient.invalidateQueries({ queryKey: ['search'] })]) }
  const add = useMutation({ mutationFn: () => createImportanceRule(keyword.trim(), Number(weight)), onSuccess: async () => { setKeyword(''); setWeight('10'); await refresh(); toast('关键词已添加，现有通知已重新评分') } })
  const restore = useMutation({ mutationFn: restoreImportanceDefaults, onSuccess: async () => { setConfirmRestore(false); await refresh(); toast('已恢复系统默认并重新评分') } })
  const numeric = Number(weight); const valid = keyword.trim().length > 0 && Number.isInteger(numeric) && numeric >= -50 && numeric <= 50
  if (rules.isPending) return <PageSkeleton/>
  if (rules.isError) return <ErrorState error={rules.error} retry={() => rules.refetch()}/>
  return <div className="divide-y divide-border"><div className="py-4"><div className="flex items-center gap-1"><h3 className="text-sm font-medium text-text-primary">个人关键词与分值</h3><ScoreHelp/></div><p className="mt-1 text-sm text-text-secondary">正数提高优先级，负数降低优先级；分类和截止日期仍作为客观信号。</p><div className="mt-3 grid gap-3 sm:grid-cols-[minmax(160px,1fr)_100px_auto]"><Input aria-label="新关键词" placeholder="例如：PWN" value={keyword} onChange={event => setKeyword(event.target.value)}/><Input aria-label="新关键词分值" type="number" min={-50} max={50} value={weight} onChange={event => setWeight(event.target.value)}/><Button variant="primary" disabled={!valid || add.isPending} onClick={() => add.mutate()}><Plus className="h-4 w-4"/>添加关键词</Button></div>{add.isError && <p role="alert" className="mt-2 text-xs text-danger">{add.error.message}</p>}</div>{rules.data.map(rule => <RuleRow key={rule.id} rule={rule} refresh={refresh}/>)}<div className="py-4">{confirmRestore ? <div role="alert" className="rounded-medium bg-surface-muted p-3 text-sm text-text-secondary"><p>恢复默认会替换当前全部个人关键词，并立即重新计算现有通知。</p><div className="mt-3 flex gap-2"><Button size="sm" variant="danger" onClick={() => restore.mutate()}>确认恢复</Button><Button size="sm" variant="ghost" onClick={() => setConfirmRestore(false)}>取消</Button></div></div> : <Button variant="ghost" onClick={() => setConfirmRestore(true)}>恢复系统默认</Button>}</div></div>
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

        <SettingsSection id="importance-settings" title="个人重要度" description="这些规则只保存在当前设备；修改后会重新计算全部现有通知。">
          <ImportanceSettings/>
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
