/**
 * API服务封装 - Axios实例与接口方法
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// Token 认证：自动附加 Authorization 头
const AUTH_TOKEN_KEY = 'gpu_gov_token'
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * 注册全局错误拦截器（由 App.vue 在 onMounted 中调用）
 * @param {(msg: string, type: string) => void} showToast
 */
export function setupInterceptor(showToast) {
  api.interceptors.response.use(
    (res) => res,
    (err) => {
      const status = err.response?.status
      const detail = err.response?.data?.detail
      if (status === 401) {
        showToast(detail || '认证失败，请检查 Token', 'error')
      } else if (status === 403) {
        showToast(detail || '权限不足，需要管理员令牌', 'warning')
      } else if (status >= 500) {
        showToast(`服务器错误 (${status})`, 'error')
      } else if (!err.response && err.message) {
        // 网络错误 / 超时
        showToast('网络连接异常，请检查后端服务', 'error')
      }
      return Promise.reject(err)
    },
  )
}

/** 设置认证令牌 */
export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token)
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY)
  }
}

// GPU相关
export const getRealtimeData = () => api.get('/gpu/realtime')
export const getGpuHistory = (index, hours = 1) => api.get(`/gpu/history/${index}`, { params: { hours } })
export const getPowerSummary = (hours = 24) => api.get('/gpu/summary', { params: { hours } })

// 任务相关
export const getTasks = () => api.get('/tasks/')
export const pauseTask = (pid, options = {}) => api.post('/tasks/pause', { pid, ...options })
export const resumeTask = (pid, options = {}) => api.post('/tasks/resume', { pid, ...options })
export const terminateTask = (pid, options = {}) => api.post('/tasks/terminate', { pid, ...options })
export const setTaskPriority = (pid, priority) => api.post('/tasks/priority', { pid, priority })

// 调度相关
export const getSchedulerStatus = () => api.get('/scheduler/status')
export const toggleAutoSchedule = (enabled) => api.post('/scheduler/auto', null, { params: { enabled } })
export const setPowerBudget = (enabled, total_power_budget) => api.post('/scheduler/budget', { enabled, total_power_budget })
export const getCarbonBudget = () => api.get('/scheduler/carbon-budget')
export const setCarbonBudget = (enabled, daily_budget_kg) => api.post('/scheduler/carbon-budget', { enabled, daily_budget_kg })
export const setManualPowerLimit = (gpu_index, power_limit, options = {}) => api.post('/scheduler/power-limit', { gpu_index, power_limit, ...options })
export const runScheduleOnce = (payload = {}) => api.post('/scheduler/run-once', payload)
export const getScheduleReport = () => api.get('/scheduler/report')
export const getScheduleEvaluation = () => api.get('/scheduler/evaluation')

// AI对话
export const aiChat = (message) => api.post('/ai/chat', { message })
export const aiControlPlan = (message) => api.post('/ai/control/plan', { message })
export const aiControlExecute = (payload) => api.post('/ai/control/execute', payload)

// 告警
export const getAlerts = (limit = 50, unack_only = false) => api.get('/alerts/', { params: { limit, unack_only } })
export const acknowledgeAlert = (id) => api.post(`/alerts/acknowledge/${id}`)

// 健康检查
export const healthCheck = () => api.get('/health')

// 系统接入与自检
export const getConnectionConfig = () => api.get('/system/connection')
export const testConnectionConfig = (payload) => api.post('/system/connection/test', payload)
export const updateConnectionConfig = (payload) => api.post('/system/connection', payload)
export const getLlmConfig = () => api.get('/system/llm')
export const testLlmConfig = (payload) => api.post('/system/llm/test', payload)
export const updateLlmConfig = (payload) => api.post('/system/llm', payload)
export const getSystemSelfCheck = () => api.get('/system/self-check')
export const createDemoAlert = () => api.post('/system/demo-alert')

// 监控观察
export const getSystemDetail = () => api.get('/monitor/system-detail')
export const getTrainingProgress = () => api.get('/monitor/training')
export const getUserStats = () => api.get('/monitor/users')
export const getTaskHistory = (hours = 24) => api.get('/monitor/task-history', { params: { hours } })
export const getMonitorReplay = (hours = 24, bucket_minutes = 10) => api.get('/monitor/replay', { params: { hours, bucket_minutes } })
export const getFairnessGovernance = () => api.get('/governance/fairness')
export const getGovernanceRules = () => api.get('/governance/rules')
export const saveGovernanceRule = (payload) => api.post('/governance/rules', payload)
export const deleteGovernanceRule = (username) => api.delete(`/governance/rules/${encodeURIComponent(username)}`)
export const exportGovernanceReport = (format = 'markdown') => api.get('/governance/export-report', { params: { format }, responseType: 'blob' })

// 能耗优化分析
export const getEnergyMetrics = (hours = 24) => api.get('/energy/metrics', { params: { hours } })
export const getAiInsight = () => api.get('/energy/ai-insight')
export const getAiAnomalies = () => api.get('/energy/ai-anomalies')
export const getTimeBreakdown = (hours = 24) => api.get('/energy/time-breakdown', { params: { hours } })
export const getGpuEfficiency = () => api.get('/energy/efficiency')
export const getPowerPrediction = (hours = 24) => api.get('/energy/prediction', { params: { hours } })
export const getCarbonData = (hours = 24) => api.get('/energy/carbon', { params: { hours } })
export const runOptimize = () => api.post('/energy/optimize')
export const getEnergyReport = (hours = 24) => api.get('/energy/report', { params: { hours } })
export const getOptimizationHistory = (hours = 72) => api.get('/energy/optimization-history', { params: { hours } })
export const getScheduleHistory = (hours = 72) => api.get('/energy/schedule-history', { params: { hours } })
export const getHistoryComparison = (hours = 72) => api.get('/energy/history-comparison', { params: { hours } })
export const exportEnergyReport = (hours = 24, format = 'markdown') => api.get('/energy/export-report', { params: { hours, format }, responseType: 'blob' })

// 审计日志
export const getAuditLogs = (limit = 100, hours = 72) => api.get('/audit/logs', { params: { limit, hours } })

// 综合治理报告
export const exportFullGovernanceReport = (hours = 24) => api.get('/governance/full-report', { params: { hours }, responseType: 'blob' })

export default api
