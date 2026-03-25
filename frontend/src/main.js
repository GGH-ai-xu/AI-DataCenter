import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('./views/Dashboard.vue') },
  { path: '/gpu/:index', name: 'GpuDetail', component: () => import('./views/GpuDetail.vue') },
  { path: '/tasks', name: 'TaskManager', component: () => import('./views/TaskManager.vue') },
  { path: '/scheduler', name: 'Scheduler', component: () => import('./views/Scheduler.vue') },
  { path: '/ai', name: 'AIAssistant', component: () => import('./views/AIAssistant.vue') },
  { path: '/alerts', name: 'AlertCenter', component: () => import('./views/AlertCenter.vue') },
  { path: '/monitor', name: 'MonitorCenter', component: () => import('./views/MonitorCenter.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
