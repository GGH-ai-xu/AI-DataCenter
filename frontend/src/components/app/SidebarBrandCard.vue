<script setup>
const props = defineProps({
  appInfo: {
    type: Object,
    required: true,
  },
  collapsed: {
    type: Boolean,
    required: true,
  },
  summary: {
    type: String,
    required: true,
  },
  switchServerBusy: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['switch-server'])
</script>

<template>
  <section
    class="app-sidebar-brand-card"
    :class="{ 'app-sidebar-brand-card--collapsed': props.collapsed }"
  >
    <div class="app-sidebar-brand-card__main">
      <div class="app-sidebar-brand-card__crest">
        <img class="app-sidebar-brand-card__logo" src="/logo.svg" alt="AI-DataCenter logo" />
      </div>
      <div
        class="app-sidebar-brand-card__copy"
        :class="{ 'app-sidebar-brand-card__copy--collapsed': props.collapsed }"
        :aria-hidden="props.collapsed ? 'true' : 'false'"
      >
        <h1 class="app-sidebar-brand-card__title">{{ props.appInfo.name || 'GPU 共享治理平台' }}</h1>
        <p class="app-sidebar-brand-card__summary">{{ props.summary || '导入范围待确认' }}</p>
      </div>
      <div class="app-sidebar-brand-card__actions">
        <button
          type="button"
          class="app-sidebar-brand-card__switch"
          :class="{ 'app-sidebar-brand-card__switch--icon': props.collapsed }"
          :disabled="props.switchServerBusy"
          :title="props.collapsed ? '切换服务器' : ''"
          :aria-label="'切换服务器'"
          @click="emit('switch-server')"
        >
          <span
            class="app-sidebar-brand-card__switch-mark"
            :class="{ 'app-sidebar-brand-card__switch-mark--hidden': !props.collapsed }"
            aria-hidden="true"
          >
            换
          </span>
          <span
            class="app-sidebar-brand-card__switch-label"
            :class="{ 'app-sidebar-brand-card__switch-label--collapsed': props.collapsed }"
          >
            {{ props.switchServerBusy ? '切换中...' : '切换服务器' }}
          </span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.app-sidebar-brand-card {
  min-width: 0;
  max-width: 100%;
  padding: 14px 15px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.03);
  transition:
    padding 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    border-radius 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    background 0.24s ease;
}

.app-sidebar-brand-card__main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  transition: gap 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-sidebar-brand-card__actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: gap 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-sidebar-brand-card__crest {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  flex-shrink: 0;
}

.app-sidebar-brand-card__logo {
  width: 24px;
  height: 24px;
  border-radius: 8px;
}

.app-sidebar-brand-card__copy {
  min-width: 0;
  flex: 1 1 auto;
  max-width: 180px;
  max-height: 56px;
  overflow: hidden;
  opacity: 1;
  transform: translateX(0);
  transition:
    max-width 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    max-height 0.26s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.18s ease,
    transform 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-sidebar-brand-card__copy--collapsed {
  flex: 0 0 auto;
  max-width: 0;
  max-height: 0;
  opacity: 0;
  transform: translateY(-6px);
  pointer-events: none;
}

.app-sidebar-brand-card__title {
  font-family: var(--font-ui);
  font-size: 0.94rem;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.app-sidebar-brand-card__summary {
  margin-top: 4px;
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.35;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.app-sidebar-brand-card__switch {
  flex-shrink: 0;
  max-width: 100%;
  min-height: 32px;
  padding: 0 11px;
  border-radius: 999px;
  border: 1px solid rgba(94, 106, 210, 0.26);
  background: rgba(94, 106, 210, 0.14);
  color: #dbe0ff;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.2;
  transition:
    background 0.24s ease,
    border-color 0.24s ease,
    opacity 0.24s ease,
    transform 0.24s var(--ease-expo),
    padding 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    min-width 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    gap 0.34s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}

.app-sidebar-brand-card__switch:hover:not(:disabled) {
  transform: translateY(-1px);
  background: rgba(94, 106, 210, 0.2);
  border-color: rgba(94, 106, 210, 0.34);
}

.app-sidebar-brand-card__switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.app-sidebar-brand-card__switch-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  max-width: 14px;
  max-height: 18px;
  overflow: hidden;
  opacity: 1;
  transform: translateX(0) scale(1);
  transition:
    max-width 0.26s cubic-bezier(0.22, 1, 0.36, 1),
    max-height 0.2s ease,
    opacity 0.18s ease,
    transform 0.26s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-sidebar-brand-card__switch-mark--hidden {
  max-width: 0;
  max-height: 0;
  opacity: 0;
  transform: translateX(6px) scale(0.82);
}

.app-sidebar-brand-card__switch-label {
  max-width: 120px;
  max-height: 20px;
  overflow: hidden;
  white-space: nowrap;
  opacity: 1;
  transform: translateX(0);
  transition:
    max-width 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    max-height 0.2s ease,
    opacity 0.18s ease,
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-sidebar-brand-card__switch-label--collapsed {
  max-width: 0;
  max-height: 0;
  opacity: 0;
  transform: translateX(-8px);
}

.app-sidebar-brand-card__switch--icon {
  min-width: 32px;
  padding: 0;
  justify-content: center;
}

.app-sidebar-brand-card__switch:disabled {
  opacity: 0.6;
  cursor: wait;
}

.app-sidebar-brand-card--collapsed {
  padding: 12px 8px;
}

.app-sidebar-brand-card--collapsed .app-sidebar-brand-card__main {
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.app-sidebar-brand-card--collapsed .app-sidebar-brand-card__actions {
  margin-left: 0;
  width: 100%;
  justify-content: center;
}
</style>
