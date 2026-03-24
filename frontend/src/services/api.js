/**
 * API服务封装 - Axios实例与接口方法
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// GPU相关
export const getRealtimeData = () => api.get('/gpu/realtime')
export const getGpuHistory = (index, hours = 1) => api.get(`/gpu/history/${index}`, { params: { hours } })
export const getPowerSummary = (hours = 24) => api.get('/gpu/summary', { params: { hours } })

// 任务相关
export const getTasks = () => api.get('/tasks/')
export const pauseTask = (pid) => api.post('/tasks/pause', { pid })
export const resumeTask = (pid) => api.post('/tasks/resume', { pid })
export const terminateTask = (pid) => api.post('/tasks/terminate', { pid })
export const setTaskPriority = (pid, priority) => api.post('/tasks/priority', { pid, priority })

// 调度相关
export const getSchedulerStatus = () => api.get('/scheduler/status')
export const toggleAutoSchedule = (enabled) => api.post('/scheduler/auto', null, { params: { enabled } })
export const setManualPowerLimit = (gpu_index, power_limit) => api.post('/scheduler/power-limit', { gpu_index, power_limit })
export const runScheduleOnce = () => api.post('/scheduler/run-once')
export const getScheduleReport = () => api.get('/scheduler/report')

// AI对话
export const aiChat = (message) => api.post('/ai/chat', { message })

// 告警
export const getAlerts = (limit = 50, unack_only = false) => api.get('/alerts/', { params: { limit, unack_only } })
export const acknowledgeAlert = (id) => api.post(`/alerts/acknowledge/${id}`)

// 健康检查
export const healthCheck = () => api.get('/health')

export default api
