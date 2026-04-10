import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

import App from './App.vue'
import './style.css'
import { resolveRouteAccess } from './lib/routeAccess.js'
import { healthCheck } from './services/api.js'
import { useAppStore } from './stores/app.js'
import { useAuthStore } from './stores/auth.js'


const ROUTE_WARMUP_TIMEOUT_MS = 1500

const pinia = createPinia()
const loadLoginView = () => import('./views/LoginView.vue')
const loadChangePasswordView = () => import('./views/ChangePasswordView.vue')
const loadImportWorkspaceView = () => import('./views/ImportWorkspace.vue')
const loadConsoleShellView = () => import('./views/ConsoleShell.vue')
const loadDashboardView = () => import('./views/Dashboard.vue')
const loadGpuDetailView = () => import('./views/GpuDetail.vue')
const loadGovernanceLayoutView = () => import('./views/GovernanceLayout.vue')
const loadGovernanceActionsView = () => import('./views/GovernanceActionsView.vue')
const loadGovernancePoliciesView = () => import('./views/GovernancePoliciesView.vue')
const loadClusterJobsView = () => import('./views/ClusterJobs.vue')
const loadGovernanceReviewView = () => import('./views/GovernanceReviewView.vue')
const loadEnergyOptimizationView = () => import('./views/EnergyOptimization.vue')
const loadAIWorkspaceLayoutView = () => import('./views/AIWorkspaceLayout.vue')
const loadAIAssistantView = () => import('./views/AIAssistant.vue')
const loadAIGraphWorkspaceView = () => import('./views/AIGraphWorkspace.vue')
const loadAlertCenterView = () => import('./views/AlertCenter.vue')
const loadMonitorCenterView = () => import('./views/MonitorCenter.vue')

const heavyViewLoaders = [
  loadConsoleShellView,
  loadImportWorkspaceView,
  loadGpuDetailView,
  loadEnergyOptimizationView,
  loadMonitorCenterView,
  loadClusterJobsView,
  loadAIWorkspaceLayoutView,
  loadAIAssistantView,
  loadAIGraphWorkspaceView,
]

const routes = [
  { path: '/login', name: 'Login', component: loadLoginView },
  { path: '/change-password', name: 'ChangePassword', component: loadChangePasswordView },
  { path: '/import', name: 'ImportWorkspace', component: loadImportWorkspaceView },
  {
    path: '/',
    component: loadConsoleShellView,
    children: [
      { path: '', name: 'Dashboard', component: loadDashboardView, meta: { hideShellHeader: true } },
      { path: 'gpu/:index', name: 'GpuDetail', component: loadGpuDetailView },
      {
        path: 'governance',
        component: loadGovernanceLayoutView,
        meta: { hideShellHeader: true },
        children: [
          { path: '', redirect: '/governance/actions' },
          { path: 'actions', name: 'GovernanceActions', component: loadGovernanceActionsView },
          { path: 'policies', name: 'GovernancePolicies', component: loadGovernancePoliciesView },
          { path: 'cluster', name: 'ClusterJobs', component: loadClusterJobsView },
          { path: 'review', name: 'GovernanceReview', component: loadGovernanceReviewView },
        ],
      },
      { path: '/cluster/jobs', redirect: '/governance/cluster' },
      { path: 'tasks', redirect: '/governance/actions' },
      { path: 'scheduler', redirect: '/governance/policies' },
      { path: 'energy', name: 'EnergyOptimization', component: loadEnergyOptimizationView, meta: { hideShellHeader: true } },
      {
        path: 'ai',
        component: loadAIWorkspaceLayoutView,
        meta: { hideShellHeader: true },
        children: [
          { path: '', redirect: '/ai/workbench' },
          { path: 'workbench', name: 'AIAssistant', component: loadAIAssistantView },
          { path: 'graph', name: 'AIGraphWorkspace', component: loadAIGraphWorkspaceView },
        ],
      },
      { path: 'alerts', name: 'AlertCenter', component: loadAlertCenterView, meta: { hideShellHeader: true } },
      { path: 'monitor', name: 'MonitorCenter', component: loadMonitorCenterView, meta: { hideShellHeader: true } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const auth = useAuthStore(pinia)
const appStore = useAppStore(pinia)
let authHydrationPromise = null
let workspaceBootstrapPromise = null

async function ensureAuthHydrated() {
  if (auth.ready) return
  if (!authHydrationPromise) {
    authHydrationPromise = auth.hydrate().finally(() => {
      authHydrationPromise = null
    })
  }
  await authHydrationPromise
}

async function bootstrapWorkspaceState() {
  if (!auth.isAuthenticated || auth.mustChangePassword || appStore.workspaceStatusChecked) {
    return
  }
  if (!workspaceBootstrapPromise) {
    workspaceBootstrapPromise = (async () => {
      try {
        const { data } = await healthCheck()
        appStore.applyRealtimePayload(data || {})
        appStore.setWorkspaceReady(Boolean(data?.workspace_ready))
      } finally {
        appStore.markWorkspaceStatusChecked(true)
      }
    })().finally(() => {
      workspaceBootstrapPromise = null
    })
  }
  await workspaceBootstrapPromise
}

router.beforeEach(async (to) => {
  await ensureAuthHydrated()
  await bootstrapWorkspaceState()
  const access = resolveRouteAccess({
    path: to.path,
    user: auth.currentUser,
    workspaceReady: appStore.workspaceReady,
  })
  if (!access.allow && access.redirectTo !== to.path) {
    return access.redirectTo
  }
  return true
})

async function warmRouteModules() {
  await Promise.all(heavyViewLoaders.map((loader) => loader()))
}

const app = createApp(App)
app.use(pinia)
app.use(router)
app.mount('#app')

void router.isReady().then(() => {
  window.requestIdleCallback(() => {
    warmRouteModules().catch((error) => {
      console.error('Route preload failed', error)
    })
  }, { timeout: ROUTE_WARMUP_TIMEOUT_MS })
})
