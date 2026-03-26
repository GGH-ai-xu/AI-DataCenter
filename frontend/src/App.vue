<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from './stores/app'

const route = useRoute()
const store = useAppStore()
const wsConnected = ref(false)
const currentTime = ref('')
const currentDate = ref('')
let ws = null
let reconnectTimer = null
let clockTimer = null

const navItems = [
  { path: '/', label: '工作台', icon: '台', en: 'Desk' },
  { path: '/scheduler', label: '治理台', icon: '治', en: 'Control' },
  { path: '/tasks', label: '处置台', icon: '令', en: 'Action' },
  { path: '/alerts', label: '风险台', icon: '警', en: 'Risk' },
  { path: '/energy', label: '复盘台', icon: '证', en: 'Replay' },
  { path: '/monitor', label: '观察台', icon: '察', en: 'Observe' },
  { path: '/ai', label: '助手', icon: '智', en: 'Copilot' },
]

const routeScenes = {
  '/': {
    kicker: '工作台',
    title: '先判断，再执行，再回放',
    desc: '把预算、风险、用户公平性与真实处置动作汇到同一桌面，让平台先像治理台，再像看板。',
    quote: '先有处置能力，后有展示价值。',
  },
  '/tasks': {
    kicker: '处置台',
    title: '围绕真实进程，做暂停、恢复、终止与分级',
    desc: '把谁该让路、谁该保留、谁该被约束落到真实动作，不让治理停留在建议层。',
    quote: '没有处置动作，治理就只是评论。',
  },
  '/scheduler': {
    kicker: '治理台',
    title: '把总功率预算、规则和调度动作收进一个控制面',
    desc: '你可以在这里启动预算治理、执行一次调度、限制功耗上限，并观察动作是否真正落地。',
    quote: '治理不是看见问题，而是让系统按规则行动。',
  },
  '/energy': {
    kicker: '复盘台',
    title: '把功耗、节能和调度效果沉淀成证据链',
    desc: '这里负责回答一个关键问题: 动作之后，到底节了多少电，是否真的更稳、更公平。',
    quote: '没有量化复盘，治理就难以服众。',
  },
  '/monitor': {
    kicker: '观察台',
    title: '把系统、用户、训练和任务时间线连成一张证据图',
    desc: '它不是用来堆指标，而是用来辅助判断: 当前异常来自哪里，治理前后发生了什么变化。',
    quote: '先把证据看全，再下结论。',
  },
  '/ai': {
    kicker: '助手台',
    title: '把运行数据、治理策略和报告生成交给同一个副驾驶',
    desc: '当你需要快速解释现场、总结风险或生成表达材料时，助手承担的是运维副驾而不是聊天挂件。',
    quote: '助手的价值，在于缩短判断到表达的距离。',
  },
  '/alerts': {
    kicker: '风险台',
    title: '把高温、超额和异常事件整理成可处置的风险队列',
    desc: '风险页不只是看红点，而是帮助你判断什么要立刻动手，什么只需继续观察。',
    quote: '风险页的价值，在于给出优先级。',
  },
  '/gpu': {
    kicker: '单卡侧写',
    title: '把单卡状态拆开看清，作为精细治理的落点',
    desc: '当你需要确认一张 GPU 是否该被限功率、是否过热、是否正在拖累预算时，这里提供最细颗粒度依据。',
    quote: '一张卡的细节，常常决定治理动作能否站住脚。',
  },
}

const activeUsers = computed(() => new Set(store.processes.map((proc) => proc.username || 'unknown')).size)
const urgentTasks = computed(() => store.processes.filter((proc) => (proc.priority || 'normal') === 'urgent').length)
const criticalAlerts = computed(() => store.alerts.filter((alert) => alert.severity === 'critical').length)

const activePath = computed(() => {
  if (route.path.startsWith('/gpu/')) return '/gpu'
  const matched = navItems.find(
    (item) => route.path === item.path || (item.path !== '/' && route.path.startsWith(item.path)),
  )
  return matched?.path || '/'
})

const activeNav = computed(() =>
  navItems.find((item) => item.path === activePath.value) || navItems[0],
)

