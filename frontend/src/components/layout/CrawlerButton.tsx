import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getCrawlerStatus, runCrawler } from '../../api/crawler'
import { useToast } from '../../stores/toast'
import { Button } from '../ui/Button'

export function CrawlerButton(){const toast=useToast();const client=useQueryClient();const [tracking,setTracking]=useState(false);const hasRun=useRef(false);const status=useQuery({queryKey:['crawler'],queryFn:getCrawlerStatus,refetchInterval:tracking?1500:false});useEffect(()=>{if(status.data?.running)hasRun.current=true;if(tracking&&hasRun.current&&status.data&&!status.data.running){setTracking(false);hasRun.current=false;toast(`检查完成：新增 ${status.data.new_count} 条，更新 ${status.data.updated_count} 条`);client.invalidateQueries({queryKey:['dashboard']});client.invalidateQueries({queryKey:['notices']});client.invalidateQueries({queryKey:['sources']})}},[status.data,tracking,toast,client]);const run=useMutation({mutationFn:runCrawler,onSuccess:()=>{toast('已开始检查新通知');setTracking(true);window.setTimeout(()=>status.refetch(),600)},onError:()=>toast('启动检查失败，请稍后重试','error')});const running=run.isPending||tracking||status.data?.running;return <Button variant="primary" onClick={()=>run.mutate()} disabled={running} aria-label="检查新通知"><RefreshCw className={`h-4 w-4 ${running?'animate-spin':''}`}/><span className="hidden lg:inline">{running?'正在检查…':'检查新通知'}</span></Button>}
