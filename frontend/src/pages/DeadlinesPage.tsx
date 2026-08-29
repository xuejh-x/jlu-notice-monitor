import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getDeadlineNotices } from '../api/notices'
import { PageHeader } from '../components/layout/PageHeader'
import { NoticeCard } from '../components/notice/NoticeCard'
import { Card } from '../components/ui/Card'
import { EmptyState, ErrorState, PageSkeleton } from '../components/ui/Feedback'
import { cn } from '../utils/cn'
import { fullDate } from '../utils/format'

const ranges=[{label:'今天',days:0},{label:'3 天内',days:3},{label:'7 天内',days:7},{label:'30 天内',days:30}]
export function DeadlinesPage(){const [days,setDays]=useState(30);const q=useQuery({queryKey:['notices','deadlines',days],queryFn:()=>getDeadlineNotices(days)});const grouped=q.data?.reduce<Record<string,typeof q.data>>((all,n)=>{const key=fullDate(n.registration_deadline);(all[key]??=[]).push(n);return all},{})??{};return <><PageHeader title="即将截止" description="按截止日期安排你的下一步行动。" actions={<div className="flex rounded-lg border border-zinc-200 bg-white p-1 dark:border-zinc-700 dark:bg-zinc-900"><button onClick={()=>setDays(365)} className={cn('rounded-md px-3 py-1.5 text-xs',days===365?'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900':'text-zinc-500')}>全部</button>{ranges.map(r=><button key={r.days} onClick={()=>setDays(r.days)} className={cn('rounded-md px-3 py-1.5 text-xs',days===r.days?'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900':'text-zinc-500')}>{r.label}</button>)}</div>}/>{q.isPending?<PageSkeleton/>:q.isError?<ErrorState message={q.error.message} retry={()=>q.refetch()}/>:q.data.length?<div className="space-y-6">{Object.entries(grouped).map(([date,items])=><section key={date}><div className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">{date}</div><Card className="px-4 sm:px-5">{items.map(n=><NoticeCard key={n.id} notice={n}/>)}</Card></section>)}</div>:<EmptyState title="近期没有截止事项" description="当前筛选范围内没有已提取到截止日期的通知。"/>}</>}