const activeScene = computed(() => routeScenes[activePath.value] || routeScenes['/'])

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  currentDate.value = now.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
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
    } catch {}
  }
  ws.onclose = () => {
    wsConnected.value = false
    store.wsConnected = false
    reconnectTimer = setTimeout(connectWs, 10000)
  }
  ws.onerror = () => ws?.close()
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  connectWs()
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearTimeout(reconnectTimer)
  ws?.close()
})
</script>

<template>
  <div class="app-shell">
    <div class="app-shell__wash app-shell__wash--one"></div>
    <div class="app-shell__wash app-shell__wash--two"></div>
    <div class="app-shell__wash app-shell__wash--three"></div>

    <aside class="ink-rail tech-card">
      <div class="ink-rail__brand">
        <div class="logo-seal">
          <span>智</span>
          <span>算</span>
          <span>有</span>
          <span>度</span>
        </div>
        <div class="ink-brand">
          <div class="ink-brand__kicker">软件应用赛道 · 治理工作台</div>
          <h1 class="ink-brand__title">GPU 共享治理</h1>
          <p class="ink-brand__sub">DESK · CONTROL · REPLAY</p>
        </div>
      </div>

      <div class="ink-rail__note">
        <div class="ink-rail__note-label">当前视角</div>
        <p class="ink-rail__note-text">{{ activeScene.quote }}</p>
      </div>

      <div class="ink-rail__pulse">
        <div class="ink-rail__pulse-item">
          <span class="ink-rail__pulse-label">在线 GPU</span>
          <strong class="stat-value">{{ store.gpus.length }}</strong>
        </div>
        <div class="ink-rail__pulse-item">
          <span class="ink-rail__pulse-label">活跃用户</span>
          <strong class="stat-value">{{ activeUsers }}</strong>
        </div>
        <div class="ink-rail__pulse-item">
          <span class="ink-rail__pulse-label">紧急任务</span>
          <strong class="stat-value">{{ urgentTasks }}</strong>
        </div>
        <div class="ink-rail__pulse-item">
          <span class="ink-rail__pulse-label">严重告警</span>
          <strong class="stat-value">{{ criticalAlerts }}</strong>
        </div>
      </div>

      <nav class="ink-nav" aria-label="主导航">
        <router-link
          v-for="(item, index) in navItems"
          :key="item.path"
          :to="item.path"
          class="ink-nav__item"
          :class="{ 'ink-nav__item--active': activePath === item.path }"
        >
          <span class="ink-nav__index stat-value">0{{ index + 1 }}</span>
          <span class="ink-nav__stamp">{{ item.icon }}</span>
          <span class="ink-nav__copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.en }}</small>
          </span>
        </router-link>
      </nav>

      <div class="ink-rail__footer">
        <div class="ink-rail__status">
          <span class="status-badge" :class="wsConnected ? 'status-badge--ok' : 'status-badge--critical'">
            {{ wsConnected ? '实时联通' : '等待重连' }}
          </span>
          <span class="status-badge status-badge--warning">真实治理界面</span>
        </div>
        <div class="ink-rail__clock">
          <div class="ink-rail__date">{{ currentDate }}</div>
          <div class="ink-rail__time stat-value">{{ currentTime }}</div>
        </div>
      </div>

      <div class="ink-rail__vertical vertical-text">功率预算 公平治理 共享秩序</div>
    </aside>

    <section class="app-stage">
      <header class="stage-banner tech-card">
        <div class="stage-banner__body">
          <div class="stage-banner__eyebrow">{{ activeScene.kicker }} · {{ activeNav.label }}</div>
          <h2 class="stage-banner__title">{{ activeScene.title }}</h2>
          <p class="stage-banner__desc">{{ activeScene.desc }}</p>
        </div>
        <div class="stage-banner__side">
          <div class="stage-banner__quote">{{ activeScene.quote }}</div>
          <div class="stage-banner__badges">
            <span class="status-badge" :class="wsConnected ? 'status-badge--ok' : 'status-badge--critical'">
              {{ wsConnected ? '在线采集' : '连接中断' }}
            </span>
            <span class="stage-chip">{{ store.gpus.length }} 张 GPU</span>
            <span class="stage-chip">{{ activeUsers }} 位用户</span>
            <span class="stage-chip">{{ store.processes.length }} 个进程</span>
            <span class="stage-chip">{{ criticalAlerts }} 条严重风险</span>
          </div>
        </div>
        <div class="stage-banner__brush"></div>
      </header>

      <main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="ink-page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  display: grid;
  grid-template-columns: 286px minmax(0, 1fr);
  gap: 22px;
  width: 100%;
  height: 100vh;
  padding: 20px;
  overflow: hidden;
}

