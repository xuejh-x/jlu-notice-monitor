import { useState, type ReactNode } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import { Card } from '../components/ui/Card'
import { Select } from '../components/ui/Form'
import { loadSettings, saveSettings } from '../stores/settings'
import { useTheme, type ThemeMode } from '../stores/theme'
import { useToast } from '../stores/toast'

export function SettingsPage(){
  const {theme,setTheme}=useTheme();const [settings,setSettings]=useState(loadSettings);const toast=useToast()
  const update=<K extends keyof typeof settings>(key:K,value:(typeof settings)[K])=>{const next={...settings,[key]:value};setSettings(next);saveSettings(next);toast('设置已保存')}
  return <><PageHeader title="设置" description="调整显示方式和通知优先级偏好。"/><div className="max-w-3xl space-y-4"><Card className="divide-y divide-zinc-100 px-5 dark:divide-zinc-800">
    <SettingRow title="外观主题" description="可选择浅色、深色或跟随系统。"><Select aria-label="外观主题" value={theme} onChange={e=>setTheme(e.target.value as ThemeMode)} className="w-36"><option value="light">浅色</option><option value="dark">深色</option><option value="system">跟随系统</option></Select></SettingRow>
    <SettingRow title="每页数量" description="全部通知页面每次显示的条目数。"><Select aria-label="每页数量" value={settings.pageSize} onChange={e=>update('pageSize',Number(e.target.value))} className="w-36"><option value="10">10 条</option><option value="20">20 条</option><option value="50">50 条</option></Select></SettingRow>
    <SettingRow title="优先级阈值" description="用于突出值得优先关注的通知。"><Select aria-label="优先级阈值" value={settings.priorityThreshold} onChange={e=>update('priorityThreshold',Number(e.target.value))} className="w-36"><option value="60">60 以上</option><option value="70">70 以上</option><option value="80">80 以上</option></Select></SettingRow>
    <SettingRow title="隐藏低优先级通知" description="仅影响首页重点区域，不删除任何通知。"><button role="switch" aria-label="隐藏低优先级通知" aria-checked={settings.hideLowPriority} onClick={()=>update('hideLowPriority',!settings.hideLowPriority)} className={`relative h-6 w-11 rounded-full transition-colors ${settings.hideLowPriority?'bg-indigo-600':'bg-zinc-300 dark:bg-zinc-700'}`}><span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.hideLowPriority?'translate-x-5':'translate-x-0'}`}/></button></SettingRow>
    <SettingRow title="默认首页" description="应用启动后优先进入的页面。"><Select aria-label="默认首页" value={settings.defaultHome} onChange={e=>update('defaultHome',e.target.value)} className="w-36"><option value="/">首页</option><option value="/today">今日</option><option value="/deadlines">即将截止</option></Select></SettingRow>
  </Card><p className="px-1 text-xs leading-5 text-zinc-400">当前仅提供中文界面。API 地址通过 VITE_API_BASE_URL 配置，便于后续适配 Windows 与 Android。</p></div></>
}

function SettingRow({title,description,children}:{title:string;description:string;children:ReactNode}){return <div className="flex items-center justify-between gap-6 py-5"><div><h2 className="text-sm font-medium">{title}</h2><p className="mt-1 text-xs leading-5 text-zinc-500">{description}</p></div>{children}</div>}
