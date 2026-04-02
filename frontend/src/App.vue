<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { healthCheck } from './services/api'
import { useAppStore } from './stores/app'
import AppPrimarySidebar from './components/app/AppPrimarySidebar.vue'
import GlobalToast from './components/GlobalToast.vue'
import { setupInterceptor } from './services/api'
import { useWebSocket } from './composables/useWebSocket'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const currentTime = ref('')
const workspaceStatusChecked = ref(false)
const lockHint = ref('')
function baseAppInfo() {
  const webDev = Boolean(import.meta.env.DEV)
  return {
    name: 'GPU 共享治理平台',
    version: '',
    updateSupported: false,
    releasesUrl: '',
    runtimeMode: webDev ? 'web-dev' : 'web-release',
    runtimeModeLabel: webDev ? '网页开发模式' : '网页正式模式',
    connectionMode: 'local',
    connectionModeLabel: '接入模式待识别',
    frontendSourceLabel: webDev ? 'start-dev.bat / Vite 开发前端' : '网页构建前端',
    backendSourceLabel: webDev ? 'start-dev.bat / 本地后端' : '当前网页后端',
    agentSourceLabel: '由接入中心决定（本机或远程 Agent）',
    webReferenceEntry: 'start-dev.bat',
    webReferenceLabel: '网页版基准入口：start-dev.bat',
  }
}

const appInfo = ref({
  ...baseAppInfo(),
})
const updateState = ref(null)
const updateBusy = ref(false)
const closeDialog = ref(null)
const closeBusy = ref(false)
const toastRef = ref(null)
let clockTimer = null
let workspaceTimer = null
let lockHintTimer = null
let updateStateTimer = null
let removeCloseListener = null
const { connected: wsConnected, connect, disconnect } = useWebSocket({
  onRealtimeMessage: (payload) => {
    store.applyRealtimePayload(payload)
  },
  onConnectionChange: (connected) => {
    store.wsConnected = connected
  },
})

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

function applyConnectionSummary(connection) {
  if (!connection) {
    return
  }

  const connectionMode = connection.mode || appInfo.value.connectionMode || 'local'
  const isRemote = connectionMode === 'remote'
  appInfo.value = {
    ...appInfo.value,
    connectionMode,
    connectionModeLabel: connection.mode_label || (isRemote ? '远程服务器模式' : '本机模式'),
    agentSourceLabel: isRemote
      ? `${connection.agent_label || '远程 Agent'} · ${connection.agent_url || '地址待配置'}`
      : (connection.agent_label || '本机 Agent'),
  }
}

async function syncAppInfo() {
  const shellBridge = getDesktopShellBridge()
  if (!shellBridge?.getAppInfo) {
    const current = { ...appInfo.value }
    const base = baseAppInfo()
    appInfo.value = {
      ...base,
      version: current.version || '',
      connectionMode: current.connectionMode || base.connectionMode,
      connectionModeLabel: current.connectionModeLabel || base.connectionModeLabel,
      agentSourceLabel: current.agentSourceLabel || base.agentSourceLabel,
    }
    return
  }

  try {
    appInfo.value = {
      ...baseAppInfo(),
      ...await shellBridge.getAppInfo(),
    }
  } catch {}
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
    applyConnectionSummary(data?.connection)
  } catch {
    store.setWorkspaceReady(false)
  } finally {
    workspaceStatusChecked.value = true
    enforceRouteAccess(route.path)
    void syncAppInfo()
  }
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
  await syncAppInfo()

  if (!shellBridge) {
    return
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
  connect()
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
  clearTimeout(lockHintTimer)
  clearTimeout(updateStateTimer)
  removeCloseListener?.()
  disconnect()
})
</script>

