import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

const ROUTE_WARMUP_TIMEOUT_MS = 1500

const loadDashboardView = () => import('./views/Dashboard.vue')
const loadGpuDetailView = () => import('./views/GpuDetail.vue')
const loadTaskManagerView = () => import('./views/TaskManager.vue')
const loadSchedulerView = () => import('./views/Scheduler.vue')
const loadEnergyOptimizationView = () => import('./views/EnergyOptimization.vue')
const loadAIAssistantView = () => import('./views/AIAssistant.vue')
const loadAlertCenterView = () => import('./views/AlertCenter.vue')
const loadMonitorCenterView = () => import('./views/MonitorCenter.vue')

const heavyViewLoaders = [
  loadGpuDetailView,
  loadEnergyOptimizationView,
  loadMonitorCenterView,
]

const routes = [
  { path: '/', name: 'Dashboard', component: loadDashboardView },
  { path: '/gpu/:index', name: 'GpuDetail', component: loadGpuDetailView },
  { path: '/tasks', name: 'TaskManager', component: loadTaskManagerView },
  { path: '/scheduler', name: 'Scheduler', component: loadSchedulerView },
  { path: '/energy', name: 'EnergyOptimization', component: loadEnergyOptimizationView },
  { path: '/ai', name: 'AIAssistant', component: loadAIAssistantView },
  { path: '/alerts', name: 'AlertCenter', component: loadAlertCenterView },
  { path: '/monitor', name: 'MonitorCenter', component: loadMonitorCenterView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

async function warmRouteModules() {
  await Promise.all(heavyViewLoaders.map((loader) => loader()))
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

void router.isReady().then(() => {
  window.requestIdleCallback(() => {
    warmRouteModules().catch((error) => {
      console.error('Route preload failed', error)
    })
  }, { timeout: ROUTE_WARMUP_TIMEOUT_MS })
})
