const RECENT_ALERT_WINDOW_SECONDS = 3600
const FIVE_MINUTES_SECONDS = 300

export const ALERT_CENTER_TABS = [
  { key: 'realtime', label: '实时流', desc: '未确认风险与即时处置' },
  { key: 'today', label: '今日告警簿', desc: '按时间复盘当天告警' },
  { key: 'archive', label: '历史归档', desc: '按类型追踪历史问题' },
]

export const ALERT_ARCHIVE_TYPES = [
  { key: 'temperature', label: '温度', desc: '温升与过热' },
  { key: 'power', label: '功率', desc: '功耗与预算' },
  { key: 'memory', label: '显存', desc: '显存占用与告警' },
  { key: 'self_check', label: '平台自检', desc: '服务状态与运行检查' },
]

function currentTs() {
  return Math.floor(Date.now() / 1000)
}

function startOfTodayTs(baseTs = currentTs()) {
  const date = new Date(baseTs * 1000)
  date.setHours(0, 0, 0, 0)
  return Math.floor(date.getTime() / 1000)
}

function sortByTimestampDesc(left, right) {
  return Number(right?.timestamp || 0) - Number(left?.timestamp || 0)
}

export function buildAlertSummaryItems(historyAlerts, realtimeAlerts, nowTs = currentTs()) {
  const activeRealtime = realtimeAlerts || []
  const recentCount = activeRealtime.filter(
    (alert) => nowTs - Number(alert?.timestamp || 0) <= RECENT_ALERT_WINDOW_SECONDS,
  ).length
  const criticalUnacknowledged = activeRealtime.filter(
    (alert) => alert?.severity === 'critical',
  ).length

  return [
    {
      key: 'critical',
      label: '严重未确认',
      value: criticalUnacknowledged,
      detail: '需要优先处理的高风险信号',
      tone: 'critical',
    },
    {
      key: 'pending',
      label: '总未确认',
      value: activeRealtime.length,
      detail: '当前仍在工作流中的未闭环告警',
      tone: 'warning',
    },
    {
      key: 'recent',
      label: '最近 1 小时新增',
      value: recentCount,
      detail: `历史样本 ${historyAlerts?.length || 0} 条`,
      tone: 'ok',
    },
  ]
}

export function buildRealtimeBuckets(alerts, selectedType = 'all', nowTs = currentTs()) {
  const filtered = (alerts || [])
    .filter((alert) => selectedType === 'all' || alert?.alert_type === selectedType)
    .sort(sortByTimestampDesc)
  const buckets = [
    { key: 'now', label: '刚刚', desc: '5 分钟内', items: [] },
    { key: 'recent', label: '近 1 小时', desc: '5 分钟到 1 小时', items: [] },
    { key: 'older', label: '更早', desc: '超过 1 小时', items: [] },
  ]

  for (const alert of filtered) {
    const age = nowTs - Number(alert?.timestamp || 0)
    if (age <= FIVE_MINUTES_SECONDS) {
      buckets[0].items.push(alert)
      continue
    }
    if (age <= RECENT_ALERT_WINDOW_SECONDS) {
      buckets[1].items.push(alert)
      continue
    }
    buckets[2].items.push(alert)
  }

  return buckets.filter((bucket) => bucket.items.length)
}

export function buildTodayTimeline(alerts, nowTs = currentTs()) {
  const todayStart = startOfTodayTs(nowTs)
  const sections = new Map()

  for (const alert of (alerts || []).filter((item) => Number(item?.timestamp || 0) >= todayStart).sort(sortByTimestampDesc)) {
    const stamp = new Date(Number(alert.timestamp || 0) * 1000)
    const hourKey = `${String(stamp.getHours()).padStart(2, '0')}:00`
    const existing = sections.get(hourKey) || {
      key: hourKey,
      label: `${hourKey} 时段`,
      items: [],
    }
    existing.items.push(alert)
    sections.set(hourKey, existing)
  }

  return Array.from(sections.values())
}

export function buildArchiveGroups(alerts, nowTs = currentTs()) {
  const todayStart = startOfTodayTs(nowTs)
  const archived = (alerts || [])
    .filter((alert) => Number(alert?.timestamp || 0) < todayStart)
    .sort(sortByTimestampDesc)
  const grouped = Object.fromEntries(ALERT_ARCHIVE_TYPES.map((item) => [item.key, []]))

  for (const alert of archived) {
    if (grouped[alert?.alert_type]) {
      grouped[alert.alert_type].push(alert)
    }
  }

  return ALERT_ARCHIVE_TYPES.map((item) => ({
    ...item,
    count: grouped[item.key].length,
    latest: grouped[item.key][0] || null,
    alerts: grouped[item.key],
  }))
}