<template>
  <div class="app-layout">
    <div class="app-shell">
      <aside class="app-sidebar">
        <AppPrimarySidebar
          :app-info="appInfo"
          :current-path="route.path"
          :current-time="currentTime"
          :is-desktop="isDesktop"
          :nav-items="navItems"
          :update-busy="updateBusy"
          :workspace-locked="workspaceLocked"
          :ws-connected="wsConnected"
          @check-updates="checkForUpdates"
          @navigate="navigateTo"
        />
      </aside>

      <div class="app-body">
        <div class="app-mobile-nav">
          <div class="app-mobile-nav__top">
            <div class="app-mobile-nav__brand">
              <img class="app-mobile-nav__logo" src="/logo.svg" alt="AI-DataCenter logo" />
              <div class="app-mobile-nav__brand-copy">
                <strong>{{ appInfo.name || 'GPU 共享治理平台' }}</strong>
                <span>{{ appInfo.runtimeModeLabel || (isDesktop ? '桌面模式' : '网页模式') }} · {{ wsConnected ? '实时在线' : '实时离线' }}</span>
              </div>
            </div>
            <button
              v-if="isDesktop"
              type="button"
              class="app-mobile-nav__update"
              :disabled="updateBusy"
              @click="checkForUpdates"
            >
              {{ updateBusy ? '检查中...' : '检查更新' }}
            </button>
          </div>
          <div class="app-mobile-nav__rail">
            <button
              v-for="item in navItems"
              :key="item.path"
              type="button"
              class="app-mobile-nav__item"
              :class="{
                'app-mobile-nav__item--active': route.path === item.path || (item.path !== '/' && route.path.startsWith(item.path)),
                'app-mobile-nav__item--locked': workspaceLocked && item.path !== '/',
              }"
              :title="workspaceLocked && item.path !== '/' ? `请先接入 Agent，再打开${item.label}` : item.desc"
              @click="navigateTo(item)"
            >
              <span class="app-mobile-nav__seal">{{ item.icon }}</span>
              <span class="app-mobile-nav__label">{{ item.label }}</span>
            </button>
          </div>
        </div>

        <div class="app-content">
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
              <transition name="ink-page">
                <component :is="Component" />
              </transition>
            </router-view>
          </main>
        </div>
      </div>

      <div class="side-deco">
        <span class="side-deco__text">绿色计算</span>
      </div>
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
  width: 100%;
  height: 100vh;
  overflow: hidden;
  position: relative;
}

.app-shell {
  display: grid;
  grid-template-columns: 268px minmax(0, 1fr);
  width: 100%;
  height: 100%;
  background:
    radial-gradient(circle at top left, rgba(58, 95, 75, 0.05), transparent 24%),
    radial-gradient(circle at bottom right, rgba(91, 75, 140, 0.05), transparent 28%),
    linear-gradient(180deg, rgba(248, 245, 240, 0.96), rgba(244, 240, 234, 0.88));
}

.app-sidebar {
  display: flex;
  min-height: 0;
  padding: 24px 18px;
  border-right: 1px solid rgba(26, 26, 26, 0.06);
  background: rgba(248, 245, 240, 0.92);
  overflow: hidden;
}

.app-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  position: relative;
}

.app-content {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.app-mobile-nav {
  display: none;
  padding: 14px 16px 10px;
  border-bottom: 1px solid rgba(26, 26, 26, 0.06);
  background: rgba(248, 245, 240, 0.94);
}

.app-mobile-nav__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.app-mobile-nav__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.app-mobile-nav__logo {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  flex-shrink: 0;
}

.app-mobile-nav__brand-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.app-mobile-nav__brand-copy strong {
  font-size: 0.92rem;
  color: var(--text-primary);
}

.app-mobile-nav__brand-copy span {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.app-mobile-nav__update {
  border: 1px solid rgba(46, 139, 87, 0.14);
  background: rgba(46, 139, 87, 0.07);
  color: #3A5F4B;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 0.7rem;
}

.app-mobile-nav__rail {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.app-mobile-nav__item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.76);
  color: var(--text-secondary);
}

.app-mobile-nav__item--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: rgba(244, 250, 247, 0.92);
}

.app-mobile-nav__item--locked {
  opacity: 0.56;
}

.app-mobile-nav__seal {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(196, 30, 58, 0.08);
  color: var(--ink-vermillion);
  font-family: var(--font-seal);
  font-size: 0.7rem;
}

.app-mobile-nav__label {
  font-size: 0.78rem;
  white-space: nowrap;
}

.app-main {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 28px 32px;
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
  font-family: var(--font-ui);
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

@media (max-width: 980px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .app-sidebar {
    display: none;
  }

  .app-mobile-nav {
    display: block;
  }

  .app-banner-stack {
    padding: 10px 16px 0;
  }

  .app-main {
    padding: 18px 16px 24px;
  }

  .side-deco {
    display: none;
  }
}

/* ===== 页面切换 - 轻量淡入出 ===== */
.ink-page-enter-active,
.ink-page-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.ink-page-enter-from,
.ink-page-leave-to {
  opacity: 0;
  transform: translateY(6px);
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
  font-family: var(--font-ui);
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
