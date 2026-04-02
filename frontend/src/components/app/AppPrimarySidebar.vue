<script setup>
const props = defineProps({
  appInfo: {
    type: Object,
    required: true,
  },
  currentPath: {
    type: String,
    required: true,
  },
  currentTime: {
    type: String,
    required: true,
  },
  isDesktop: {
    type: Boolean,
    required: true,
  },
  navItems: {
    type: Array,
    required: true,
  },
  updateBusy: {
    type: Boolean,
    required: true,
  },
  workspaceLocked: {
    type: Boolean,
    required: true,
  },
  wsConnected: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['check-updates', 'navigate'])

function isActive(path) {
  return props.currentPath === path || (path !== '/' && props.currentPath.startsWith(path))
}
</script>

<template>
  <div class="app-primary-sidebar">
    <div class="app-primary-sidebar__brand">
      <img class="app-primary-sidebar__logo" src="/logo.svg" alt="AI-DataCenter logo" />
      <div class="app-primary-sidebar__brand-copy">
        <h1 class="app-primary-sidebar__title">{{ props.appInfo.name || 'GPU 共享治理平台' }}</h1>
        <p class="app-primary-sidebar__sub">
          {{ props.workspaceLocked ? 'CONNECT FIRST · UNLOCK LATER' : 'LAB · OPS · POWER BUDGET' }}
        </p>
      </div>
    </div>

    <nav class="app-primary-sidebar__nav">
      <button
        v-for="item in props.navItems"
        :key="item.path"
        type="button"
        class="app-primary-nav__item"
        :class="{
          'app-primary-nav__item--active': isActive(item.path),
          'app-primary-nav__item--locked': props.workspaceLocked && item.path !== '/',
        }"
        :title="props.workspaceLocked && item.path !== '/' ? `请先接入 Agent，再打开${item.label}` : item.desc"
        @click="emit('navigate', item)"
      >
        <span class="app-primary-nav__seal">{{ item.icon }}</span>
        <span class="app-primary-nav__body">
          <strong class="app-primary-nav__label">{{ item.label }}</strong>
          <span class="app-primary-nav__desc">{{ item.desc }}</span>
        </span>
      </button>
    </nav>

    <div class="app-primary-sidebar__footer">
      <div v-if="props.isDesktop" class="app-primary-sidebar__desktop">
        <span class="app-primary-sidebar__version">v{{ props.appInfo.version || '1.1.0' }}</span>
        <button
          type="button"
          class="app-primary-sidebar__action"
          :disabled="props.updateBusy"
          @click="emit('check-updates')"
        >
          {{ props.updateBusy ? '检查中...' : '检查更新' }}
        </button>
      </div>
      <div
        class="app-primary-sidebar__status"
        :class="props.wsConnected ? 'app-primary-sidebar__status--on' : 'app-primary-sidebar__status--off'"
      >
        <span class="app-primary-sidebar__dot"></span>
        {{ props.wsConnected ? '实时通道在线' : '实时通道离线' }}
      </div>
      <div class="app-primary-sidebar__clock">{{ props.currentTime }}</div>
    </div>
  </div>
</template>

<style scoped>
.app-primary-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 20px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.app-primary-sidebar__brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(26, 26, 26, 0.06);
}

.app-primary-sidebar__logo {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 14px;
  filter: drop-shadow(0 10px 18px rgba(6, 91, 83, 0.12));
}

.app-primary-sidebar__brand-copy {
  min-width: 0;
}

.app-primary-sidebar__title {
  font-family: var(--font-xingshu);
  font-size: 1.22rem;
  font-weight: 400;
  color: #1a1a1a;
  letter-spacing: 0.12em;
  line-height: 1.2;
}

.app-primary-sidebar__sub {
  margin-top: 3px;
  font-family: var(--font-song);
  font-size: 0.56rem;
  color: #a8a29b;
  letter-spacing: 0.24em;
  line-height: 1.5;
}

