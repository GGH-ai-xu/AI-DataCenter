<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { healthCheck } from './services/api'
import { useAppStore } from './stores/app'
import GlobalToast from './components/GlobalToast.vue'
import { setupInterceptor } from './services/api'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const wsConnected = ref(false)
const currentTime = ref('')
const workspaceStatusChecked = ref(false)
const lockHint = ref('')
const appInfo = ref({
  name: 'GPU 共享治理平台',
  version: '',
  updateSupported: false,
  releasesUrl: '',
})
const updateState = ref(null)
const updateBusy = ref(false)
const closeDialog = ref(null)
const closeBusy = ref(false)
const toastRef = ref(null)
let ws = null
let reconnectTimer = null
let wsRetryDelay = 1000  // WebSocket 指数退避初始延迟
let clockTimer = null
let workspaceTimer = null
let lockHintTimer = null
let updateStateTimer = null
let removeCloseListener = null

const navItems = [
  { path: '/', label: '总览', icon: '览', desc: '接入中心与自检' },
  { path: '/tasks', label: '任务', icon: '务', desc: '处置真实任务' },
  { path: '/scheduler', label: '调度', icon: '策', desc: '预算与治理动作' },
  { path: '/energy', label: '能耗', icon: '能', desc: '节能复盘与测算' },
  { path: '/monitor', label: '观察', icon: '观', desc: '画像与过程观察' },
  { path: '/ai', label: '智能', icon: '智', desc: 'AI 解释与问答' },
  { path: '/alerts', label: '告警', icon: '警', desc: '风险台与异常确认' },
]

const isDesktop = computed(() => typeof window !== 'undefined' && Boolean(window.desktopShell))
const workspaceLocked = computed(() => workspaceStatusChecked.value && !store.workspaceReady)

function getDesktopShellBridge() {
  if (typeof window === 'undefined') return null
  return window.desktopShell || null
}

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function setLockHint(message) {
  lockHint.value = message
  clearTimeout(lockHintTimer)
  lockHintTimer = setTimeout(() => {
    lockHint.value = ''
  }, 3200)
}

function clearUpdateNotice() {
  clearTimeout(updateStateTimer)
  updateStateTimer = null
  updateState.value = null
}

function applyUpdateNotice(nextState) {
  clearTimeout(updateStateTimer)
  updateStateTimer = null
  updateState.value = nextState

  if (!nextState) {
    return
  }

  if (nextState.ok && nextState.available) {
    return
  }

  updateStateTimer = setTimeout(() => {
    updateState.value = null
    updateStateTimer = null
  }, nextState.ok ? 4200 : 6500)
}

function enforceRouteAccess(path = route.path) {
  if (!workspaceLocked.value || path === '/') {
    return
  }

  if (route.path !== '/') {
    router.replace('/')
  }
  setLockHint('当前还未接入 Agent，已返回首页接入中心。')
}

async function refreshWorkspaceStatus() {
  try {
    const { data } = await healthCheck()
    store.setWorkspaceReady(Boolean(data?.agent_connected))
  } catch {
    store.setWorkspaceReady(false)
  } finally {
    workspaceStatusChecked.value = true
    enforceRouteAccess(route.path)
  }
}

