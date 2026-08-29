import { useState } from 'react'
import { cn } from '../utils/cn'
import { FeedPage } from './FeedPage'

const tabs=[['全部',''],['实训','training'],['实习','internship']] as const
export function TrainingPage(){const [category,setCategory]=useState('');return <div><div className="mb-5 flex gap-1 overflow-x-auto border-b border-zinc-200 dark:border-zinc-800">{tabs.map(([label,value])=><button key={label} onClick={()=>setCategory(value)} className={cn('whitespace-nowrap border-b-2 px-4 py-2.5 text-sm',category===value?'border-indigo-600 font-medium text-indigo-700 dark:text-indigo-300':'border-transparent text-zinc-500')}>{label}</button>)}</div><FeedPage key={category||'all'} title="实训与实习" description="查看校内外实训项目与实习机会。" categories={category?[category]:['training','internship']}/></div>}
