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
})
</script>

<template>
  <section class="app-sidebar-brand-card">
    <div class="app-sidebar-brand-card__crest">
      <img class="app-sidebar-brand-card__logo" src="/logo.svg" alt="AI-DataCenter logo" />
    </div>
    <div class="app-sidebar-brand-card__copy">
      <h1 class="app-sidebar-brand-card__title">{{ props.appInfo.name || 'GPU 共享治理平台' }}</h1>
      <p class="app-sidebar-brand-card__summary">
        {{ props.summary || '导入范围待确认' }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.app-sidebar-brand-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 14px 12px;
  border-radius: 22px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: linear-gradient(180deg, rgba(255, 252, 247, 0.96), rgba(246, 241, 233, 0.94));
  box-shadow: 0 10px 24px rgba(79, 59, 22, 0.04);
}

.app-sidebar-brand-card__crest {
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: inset 0 0 0 1px rgba(58, 95, 75, 0.06);
  flex-shrink: 0;
}

.app-sidebar-brand-card__logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  filter: drop-shadow(0 10px 18px rgba(6, 91, 83, 0.12));
}

.app-sidebar-brand-card__copy {
  min-width: 0;
}

.app-sidebar-brand-card__title {
  font-family: var(--font-xingshu);
  font-size: 1.16rem;
  font-weight: 400;
  color: #1a1a1a;
  letter-spacing: 0.08em;
  line-height: 1.22;
  white-space: normal;
}

.app-sidebar-brand-card__summary {
  margin-top: 5px;
  font-size: 0.77rem;
  color: #857d74;
  line-height: 1.55;
  white-space: normal;
  word-break: break-word;
}
</style>