function connectWs() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws`
  ws = new WebSocket(url)
  ws.onopen = () => {
    wsConnected.value = true
    store.wsConnected = true
    wsRetryDelay = 1000  // 连接成功后重置退避
  }
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'realtime') {
        store.updateFromWs(data)
      }
    } catch {}
  }
  ws.onclose = () => {
    wsConnected.value = false
    store.wsConnected = false
    // 指数退避重连：1s → 2s → 4s → 8s → ... → 30s max
    reconnectTimer = setTimeout(connectWs, wsRetryDelay)
    wsRetryDelay = Math.min(wsRetryDelay * 2, 30000)
  }
  ws.onerror = () => ws?.close()
}

function navigateTo(item) {
  if (workspaceLocked.value && item.path !== '/') {
    setLockHint(`请先在首页完成 Agent 接入，再进入“${item.label}”页面。`)
    if (route.path !== '/') {
      router.replace('/')
    }
    return
  }
  if (route.path !== item.path) {
    router.push(item.path)
  }
}

async function loadDesktopInfo() {
  const shellBridge = getDesktopShellBridge()
  if (!shellBridge) {
    return
  }

  if (shellBridge.getAppInfo) {
    try {
      appInfo.value = {
        ...appInfo.value,
        ...await shellBridge.getAppInfo(),
      }
    } catch {}
  }

  if (shellBridge.onCloseRequest) {
    removeCloseListener?.()
    removeCloseListener = shellBridge.onCloseRequest((payload) => {
      closeBusy.value = false
      closeDialog.value = payload || {
        title: '关闭桌面平台',
        message: '你可以选择退出并关闭服务，或者最小化到后台继续运行。',
        detail: '最小化到后台会保留桌面程序和本机托管服务。',
      }
    })
  }
}

async function checkForUpdates() {
  const shellBridge = getDesktopShellBridge()
  if (!shellBridge?.checkForUpdates) {
    return
  }

  clearTimeout(updateStateTimer)
  updateStateTimer = null
  updateBusy.value = true
  try {
    const result = await shellBridge.checkForUpdates()
    if (!result?.ok) {
      const errorText = String(result?.error || '')
      if (
        errorText.includes('还没有发布正式版本')
        || errorText.includes('未配置 GitHub Releases 发布源')
      ) {
        applyUpdateNotice({
          ok: true,
          available: false,
          noReleaseYet: true,
          currentVersion: appInfo.value.version || '1.1.0',
          releasesUrl: appInfo.value.releasesUrl || result?.releasesUrl || '',
        })
      } else {
        applyUpdateNotice(result)
      }
      return
    }
    applyUpdateNotice(result)
  } catch (error) {
    applyUpdateNotice({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    })
  } finally {
    updateBusy.value = false
  }
}

async function openUpdateTarget(url) {
  const target = String(url || '').trim()
  if (!target) return

  const shellBridge = getDesktopShellBridge()
  if (shellBridge?.openExternal) {
    await shellBridge.openExternal(target)
    return
  }

  window.open(target, '_blank', 'noopener,noreferrer')
}

async function resolveCloseAction(action) {
  const shellBridge = getDesktopShellBridge()
  closeBusy.value = true

  try {
    if (shellBridge?.resolveCloseRequest) {
      await shellBridge.resolveCloseRequest(action)
    }
    closeDialog.value = null
  } finally {
    closeBusy.value = false
  }
}

watch(
  () => route.path,
  (path) => {
    enforceRouteAccess(path)
  },
)

watch(
  () => store.workspaceReady,
  () => {
    enforceRouteAccess(route.path)
  },
)

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  connectWs()
  // 注册 axios 全局错误拦截器
  setupInterceptor((msg, type) => {
    toastRef.value?.show(msg, type)
  })
  void refreshWorkspaceStatus()
  workspaceTimer = setInterval(() => {
    void refreshWorkspaceStatus()
  }, 15000)
  void loadDesktopInfo()
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(workspaceTimer)
  clearTimeout(reconnectTimer)
  clearTimeout(lockHintTimer)
  clearTimeout(updateStateTimer)
  removeCloseListener?.()
  ws?.close()
})
</script>

<template>
  <div class="app-layout">
    <header class="ink-header">
      <div class="ink-header__left">
        <img class="logo-mark" src="/logo.svg" alt="AI-DataCenter logo" />
        <div class="logo-text">
          <h1 class="logo-title">{{ appInfo.name || 'GPU 共享治理平台' }}</h1>
          <p class="logo-sub">
            {{ workspaceLocked ? 'CONNECT FIRST · UNLOCK LATER' : 'LAB · OPS · POWER BUDGET' }}
          </p>
        </div>
      </div>

      <nav class="ink-nav">
        <button
          v-for="item in navItems"
          :key="item.path"
          type="button"
          class="ink-nav__item"
          :class="{
            'ink-nav__item--active': route.path === item.path || (item.path !== '/' && route.path.startsWith(item.path)),
            'ink-nav__item--locked': workspaceLocked && item.path !== '/',
          }"
          :title="workspaceLocked && item.path !== '/' ? `请先接入 Agent，再打开${item.label}` : item.desc"
          @click="navigateTo(item)"
        >
          <span class="ink-nav__seal">{{ item.icon }}</span>
          <span class="ink-nav__label">{{ item.label }}</span>
        </button>
      </nav>

      <div class="ink-header__right">
        <div v-if="isDesktop" class="desktop-meta">
          <span class="desktop-meta__version">v{{ appInfo.version || '1.1.0' }}</span>
          <button
            type="button"
            class="desktop-meta__action"
            :disabled="updateBusy"
            @click="checkForUpdates"
          >
            {{ updateBusy ? '检查中...' : '检查更新' }}
          </button>
        </div>
        <div class="ink-status" :class="wsConnected ? 'ink-status--on' : 'ink-status--off'">
          <span class="ink-status__dot"></span>
          {{ wsConnected ? '在线' : '离线' }}
        </div>
        <div class="ink-clock">{{ currentTime }}</div>
      </div>

      <div class="ink-header__brush"></div>
    </header>

    <div v-if="workspaceLocked || lockHint || updateState" class="app-banner-stack">
      <div v-if="workspaceLocked" class="app-banner app-banner--warning">
        当前未接入 Agent，平台先只开放首页接入中心；任务、治理、观察、风险、AI 与复盘页面暂不开放。
      </div>
      <div v-if="lockHint" class="app-banner app-banner--soft">
        {{ lockHint }}
      </div>
      <div
        v-if="updateState"
        class="app-banner"
        :class="updateState.ok
          ? (updateState.available ? 'app-banner--ok' : 'app-banner--neutral')
          : 'app-banner--critical'"
      >
        <button type="button" class="app-banner__close" @click="clearUpdateNotice">
          关闭
        </button>
        <template v-if="updateState.ok && updateState.available">
          检测到新版本 `v{{ updateState.latestVersion }}`，当前版本 `v{{ updateState.currentVersion }}`。
          <button type="button" class="app-banner__link" @click="openUpdateTarget(updateState.downloadUrl || updateState.releaseUrl)">
            打开下载地址
          </button>
        </template>
        <template v-else-if="updateState.ok">
          {{ updateState.noReleaseYet ? '当前仓库还没有发布正式 Release，暂时无法在线更新。' : `当前已是最新版本 v${updateState.currentVersion}。` }}
          <button
            v-if="updateState.releasesUrl"
            type="button"
            class="app-banner__link"
            @click="openUpdateTarget(updateState.releasesUrl)"
          >
            打开 Releases
          </button>
        </template>
        <template v-else>
          更新检查失败：{{ updateState.error || '无法连接 GitHub Releases。' }}
          <button
            v-if="updateState.releasesUrl || appInfo.releasesUrl"
            type="button"
            class="app-banner__link"
            @click="openUpdateTarget(updateState.releasesUrl || appInfo.releasesUrl)"
          >
            手动打开 Releases
          </button>
        </template>
      </div>
    </div>

    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="ink-page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <div class="side-deco">
      <span class="side-deco__text">绿色计算</span>
    </div>

    <div v-if="closeDialog" class="shell-modal">
      <div class="shell-modal__mask" @click="resolveCloseAction('cancel')"></div>
      <div class="shell-modal__panel tech-card">
        <div class="shell-modal__eyebrow">桌面程序关闭选项</div>
        <h2 class="shell-modal__title">{{ closeDialog.title || '关闭桌面平台' }}</h2>
        <p class="shell-modal__message">{{ closeDialog.message }}</p>
        <p class="shell-modal__detail">{{ closeDialog.detail }}</p>
        <div class="shell-modal__actions">
          <button type="button" class="btn-tech" :disabled="closeBusy" @click="resolveCloseAction('cancel')">
            继续使用
          </button>
          <button type="button" class="btn-tech" :disabled="closeBusy" @click="resolveCloseAction('minimize')">
            最小化到后台
          </button>
          <button type="button" class="btn-tech btn-tech--primary" :disabled="closeBusy" @click="resolveCloseAction('quit')">
            退出并关闭服务
          </button>
        </div>
      </div>
    </div>
    <GlobalToast ref="toastRef" />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  position: relative;
}

/* ===== 水墨顶栏 ===== */
.ink-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 32px;
  background: rgba(248, 245, 240, 0.92);
  backdrop-filter: blur(16px);
  flex-shrink: 0;
  position: relative;
  z-index: 100;
}

/* 底部毛笔笔触线 */
.ink-header__brush {
  position: absolute;
  bottom: 0; left: 3%; right: 3%;
  height: 1px;
  /* 模拟毛笔不均匀笔触 */
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(0,0,0,0.03) 5%,
    rgba(0,0,0,0.08) 15%,
    rgba(0,0,0,0.12) 30%,
    rgba(0,0,0,0.1) 45%,
    rgba(0,0,0,0.06) 55%,
    rgba(0,0,0,0.1) 65%,
    rgba(0,0,0,0.08) 80%,
    rgba(0,0,0,0.04) 92%,
    transparent 100%
  );
}

.ink-header__left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo-mark {
  width: 40px;
  height: 40px;
  display: block;
  flex-shrink: 0;
  border-radius: 12px;
  filter: drop-shadow(0 8px 14px rgba(6, 91, 83, 0.12));
}

.logo-title {
  font-family: var(--font-xingshu);
  font-size: 1.2rem;
  font-weight: 400;
  color: #1a1a1a;
  letter-spacing: 0.18em;
  line-height: 1.2;
}

.logo-sub {
  font-family: var(--font-song);
  font-size: 0.5rem;
  color: #bbb;
  letter-spacing: 0.35em;
  font-weight: 300;
  margin-top: 1px;
}

/* ===== 水墨导航 ===== */
.ink-nav {
  display: flex;
  gap: 2px;
}

.ink-nav__item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 4px;
  border: none;
  background: transparent;
  text-decoration: none;
  transition: all 0.3s;
  position: relative;
  cursor: pointer;
}

.ink-nav__seal {
  font-family: var(--font-seal);
  font-size: 0.7rem;
  color: #bbb;
  width: 20px; height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid transparent;
  border-radius: 2px;
  transition: all 0.3s;
}

.ink-nav__label {
  font-family: var(--font-kaishu);
  font-size: 0.8125rem;
  color: #888;
  letter-spacing: 0.1em;
  transition: color 0.3s;
}

.ink-nav__item:hover .ink-nav__label {
  color: #333;
}

.ink-nav__item:hover .ink-nav__seal {
  color: #999;
  border-color: rgba(0,0,0,0.08);
}

/* 活跃项 */
.ink-nav__item--active .ink-nav__seal {
  color: var(--ink-vermillion);
  border-color: var(--ink-vermillion);
  opacity: 0.6;
}

.ink-nav__item--active .ink-nav__label {
  color: var(--text-primary);
  font-weight: 500;
}

/* 活跃项底部朱红墨点 */
.ink-nav__item--active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 4px;
  height: 4px;
  background: var(--ink-vermillion);
  border-radius: 50%;
  transform: translateX(-50%);
  opacity: 0.5;
}

.ink-nav__item--locked {
  opacity: 0.52;
}

.ink-nav__item--locked .ink-nav__seal,
.ink-nav__item--locked .ink-nav__label {
  color: #b6afa7;
}

/* ===== 右侧 ===== */
.ink-header__right {
  display: flex;
  align-items: center;
  gap: 18px;
}

.desktop-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.desktop-meta__version {
  font-family: var(--font-song);
  font-size: 0.75rem;
  color: #9c968f;
}

.desktop-meta__action {
  border: 1px solid rgba(46, 139, 87, 0.14);
  background: rgba(46, 139, 87, 0.07);
  color: #3A5F4B;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: all 0.2s ease;
}

.desktop-meta__action:hover:not(:disabled) {
  background: rgba(46, 139, 87, 0.12);
}

.desktop-meta__action:disabled {
  opacity: 0.6;
  cursor: wait;
}

.ink-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.6875rem;
  padding: 3px 10px;
  border-radius: 3px;
  font-family: var(--font-kaishu);
  letter-spacing: 0.1em;
}

.ink-status--on {
  color: #2E8B57;
  background: rgba(46, 139, 87, 0.05);
}

.ink-status--off {
  color: #C41E3A;
  background: rgba(196, 30, 58, 0.05);
}

.ink-status__dot {
  width: 4px; height: 4px;
  border-radius: 50%;
}

.ink-status--on .ink-status__dot {
  background: #2E8B57;
  box-shadow: 0 0 4px rgba(46,139,87,0.3);
  animation: pulse-glow 3s ease-in-out infinite;
}

.ink-status--off .ink-status__dot {
  background: #C41E3A;
}

.ink-clock {
  font-family: var(--font-song);
  font-size: 0.8125rem;
  color: #bbb;
  font-weight: 300;
  letter-spacing: 0.08em;
}

/* ===== 内容区 ===== */
.app-main {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 28px 32px;
  position: relative;
  z-index: 1;
}

.app-banner-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 32px 0;
}

.app-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  position: relative;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid rgba(26, 26, 26, 0.06);
  background: rgba(255, 255, 255, 0.52);
  box-shadow: 0 8px 18px rgba(79, 59, 22, 0.05);
  font-family: var(--font-kaishu);
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.app-banner--warning,
.app-banner--soft {
  border-color: rgba(212, 175, 55, 0.14);
  background: rgba(212, 175, 55, 0.08);
  color: #7B5D15;
}

.app-banner--ok {
  border-color: rgba(46, 139, 87, 0.16);
  background: rgba(46, 139, 87, 0.08);
  color: #2F6A46;
}

.app-banner--neutral {
  border-color: rgba(58, 95, 75, 0.12);
  background: rgba(58, 95, 75, 0.06);
  color: #3A5F4B;
}

.app-banner--critical {
  border-color: rgba(196, 30, 58, 0.16);
  background: rgba(196, 30, 58, 0.08);
  color: #9A1730;
}

.app-banner__link {
  border: none;
  background: transparent;
  color: inherit;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}

.app-banner__close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  cursor: pointer;
  opacity: 0.7;
}

.app-banner__close:hover {
  opacity: 1;
}

/* ===== 右侧竖排装饰 ===== */
.side-deco {
  position: fixed;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 50;
  pointer-events: none;
}

.side-deco__text {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-family: var(--font-xingcao);
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.04);
  letter-spacing: 0.6em;
}

/* ===== 页面切换 - 云雾出入 ===== */
.ink-page-enter-active {
  animation: cloud-appear 0.4s ease-out;
}
.ink-page-leave-active {
  transition: opacity 0.2s ease, filter 0.2s ease;
}
.ink-page-leave-to {
  opacity: 0;
  filter: blur(3px);
}

@keyframes cloud-appear {
  from { opacity: 0; transform: translateY(10px); filter: blur(3px); }
  to   { opacity: 1; transform: translateY(0); filter: blur(0); }
}

.shell-modal {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.shell-modal__mask {
  position: absolute;
  inset: 0;
  background: rgba(38, 30, 18, 0.24);
  backdrop-filter: blur(8px);
}

.shell-modal__panel {
  position: relative;
  z-index: 1;
  width: min(620px, calc(100vw - 48px));
  padding: 28px 28px 24px;
}

.shell-modal__eyebrow {
  font-family: var(--font-song);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  color: #9a948d;
  text-transform: uppercase;
}

.shell-modal__title {
  margin-top: 10px;
  font-family: var(--font-xingshu);
  font-size: 2rem;
  font-weight: 400;
  color: var(--text-primary);
}

.shell-modal__message {
  margin-top: 12px;
  font-family: var(--font-kaishu);
  font-size: 0.95rem;
  line-height: 1.8;
  color: var(--text-secondary);
}

.shell-modal__detail {
  margin-top: 10px;
  white-space: pre-line;
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--text-tertiary);
}

.shell-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 22px;
  flex-wrap: wrap;
}
</style>
