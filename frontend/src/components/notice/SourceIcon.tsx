import { Building2, Globe2, GraduationCap, Landmark, Rss, University, type LucideIcon } from 'lucide-react'
import { cn } from '../../utils/cn'

type Identity = { icon: LucideIcon; tone: string }

function sourceIdentity(name: string): Identity {
  const value = name.toLowerCase()
  if (value.includes('rss')) return { icon: Rss, tone: 'bg-source-green-bg text-source-green-fg' }
  if (value.includes('campus') || value.includes('portal') || value.includes('网站')) return { icon: Globe2, tone: 'bg-source-violet-bg text-source-violet-fg' }
  if (value.includes('seu') || value.includes('东南大学')) return { icon: University, tone: 'bg-source-green-bg text-source-green-fg' }
  if (value.includes('教务')) return { icon: GraduationCap, tone: 'bg-source-cyan-bg text-source-cyan-fg' }
  if (value.includes('jlu') || value.includes('吉林大学') || value.includes('oa')) return { icon: Landmark, tone: 'bg-source-blue-bg text-source-blue-fg' }
  return { icon: Building2, tone: 'bg-source-violet-bg text-source-violet-fg' }
}

export function SourceIcon({ name, metadata = false, className }: { name: string; metadata?: boolean; className?: string }) {
  const { icon: Icon, tone } = sourceIdentity(name)
  if (metadata) {
    const MetadataIcon = Icon === Globe2 || Icon === Rss ? Icon : Landmark
    return <MetadataIcon className={cn('h-4 w-4 shrink-0 text-text-secondary', className)} aria-hidden="true" />
  }
  return <span className={cn('grid h-[25px] w-[25px] shrink-0 place-items-center rounded-[5px]', tone, className)} aria-hidden="true"><Icon className="h-3.5 w-3.5" /></span>
}
