/**
 * API服务封装 - Axios实例与接口方法
 */
import axios from 'axios'

import {
  clearSessionToken,
  readSessionToken,
  writeSessionToken,
} from '../lib/authSession.js'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = readSessionToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let interceptorInstalled = false
const interceptorHooks = {
  onPasswordChangeRequired: null,
  onUnauthorized: null,
  showToast: null,
}

/**
 * 注册全局错误拦截器（由 App.vue 在 onMounted 中调用）
 */
export function setupInterceptor(options = {}) {
  interceptorHooks.showToast = options.showToast || interceptorHooks.showToast
  interceptorHooks.onUnauthorized = options.onUnauthorized || interceptorHooks.onUnauthorized
  interceptorHooks.onPasswordChangeRequired = options.onPasswordChangeRequired || interceptorHooks.onPasswordChangeRequired
  if (interceptorInstalled) return

  interceptorInstalled = true
  api.interceptors.response.use(
    (res) => res,
    async (err) => {
      const status = err.response?.status
      const detail = err.response?.data?.detail
      const code = err.response?.data?.code
      const url = String(err.config?.url || '')
      const showToast = interceptorHooks.showToast

      if (status === 401) {
        if (!url.endsWith('/auth/login')) {
          await interceptorHooks.onUnauthorized?.(err)
        }
        showToast?.(detail || '请先登录平台', 'error')
      } else if (status === 403 && code === 'PASSWORD_CHANGE_REQUIRED') {
        await interceptorHooks.onPasswordChangeRequired?.(err)
        showToast?.(detail || '首次登录后必须先修改密码', 'warning')
      } else if (status === 403) {
        showToast?.(detail || '权限不足，需要管理员权限', 'warning')
      } else if (status >= 500) {
        showToast?.(`服务器错误 (${status})`, 'error')
      } else if (!err.response && err.message) {
        showToast?.('网络连接异常，请检查后端服务', 'error')
      }
      return Promise.reject(err)
    },
  )
}

/** 设置认证令牌 */
export function setAuthToken(token) {
  if (token) {
    writeSessionToken(token)
  } else {
    clearSessionToken()
  }
}

export const login = (payload) => api.post('/auth/login', payload)
export const getCurrentUser = () => api.get('/auth/me')
export const logout = () => api.post('/auth/logout')
export const changePassword = (payload) => api.post('/auth/change-password', payload)
export const getUsers = () => api.get('/admin/users')
export const createUser = (payload) => api.post('/admin/users', payload)
export const resetUserPassword = (userId, payload) => api.post(`/admin/users/${userId}/reset-password`, payload)
export const getSavedHosts = (scope = 'mine') => api.get('/hosts', { params: { scope } })
export const deleteSavedHost = (hostId) => api.delete(`/hosts/${hostId}`)

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
export const getImportContext = () => api.get('/system/import-context')
export const scanImportContext = (payload) => api.post('/system/import-context/scan', payload)
export const commitImportContext = (payload) => api.post('/system/import-context', payload)
export const resetImportContext = () => api.delete('/system/import-context')
export const getLlmConfig = () => api.get('/system/llm')
export const testLlmConfig = (payload) => api.post('/system/llm/test', payload)
export const updateLlmConfig = (payload) => api.post('/system/llm', payload)
export const getSystemSelfCheck = () => api.get('/system/self-check')

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