.app-shell__wash {
  position: fixed;
  inset: auto;
  border-radius: 999px;
  filter: blur(48px);
  pointer-events: none;
  z-index: 0;
  opacity: 0.55;
}

.app-shell__wash--one {
  top: 6%;
  right: 10%;
  width: 260px;
  height: 180px;
  background: radial-gradient(circle, rgba(46, 139, 87, 0.1) 0%, rgba(46, 139, 87, 0) 72%);
}

.app-shell__wash--two {
  bottom: 8%;
  left: 22%;
  width: 320px;
  height: 220px;
  background: radial-gradient(circle, rgba(196, 30, 58, 0.06) 0%, rgba(196, 30, 58, 0) 72%);
}

.app-shell__wash--three {
  bottom: 18%;
  right: 14%;
  width: 220px;
  height: 220px;
  background: radial-gradient(circle, rgba(212, 175, 55, 0.09) 0%, rgba(212, 175, 55, 0) 72%);
}

.ink-rail,
.stage-banner,
.app-main {
  position: relative;
  z-index: 1;
}

.ink-rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 22px 18px 18px;
  gap: 20px;
}

.ink-rail__brand {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.logo-seal {
  width: 58px;
  height: 58px;
  border: 2px solid var(--ink-vermillion);
  border-radius: 6px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  align-items: center;
  justify-items: center;
  padding: 6px;
  color: var(--ink-vermillion);
  font-family: var(--font-seal);
  font-size: 0.8rem;
  transform: rotate(-6deg);
  box-shadow: 0 12px 26px rgba(196, 30, 58, 0.08);
}

.ink-brand__kicker {
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.ink-brand__title {
  margin-top: 8px;
  font-family: var(--font-caoshu);
  font-size: clamp(2rem, 2.8vw, 2.7rem);
  line-height: 1;
  color: var(--text-primary);
}

.ink-brand__sub {
  margin-top: 6px;
  font-family: var(--font-song);
  font-size: 0.68rem;
  letter-spacing: 0.28em;
  color: var(--text-muted);
}

.ink-rail__note {
  padding: 14px 14px 12px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.64), rgba(255, 255, 255, 0.3));
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.ink-rail__note-label {
  font-size: 0.72rem;
  color: var(--text-muted);
  letter-spacing: 0.18em;
}

.ink-rail__note-text {
  margin-top: 8px;
  font-family: var(--font-xingcao);
  font-size: 1.2rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.ink-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ink-rail__pulse {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.ink-rail__pulse-item {
  padding: 12px 12px 10px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.66), rgba(255, 255, 255, 0.32));
  border: 1px solid rgba(58, 95, 75, 0.08);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ink-rail__pulse-label {
  font-size: 0.68rem;
  color: var(--text-muted);
  letter-spacing: 0.14em;
}

.ink-rail__pulse-item strong {
  font-size: 1.18rem;
  color: var(--text-primary);
}

.ink-nav__item {
  display: grid;
  grid-template-columns: 36px 34px 1fr;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  padding: 10px 10px 10px 12px;
  border-radius: 16px;
  border: 1px solid transparent;
  transition: transform 0.24s ease, border-color 0.24s ease, background 0.24s ease;
}

.ink-nav__item:hover {
  transform: translateX(3px);
  border-color: rgba(58, 95, 75, 0.12);
  background: rgba(255, 255, 255, 0.48);
}

.ink-nav__item--active {
  border-color: rgba(196, 30, 58, 0.14);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(196, 30, 58, 0.05));
}

.ink-nav__index {
  font-size: 0.78rem;
  color: rgba(26, 26, 26, 0.3);
}

.ink-nav__stamp {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid rgba(58, 95, 75, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-seal);
  font-size: 0.9rem;
  color: var(--accent-primary);
  background: rgba(255, 255, 255, 0.58);
}

.ink-nav__item--active .ink-nav__stamp {
  color: var(--ink-vermillion);
  border-color: rgba(196, 30, 58, 0.18);
}

.ink-nav__copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.ink-nav__copy strong {
  font-family: var(--font-xingshu);
  font-size: 1rem;
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: 0.08em;
}

.ink-nav__copy small {
  font-family: var(--font-song);
  font-size: 0.64rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--text-muted);
}

