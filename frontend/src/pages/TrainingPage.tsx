import { useState } from 'react'
import { cn } from '../utils/cn'
import { FeedPage } from './FeedPage'

const tabs = [['全部', ''], ['实训', 'training'], ['实习', 'internship']] as const

export function TrainingPage() {
  const [category, setCategory] = useState('')
  const controls = (
    <div className="mb-5 flex max-w-full gap-1 overflow-x-auto border-b border-border" aria-label="实训与实习分类">
      {tabs.map(([label, value]) => (
        <button
          key={label}
          type="button"
          aria-pressed={category === value}
          onClick={() => setCategory(value)}
          className={cn('min-h-11 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm', category === value ? 'border-accent font-medium text-accent-soft-text' : 'border-transparent text-text-muted hover:text-text-primary')}
        >
          {label}
        </button>
      ))}
    </div>
  )
  return <FeedPage key={category || 'all'} title="实训与实习" description="查看校内外实训项目与实习机会。" categories={category ? [category] : ['training', 'internship']} controls={controls}/>
}
