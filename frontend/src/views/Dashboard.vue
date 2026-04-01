<script setup>
/**
 * Dashboard.vue - 治理型总览页
 * 突出实验室GPU运维、总功率预算、任务优先级与实时状态
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { createDemoAlert, getConnectionConfig, getFairnessGovernance, getSystemSelfCheck, healthCheck, getSchedulerStatus, runOptimize, runScheduleOnce, setPowerBudget, testConnectionConfig, updateConnectionConfig, exportFullGovernanceReport } from '../services/api'
import { useAppStore } from '../stores/app'
import { exportTextFile } from '../services/desktopExport'
import PowerTrendChart from '../components/charts/PowerTrendChart.vue'
import UtilizationChart from '../components/charts/UtilizationChart.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'

const router = useRouter()
const store = useAppStore()
const activeTab = ref('overview')
const schedulerState = ref({
  time_period_label: '平峰时段',
  budget: {
    enabled: false,
    total_power_budget: 1200,
    current_total_power: 0,
    remaining_power: 1200,
    usage_pct: 0,
    is_exceeded: false,
    managed_gpu_count: 0,
    last_actions: [],
  },
})
const sourceState = ref({
  connected: false,
  gpu_count: 0,
  label: '未连接',
  detail: '等待 Agent 数据',
})
const connectionState = ref({
  mode: 'local',
  mode_label: '本机模式',
  agent_url: 'http://127.0.0.1:8001',
  agent_label: '本机 Agent',
  connected: false,
  updated_at: null,
  default_local_url: 'http://127.0.0.1:8001',
  target_hint: '使用当前电脑上的 Agent 采集与执行',
  agent_health: null,
})
const connectionForm = ref({
  mode: 'local',
  agent_url: '',
  agent_label: '本机 Agent',
})
const fairnessState = ref({
  overview: {
    fairness_index: 100,
    level: 'balanced',
    summary: '当前共享较均衡。',
    active_users: 0,
    dominant_user: null,
    highest_share_pct: 0,
    reclaimable_candidates: 0,
  },
  users: [],
  recommendations: [],
  yield_candidates: [],
})
const actionBusy = ref(false)
const actionFeedback = ref(null)
const optimizePreview = ref(null)
const lastDispatch = ref(null)
const connectionBusy = ref(false)
const connectionDirty = ref(false)
const connectionFeedback = ref(null)
const remoteAssistState = ref({
  busy: false,
  exportedPath: '',
  feedback: null,
})
const selfCheckBusy = ref(false)
const demoAlertBusy = ref(false)
const demoAlertFeedback = ref(null)
const selfCheckState = ref({
  checked_at: null,
  summary: {
    status: 'warning',
    title: '建议先执行平台自检',
    message: '先确认治理后端、Agent、GPU 采集和实时连接是否正常，再去做真实治理动作。',
  },
  checks: [],
  gpu_count: 0,
  process_count: 0,
  ws_connections: 0,
  llm_available: false,
})
const desktopOpsReady = ref(false)
const desktopRuntime = ref({
  runtimeRoot: '',
  logsRoot: '',
  backendBaseUrl: '',
  agentBaseUrl: '',
  connectionMode: '',
})
const desktopServiceState = ref({})
const desktopOpsBusy = ref(false)
const desktopOpsFeedback = ref(null)
let refreshTimer = null
let removeDesktopServiceListener = null
const REMOTE_AGENT_PORT = 8001
const REMOTE_AGENT_EXPORT_DIRNAME = 'GPU-Server-Agent'
const REMOTE_AGENT_START_SCRIPT = 'Start-Agent.bat'

const fmtMem = (bytes) => (bytes / 1073741824).toFixed(1)
const shortUser = (username = 'unknown') => username.split('\\').pop() || username
const tempColor = (t) => t >= 90 ? '#C41E3A' : t >= 80 ? '#B8860B' : t >= 60 ? '#3A5F4B' : '#2E8B57'
const utilColor = (u) => u >= 90 ? '#C41E3A' : u >= 70 ? '#B8860B' : u >= 40 ? '#3A5F4B' : '#2E8B57'
const powerPct = (usage, limit) => limit > 0 ? Math.round(usage / limit * 100) : 0
const memPct = (used, total) => total > 0 ? Math.round(used / total * 100) : 0
const formatConnectionTime = (timestamp) => {
  if (!timestamp) return '未保存'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
const formatRuntimeTime = (timestamp) => {
  const value = Number(timestamp || 0)
  if (!value) return '未执行'
  const dateValue = value > 1e12 ? value : value * 1000
  return new Date(dateValue).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function getDesktopShellBridge() {
  if (typeof window === 'undefined') return null
  return window.desktopShell || null
}

const quickRoutes = [
  { label: '进入治理台', desc: '调预算、跑调度、限功率', path: '/scheduler', stamp: '治' },
  { label: '进入处置台', desc: '暂停、恢复、终止真实任务', path: '/tasks', stamp: '令' },
  { label: '进入风险台', desc: '处理高温、异常与告警', path: '/alerts', stamp: '警' },
  { label: '进入复盘台', desc: '查看节能测算与回放', path: '/energy', stamp: '证' },
]
const dashboardTabs = [
  { key: 'overview', label: '概览', desc: '判断与入口' },
  { key: 'access', label: '接入与自检', desc: '接入、自检、桌面服务' },
  { key: 'live', label: '实时态势', desc: 'GPU、图表、告警' },
]

const totalPowerLimit = computed(() =>
  store.gpus.reduce((sum, g) => sum + (g.power_limit || 350), 0)
)

const budget = computed(() => schedulerState.value.budget || {})
const fairnessOverview = computed(() => fairnessState.value.overview || {})
const activeUsers = computed(() => new Set(store.processes.map(p => p.username || 'unknown')).size)
const urgentTasks = computed(() => store.processes.filter(p => (p.priority || 'normal') === 'urgent').length)
const deferrableTasks = computed(() => store.processes.filter(p => (p.priority || 'normal') === 'deferrable').length)
const normalTasks = computed(() => store.processes.filter(p => (p.priority || 'normal') === 'normal').length)
const criticalAlerts = computed(() => store.alerts.filter(alert => alert.severity === 'critical').slice(0, 4))
const hotGpuCount = computed(() => store.gpus.filter(gpu => (gpu.temperature || 0) >= 80).length)
const yieldQueue = computed(() => (fairnessState.value.yield_candidates || []).slice(0, 4))
const topRiskUsers = computed(() => (fairnessState.value.users || []).slice(0, 4))
const budgetActions = computed(() => (budget.value.last_actions || []).slice(0, 4))
const memoryUsagePct = computed(() => {
  if (!store.totalMemoryTotal) return 0
  return Math.round((store.totalMemoryUsed / store.totalMemoryTotal) * 100)
})

const timePeriodInfo = computed(() => {
  const budgetExceeded = !!budget.value.is_exceeded
  if (budgetExceeded) return { label: '预算超限', color: '#C41E3A', bg: 'rgba(196,30,58,0.12)' }

  const h = new Date().getHours()
  if (h >= 9 && h < 12 || h >= 14 && h < 18) return { label: '用电高峰', color: '#C41E3A', bg: 'rgba(196,30,58,0.12)' }
  if (h >= 22 || h < 6) return { label: '用电低谷', color: '#2E8B57', bg: 'rgba(46,139,87,0.12)' }
  return { label: '平峰时段', color: '#3A5F4B', bg: 'rgba(58,95,75,0.12)' }
})

const governanceTip = computed(() => {
  if (budget.value.is_exceeded) {
    return `当前总功率 ${Number(budget.value.current_total_power || 0).toFixed(1)}W，已超出预算 ${Number(budget.value.total_power_budget || 0).toFixed(0)}W，应先收口预算。`
  }
  if ((fairnessOverview.value.violation_user_count || 0) > 0) {
    return `当前有 ${fairnessOverview.value.violation_user_count} 个用户触发额度规则，建议优先执行规则治理和任务让路。`
  }
  if (fairnessOverview.value.level === 'critical') {
    return `当前资源集中度偏高，${fairnessOverview.value.dominant_user ? `${shortUser(fairnessOverview.value.dominant_user)} 占用偏高，` : ''}建议先处理让路候选任务。`
  }
  if (fairnessOverview.value.level === 'watch') {
    return '当前共享开始向少数用户集中，建议通过优先级约束和额度提醒提前干预。'
  }
  if (yieldQueue.value.length) {
    return `系统已识别 ${yieldQueue.value.length} 个候选让路任务，可直接进入处置台处理。`
  }
  if (timePeriodInfo.value.label === '用电高峰' && deferrableTasks.value > 0) {
    return '当前处于高峰时段，建议开启预算治理，让可延迟任务主动让路关键任务。'
  }
  if (!store.processes.length) {
    return '当前没有GPU任务运行，可将此时段作为低负载巡检和策略验证窗口。'
  }
  return '当前集群运行平稳，适合继续积累治理日志与优化前后量化数据。'
})

const sourceBadge = computed(() => {
  if (!sourceState.value.connected) {
    return { label: '数据源离线', detail: '请检查 Agent 服务', cls: 'status-badge--critical' }
  }
  if ((sourceState.value.gpu_count || 0) <= 0) {
    return { label: '无真实GPU', detail: 'Agent 在线，但当前未检测到真实 GPU', cls: 'status-badge--warning' }
  }
  const modeLabel = connectionState.value.mode === 'remote' ? '远程服务器' : '本机'
  return { label: '真实采集', detail: `${sourceState.value.gpu_count} 卡${modeLabel}GPU`, cls: 'status-badge--ok' }
})
const workspaceReady = computed(() => sourceState.value.connected)

const connectionSummary = computed(() => {
  if (connectionState.value.mode === 'remote') {
    return connectionState.value.agent_label || '远程 Agent'
  }
  return '当前电脑'
})

function normalizeRemoteAgentUrl(value) {
  const raw = (value || '').trim()
  if (!raw) return ''

  let candidate = raw
  if (!candidate.includes('://')) {
    candidate = `http://${candidate}`
  }

  try {
    const parsed = new URL(candidate)
    if (!parsed.hostname) {
      return candidate.replace(/\/+$/, '')
    }
    const port = parsed.port || String(REMOTE_AGENT_PORT)
    return `${parsed.protocol}//${parsed.hostname}${port ? `:${port}` : ''}`
  } catch {
    return candidate.replace(/\/+$/, '')
  }
}

function extractRemoteHost(value) {
  const normalized = normalizeRemoteAgentUrl(value)
  if (!normalized) return ''
  try {
    return new URL(normalized).hostname || ''
  } catch {
    return ''
  }
}

const remoteAddressState = computed(() => {
  const raw = (connectionForm.value.agent_url || '').trim()
  const normalized = normalizeRemoteAgentUrl(raw)
  const host = extractRemoteHost(raw) || '10.151.225.108'
  const missingPort = !!raw && !raw.includes(`:${REMOTE_AGENT_PORT}`) && !/:\d+$/.test(raw)

  return {
    raw,
    normalized,
    host,
    missingPort,
    healthUrl: normalized ? `${normalized}/api/health` : `http://${host}:${REMOTE_AGENT_PORT}/api/health`,
  }
})

const remoteTargetUrl = computed(() => (
  remoteAddressState.value.normalized || `http://${remoteAddressState.value.host}:${REMOTE_AGENT_PORT}`
))

const remoteLocalHealthUrl = computed(() => `http://127.0.0.1:${REMOTE_AGENT_PORT}/api/health`)
const canExportRemoteAgent = computed(() => Boolean(getDesktopShellBridge()?.exportAgentPackage))
const canOpenLocalPath = computed(() => Boolean(getDesktopShellBridge()?.openPath))
const canCopyFromWorkbench = computed(() => (
  Boolean(getDesktopShellBridge()?.copyText) ||
  (typeof navigator !== 'undefined' && Boolean(navigator.clipboard?.writeText))
))

const connectionGuide = computed(() => {
  if (connectionForm.value.mode === 'local') {
    return {
      title: '本机使用方式',
      desc: '适合演示或直接管理当前电脑。平台会固定连接本机 Agent，不需要手填地址。',
      steps: [
        '先在当前电脑启动 server-agent。',
        '确认本机健康检查可以打开。',
        '回到平台点击“测试连接”或“保存并切换”。',
      ],
      commands: [
        'cd server-agent',
        'python .\\main.py',
        `Invoke-RestMethod ${connectionState.value.default_local_url}/api/health`,
      ],
      extra: '如果你使用的是桌面安装版，本机模式下通常会由桌面壳自动拉起本机服务。',
    }
  }

  return {
    title: canExportRemoteAgent.value ? '远端接入向导' : '远端主机最短启动步骤',
    desc: canExportRemoteAgent.value
      ? '桌面版会直接把远端 Agent 包导出到本机桌面。把整个文件夹复制到服务器后，双击启动脚本即可运行。'
      : '适合连接实验室服务器。平台接的是远端 Agent 接口，不是远程桌面账号本身。',
    steps: canExportRemoteAgent.value
      ? [
          '先点击下方“导出远端 Agent 包”，平台会直接把完整 Agent 文件夹放到本机桌面。',
          `把整个 ${REMOTE_AGENT_EXPORT_DIRNAME} 文件夹复制到远端主机，例如桌面或 C:\\gpu-agent。`,
          `在远端主机双击 ${REMOTE_AGENT_START_SCRIPT}；它会启动 GPUServerAgent.exe，并尝试放行 ${REMOTE_AGENT_PORT} 端口。`,
          `回到平台填写服务器 IP 或完整地址，例如 ${remoteTargetUrl.value}，然后点击“测试连接”或“保存并切换”。`,
        ]
      : [
          '把打包好的 agent 整个文件夹复制到远端主机，例如 C:\\gpu-agent。',
          '在远端主机上运行 GPUServerAgent.exe。',
          `先在远端主机本机确认 ${remoteLocalHealthUrl.value} 可返回 JSON，再回平台连接。`,
        ],
    commands: canExportRemoteAgent.value
      ? [
          `双击: ${REMOTE_AGENT_START_SCRIPT}`,
          `健康检查: ${remoteLocalHealthUrl.value}`,
          `平台连接地址: ${remoteTargetUrl.value}`,
        ]
      : [
          'cd C:\\gpu-agent',
          'Start-Process -FilePath .\\GPUServerAgent.exe -WorkingDirectory $PWD',
          `Invoke-RestMethod ${remoteLocalHealthUrl.value}`,
          `netsh advfirewall firewall add rule name="GPU Server Agent ${REMOTE_AGENT_PORT}" dir=in action=allow protocol=TCP localport=${REMOTE_AGENT_PORT}`,
        ],
    extra: canExportRemoteAgent.value
      ? `平台会连接 ${remoteTargetUrl.value}。如果你只填 IP，系统会自动补全默认端口 ${REMOTE_AGENT_PORT}。${remoteAssistState.value.exportedPath ? ` 最近一次导出目录：${remoteAssistState.value.exportedPath}。` : ''}`
      : `平台会连接 ${remoteTargetUrl.value}。如果你只填 IP，系统会自动补全默认端口 ${REMOTE_AGENT_PORT}。`,
  }
})

const connectionDiagnostics = computed(() => {
  if (connectionForm.value.mode === 'local') {
    return [
      `本机模式固定接入 ${connectionState.value.default_local_url}。`,
      '如果没有数据，优先检查当前电脑上的 Agent 是否已启动。',
    ]
  }

  const hints = []
  if (canExportRemoteAgent.value) {
    hints.push(`桌面版可直接导出远端 Agent 包；复制到服务器后双击 ${REMOTE_AGENT_START_SCRIPT} 即可启动。`)
  }
  if (!remoteAddressState.value.raw) {
    hints.push(`请输入远端 Agent 地址，格式如 http://10.151.225.108:${REMOTE_AGENT_PORT}。`)
  } else {
    if (remoteAddressState.value.missingPort) {
      hints.push(`你当前更像只填了 IP，平台会自动按默认端口补成 ${remoteAddressState.value.normalized}。`)
    } else {
      hints.push(`当前将按 ${remoteAddressState.value.normalized} 测试远端 Agent。`)
    }
    hints.push(`先在远端主机本机打开 ${remoteLocalHealthUrl.value}，确认能返回健康状态。`)
  }
  hints.push('如果端口能通但平台仍提示不可达，通常是 8001 上不是我们的 Agent，或 Agent 已卡住。')
  return hints
})

const fairnessTone = computed(() => {
  if (fairnessOverview.value.level === 'critical') {
    return { color: '#C41E3A', bg: 'rgba(196,30,58,0.12)', label: '需干预' }
  }
  if (fairnessOverview.value.level === 'watch') {
    return { color: '#B8860B', bg: 'rgba(184,134,11,0.12)', label: '需关注' }
  }
  return { color: '#2E8B57', bg: 'rgba(46,139,87,0.12)', label: '较均衡' }
})

const boardTone = computed(() => {
  if (budget.value.is_exceeded || (fairnessOverview.value.violation_user_count || 0) > 0) {
    return {
      badge: '立即执行',
      title: '系统已经进入需要主动治理的状态',
      color: '#C41E3A',
      bg: 'rgba(196,30,58,0.10)',
      border: 'rgba(196,30,58,0.16)',
    }
  }
  if (yieldQueue.value.length || hotGpuCount.value > 0 || fairnessOverview.value.level === 'watch') {
    return {
      badge: '建议干预',
      title: '当前已经出现明显信号，建议在本轮完成一次治理动作',
      color: '#B8860B',
      bg: 'rgba(184,134,11,0.10)',
      border: 'rgba(184,134,11,0.16)',
    }
  }
  return {
    badge: '继续观测',
    title: '当前更适合观测、留痕并等待更具代表性的真实负载窗口',
    color: '#2E8B57',
    bg: 'rgba(46,139,87,0.10)',
    border: 'rgba(46,139,87,0.16)',
  }
})

const recommendationList = computed(() => {
  const recommendations = fairnessState.value.recommendations || []
  if (recommendations.length) return recommendations.slice(0, 3)
  return [governanceTip.value]
})

const selfCheckSummary = computed(() => selfCheckState.value.summary || {})
const selfCheckBadgeClass = computed(() => ({
  ok: 'status-badge--ok',
  warning: 'status-badge--warning',
  critical: 'status-badge--critical',
}[selfCheckSummary.value.status] || 'status-badge--warning'))
const selfCheckBadgeLabel = computed(() => ({
  ok: '主体链路正常',
  warning: '仍需确认',
  critical: '链路异常',
}[selfCheckSummary.value.status] || '等待自检'))
const selfCheckLastTime = computed(() => formatRuntimeTime(selfCheckState.value.checked_at))
const canRestartDesktopServices = computed(() => Boolean(getDesktopShellBridge()?.restartManagedServices))
const desktopServiceCards = computed(() =>
  ['backend', 'agent']
    .map((key) => desktopServiceState.value?.[key])
    .filter(Boolean),
)
const hasDemoAlert = computed(() =>
  store.alerts.some((alert) => alert?.alert_type === 'self_check' && !alert?.acknowledged),
)
const journeySteps = computed(() => {
  const selfCheckOk = selfCheckSummary.value.status === 'ok'
  const hasDispatch = Boolean(lastDispatch.value)

  return [
    {
      key: 'connect',
      index: 1,
      title: '接通 Agent',
      done: workspaceReady.value,
      active: !workspaceReady.value,
      action: '留在接入中心',
      desc: workspaceReady.value
        ? `当前已接入 ${connectionSummary.value}，可以继续验证平台主体链路。`
        : '先在上方接入中心完成本机或远程 Agent 的测试和保存。',
    },
    {
      key: 'self-check',
      index: 2,
      title: '完成平台自检',
      done: selfCheckOk,
      active: workspaceReady.value && !selfCheckOk,
      action: selfCheckOk ? '自检已完成' : '点击平台自检',
      desc: selfCheckOk
        ? '治理后端、Agent、GPU 采集和实时连接已经过一轮主体检查。'
        : '确认后端、Agent、GPU 与实时连接状态，不要在链路未通时直接做治理动作。',
    },
    {
      key: 'alert',
      index: 3,
      title: '验证风险链路',
      done: hasDemoAlert.value,
      active: workspaceReady.value && selfCheckOk && !hasDemoAlert.value,
      action: hasDemoAlert.value ? '去风险台确认' : '生成测试告警',
      desc: hasDemoAlert.value
        ? '测试告警已经出现，现在可以进入风险台完成确认流程。'
        : '生成一条可安全忽略的测试告警，确认“工作台 -> 风险台”链路真的能走通。',
    },
    {
      key: 'dispatch',
      index: 4,
      title: '执行一次治理',
      done: hasDispatch,
      active: workspaceReady.value && selfCheckOk && (!hasDemoAlert.value || hasDemoAlert.value) && !hasDispatch,
      action: hasDispatch ? '已完成首轮治理' : '执行真实治理或去治理台',
      desc: hasDispatch
        ? '平台已经完成过一轮真实治理动作，接下来可以去复盘台看结果。'
        : store.gpus.length
          ? '当真实 GPU 在线时，执行一次治理动作或预算治理，验证平台不是只会看。'
          : '当前还没有真实 GPU 或真实负载，建议先等待可演示的真实窗口。',
    },
  ]
})

const todoItems = computed(() => {
  const items = []

  if (budget.value.is_exceeded) {
    items.push({
      tone: 'critical',
      title: '总功率已超预算',
      desc: `当前 ${Number(budget.value.current_total_power || 0).toFixed(1)}W，超出上限 ${Math.abs(Number(budget.value.remaining_power || 0)).toFixed(1)}W。`,
      path: '/scheduler',
      cta: '去治理台',
    })
  }

  if ((fairnessOverview.value.violation_user_count || 0) > 0) {
    items.push({
      tone: 'critical',
      title: '用户额度规则被触发',
      desc: `${fairnessOverview.value.violation_user_count} 个用户触发 ${fairnessOverview.value.violation_count || 0} 条规则，应优先约束其普通/可延迟任务。`,
      path: '/tasks',
      cta: '去处置台',
    })
  }

  if (yieldQueue.value.length) {
    items.push({
      tone: 'warning',
      title: '存在建议让路任务',
      desc: `首个候选为 PID ${yieldQueue.value[0].pid}，原因：${yieldQueue.value[0].yield_reason}`,
      path: '/tasks',
      cta: '查看候选',
    })
  }

  if (criticalAlerts.value.length) {
    items.push({
      tone: 'critical',
      title: '出现严重告警',
      desc: criticalAlerts.value[0].message,
      path: '/alerts',
      cta: '查看风险',
    })
  }

  if (hotGpuCount.value > 0) {
    items.push({
      tone: 'warning',
      title: '存在高温 GPU',
      desc: `${hotGpuCount.value} 张 GPU 温度达到 80°C 以上，建议检查热卡并考虑限功率。`,
      path: '/scheduler',
      cta: '快速处理',
    })
  }

  if (!items.length) {
    items.push({
      tone: 'ok',
      title: '当前无必须立即处置事项',
      desc: '平台已具备治理能力，但当前更适合继续观测、积累样本和导出复盘材料。',
      path: '/energy',
      cta: '前往复盘',
    })
  }

  return items.slice(0, 4)
})

function statusBadgeClass(status = 'warning') {
  return {
    ok: 'status-badge--ok',
    warning: 'status-badge--warning',
    critical: 'status-badge--critical',
  }[status] || 'status-badge--warning'
}

function statusLabel(status = 'warning') {
  return {
    ok: '正常',
    warning: '需关注',
    critical: '异常',
  }[status] || '待确认'
}

function syncConnectionState(connection, force = false) {
  if (!connection) return
  connectionState.value = {
    mode: connection.mode || 'local',
    mode_label: connection.mode_label || '本机模式',
    agent_url: connection.agent_url || connectionState.value.agent_url,
    agent_label: connection.agent_label || (connection.mode === 'remote' ? '远程 Agent' : '本机 Agent'),
    connected: !!connection.connected,
    updated_at: connection.updated_at || null,
    default_local_url: connection.default_local_url || connectionState.value.default_local_url,
    target_hint: connection.target_hint || '',
    agent_health: connection.agent_health || null,
  }
  if (force || !connectionDirty.value) {
    connectionForm.value = {
      mode: connectionState.value.mode,
      agent_url: connectionState.value.mode === 'remote' ? (connectionState.value.agent_url || '') : '',
      agent_label: connectionState.value.agent_label || '',
    }
    connectionDirty.value = false
  }
}

function buildConnectionPayload() {
  return {
    mode: connectionForm.value.mode,
    agent_url: connectionForm.value.mode === 'remote' ? normalizeRemoteAgentUrl(connectionForm.value.agent_url) : null,
    agent_label: connectionForm.value.agent_label.trim(),
  }
}

async function loadConnectionConfig(force = false) {
  try {
    const { data } = await getConnectionConfig()
    syncConnectionState(data, force)
  } catch {}
}

function applyDesktopServiceState(payload = {}) {
  const services = payload?.services
  if (!services || typeof services !== 'object') {
    return
  }
  desktopServiceState.value = services
}

async function loadDesktopOpsState() {
  const shellBridge = getDesktopShellBridge()
  if (!shellBridge?.getRuntimeInfo || !shellBridge?.getServiceState) {
    desktopOpsReady.value = false
    return
  }

  try {
    const [runtime, serviceState] = await Promise.all([
      shellBridge.getRuntimeInfo(),
      shellBridge.getServiceState(),
    ])
    desktopRuntime.value = {
      runtimeRoot: runtime?.runtimeRoot || '',
      logsRoot: runtime?.logsRoot || '',
      backendBaseUrl: runtime?.backendBaseUrl || '',
      agentBaseUrl: runtime?.agentBaseUrl || '',
      connectionMode: runtime?.connectionMode || '',
    }
    applyDesktopServiceState(serviceState)
    desktopOpsReady.value = true
  } catch (error) {
    desktopOpsReady.value = false
    desktopOpsFeedback.value = {
      tone: 'warning',
      title: '无法读取桌面服务状态',
      detail: error?.message || '当前环境没有返回桌面运行时信息。',
    }
  }
}

async function refreshDesktopOpsState() {
  desktopOpsBusy.value = true
  try {
    await loadDesktopOpsState()
    desktopOpsFeedback.value = {
      tone: 'ok',
      title: '桌面服务状态已刷新',
      detail: '当前展示的是桌面壳维护的本机服务状态。',
    }
  } finally {
    desktopOpsBusy.value = false
  }
}

async function openDesktopPath(targetPath, title) {
  const shellBridge = getDesktopShellBridge()
  if (!targetPath || !shellBridge?.openPath) {
    return
  }

  try {
    await shellBridge.openPath(targetPath)
  } catch (error) {
    desktopOpsFeedback.value = {
      tone: 'warning',
      title: `${title}打开失败`,
      detail: error?.message || '请稍后重试。',
    }
  }
}

async function restartDesktopServices() {
  const shellBridge = getDesktopShellBridge()
  if (!shellBridge?.restartManagedServices) {
    return
  }
  if (!window.confirm('这会让桌面壳重新检查并拉起本机后端与本机 Agent，是否继续？')) {
    return
  }

  desktopOpsBusy.value = true
  desktopOpsFeedback.value = {
    tone: 'warning',
    title: '正在重拉本机服务',
    detail: '桌面壳正在重新检查本机后端和 Agent，页面可能会自动刷新。',
  }

  try {
    const result = await shellBridge.restartManagedServices()
    applyDesktopServiceState(result)
    if (result?.runtime) {
      desktopRuntime.value = {
        runtimeRoot: result.runtime.runtimeRoot || desktopRuntime.value.runtimeRoot,
        logsRoot: result.runtime.logsRoot || desktopRuntime.value.logsRoot,
        backendBaseUrl: result.runtime.backendBaseUrl || desktopRuntime.value.backendBaseUrl,
        agentBaseUrl: result.runtime.agentBaseUrl || desktopRuntime.value.agentBaseUrl,
        connectionMode: result.runtime.connectionMode || desktopRuntime.value.connectionMode,
      }
    }

    if (!result?.ok) {
      desktopOpsFeedback.value = {
        tone: 'critical',
        title: '本机服务重拉失败',
        detail: result?.error || '请打开日志目录查看失败原因。',
      }
      return
    }

    desktopOpsFeedback.value = {
      tone: 'ok',
      title: '本机服务已重新检查',
      detail: '桌面壳已经重新同步本机服务，接下来会自动恢复页面数据。',
    }
    await Promise.all([
      loadGovernance(),
      runPlatformSelfCheck(),
      loadDesktopOpsState(),
    ])
  } catch (error) {
    desktopOpsFeedback.value = {
      tone: 'critical',
      title: '本机服务重拉失败',
      detail: error?.message || '请打开日志目录查看失败原因。',
    }
  } finally {
    desktopOpsBusy.value = false
  }
}

async function runPlatformSelfCheck() {
  selfCheckBusy.value = true
  try {
    const { data } = await getSystemSelfCheck()
    selfCheckState.value = data
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '平台自检失败'
    selfCheckState.value = {
      checked_at: Date.now() / 1000,
      summary: {
        status: 'critical',
        title: '平台自检失败',
        message: detail,
      },
      checks: [],
      gpu_count: 0,
      process_count: 0,
      ws_connections: 0,
      llm_available: false,
    }
  } finally {
    selfCheckBusy.value = false
  }
}

const fullReportExporting = ref(false)
async function doExportFullReport() {
  fullReportExporting.value = true
  try {
    const res = await exportFullGovernanceReport(24)
    await exportTextFile(res.data, {
      filename: 'full-governance-report.md',
      mime: 'text/markdown; charset=utf-8',
    })
  } catch (error) {
    console.error('综合报告导出失败', error)
  }
  fullReportExporting.value = false
}

async function generateDemoAlert() {
  demoAlertBusy.value = true
  try {
    const { data } = await createDemoAlert()
    demoAlertFeedback.value = {
      tone: 'ok',
      title: '测试告警已写入',
      detail: data?.message || '现在可以进入风险台，验证告警确认链路。',
    }
    if (data?.alert) {
      store.$patch({
        alerts: [data.alert, ...store.alerts].slice(0, 100),
      })
    }
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '测试告警写入失败'
    demoAlertFeedback.value = {
      tone: 'critical',
      title: '测试告警写入失败',
      detail,
    }
  } finally {
    demoAlertBusy.value = false
  }
}

async function testConnection() {
  connectionBusy.value = true
  try {
    const { data } = await testConnectionConfig(buildConnectionPayload())
    connectionFeedback.value = {
      tone: data.success ? 'ok' : 'warning',
      title: data.success ? '目标 Agent 可达' : '目标 Agent 不可达',
      detail: data.success
        ? `已连接到 ${data.agent_url}，检测到 ${Number(data.agent_health?.gpu_count || 0)} 张 GPU。`
        : `已尝试连接 ${data.agent_url}。请先确认目标主机上的 GPUServerAgent.exe 已启动，并检查 ${data.agent_url}/api/health 是否能打开。`,
    }
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '连接测试失败'
    const hint = connectionForm.value.mode === 'remote'
      ? ` 建议先在远端主机本机执行 Invoke-RestMethod http://127.0.0.1:${REMOTE_AGENT_PORT}/api/health。`
      : ''
    connectionFeedback.value = { tone: 'critical', title: '连接测试失败', detail: `${detail}${hint}` }
  } finally {
    connectionBusy.value = false
  }
}

async function saveConnection() {
  connectionBusy.value = true
  try {
    const { data } = await updateConnectionConfig(buildConnectionPayload())
    syncConnectionState(data.connection, true)
    connectionFeedback.value = {
      tone: data.connection?.connected ? 'ok' : 'warning',
      title: data.connection?.connected ? '接入配置已切换' : '接入配置已保存',
      detail: data.connection?.connected
        ? `当前已切换到 ${data.connection.mode_label}，目标 ${data.connection.agent_url}。`
        : `配置已保存到 ${data.connection.mode_label}，当前尝试目标为 ${data.connection.agent_url}，但目标 Agent 目前不可达。`,
    }
    await loadGovernance()
    await runPlatformSelfCheck()
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '接入配置保存失败'
    connectionFeedback.value = { tone: 'critical', title: '接入配置保存失败', detail }
  } finally {
    connectionBusy.value = false
  }
}

function setRemoteAssistFeedback(tone, title, detail) {
  remoteAssistState.value = {
    ...remoteAssistState.value,
    feedback: { tone, title, detail },
  }
}

async function copyPlainText(value) {
  const text = String(value || '')
  const shellBridge = getDesktopShellBridge()

  if (shellBridge?.copyText) {
    await shellBridge.copyText(text)
    return
  }

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  throw new Error('当前环境不支持复制到剪贴板')
}

async function copyGuideCommands() {
  try {
    await copyPlainText(connectionGuide.value.commands.join('\r\n'))
    setRemoteAssistFeedback('ok', '已复制启动说明', '可以直接发给远端主机的使用者。')
  } catch (error) {
    setRemoteAssistFeedback('warning', '复制失败', error?.message || '无法复制启动说明。')
  }
}

async function copyRemoteHealthUrl() {
  try {
    await copyPlainText(remoteLocalHealthUrl.value)
    setRemoteAssistFeedback('ok', '已复制健康检查地址', `请在远端主机本机打开 ${remoteLocalHealthUrl.value}。`)
  } catch (error) {
    setRemoteAssistFeedback('warning', '复制失败', error?.message || '无法复制健康检查地址。')
  }
}

async function exportRemoteAgentPackage() {
  const shellBridge = getDesktopShellBridge()
  if (!shellBridge?.exportAgentPackage) {
    setRemoteAssistFeedback('warning', '当前环境不支持导出', '请使用桌面安装版来导出远端 Agent 包。')
    return
  }

  remoteAssistState.value = {
    ...remoteAssistState.value,
    busy: true,
    feedback: null,
  }

  try {
    const result = await shellBridge.exportAgentPackage()
    if (result?.canceled) {
      remoteAssistState.value = {
        ...remoteAssistState.value,
        busy: false,
      }
      return
    }

    if (!result?.ok) {
      throw new Error(result?.error || '远端 Agent 包导出失败')
    }

    remoteAssistState.value = {
      busy: false,
      exportedPath: result.targetDir || '',
      feedback: {
        tone: 'ok',
        title: '远端 Agent 包已导出',
        detail: `已导出到 ${result.targetDir}。导出位置：${result.destinationLabel || 'desktop'}。把整个 ${REMOTE_AGENT_EXPORT_DIRNAME} 文件夹复制到远端主机后，双击 ${result.scriptName || REMOTE_AGENT_START_SCRIPT} 即可。`,
      },
    }
  } catch (error) {
    remoteAssistState.value = {
      ...remoteAssistState.value,
      busy: false,
      feedback: {
        tone: 'critical',
        title: '导出失败',
        detail: error?.message || '远端 Agent 包导出失败。',
      },
    }
  }
}

async function openExportedAgentFolder() {
  const shellBridge = getDesktopShellBridge()
  if (!remoteAssistState.value.exportedPath || !shellBridge?.openPath) {
    return
  }

  try {
    await shellBridge.openPath(remoteAssistState.value.exportedPath)
  } catch (error) {
    setRemoteAssistFeedback('warning', '无法打开目录', error?.message || '请手动打开导出目录。')
  }
}

async function loadGovernance() {
  try {
    const [{ data: schedulerData }, { data: healthData }, { data: fairnessData }] = await Promise.all([
      getSchedulerStatus(),
      healthCheck(),
      getFairnessGovernance(),
    ])
    schedulerState.value = schedulerData
    fairnessState.value = fairnessData
    const gpuCount = Number(healthData?.agent_info?.gpu_count || 0)
    syncConnectionState(healthData?.connection)
    sourceState.value = {
      connected: !!healthData?.agent_connected,
      gpu_count: gpuCount,
      label: gpuCount > 0 ? '真实采集' : '无真实GPU',
      detail: gpuCount > 0
        ? `当前接入 ${connectionState.value.mode === 'remote' ? '远程服务器' : '本机'} Agent，已检测到真实 GPU`
        : 'Agent 在线，但当前未检测到真实 GPU',
    }
  } catch (e) {
    sourceState.value = {
      connected: false,
      gpu_count: 0,
      label: '未连接',
      detail: '无法获取调度与数据源状态',
    }
    await loadConnectionConfig()
    fairnessState.value = {
      overview: {
        fairness_index: 0,
        level: 'critical',
        summary: '无法获取公平治理分析结果。',
        active_users: 0,
        dominant_user: null,
        highest_share_pct: 0,
        reclaimable_candidates: 0,
      },
      users: [],
      recommendations: [],
      yield_candidates: [],
    }
  }
}

function formatActionLabel(action = '') {
  return {
    set_power_limit: '限功率',
    pause_task: '暂停任务',
    resume_task: '恢复任务',
  }[action] || action
}

function setFeedback(tone, title, detail) {
  actionFeedback.value = { tone, title, detail, timestamp: Date.now() }
}

function formatFeedbackDetail(payload) {
  const ruleCount = (payload.rule_results || []).filter(item => item.success).length
  const budgetCount = (payload.budget_results || []).filter(item => item.success).length
  const aiCount = (payload.ai_results || []).filter(item => item.success).length
  const total = ruleCount + budgetCount + aiCount
  if (!total) return '本次未执行实际治理动作，系统判断当前状态可继续观察。'
  return `已执行 ${total} 条动作，其中规则 ${ruleCount} 条、预算 ${budgetCount} 条、AI ${aiCount} 条。`
}

async function executeDispatch() {
  if (!store.gpus.length) {
    setFeedback('warning', '当前没有可治理 GPU', '请等待真实 GPU 数据接入后再执行治理动作。')
    return
  }
  if (!window.confirm('这会对真实任务和真实功耗上限执行治理动作，是否继续？')) return

  actionBusy.value = true
  try {
    const { data } = await runScheduleOnce({ dry_run: false, acknowledge_risk: true })
    lastDispatch.value = data
    setFeedback('ok', '治理动作已执行', formatFeedbackDetail(data))
    await loadGovernance()
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '执行治理动作失败'
    setFeedback('critical', '治理执行失败', detail)
  } finally {
    actionBusy.value = false
  }
}

async function measureOptimization() {
  if (!store.gpus.length) {
    setFeedback('warning', '当前没有可分析 GPU', '请等待真实 GPU 数据接入后再做能耗测算。')
    return
  }

  actionBusy.value = true
  try {
    const { data } = await runOptimize()
    optimizePreview.value = data
    if (data.insufficient_data) {
      setFeedback('warning', '真实数据不足', data.message || '当前历史样本不足，暂不生成优化结论。')
    } else if (data.low_load) {
      setFeedback('warning', '当前仅生成观察结论', '设备功耗很低，平台不会给出夸张节能值，建议继续观察真实负载窗口。')
    } else {
      setFeedback('ok', '已生成理论节能测算', `理论节省 ${Number(data.estimated_saving_w || 0).toFixed(0)}W。`)
    }
    await loadGovernance()
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '能耗测算失败'
    setFeedback('critical', '测算失败', detail)
  } finally {
    actionBusy.value = false
  }
}

async function quickBudgetAction() {
  if (!store.gpus.length) {
    setFeedback('warning', '当前没有可治理 GPU', '请等待真实 GPU 数据接入后再调整预算治理。')
    return
  }

  if (budget.value.enabled) {
    router.push('/scheduler')
    return
  }

  const targetBudget = Math.max(400, Number(budget.value.total_power_budget || totalPowerLimit.value || 1200))
  if (!window.confirm(`将以 ${targetBudget}W 启用总功率预算治理，是否继续？`)) return

  actionBusy.value = true
  try {
    await setPowerBudget(true, targetBudget)
    setFeedback('ok', '预算治理已启用', `当前预算上限为 ${targetBudget}W，可继续前往治理台做精细调整。`)
    await loadGovernance()
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '预算治理启用失败'
    setFeedback('critical', '预算治理启用失败', detail)
  } finally {
    actionBusy.value = false
  }
}

onMounted(() => {
  loadConnectionConfig(true)
  loadGovernance()
  runPlatformSelfCheck()
  loadDesktopOpsState()
  if (getDesktopShellBridge()?.onServiceState) {
    removeDesktopServiceListener = getDesktopShellBridge().onServiceState(applyDesktopServiceState)
  }
  refreshTimer = setInterval(loadGovernance, 8000)
})

watch(
  () => connectionForm.value.mode,
  (mode, previousMode) => {
    if (!mode || mode === previousMode) return

    if (mode === 'local') {
      connectionForm.value.agent_url = ''
      if (!connectionForm.value.agent_label || connectionForm.value.agent_label === '远程 Agent') {
        connectionForm.value.agent_label = '本机 Agent'
      }
      return
    }

    if (!connectionForm.value.agent_label || connectionForm.value.agent_label === '本机 Agent') {
      connectionForm.value.agent_label = '远程 Agent'
    }
    if (!connectionForm.value.agent_url && connectionState.value.mode === 'remote') {
      connectionForm.value.agent_url = connectionState.value.agent_url || ''
    }
  },
)

watch(
  workspaceReady,
  (ready) => {
    if (!ready && activeTab.value !== 'access') {
      activeTab.value = 'access'
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  clearInterval(refreshTimer)
  removeDesktopServiceListener?.()
})
</script>

<template>
  <div class="dashboard ink-page-shell">
    <WorkspaceSummary
      :eyebrow="workspaceReady ? '治理工作台 · 第一屏先给判断与动作' : '接入中心 · 先接通，再解锁治理页面'"
      :title="workspaceReady ? '不是只看 GPU，而是先知道现在该不该动、该动谁、动完如何回放' : '当前先完成 Agent 接入，接通后再开放治理、处置、风险与复盘功能'"
      :description="workspaceReady ? governanceTip : '现在首页先不展示后续治理模块，避免未接入时出现空数据和错误动作。你先完成本机或远程 Agent 接入，再进入完整工作台。'"
    >
      <template #meta>
        <div class="governance-hero__side">
          <span class="status-badge" :class="sourceBadge.cls">{{ sourceBadge.label }}</span>
          <span class="status-badge">{{ connectionState.mode_label }}</span>
          <span
            v-if="workspaceReady"
            class="status-badge"
            :style="{ background: timePeriodInfo.bg, color: timePeriodInfo.color, border: '1px solid ' + timePeriodInfo.color + '33' }"
          >
            {{ timePeriodInfo.label }}
          </span>
          <span
            v-if="workspaceReady"
            class="status-badge"
            :style="{ background: fairnessTone.bg, color: fairnessTone.color, border: '1px solid ' + fairnessTone.color + '33' }"
          >
            {{ fairnessTone.label }}
          </span>
          <span v-else class="status-badge status-badge--warning">仅开放接入中心</span>
        </div>
      </template>
    </WorkspaceSummary>

    <WorkspaceTabs v-model="activeTab" :items="dashboardTabs" />

    <template v-if="activeTab === 'access'">
    <section class="connection-panel tech-card">
      <div class="connection-panel__head">
        <div>
          <div class="section-title">接入中心</div>
          <div class="workbench-card__sub">安装后可直接选择使用当前电脑的 Agent，或连接指定服务器上的 Agent。</div>
        </div>
        <div class="connection-panel__badges">
          <span class="status-badge" :class="connectionState.connected ? 'status-badge--ok' : 'status-badge--warning'">
            {{ connectionState.connected ? '接入正常' : '等待连接' }}
          </span>
          <span class="status-badge">{{ connectionState.mode_label }}</span>
        </div>
      </div>

      <div class="connection-layout">
        <div class="connection-card">
          <div class="connection-toggle">
            <button
              class="connection-toggle__item"
              :class="{ 'connection-toggle__item--active': connectionForm.mode === 'local' }"
              @click="connectionForm.mode = 'local'; connectionForm.agent_label = '本机 Agent'; connectionDirty = true"
            >
              本机模式
            </button>
            <button
              class="connection-toggle__item"
              :class="{ 'connection-toggle__item--active': connectionForm.mode === 'remote' }"
              @click="connectionForm.mode = 'remote'; connectionForm.agent_label = connectionForm.agent_label || '远程 Agent'; connectionDirty = true"
            >
              远程服务器模式
            </button>
          </div>

          <div class="connection-form">
            <label class="connection-field">
              <span class="connection-field__label">接入名称</span>
              <input
                v-model="connectionForm.agent_label"
                class="connection-input"
                type="text"
                maxlength="120"
                placeholder="例如：本机 Agent / 实验室 4090 服务器"
                @input="connectionDirty = true"
              />
            </label>

            <label class="connection-field">
              <span class="connection-field__label">Agent 地址</span>
              <input
                v-model="connectionForm.agent_url"
                class="connection-input"
                type="text"
                :disabled="connectionForm.mode === 'local'"
                :placeholder="connectionForm.mode === 'local' ? connectionState.default_local_url : 'http://192.168.1.20:8001'"
                @input="connectionDirty = true"
              />
            </label>

            <div class="connection-field__hint">
              {{ connectionForm.mode === 'local'
                ? `本机模式固定接入 ${connectionState.default_local_url}，需要当前电脑已启动 server-agent。`
                : '远程模式请输入目标服务器上 Agent 的地址与端口，例如 http://192.168.1.20:8001。' }}
            </div>

            <div v-if="connectionForm.mode === 'remote' && remoteAddressState.raw" class="connection-smart-tip">
              <div class="connection-smart-tip__title">平台将按这个地址连接</div>
              <div class="connection-smart-tip__value">{{ remoteAddressState.normalized }}</div>
              <div class="connection-smart-tip__desc">
                {{ remoteAddressState.missingPort
                  ? `你刚才更像只填了主机 IP，平台已自动补全默认端口 ${REMOTE_AGENT_PORT}。`
                  : '这是当前会用于测试和保存的目标 Agent 地址。' }}
              </div>
            </div>
          </div>

          <div class="action-grid" style="margin-top: 14px">
            <button class="btn-tech" :disabled="connectionBusy" @click="testConnection">
              {{ connectionBusy ? '测试中...' : '测试连接' }}
            </button>
            <button class="btn-tech btn-tech--primary" :disabled="connectionBusy" @click="saveConnection">
              {{ connectionBusy ? '保存中...' : '保存并切换' }}
            </button>
          </div>

          <div v-if="connectionFeedback" class="action-feedback" :class="`action-feedback--${connectionFeedback.tone}`">
            <div class="action-feedback__title">{{ connectionFeedback.title }}</div>
            <div class="action-feedback__desc">{{ connectionFeedback.detail }}</div>
          </div>
        </div>

        <div class="connection-card connection-card--info">
          <div class="connection-meta">
            <div class="connection-meta__label">当前接入</div>
            <div class="connection-meta__value">{{ connectionSummary }}</div>
            <div class="connection-meta__desc">{{ connectionState.target_hint }}</div>
          </div>

          <div class="connection-facts">
            <div class="connection-facts__item">
              <span class="connection-facts__label">当前地址</span>
              <span class="connection-facts__value">{{ connectionState.agent_url }}</span>
            </div>
            <div class="connection-facts__item">
              <span class="connection-facts__label">GPU 数量</span>
              <span class="connection-facts__value">{{ Number(connectionState.agent_health?.gpu_count || sourceState.gpu_count || 0) }}</span>
            </div>
            <div class="connection-facts__item">
              <span class="connection-facts__label">接入状态</span>
              <span class="connection-facts__value">{{ connectionState.connected ? '在线' : '离线' }}</span>
            </div>
            <div class="connection-facts__item">
              <span class="connection-facts__label">最后保存</span>
              <span class="connection-facts__value">{{ formatConnectionTime(connectionState.updated_at) }}</span>
            </div>
          </div>

          <div class="connection-notes">
            <div v-for="(item, index) in connectionDiagnostics" :key="index" class="connection-notes__item">{{ item }}</div>
          </div>

          <div class="connection-guide">
            <div class="connection-guide__head">
              <div class="connection-guide__title">{{ connectionGuide.title }}</div>
              <div class="connection-guide__desc">{{ connectionGuide.desc }}</div>
            </div>

            <div v-if="connectionForm.mode === 'remote'" class="connection-guide__toolbar">
              <button
                v-if="canExportRemoteAgent"
                class="btn-tech btn-tech--primary"
                :disabled="remoteAssistState.busy"
                @click="exportRemoteAgentPackage"
              >
                {{ remoteAssistState.busy ? '导出中...' : '导出远端 Agent 包' }}
              </button>
              <button v-if="canCopyFromWorkbench" class="btn-tech" @click="copyGuideCommands">
                复制启动说明
              </button>
              <button v-if="canCopyFromWorkbench" class="btn-tech" @click="copyRemoteHealthUrl">
                复制健康检查地址
              </button>
              <button
                v-if="remoteAssistState.exportedPath && canOpenLocalPath"
                class="btn-tech"
                @click="openExportedAgentFolder"
              >
                打开导出目录
              </button>
            </div>

            <div class="connection-guide__steps">
              <div v-for="(step, index) in connectionGuide.steps" :key="index" class="connection-guide__step">
                <span class="connection-guide__idx">{{ index + 1 }}</span>
                <span class="connection-guide__text">{{ step }}</span>
              </div>
            </div>

            <pre class="connection-guide__code">{{ connectionGuide.commands.join('\n') }}</pre>
            <div
              v-if="remoteAssistState.exportedPath && connectionForm.mode === 'remote'"
              class="connection-guide__exported"
            >
              最近导出目录：{{ remoteAssistState.exportedPath }}
            </div>
            <div
              v-if="remoteAssistState.feedback && connectionForm.mode === 'remote'"
              class="action-feedback"
              :class="`action-feedback--${remoteAssistState.feedback.tone}`"
            >
              <div class="action-feedback__title">{{ remoteAssistState.feedback.title }}</div>
              <div class="action-feedback__desc">{{ remoteAssistState.feedback.detail }}</div>
            </div>
            <div class="connection-guide__extra">{{ connectionGuide.extra }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="self-check-panel tech-card">
      <div class="self-check-panel__head">
        <div>
          <div class="section-title">平台自检</div>
          <div class="workbench-card__sub">先确认平台主体链路正常，再去验证风险台与治理动作，不让第一次使用者在空页面里猜。</div>
        </div>
        <div class="connection-panel__badges">
          <span class="status-badge" :class="selfCheckBadgeClass">{{ selfCheckBadgeLabel }}</span>
          <span class="status-badge">{{ selfCheckLastTime }}</span>
        </div>
      </div>

      <div class="self-check-layout">
        <div class="self-check-card self-check-card--main">
          <div class="self-check-card__label">主体结论</div>
          <div class="self-check-card__headline">{{ selfCheckSummary.title }}</div>
          <div class="self-check-card__desc">{{ selfCheckSummary.message }}</div>

          <div class="self-check-facts">
            <div class="self-check-facts__item">
              <span class="self-check-facts__label">GPU</span>
              <strong class="stat-value">{{ Number(selfCheckState.gpu_count || 0) }}</strong>
            </div>
            <div class="self-check-facts__item">
              <span class="self-check-facts__label">进程</span>
              <strong class="stat-value">{{ Number(selfCheckState.process_count || 0) }}</strong>
            </div>
            <div class="self-check-facts__item">
              <span class="self-check-facts__label">实时连接</span>
              <strong class="stat-value">{{ Number(selfCheckState.ws_connections || 0) }}</strong>
            </div>
            <div class="self-check-facts__item">
              <span class="self-check-facts__label">AI 助手</span>
              <strong class="stat-value">{{ selfCheckState.llm_available ? '开' : '关' }}</strong>
            </div>
          </div>

          <div class="action-grid" style="margin-top: 16px">
            <button class="btn-tech btn-tech--primary" :disabled="selfCheckBusy" @click="runPlatformSelfCheck">
              {{ selfCheckBusy ? '自检中...' : '平台自检' }}
            </button>
            <button class="btn-tech" :disabled="demoAlertBusy" @click="generateDemoAlert">
              {{ demoAlertBusy ? '写入中...' : '生成测试告警' }}
            </button>
            <button class="btn-tech btn-tech--primary" :disabled="fullReportExporting || !workspaceReady" @click="doExportFullReport">
              {{ fullReportExporting ? '生成中...' : '一键导出综合报告' }}
            </button>
            <button class="btn-tech" :disabled="!workspaceReady" @click="router.push('/alerts')">
              打开风险台
            </button>
            <button class="btn-tech" :disabled="!workspaceReady" @click="router.push('/scheduler')">
              打开治理台
            </button>
          </div>

          <div class="workbench-card__hint">
            建议顺序：先点“平台自检”，确认后端、Agent、GPU 与实时连接；再点“生成测试告警”，去风险台做一遍确认流程。
          </div>

          <div v-if="demoAlertFeedback" class="action-feedback" :class="`action-feedback--${demoAlertFeedback.tone}`">
            <div class="action-feedback__title">{{ demoAlertFeedback.title }}</div>
            <div class="action-feedback__desc">{{ demoAlertFeedback.detail }}</div>
          </div>
        </div>

        <div class="self-check-card">
          <div class="self-check-card__label">检查明细</div>
          <div v-if="selfCheckState.checks?.length" class="self-check-list">
            <div
              v-for="item in selfCheckState.checks"
              :key="item.key"
              class="self-check-item"
              :class="`self-check-item--${item.status}`"
            >
              <div class="self-check-item__top">
                <span class="self-check-item__title">{{ item.label }}</span>
                <span class="status-badge" :class="statusBadgeClass(item.status)">{{ statusLabel(item.status) }}</span>
              </div>
              <div class="self-check-item__desc">{{ item.detail }}</div>
            </div>
          </div>
          <div v-else class="signal-card__empty">自检结果还没有返回，稍后再试。</div>
        </div>
      </div>
    </section>

    <section v-if="desktopOpsReady" class="desktop-ops-panel tech-card">
      <div class="desktop-ops-panel__head">
        <div>
          <div class="section-title">桌面服务</div>
          <div class="workbench-card__sub">这是桌面安装版自己维护的本机后端与本机 Agent 状态。出问题时先看这里，再决定要不要重拉本机服务。</div>
        </div>
        <div class="connection-panel__badges">
          <span class="status-badge">{{ desktopRuntime.connectionMode === 'remote' ? '远程接入模式' : '本机接入模式' }}</span>
          <span class="status-badge">{{ desktopRuntime.backendBaseUrl || '未识别后端地址' }}</span>
        </div>
      </div>

      <div class="desktop-ops-layout">
        <div class="desktop-ops-services">
          <div
            v-for="service in desktopServiceCards"
            :key="service.key"
            class="desktop-ops-item"
            :class="`desktop-ops-item--${service.status}`"
          >
            <div class="desktop-ops-item__top">
              <div>
                <div class="desktop-ops-item__title">{{ service.label }}</div>
                <div class="desktop-ops-item__meta">端口 {{ service.port || '—' }} · {{ service.managed ? '桌面壳托管' : '外部实例/未托管' }}</div>
              </div>
              <span class="status-badge" :class="statusBadgeClass(service.status === 'error' ? 'critical' : service.status === 'running' ? 'ok' : 'warning')">
                {{ service.status === 'running' ? '运行中' : service.status === 'error' ? '异常' : service.status === 'idle' ? '未运行' : '处理中' }}
              </span>
            </div>
            <div class="desktop-ops-item__desc">{{ service.detail || '暂无状态说明。' }}</div>
          </div>
        </div>

        <div class="desktop-ops-card">
          <div class="desktop-ops-card__label">本机目录</div>
          <div class="desktop-ops-card__path">{{ desktopRuntime.logsRoot || '未识别日志目录' }}</div>
          <div class="desktop-ops-card__sub">优先打开日志目录查看 backend-shell.log 和 agent-shell.log；如果目录没问题，再考虑重拉本机服务。</div>

          <div class="action-grid" style="margin-top: 16px">
            <button class="btn-tech" :disabled="desktopOpsBusy" @click="refreshDesktopOpsState">
              {{ desktopOpsBusy ? '处理中...' : '刷新桌面状态' }}
            </button>
            <button class="btn-tech" :disabled="!desktopRuntime.logsRoot" @click="openDesktopPath(desktopRuntime.logsRoot, '日志目录')">
              打开日志目录
            </button>
            <button class="btn-tech" :disabled="!desktopRuntime.runtimeRoot" @click="openDesktopPath(desktopRuntime.runtimeRoot, '运行目录')">
              打开运行目录
            </button>
            <button class="btn-tech btn-tech--primary" :disabled="desktopOpsBusy || !canRestartDesktopServices" @click="restartDesktopServices">
              重新拉起本机服务
            </button>
          </div>

          <div v-if="desktopOpsFeedback" class="action-feedback" :class="`action-feedback--${desktopOpsFeedback.tone}`">
            <div class="action-feedback__title">{{ desktopOpsFeedback.title }}</div>
            <div class="action-feedback__desc">{{ desktopOpsFeedback.detail }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="journey-panel tech-card">
      <div class="journey-panel__head">
        <div>
          <div class="section-title">下一步路线</div>
          <div class="workbench-card__sub">接入之后不要自己猜。按下面这 4 步走，能更快把平台从“能打开”推进到“能演示”。</div>
        </div>
      </div>

      <div class="journey-steps">
        <div
          v-for="step in journeySteps"
          :key="step.key"
          class="journey-step"
          :class="{ 'journey-step--done': step.done, 'journey-step--active': step.active }"
        >
          <div class="journey-step__idx">{{ step.index }}</div>
          <div class="journey-step__body">
            <div class="journey-step__top">
              <span class="journey-step__title">{{ step.title }}</span>
              <span class="journey-step__action">{{ step.action }}</span>
            </div>
            <div class="journey-step__desc">{{ step.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="!workspaceReady" class="unlock-stage tech-card">
      <div class="unlock-stage__head">
        <div>
          <div class="section-title">待解锁页面</div>
          <div class="unlock-stage__desc">接通 Agent 之前，平台先只开放接入中心；接通之后，下面这些治理页面会自动显示。</div>
        </div>
        <span class="status-badge status-badge--warning">接入后自动解锁</span>
      </div>

      <div class="route-grid" style="margin-top: 14px">
        <div v-for="entry in quickRoutes" :key="entry.path" class="route-entry route-entry--locked">
          <span class="route-entry__stamp">{{ entry.stamp }}</span>
          <span class="route-entry__body">
            <strong>{{ entry.label }}</strong>
            <small>{{ entry.desc }}</small>
          </span>
        </div>
      </div>

      <div class="unlock-stage__note">
        {{ connectionForm.mode === 'local'
          ? `本机模式固定接入 ${connectionState.default_local_url}。`
          : `远程模式将连接 ${remoteAddressState.normalized || '请先填写远端 Agent 地址'}。` }}
      </div>
    </section>
    </template>

    <template v-if="workspaceReady && activeTab === 'overview'">
    <section class="workbench-grid">
      <div class="workbench-card workbench-card--main tech-card">
        <div class="workbench-card__head">
          <div>
            <div class="section-title">治理判断</div>
            <div class="workbench-card__sub">{{ sourceState.detail }}</div>
          </div>
          <span class="status-badge" :style="{ background: boardTone.bg, color: boardTone.color, border: '1px solid ' + boardTone.border }">
            {{ boardTone.badge }}
          </span>
        </div>

        <div class="workbench-card__headline">{{ boardTone.title }}</div>
        <div class="workbench-chips">
          <span class="governance-chip">活跃用户 {{ activeUsers }}</span>
          <span class="governance-chip">紧急任务 {{ urgentTasks }}</span>
          <span class="governance-chip">可延迟 {{ deferrableTasks }}</span>
          <span class="governance-chip">严重告警 {{ criticalAlerts.length }}</span>
        </div>

        <div class="workbench-list">
          <div v-for="(item, index) in recommendationList" :key="index" class="workbench-list__item">
            <span class="workbench-list__idx">{{ index + 1 }}</span>
            <span class="workbench-list__text">{{ item }}</span>
          </div>
        </div>

        <div class="action-grid">
          <button class="btn-tech btn-tech--primary" :disabled="actionBusy || !store.gpus.length" @click="executeDispatch">
            {{ actionBusy ? '执行中...' : '执行一次真实治理' }}
          </button>
          <button class="btn-tech" :disabled="actionBusy" @click="quickBudgetAction">
            {{ budget.enabled ? '前往预算治理' : '一键启用预算治理' }}
          </button>
          <button class="btn-tech" :disabled="actionBusy || !store.gpus.length" @click="measureOptimization">
            先做节能测算
          </button>
          <button class="btn-tech" @click="router.push('/tasks')">
            打开任务处置
          </button>
        </div>
        <div class="workbench-card__hint">“执行一次真实治理”会对真实任务和真实功耗上限生效；“节能测算”只输出理论分析。</div>

        <div v-if="actionFeedback" class="action-feedback" :class="`action-feedback--${actionFeedback.tone}`">
          <div class="action-feedback__title">{{ actionFeedback.title }}</div>
          <div class="action-feedback__desc">{{ actionFeedback.detail }}</div>
        </div>

        <div v-if="optimizePreview && !optimizePreview.insufficient_data" class="action-preview">
          <div class="action-preview__label">{{ optimizePreview.low_load ? '测算结论' : '理论节能预览' }}</div>
          <div class="action-preview__value stat-value">
            {{ optimizePreview.low_load ? '继续观察' : `${optimizePreview.optimized_power?.toFixed(0) || '—'}W` }}
          </div>
          <div class="action-preview__desc">
            {{ optimizePreview.low_load ? '当前整机功耗较低，平台不会给出夸张节能值。' : `理论节省 ${optimizePreview.estimated_saving_w?.toFixed(0) || '0'}W，首条策略：${optimizePreview.suggestions?.[0]?.reason || '继续前往复盘台查看详情。'}` }}
          </div>
        </div>
      </div>

      <div class="workbench-card tech-card">
        <div class="workbench-card__head">
          <div class="section-title">待处置事项</div>
          <span class="workbench-card__count stat-value">{{ todoItems.length }}</span>
        </div>
        <div class="todo-list">
          <button
            v-for="(item, index) in todoItems"
            :key="index"
            class="todo-item"
            :class="`todo-item--${item.tone}`"
            @click="router.push(item.path)"
          >
            <div class="todo-item__top">
              <span class="todo-item__title">{{ item.title }}</span>
              <span class="todo-item__cta">{{ item.cta }}</span>
            </div>
            <div class="todo-item__desc">{{ item.desc }}</div>
          </button>
        </div>
      </div>
    </section>

    <section class="signal-grid">
      <div class="signal-card tech-card">
        <div class="signal-card__head">
          <div class="section-title">候选让路</div>
          <button class="signal-card__link" @click="router.push('/tasks')">去处置台</button>
        </div>
        <div v-if="yieldQueue.length" class="signal-card__body">
          <div v-for="item in yieldQueue" :key="item.pid" class="queue-item">
            <div class="queue-item__top">
              <span class="queue-item__user">{{ shortUser(item.username) }}</span>
              <span class="queue-item__tag">PID {{ item.pid }}</span>
              <span class="queue-item__tag queue-item__tag--accent">{{ item.priority }}</span>
            </div>
            <div class="queue-item__desc">{{ item.yield_reason }}</div>
            <div class="queue-item__meta">让路分 {{ item.yield_score }}</div>
          </div>
        </div>
        <div v-else class="signal-card__empty">当前没有建议优先让路的任务。</div>
      </div>

      <div class="signal-card tech-card">
        <div class="signal-card__head">
          <div class="section-title">重点用户</div>
          <button class="signal-card__link" @click="router.push('/monitor')">看画像</button>
        </div>
        <div v-if="topRiskUsers.length" class="signal-card__body">
          <div v-for="user in topRiskUsers" :key="user.username" class="user-item">
            <div class="user-item__top">
              <span class="user-item__name">{{ shortUser(user.username) }}</span>
              <span class="user-item__score stat-value" :style="{ color: user.fairness_score < 60 ? '#C41E3A' : user.fairness_score < 80 ? '#B8860B' : '#2E8B57' }">
                {{ Number(user.fairness_score || 0).toFixed(0) }}
              </span>
            </div>
            <div class="user-item__meta">
              <span>占用 {{ user.effective_share_pct }}%</span>
              <span>违规 {{ user.violation_count }}</span>
              <span>任务 {{ user.task_count }}</span>
            </div>
            <div class="user-item__desc">{{ user.recommended_action }}</div>
          </div>
        </div>
        <div v-else class="signal-card__empty">当前没有重点用户需要单独干预。</div>
      </div>

      <div class="signal-card tech-card">
        <div class="signal-card__head">
          <div class="section-title">最近动作</div>
          <button class="signal-card__link" @click="router.push('/energy')">去复盘台</button>
        </div>
        <div v-if="budgetActions.length" class="signal-card__body">
          <div v-for="(item, index) in budgetActions" :key="index" class="action-item">
            <div class="action-item__top">
              <span class="action-item__label">{{ formatActionLabel(item.action) }}</span>
              <span v-if="item.target?.gpu_index !== undefined" class="action-item__tag">GPU {{ item.target.gpu_index }}</span>
              <span v-if="item.target?.pid" class="action-item__tag">PID {{ item.target.pid }}</span>
            </div>
            <div class="action-item__desc">{{ item.reason }}</div>
          </div>
        </div>
        <div v-else-if="criticalAlerts.length" class="signal-card__body">
          <div v-for="(alert, index) in criticalAlerts" :key="index" class="action-item action-item--risk">
            <div class="action-item__top">
              <span class="action-item__label">严重告警</span>
              <span class="action-item__tag">GPU {{ alert.gpu_index }}</span>
            </div>
            <div class="action-item__desc">{{ alert.message }}</div>
          </div>
        </div>
        <div v-else class="signal-card__empty">最近没有新的治理动作，适合先触发一次治理或查看复盘。</div>
      </div>

      <div class="signal-card tech-card">
        <div class="signal-card__head">
          <div class="section-title">工作入口</div>
          <div class="signal-card__note">把执行、观察、复盘连起来</div>
        </div>
        <div class="route-grid">
          <button v-for="entry in quickRoutes" :key="entry.path" class="route-entry" @click="router.push(entry.path)">
            <span class="route-entry__stamp">{{ entry.stamp }}</span>
            <span class="route-entry__body">
              <strong>{{ entry.label }}</strong>
              <small>{{ entry.desc }}</small>
            </span>
          </button>
        </div>
      </div>
    </section>
    </template>

    <template v-if="workspaceReady && activeTab === 'live'">
    <div class="section-title" style="margin: 8px 0 4px">运行底盘</div>

    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #3A5F4B, #5B4B8C)">⚡</div>
        <div class="stat-card__content">
          <div class="stat-card__label">当前总功率</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl">{{ store.totalPower.toFixed(1) }}</span>
            <span class="stat-card__unit">W</span>
          </div>
          <div class="stat-card__sub">{{ store.gpus.length }} 张GPU实时汇总</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #C41E3A, #F97316)">⌁</div>
        <div class="stat-card__content">
          <div class="stat-card__label">剩余预算</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl" :style="{ color: budget.is_exceeded ? '#C41E3A' : '#2E8B57' }">{{ Math.abs(budget.remaining_power || 0).toFixed(1) }}</span>
            <span class="stat-card__unit">W</span>
          </div>
          <div class="stat-card__sub">
            {{ budget.is_exceeded ? '预算已超限' : `预算上限 ${budget.total_power_budget || 0}W` }}
          </div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #B8860B, #B8860B)">🌡</div>
        <div class="stat-card__content">
          <div class="stat-card__label">平均温度</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl" :style="{ color: tempColor(store.avgTemperature) }">{{ store.avgTemperature }}</span>
            <span class="stat-card__unit">°C</span>
          </div>
          <div class="stat-card__sub">热点风险与散热压力</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #5B8C7E, #7BB5A3)">人</div>
        <div class="stat-card__content">
          <div class="stat-card__label">活跃用户</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl">{{ activeUsers }}</span>
            <span class="stat-card__unit">人</span>
          </div>
          <div class="stat-card__sub">{{ store.processes.length }} 个GPU进程</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #7B6BA4, #5B4B8C)">优</div>
        <div class="stat-card__content">
          <div class="stat-card__label">任务优先级</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl">{{ urgentTasks }}</span>
            <span class="stat-card__unit">紧急</span>
          </div>
          <div class="stat-card__sub">可延迟 {{ deferrableTasks }} / 普通 {{ normalTasks }}</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #2E8B57, #3A5F4B)">卡</div>
        <div class="stat-card__content">
          <div class="stat-card__label">GPU数量</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl">{{ store.gpus.length }}</span>
            <span class="stat-card__unit">张</span>
          </div>
          <div class="stat-card__sub">{{ sourceState.label }}</div>
        </div>
      </div>
    </div>

    <div class="governance-grid">
      <div class="tech-card governance-panel">
        <div class="section-title">预算治理状态</div>
        <div class="governance-panel__value">
          <span class="stat-value">{{ budget.usage_pct || 0 }}%</span>
          <span>预算占用</span>
        </div>
        <div class="governance-panel__bar">
          <div class="governance-panel__bar-fill" :style="{ width: Math.min(100, Math.max(0, budget.usage_pct || 0)) + '%', background: budget.is_exceeded ? 'var(--gradient-red)' : 'var(--gradient-green)' }"></div>
        </div>
        <div class="governance-panel__hint">
          {{ budget.enabled ? '预算治理已启用' : '预算治理当前关闭' }}，已接管 {{ budget.managed_gpu_count || 0 }} 张GPU
        </div>
      </div>

      <div class="tech-card governance-panel">
        <div class="section-title">任务治理建议</div>
        <div class="governance-panel__desc">{{ governanceTip }}</div>
        <div class="governance-panel__chips">
          <span class="governance-chip">紧急任务 {{ urgentTasks }}</span>
          <span class="governance-chip">普通任务 {{ normalTasks }}</span>
          <span class="governance-chip">可延迟任务 {{ deferrableTasks }}</span>
        </div>
      </div>

      <div class="tech-card governance-panel">
        <div class="section-title">数据来源</div>
        <div class="governance-panel__value">
          <span class="stat-value">{{ sourceState.gpu_count }}</span>
          <span>张卡</span>
        </div>
        <div class="governance-panel__desc">{{ sourceState.detail }}</div>
        <button class="btn-tech" @click="router.push('/scheduler')">进入治理调度页</button>
      </div>

      <div class="tech-card governance-panel">
        <div class="section-title">公平治理指数</div>
        <div class="governance-panel__value">
          <span class="stat-value" :style="{ color: fairnessTone.color }">{{ fairnessOverview.fairness_index ?? 0 }}</span>
          <span>分</span>
        </div>
        <div class="governance-panel__desc">{{ fairnessOverview.summary }}</div>
        <div class="governance-panel__chips">
          <span class="governance-chip" :style="{ color: fairnessTone.color, background: fairnessTone.bg }">{{ fairnessTone.label }}</span>
          <span class="governance-chip">最高占用 {{ fairnessOverview.highest_share_pct || 0 }}%</span>
          <span class="governance-chip">候选让路 {{ fairnessOverview.reclaimable_candidates || 0 }}</span>
          <span class="governance-chip">规则违规 {{ fairnessOverview.violation_user_count || 0 }}</span>
        </div>
      </div>
    </div>

    <div class="section-title" style="margin: 20px 0 12px">GPU 实时状态</div>
    <div class="gpu-grid">
      <div class="gpu-grid__source-badge" v-if="store.gpus.length">
        <span class="source-dot" :style="{ background: store.dataSourceLabel.color }"></span>
        <span class="source-text" :style="{ color: store.dataSourceLabel.color }">{{ store.dataSourceLabel.text }}</span>
        <span v-if="store.dataSourceStatus.gpu_count" class="source-count">{{ store.dataSourceStatus.gpu_count }} 卡</span>
      </div>
      <div
        v-for="gpu in store.gpus"
        :key="gpu.index"
        class="gpu-card tech-card"
        @click="router.push(`/gpu/${gpu.index}`)"
      >
        <div class="gpu-card__header">
          <div class="gpu-card__id">
            <span class="gpu-card__badge">GPU {{ gpu.index }}</span>
            <span class="gpu-card__name">{{ gpu.name }}</span>
          </div>
          <span
            class="status-badge"
            :class="gpu.temperature >= 85 ? 'status-badge--critical' : gpu.temperature >= 70 ? 'status-badge--warning' : 'status-badge--ok'"
          >
            {{ gpu.temperature >= 85 ? '高温' : gpu.temperature >= 70 ? '偏高' : '正常' }}
          </span>
        </div>

        <div class="gpu-card__metrics">
          <div class="metric-item">
            <div class="metric-item__label">温度</div>
            <div class="metric-item__value stat-value" :style="{ color: tempColor(gpu.temperature) }">
              {{ gpu.temperature }}<span class="metric-item__unit">°C</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: Math.min(gpu.temperature, 100) + '%', background: tempColor(gpu.temperature) }"></div>
            </div>
          </div>

          <div class="metric-item">
            <div class="metric-item__label">功耗</div>
            <div class="metric-item__value stat-value">
              {{ gpu.power_usage.toFixed(0) }}<span class="metric-item__unit">/ {{ gpu.power_limit.toFixed(0) }}W</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: powerPct(gpu.power_usage, gpu.power_limit) + '%', background: 'var(--gradient-blue)' }"></div>
            </div>
          </div>

          <div class="metric-item">
            <div class="metric-item__label">GPU利用率</div>
            <div class="metric-item__value stat-value" :style="{ color: utilColor(gpu.gpu_utilization) }">
              {{ gpu.gpu_utilization }}<span class="metric-item__unit">%</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: gpu.gpu_utilization + '%', background: utilColor(gpu.gpu_utilization) }"></div>
            </div>
          </div>

          <div class="metric-item">
            <div class="metric-item__label">显存</div>
            <div class="metric-item__value stat-value">
              {{ fmtMem(gpu.memory_used) }}<span class="metric-item__unit">/ {{ fmtMem(gpu.memory_total) }}G</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: memPct(gpu.memory_used, gpu.memory_total) + '%', background: 'var(--gradient-green)' }"></div>
            </div>
          </div>
        </div>

        <div class="gpu-card__footer">
          <span>风扇 {{ gpu.fan_speed }}%</span>
          <span>SM {{ gpu.clock_sm }} MHz</span>
          <span>MEM {{ gpu.clock_mem }} MHz</span>
        </div>
      </div>

      <div v-if="!store.gpus.length" class="gpu-grid__empty tech-card">
        <div class="text-center" style="padding: 60px 20px; color: var(--text-muted)">
          <div style="font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3">◉</div>
          <div style="font-size: 1rem; margin-bottom: 8px">等待GPU数据...</div>
          <div style="font-size: 0.8rem">请确保 Agent 服务已启动，并确认当前数据源是否为真实采集</div>
        </div>
      </div>
    </div>

    <div class="charts-row" v-if="store.gpus.length">
      <div class="chart-panel tech-card">
        <div class="chart-panel__header">
          <div class="section-title">功耗趋势</div>
        </div>
        <div class="chart-panel__body">
          <PowerTrendChart :gpus="store.gpus" />
        </div>
      </div>
      <div class="chart-panel tech-card">
        <div class="chart-panel__header">
          <div class="section-title">利用率分布</div>
        </div>
        <div class="chart-panel__body">
          <UtilizationChart :gpus="store.gpus" />
        </div>
      </div>
    </div>

    <div class="alerts-strip" v-if="store.alerts.length">
      <div class="section-title" style="margin-bottom: 8px">最近告警</div>
      <div class="alerts-list">
        <div
          v-for="(alert, i) in store.alerts.slice(0, 5)"
          :key="i"
          class="alert-item"
          :class="alert.severity === 'critical' ? 'alert-item--critical' : 'alert-item--warning'"
        >
          <span class="alert-item__icon">{{ alert.severity === 'critical' ? '⚠' : '△' }}</span>
          <span class="alert-item__text">{{ alert.message }}</span>
          <span class="alert-item__time">{{ new Date(alert.timestamp * 1000).toLocaleTimeString('zh-CN') }}</span>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1600px;
  margin: 0 auto;
}

.governance-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 26px;
  margin-bottom: 16px;
  background:
    radial-gradient(circle at top right, rgba(91,75,140,0.08), transparent 35%),
    radial-gradient(circle at bottom left, rgba(58,95,75,0.08), transparent 35%),
    var(--gradient-card);
}

.governance-hero__eyebrow {
  font-size: 0.75rem;
  color: var(--text-muted);
  letter-spacing: 0.12em;
  margin-bottom: 8px;
}

.governance-hero__title {
  font-family: var(--font-song);
  font-weight: 700;
  font-size: 1.6rem;
  line-height: 1.4;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.governance-hero__desc,
.governance-hero__meta {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.governance-hero__side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  min-width: 220px;
}

.connection-panel {
  margin-bottom: 14px;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(46,139,87,0.07), transparent 32%),
    radial-gradient(circle at bottom right, rgba(91,75,140,0.08), transparent 36%),
    linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,252,247,0.56));
}

.connection-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.connection-panel__badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.connection-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 14px;
  margin-top: 18px;
}

.connection-card {
  padding: 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.52);
  border: 1px solid rgba(58,95,75,0.08);
}

.connection-card--info {
  background:
    linear-gradient(180deg, rgba(255,255,255,0.7), rgba(255,252,247,0.48));
}

.connection-toggle {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.connection-toggle__item {
  border: 1px solid rgba(58,95,75,0.08);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255,255,255,0.68);
  color: var(--text-secondary);
  cursor: pointer;
  transition: transform 0.24s ease, border-color 0.24s ease, background 0.24s ease;
}

.connection-toggle__item:hover {
  transform: translateY(-1px);
}

.connection-toggle__item--active {
  border-color: rgba(46,139,87,0.2);
  background: rgba(46,139,87,0.08);
  color: var(--accent-secondary);
}

.connection-form {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.connection-field {
  display: grid;
  gap: 8px;
}

.connection-field__label {
  font-size: 0.76rem;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

.connection-input {
  width: 100%;
  border: 1px solid rgba(58,95,75,0.12);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255,255,255,0.82);
  color: var(--text-primary);
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.24s ease, box-shadow 0.24s ease;
}

.connection-input:focus {
  border-color: rgba(46,139,87,0.26);
  box-shadow: 0 0 0 4px rgba(46,139,87,0.08);
}

.connection-input:disabled {
  opacity: 0.72;
  cursor: not-allowed;
}

.connection-field__hint {
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.connection-smart-tip {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(46,139,87,0.12);
  background: rgba(46,139,87,0.06);
}

.connection-smart-tip__title {
  font-size: 0.74rem;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

.connection-smart-tip__value {
  margin-top: 6px;
  font-size: 0.92rem;
  color: var(--text-primary);
  word-break: break-all;
  font-family: 'JetBrains Mono', monospace;
}

.connection-smart-tip__desc {
  margin-top: 8px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.connection-meta__label {
  font-size: 0.72rem;
  color: var(--text-muted);
  letter-spacing: 0.14em;
}

.connection-meta__value {
  margin-top: 8px;
  font-family: var(--font-song);
  font-size: 1.42rem;
  color: var(--text-primary);
}

.connection-meta__desc {
  margin-top: 8px;
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.75;
}

.connection-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.connection-facts__item {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255,255,255,0.6);
  border: 1px solid rgba(58,95,75,0.06);
}

.connection-facts__label {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

.connection-facts__value {
  display: block;
  margin-top: 6px;
  font-size: 0.86rem;
  color: var(--text-primary);
  line-height: 1.6;
  word-break: break-all;
}

.connection-notes {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

.connection-notes__item {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255,255,255,0.52);
  border: 1px solid rgba(58,95,75,0.06);
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.connection-guide {
  margin-top: 16px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(58,95,75,0.08);
  background: rgba(255,255,255,0.58);
}

.connection-guide__head {
  display: grid;
  gap: 8px;
}

.connection-guide__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.connection-guide__title {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.connection-guide__desc,
.connection-guide__extra {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.72;
}

.connection-guide__steps {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.connection-guide__step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.connection-guide__idx {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(196,30,58,0.08);
  color: var(--ink-vermillion);
  font-size: 0.72rem;
  flex-shrink: 0;
}

.connection-guide__text {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.72;
}

.connection-guide__code {
  margin: 14px 0 0;
  padding: 14px;
  border-radius: 16px;
  background: rgba(26,26,26,0.94);
  color: #f8f5f0;
  font-size: 0.76rem;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'JetBrains Mono', monospace;
}

.connection-guide__exported {
  margin-top: 12px;
  padding: 11px 12px;
  border-radius: 14px;
  border: 1px solid rgba(58,95,75,0.08);
  background: rgba(255,255,255,0.52);
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.7;
  word-break: break-all;
  font-family: 'JetBrains Mono', monospace;
}

.self-check-panel {
  margin-bottom: 14px;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(46,139,87,0.07), transparent 32%),
    radial-gradient(circle at bottom right, rgba(212,175,55,0.08), transparent 34%),
    linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,252,247,0.56));
}

.self-check-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.self-check-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 14px;
  margin-top: 18px;
}

.self-check-card {
  padding: 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.56);
  border: 1px solid rgba(58,95,75,0.08);
}

.self-check-card--main {
  background:
    radial-gradient(circle at top right, rgba(46,139,87,0.08), transparent 30%),
    linear-gradient(180deg, rgba(255,255,255,0.74), rgba(255,252,247,0.52));
}

.self-check-card__label {
  font-size: 0.74rem;
  color: var(--text-muted);
  letter-spacing: 0.12em;
}

.self-check-card__headline {
  margin-top: 14px;
  font-family: var(--font-song);
  font-size: 1.48rem;
  line-height: 1.42;
  color: var(--text-primary);
}

.self-check-card__desc {
  margin-top: 10px;
  font-size: 0.84rem;
  line-height: 1.78;
  color: var(--text-secondary);
}

.self-check-facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.self-check-facts__item {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255,255,255,0.62);
  border: 1px solid rgba(58,95,75,0.06);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.self-check-facts__label {
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

.self-check-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.self-check-item {
  padding: 14px 15px;
  border-radius: 16px;
  background: rgba(255,255,255,0.62);
  border: 1px solid rgba(58,95,75,0.08);
}

.self-check-item--ok {
  border-color: rgba(46,139,87,0.14);
  background: rgba(46,139,87,0.05);
}

.self-check-item--warning {
  border-color: rgba(184,134,11,0.14);
  background: rgba(212,175,55,0.06);
}

.self-check-item--critical {
  border-color: rgba(196,30,58,0.14);
  background: rgba(196,30,58,0.06);
}

.self-check-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.self-check-item__title {
  font-size: 0.88rem;
  color: var(--text-primary);
}

.self-check-item__desc {
  margin-top: 8px;
  font-size: 0.8rem;
  line-height: 1.72;
  color: var(--text-secondary);
}

.desktop-ops-panel,
.journey-panel {
  margin-bottom: 14px;
  padding: 20px;
  background:
    radial-gradient(circle at top right, rgba(58,95,75,0.08), transparent 34%),
    linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,252,247,0.56));
}

.desktop-ops-panel__head,
.journey-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.desktop-ops-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.92fr);
  gap: 14px;
  margin-top: 18px;
}

.desktop-ops-services {
  display: grid;
  gap: 10px;
}

.desktop-ops-item,
.desktop-ops-card {
  padding: 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.56);
  border: 1px solid rgba(58,95,75,0.08);
}

.desktop-ops-item--running {
  border-color: rgba(46,139,87,0.14);
  background: rgba(46,139,87,0.05);
}

.desktop-ops-item--error {
  border-color: rgba(196,30,58,0.14);
  background: rgba(196,30,58,0.06);
}

.desktop-ops-item--starting,
.desktop-ops-item--restarting,
.desktop-ops-item--idle,
.desktop-ops-item--external {
  border-color: rgba(184,134,11,0.14);
  background: rgba(212,175,55,0.05);
}

.desktop-ops-item__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.desktop-ops-item__title {
  font-size: 0.92rem;
  color: var(--text-primary);
}

.desktop-ops-item__meta {
  margin-top: 6px;
  font-size: 0.74rem;
  color: var(--text-muted);
}

.desktop-ops-item__desc,
.desktop-ops-card__sub {
  margin-top: 10px;
  font-size: 0.8rem;
  line-height: 1.72;
  color: var(--text-secondary);
}

.desktop-ops-card__label {
  font-size: 0.74rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.desktop-ops-card__path {
  margin-top: 10px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255,255,255,0.68);
  border: 1px solid rgba(58,95,75,0.08);
  font-size: 0.78rem;
  line-height: 1.72;
  color: var(--text-primary);
  word-break: break-all;
  font-family: 'JetBrains Mono', monospace;
}

.journey-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.journey-step {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255,255,255,0.56);
  border: 1px solid rgba(58,95,75,0.08);
}

.journey-step--done {
  border-color: rgba(46,139,87,0.16);
  background: rgba(46,139,87,0.05);
}

.journey-step--active {
  border-color: rgba(196,30,58,0.16);
  background: rgba(196,30,58,0.05);
}

.journey-step__idx {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(58,95,75,0.08);
  color: var(--accent-secondary);
  font-size: 0.8rem;
}

.journey-step__body {
  min-width: 0;
}

.journey-step__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.journey-step__title {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.journey-step__action {
  font-size: 0.72rem;
  color: var(--accent-secondary);
}

.journey-step__desc {
  margin-top: 8px;
  font-size: 0.78rem;
  line-height: 1.72;
  color: var(--text-secondary);
}

.unlock-stage {
  margin-bottom: 14px;
  padding: 20px;
  background:
    radial-gradient(circle at top right, rgba(212,175,55,0.08), transparent 34%),
    radial-gradient(circle at bottom left, rgba(58,95,75,0.08), transparent 36%),
    linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,252,247,0.56));
}

.unlock-stage__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.unlock-stage__desc,
.unlock-stage__note {
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.74;
}

.unlock-stage__note {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255,255,255,0.56);
  border: 1px solid rgba(58,95,75,0.08);
}

.workbench-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.75fr);
  gap: 14px;
}

.workbench-card {
  padding: 20px;
}

.workbench-card--main {
  background:
    radial-gradient(circle at top right, rgba(91,75,140,0.08), transparent 36%),
    linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,252,247,0.56));
}

.workbench-card__head,
.signal-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.workbench-card__sub,
.signal-card__note {
  margin-top: 8px;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.workbench-card__headline {
  margin-top: 18px;
  font-family: var(--font-song);
  font-weight: 700;
  font-size: 1.58rem;
  line-height: 1.38;
  color: var(--text-primary);
}

.workbench-card__hint {
  margin-top: 12px;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.workbench-card__count {
  font-size: 1.5rem;
  color: var(--text-primary);
}

.workbench-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.workbench-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}

.workbench-list__item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255,255,255,0.52);
  border: 1px solid rgba(58,95,75,0.06);
}

.workbench-list__idx {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.74rem;
  color: var(--ink-vermillion);
  background: rgba(196,30,58,0.08);
}

.workbench-list__text {
  font-size: 0.86rem;
  color: var(--text-secondary);
  line-height: 1.75;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.action-feedback,
.action-preview {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(58,95,75,0.08);
  background: rgba(255,255,255,0.54);
}

.action-feedback--ok {
  border-color: rgba(46,139,87,0.14);
  background: rgba(46,139,87,0.06);
}

.action-feedback--warning {
  border-color: rgba(184,134,11,0.16);
  background: rgba(212,175,55,0.08);
}

.action-feedback--critical {
  border-color: rgba(196,30,58,0.16);
  background: rgba(196,30,58,0.06);
}

.action-feedback__title,
.action-preview__label {
  font-size: 0.78rem;
  color: var(--text-muted);
  letter-spacing: 0.12em;
}

.action-feedback__desc,
.action-preview__desc {
  margin-top: 8px;
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.75;
}

.action-preview__value {
  margin-top: 8px;
  font-size: 1.8rem;
  color: var(--accent-secondary);
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 18px;
}

.todo-item {
  width: 100%;
  text-align: left;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(58,95,75,0.08);
  background: rgba(255,255,255,0.52);
  cursor: pointer;
  transition: transform 0.24s ease, border-color 0.24s ease, background 0.24s ease;
}

.todo-item:hover {
  transform: translateY(-1px);
}

.todo-item--critical {
  border-color: rgba(196,30,58,0.14);
  background: rgba(196,30,58,0.05);
}

.todo-item--warning {
  border-color: rgba(184,134,11,0.14);
  background: rgba(212,175,55,0.06);
}

.todo-item--ok {
  border-color: rgba(46,139,87,0.12);
  background: rgba(46,139,87,0.05);
}

.todo-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.todo-item__title {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.todo-item__cta {
  font-size: 0.72rem;
  color: var(--accent-secondary);
}

.todo-item__desc {
  margin-top: 8px;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.72;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.signal-card {
  padding: 20px;
}

.signal-card__link {
  border: 0;
  background: transparent;
  color: var(--accent-secondary);
  cursor: pointer;
  font-size: 0.76rem;
}

.signal-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}

.signal-card__empty {
  margin-top: 18px;
  font-size: 0.82rem;
  color: var(--text-muted);
  line-height: 1.75;
}

.queue-item,
.user-item,
.action-item {
  padding: 14px 15px;
  border-radius: 16px;
  background: rgba(255,255,255,0.52);
  border: 1px solid rgba(58,95,75,0.08);
}

.queue-item__top,
.user-item__top,
.action-item__top {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;
  flex-wrap: wrap;
}

.queue-item__user,
.user-item__name,
.action-item__label {
  font-size: 0.88rem;
  color: var(--text-primary);
}

.queue-item__tag,
.action-item__tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(58,95,75,0.08);
  color: var(--accent-secondary);
  font-size: 0.7rem;
}

.queue-item__tag--accent {
  background: rgba(196,30,58,0.08);
  color: var(--ink-vermillion);
}

.queue-item__desc,
.user-item__desc,
.action-item__desc {
  margin-top: 8px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.queue-item__meta,
.user-item__meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.user-item__score {
  font-size: 1.2rem;
}

.action-item--risk {
  border-color: rgba(196,30,58,0.14);
  background: rgba(196,30,58,0.05);
}

.route-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.route-entry {
  width: 100%;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border: 1px solid rgba(58,95,75,0.08);
  border-radius: 16px;
  background: rgba(255,255,255,0.5);
  cursor: pointer;
  transition: transform 0.24s ease, border-color 0.24s ease;
}

.route-entry:hover {
  transform: translateY(-1px);
  border-color: rgba(58,95,75,0.16);
}

.route-entry--locked {
  cursor: default;
  opacity: 0.88;
}

.route-entry--locked:hover {
  transform: none;
  border-color: rgba(58,95,75,0.08);
}

.route-entry__stamp {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(196,30,58,0.18);
  color: var(--ink-vermillion);
  font-family: var(--font-seal);
  background: rgba(255,255,255,0.82);
  flex-shrink: 0;
}

.route-entry__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.route-entry__body strong {
  font-size: 0.84rem;
  color: var(--text-primary);
}

.route-entry__body small {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--gradient-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  transition: all 0.25s;
}

.stat-card:hover {
  border-color: var(--border-glow);
  box-shadow: var(--shadow-glow-blue);
}

.stat-card__icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
  color: #fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.stat-card__label {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-card__unit,
.stat-card__sub {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.governance-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}

.governance-panel {
  padding: 18px;
}

.governance-panel__value {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 12px 0 8px;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.governance-panel__value .stat-value {
  font-size: 2rem;
  color: var(--text-primary);
}

.governance-panel__bar {
  height: 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.05);
  overflow: hidden;
  margin-bottom: 10px;
}

.governance-panel__bar-fill {
  height: 100%;
  border-radius: inherit;
}

.governance-panel__hint,
.governance-panel__desc {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.governance-panel__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.governance-chip {
  font-size: 0.6875rem;
  color: var(--accent-primary);
  background: rgba(58,95,75,0.08);
  padding: 4px 8px;
  border-radius: 999px;
}

.gpu-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  position: relative;
}

.gpu-grid__source-badge {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.6);
  border: 1px solid rgba(0,0,0,0.04);
  width: fit-content;
  font-size: 0.75rem;
}

.source-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.source-text {
  font-weight: 600;
  letter-spacing: 0.05em;
}

.source-count {
  color: var(--text-muted);
  font-size: 0.6875rem;
}

.gpu-grid__empty {
  grid-column: 1 / -1;
}

.gpu-card {
  padding: 18px;
  cursor: pointer;
}

.gpu-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.gpu-card__id {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gpu-card__badge {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--accent-primary);
  background: rgba(58, 95, 75, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
}

.gpu-card__name {
  font-size: 0.75rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
}

.gpu-card__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.metric-item__label {
  font-size: 0.6875rem;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.metric-item__value {
  font-size: 1.25rem;
  margin-bottom: 6px;
}

.metric-item__unit {
  font-size: 0.6875rem;
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 2px;
}

.metric-bar {
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.metric-bar__fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.gpu-card__footer {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 0.6875rem;
  color: var(--text-muted);
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 16px;
}

.chart-panel {
  padding: 18px;
}

.chart-panel__header {
  margin-bottom: 12px;
}

.chart-panel__body {
  height: 240px;
}

.alerts-strip {
  margin-top: 16px;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 0.8125rem;
}

.alert-item--warning {
  background: rgba(184, 134, 11, 0.06);
  border: 1px solid rgba(184, 134, 11, 0.15);
  color: #B8860B;
}

.alert-item--critical {
  background: rgba(196, 30, 58, 0.06);
  border: 1px solid rgba(196, 30, 58, 0.15);
  color: #C41E3A;
}

.alert-item__icon {
  font-size: 1rem;
}

.alert-item__text {
  flex: 1;
}

.alert-item__time {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: monospace;
}

@media (max-width: 1400px) {
  .connection-layout,
  .self-check-layout { grid-template-columns: 1fr; }
  .desktop-ops-layout { grid-template-columns: 1fr; }
  .workbench-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(3, 1fr); }
  .journey-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .signal-grid,
  .governance-grid { grid-template-columns: repeat(2, 1fr); }
  .gpu-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 980px) {
  .governance-hero {
    flex-direction: column;
  }

  .governance-hero__side {
    align-items: flex-start;
    min-width: 0;
  }

  .connection-panel__head {
    flex-direction: column;
  }

  .connection-panel__badges {
    justify-content: flex-start;
  }

  .self-check-panel__head {
    flex-direction: column;
  }

  .self-check-facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .desktop-ops-panel__head,
  .journey-panel__head {
    flex-direction: column;
  }

  .signal-grid,
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .governance-grid { grid-template-columns: 1fr; }
  .charts-row { grid-template-columns: 1fr; }
}

@media (max-width: 720px) {
  .action-grid,
  .connection-toggle,
  .connection-facts,
  .self-check-facts,
  .journey-steps,
  .signal-grid,
  .stats-row,
  .route-grid,
  .gpu-grid,
  .gpu-card__metrics {
    grid-template-columns: 1fr;
  }

  .workbench-card,
  .signal-card {
    padding: 18px;
  }
}
</style>