.ink-rail__footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ink-rail__status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ink-rail__clock {
  padding-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.ink-rail__date {
  font-size: 0.74rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.ink-rail__time {
  margin-top: 6px;
  font-size: 1.32rem;
  color: var(--text-primary);
}

.ink-rail__vertical {
  position: absolute;
  right: 10px;
  top: 84px;
  font-family: var(--font-xingcao);
  font-size: 0.88rem;
  letter-spacing: 0.34em;
  color: rgba(0, 0, 0, 0.1);
  pointer-events: none;
}

.app-stage {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  gap: 18px;
}

.stage-banner {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18px;
  min-height: 142px;
  padding: 22px 26px;
}

.stage-banner__body {
  flex: 1;
  min-width: 0;
}

.stage-banner__eyebrow {
  font-size: 0.74rem;
  color: var(--text-muted);
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.stage-banner__title {
  margin-top: 10px;
  font-family: var(--font-xingshu);
  font-size: clamp(1.8rem, 3.5vw, 2.7rem);
  line-height: 1.1;
  color: var(--text-primary);
}

.stage-banner__desc {
  max-width: 880px;
  margin-top: 10px;
  font-size: 0.95rem;
  line-height: 1.85;
  color: var(--text-secondary);
}

.stage-banner__side {
  width: min(340px, 34%);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  gap: 14px;
}

.stage-banner__quote {
  font-family: var(--font-xingcao);
  font-size: 1.16rem;
  color: var(--accent-primary);
  text-align: right;
  line-height: 1.6;
}

.stage-banner__badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.stage-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(58, 95, 75, 0.08);
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.stage-banner__brush {
  position: absolute;
  left: 26px;
  right: 26px;
  bottom: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(26, 26, 26, 0.06) 12%,
    rgba(26, 26, 26, 0.12) 42%,
    rgba(46, 139, 87, 0.18) 60%,
    rgba(26, 26, 26, 0.05) 84%,
    transparent
  );
}

.app-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 6px;
}

.ink-page-enter-active {
  animation: cloud-appear 0.42s ease-out;
}

.ink-page-leave-active {
  transition: opacity 0.22s ease, filter 0.22s ease;
}

.ink-page-leave-to {
  opacity: 0;
  filter: blur(4px);
}

@keyframes cloud-appear {
  from {
    opacity: 0;
    transform: translateY(12px);
    filter: blur(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
    filter: blur(0);
  }
}

@media (max-width: 1180px) {
  .app-shell {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 14px;
  }

  .ink-rail {
    gap: 16px;
    padding: 18px 16px;
  }

  .ink-nav {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .ink-rail__pulse {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .ink-nav__item {
    grid-template-columns: 24px 28px 1fr;
    padding: 10px;
  }

  .ink-rail__vertical {
    display: none;
  }

  .stage-banner {
    flex-direction: column;
    min-height: auto;
  }

  .stage-banner__side {
    width: 100%;
    align-items: flex-start;
  }

  .stage-banner__quote,
  .stage-banner__badges {
    text-align: left;
    justify-content: flex-start;
  }
}

@media (max-width: 780px) {
  .app-shell {
    padding: 10px;
  }

  .ink-rail__brand {
    flex-direction: column;
  }

  .logo-seal {
    width: 50px;
    height: 50px;
  }

  .ink-nav {
    display: flex;
    flex-direction: row;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .ink-nav__item {
    min-width: 162px;
    flex: 0 0 auto;
  }

  .stage-banner {
    padding: 18px 18px 20px;
  }

  .stage-banner__title {
    font-size: 1.65rem;
  }

  .stage-banner__desc {
    font-size: 0.88rem;
  }
}
</style>