.app-primary-sidebar__nav {
  display: grid;
  gap: 10px;
  min-height: 0;
  align-content: start;
  overflow-y: auto;
  padding-right: 4px;
}

.app-primary-nav__item {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  width: 100%;
  padding: 14px 14px 13px;
  border-radius: 18px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.76);
  color: var(--text-secondary);
  text-align: left;
  transition: border-color 0.24s ease, transform 0.24s ease, background 0.24s ease, box-shadow 0.24s ease;
}

.app-primary-nav__item:hover {
  transform: translateY(-1px);
  border-color: rgba(58, 95, 75, 0.16);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-card);
}

.app-primary-nav__item--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(244, 250, 247, 0.82));
  box-shadow: 0 18px 36px rgba(46, 139, 87, 0.08);
}

.app-primary-nav__item--locked {
  opacity: 0.56;
}

.app-primary-nav__seal {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid rgba(196, 30, 58, 0.16);
  color: var(--ink-vermillion);
  background: rgba(255, 255, 255, 0.76);
  font-family: var(--font-seal);
  flex-shrink: 0;
}

.app-primary-nav__item--active .app-primary-nav__seal {
  background: rgba(196, 30, 58, 0.08);
}

.app-primary-nav__body {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.app-primary-nav__label {
  font-size: 0.88rem;
  color: var(--text-primary);
  line-height: 1.3;
}

.app-primary-nav__desc {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.app-primary-sidebar__footer {
  display: grid;
  gap: 12px;
  padding-top: 18px;
  border-top: 1px solid rgba(26, 26, 26, 0.06);
  background: linear-gradient(180deg, rgba(248, 245, 240, 0), rgba(248, 245, 240, 0.9) 18%, rgba(248, 245, 240, 0.98));
  position: relative;
  z-index: 1;
}

.app-primary-sidebar__desktop {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.app-primary-sidebar__version {
  font-family: var(--font-song);
  font-size: 0.75rem;
  color: #9c968f;
}

.app-primary-sidebar__action {
  border: 1px solid rgba(46, 139, 87, 0.14);
  background: rgba(46, 139, 87, 0.07);
  color: #3A5F4B;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: background 0.2s ease;
}

.app-primary-sidebar__action:hover:not(:disabled) {
  background: rgba(46, 139, 87, 0.12);
}

.app-primary-sidebar__action:disabled {
  opacity: 0.6;
  cursor: wait;
}

.app-primary-sidebar__status {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  padding: 8px 12px;
  border-radius: 14px;
  font-size: 0.72rem;
  font-family: var(--font-kaishu);
  letter-spacing: 0.08em;
  line-height: 1.5;
}

.app-primary-sidebar__status--on {
  color: #2E8B57;
  background: rgba(46, 139, 87, 0.06);
}

.app-primary-sidebar__status--off {
  color: #C41E3A;
  background: rgba(196, 30, 58, 0.06);
}

.app-primary-sidebar__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.app-primary-sidebar__status--on .app-primary-sidebar__dot {
  background: #2E8B57;
  box-shadow: 0 0 6px rgba(46, 139, 87, 0.3);
}

.app-primary-sidebar__status--off .app-primary-sidebar__dot {
  background: #C41E3A;
}

.app-primary-sidebar__clock {
  font-family: var(--font-song);
  font-size: 0.78rem;
  color: #9c968f;
  letter-spacing: 0.08em;
}

@media (max-height: 780px) {
  .app-primary-sidebar {
    gap: 16px;
  }

  .app-primary-sidebar__brand {
    padding-bottom: 14px;
  }

  .app-primary-nav__item {
    padding: 12px 13px;
  }

  .app-primary-nav__desc {
    font-size: 0.71rem;
    line-height: 1.5;
  }

  .app-primary-sidebar__footer {
    gap: 10px;
    padding-top: 14px;
  }
}
</style>
