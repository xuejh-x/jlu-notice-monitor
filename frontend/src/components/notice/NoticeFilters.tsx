import { Input, Select } from '../ui/Form'
import type { NoticesUrlState } from '../../utils/noticeSearchParams'

/** The seven URL-driven filter controls (search input is page-level, not here). */
export function FilterFields({ state, onPatch }: { state: NoticesUrlState; onPatch: (changes: Partial<NoticesUrlState>) => void }) {
  return (
    <>
      <Select aria-label="分类" value={state.category} onChange={event => onPatch({ category: event.target.value })}>
        <option value="">全部分类</option>
        <option value="algorithm_competition">算法竞赛</option>
        <option value="cybersecurity_competition">网络安全</option>
        <option value="innovation_competition">创新创业</option>
        <option value="training">实训</option>
        <option value="internship">实习</option>
        <option value="research">科研</option>
        <option value="postgraduate_recommendation">推免</option>
        <option value="academic">教学</option>
      </Select>
      <Select aria-label="来源" value={state.source} onChange={event => onPatch({ source: event.target.value })}>
        <option value="">全部来源</option>
        <option value="cse">网络安全学院</option>
        <option value="ccst">计算机学院</option>
        <option value="csw">软件学院</option>
        <option value="jwc">本科生院</option>
        <option value="innovation">创新创业教育学院</option>
        <option value="oa">吉林大学 OA</option>
      </Select>
      <Select aria-label="最低优先级" value={state.minScore} onChange={event => onPatch({ minScore: event.target.value })}>
        <option value="">不限优先级</option>
        <option value="70">70 以上</option>
        <option value="80">80 以上</option>
        <option value="90">90 以上</option>
      </Select>
      <Input aria-label="起始日期" type="date" value={state.dateFrom} onChange={event => onPatch({ dateFrom: event.target.value })} />
      <Select aria-label="截止状态" value={state.deadlineStatus} onChange={event => onPatch({ deadlineStatus: event.target.value })}>
        <option value="">全部截止状态</option>
        <option value="today">今天截止</option>
        <option value="urgent">3 天内截止</option>
        <option value="normal">稍后截止</option>
        <option value="expired">已截止</option>
        <option value="unknown">时间待定</option>
      </Select>
      <Select aria-label="阅读状态" value={state.read} onChange={event => onPatch({ read: event.target.value as NoticesUrlState['read'] })}>
        <option value="">全部阅读状态</option>
        <option value="unread">未读</option>
        <option value="read">已读</option>
      </Select>
      <Select aria-label="收藏状态" value={state.favorite} onChange={event => onPatch({ favorite: event.target.value as NoticesUrlState['favorite'] })}>
        <option value="">全部收藏状态</option>
        <option value="favorite">已收藏</option>
        <option value="normal">未收藏</option>
      </Select>
    </>
  )
}
