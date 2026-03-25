<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from './stores/app'
import { generateMockGpus, generateMockSystem, generateMockProcesses, generateMockAlerts } from './services/mock'

const router = useRouter()
const route = useRoute()
const store = useAppStore()
const wsConnected = ref(false)
const mockMode = ref(false)
const currentTime = ref('')
let ws = null
let reconnectTimer = null
let clockTimer = null
let mockTimer = null

const navItems = [
  { path: '/', label: '监控大屏', icon: '◉' },
  { path: '/tasks', label: '任务管理', icon: '⚙' },
  { path: '/scheduler', label: '智能调度', icon: '⚡' },
  { path: '/monitor', label: '观察中心', icon: '◎' },
  { path: '/ai', label: 'AI助手', icon: '✦' },
  { path: '/alerts', label: '告警中心', icon: '△' },
]

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  })
}

function connectWs() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws`
  ws = new WebSocket(url)

  ws.onopen = () => {
    wsConnected.value = true
    store.wsConnected = true
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'realtime') {
        store.updateFromWs(data)
      }
    } catch (e) { /* pong */ }
  }

  ws.onclose = () => {
    wsConnected.value = false
    store.wsConnected = false
    // WebSocket连不上时自动切换到Mock模式
    if (!mockMode.value) {
      startMock()
    }
    reconnectTimer = setTimeout(connectWs, 10000)
  }

  ws.onerror = () => ws?.close()
}

function startMock() {
  mockMode.value = true
  wsConnected.value = true
  store.wsConnected = true
  mockTimer = setInterval(() => {
    store.updateFromWs({
      gpus: generateMockGpus(),
      system: generateMockSystem(),
      processes: generateMockProcesses(),
      alerts: generateMockAlerts(),
    })
  }, 1500)
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  connectWs()
  // 3秒后如果WebSocket没连上，启动Mock
  setTimeout(() => {
    if (!wsConnected.value) startMock()
  }, 3000)
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(mockTimer)
  clearTimeout(reconnectTimer)
  ws?.close()
})
</script>

<template>
  <div class="app-layout bg-grid">
    <!-- 顶部标题栏 -->
    <header class="app-header">
      <div class="header-left">
        <div class="logo-mark"></div>
        <h1 class="header-title">AI 数据中心能耗智能优化管理系统</h1>
      </div>
      <nav class="header-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ 'nav-item--active': route.path === item.path || (item.path !== '/' && route.path.startsWith(item.path)) }"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="header-right">
        <div class="ws-status" :class="wsConnected ? 'ws-status--on' : 'ws-status--off'">
          <span class="ws-dot"></span>
          {{ mockMode ? '演示模式' : wsConnected ? '实时连接' : '断开连接' }}
        </div>
        <div class="header-clock stat-value">{{ currentTime }}</div>
      </div>
    </header>

    <!-- 内容区 -->
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.98), rgba(10, 14, 26, 0.95));
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  position: relative;
  z-index: 100;
}

.app-header::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent-primary), var(--accent-secondary), transparent);
  opacity: 0.4;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--gradient-blue);
  position: relative;
  box-shadow: 0 0 16px rgba(56, 189, 248, 0.3);
}

.logo-mark::after {
  content: 'AI';
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 800;
  color: white;
  letter-spacing: -0.5px;
}

.header-title {
  font-size: 1rem;
  font-weight: 600;
  background: linear-gradient(135deg, #f1f5f9, #38bdf8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 0.02em;
}

.header-nav {
  display: flex;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.2s;
}

.nav-item:hover {
  color: var(--text-primary);
  background: rgba(56, 189, 248, 0.06);
}

.nav-item--active {
  color: var(--accent-primary);
  background: rgba(56, 189, 248, 0.1);
}

.nav-icon {
  font-size: 0.875rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ws-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  padding: 4px 10px;
  border-radius: 9999px;
}

.ws-status--on {
  color: #34d399;
  background: rgba(52, 211, 153, 0.1);
}

.ws-status--off {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
}

.ws-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.ws-status--on .ws-dot {
  background: #34d399;
  box-shadow: 0 0 6px #34d399;
  animation: pulse-glow 2s ease-in-out infinite;
}

.ws-status--off .ws-dot {
  background: #f87171;
}

.header-clock {
  font-size: 0.875rem;
  color: var(--accent-primary);
}

.app-main {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease;
}

.page-enter-from,
.page-leave-to {
  opacity: 0;
}
</style>
