<script setup>
const props = defineProps({
  appInfo: {
    type: Object,
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
  <section class="app-sidebar-brand-card">
    <div class="app-sidebar-brand-card__eyebrow">GPU Governance OS</div>
    <div class="app-sidebar-brand-card__main">
      <div class="app-sidebar-brand-card__crest">
        <img class="app-sidebar-brand-card__logo" src="/logo.svg" alt="AI-DataCenter logo" />
      </div>
      <div class="app-sidebar-brand-card__copy">
        <h1 class="app-sidebar-brand-card__title">{{ props.appInfo.name || 'GPU 共享治理平台' }}</h1>
        <p class="app-sidebar-brand-card__summary">
          {{ props.summary || '导入范围待确认' }}
        </p>
      </div>
    </div>
    <div class="app-sidebar-brand-card__meta">
      <span class="app-sidebar-brand-card__pill">
        {{ props.appInfo.connectionModeLabel || '导入模式待识别' }}
      </span>
      <span class="app-sidebar-brand-card__pill">
        {{ props.appInfo.runtimeModeLabel || '运行模式待识别' }}
      </span>
    </div>
    <p class="app-sidebar-brand-card__detail">
      {{ props.appInfo.agentSourceLabel || '由导入层决定接入范围与 Agent 来源。' }}
    </p>
    <button
      type="button"
      class="app-sidebar-brand-card__switch"
      :disabled="props.switchServerBusy"
      @click="emit('switch-server')"
    >
      {{ props.switchServerBusy ? '切换中...' : '切换服务器' }}
    </button>
  </section>
</template>

<style scoped>
.app-sidebar-brand-card {
  display: grid;
  gap: 16px;
  padding: 20px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: #121a24;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
}

.app-sidebar-brand-card__eyebrow {
  font-family: var(--font-seal);
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.app-sidebar-brand-card__main {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.app-sidebar-brand-card__crest {
  width: 52px;
  height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: #0e151d;
  flex-shrink: 0;
}

.app-sidebar-brand-card__logo {
  width: 34px;
  height: 34px;
  border-radius: 10px;
}

.app-sidebar-brand-card__copy {
  min-width: 0;
}

.app-sidebar-brand-card__title {
  font-family: var(--font-ui);
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1.18;
  letter-spacing: -0.03em;
  color: var(--text-primary);
  white-space: normal;
}

.app-sidebar-brand-card__summary {
  margin-top: 8px;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: normal;
  word-break: break-word;
}

.app-sidebar-brand-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.app-sidebar-brand-card__pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  font-size: 0.68rem;
  line-height: 1.2;
  letter-spacing: 0.08em;
}

.app-sidebar-brand-card__detail {
  font-size: 0.78rem;
  line-height: 1.65;
  color: var(--text-tertiary);
}

.app-sidebar-brand-card__switch {
  min-height: 42px;
  width: 100%;
  border-radius: 12px;
  border: 1px solid transparent;
  background: #5e6ad2;
  color: #ffffff;
  font-size: 0.82rem;
  font-weight: 600;
  line-height: 1.2;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 10px 24px rgba(94, 106, 210, 0.22);
  transition:
    background 0.24s ease,
    box-shadow 0.24s ease,
    opacity 0.24s ease,
    transform 0.24s var(--ease-expo);
}

.app-sidebar-brand-card__switch:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #6872d9;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    0 14px 28px rgba(94, 106, 210, 0.26);
}

.app-sidebar-brand-card__switch:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>
