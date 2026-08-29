export const categoryLabels: Record<string, string> = {
  competition: '学科竞赛', algorithm: '算法竞赛', algorithm_competition: '算法竞赛',
  cybersecurity: '网络安全', cybersecurity_competition: '网络安全竞赛', innovation_competition: '创新创业',
  training: '实训', internship: '实习', research: '科研/实验室', postgraduate: '推免',
  postgraduate_recommendation: '推免', academic: '教学通知', other: '其他',
}
export const deadlineLabels: Record<string, string> = {
  today: '今天截止', urgent: '3 天内截止', normal: '截止日期已知', expired: '已截止', unknown: '时间待定',
}

export const sourceStatusLabels: Record<string, string> = {
  healthy: '运行正常', disabled: '尚未配置', unconfigured: '尚未配置', login_required: '需要登录',
  login_expired: '登录已失效', unavailable: '暂时不可用',
}
